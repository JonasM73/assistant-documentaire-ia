# Déployer le site vitrine (ce dossier) sur Cloudflare Pages

Le site est statique : ce dossier `marketing/` se sert tel quel, sans build.
Il est déployé **depuis ce dépôt GitHub**, pas depuis un dépôt séparé.

## Mise en place (une fois, ~10 min)

1. Cloudflare → **Workers & Pages → Create → Pages → Connect to Git**.
2. Choisir le dépôt `JonasM73/assistant-documentaire-demo`, branche `main`.
3. Réglages de build :
   - Framework preset : **None**
   - Build command : *(vide)*
   - Build output directory : **`/`** (ou `.`)
   - **Root directory (advanced) : `marketing`**  ← le réglage qui compte
4. Save and Deploy → le site sort sur `<nom-du-projet>.pages.dev`. Vérifier
   `index.html`, `simulation.html`, `mentions-legales.html`, `partage.png`.
5. **Custom domains** → ajouter le domaine acheté (racine + `www`). Si le domaine
   est chez Cloudflare, les enregistrements DNS se créent seuls.
6. Dans `index.html` et `simulation.html`, remplacer `https://assistant-documentaire.com/`
   (og:url, og:image, twitter:image, canonical, JSON-LD) par le nouveau domaine,
   commiter, pousser : Pages redéploie tout seul.

## Ensuite, à chaque changement

`git add marketing/ && git commit -m "site : ..." && git push` — c'est tout.
Chaque push sur `main` redéploie le site ; les autres dossiers du dépôt
(app Python, data/, tests/) ne sont ni lus ni publiés par Pages.

## Ce qui reste hors Pages

- Le formulaire de devis : renseigner la clé Web3Forms dans `formulaire.js`
  (voir l'en-tête du fichier). Sans clé, le formulaire ouvre le client mail.
- L'adresse `jonas@jonasmionnet.com` reste valable (elle vit sur le domaine
  du portfolio, pas sur celui du site) — à changer uniquement si tu veux une
  adresse sur le nouveau domaine (Cloudflare Email Routing, gratuit).
- Le fichier `_headers` fixe quelques en-têtes de sécurité et de cache ;
  Pages le lit automatiquement.
