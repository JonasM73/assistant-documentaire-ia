"""
test_documents.py — Lecture et découpage des documents, cas limites.

Un client dépose ce qu'il a sous la main : PDF scanné, fichier renommé à la
main, export Word corrompu, texte en cp1252. Rien de tout cela ne doit produire
une trace technique — au pire un message qui dit quoi faire.

Lancement :  python -m pytest tests/test_documents.py -q
"""

import os

import pytest

import ingest_ameliore
import rag_core

# En-tête de PDF valide suivi de n'importe quoi : le fichier ressemble à un PDF
# mais aucun lecteur ne peut en tirer du texte.
PDF_CORROMPU = b"%PDF-1.4\n" + b"\x00\xff" * 200


# --------------------------------------------------------------------------- #
# Lecture d'un document isolé
# --------------------------------------------------------------------------- #

def test_lecture_texte_utf8(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("Garantie de dix ans sur le compresseur.", encoding="utf-8")
    assert "compresseur" in rag_core.lire_document(str(p))


def test_lecture_texte_cp1252(tmp_path):
    """Un .txt produit par un Windows francophone n'est pas en UTF-8."""
    p = tmp_path / "note.txt"
    p.write_bytes("Délai de livraison : 5 jours ouvrés.".encode("cp1252"))
    texte = rag_core.lire_document(str(p))
    assert "Délai" in texte and "ouvrés" in texte


def test_lecture_fichier_vide(tmp_path):
    p = tmp_path / "vide.md"
    p.write_text("", encoding="utf-8")
    assert rag_core.lire_document(str(p)) == ""


def test_lecture_format_inconnu(tmp_path):
    p = tmp_path / "image.png"
    p.write_bytes(b"\x89PNG")
    with pytest.raises(ValueError, match="Format non supporté"):
        rag_core.lire_document(str(p))


def test_lecture_fichier_absent(tmp_path):
    with pytest.raises(OSError):
        rag_core.lire_document(str(tmp_path / "absent.txt"))


def test_lecture_pdf_corrompu(tmp_path):
    p = tmp_path / "casse.pdf"
    p.write_bytes(PDF_CORROMPU)
    with pytest.raises(Exception):
        rag_core.lire_document(str(p))


def test_lecture_docx_corrompu(tmp_path):
    p = tmp_path / "casse.docx"
    p.write_bytes(b"PK\x03\x04 ceci n'est pas un docx")
    with pytest.raises(Exception):
        rag_core.lire_document(str(p))


# --------------------------------------------------------------------------- #
# Découpage pour l'indexation
# --------------------------------------------------------------------------- #

def test_chunks_document_texte(tmp_path):
    p = tmp_path / "faq.md"
    p.write_text("# FAQ\n\nLivraison en 5 jours.\n\nRetours sous 30 jours.\n",
                 encoding="utf-8")
    chunks, methode = ingest_ameliore.chunks_document(str(p))
    assert chunks and methode == "paragraphes"


def test_chunks_document_vide(tmp_path):
    p = tmp_path / "vide.txt"
    p.write_text("   \n\n  ", encoding="utf-8")
    assert ingest_ameliore.chunks_document(str(p)) == ([], "vide")


def test_chunks_document_format_inconnu(tmp_path):
    p = tmp_path / "archive.zip"
    p.write_bytes(b"PK\x03\x04")
    with pytest.raises(ValueError, match="Format non supporté"):
        ingest_ameliore.chunks_document(str(p))


def test_chunks_pdf_corrompu_message_explicite(tmp_path):
    """pdfplumber puis pypdf échouent : l'erreur doit rester compréhensible."""
    p = tmp_path / "scan.pdf"
    p.write_bytes(PDF_CORROMPU)
    with pytest.raises(ValueError, match="PDF illisible"):
        ingest_ameliore.chunks_document(str(p))


def test_chunks_pdf_reel():
    """Les PDF de démonstration doivent produire des extraits étiquetés."""
    data = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    pdf = os.path.join(data, "Catalogue-produits.pdf")
    if not os.path.exists(pdf):
        pytest.skip("PDF de démonstration absent")
    chunks, methode = ingest_ameliore.chunks_document(pdf)
    assert chunks and all(isinstance(c, str) and c.strip() for c in chunks)
    assert methode in ("tableau+prose", "paragraphes", "paragraphes (repli)")


def test_indexation_ignore_un_document_illisible(tmp_path, dossier_chroma,
                                                 embedding_factice):
    """Un PDF corrompu au milieu du corpus ne doit pas empêcher d'indexer
    les autres documents."""
    data = tmp_path / "corpus"
    data.mkdir()
    (data / "bon.txt").write_text("Livraison en 5 jours ouvrés.", encoding="utf-8")
    (data / "casse.pdf").write_bytes(PDF_CORROMPU)

    n = ingest_ameliore.build_index_ameliore(
        data_dir=str(data), chroma_dir=dossier_chroma,
        embedding_function=embedding_factice, verbeux=False)
    assert n >= 1
    chunks = rag_core.retrieve("livraison", embedding_function=embedding_factice,
                               chroma_dir=dossier_chroma)
    assert any("bon.txt" == c["source"] for c in chunks)


def test_index_file_reindexe_sans_doublon(tmp_path, dossier_chroma, embedding_factice):
    """Ré-envoyer le même document remplace ses extraits au lieu de les cumuler."""
    p = tmp_path / "faq.txt"
    p.write_text("Retours acceptés sous 30 jours.", encoding="utf-8")
    n1 = ingest_ameliore.index_file(str(p), chroma_dir=dossier_chroma,
                                    embedding_function=embedding_factice)
    n2 = ingest_ameliore.index_file(str(p), chroma_dir=dossier_chroma,
                                    embedding_function=embedding_factice)
    assert n1 == n2
    col = rag_core.get_collection(embedding_factice, dossier_chroma)
    assert col.count() == n1
