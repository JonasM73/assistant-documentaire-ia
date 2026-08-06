"""
test_journal.py — Tests du journal des questions (option tableau de bord).

Lancement :  python -m pytest tests/test_journal.py -q
Aucune dépendance externe (stdlib + pytest) : ne touche ni Chroma ni l'API.
"""

import importlib
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core"))
import journal  # noqa: E402


@pytest.fixture
def journal_actif(tmp_path, monkeypatch):
    """Journal activé, fichier dans un dossier temporaire."""
    monkeypatch.setenv("LOG_QUESTIONS", "1")
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    importlib.reload(journal)
    return tmp_path


def test_desactive_par_defaut(tmp_path, monkeypatch):
    """Opt-in strict : sans LOG_QUESTIONS, rien n'est écrit."""
    monkeypatch.delenv("LOG_QUESTIONS", raising=False)
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    assert journal.actif() is False
    journal.enregistrer("Quel est le prix ?", ["catalogue.pdf"], False)
    assert not os.path.exists(journal.chemin())
    s = journal.stats()
    assert s["actif"] is False and s["total"] == 0


def test_enregistre_les_bons_champs(journal_actif):
    journal.enregistrer("  Quel est le prix du BOR-CEI ?  ", ["Catalogue-produits.pdf"], False)
    with open(journal.chemin(), encoding="utf-8") as f:
        ligne = json.loads(f.readline())
    # Exactement quatre champs — pas d'IP, pas d'identifiant.
    assert set(ligne) == {"date", "question", "sources", "refus"}
    assert ligne["question"] == "Quel est le prix du BOR-CEI ?"
    assert ligne["sources"] == ["Catalogue-produits.pdf"]
    assert ligne["refus"] is False


def test_duree_optionnelle(journal_actif):
    journal.enregistrer("Sans durée ?", [], False)
    journal.enregistrer("Avec durée ?", [], False, duree=3.456)
    lignes = journal.lire()
    assert "duree" not in lignes[0]           # absente si non mesurée
    assert lignes[1]["duree"] == 3.46         # arrondie à 2 décimales
    s = journal.stats()
    assert s["duree_moyenne"] == 3.5          # moyenne sur les lignes mesurées
    assert len(s["par_heure"]) == 24 and sum(s["par_heure"]) == 2
    assert len(s["par_semaine"]) == 7 and sum(s["par_semaine"]) == 2


def test_question_tronquee(journal_actif):
    journal.enregistrer("x" * 2000, [], False)
    e = journal.lire()[0]
    assert len(e["question"]) == journal.LONGUEUR_MAX_QUESTION


def test_est_refus():
    assert journal.est_refus("Je ne trouve pas cette information dans les documents.")
    assert journal.est_refus("Cette donnée ne figure pas dans les documents fournis.")
    assert not journal.est_refus("Le chauffe-eau BOR-CEI est à 1 340 $ net.")
    assert not journal.est_refus("")
    assert not journal.est_refus(None)


def test_stats_lexical(journal_actif):
    for _ in range(3):
        journal.enregistrer("Quel est le prix du BOR-CEI ?", ["catalogue.pdf"], False)
    journal.enregistrer("quel est le prix du bor-cei", ["catalogue.pdf"], False)  # même question, autre casse
    journal.enregistrer("Quelle est la capitale de la France ?", [], True)
    s = journal.stats()  # sans embed_fn → regroupement lexical
    assert s["actif"] is True
    assert s["groupement"] == "lexical"
    assert s["total"] == 5
    assert s["refus"] == 1
    assert s["taux_refus"] == pytest.approx(0.2)
    # Regroupement lexical : les 4 formulations quasi identiques comptent ensemble.
    assert s["sujets"][0]["n"] == 4
    # Série continue de 60 jours, tout le volume sur aujourd'hui.
    assert len(s["par_jour"]) == 60
    assert s["par_jour"][-1]["questions"] == 5
    assert s["par_jour"][-1]["refus"] == 1
    # Documents cités et sujets sans réponse.
    assert s["sources"][0] == {"source": "catalogue.pdf", "n": 4}
    assert s["sans_reponse"][0]["n"] == 1
    # Dernières questions : la plus récente d'abord.
    assert s["dernieres"][0]["refus"] is True


def _embed_factice(questions):
    """Embedding jouet : les questions de prix pointent dans une direction,
    les autres dans une autre — simule le regroupement par sens."""
    vecs = []
    for q in questions:
        prix = ("prix" in q) or ("coûte" in q) or ("tarif" in q)
        vecs.append([1.0, 0.0] if prix else [0.0, 1.0])
    return vecs


def test_stats_regroupement_par_sens(journal_actif):
    # Trois formulations DIFFÉRENTES de la même idée + un sujet distinct.
    journal.enregistrer("Quel est le prix du BOR-CEI ?", ["catalogue.pdf"], False)
    journal.enregistrer("Quel est le prix du BOR-CEI ?", ["catalogue.pdf"], False)
    journal.enregistrer("Combien coûte le BOR-CEI ?", ["catalogue.pdf"], False)
    journal.enregistrer("C'est quoi le tarif du chauffe-eau BOR-CEI ?", ["catalogue.pdf"], False)
    journal.enregistrer("Quelle est la durée de garantie ?", ["garantie.pdf"], False)
    s = journal.stats(embed_fn=_embed_factice)
    assert s["groupement"] == "semantique"
    # Un seul sujet « prix » qui cumule les 4 questions, 3 formulations.
    assert s["sujets"][0]["n"] == 4
    assert s["sujets"][0]["formulations"] == 3
    # Le représentant est la formulation la plus posée.
    assert s["sujets"][0]["question"] == "Quel est le prix du BOR-CEI ?"
    assert len(s["sujets"]) == 2 and s["nb_sujets"] == 2


def test_embed_en_echec_repli_lexical(journal_actif):
    journal.enregistrer("Question A ?", [], False)
    journal.enregistrer("Question B ?", [], False)

    def embed_casse(_):
        raise RuntimeError("modèle indisponible")

    s = journal.stats(embed_fn=embed_casse)
    assert s["groupement"] == "lexical"  # repli silencieux, jamais d'erreur
    assert s["total"] == 2


def test_rechercher(journal_actif):
    from datetime import date
    journal.enregistrer("Prix du BOR-CEI ?", ["catalogue.pdf"], False)
    journal.enregistrer("Garantie des thermopompes ?", ["garantie.pdf"], True)
    auj = date.today().isoformat()
    # Filtre par période (bornes incluses) — plus récentes d'abord.
    r = journal.rechercher(debut=auj, fin=auj)
    assert r["total"] == 2
    assert r["questions"][0]["question"] == "Garantie des thermopompes ?"
    # Filtre par texte, insensible à la casse.
    r = journal.rechercher(texte="GARANTIE")
    assert r["total"] == 1 and r["questions"][0]["refus"] is True
    # Période sans correspondance.
    assert journal.rechercher(fin="2000-01-01")["total"] == 0
    # Limite bornée et robuste.
    assert journal.rechercher(limite="abc")["total"] == 2


def test_lignes_corrompues_tolerees(journal_actif):
    journal.enregistrer("Question valide ?", [], False)
    with open(journal.chemin(), "a", encoding="utf-8") as f:
        f.write("ceci n'est pas du JSON\n{\"sans_question\": 1}\n")
    s = journal.stats()
    assert s["total"] == 1  # les lignes invalides sont ignorées sans erreur
