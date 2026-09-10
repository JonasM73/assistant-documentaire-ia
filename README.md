# Assistant documentaire — répondre à partir de documents, sans inventer

Projet personnel. Un assistant qui répond aux questions posées sur un corpus de
documents d'entreprise (PDF, Word, texte, **tableaux compris**), en citant le
document dont la réponse est tirée, et qui **refuse de répondre quand
l'information n'y figure pas**.

L'intérêt du projet n'est pas le chatbot — c'est le **protocole de mesure** qui
va avec, et ce qu'il a permis de trouver.

---

## Le problème

Un système de question-réponse sur documents est facile à faire marcher sur une
démonstration choisie, et très difficile à faire marcher honnêtement. Deux
défauts sont invisibles tant qu'on ne les cherche pas : il répond quand il ne
sait pas, et il cite une source qui ne dit pas ce qu'il affirme.

J'ai donc construit le système **et** sa recette : un jeu de 28 questions de
contrôle sur un corpus de démonstration, avec les réponses attendues connues
d'avance, dont cinq questions dont la réponse **n'existe pas** dans les
documents — pour vérifier qu'il refuse au lieu de combler le vide.

## Ce que la mesure a trouvé

C'est la partie intéressante. Les trois défauts ci-dessous étaient invisibles à
l'usage courant : le système avait l'air de fonctionner.

**Les tableaux étaient lus de travers.** Les PDF utilisés n'ont aucun trait de
séparation ; l'extracteur renvoyait alors une seule colonne par ligne, et les
en-têtes perdaient tout lien avec les valeurs. Sur un barème à trois colonnes,
l'assistant annonçait 5,0 % là où le document dit 4,2 % — la valeur de la ligne
voisine. Correctif : reconstruction des colonnes à partir des **abscisses des
mots**, avec recollage des lignes dont le libellé déborde sur la ligne suivante.

**Chaque tableau était indexé deux fois.** Une fois proprement, en fiches
« en-tête : valeur », et une fois en vrac dans le texte de la page. Les deux
copies se contredisaient. Tant que la recherche ne remontait que la bonne, tout
allait bien — élargir le nombre d'extraits transmis au modèle faisait
apparaître la mauvaise et **dégradait** le résultat. C'est ce qui a mis la
double indexation en évidence : un réglage censé améliorer les choses les
empirait. Correctif : les zones de tableau sont retirées du texte de page.

**La recherche exacte ignorait les noms propres.** Elle ne se déclenchait que
sur des identifiants (`BX-1003`, `S001`). Résultat : à la question « quels
honoraires pour l'agence de Blois ? », le tableau qui associe Blois à sa zone
tarifaire ne remontait jamais — il ne contient que des villes et des codes, il
n'a presque aucune proximité sémantique avec le mot « honoraires ». Correctif :
reconnaissance des noms propres, avec un garde-fou écartant les termes présents
dans plus d'un quart du corpus, et un plafond d'extraits forcés.

## Résultat

Sur 28 questions de contrôle, dont 5 sans réponse possible :

| Réglage | Réponses exactes | Refus corrects | Réponses inventées |
|---|---|---|---|
| 12 extraits | 17 / 23 | 5 / 5 | **0** |
| 20 extraits | 18 / 23 | 5 / 5 | **0** |

Zéro réponse inventée aux deux réglages : après le correctif de double
indexation, le comportement ne dépend plus du nombre d'extraits transmis.

Ce qui reste imparfait, c'est le **rappel** : sur quelques questions, le bon
extrait existe dans l'index mais ne remonte pas, et l'assistant refuse alors
honnêtement. Les questions qui échouent changent d'un réglage à l'autre — la
signature d'un problème de classement, pas de véracité.

*Ces chiffres valent pour ce corpus et ces 28 questions. Ils ne prédisent rien
sur un autre jeu de documents.*

## Comment c'est construit

Serveur **FastAPI**. Index vectoriel **ChromaDB**. Embeddings **fastembed**
calculés localement (`paraphrase-multilingual-MiniLM-L12-v2`), donc sans appel
réseau ni clé pour la partie recherche. Génération par **Claude Haiku 4.5**.
Interface de chat en JavaScript sans dépendance, intégrable en bulle flottante,
en ligne dans une page ou en plein écran.

Deux points de conception qui font l'essentiel du comportement :

**Les sources ne sont pas écrites par le modèle.** Elles proviennent des
métadonnées des extraits réellement récupérés. Une source ne peut donc pas être
hallucinée — c'est une propriété de la construction, pas une consigne.

**La phrase de refus est unique**, quelle que soit la raison du refus :
information absente, question hors sujet, tentative de détournement. Le
comportement devient prévisible pour l'utilisateur, et vérifiable
automatiquement par la recette. Une règle interdit par ailleurs de relier deux
documents si un maillon manque, ou d'énoncer une justification (« parce
que… ») qui ne figure pas telle quelle dans un extrait.

Le corpus de démonstration décrit un réseau d'agences immobilières **fictif**,
écrit pour ce projet : aucune entreprise de ce nom n'existe.

## Tests

Une centaine de tests hors ligne, exécutables sans clé d'API : ils injectent un
embedding déterministe et un double du cœur de recherche. Ils couvrent
l'ingestion, le journal, les protections du serveur et le pipeline complet.

## Statut et réutilisation

**Projet personnel, présenté ici à titre de démonstration technique.** Il n'est
ni maintenu, ni supporté, ni destiné à être déployé tel quel. Aucune clé d'API
ni aucun secret n'a jamais été versionné dans ce dépôt.

**Tous droits réservés.** Ce dépôt ne comporte aucune licence : le code est
consultable, il n'est pas réutilisable — ni en l'état, ni dérivé, ni à des fins
commerciales. Pour toute question : contact via mon profil GitHub.
