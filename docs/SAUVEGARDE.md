# Sauvegarde, restauration et surveillance

## Ce qui doit être sauvegardé

Sur le volume `/data` de l'instance :

| Chemin | Contenu | Reconstructible ? |
|---|---|---|
| `/data/documents` | documents déposés par le client | **non** — c'est la donnée première |
| `/data/chroma_db` | index vectoriel | oui, par `python ingest.py` sur les documents |
| `/data/logs/questions.jsonl` | journal des questions (option) | non, mais non critique |

## Règle

1. Le client garde **ses documents sources** dans son propre espace : l'instance n'est jamais
   le seul exemplaire.
2. Railway sauvegarde le volume selon son offre (vérifier l'option de *snapshots* du plan
   retenu et l'activer avec le client lors du déploiement).
3. Si la maintenance est souscrite : export mensuel de `/data/documents` et du journal vers
   l'espace du client (par `railway ssh`/`railway run` + archive `.tar.gz`), **jamais** sur le
   poste de Jonas au-delà de l'opération.

## Restauration

1. Recréer le service depuis le dépôt (`DEPLOIEMENT-RAILWAY.md`), même région, volume `/data`.
2. Redéposer les documents (page de gestion, ou copie dans `/data/documents`).
3. Reconstruire l'index : depuis le service, `python ingest.py` avec `DATA_DIR=/data/documents`
   et `CHROMA_DIR=/data/chroma_db` (ou indexation locale puis copie de l'index).
4. Vérifier `/api/health`, puis rejouer 5 questions du jeu de recette.

## Surveillance de la disponibilité (maintenance)

- Sonde HTTP sur `https://<instance>/api/health` toutes les 5 minutes, alerte par e-mail à
  jonas@jonasmionnet.com (service d'uptime gratuit : UptimeRobot, Better Stack…). À mettre en
  place **avant** de facturer le premier mois de maintenance.
- Alerte de dépense : plafond mensuel dans la Console Anthropic (fixé avec le client) et alerte
  d'usage Railway.
- Engagement du devis : incident imputable à Jonas non résolu sous 48 h ouvrées → le mois n'est
  pas facturé.
