"""ingest.py — Indexe les documents. Utilise l'ingestion améliorée (tableaux)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))
from ingest_ameliore import build_index_ameliore

if __name__ == "__main__":
    print("Indexation en cours...")
    n = build_index_ameliore()
    print(f"OK — {n} chunks indexés.")