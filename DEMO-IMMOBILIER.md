# Démo verticale — immobilier (« Horizon Immobilier »)

Cas de démonstration public du projet (l'ancien jeu Boréale, québécois, n'est plus montré). Cible : les
**réseaux d'agences immobilières** (voir `MAILS/MAIL 2 immobilier réseaux.txt`).

Horizon Immobilier est un **réseau fictif** : 6 agences en Centre-Val de Loire,
6 documents, 15 pages. Le cadre réglementaire cité (diagnostics, DPE, mandats,
honoraires de location) est en revanche **réel et vérifié au 20 août 2026** —
c'est ce qui rend la démo crédible devant un professionnel du secteur.

## Les documents

| Fichier | Contenu | Ce qu'il sert à démontrer |
|---|---|---|
| `01_bareme-honoraires-2026.pdf` | Barème transaction / location / gestion, 6 tableaux | Lecture de tableaux multi-colonnes |
| `02_guide-des-mandats.pdf` | Mandats simple / semi-exclusif / exclusif, rétractation | Distinctions fines, deux délais à ne pas confondre |
| `03_diagnostics-obligatoires.pdf` | Validités, audit énergétique, interdictions de location | Exactitude contre les idées reçues |
| `04_procedure-de-la-prise-de-mandat-a-l-acte.pdf` | Procédure interne en 6 étapes, LCB-FT | Questions de process |
| `05_faq-clients.pdf` | FAQ vendeurs / acquéreurs / locataires | Usage grand public du widget |
| `06_manuel-interne-des-conseillers.pdf` | Rétrocession, primes, horaires, déontologie | Usage interne |

## Lancer la démo

```bash
# Windows
set DATA_DIR=data-immobilier
python ingest.py
python -m uvicorn server:app --reload
```

L'index Chroma étant partagé, relancer `ingest.py` après tout changement de `DATA_DIR`.
Pour garder deux index en parallèle, pointer aussi `CHROMA_DIR` sur un dossier dédié
(ex. `chroma_db_immo`).

## Questions de contrôle

`tests/questions_controle_immobilier.json` — **28 questions**, réponses vérifiées à
la main dans les PDF (ne jamais régénérer les `attendu` en interrogeant le modèle) :

- 12 factuelles simples
- 4 de lecture de tableau, dont une qui exige de croiser deux tableaux
- 3 croisées entre documents
- 4 pièges (10 jours contre 14 jours, classe F contre classe G, validité de l'amiante)
- **5 sans réponse** : le refus attendu, dont « tarifs de syndic » — activité que le
  réseau n'exerce pas et qui est explicitement exclue dans deux documents

```bash
set DATA_DIR=data-immobilier
python ingest.py
python tests/evaluer.py --modeles claude-haiku-4-5 --client "Horizon Immobilier" --rapport tests/recette-horizon.md
```

> Le jeu Horizon est celui lu par défaut par `evaluer.py` ; `--seuil 0.9` porte le
> seuil d'exactitude convenu sur le procès-verbal.

Le chiffre à retenir de ce test, c'est **zéro hallucination** : une seule est un
défaut bloquant, pas une statistique.

## Vidéo

Script minuté dans `script-video-demo-immobilier.docx` (racine du dossier projet) —
80 secondes, quatre questions, une seule prise. Ordre des questions choisi pour lever
quatre objections successives : capacité, vérifiabilité, exactitude, honnêteté.
