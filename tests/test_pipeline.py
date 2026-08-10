"""
test_pipeline.py — Test hors-ligne de l'orchestration RAG.

Ce test N'UTILISE AUCUNE API : il injecte un embedding local déterministe
(voir conftest.py) pour vérifier que le chargement, le découpage, le stockage
vectoriel et la récupération s'enchaînent correctement.

Il travaille exclusivement dans des dossiers temporaires : ni l'index réel
(chroma_db/) ni les documents réels (data/) ne sont modifiés.

Lancement :  python -m pytest tests/test_pipeline.py -q
"""

import os

import pytest

import rag_core


# --------------------------------------------------------------------------- #
# 1. Chargement des documents
# --------------------------------------------------------------------------- #

def test_chargement_documents(dossier_documents):
    docs = rag_core.load_documents(dossier_documents)
    sources = sorted(d.source for d in docs)
    assert sources == ["Catalogue.txt", "Manuel-employe.md"]
    assert all(d.text.strip() for d in docs)


def test_chargement_ignore_les_formats_non_supportes(dossier_documents):
    with open(os.path.join(dossier_documents, "photo.png"), "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
    assert len(rag_core.load_documents(dossier_documents)) == 2


def test_chargement_dossier_inexistant(tmp_path):
    """Un dossier absent ne lève pas : il ne contient simplement rien."""
    assert rag_core.load_documents(str(tmp_path / "nexiste-pas")) == []


def test_chargement_ignore_un_pdf_corrompu(dossier_documents):
    """Un PDF illisible est ignoré : il ne doit pas faire échouer le lot."""
    with open(os.path.join(dossier_documents, "corrompu.pdf"), "wb") as f:
        f.write(b"%PDF-1.4 ceci n'est pas un vrai PDF")
    docs = rag_core.load_documents(dossier_documents)
    assert sorted(d.source for d in docs) == ["Catalogue.txt", "Manuel-employe.md"]


def test_chargement_ignore_un_fichier_vide(dossier_documents):
    open(os.path.join(dossier_documents, "vide.txt"), "w").close()
    assert len(rag_core.load_documents(dossier_documents)) == 2


# --------------------------------------------------------------------------- #
# 2. Découpage
# --------------------------------------------------------------------------- #

def test_decoupage_texte_vide():
    assert rag_core.chunk_text("") == []
    assert rag_core.chunk_text("   \n\n  ") == []


def test_decoupage_paragraphe_court():
    assert rag_core.chunk_text("Un seul paragraphe court.") == ["Un seul paragraphe court."]


def test_decoupage_respecte_la_taille():
    texte = "\n\n".join(f"Paragraphe numéro {i} " + "mot " * 40 for i in range(20))
    chunks = rag_core.chunk_text(texte, size=300, overlap=50)
    assert len(chunks) > 1
    # taille + chevauchement recollé en tête : on tolère la marge du chevauchement
    assert all(len(c) <= 300 + 50 + 1 for c in chunks)


def test_decoupage_coupe_un_paragraphe_geant():
    chunks = rag_core.chunk_text("x" * 5000, size=500, overlap=100)
    assert len(chunks) > 1
    assert "".join(c.replace(" ", "") for c in chunks).count("x") >= 5000


# --------------------------------------------------------------------------- #
# 3. Indexation + récupération (bout en bout, hors-ligne)
# --------------------------------------------------------------------------- #

def test_indexation_et_recuperation(dossier_documents, dossier_chroma, embedding_factice):
    docs = rag_core.load_documents(dossier_documents)
    total = sum(len(rag_core.chunk_text(d.text)) for d in docs)

    n = rag_core.build_index(embedding_function=embedding_factice,
                             data_dir=dossier_documents,
                             chroma_dir=dossier_chroma, reset=True)
    assert n == total

    chunks = rag_core.retrieve("vacances ancienneté", embedding_function=embedding_factice,
                               top_k=3, chroma_dir=dossier_chroma)
    assert chunks, "aucun extrait récupéré"
    assert any("manuel" in c["source"].lower() for c in chunks), \
        "récupération incohérente : le manuel employé devrait ressortir"
    assert all({"source", "chunk", "text"} <= set(c) for c in chunks)


def test_indexation_dossier_vide(tmp_path, dossier_chroma, embedding_factice):
    vide = tmp_path / "sans-docs"
    vide.mkdir()
    with pytest.raises(RuntimeError):
        rag_core.build_index(embedding_function=embedding_factice,
                             data_dir=str(vide), chroma_dir=dossier_chroma)


def test_recuperation_index_absent(dossier_chroma, embedding_factice):
    """Interroger un index qui n'existe pas donne une erreur explicite,
    pas une exception technique de Chroma."""
    with pytest.raises(rag_core.IndexIntrouvable):
        rag_core.retrieve("une question", embedding_function=embedding_factice,
                          chroma_dir=dossier_chroma)


def test_reponse_sans_index(dossier_chroma, embedding_factice):
    """answer_question ne doit jamais remonter d'exception à l'utilisateur
    quand l'index n'a pas encore été construit."""
    res = rag_core.answer_question("une question", embedding_function=embedding_factice,
                                   chroma_dir=dossier_chroma)
    assert res.sources == [] and res.chunks == []
    assert "indexé" in res.answer.lower()


# --------------------------------------------------------------------------- #
# 4. Corpus réel de démonstration (facultatif)
# --------------------------------------------------------------------------- #

def test_corpus_de_demonstration_lisible():
    """Les PDF livrés avec la démo doivent tous se charger."""
    data = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    if not os.path.isdir(data):
        pytest.skip("dossier data/ absent")
    docs = rag_core.load_documents(data)
    assert docs, "aucun document chargé depuis data/"
