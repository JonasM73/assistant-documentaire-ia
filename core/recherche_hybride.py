"""
recherche_hybride.py — Récupération hybride : mot-clé exact + vectoriel.

Problème résolu (constaté sur le jeu de contrôle) : la recherche vectorielle
seule ne distingue pas « S001 » de « S007 ». Les fiches sont sémantiquement
jumelles — seul le numéro change — et l'embedding ne pèse presque pas ce numéro.
La bonne fiche ne remonte donc pas dans le top-K, et l'assistant refuse à tort.
Les logs le prouvent : il liste les fiches reçues, la cible n'y est jamais.

Correctif : quand la question contient un identifiant (S001, BX-1003, étape 4),
on récupère d'abord par correspondance EXACTE les fiches qui le contiennent et on
les place EN TÊTE. Le vectoriel complète pour les questions en langage naturel
(commande minimale, seuil d'escalade).

Activation, sans toucher au reste du pipeline :
    import recherche_hybride
    recherche_hybride.activer()      # à appeler une fois au démarrage
"""

from __future__ import annotations

import re
import unicodedata

import rag_core

_MOTIFS_ID = [
    re.compile(r'\b[A-Z]{2,4}-\d{2,5}\b'),                 # BX-1003, REF-42
    re.compile(r'\bS\d{2,4}\b'),                           # S001
    re.compile(r'[ée]tape\s+\d+', re.IGNORECASE),         # étape 4
    re.compile(r'proc[ée]dure\s+\d+', re.IGNORECASE),     # procédure 12
]

# Noms propres : même problème que les identifiants, constaté sur la recette
# Horizon du 09/09/2026. « Quels honoraires pour l'agence de Blois ? » ne fait
# pas remonter le tableau qui dit que Blois est en zone B : ce tableau ne
# contient que des noms de villes et des codes, il n'a presque aucune proximité
# sémantique avec le mot « honoraires ». L'assistant reçoit le barème sans la
# correspondance, et refuse à juste titre. Quatre échecs sur six venaient de là.
_MOTIF_NOM_PROPRE = re.compile(r'\b[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-öø-ÿ-]{2,}\b')

# Mots capitalisés qui n'apprennent rien : début de phrase, interrogatifs,
# déterminants. Comparés sans accent ni casse.
_BANALS = {
    "quel", "quels", "quelle", "quelles", "combien", "comment", "pourquoi",
    "quand", "est", "sont", "peux", "peut", "pouvez", "dois", "doit", "faut",
    "que", "qui", "quoi", "dans", "pour", "avec", "sans", "selon", "sur",
    "les", "des", "une", "aux", "cette", "cet", "ces", "mon", "mes", "nos",
    "votre", "vos", "leur", "leurs", "son", "ses", "par", "vers", "chez",
    "sources", "source", "document", "documents", "bonjour", "merci",
    "assistant", "agence", "client", "locataire", "vendeur", "acheteur",
    "mandat", "bien", "logement", "prix", "zone", "tarif", "honoraires",
    # formes interrogatives inversées et débuts de phrase fréquents
    "peut-il", "peut-elle", "peux-tu", "pouvez-vous", "doit-il", "doit-elle",
    "y-a-t-il", "sous", "lors", "apres", "avant", "faut-il", "existe-t-il",
}


