"""
ingest_ameliore.py — Ingestion structurée pour documents tabulaires.

Remplace le découpage par paquets de 900 caractères (insuffisant sur les
tableaux multi-colonnes) par une extraction géométrique des tableaux via pdfplumber :
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
from itertools import groupby

import pdfplumber

import rag_core

# Lots envoyés à Chroma (qui déclenche l'embedding). Petit = pic mémoire
# faible pendant l'indexation à chaud dans le container (1 Go sur Railway).
ADD_BATCH = int(os.environ.get("ADD_BATCH", "16"))


# --------------------------------------------------------------------------- #
# Boilerplate : paragraphes répétés, sans valeur informative
# --------------------------------------------------------------------------- #

# Sert UNIQUEMENT à protéger de la détection de boilerplate une ligne répétée
# qui porte de l'information. Ce vocabulaire vient d'une démonstration
# abandonnée (catalogue de produits) : il ne doit plus servir à décider ce qui
# entre dans l'index. Reste à remplacer ici aussi par une règle neutre.
_UTILE = re.compile(
    r"\d|EUR|€|jour|mois|garantie|livraison|commande|minimale|validité|"
    r"catégorie|prix|stock|essentiel|pro|premium|délai|étape|responsable",
    re.IGNORECASE,
)

# Cellules remplies exigées pour qu'une ligne de tableau devienne une fiche.
# En dessous, il ne reste qu'un fragment de ligne repliée, sans son libellé ou
# sans sa valeur : l'indexer n'aide personne, et il brouille la recherche.
CELLULES_MIN = 2


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
    """Voie de repli (tableaux à filets). Retourne "" sous CELLULES_MIN."""
    paires = []
    for h, c in zip(entetes, row):
        h = (h or "").strip().replace("\n", " ")
        c = (c or "").strip().replace("\n", " ")
        if c:
            paires.append(f"{h} : {c}" if h else c)
    if len(paires) < CELLULES_MIN:
        return ""
    return " — ".join(paires)


def _entetes_valides(entetes: list[str]) -> bool:
    remplies = [e for e in entetes if e and e.strip()]
    return len(remplies) >= 2


_CODE = re.compile(r"^[A-Z]{2,4}-\d{3,5}$")
# pied de page global du catalogue, à ne pas prendre pour une fiche produit
_PIED_CATALOGUE = re.compile(r"commande minimale|livraison standard|150 EUR HT", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Tableaux sans filets : reconstruction des colonnes par position horizontale
# --------------------------------------------------------------------------- #
# Constat de la recette Horizon du 09/09/2026. Les tableaux de ces PDF n'ont
# aucun trait de séparation : pdfplumber renvoie alors UNE seule colonne par
# ligne, et la fiche produite ressemble à
#     « Tranche Zone A Zone B Zone C : De 250 001 € à 400 000 € 4,5 % 4,2 % 4,0 % »
# où plus rien ne relie un en-tête à sa valeur. L'assistant a lu 5,0 % au lieu
# de 4,2 % — la valeur de la ligne du dessus. On reconstruit donc les colonnes
# à partir des abscisses des mots, ce qui donne
#     « Tranche : De 250 001 € à 400 000 € — Zone A : 4,5 % — Zone B : 4,2 % … »

def _lignes_de_mots(page, bbox, tol_y=2.5):
    """Mots du tableau, regroupés en lignes visuelles."""
    x0, t0, x1, t1 = bbox
    mots = [m for m in page.extract_words(x_tolerance=1.5, y_tolerance=2)
            if m["x0"] >= x0 - 2 and m["x1"] <= x1 + 2
            and m["top"] >= t0 - 2 and m["bottom"] <= t1 + 2]
    mots.sort(key=lambda m: (round(m["top"] / tol_y), m["x0"]))
    return [sorted(g, key=lambda m: m["x0"])
            for _, g in groupby(mots, key=lambda m: round(m["top"] / tol_y))]


def _blocs(ligne, ecart=12):
    """Découpe une ligne là où un blanc dépasse `ecart` points."""
    blocs, cur = [], [ligne[0]]
    for prec, m in zip(ligne, ligne[1:]):
        if m["x0"] - prec["x1"] > ecart:
            blocs.append(cur)
            cur = [m]
        else:
            cur.append(m)
    blocs.append(cur)
    return blocs


def _bornes_colonnes(lignes, tol=8, part=0.4):
    """Abscisses où une colonne commence, retenues si assez de lignes le confirment.

    La colonne la plus à gauche est retenue d'office. C'est celle du libellé, et
    elle n'apparaît que sur les lignes qui ouvrent un enregistrement : dans un
    tableau dont les libellés tiennent sur deux ou trois lignes, elle ne franchit
    pas le seuil et se retrouve écartée. Le libellé est alors versé dans la
    colonne suivante, ce qui donne un en-tête « Diagnostic Validité en vente » et
    des fiches où plus rien ne dit à quel diagnostic appartient la durée :
    « Validité en vente : Illimitée si le constat conclut à l'absence » d'un
    côté, « Amiante » de l'autre. Constat de la recette du 10/09/2026 : le modèle
    a alors attribué à l'amiante les 6 mois de la ligne des termites.
    """
    compte = Counter()
    for lg in lignes:
        for b in _blocs(lg):
            compte[round(b[0]["x0"] / tol) * tol] += 1
    seuil = max(2, int(len(lignes) * part))
    bornes = {x for x, n in compte.items() if n >= seuil}
    if compte:
        bornes.add(min(compte))
    return sorted(bornes)


def _cellules(ligne, bornes):
    cells = [[] for _ in bornes]
    for b in _blocs(ligne):
        x = b[0]["x0"]
        candidats = [j for j, bo in enumerate(bornes) if bo <= x + 4]
        cells[max(candidats) if candidats else 0].append(
            " ".join(w["text"] for w in b))
    return [" ".join(c).strip() for c in cells]


def _fusion_colonnes(lignes, bornes) -> list[str]:
    """Cellules d'une rangée, recomposées colonne par colonne.

    Les lignes arrivent dans l'ordre du haut vers le bas, donc les morceaux
    d'une même cellule se recollent dans l'ordre de lecture."""
    cells = [""] * len(bornes)
    for lg in lignes:
        for j, c in enumerate(_cellules(lg, bornes)):
            if c:
                cells[j] = (cells[j] + " " + c).strip()
    return cells


def _rangees_de_lignes(rangees, lignes) -> list[list] | None:
    """Répartit les lignes visuelles dans les rangées du tableau, ou None si la
    géométrie ne colle pas (rangées absentes, ou lignes qui tombent hors de
    toute rangée) : l'appelant se rabat alors sur le recollage de proche en
    proche."""
    if len(rangees) < 2:
        return None
    groupes = [[] for _ in rangees]
    orphelines = 0
    for lg in lignes:
        centre = sum((w["top"] + w["bottom"]) / 2 for w in lg) / len(lg)
        for i, r in enumerate(rangees):
            if r.bbox[1] - 1 <= centre <= r.bbox[3] + 1:
                groupes[i].append(lg)
                break
        else:
            orphelines += 1
    if orphelines > len(lignes) * 0.2 or not groupes[0]:
        return None
    return groupes


def _fiches_par_colonnes(page) -> list[str]:
    """Une RANGÉE de tableau = une fiche « En-tête : valeur — En-tête : valeur ».

    Une rangée occupe souvent plusieurs lignes de texte, et le libellé n'est pas
    forcément sur la première : dans le tableau des diagnostics, « Amiante »
    apparaît deux lignes plus bas que le début de sa durée de validité, parce
    que le texte est centré dans sa cellule. Recoller les lignes de proche en
    proche coupait donc la phrase « Illimitée si le constat conclut à l'absence
    d'amiante et a été établi à partir du 1er avril 2013 » en trois fiches, dont
    une seule portait le mot « Amiante » — le modèle ne pouvait plus rattacher
    la durée au bon diagnostic et lui a attribué les 6 mois des termites.

    On s'appuie donc d'abord sur les rangées que pdfplumber délimite lui-même,
    et on ne recolle de proche en proche qu'à défaut.
    """
    fiches = []
    for t in page.find_tables():
        lignes = _lignes_de_mots(page, t.bbox)
        if len(lignes) < 2:
            continue
        bornes = _bornes_colonnes(lignes)
        if len(bornes) < 2:
            continue

        groupes = _rangees_de_lignes(getattr(t, "rows", None) or [], lignes)
        if groupes:
            entetes = _fusion_colonnes(groupes[0], bornes)
            for g in groupes[1:]:
                if g:
                    fiches.append(_assembler(entetes, _fusion_colonnes(g, bornes)))
            continue

        entetes = _cellules(lignes[0], bornes)
        courant = None
        for lg in lignes[1:]:
            vals = _cellules(lg, bornes)
            if not any(vals):
                continue
            seul_libelle = bool(vals[0]) and not any(vals[1:])
            if courant is None:
                courant = vals
            elif seul_libelle and any(courant[1:]):
                # suite du libellé d'une ligne déjà pourvue de valeurs
                courant[0] = (courant[0] + " " + vals[0]).strip()
            elif all(not (a and b) for a, b in zip(courant, vals)):
                # lignes complémentaires : le libellé d'un côté, les valeurs de l'autre
                courant = [(a or "") + (" " if a and b else "") + (b or "")
                           for a, b in zip(courant, vals)]
                courant = [c.strip() for c in courant]
            else:
                fiches.append(_assembler(entetes, courant))
                courant = vals
        if courant:
            fiches.append(_assembler(entetes, courant))
    return [f for f in fiches if f]


def _assembler(entetes: list[str], vals: list[str]) -> str:
    """Fiche « En-tête : valeur — En-tête : valeur ».

    Retourne "" sous CELLULES_MIN : l'appelant écarte alors la fiche. C'est le
    seul critère d'entrée dans l'index — il ne regarde jamais le VOCABULAIRE de
    la ligne. Un filtre par mots-clés écartait auparavant en silence les lignes
    de tableau purement textuelles, par exemple « Autres agences — Mandat
    simple : Autorisées — Mandat exclusif : Interdites », ou la ligne du barème
    « Visite, dossier, rédaction du bail — Montant : identique au plafond
    locataire ». Douze lignes du corpus Horizon disparaissaient ainsi, dont cinq
    définitivement : leur zone de tableau étant retirée du texte de page, la
    prose ne les rattrapait pas. Chez un client dont un tableau serait
    entièrement textuel, le tableau entier manquait à l'appel."""
    paires = []
    for h, v in zip(entetes, vals):
        h, v = (h or "").strip(), (v or "").strip()
        if v:
            paires.append(f"{h} : {v}" if h else v)
    if len(paires) < CELLULES_MIN:
        return ""
    return " — ".join(paires)


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



