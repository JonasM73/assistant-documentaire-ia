"""
test_journal_limites.py — Cas limites du journal et du tableau de bord.

Le journal est un simple fichier JSONL en ajout seul : il peut être vide,
tronqué au milieu d'une ligne, contenir des entrées d'une version antérieure,
ou disparaître. Aucun de ces cas ne doit faire tomber /api/admin/stats ni
l'explorateur de questions.

Lancement :  python -m pytest tests/test_journal_limites.py -q
"""

import importlib
import json
import os

import pytest

import journal

ADMIN = {"X-API-Password": "admin456"}


@pytest.fixture
def journal_actif(tmp_path, monkeypatch):
    monkeypatch.setenv("LOG_QUESTIONS", "1")
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    importlib.reload(journal)
    journal._CACHE["sig"] = None      # le cache ne doit pas traverser les tests
    return tmp_path


def ecrire(chemin, lignes):
    with open(chemin, "w", encoding="utf-8") as f:
        f.write("\n".join(lignes) + "\n" if lignes else "")


# --------------------------------------------------------------------------- #
# Journal absent, vide ou illisible
# --------------------------------------------------------------------------- #

def test_journal_absent(journal_actif):
    assert not os.path.exists(journal.chemin())
    assert journal.lire() == []
    s = journal.stats()
    assert s["total"] == 0 and s["refus"] == 0 and s["taux_refus"] == 0.0
    assert len(s["par_jour"]) == 60 and s["sujets"] == []
    assert journal.rechercher() == {"total": 0, "questions": []}


def test_journal_vide(journal_actif):
    open(journal.chemin(), "w").close()
    assert journal.lire() == []
    assert journal.stats()["total"] == 0


def test_journal_seulement_des_lignes_blanches(journal_actif):
    ecrire(journal.chemin(), ["", "   ", ""])
    assert journal.stats()["total"] == 0


def test_journal_tronque_en_cours_de_ligne(journal_actif):
    """Coupure d'alimentation pendant une écriture : la dernière ligne est
    incomplète, les précédentes doivent rester exploitables."""
    journal.enregistrer("Question complète ?", ["a.pdf"], False)
    with open(journal.chemin(), "a", encoding="utf-8") as f:
        f.write('{"date": "2026-01-01T10:00:00", "quest')
    s = journal.stats()
    assert s["total"] == 1


def test_journal_illisible(journal_actif, monkeypatch):
    """Un dossier là où on attend un fichier : lecture impossible, pas de crash."""
    os.makedirs(journal.chemin(), exist_ok=True)
    assert journal.lire() == []
    assert journal.stats()["total"] == 0


def test_ecriture_impossible_ne_casse_pas_la_reponse(journal_actif, monkeypatch):
    def boum(*a, **k):
        raise OSError("disque plein")
    monkeypatch.setattr("builtins.open", boum)
    journal.enregistrer("Une question ?", [], False)   # ne doit rien lever


# --------------------------------------------------------------------------- #
# Entrées mal formées
# --------------------------------------------------------------------------- #

def test_entrees_de_types_inattendus(journal_actif):
    ecrire(journal.chemin(), [
        json.dumps({"question": "Sources en texte ?", "sources": "catalogue.pdf",
                    "date": "2026-08-10T09:00:00", "refus": False}),
        json.dumps({"question": "Sources nulles ?", "sources": None,
                    "date": "2026-08-10T09:01:00", "refus": None}),
        json.dumps({"question": 12345, "date": "2026-08-10T09:02:00"}),
        json.dumps({"question": "Sans date ?"}),
        json.dumps(["une liste, pas un objet"]),
        json.dumps({"pas_de_champ_question": 1}),
    ])
    s = journal.stats()
    assert s["total"] == 4          # les deux dernières lignes sont rejetées
    # Une source en chaîne ne doit pas être éclatée lettre par lettre.
    assert s["sources"] == [{"source": "catalogue.pdf", "n": 1}]
    r = journal.rechercher()
    assert r["total"] == 4
    assert all(isinstance(q["question"], str) for q in r["questions"])
    assert all(isinstance(q["sources"], list) for q in r["questions"])


