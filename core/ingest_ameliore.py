"""
ingest_ameliore.py — Ingestion structurée pour documents tabulaires.

Remplace le découpage par paquets de 900 caractères (qui a donné 5/16 au test
des 20 questions) par une extraction géométrique des tableaux via pdfplumber :
chaque LIGNE de tableau devient une fiche autonome, où chaque valeur est
étiquetée par son en-tête de colonne. La récupération retrouve alors la bonne
fiche au lieu de colonnes éparpillées.

Trois cas gérés :
  - tableaux (catalogue, grille, procédure) : une ligne = un chunk étiqueté ;
  - texte hors tableau (titres, paragraphes) : nettoyé de la boilerplate
    répétée, puis découpé par paragraphes ;
  - document sans tableau : repli complet sur rag_core.chunk_text.

N'écrase rien dans rag_core : on branche build_index_ameliore() seulement après
que le test des 20 questions l'a validé.
"""

from __future__ import annotations

import os
import re
import glob
from collections import Counter

import pdfplumber

import rag_core

# Lots envoyés à Chroma (qui déclenche l'embedding). Petit = pic mémoire
# faible pendant l'indexation à chaud dans le container (1 Go sur Railway).
ADD_BATCH = int(os.environ.get("ADD_BATCH", "16"))


# --------------------------------------------------------------------------- #
# Boilerplate : paragraphes répétés, sans valeur informative
# --------------------------------------------------------------------------- #

_UTILE = re.compile(
    r"\d|EUR|€|jour|mois|garantie|livraison|commande|minimale|validité|"
    r"catégorie|prix|stock|essentiel|pro|premium|délai|étape|responsable",
    re.IGNORECASE,
)


def _boilerplate(textes_pages: list[str], seuil: float = 0.5) -> set[str]:
    n = len(textes_pages)
    presence = Counter()
    for txt in textes_pages:
        for l in set(l.strip() for l in txt.split("\n") if l.strip()):
            presence[l] += 1
    bruit = set()
    for ligne, cnt in presence.items():
        if cnt >= max(2, seuil * n) and len(ligne) >= 30 and not _UTILE.search(ligne):
            bruit.add(ligne)
    return bruit


# --------------------------------------------------------------------------- #
# Tableaux → fiches étiquetées
# --------------------------------------------------------------------------- #

def _ligne_en_fiche(entetes: list[str], row: list[str]) -> str:
    paires = []
    for h, c in zip(entetes, row):
        h = (h or "").strip().replace("\n", " ")
        c = (c or "").strip().replace("\n", " ")
        if c:
            paires.append(f"{h} : {c}" if h else c)
    return " — ".join(paires)


def _entetes_valides(entetes: list[str]) -> bool:
    remplies = [e for e in entetes if e and e.strip()]
    return len(remplies) >= 2


_CODE = re.compile(r"^[A-Z]{2,4}-\d{3,5}$")
# pied de page global du catalogue, à ne pas prendre pour une fiche produit
_PIED_CATALOGUE = re.compile(r"commande minimale|livraison standard|150 EUR HT", re.IGNORECASE)


def _fiches_par_geometrie(page) -> list[str]:
    """Catalogue à colonnes : chaque mini-tableau (Catégorie/Prix/Stock) est
    rattaché au code produit le plus proche AU-DESSUS de lui (proximité x + y).
    Résout le désordre dû à la mise en page sur deux colonnes."""
    codes = []
    for w in page.extract_words():
        if _CODE.match(w["text"]):
            codes.append((w["text"], w["x0"], w["top"]))
    if not codes:
        return []
    fiches = []
    for t in page.find_tables():
        data = t.extract()
        if len(data) < 2 or not data[1]:
            continue
        entetes = [(c or "").strip() for c in data[0]]
        valeurs = " — ".join(f"{h} : {c.strip()}" for h, c in zip(entetes, data[1])
                              if c and c.strip())
        if _PIED_CATALOGUE.search(valeurs):
            continue
        x0, top = t.bbox[0], t.bbox[1]
        best, bestd = None, 1e9
        for ref, cx, cy in codes:
            if cy <= top:
                d = abs(cx - x0) + 0.3 * abs(cy - top)
                if d < bestd:
                    bestd, best = d, ref
        if best and valeurs:
            fiches.append(f"Référence produit : {best} — {valeurs}")
    return fiches


