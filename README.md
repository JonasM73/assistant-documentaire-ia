# Assistant documentaire (démo RAG)

Assistant qui répond aux questions **à partir des documents d'une entreprise**, avec la **source citée** à chaque réponse. C'est le cas de démonstration à montrer en partage d'écran pendant la prospection.

La démo est pré-remplie avec une PME fictive (**Boréale Équipement**, distributeur CVC/plomberie) et ses documents : manuel employé, catalogue produits, politique de garantie, procédures internes, FAQ. Pour une démo client, on remplace le dossier `data/` par leurs documents et on relance l'ingestion — rien d'autre à changer.

## Stack

- **Chroma** — base vectorielle locale et persistante (aucun service cloud à configurer).
- **OpenAI** — embeddings (`text-embedding-3-small`) + génération (`gpt-4o-mini`) par défaut.
- **Streamlit** — interface de démonstration.
- Bascule optionnelle vers **Claude** pour la génération (`LLM_PROVIDER=anthropic`).

Architecture RAG classique (chargement → découpage → embeddings → récupération → génération sourcée) ; transposable à LangChain ou LlamaIndex si un client le demande.

## Démarrage (5 minutes)

```bash
# 1. Environnement
python -m venv venv && source venv/bin/activate      # Windows : venv\Scripts\activate
pip install -r requirements.txt

# 2. Clé API (une seule suffit pour démarrer)
cp .env.example .env       # puis éditez .env et collez votre OPENAI_API_KEY
                           # le .env est chargé automatiquement, rien d'autre à faire

# 3. Indexer les documents
python ingest.py

# 4. Lancer l'interface
streamlit run app.py
```

L'interface s'ouvre sur `http://localhost:8501`. Cliquez une question d'exemple dans la barre latérale ou tapez la vôtre.

## Tester sans clé API

```bash
python test_pipeline.py
```

Vérifie tout l'enchaînement (chargement, découpage, stockage, récupération) avec un embedding local déterministe — utile pour valider l'installation avant d'ajouter la clé.

## Adapter à un client

1. Videz `data/` et déposez-y les documents du client (`.md` ou `.txt` ; pour PDF/DOCX, étendre `load_documents` dans `rag_core.py`).
2. Dans `app.py` ou via `.env`, ajustez `CLIENT_NAME` et `ASSISTANT_NAME`.
3. `python ingest.py` puis `streamlit run app.py`.

## Réglages (variables d'environnement)

| Variable | Défaut | Rôle |
|---|---|---|
| `OPENAI_API_KEY` | — | Requis (embeddings + génération par défaut) |
| `LLM_PROVIDER` | `openai` | `openai` ou `anthropic` |
| `ANTHROPIC_API_KEY` | — | Requis si `LLM_PROVIDER=anthropic` |
| `TOP_K` | `5` | Nombre d'extraits récupérés par question |
| `CHUNK_SIZE` | `900` | Taille des chunks (caractères) |
| `CLIENT_NAME` | `Boréale Équipement` | Nom affiché dans l'UI |

## Limites (à dire au client, c'est une démo)

- Pas d'authentification ni de gestion multi-utilisateurs.
- Documents en `.md`/`.txt` par défaut ; PDF/DOCX à brancher.
- Pas de mise à jour incrémentale : on réindexe tout le corpus à chaque `ingest.py`.

Ces limites correspondent exactement au **hors-scope** de l'offre de lancement. Les lever se fait sur devis séparé.
