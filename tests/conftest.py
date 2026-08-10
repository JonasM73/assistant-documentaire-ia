"""
conftest.py — configuration commune à toute la suite de tests.

Deux rôles :

1. Rendre les modules du projet importables (racine du projet + core/) quel que
   soit le dossier depuis lequel pytest est lancé. Sans cela, `import server`
   échoue dès qu'on lance `pytest tests/`.

2. Fournir un embedding déterministe et hors-ligne (`embedding_factice`) partagé
   par tous les tests : aucun appel réseau, aucune clé API, aucun modèle à
   télécharger. Les tests ne doivent JAMAIS toucher l'index réel (chroma_db/)
   ni le journal réel (logs/) — chaque test qui indexe reçoit ses propres
   dossiers temporaires.
"""

import hashlib
import os
import re
import sys

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _d in (RACINE, os.path.join(RACINE, "core")):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from chromadb.utils import embedding_functions  # noqa: E402


class EmbeddingFactice(embedding_functions.EmbeddingFunction):
    """Embedding déterministe (sac de mots hashé), sans réseau.

    Suffisant pour vérifier que l'orchestration récupère bien le bon extrait :
    deux textes qui partagent des mots pointent dans la même direction.
    """

    DIM = 256

    def __call__(self, input):
        vecs = []
        for texte in input:
            vec = [0.0] * self.DIM
            for tok in re.findall(r"\w+", str(texte).lower()):
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                vec[h % self.DIM] += 1.0
            norme = sum(v * v for v in vec) ** 0.5 or 1.0
            vecs.append([v / norme for v in vec])
        return vecs

    def name(self):
        return "factice-test"


@pytest.fixture
def embedding_factice():
    return EmbeddingFactice()


@pytest.fixture
def dossier_chroma(tmp_path):
    """Dossier d'index isolé : aucun test ne doit écrire dans chroma_db/."""
    d = tmp_path / "chroma"
    d.mkdir()
    return str(d)


@pytest.fixture
def dossier_documents(tmp_path):
    """Petit corpus temporaire, indépendant du contenu réel de data/."""
    d = tmp_path / "docs"
    d.mkdir()
    (d / "Manuel-employe.md").write_text(
        "# Manuel de l'employé\n\n"
        "Les vacances augmentent avec l'ancienneté : trois semaines dès "
        "l'embauche, quatre semaines après cinq ans d'ancienneté.\n\n"
        "Le télétravail est autorisé deux jours par semaine.\n",
        encoding="utf-8")
    (d / "Catalogue.txt").write_text(
        "Chauffe-eau instantané au gaz BOR-CEI : 1 340 $ net.\n\n"
        "Thermopompe murale BOR-TP24 : 1 890 $ net, garantie compresseur dix ans.\n",
        encoding="utf-8")
    return str(d)
