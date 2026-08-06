"""
genere_journal_demo.py — Remplit le journal avec des données réalistes pour la
démo de 30 s et la capture d'écran de la section Statistiques (gestion.html).

Usage :
    python tests/genere_journal_demo.py            # écrit logs/questions.jsonl
    LOG_DIR=data/logs python tests/genere_journal_demo.py

Génère ~5 semaines d'activité type PME (questions Boréale), avec plusieurs
FORMULATIONS différentes d'une même idée (pour montrer le regroupement par
sens), des documents cités et ~12 % de refus. NE PAS utiliser chez un client :
c'est un outil de démonstration.
"""

import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core"))
import journal  # noqa: E402

random.seed(42)

# Chaque sujet = plusieurs formulations de la MÊME idée (regroupées par sens
# dans les stats), les sources citées, et un poids de fréquence.
SUJETS = [
    (["Quel est le prix du chauffe-eau instantané au gaz BOR-CEI ?",
      "Combien coûte le BOR-CEI ?",
      "C'est quoi le tarif du chauffe-eau BOR-CEI ?"],
     ["Catalogue-produits.pdf"], 7),
    (["Quelle est la durée de garantie des thermopompes ?",
      "Les thermopompes sont garanties combien de temps ?",
      "Garantie thermopompe : combien d'années ?"],
     ["Politique-garantie-retours.pdf"], 6),
    (["Quel est le délai de livraison standard ?",
      "En combien de jours êtes-vous livrés ?"],
     ["FAQ-service-client.pdf"], 5),
    (["Comment faire une demande de retour ?",
      "Quelle est la procédure pour retourner un produit ?"],
     ["Politique-garantie-retours.pdf", "FAQ-service-client.pdf"], 4),
    (["Quels sont les paliers d'ancienneté pour les vacances ?",
      "Après combien d'années a-t-on 4 semaines de vacances ?"],
     ["Manuel-employe.pdf"], 4),
    (["Le BOR-TH8 est-il compatible avec un plancher chauffant ?"],
     ["Catalogue-produits.pdf"], 3),
    (["Quelle est la procédure d'ouverture de compte client ?",
      "Comment ouvrir un compte pour un nouveau client ?"],
     ["Procedures-internes.pdf"], 3),
    (["Y a-t-il un rabais pour les commandes de plus de 10 unités ?",
      "Vous faites un prix de volume ?"],
     ["Catalogue-produits.pdf"], 2),
    (["Quelles sont les heures d'ouverture du service client ?"],
     ["FAQ-service-client.pdf"], 2),
    (["Comment soumettre une réclamation de garantie ?"],
     ["Politique-garantie-retours.pdf"], 2),
    (["Quel est le débit du BOR-CEI en litres par minute ?"],
     ["Catalogue-produits.pdf"], 1),
    (["Quelle est la politique de télétravail ?"],
     ["Manuel-employe.pdf"], 1),
]
# Refus : l'info n'est pas dans les documents (ou hors périmètre).
REFUSES = [
    (["Avez-vous des thermopompes de marque Daikin ?",
      "Est-ce que vous vendez du Daikin ?"], 3),
    (["Quel est le chiffre d'affaires de l'entreprise ?"], 2),
    (["Peux-tu me faire un rabais de 20 % ?"], 2),
    (["Quelle est la météo prévue demain ?"], 1),
    (["Qui est le meilleur employé du mois ?"], 1),
]

entrees = []
maintenant = datetime.now(timezone.utc).astimezone()
for jours_avant in range(34, -1, -1):
    jour = maintenant - timedelta(days=jours_avant)
    est_weekend = jour.weekday() >= 5
    # trafic en légère croissance sur la période (plus vendeur, et réaliste)
    base = 3 + (34 - jours_avant) // 9
    n = random.randint(0, 2) if est_weekend else random.randint(base, base + 8)
    for _ in range(n):
        ts = jour.replace(hour=random.randint(8, 17), minute=random.randint(0, 59),
                          second=random.randint(0, 59))
        duree = round(random.uniform(2.4, 6.2), 2)
        if random.random() < 0.12:
            formes, _p = random.choices(REFUSES, weights=[r[1] for r in REFUSES])[0]
            entrees.append({"date": ts.isoformat(timespec="seconds"),
                            "question": random.choice(formes),
                            "sources": [], "refus": True, "duree": duree})
        else:
            formes, srcs, _p = random.choices(SUJETS, weights=[s[2] for s in SUJETS])[0]
            entrees.append({"date": ts.isoformat(timespec="seconds"),
                            "question": random.choice(formes),
                            "sources": srcs, "refus": False, "duree": duree})

entrees.sort(key=lambda e: e["date"])
p = journal.chemin()
os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
with open(p, "w", encoding="utf-8") as f:
    for e in entrees:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")

refus = sum(1 for e in entrees if e["refus"])
print(f"{len(entrees)} questions écrites dans {p} ({refus} refus, "
      f"{refus/len(entrees):.0%}). Lancez le serveur puis ouvrez gestion.html.")
