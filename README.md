# Assistant documentaire (démo RAG)

Assistant qui répond aux questions **à partir des documents d'une entreprise**, avec la **source citée** à chaque réponse. C'est le cas de démonstration à montrer en partage d'écran pendant la prospection.

Deux jeux de démonstration sont dans le dépôt : `data-immobilier/` (**Horizon Immobilier**, réseau d'agences fictif, France — **c'est la vitrine publique**, voir `DEMO-IMMOBILIER.md`) et `data/` (Boréale Équipement, ancien jeu québécois en dollars, **plus montré nulle part** ; à remplacer par un jeu français ou à supprimer). Pour une démo client, on pointe `DATA_DIR` sur leurs documents et on relance l'ingestion — rien d'autre à changer.

Le déploiement de référence est **Railway** (`railway.json` : commande de démarrage, sonde `/api/health`, en-têtes de proxy). Les procédures client sont dans `docs/` : ouverture des comptes, déploiement, exploitation, sauvegarde.

## Stack

- **Chroma** — base vectorielle locale et persistante (aucun service cloud à configurer).
- **fastembed** — embeddings multilingues **locaux** par défaut (aucune clé, rien ne sort de l'instance). Bascule sur OpenAI avec `EMBEDDING_PROVIDER=openai`.
- **Claude** ou **OpenAI** pour la génération (`LLM_PROVIDER`). Auto : Claude si seule la clé Anthropic est présente.
- **FastAPI** — serveur : API `/api/*`, widget de chat embarquable, espace d'administration.

Architecture RAG classique (chargement → découpage → embeddings → récupération → génération sourcée), enrichie de deux correctifs : extraction **géométrique des tableaux** (`core/ingest_ameliore.py`) et **récupération hybride** mot-clé + vectoriel (`core/recherche_hybride.py`).

Aucune base de données : le journal des questions est un simple fichier **JSONL en ajout seul**.

## Démarrage (5 minutes)

```bash
# 1. Environnement
python -m venv venv && source venv/bin/activate      # Windows : venv\Scripts\activate
pip install -r requirements.txt

# 2. Clé API (une seule suffit pour démarrer)
cp .env.example .env       # puis éditez .env et collez votre ANTHROPIC_API_KEY
                           # le .env est chargé automatiquement, rien d'autre à faire

# 3. Indexer les documents (DATA_DIR=data-immobilier pour la démo Horizon)
python ingest.py

# 4. Lancer le serveur web
python -m uvicorn server:app --reload
```

- `http://localhost:8000` — site de démonstration avec l'assistant en bulle, intégré ou plein écran (protégé par `DEMO_PASSWORD` s'il est défini).
- `http://localhost:8000/gestion.html` — espace d'administration : documents et statistiques d'usage (`ADMIN_PASSWORD`).

## Tester sans clé API

```bash
pip install -r requirements-dev.txt
python -m pytest
```

