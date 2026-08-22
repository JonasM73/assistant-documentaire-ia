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
- **« Hébergement en Europe »** : à ne réintroduire qu'après vérification de la région du
  service Railway. Les emplacements concernés portent un commentaire HTML dans
  `marketing/index.html`.
- **« N'invente jamais »**, « zéro invention » comme garantie absolue : la formulation retenue
  est « il refuse quand l'information ne figure pas dans les documents », adossée à la recette.

## Structure

| Chemin | Rôle |
|---|---|
| `marketing/index.html` | Page vitrine déployée sur jonasmionnet.com (Cloudflare Worker). Autonome : un seul fichier, une police, aucune animation |
| `marketing/mentions-legales.html` | Mentions légales, même charte, autonome |
| `web/` | Vitrine fictive Boréale Équipement servie par l'instance FastAPI — **ce n'est pas le site commercial**, ne pas y propager les textes marketing |
| `data/` | Documents de la démo Boréale (⚠️ entreprise québécoise, montants en dollars) |
| `data-immobilier/` | Documents de la démo Horizon Immobilier — **c'est la vitrine publique** |
| `tests/evaluer.py` | Recette : `--questions` pour choisir le jeu, `--rapport` pour le procès-verbal remis au client |

## Recette d'un client

```
set DATA_DIR=data-immobilier && python ingest.py
python tests/evaluer.py --modeles claude-haiku-4-5 ^
    --questions tests/questions_controle_immobilier.json ^
    --client "Horizon Immobilier" ^
    --rapport tests/recette-horizon.md
```

Le fichier `--rapport` est la pièce remise au client avant règlement du solde.

## Style d'écriture

Français de France, euros uniquement. Ton factuel et sobre : pas de superlatif, pas de jargon
technique côté client (jamais « RAG », « LLM », « embeddings »). Les limites sont annoncées
plutôt que découvertes. Ne jamais inventer de témoignage, de logo client ou de statistique.