def _texte_hors_tableaux(page, bboxes) -> str:
    """Texte de la page PRIVÉ des zones de tableau déjà converties en fiches.

    Sans cela, chaque tableau est indexé deux fois : une fois proprement en
    fiches étiquetées, une fois en vrac dans le texte de la page, où les
    en-têtes ont perdu leur lien avec les valeurs. Les deux copies se
    contredisent, et il suffit que la mauvaise remonte pour que l'assistant
    lise « 5,0 % » là où le tableau dit « 4,2 % » — c'est exactement ce qui
    s'est produit à la recette du 09/09/2026 en élargissant le top-K.
    """
    if not bboxes:
        return page.extract_text() or ""
    lignes = {}
    for m in page.extract_words(x_tolerance=1.5, y_tolerance=2):
        centre = (m["top"] + m["bottom"]) / 2
        if any(t0 - 2 <= centre <= t1 + 2 for _, t0, _, t1 in bboxes):
            continue                      # ligne appartenant à un tableau
        lignes.setdefault(round(m["top"] / 2.5), []).append(m)
    sortie = []
    for cle in sorted(lignes):
        mots = sorted(lignes[cle], key=lambda m: m["x0"])
        sortie.append(" ".join(w["text"] for w in mots))
    return "\n".join(sortie)


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
            zones_tableau = []          # bboxes converties en fiches sur CETTE page
            fiches_geo = _fiches_par_geometrie(page) if codes_totaux >= 10 else []
            if fiches_geo:
                fiches.extend(fiches_geo)
            else:
                # grille / manuel : tableaux à en-tête, une ligne = une fiche.
                # On reconstruit d'abord les colonnes par abscisse (tableaux sans
                # filets) ; l'extraction native ne sert que de repli.
                par_colonnes = _fiches_par_colonnes(page)
                if par_colonnes:
                    fiches.extend(par_colonnes)
                    zones_tableau = [t.bbox for t in page.find_tables()]
                else:
                    for t in page.extract_tables():
                        if not t or len(t) < 2:
                            continue
                        entetes = [(c or "").strip() for c in t[0]]
                        for row in t[1:]:
                            fiche = _ligne_en_fiche(entetes, row)
                            if fiche:
                                fiches.append(fiche)

            txt = _texte_hors_tableaux(page, zones_tableau)
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