def _sans_accent(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def noms_propres(texte: str) -> list[str]:
    """Noms propres plausibles d'une question : mots capitalisés, hors
    interrogatifs et vocabulaire métier courant. Le premier mot de la phrase
    est ignoré s'il est banal, gardé sinon (« Blois compte-t-elle... »)."""
    out = []
    for m in _MOTIF_NOM_PROPRE.finditer(texte or ""):
        mot = m.group(0)
        if _sans_accent(mot).lower() in _BANALS:
            continue
        if mot not in out:
            out.append(mot)
    return out


def identifiants(texte: str) -> list[str]:
    out = []
    for rx in _MOTIFS_ID:
        for m in rx.finditer(texte or ""):
            if m.group(0) not in out:
                out.append(m.group(0))
    return out


def _variantes(ident: str) -> list[str]:
    """Formes possibles de l'identifiant dans un chunk. Nos fiches écrivent
    « Étape : 4 » là où la question dit « étape 4 »."""
    v = [ident]
    m = re.match(r'([ée]tape|proc[ée]dure)\s+(\d+)', ident, re.IGNORECASE)
    if m:
        num = m.group(2)
        v += [f"Étape : {num}", f"Procédure {num}", f"tape : {num}"]
    return v


# Plafond de chunks forcés par correspondance exacte : au-delà, on noierait
# le contexte utile sous des tableaux entiers.
MAX_EXACTS = 6


def _cle_chunk(c: dict) -> tuple:
    return (c.get("source"), c.get("chunk"))


def _par_terme(col, termes, limite=3, part_max=0.25):
    """Chunks contenant EXACTEMENT l'un des termes (noms propres).

    Garde-fou : un terme présent dans plus de `part_max` des chunks ne
    discrimine rien (ce serait le nom du client, écrit partout) — on l'ignore
    plutôt que de noyer le contexte."""
    if not termes:
        return []
    tout = col.get() or {}
    docs = tout.get("documents") or []
    metas = tout.get("metadatas") or []
    if not docs:
        return []
    seuil = max(1, int(len(docs) * part_max))
    res, vus = [], set()
    for terme in termes:
        trouves = [(t, m) for t, m in zip(docs, metas) if t and terme in t]
        if not trouves or len(trouves) > seuil:
            continue
        for texte, meta in trouves[:limite]:
            meta = meta or {}
            c = {"source": meta.get("source", "?"),
                 "chunk": meta.get("chunk", -1), "text": texte}
            cle = _cle_chunk(c)
            if cle in vus:
                continue
            vus.add(cle)
            res.append(c)
    return res


def _par_identifiant(col, idents, limite=5):
    """Fiches contenant EXACTEMENT l'un des identifiants, sans doublon.
    Un même extrait peut correspondre à deux identifiants de la question : on
    ne le renvoie qu'une fois."""
    if not idents:
        return []
    tout = col.get() or {}
    docs = tout.get("documents") or []
    metas = tout.get("metadatas") or []
    res, vus = [], set()
    for ident in idents:
        variantes = _variantes(ident)
        n = 0
        for texte, meta in zip(docs, metas):
            if not texte or not any(v in texte for v in variantes):
                continue
            meta = meta or {}
            c = {"source": meta.get("source", "?"),
                 "chunk": meta.get("chunk", -1), "text": texte}
            cle = _cle_chunk(c)
            if cle in vus:
                continue
            vus.add(cle)
            res.append(c)
            n += 1
            if n >= limite:
                break
    return res


def _vectoriel(col, question, top_k):
    return rag_core.formater_resultats(
        col.query(query_texts=[question], n_results=max(1, int(top_k or 1))))


def activer():
    """Branche la récupération hybride dans rag_core.retrieve.
    Idempotent : un second appel ne double pas le patch."""
    if getattr(rag_core.retrieve, "_hybride", False):
        return

    def retrieve_hybride(question, embedding_function=None,
                         top_k=None, chroma_dir=None):
        top_k = top_k or rag_core.TOP_K
        chroma_dir = chroma_dir or rag_core.CHROMA_DIR
        # Une seule ouverture de collection pour les deux voies de récupération.
        col = rag_core.get_collection(embedding_function, chroma_dir)
        exacts = _par_identifiant(col, identifiants(question))
        vus_ex = {_cle_chunk(c) for c in exacts}
        # Puis les noms propres, sans redoubler ce que la voie identifiant a déjà pris.
        for c in _par_terme(col, noms_propres(question)):
            if _cle_chunk(c) not in vus_ex:
                exacts.append(c)
                vus_ex.add(_cle_chunk(c))
        exacts = exacts[:MAX_EXACTS]
        vect = _vectoriel(col, question, top_k)
        vus = {_cle_chunk(c) for c in exacts}
        fusion = list(exacts)
        for c in vect:
            cle = _cle_chunk(c)
            if cle not in vus:
                fusion.append(c)
                vus.add(cle)
        return fusion[:len(exacts) + top_k]

    retrieve_hybride._hybride = True
    rag_core.retrieve = retrieve_hybride