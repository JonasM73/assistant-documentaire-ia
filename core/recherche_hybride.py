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
import rag_core

_MOTIFS_ID = [
    re.compile(r'\b[A-Z]{2,4}-\d{2,5}\b'),                 # BX-1003, REF-42
    re.compile(r'\bS\d{2,4}\b'),                           # S001
    re.compile(r'[ée]tape\s+\d+', re.IGNORECASE),         # étape 4
    re.compile(r'proc[ée]dure\s+\d+', re.IGNORECASE),     # procédure 12
]


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


def _cle_chunk(c: dict) -> tuple:
    return (c.get("source"), c.get("chunk"))


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
        idents = identifiants(question)
        exacts = _par_identifiant(col, idents)
        vect = _vectoriel(col, question, top_k)
        vus = {_cle_chunk(c) for c in exacts}
        fusion = list(exacts)
        for c in vect:
            cle = _cle_chunk(c)
            if cle not in vus:
                fusion.append(c)
                vus.add(cle)
        return fusion[:max(top_k, len(exacts) + top_k)]

    retrieve_hybride._hybride = True
    rag_core.retrieve = retrieve_hybride