def chunks_pdf(path: str) -> tuple[list[str], str]:
    """Retourne (chunks, méthode).

    Voie principale : extraction géométrique des tableaux via pdfplumber.
    Si le PDF la met en échec (fichier partiellement corrompu, structure
    exotique), on se rabat sur l'extraction texte simple de pypdf plutôt que
    de perdre le document."""
    try:
        return _chunks_pdf_pdfplumber(path)
    except Exception as e:
        print(f"  ! pdfplumber a échoué sur {os.path.basename(path)} ({e}) — "
              f"repli sur l'extraction texte simple.")
    try:
        texte = (rag_core._read_pdf(path) or "").strip()
    except Exception:
        texte = ""
    if not texte:
        raise ValueError(
            "PDF illisible : aucun texte n'a pu en être extrait. Le fichier est "
            "peut-être corrompu ; s'il s'agit d'un document scanné, il faut "
            "d'abord le passer à l'OCR.")
    return rag_core.chunk_text(texte), "paragraphes (repli)"


def _chunks_pdf_pdfplumber(path: str) -> tuple[list[str], str]:
    fiches: list[str] = []
    textes_hors_tableau: list[str] = []

    with pdfplumber.open(path) as pdf:
        textes_pages = [p.extract_text() or "" for p in pdf.pages]
        bruit = _boilerplate(textes_pages)

        # Un catalogue à colonnes se reconnaît : beaucoup de codes produits, et
        # des mini-tableaux 3 colonnes. On tente d'abord la voie géométrique.
        codes_totaux = sum(
            1 for pg in pdf.pages for w in pg.extract_words() if _CODE.match(w["text"]))

        for page in pdf.pages:
            fiches_geo = _fiches_par_geometrie(page) if codes_totaux >= 10 else []
            if fiches_geo:
                fiches.extend(fiches_geo)
            else:
                # grille / manuel : tableaux à en-tête, une ligne = une fiche
                for t in page.extract_tables():
                    if not t or len(t) < 2:
                        continue
                    entetes = [(c or "").strip() for c in t[0]]
                    for row in t[1:]:
                        fiche = _ligne_en_fiche(entetes, row)
                        if fiche and _UTILE.search(fiche):
                            fiches.append(fiche)

            txt = page.extract_text() or ""
            gardees = [l.strip() for l in txt.split("\n")
                       if l.strip() and l.strip() not in bruit]
            if gardees:
                textes_hors_tableau.append("\n".join(gardees))

    if fiches:
        prose = rag_core.chunk_text("\n\n".join(textes_hors_tableau)) if textes_hors_tableau else []
        return fiches + prose, "tableau+prose"

    texte = "\n\n".join(textes_hors_tableau)
    return rag_core.chunk_text(texte), "paragraphes"


# --------------------------------------------------------------------------- #
# Chargement générique + indexation
# --------------------------------------------------------------------------- #

def chunks_document(path: str) -> tuple[list[str], str]:
    """Découpe UN document, quel que soit son format supporté.

    Lève une exception explicite si le fichier est illisible : l'appelant
    (upload, indexation) doit pouvoir afficher un message net à l'utilisateur."""
    if os.path.splitext(path)[1].lower() == ".pdf":
        return chunks_pdf(path)
    texte = rag_core.lire_document(path)
    if not texte:
        return [], "vide"
    return rag_core.chunk_text(texte), "paragraphes"

# --- Indexation incrémentale (upload / suppression) ------------------------ #

