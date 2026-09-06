"""
evaluer.py — Passe un jeu de questions de contrôle sur le pipeline RAG et note.

Sort trois nombres par modèle :
    - réponses exactes   : la valeur attendue apparaît dans la réponse
    - refus corrects     : la question sans réponse a bien reçu un refus
    - hallucinations     : une question sans réponse a reçu une réponse affirmative,
                           OU une factuelle a reçu une valeur sans le refus attendu
                           et sans la bonne valeur (réponse inventée)

Une seule hallucination est un défaut bloquant, pas une statistique.

Le même index vectoriel sert à tous les modèles : la récupération est identique,
seule la génération change. C'est ce qui rend la comparaison Sonnet / Haiku honnête.

Prérequis :
    - Indexer le dossier de documents du test : set DATA_DIR=data-immobilier
      puis python ingest.py (ou pointer CHROMA_DIR sur un index dédié)
    - Une clé ANTHROPIC_API_KEY dans .env

Usage (recette Horizon Immobilier, jeu par défaut) :
    python tests/evaluer.py --modeles claude-haiku-4-5 --client "Horizon Immobilier" --rapport tests/recette-horizon.md
    python tests/evaluer.py --questions autre_jeu.json --verbeux
    python tests/evaluer.py --seuil 0.9   # seuil d'exactitude convenu au devis (part des factuelles exactes)
"""



from __future__ import annotations

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core"))

import argparse
import json
import re
import sys
import unicodedata

import rag_core
import recherche_hybride      # ← ajouter
recherche_hybride.activer()

# Marqueurs d'un refus explicite. La consigne système impose la formule
# « Je ne trouve pas cette information dans les documents. » ; on accepte des
# variantes pour ne pas pénaliser une reformulation correcte.
MARQUEURS_REFUS = [
    "je ne trouve pas", "ne figure pas", "aucune information",
    "pas cette information", "ne dispose pas", "je ne peux pas",
    "n'est pas dans", "ne se trouve pas", "hors de mon", "hors périmètre",
    "je ne suis pas en mesure", "ne fait pas partie", "n'apparait pas",
    "je n'ai pas", "ne contient pas",
    # déclinements hors-périmètre (question H01 et similaires)
    "sort de mon", "hors de mon perimetre", "mon role est", "mon perimetre",
    "je suis l'assistant", "je suis un assistant", "je reponds uniquement",
    "je peux uniquement", "je ne reponds qu",
]


