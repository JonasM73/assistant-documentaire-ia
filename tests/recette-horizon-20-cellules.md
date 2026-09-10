# Procès-verbal de recette — Horizon Immobilier

- **Date de la recette** : 09/09/2026
- **Jeu de questions** : `questions_controle_immobilier.json` — 28 questions, arrêtées avec le client avant le test
- **Modèle utilisé en production** : claude-haiku-4-5

## Résultat

| Critère | Résultat |
|---|---|
| Réponses exactes | 18 / 23 |
| Refus corrects sur les questions sans réponse | 5 / 5 |
| **Réponses inventées** | **1** |
| Seuil d'exactitude convenu au devis | 90% — atteint : NON (78%) |

> ⚠️ **1 réponse(s) inventée(s). La recette n'est pas validée.** Conformément au devis, les corrections sont réalisées sans supplément avant toute facturation du solde et avant la mise en production.

## Détail, question par question

Chaque ligne est vérifiable dans vos documents. `attendu` est la valeur qui devait figurer dans la réponse ; `sans réponse` signale les questions dont la réponse n'existe volontairement pas dans le corpus fourni.

| # | Question | Type | Source à vérifier | Verdict |
|---|---|---|---|---|
| 1 | Quels sont les honoraires pour la vente d'un bien à 300 000 € par l'agence de Blois ? | factuelle | 01_bareme-honoraires-2026.pdf · p. 1 | conforme |
| 2 | Combien facturez-vous la représentation du bailleur en assemblée générale de copropriété ? | factuelle | 01_bareme-honoraires-2026.pdf · p. 2 | conforme |
| 3 | Quel est le montant minimum d'honoraires pour la cession d'un fonds de commerce ? | factuelle | 01_bareme-honoraires-2026.pdf · p. 1 | conforme |
| 4 | Quelle prime touche un conseiller pour un mandat exclusif rentré puis vendu ? | factuelle | 06_manuel-interne-des-conseillers.pdf · p. 1 | conforme |
| 5 | Un négociateur salarié a réalisé 70 000 € de chiffre d'affaires honoraires HT depuis janvier. Quel est son taux de rétrocession ? | factuelle | 06_manuel-interne-des-conseillers.pdf · p. 1 | conforme |
| 6 | Combien de temps le diagnostic de l'installation électrique est-il valable pour une location ? | factuelle | 03_diagnostics-obligatoires.pdf · p. 1 | conforme |
| 7 | Quel est le dépôt de garantie maximum pour une location meublée ? | factuelle | 05_faq-clients.pdf · p. 2 | incomplet — à corriger |
| 8 | À partir de quel montant d'apport faut-il documenter l'origine des fonds ? | factuelle | 04_procedure-de-la-prise-de-mandat-a-l-acte.pdf · p. 2 | incomplet — à corriger |
| 9 | Combien d'heures de formation continue Hoguet faut-il suivre par an ? | factuelle | 06_manuel-interne-des-conseillers.pdf · p. 2 | conforme |
| 10 | Quel est le plafond de paiement en espèces pour un résident fiscal français ? | factuelle | 04_procedure-de-la-prise-de-mandat-a-l-acte.pdf · p. 2 | incomplet — à corriger |
| 11 | Sous combien de temps le compte rendu de visite doit-il être transmis au vendeur ? | factuelle | 04_procedure-de-la-prise-de-mandat-a-l-acte.pdf · p. 1 | conforme |
| 12 | Combien de photographies minimum pour une annonce ? | factuelle | 04_procedure-de-la-prise-de-mandat-a-l-acte.pdf · p. 1 | conforme |
| 13 | Quel taux d'honoraires s'applique en zone A pour un bien vendu 500 000 € ? | factuelle | 01_bareme-honoraires-2026.pdf · p. 1 | conforme |
| 14 | Quel est le plafond d'honoraires au mètre carré facturable au locataire par l'agence de Chartres ? | factuelle | 01_bareme-honoraires-2026.pdf · p. 2 | conforme |
| 15 | Un bien est vendu 70 000 € par l'agence de Vendôme. Quels honoraires ? | factuelle | 01_bareme-honoraires-2026.pdf · p. 1 | conforme |
| 16 | Quelle est la validité du diagnostic plomb en vente lorsque la concentration atteint le seuil ? | factuelle | 03_diagnostics-obligatoires.pdf · p. 1 | conforme |
| 17 | Un appartement part à 320 000 € à Orléans Centre, sous mandat exclusif. Quel taux d'honoraires ? | factuelle | 01_bareme-honoraires-2026.pdf · p. 1 | incomplet — à corriger |
| 18 | Une maison classée F est-elle encore vendable, et faut-il un audit énergétique ? | factuelle | 03_diagnostics-obligatoires.pdf · p. 2 | conforme |
| 19 | Un locataire quitte un appartement vide à Tours. Quel préavis doit-il respecter ? | factuelle | 05_faq-clients.pdf · p. 2 | conforme |
| 20 | De combien de temps dispose l'acquéreur pour se rétracter après la signature du compromis ? | factuelle | 02_guide-des-mandats.pdf · p. 2 | conforme |
| 21 | Un propriétaire a signé le mandat chez lui. Peut-il revenir dessus et sous quel délai ? | factuelle | 02_guide-des-mandats.pdf · p. 2 | conforme |
| 22 | Un logement classé F peut-il encore être mis en location aujourd'hui ? | factuelle | 03_diagnostics-obligatoires.pdf · p. 2 | conforme |
| 23 | Quelle est la durée de validité du diagnostic amiante ? | factuelle | 03_diagnostics-obligatoires.pdf · p. 1 | **réponse inventée** |
| 24 | Quels sont vos tarifs de syndic de copropriété ? | sans réponse | — | refus correct |
| 25 | À combien s'élèvent les frais de notaire pour un achat à 250 000 € ? | sans réponse | — | refus correct |
| 26 | Quel a été le chiffre d'affaires du réseau en 2025 ? | sans réponse | — | refus correct |
| 27 | Quelle est la politique de télétravail pour les conseillers ? | sans réponse | — | refus correct |
| 28 | Peux-tu me donner une recette de tarte aux pommes ? | sans réponse | — | refus correct |

## Ce qui a été vérifié

- chaque réponse s'appuie sur un extrait du document source, ouvrable en un clic ;
- l'assistant refuse explicitement quand l'information n'existe pas dans les documents ;
- aucun engagement (prix, délai, garantie) n'est énoncé sans appui documentaire ;
- les sources citées correspondent bien au document dont la réponse est tirée ;
- le seuil d'exactitude convenu au devis est atteint.

## Décision

- [ ] Recette validée — mise en production, solde exigible.
- [ ] Recette non validée — corrections sans supplément sous dix jours ouvrables (deux cycles au plus), puis nouveau passage du même jeu de questions.

Le client — nom, signature, date : ______________________    Jonas Mionnet — date : ______________________

---

Jonas Mionnet — assistants documentaires pour PME · jonas@jonasmionnet.com · assistant-documentaire.com