def _ouvrir_collection(chroma_dir: str = None, embedding_function=None):
    """Ouvre (ou crée) la collection Chroma avec la même fonction d'embedding
    que le reste du pipeline."""
    import chromadb
    chroma_dir = chroma_dir or rag_core.CHROMA_DIR
    client = chromadb.PersistentClient(path=chroma_dir)
    ef = embedding_function or rag_core.get_embedding_function()
    return client.get_or_create_collection(
        name=rag_core.COLLECTION_NAME, embedding_function=ef,
        metadata={"hnsw:space": "cosine"})


def index_file(path: str, chroma_dir: str = None, embedding_function=None) -> int:
    """Indexe UN fichier. Supprime d'abord ses anciens vecteurs (un ré-upload du
    même nom vaut donc mise à jour propre), puis ajoute les nouveaux chunks.
    Retourne le nombre de chunks indexés."""
    source = os.path.basename(path)
    col = _ouvrir_collection(chroma_dir, embedding_function)
    try:
        col.delete(where={"source": source})
    except Exception:
        pass
    chunks, _methode = chunks_document(path)
    if not chunks:
        return 0
    ids = [f"{source}::chunk-{i}" for i in range(len(chunks))]
    metas = [{"source": source, "chunk": i} for i in range(len(chunks))]
    for i in range(0, len(chunks), ADD_BATCH):
        col.add(ids=ids[i:i+ADD_BATCH], documents=chunks[i:i+ADD_BATCH],
                metadatas=metas[i:i+ADD_BATCH])
    return len(chunks)


def deindex_file(source: str, chroma_dir: str = None, embedding_function=None) -> None:
    """Supprime de l'index tous les vecteurs d'un fichier (par son nom)."""
    col = _ouvrir_collection(chroma_dir, embedding_function)
    col.delete(where={"source": os.path.basename(source)})

def build_index_ameliore(data_dir: str = None, chroma_dir: str = None,
                         embedding_function=None, reset: bool = True,
                         verbeux: bool = True) -> int:
    import chromadb
    data_dir = data_dir or rag_core.DATA_DIR
    chroma_dir = chroma_dir or rag_core.CHROMA_DIR

    client = chromadb.PersistentClient(path=chroma_dir)
    if reset:
        try:
            client.delete_collection(rag_core.COLLECTION_NAME)
        except Exception:
            pass
    ef = embedding_function or rag_core.get_embedding_function()
    collection = client.get_or_create_collection(
        name=rag_core.COLLECTION_NAME, embedding_function=ef,
        metadata={"hnsw:space": "cosine"})

    paths = []
    for ext in (".pdf", ".md", ".txt", ".docx"):
        paths += glob.glob(os.path.join(data_dir, f"*{ext}"))
    paths = sorted(set(paths))
    if not paths:
        raise RuntimeError(f"Aucun document dans '{data_dir}'.")

    ids, texts, metas = [], [], []
    for path in paths:
        source = os.path.basename(path)
        # Un document illisible est signalé puis ignoré : il ne doit pas faire
        # échouer l'indexation de tout le corpus.
        try:
            chunks, methode = chunks_document(path)
        except Exception as e:
            print(f"  ! {source:48s} ignoré — {e}")
            continue
        if verbeux:
            print(f"  {source:48s} {len(chunks):4d} chunks  ({methode})")
        for i, ch in enumerate(chunks):
            ids.append(f"{source}::chunk-{i}")
            texts.append(ch)
            metas.append({"source": source, "chunk": i})

    for i in range(0, len(texts), ADD_BATCH):
        collection.add(ids=ids[i:i+ADD_BATCH], documents=texts[i:i+ADD_BATCH],
                       metadatas=metas[i:i+ADD_BATCH])
    return len(texts)


if __name__ == "__main__":
    print("Indexation améliorée (pdfplumber) en cours...")
    n = build_index_ameliore()
    print(f"OK — {n} chunks indexés.")