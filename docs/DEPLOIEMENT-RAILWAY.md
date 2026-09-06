# Déploiement d'une instance client sur Railway

Procédure suivie par Jonas après `OUVERTURE-COMPTES.md`. Durée : 30 à 60 minutes, plus
l'indexation.

## 1. Le service

1. Dans le projet Railway du client : « New » → « GitHub Repo » → dépôt du socle
   (`assistant-documentaire-demo`, branche `main`) — ou « Empty service » + déploiement par
   `railway up` depuis le poste de Jonas si le client ne doit pas être lié au dépôt GitHub.
2. `railway.json` du dépôt fixe la commande de démarrage
   (`uvicorn server:app --proxy-headers --forwarded-allow-ips='*'`), la sonde `/api/health` et
   la politique de redémarrage. Ne pas définir de « Start Command » dans l'interface : elle
   écraserait celle du fichier.
3. Vérifier que la **région** du service est bien celle notée avec le client.
4. Attacher le **volume** créé avec le client, point de montage `/data`.

## 2. Variables d'environnement (service → Variables)

| Variable | Valeur |
|---|---|
| `ANTHROPIC_API_KEY` | clé créée par le client dans sa Console (collée une seule fois) |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5` |
| `DATA_DIR` | `/data/documents` |
| `CHROMA_DIR` | `/data/chroma_db` |
| `LOG_DIR` | `/data/logs` |
| `LOG_QUESTIONS` | `0` — `1` seulement si l'option tableau de bord est souscrite **et** que le client a informé ses utilisateurs |
| `DEMO_PASSWORD` | mot de passe du chat (long, aléatoire, généré devant le client) |
| `ADMIN_PASSWORD` | mot de passe de la page de gestion, **différent** du précédent — obligatoire |
| `ALLOWED_ORIGINS` | `https://www.client.fr,https://client.fr` — **jamais `*`** en production |
| `RATE_LIMIT` | `30/minute` (widget public) ou `120/minute` (usage interne) |
| `CLIENT_NAME` | nom de l'entreprise |
| `ASSISTANT_NAME` / `ASSISTANT_CONTACT` | nom affiché / service vers lequel renvoyer (« le service client au 01… ») |
| `MAX_UPLOAD_MB` | `20` |
| `EMBED_BATCH` / `ADD_BATCH` | `4` / `8` si l'indexation manque de mémoire |

## 3. Domaine

- « Settings » → « Networking » → « Generate domain » (adresse `*.up.railway.app`), ou domaine
  du client (`assistant.client.fr`) via un CNAME chez son registrar.
- Reporter l'URL dans `ALLOWED_ORIGINS` si l'assistant est intégré sur un autre domaine.

## 4. Documents et indexation

1. Déposer les documents du client depuis `https://<instance>/gestion.html` (mot de passe
   `ADMIN_PASSWORD`) : ils sont indexés à chaud, un par un — c'est la voie normale.
2. Pour un premier lot volumineux, préférer une indexation locale puis l'envoi de l'index :
   `set DATA_DIR=<dossier client> && set CHROMA_DIR=chroma_client && python ingest.py`, puis
   copier `chroma_client/` vers `/data/chroma_db` du volume (`railway ssh`/`railway run`
   selon l'outillage du moment). L'indexation à chaud d'un gros lot peut saturer la mémoire
   d'un petit plan.
3. Contrôle : `GET https://<instance>/api/health` doit répondre `status: ok`, `auth: activée`,
   `admin: séparé`.

## 5. Recette et remise

1. Jouer le jeu de questions arrêté avec le client :
   `python tests/evaluer.py --questions <jeu-client>.json --client "<Client>" --seuil <seuil du devis> --rapport recette-<client>.md`
   (l'instance locale doit pointer sur le même index que la production, ou rejouer sur la
   production via l'API).
2. Remettre le procès-verbal (modèle `pv-recette-type.docx` à la racine du dossier commercial)
   et la documentation d'exploitation (`EXPLOITATION.md` complété).
3. À la fin de la mission sans maintenance : quitter le projet Railway du client, supprimer les
   copies de travail sous 30 jours, attestation sur demande.

## 6. Répétition générale (chantier 4)

Avant le premier client : dérouler cette procédure à blanc, chronométrée, sur un projet Railway
de test au plan Hobby, avec les 6 PDF Horizon, et noter le temps réel de chaque étape ici.
