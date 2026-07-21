"""
ingest.py — Indexe les documents du dossier data/ dans la base vectorielle.

Usage :
    python ingest.py

Relancez ce script chaque fois que vous ajoutez ou modifiez des documents.
Pour indexer les documents d'un client, remplacez le contenu de data/ (ou
pointez la variable DATA_DIR sur son dossier) et relancez.
"""

from rag_core import build_index

if __name__ == "__main__":
    print("Indexation des documents en cours...")
    n = build_index(reset=True)
    print(f"OK — {n} chunks indexés. La base est prête (dossier chroma_db/).")
    print("Lancez l'interface avec :  streamlit run app.py")