**Aucun appel réseau, aucune clé, quelques secondes.** La suite injecte un embedding déterministe et un double du cœur RAG : elle ne consomme aucun crédit d'API.

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
| `ANTHROPIC_MODEL` (ou `CLAUDE_MODEL`) | `claude-haiku-4-5` | Modèle Claude utilisé — celui de l'offre |
| `CHUNK_OVERLAP` | `150` | Recouvrement entre chunks (caractères) |
| `CLIENT_NAME` | `l'entreprise` | Nom du client dans l'invite système |
| `ASSISTANT_NAME` / `ASSISTANT_CONTACT` | `Assistant documentaire` / `le service concerné` | Nom de l'assistant, service vers lequel il renvoie en cas de refus |
| `DATA_DIR` | `data` | Dossier des documents (sur Railway : `/data/documents`, volume persistant) |
| `CHROMA_DIR` | `chroma_db` | Dossier de l'index (sur Railway : `/data/chroma_db`) |
| `COLLECTION_NAME` | `documents_client` | Nom de la collection Chroma |
| `EMBED_BATCH` / `ADD_BATCH` | `8` / `16` | Tailles de lots à l'ingestion (baisser si mémoire limitée) |
| `MAX_UPLOAD_MB` | `20` | Taille maximale d'un document téléversé |
| `DEMO_PASSWORD` | — | Mot de passe du chat (vide = pas d'authentification, usage local) |
| `ADMIN_PASSWORD` | — | Mot de passe de l'administration. **Obligatoire dès que `DEMO_PASSWORD` est défini** : sans lui, l'administration est fermée (aucun repli sur le mot de passe du chat) |
| `ALLOWED_ORIGINS` | `*` | Domaines autorisés à appeler l'API (CORS). En production : le domaine du client, jamais `*` |
| `RATE_LIMIT` | `30/minute` | Limite de débit par IP sur `/api/chat` (IP lue dans `X-Forwarded-For` derrière Railway) |
| `LOG_QUESTIONS` | `0` | Journal des questions (opt-in strict) |
| `LOG_DIR` | `logs` | Dossier du fichier `questions.jsonl` (sur Railway : `/data/logs`) |

## Interfaces

Toutes les pages partagent **un seul système de design**, « Encre & Signal » :

| Fichier | Rôle |
|---|---|
| `web/da.css` | Jetons (encre, papier, signal, typographie, courbes), primitives d'animation, composants communs (boutons, filets, pastilles, médias). |
| `web/motion.js` | Moteur d'animation maison, sans dépendance obligatoire : apparitions à l'entrée dans l'écran, titres découpés mot à mot, parallaxe, compteurs, micro-interactions, en-tête réactif. |
| `web/lenis.min.js` | Défilement inertiel (Lenis, MIT), servi en local — le site fonctionne à l'identique s'il est absent. |
| `web/img/` | Photographies servies en local (les polices, elles, viennent de Google Fonts). |

Le site commercial vit dans un **dépôt séparé** (`../site-vitrine/`, déployé sur assistant-documentaire.com via Cloudflare Pages) : `da.css`, `motion.js` et `lenis.min.js` y sont **copiés à l'identique**. Toute modification doit être répercutée dans les deux dépôts.

Deux exceptions assumées à la règle « aucun conteneur » : l'onglet **Statistiques** de l'administration pose ses blocs sur des cartes translucides (sans quoi on ne distingue plus un groupe de chiffres du suivant), et les **réponses du chatbot** sont dans des bulles blanches (sans quoi on ne voit plus où commence un tour de parole). Partout ailleurs, le contenu reste posé à nu sur le fond.

L'explorateur de questions affiche **15 questions par page** ; le serveur en renvoie au plus 500 (borne de `journal.rechercher`), la pagination est faite côté client.

Le widget (`web/widget.js`) embarque sa propre feuille de style, alignée sur les mêmes valeurs mais avec des jetons préfixés `--da-` : il ne peut ni entrer en collision avec le CSS du site hôte, ni en hériter.

Deux axes de variation, et deux seulement :

| Axe | Attribut sur `<html>` | Qui l'utilise |
|---|---|---|
| **Thème** | `data-theme="clair"` (papier) · absent = sombre (encre) | Clair : vitrine Boréale, administration, widget. Sombre : site de l'offre. |
| **Signal** | `data-skin="boreale"` (cobalt & ambre) · absent = émeraude | Cobalt : vitrine Boréale. Émeraude : le produit (assistant, administration, offre). |

Le thème clair ne redéfinit que des **valeurs de jetons**, jamais des règles : toute la mise en page écrite pour le sombre fonctionne telle quelle. Les couleurs en dur sont proscrites dans les pages — on ne manipule que des rôles (`--ink-*` pour les surfaces, `--on-ink-*` pour le texte, `--tint*` pour les surfaces surélevées, `--sh-*` pour les ombres, `--on-media` pour le texte posé sur une photo).

Le contenu reste lisible sans JavaScript : les états masqués sont conditionnés à une classe posée par `motion.js`, et un filet de sécurité révèle tout au bout de 3 secondes. `prefers-reduced-motion` neutralise l'ensemble des animations.

## Limites (à dire au client, c'est une démo)

- Pas de gestion multi-utilisateurs : un mot de passe partagé pour le chat, un pour l'administration.
- Documents scannés non gérés (pas d'OCR) — l'assistant le dit explicitement au téléversement.
- Pas de mise à jour incrémentale par `ingest.py` : il réindexe tout le corpus. (Le téléversement depuis `gestion.html`, lui, est bien incrémental.)
- Formats : `.pdf`, `.docx`, `.md`, `.txt`. Ni `.doc` ancien format, ni Excel, ni boîtes mail, ni SharePoint/Drive — à dire avant le devis.

Ces limites correspondent exactement au **hors-scope** de l'offre de lancement. Les lever se fait sur devis séparé.
