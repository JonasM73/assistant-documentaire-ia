"""
journal.py — Journal des questions (option « tableau de bord d'usage »).

Opt-in strict : tant que LOG_QUESTIONS n'est pas activé, RIEN n'est écrit.
Chaque ligne du fichier JSONL contient exactement quatre champs :
    date (ISO), question (texte), sources (fichiers cités), refus (oui/non).
Aucune donnée personnelle au-delà du texte de la question : ni adresse IP,
ni identifiant, ni en-tête, ni historique de conversation.

Statistiques (stats) : les questions sont regroupées par SENS quand une
fonction d'embedding est fournie (le même modèle local fastembed que
l'index — coût zéro, rien ne sort de l'instance) : « Quel est le prix du
BOR-CEI ? » et « Combien coûte le BOR-CEI ? » comptent alors comme un seul
sujet. Sans fonction d'embedding, repli sur un regroupement par formulation
(minuscules + ponctuation ignorées).

Configuration (.env) :
    LOG_QUESTIONS=1        active le journal (défaut : désactivé)
    LOG_DIR=logs           dossier du fichier questions.jsonl
                           (sur Railway : pointer vers le volume persistant,
                           p. ex. LOG_DIR=data/logs si le volume monte data/)

Le module est volontairement fail-safe : une erreur d'écriture, de lecture ou
d'embedding ne doit JAMAIS faire échouer une réponse ni la page de stats.
"""

from __future__ import annotations

import os
import json
import math
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

FICHIER = "questions.jsonl"

# Ligne gardée volontairement courte : le journal sert aux statistiques,
# pas à archiver des conversations.
LONGUEUR_MAX_QUESTION = 500

# Similarité cosinus minimale pour considérer que deux questions posent la
# même chose (modèle paraphrase multilingue : ~0,75 sépare bien reformulation
# et sujet différent).
SEUIL_SIMILARITE = 0.75

# Marqueurs d'un refus (l'assistant dit que l'info n'est pas dans les docs,
# ou décline une demande hors périmètre). Comparaison en minuscules.
REFUS_MARQUEURS = (
    "je ne trouve pas cette information",
    "ne figure pas dans les documents",
    "pas cette information dans les documents",
    "je ne peux pas répondre à cette demande",
)


def actif() -> bool:
    """Le journal est-il activé ? (LOG_QUESTIONS=1/true/oui/on)"""
    v = os.environ.get("LOG_QUESTIONS", "").strip().lower()
    return v in {"1", "true", "vrai", "oui", "yes", "on"}


def chemin() -> str:
    """Chemin du fichier JSONL (LOG_DIR/questions.jsonl)."""
    return os.path.join(os.environ.get("LOG_DIR", "logs"), FICHIER)


def est_refus(reponse: str) -> bool:
    """Détecte si la réponse est un refus (info absente ou hors périmètre)."""
    r = (reponse or "").lower()
    return any(m in r for m in REFUS_MARQUEURS)


def enregistrer(question: str, sources: list[str] | None, refus: bool,
                duree: float | None = None) -> None:
    """Ajoute une ligne au journal. Silencieux si désactivé ; n'échoue jamais.
    `duree` (secondes, optionnel) : temps de réponse mesuré par le serveur —
    une métrique technique, pas une donnée personnelle."""
    if not actif():
        return
    try:
        p = chemin()
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        ligne = {
            "date": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "question": (question or "").strip()[:LONGUEUR_MAX_QUESTION],
            "sources": _sources({"sources": sources}),
            "refus": bool(refus),
        }
        if duree is not None:
            ligne["duree"] = round(float(duree), 2)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    except Exception:
        # Le journal ne doit jamais casser une réponse.
        pass


def lire(limite: int = 5000) -> list[dict]:
    """Lit les dernières `limite` entrées du journal (tolérant aux lignes
    corrompues). Liste vide si le fichier n'existe pas."""
    p = chemin()
    if not os.path.exists(p):
        return []
    entrees: list[dict] = []
    try:
        with open(p, "r", encoding="utf-8") as f:
            lignes = f.readlines()[-limite:]
        for l in lignes:
            l = l.strip()
            if not l:
                continue
            try:
                e = json.loads(l)
                if isinstance(e, dict) and "question" in e:
                    entrees.append(e)
            except Exception:
                continue
    except Exception:
        return []
    return entrees


def _sources(entree: dict) -> list[str]:
    """Sources d'une entrée, toujours sous forme de liste de chaînes.

    Le journal étant un fichier en ajout seul, il peut contenir des lignes
    écrites par une version antérieure : `sources` y est parfois une chaîne
    unique, ou absent. Sans cette normalisation, `list("a.pdf")` produirait une
    source par lettre."""
    src = entree.get("sources")
    if not src:
        return []
    if isinstance(src, str):
        return [src]
    if isinstance(src, (list, tuple, set)):
        return [str(s) for s in src if s]
    return [str(src)]


