"""
test_admin_documents.py — Cas limites de la gestion des documents.

Vérifie qu'AUCUN chemin d'erreur du téléversement, du listing ou de la
suppression ne produit de 500 nu ni de trace technique : l'administrateur doit
toujours lire une phrase en français qui lui dit quoi faire.

L'indexation réelle (Chroma + modèle d'embedding) est remplacée par un double :
ces tests portent sur le contrat HTTP, pas sur la qualité de l'indexation.

Lancement :  python -m pytest tests/test_admin_documents.py -q
"""

import os

import pytest

import ingest_ameliore
import server

ADMIN = {"X-API-Password": "admin456"}
CHAT = {"X-API-Password": "secret123"}


@pytest.fixture
def index_simule(monkeypatch):
    """Indexation simulée : compte les appels, renvoie un nombre de chunks."""
    appels = {"index": [], "deindex": []}

    def index_file(path, *a, **k):
        appels["index"].append(path)
        return 3

    def deindex_file(source, *a, **k):
        appels["deindex"].append(source)

    monkeypatch.setattr(ingest_ameliore, "index_file", index_file)
    monkeypatch.setattr(ingest_ameliore, "deindex_file", deindex_file)
    return appels


def envoyer(client, nom, contenu=b"Contenu du document.", headers=ADMIN):
    return client.post("/api/admin/upload",
                       files={"file": (nom, contenu, "application/octet-stream")},
                       headers=headers)


# --------------------------------------------------------------------------- #
# Téléversement
# --------------------------------------------------------------------------- #

def test_upload_nominal(client, index_simule):
    r = envoyer(client, "Manuel.txt")
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True and d["name"] == "Manuel.txt" and d["chunks"] == 3
    assert [f["name"] for f in client.get("/api/admin/files", headers=ADMIN).json()["files"]] \
        == ["Manuel.txt"]


def test_upload_exige_le_mot_de_passe_admin(client, index_simule):
    assert envoyer(client, "Manuel.txt", headers=None).status_code == 401
    assert envoyer(client, "Manuel.txt", headers=CHAT).status_code == 401


def test_upload_format_refuse(client, index_simule):
    r = envoyer(client, "virus.exe")
    assert r.status_code == 400
    assert "Format non supporté" in r.json()["detail"]
    assert not index_simule["index"]


def test_upload_sans_extension(client, index_simule):
    r = envoyer(client, "document")
    assert r.status_code == 400 and "sans extension" in r.json()["detail"]


def test_upload_fichier_vide(client, index_simule):
    r = envoyer(client, "vide.txt", contenu=b"")
    assert r.status_code == 400 and "vide" in r.json()["detail"].lower()
    # Aucun fichier fantôme ne doit rester sur le disque.
    assert client.get("/api/admin/files", headers=ADMIN).json()["files"] == []


def test_upload_trop_volumineux(client, index_simule, monkeypatch):
    monkeypatch.setattr(server, "MAX_UPLOAD_MB", 1)
    r = envoyer(client, "gros.txt", contenu=b"x" * (2 * 1024 * 1024))
    assert r.status_code == 400 and "volumineux" in r.json()["detail"]
    # Le fichier partiel est nettoyé : il ne doit pas apparaître dans la liste.
    assert client.get("/api/admin/files", headers=ADMIN).json()["files"] == []


def test_upload_nom_piege_reste_dans_le_dossier(client, index_simule):
    """Un nom de fichier hostile ne doit jamais sortir du dossier des documents."""
    r = envoyer(client, "../../../etc/passwd.txt")
    assert r.status_code == 200
    nom = r.json()["name"]
    assert "/" not in nom and "\\" not in nom and ".." not in nom
    chemin = index_simule["index"][0]
    assert os.path.dirname(os.path.abspath(chemin)) == \
        os.path.abspath(os.environ["DATA_DIR"])


def test_upload_nom_avec_accents_et_espaces(client, index_simule):
    r = envoyer(client, "Politique de garantie (2026).pdf")
    assert r.status_code == 200
    assert r.json()["name"].endswith(".pdf")


def test_upload_indexation_en_echec(client, monkeypatch):
    def boum(*a, **k):
        raise RuntimeError("Chroma indisponible")
    monkeypatch.setattr(ingest_ameliore, "index_file", boum)
    r = envoyer(client, "Manuel.txt")
    assert r.status_code == 500
    detail = r.json()["detail"]
    assert "enregistré" in detail and "indexation" in detail
    assert "Traceback" not in detail
    # Le fichier reste visible : l'administrateur peut le supprimer ou réessayer.
    assert [f["name"] for f in client.get("/api/admin/files", headers=ADMIN).json()["files"]] \
        == ["Manuel.txt"]


def test_upload_document_sans_texte(client, monkeypatch):
    monkeypatch.setattr(ingest_ameliore, "index_file", lambda *a, **k: 0)
    r = envoyer(client, "scan.pdf")
    assert r.status_code == 422 and "OCR" in r.json()["detail"]


# --------------------------------------------------------------------------- #
# Listing
# --------------------------------------------------------------------------- #

def test_liste_vide(client):
    r = client.get("/api/admin/files", headers=ADMIN)
    assert r.status_code == 200 and r.json()["files"] == []


def test_liste_triee_et_dimensionnee(client, index_simule):
    for nom in ("Zebre.txt", "alpha.md", "Beta.txt"):
        envoyer(client, nom, contenu=b"abc")
    files = client.get("/api/admin/files", headers=ADMIN).json()["files"]
    assert [f["name"] for f in files] == ["alpha.md", "Beta.txt", "Zebre.txt"]
    assert all(f["size"] == 3 for f in files)


# --------------------------------------------------------------------------- #
# Suppression
# --------------------------------------------------------------------------- #

def test_suppression_nominale(client, index_simule):
    envoyer(client, "Manuel.txt")
    r = client.post("/api/admin/delete", data={"name": "Manuel.txt"}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["existait"] is True
    assert index_simule["deindex"] == ["Manuel.txt"]
    assert client.get("/api/admin/files", headers=ADMIN).json()["files"] == []


def test_suppression_fichier_inconnu(client, index_simule):
    """Supprimer un document déjà absent n'est pas une erreur : on désindexe
    quand même, au cas où des vecteurs orphelins subsistent."""
    r = client.post("/api/admin/delete", data={"name": "fantome.txt"}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["existait"] is False


def test_suppression_nom_vide(client, index_simule):
    r = client.post("/api/admin/delete", data={"name": "   "}, headers=ADMIN)
    assert r.status_code == 400


def test_suppression_desindexation_en_echec(client, index_simule, monkeypatch):
    envoyer(client, "Manuel.txt")

    def boum(*a, **k):
        raise RuntimeError("Chroma indisponible")
    monkeypatch.setattr(ingest_ameliore, "deindex_file", boum)
    r = client.post("/api/admin/delete", data={"name": "Manuel.txt"}, headers=ADMIN)
    assert r.status_code == 500 and "désindexation" in r.json()["detail"]


def test_suppression_exige_le_mot_de_passe_admin(client, index_simule):
    assert client.post("/api/admin/delete", data={"name": "x.txt"}).status_code == 401
