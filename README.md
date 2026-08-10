# Assistant documentaire (démo RAG)

Assistant qui répond aux questions **à partir des documents d'une entreprise**, avec la **source citée** à chaque réponse. C'est le cas de démonstration à montrer en partage d'écran pendant la prospection.

La démo est pré-remplie avec une PME fictive (**Boréale Équipement**, distributeur CVC/plomberie) et ses documents : manuel employé, catalogue produits, politique de garantie, procédures internes, FAQ. Pour une démo client, on remplace le dossier `data/` par leurs documents et on relance l'ingestion — rien d'autre à changer.

## Stack

- **Chroma** — base vectorielle locale et persistante (aucun service cloud à configurer).
- **fastembed** — embeddings multilingues **locaux** par défaut (aucune clé, rien ne sort de l'instance). Bascule sur OpenAI avec `EMBEDDING_PROVIDER=openai`.
- **Claude** ou **OpenAI** pour la génération (`LLM_PROVIDER`). Auto : Claude si seule la clé Anthropic est présente.
- **FastAPI** — serveur de démonstration : API `/api/*`, widget de chat embarquable, espace d'administration.
- **Streamlit** (`app.py`) — interface d'appoint pour tester en local.

Architecture RAG classique (chargement → découpage → embeddings → récupération → génération sourcée), enrichie de deux correctifs mesurés sur le test des 20 questions : extraction **géométrique des tableaux** (`core/ingest_ameliore.py`) et **récupération hybride** mot-clé + vectoriel (`core/recherche_hybride.py`).

Aucune base de données : le journal des questions est un simple fichier **JSONL en ajout seul**.

## Démarrage (5 minutes)

```bash
# 1. Environnement
python -m venv venv && source venv/bin/activate      # Windows : venv\Scripts\activate
pip install -r requirements.txt

# 2. Clé API (une seule suffit pour démarrer)
cp .env.example .env       # puis éditez .env et collez votre ANTHROPIC_API_KEY
                           # le .env est chargé automatiquement, rien d'autre à faire

# 3. Indexer les documents
python ingest.py

# 4. Lancer le serveur web
python -m uvicorn server:app --reload
```

- `http://localhost:8000` — site de démonstration avec l'assistant en bulle, intégré ou plein écran.
- `http://localhost:8000/gestion.html` — espace d'administration : documents et statistiques d'usage.

Pour l'interface Streamlit d'appoint : `streamlit run app.py` (port 8501).

## Tester sans clé API

```bash
pip install -r requirements-dev.txt
python -m pytest
```

**90 tests, aucun appel réseau, aucune clé, quelques secondes.** La suite injecte un embedding déterministe et un double du cœur RAG : elle ne consomme aucun crédit d'API.

| Fichier | Ce qu'il couvre |
|---|---|
| `tests/test_pipeline.py` | Chargement → découpage → indexation → récupération, bout en bout |
| `tests/test_documents.py` | PDF et DOCX corrompus, encodages non UTF-8, formats inconnus, réindexation |
| `tests/test_admin_documents.py` | Téléversement, listing, suppression et tous leurs chemins d'erreur |
| `tests/test_journal.py` | Journal des questions : écriture, regroupement par sens, recherche |
| `tests/test_journal_limites.py` | Journal absent, vide, tronqué, corrompu ; paramètres hostiles |
| `tests/test_protections.py` | Authentification, CORS, limite de débit, requêtes malformées |

Les tests travaillent **exclusivement dans des dossiers temporaires** : ni `chroma_db/`, ni `data/`, ni `logs/`, ni le `.env` ne sont touchés.

## Adapter à un client

1. Videz `data/` et déposez-y les documents du client (`.pdf`, `.docx`, `.md`, `.txt`). Ou, sans toucher au serveur : déposez-les depuis `gestion.html`, ils sont indexés à chaud.
2. Via `.env`, ajustez `CLIENT_NAME` et `ASSISTANT_NAME`.
3. Adaptez le cadre de comportement de l'assistant (ton, périmètre, confidentialité) : c'est le `SYSTEM_PROMPT` de `core/rag_core.py`, et rien d'autre.
4. `python ingest.py`, puis relancez le serveur.

## Réglages (variables d'environnement)

| Variable | Défaut | Rôle |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Requis si la génération passe par Claude |
| `OPENAI_API_KEY` | — | Requis si la génération passe par OpenAI |
| `LLM_PROVIDER` | auto | `openai` ou `anthropic` (auto selon la clé présente) |
| `EMBEDDING_PROVIDER` | auto | `local` (défaut, sans clé) ou `openai` |
| `TOP_K` | `8` | Nombre d'extraits récupérés par question |
| `CHUNK_SIZE` | `900` | Taille des chunks (caractères) |
| `CLIENT_NAME` | `Boréale Équipement` | Nom affiché dans l'UI |
| `DATA_DIR` | `data` | Dossier des documents |
| `MAX_UPLOAD_MB` | `20` | Taille maximale d'un document téléversé |
| `DEMO_PASSWORD` | — | Mot de passe du chat (vide = pas d'authentification) |
| `ADMIN_PASSWORD` | — | Mot de passe de l'administration (repli sur `DEMO_PASSWORD`) |
| `ALLOWED_ORIGINS` | `*` | Domaines autorisés à appeler l'API (CORS) |
| `RATE_LIMIT` | `30/minute` | Limite de débit par IP sur `/api/chat` |
| `LOG_QUESTIONS` | `0` | Journal des questions (opt-in strict) |
| `LOG_DIR` | `logs` | Dossier du fichier `questions.jsonl` |

## Interfaces

Le widget (`web/widget.js`) et l'espace d'administration (`web/gestion.html`) partagent **un seul système de design** : mêmes jetons de couleur, mêmes ombres, même typographie. Les jetons du widget sont préfixés `--da-` pour ne jamais entrer en collision avec la feuille de style du site hôte. Toute modification d'un jeton doit être répercutée dans les deux fichiers.

## Limites (à dire au client, c'est une démo)

- Pas de gestion multi-utilisateurs : un mot de passe partagé pour le chat, un pour l'administration.
- Documents scannés non gérés (pas d'OCR) — l'assistant le dit explicitement au téléversement.
- Pas de mise à jour incrémentale par `ingest.py` : il réindexe tout le corpus. (Le téléversement depuis `gestion.html`, lui, est bien incrémental.)

Ces limites correspondent exactement au **hors-scope** de l'offre de lancement. Les lever se fait sur devis séparé.
