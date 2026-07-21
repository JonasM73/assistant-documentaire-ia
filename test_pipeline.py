"""
test_pipeline.py — Test hors-ligne de l'orchestration RAG.

Ce test N'UTILISE PAS d'API : il injecte un embedding local déterministe
(bag-of-words hashé) uniquement pour vérifier que le chargement, le découpage,
le stockage vectoriel et la récupération s'enchaînent correctement.

En production, l'embedding OpenAI (get_embedding_function) est bien plus précis.
Lancer :  python test_pipeline.py
"""

import hashlib
import re
import chromadb.utils.embedding_functions as ef_mod

import rag_core


class HashEmbeddingFunction(ef_mod.EmbeddingFunction):
    """Embedding déterministe, sans réseau, pour les tests uniquement."""
    DIM = 256

    def __init__(self):
        pass

    def __call__(self, input):
        vecs = []
        for text in input:
            vec = [0.0] * self.DIM
            for tok in re.findall(r"\w+", text.lower()):
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                vec[h % self.DIM] += 1.0
            norm = sum(v * v for v in vec) ** 0.5 or 1.0
            vecs.append([v / norm for v in vec])
        return vecs


def main():
    fake_ef = HashEmbeddingFunction()

    # 1. Chargement
    docs = rag_core.load_documents()
    assert docs, "aucun document chargé"
    print(f"[1] Documents chargés : {len(docs)} -> {[d.source for d in docs]}")

    # 2. Découpage
    total_chunks = sum(len(rag_core.chunk_text(d.text)) for d in docs)
    print(f"[2] Chunks générés : {total_chunks}")
    assert total_chunks >= len(docs)

    # 3. Indexation (embedding local)
    n = rag_core.build_index(embedding_function=fake_ef, reset=True)
    print(f"[3] Chunks indexés dans Chroma : {n}")
    assert n == total_chunks

    # 4. Récupération
    q = "vacances ancienneté"
    chunks = rag_core.retrieve(q, embedding_function=fake_ef, top_k=3)
    print(f"[4] Requête '{q}' -> {len(chunks)} extraits récupérés")
    for c in chunks:
        print(f"      - {c['source']} (extrait {c['chunk']})")
    assert chunks, "aucun extrait récupéré"
    # l'extrait le plus pertinent devrait venir du manuel employé
    assert any("manuel" in c["source"] for c in chunks), \
        "récupération incohérente : le manuel employé devrait ressortir"

    print("\nTOUS LES TESTS PASSENT. L'orchestration fonctionne.")
    print("En production, ajoutez OPENAI_API_KEY et lancez `python ingest.py`.")


if __name__ == "__main__":
    main()