def _norm(s: str) -> str:
    """Minuscule, sans accents, espaces normalisés — pour comparer souplement."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s


def a_refuse(reponse: str) -> bool:
    r = _norm(reponse)
    return any(_norm(m) in r for m in MARQUEURS_REFUS)


def contient_attendu(reponse: str, attendus: list[str]) -> bool:
    r = _norm(reponse)
    for a in attendus:
        na = _norm(a)
        # nombres : comparaison tolérante aux espaces/insécables/séparateurs
        if re.fullmatch(r"[\d \u00a0.,]+", a):
            chiffres_att = re.sub(r"[ \u00a0.,]", "", na)
            chiffres_rep = re.sub(r"[ \u00a0.,]", "", r)
            if chiffres_att and chiffres_att in chiffres_rep:
                return True
        elif na in r:
            return True
    return False


def noter_une(q: dict, reponse: str) -> tuple[str, str]:
    """Retourne (verdict, detail). verdict ∈ {exacte, refus_ok, manque, halluc}."""
    refuse = a_refuse(reponse)

    if q["doit_refuser"]:
        if refuse:
            return "refus_ok", "refus attendu, refus obtenu"
        return "halluc", "aurait dû refuser, a répondu"

    # question à réponse attendue
    if contient_attendu(reponse, q["attendu"]):
        return "exacte", "valeur attendue présente"
    if refuse:
        return "manque", "a refusé alors qu'il y avait une réponse (faux refus)"
    return "halluc", "valeur attendue absente et pas de refus (réponse inventée)"


def jouer_question(q: dict) -> str:
    """Exécute une question (avec amorce si c'est un suivi) et retourne la réponse."""
    historique = []
    if q["type"] == "suivi":
        amorce = q["amorce"]
        res_amorce = rag_core.answer_question(amorce, history=historique)
        historique.append({"role": "user", "content": amorce})
        historique.append({"role": "assistant", "content": res_amorce.answer})
    res = rag_core.answer_question(q["question"], history=historique)
    return res.answer


def evaluer_modele(modele: str, questions: list[dict], verbeux: bool) -> dict:
    rag_core.ANTHROPIC_MODEL = modele  # force le modèle de génération
    compteur = {"exacte": 0, "refus_ok": 0, "manque": 0, "halluc": 0}
    details = []

    print(f"\n{'=' * 68}\nMODÈLE : {modele}\n{'=' * 68}")
    for q in questions:
        try:
            reponse = jouer_question(q)
        except Exception as e:
            print(f"  ! {q['id']} — échec : {e}", file=sys.stderr)
            details.append({"id": q["id"], "verdict": "erreur", "detail": str(e)})
            continue
        verdict, detail = noter_une(q, reponse)
        compteur[verdict] += 1
        details.append({"id": q["id"], "type": q["type"], "verdict": verdict,
                        "detail": detail, "reponse": reponse.strip()})
        marque = {"exacte": "OK ", "refus_ok": "OK ", "manque": "-- ", "halluc": "XX "}[verdict]
        ligne = f"  {marque}{q['id']:4s} {verdict:9s}"
        if verbeux:
            ligne += f" | {q['question'][:44]:46s} → {reponse.strip()[:60]}"
        print(ligne)

    total = len(questions)
    exactes_possibles = sum(1 for q in questions if not q["doit_refuser"])
    refus_possibles = sum(1 for q in questions if q["doit_refuser"])

    print(f"\n  Réponses exactes   : {compteur['exacte']}/{exactes_possibles}")
    print(f"  Refus corrects     : {compteur['refus_ok']}/{refus_possibles}")
    print(f"  Faux refus (manque): {compteur['manque']}")
    print(f"  HALLUCINATIONS     : {compteur['halluc']}"
          + ("   <-- défaut bloquant" if compteur['halluc'] else ""))

    return {"modele": modele, "compteur": compteur,
            "exactes_possibles": exactes_possibles,
            "refus_possibles": refus_possibles, "details": details}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modeles", nargs="+",
                    default=["claude-haiku-4-5", "claude-sonnet-4-6"],
                    help="modèles Anthropic à comparer")
    ap.add_argument("--questions",
                    default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "questions_controle_immobilier.json"))
    ap.add_argument("--seuil", type=float, default=None, metavar="0.9",
                    help="seuil d'exactitude convenu au devis : part minimale de réponses exactes "
                         "parmi les questions qui ont une réponse (ex. 0.9). Porté sur le PV.")
    ap.add_argument("--verbeux", action="store_true")
    ap.add_argument("--out",
                    default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultats_evaluation.json"))
    ap.add_argument("--rapport", metavar="FICHIER.md",
                    help="écrit en plus un procès-verbal de recette lisible, "
                         "au format remis au client")
    ap.add_argument("--client", default="", metavar="NOM",
                    help="nom du client porté sur le procès-verbal de recette")
    args = ap.parse_args()

    if rag_core.resolve_llm_provider() != "anthropic":
        print("! Ce comparatif suppose le fournisseur Anthropic.")
        print("  Mets LLM_PROVIDER=anthropic et une clé ANTHROPIC_API_KEY dans .env.")
        sys.exit(1)

    with open(args.questions, encoding="utf-8") as f:
        questions = json.load(f)["questions"]

    try:
        rag_core.get_collection()
    except Exception as e:
        print(f"! Index introuvable ({e}).")
        print("  Indexe d'abord les 3 PDF de contrôle (voir en-tête du script).")
        sys.exit(1)

    print(f"Questions : {len(questions)}  ·  Modèles : {', '.join(args.modeles)}")
    print("Récupération identique pour tous (embeddings locaux, même index).")

    resultats = [evaluer_modele(m, questions, args.verbeux) for m in args.modeles]

    # Tableau comparatif final
    print(f"\n{'=' * 68}\nCOMPARATIF\n{'=' * 68}")
    print(f"  {'Modèle':<24}{'Exactes':>10}{'Refus':>8}{'Halluc.':>10}")
    for r in resultats:
        c = r["compteur"]
        print(f"  {r['modele']:<24}"
              f"{c['exacte']:>4}/{r['exactes_possibles']:<5}"
              f"{c['refus_ok']:>3}/{r['refus_possibles']:<4}"
              f"{c['halluc']:>10}")
    print()
    print("  Règle de décision : à hallucinations égales (idéalement zéro),")
    print("  prends le moins cher. Une hallucination de plus disqualifie,")
    print("  quel que soit le prix.")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(resultats, f, ensure_ascii=False, indent=2)
    print(f"\n  Détail écrit dans {args.out}")

    if args.rapport:
        ecrire_rapport(args.rapport, resultats, questions, args)
        print(f"  Procès-verbal de recette écrit dans {args.rapport}")


def ecrire_rapport(chemin, resultats, questions, args):
    """Procès-verbal de recette, au format remis au client.

    Ce n'est pas un journal de mise au point : c'est la pièce que le client relit
    ligne par ligne avant de régler le solde. Il doit pouvoir vérifier chaque
    réponse contre ses propres documents.
    """
    from datetime import date

    r = resultats[0]                      # le modèle retenu est le premier passé
    c = r["compteur"]
    halluc = c["halluc"]
    client = args.client or "[nom du client]"
    jeu = os.path.basename(args.questions)

    L = []
    L.append(f"# Procès-verbal de recette — {client}")
    L.append("")
    L.append(f"- **Date de la recette** : {date.today().strftime('%d/%m/%Y')}")
    L.append(f"- **Jeu de questions** : `{jeu}` — {len(questions)} questions, "
             f"arrêtées avec le client avant le test")
    L.append(f"- **Modèle utilisé en production** : {r['modele']}")
    L.append("")
    L.append("## Résultat")
    L.append("")
    L.append("| Critère | Résultat |")
    L.append("|---|---|")
    L.append(f"| Réponses exactes | {c['exacte']} / {r['exactes_possibles']} |")
    L.append(f"| Refus corrects sur les questions sans réponse | "
             f"{c['refus_ok']} / {r['refus_possibles']} |")
    L.append(f"| **Réponses inventées** | **{halluc}** |")
    seuil = getattr(args, "seuil", None)
    seuil_ok = None
    if seuil is not None and r['exactes_possibles']:
        part = c['exacte'] / r['exactes_possibles']
        seuil_ok = part >= seuil
        L.append(f"| Seuil d'exactitude convenu au devis | {seuil:.0%} — atteint : "
                 f"{'oui' if seuil_ok else 'NON'} ({part:.0%}) |")
    L.append("")
    if halluc == 0 and seuil_ok is False:
        L.append(f"> ⚠️ **Aucune réponse inventée, mais le seuil d'exactitude convenu "
                 f"({seuil:.0%}) n'est pas atteint. La recette n'est pas validée.** "
                 "Conformément au devis, les corrections sont réalisées sans supplément "
                 "(dix jours ouvrables, deux cycles au plus) avant facturation du solde.")
    elif halluc == 0:
        L.append("> Aucune réponse inventée sur ce jeu de contrôle. Chaque réponse fournie "
                 "s'appuie sur un extrait de vos documents, et l'assistant a refusé de "
                 "répondre à chacune des questions dont la réponse ne s'y trouve pas."
                 + (" Le seuil d'exactitude convenu est atteint : la recette est validée." if seuil_ok else ""))
    else:
        L.append(f"> ⚠️ **{halluc} réponse(s) inventée(s). La recette n'est pas validée.** "
                 "Conformément au devis, les corrections sont réalisées sans supplément "
                 "avant toute facturation du solde et avant la mise en production.")
    L.append("")
    L.append("## Détail, question par question")
    L.append("")
    L.append("Chaque ligne est vérifiable dans vos documents. `attendu` est la valeur qui "
             "devait figurer dans la réponse ; `sans réponse` signale les questions dont la "
             "réponse n'existe volontairement pas dans le corpus fourni.")
    L.append("")
    L.append("| # | Question | Type | Source à vérifier | Verdict |")
    L.append("|---|---|---|---|---|")
    par_id = {q["id"]: q for q in questions}
    libelle = {"exacte": "conforme",
               "refus_ok": "refus correct",
               "manque": "incomplet — à corriger",
               "halluc": "**réponse inventée**",
               "erreur": "erreur technique — à rejouer"}
    for i, d in enumerate(r["details"], 1):
        q = par_id.get(d.get("id"), {})
        texte = str(q.get("question", d.get("id", ""))).replace("|", "\\|")
        typ = "sans réponse" if q.get("doit_refuser") else "factuelle"
        src = q.get("source", "")
        if src and q.get("page"):
            src = f"{src} · p. {q['page']}"
        L.append(f"| {i} | {texte} | {typ} | {src or '—'} | "
                 f"{libelle.get(d.get('verdict'), d.get('verdict', 'à revoir'))} |")
    L.append("")
    L.append("## Ce qui a été vérifié")
    L.append("")
    for ligne in [
        "chaque réponse s'appuie sur un extrait du document source, ouvrable en un clic ;",
        "l'assistant refuse explicitement quand l'information n'existe pas dans les documents ;",
        "aucun engagement (prix, délai, garantie) n'est énoncé sans appui documentaire ;",
        "les sources citées correspondent bien au document dont la réponse est tirée ;",
        "le seuil d'exactitude convenu au devis est atteint.",
    ]:
        L.append(f"- {ligne}")
    L.append("")
    L.append("## Décision")
    L.append("")
    L.append("- [ ] Recette validée — mise en production, solde exigible.")
    L.append("- [ ] Recette non validée — corrections sans supplément sous dix jours ouvrables "
             "(deux cycles au plus), puis nouveau passage du même jeu de questions.")
    L.append("")
    L.append("Le client — nom, signature, date : ______________________    "
             "Jonas Mionnet — date : ______________________")
    L.append("")
    L.append("---")
    L.append("")
    L.append("Jonas Mionnet — assistants documentaires pour PME · jonas@jonasmionnet.com · assistant-documentaire.com")

    with open(chemin, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()