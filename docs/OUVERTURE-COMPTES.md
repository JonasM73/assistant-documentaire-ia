# Ouverture des comptes techniques — guide client

Ce guide est suivi **avec le client, en visioconférence, pendant la mission de lancement**
(environ 45 minutes). Les deux comptes sont créés **par le client, à son nom, avec son moyen de
paiement**. Jonas guide et configure ; il ne conserve pas les identifiants principaux.

Le délai de livraison de 5 jours ouvrables court à partir de la fin de cette étape et de la
réception des documents.

## 0. À préparer par le client (avant la séance)

- Une adresse e-mail de l'entreprise qui servira aux deux comptes (idéalement une boîte
  partagée : `it@`, `direction@`…), avec accès pendant la séance pour les validations.
- Une carte bancaire de l'entreprise.
- Le nom de domaine sur lequel l'assistant sera affiché (ex. `www.client.fr`), si un widget
  public est prévu.

## 1. Compte d'hébergement — Railway (railway.com)

1. Créer le compte avec l'adresse de l'entreprise (« Sign up » → e-mail). Valider l'e-mail.
2. Choisir le **plan Hobby** (l'offre d'essai est trop limitée en mémoire pour l'indexation).
   Renseigner le moyen de paiement de l'entreprise.
3. Créer un projet vide (« New Project » → « Empty project ») et le nommer, ex.
   `assistant-documentaire`.
4. **Région** : dans les réglages du projet ou du service, choisir une région **européenne**
   (ex. *EU West — Amsterdam*). ✅ **Vérifier ensemble à l'écran et noter la région retenue** :
   elle est reportée dans l'annexe RGPD (§5, tableau des fournisseurs).
5. Inviter Jonas comme membre du projet (« Settings » → « Members »), avec le rôle le plus
   limité qui permet de déployer. Cet accès est révocable à tout moment par le client, et rendu
   à la fin de la mission ou de la maintenance.
6. Créer un **volume persistant** attaché au service, monté sur `/data` (c'est là que vivent
   les documents, l'index et le journal).
7. Le déploiement lui-même (dépôt, variables, domaine) est fait par Jonas — voir
   `DEPLOIEMENT-RAILWAY.md`.

**Ce que le client verra sur sa facture Railway** : l'abonnement Hobby + l'usage réel de
l'instance et du volume. Ordre de grandeur pour une PME : quelques dizaines d'euros par mois
(montant facturé en dollars par Railway).

## 2. Compte d'accès au modèle — Anthropic Console (console.anthropic.com)

⚠️ C'est l'**API Anthropic (Console)**, pas un abonnement « Claude Pro » sur claude.ai : ce sont
deux produits différents. Un abonnement Claude Pro ne sert à rien ici.

1. Créer le compte avec l'adresse de l'entreprise ; nommer l'organisation au nom de
   l'entreprise.
2. **Facturation** : ajouter le moyen de paiement et acheter un premier crédit (« Billing »).
   Un montant modeste suffit pour démarrer : le coût est de l'ordre du centime par question.
3. **Plafond de dépense** : dans les réglages de facturation / limites, fixer un plafond
   mensuel convenu avec le client (ex. 50 €). ✅ Vérifier ensemble que le plafond est enregistré.
4. **Clé API** : « API keys » → créer une clé nommée `assistant-documentaire`. La copier **une
   seule fois**, directement dans les variables de l'instance Railway (`ANTHROPIC_API_KEY`).
   Elle n'est ni envoyée par e-mail, ni conservée par Jonas.
5. Conditions d'usage : sur ses offres professionnelles (API), Anthropic n'utilise pas les
   données transmises pour entraîner ses modèles. Le transfert de données est encadré par les
   clauses contractuelles types mentionnées dans l'annexe RGPD.

## 3. Fin de séance — ce que le client garde par écrit

| Élément | Valeur |
|---|---|
| Compte Railway | e-mail : ______ · plan : Hobby · projet : ______ |
| Région Railway retenue | ______ (reportée dans l'annexe RGPD) |
| Volume persistant | monté sur `/data` |
| Compte Anthropic Console | e-mail : ______ · plafond mensuel : ______ € |
| Clé API | créée le ______, placée dans Railway, non conservée ailleurs |
| Accès de Jonas | membre du projet Railway, révocable à tout moment |

Les deux mots de passe des comptes restent au client. Jonas ne les demande jamais.