def test_dates_malformees(journal_actif):
    ecrire(journal.chemin(), [
        json.dumps({"question": "Date vide ?", "date": ""}),
        json.dumps({"question": "Date absurde ?", "date": "pas-une-date"}),
        json.dumps({"question": "Heure absurde ?", "date": "2026-08-10T99:99:99"}),
    ])
    s = journal.stats()
    assert s["total"] == 3
    assert sum(s["par_heure"]) == 0
    # Seule la 3e entrée a une PARTIE DATE valide (l'heure, elle, est absurde) :
    # elle compte dans le rythme hebdomadaire, pas dans le rythme horaire.
    assert sum(s["par_semaine"]) == 1


def test_duree_de_type_invalide(journal_actif):
    ecrire(journal.chemin(), [
        json.dumps({"question": "A ?", "date": "2026-08-10T09:00:00", "duree": "lent"}),
        json.dumps({"question": "B ?", "date": "2026-08-10T09:00:00", "duree": -5}),
        json.dumps({"question": "C ?", "date": "2026-08-10T09:00:00", "duree": 4.0}),
    ])
    assert journal.stats()["duree_moyenne"] == 4.0


# --------------------------------------------------------------------------- #
# Recherche : paramètres hostiles
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("limite", [0, -10, 10 ** 9, "abc", None, 1.5])
def test_recherche_limite_hostile(journal_actif, limite):
    for i in range(5):
        journal.enregistrer(f"Question {i} ?", [], False)
    r = journal.rechercher(limite=limite)
    assert r["total"] == 5
    assert 1 <= len(r["questions"]) <= 500


def test_recherche_dates_malformees(journal_actif):
    journal.enregistrer("Une question ?", [], False)
    for debut, fin in [("pas-une-date", ""), ("", "pas-une-date"),
                       ("2026-13-45", "2026-99-99"), ("2030-01-01", "2020-01-01")]:
        r = journal.rechercher(debut=debut, fin=fin)
        assert isinstance(r["total"], int) and isinstance(r["questions"], list)


def test_recherche_texte_hostile(journal_actif):
    journal.enregistrer("Prix du BOR-CEI ?", [], False)
    assert journal.rechercher(texte=".*")["total"] == 0     # pas d'interprétation regex
    assert journal.rechercher(texte="BOR-CEI")["total"] == 1
    assert journal.rechercher(texte=None)["total"] == 1


# --------------------------------------------------------------------------- #
# Le tableau de bord côté API
# --------------------------------------------------------------------------- #

def test_api_stats_journal_desactive(client, monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_QUESTIONS", "0")
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "vide"))
    r = client.get("/api/admin/stats", headers=ADMIN)
    assert r.status_code == 200
    d = r.json()
    assert d["actif"] is False and d["total"] == 0
    assert len(d["par_jour"]) == 60 and len(d["par_heure"]) == 24


def test_api_stats_resiste_a_une_panne(client, monkeypatch):
    """Même si le calcul des statistiques échoue, la page reste affichable."""
    import server

    def boum(*a, **k):
        raise RuntimeError("journal corrompu")
    monkeypatch.setattr(server.journal, "stats", boum)
    r = client.get("/api/admin/stats", headers=ADMIN)
    assert r.status_code == 200
    d = r.json()
    assert d["total"] == 0 and d["sujets"] == [] and len(d["par_heure"]) == 24


def test_api_questions_parametres_hostiles(client):
    for params in ({"limite": "abc"}, {"limite": -1}, {"debut": "pas-une-date"},
                   {"q": "%00"}, {"fin": "2020-99-99"}, {}):
        r = client.get("/api/admin/questions", params=params, headers=ADMIN)
        assert r.status_code in (200, 422), params
        if r.status_code == 200:
            assert "total" in r.json() and "questions" in r.json()


def test_api_questions_exige_le_mot_de_passe_admin(client):
    assert client.get("/api/admin/questions").status_code == 401
    assert client.get("/api/admin/stats").status_code == 401
