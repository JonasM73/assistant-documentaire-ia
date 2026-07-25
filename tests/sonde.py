"""
sonde.py — Diagnostic : que contient l'index, et que renvoie la recherche hybride ?
À lancer dans le dossier rag-demo, après avoir indexé data_controle.

    $env:DATA_DIR="data_controle"; $env:LLM_PROVIDER="anthropic"
    python sonde.py
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core"))

import rag_core
import recherche_hybride

col = rag_core.get_collection()
tout = col.get()
docs = tout.get("documents", []) or []
metas = tout.get("metadatas", []) or []
print(f"Index : {len(docs)} chunks au total")

# répartition par source
from collections import Counter
par_source = Counter(m.get("source","?") for m in metas)
for s, n in par_source.items():
    print(f"   {s} : {n} chunks")

# la fiche S001 existe-t-elle dans l'index ?
print("\nRecherche brute de 'Code : S001' dans l'index :")
for d, m in zip(docs, metas):
    if "Code : S001" in d or "S001" in d[:40]:
        print(f"   TROUVÉ dans {m['source']} : {d[:80]}")
        break
else:
    print("   ABSENT — la fiche S001 n'est pas dans l'index !")

# la fiche étape 3 ?
print("\nRecherche brute de 'Étape : 3' :")
for d, m in zip(docs, metas):
    if "Étape : 3" in d:
        print(f"   TROUVÉ dans {m['source']} : {d[:80]}")
        break
else:
    print("   ABSENT")

# maintenant la recherche hybride est-elle active ?
print("\nretrieve est hybride ?", getattr(rag_core.retrieve, "_hybride", False))
recherche_hybride.activer()
print("après activer() :", getattr(rag_core.retrieve, "_hybride", False))

# que renvoie une recherche sur S001 ?
print("\nRecherche hybride 'tarif Premium de la prestation S001' :")
chunks = rag_core.retrieve("tarif Premium de la prestation S001")
for c in chunks[:5]:
    print(f"   [{c['source']}] {c['text'][:70]}")