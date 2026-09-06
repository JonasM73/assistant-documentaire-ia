# Instructions de dépôt — assistant documentaire

## Avant toute rédaction commerciale, lire OFFRE_ACTUELLE.md

Le fichier `OFFRE_ACTUELLE.md`, à la racine du dossier parent
(`../OFFRE_ACTUELLE.md` depuis ce dépôt), est **la seule source de vérité** pour :
les prix, le volume inclus, le délai de livraison, le modèle d'hébergement, les critères de
recette, et les formulations autorisées.

Aucun prix, aucun délai, aucune promesse ne doit être écrit dans le site, un devis, un mail ou
une publication sans avoir été vérifié dans ce fichier.

## Documents périmés — ne jamais s'en servir

Tout fichier préfixé `OBSOLETE_` ou rangé dans `_archive/` décrit une version abandonnée de
l'offre. Il ne faut **jamais** en tirer un prix, un montant, un volume ou une formulation, même
s'il semble plus détaillé que la source actuelle. Voir `_archive/README.md`.

Les valeurs périmées à reconnaître immédiatement : 500 €, 800 $ CAD, 15-25 $/mois,
0,005 $ la question, 30 fichiers / 300 pages, 16 questions de contrôle, « France et Québec ».

## Affirmations interdites tant qu'elles ne sont pas mesurées

- Toute **latence chiffrée** (« 4 secondes », « 3,8 s ») : seulement après une mesure
  reproductible, datée et conservée dans `tests/`.
- Tout **taux d'exactitude** (« 14/16 ») : publier la procédure de recette, pas le score.
- **« Hébergement en Europe »** : la région européenne est **choisie et vérifiée avec le
  client** à l'ouverture de son compte Railway (`docs/OUVERTURE-COMPTES.md`) ; c'est ce fait,
  pas une promesse, que le site et l'annexe RGPD affirment.
- **« N'invente jamais »**, « zéro invention » comme garantie absolue : la formulation retenue
  est « il refuse quand l'information ne figure pas dans les documents », adossée à la recette.

## Structure

| Chemin | Rôle |
|---|---|
| `../site-vitrine/` (dépôt Git séparé) | Site commercial déployé sur assistant-documentaire.com via Cloudflare Pages. Plus dans ce dépôt depuis le 02/09/2026 |
| `web/` | Front de démonstration servi par l'instance FastAPI (encore habillé « Boréale », à refaire en français) — **ce n'est pas le site commercial**, ne pas y propager les textes marketing |
| `data/` | Ancien jeu Boréale (⚠️ québécois, dollars) — **plus montré nulle part depuis le 05/09**, à remplacer ou supprimer |
| `data-immobilier/` | Documents de la démo Horizon Immobilier — **c'est la vitrine publique** |
| `docs/` | Procédures client : ouverture des comptes, déploiement Railway, exploitation, sauvegarde |
| `railway.json` | Déploiement Railway : commande de démarrage avec en-têtes de proxy, sonde `/api/health` |
| `tests/evaluer.py` | Recette : jeu Horizon par défaut, `--seuil` pour le seuil du devis, `--rapport` pour le procès-verbal remis au client |

## Recette d'un client

```
set DATA_DIR=data-immobilier && python ingest.py
python tests/evaluer.py --modeles claude-haiku-4-5 ^
    --client "Horizon Immobilier" --seuil 0.9 ^
    --rapport tests/recette-horizon.md
```

Le fichier `--rapport` est la pièce remise au client avant règlement du solde.

## Style d'écriture

Français de France, euros uniquement. Ton factuel et sobre : pas de superlatif, pas de jargon
technique côté client (jamais « RAG », « LLM », « embeddings »). Les limites sont annoncées
plutôt que découvertes. Ne jamais inventer de témoignage, de logo client ou de statistique.