def _question(entree: dict) -> str:
    return str(entree.get("question", ""))


def _normaliser(q: str) -> str:
    """Clé de regroupement lexical : minuscules, ponctuation et espaces
    superflus retirés."""
    q = (q or "").lower().strip()
    q = re.sub(r"[?!.,;:«»\"']", " ", q)
    q = re.sub(r"\s+", " ", q)
    return q.strip()


def rechercher(debut: str = "", fin: str = "", texte: str = "",
               limite: int = 100) -> dict:
    """Recherche dans le journal : période [debut, fin] (AAAA-MM-JJ, bornes
    incluses) et/ou texte contenu dans la question (insensible à la casse).
    Renvoie {"total": nb de correspondances, "questions": [...]} — les plus
    récentes d'abord, au plus `limite` (bornée à 500)."""
    texte = (texte or "").lower().strip()
    correspondances = []
    for e in lire():
        jour = str(e.get("date", ""))[:10]
        if debut and jour < debut:
            continue
        if fin and jour > fin:
            continue
        if texte and texte not in _question(e).lower():
            continue
        correspondances.append(e)
    total = len(correspondances)
    try:
        limite = max(1, min(int(limite), 500))
    except (TypeError, ValueError):
        limite = 100
    questions = [{"date": str(e.get("date", "")),
                  "question": _question(e)[:300],
                  "sources": _sources(e)[:4],
                  "refus": bool(e.get("refus"))}
                 for e in reversed(correspondances)][:limite]
    return {"total": total, "questions": questions}


# --------------------------------------------------------------------------- #
# Regroupement par sens
# --------------------------------------------------------------------------- #

def _clusteriser(cles: list[str], embed_fn, seuil: float) -> tuple[list[list[int]], str]:
    """Regroupe les clés (questions normalisées) par similarité sémantique.

    Algorithme glouton : les clés arrivent triées par fréquence décroissante ;
    chaque clé rejoint le groupe dont le représentant (première clé du groupe,
    donc la plus posée) lui ressemble le plus (cosinus >= seuil), sinon ouvre
    un nouveau groupe. Retourne (groupes d'indices, mode utilisé).
    """
    if len(cles) < 2:
        return [[i] for i in range(len(cles))], ("semantique" if embed_fn else "lexical")
    if embed_fn is None:
        return [[i] for i in range(len(cles))], "lexical"
    try:
        vecs = [list(map(float, v)) for v in embed_fn(list(cles))]
        normes = [math.sqrt(sum(x * x for x in v)) or 1.0 for v in vecs]
        vecs = [[x / n for x in v] for v, n in zip(vecs, normes)]
    except Exception:
        # Modèle indisponible → repli lexical, jamais d'erreur.
        return [[i] for i in range(len(cles))], "lexical"

    groupes: list[list[int]] = []
    for i in range(len(cles)):
        meilleur, meilleure_sim = None, seuil
        for gi, membres in enumerate(groupes):
            rep = vecs[membres[0]]
            sim = sum(a * b for a, b in zip(vecs[i], rep))
            if sim >= meilleure_sim:
                meilleur, meilleure_sim = gi, sim
        if meilleur is None:
            groupes.append([i])
        else:
            groupes[meilleur].append(i)
    return groupes, "semantique"


# --------------------------------------------------------------------------- #
# Statistiques
# --------------------------------------------------------------------------- #

# Cache : le clustering (embeddings) n'est recalculé que si le fichier change.
_CACHE: dict = {"sig": None, "res": None}


def stats(embed_fn=None, jours_graphe: int = 60, top: int = 8,
          dernieres_n: int = 10, seuil: float = SEUIL_SIMILARITE) -> dict:
    """Statistiques agrégées pour /api/admin/stats et gestion.html.

    - par_jour : série continue (questions / refus) sur `jours_graphe` jours,
      pour les vues 7 / 14 / 30 jours côté page.
    - sujets : questions regroupées par sens (ou par formulation en repli),
      avec le nombre de formulations différentes et des exemples.
    - sans_reponse : sujets où l'assistant a refusé (info absente des docs).
    - sources : documents les plus cités dans les réponses.
    - dernieres : dernières questions, plus récentes d'abord.
    """
    # --- cache (le clustering coûte quelques secondes sur un gros journal) - #
    p = chemin()
    try:
        st = os.stat(p)
        sig = (p, st.st_mtime_ns, st.st_size, jours_graphe, top, dernieres_n,
               seuil, embed_fn is not None, actif())
    except OSError:
        sig = (p, None, None, jours_graphe, top, dernieres_n,
               seuil, embed_fn is not None, actif())
    if _CACHE["sig"] == sig:
        return _CACHE["res"]

    entrees = lire()
    total = len(entrees)
    refus = sum(1 for e in entrees if e.get("refus"))

    # --- volume par jour, série continue --------------------------------- #
    par_jour_brut: dict[str, dict] = {}
    for e in entrees:
        jour = str(e.get("date", ""))[:10]
        if not jour:
            continue
        d = par_jour_brut.setdefault(jour, {"questions": 0, "refus": 0})
        d["questions"] += 1
        if e.get("refus"):
            d["refus"] += 1
    aujourdhui = datetime.now(timezone.utc).astimezone().date()
    par_jour = []
    for i in range(jours_graphe - 1, -1, -1):
        jour = (aujourdhui - timedelta(days=i)).isoformat()
        d = par_jour_brut.get(jour, {"questions": 0, "refus": 0})
        par_jour.append({"date": jour, "questions": d["questions"], "refus": d["refus"]})

    # --- rythme d'utilisation : par heure et par jour de semaine ----------- #
    par_heure = [0] * 24
    par_semaine = [0] * 7  # 0 = lundi … 6 = dimanche
    for e in entrees:
        ds = str(e.get("date", ""))
        try:
            par_heure[int(ds[11:13])] += 1
        except (ValueError, IndexError):
            pass
        try:
            par_semaine[datetime.strptime(ds[:10], "%Y-%m-%d").weekday()] += 1
        except ValueError:
            pass

    # --- durée moyenne de réponse (si mesurée) ----------------------------- #
    durees = [e["duree"] for e in entrees
              if isinstance(e.get("duree"), (int, float)) and e["duree"] >= 0]
    duree_moyenne = round(sum(durees) / len(durees), 1) if durees else None

    # --- comptage par formulation normalisée ------------------------------ #
    lim_7j = (aujourdhui - timedelta(days=6)).isoformat()
    lim_prec = (aujourdhui - timedelta(days=13)).isoformat()
    comptes: dict[str, dict] = {}
    for e in entrees:
        q = _question(e).strip()
        cle = _normaliser(q)
        if not cle:
            continue
        d = comptes.setdefault(cle, {"n": 0, "refus": 0, "n_7j": 0, "n_prec": 0,
                                     "formulations": Counter()})
        d["n"] += 1
        if e.get("refus"):
            d["refus"] += 1
        jour = str(e.get("date", ""))[:10]
        if jour >= lim_7j:
            d["n_7j"] += 1
        elif jour >= lim_prec:
            d["n_prec"] += 1
        d["formulations"][q] += 1

    # --- regroupement par sens -------------------------------------------- #
    cles = sorted(comptes, key=lambda c: -comptes[c]["n"])
    groupes, mode = _clusteriser(cles, embed_fn, seuil)

    sujets = []
    for membres in groupes:
        formulations: Counter = Counter()
        n = nb_refus = n_7j = n_prec = 0
        for idx in membres:
            d = comptes[cles[idx]]
            n += d["n"]
            nb_refus += d["refus"]
            n_7j += d["n_7j"]
            n_prec += d["n_prec"]
            formulations += d["formulations"]
        representant = formulations.most_common(1)[0][0]
        exemples = [q for q, _ in formulations.most_common(4) if q != representant][:3]
        sujets.append({
            "question": representant,
            "n": n,
            "refus": nb_refus,
            "n_7j": n_7j,          # occurrences sur les 7 derniers jours
            "n_prec": n_prec,      # occurrences sur les 7 jours précédents
            "formulations": len(formulations),
            "exemples": exemples,
        })
    sujets.sort(key=lambda s: -s["n"])

    # --- sujets restés sans réponse (arguments pour compléter les docs) --- #
    sans_reponse = sorted((s for s in sujets if s["refus"]),
                          key=lambda s: -s["refus"])[:6]
    sans_reponse = [{"question": s["question"], "n": s["refus"]} for s in sans_reponse]

    # --- documents les plus cités ----------------------------------------- #
    cites: Counter = Counter()
    for e in entrees:
        for src in _sources(e):
            cites[src] += 1
    sources = [{"source": s, "n": n} for s, n in cites.most_common(6)]

    # --- dernières questions (plus récentes d'abord) ----------------------- #
    dernieres = [{"date": str(e.get("date", "")),
                  "question": _question(e)[:200],
                  "sources": _sources(e)[:3],
                  "refus": bool(e.get("refus"))}
                 for e in reversed(entrees[-dernieres_n:])]

    res = {
        "actif": actif(),
        "groupement": mode,
        "total": total,
        "refus": refus,
        "taux_refus": round(refus / total, 4) if total else 0.0,
        "duree_moyenne": duree_moyenne,
        "par_jour": par_jour,
        "par_heure": par_heure,
        "par_semaine": par_semaine,
        "sujets": sujets[:top],
        "nb_sujets": len(sujets),
        "sans_reponse": sans_reponse,
        "sources": sources,
        "dernieres": dernieres,
    }
    _CACHE["sig"], _CACHE["res"] = sig, res
    return res
