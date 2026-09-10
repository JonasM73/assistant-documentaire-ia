"""
test_protections.py — Protections et robustesse de server.py.

Aucun appel réel : le cœur RAG est remplacé par un double, et le journal est
redirigé vers un dossier temporaire. Les tests vérifient l'authentification,
le CORS, la limite de débit, et le fait qu'AUCUNE panne interne ne remonte à
l'utilisateur sous forme de trace technique.

Lancement :  python -m pytest tests/test_protections.py -q
"""

import pytest

import rag_core  # noqa: F401  (server et le client de test viennent de conftest)
import server

CHAT = {"X-API-Password": "secret123"}
ADMIN = {"X-API-Password": "admin456"}


# --------------------------------------------------------------------------- #
# 1. Authentification
# --------------------------------------------------------------------------- #

def test_chat_sans_mot_de_passe(client):
    assert client.post("/api/chat", json={"question": "test"}).status_code == 401


def test_chat_mauvais_mot_de_passe(client):
    r = client.post("/api/chat", json={"question": "test"},
                    headers={"X-API-Password": "faux"})
    assert r.status_code == 401


def test_verify(client):
    assert client.get("/api/verify", headers=CHAT).status_code == 200
    assert client.get("/api/verify").status_code == 401


def test_admin_refuse_le_mot_de_passe_du_chat(client):
    """Le mot de passe admin est bien distinct de celui du chat."""
    assert client.get("/api/admin/verify", headers=CHAT).status_code == 401
    assert client.get("/api/admin/verify", headers=ADMIN).status_code == 200


def test_health_est_public(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_health_ne_publie_pas_la_configuration(client):
    """La sonde reste ouverte (l'hébergeur l'appelle sans mot de passe), mais
    elle ne dresse plus la carte du service pour un visiteur quelconque."""
    assert client.get("/api/health").json() == {"status": "ok"}
    detail = client.get("/api/health", headers=ADMIN).json()
    assert detail["rate_limit"] and detail["llm"] and detail["origines"]


def test_documentation_interactive_fermee(client):
    """/docs listait publiquement toutes les routes d'administration."""
    for chemin in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(chemin).status_code == 404, chemin


def test_entetes_de_securite(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["x-robots-tag"].startswith("noindex")
    assert r.headers["cache-control"] == "no-store"


def test_force_brute_admin_verrouillee(client):
    """Sans verrou, le mot de passe qui commande les documents du client se
    trouve par essais successifs : /api/admin/* n'en refusait aucun."""
    codes = [client.get("/api/admin/verify",
                        headers={"X-API-Password": f"essai{i}"}).status_code
             for i in range(7)]
    assert codes[:server.ECHECS_MAX] == [401] * server.ECHECS_MAX
    assert set(codes[server.ECHECS_MAX:]) == {429}
    # Le verrou tient même pour le bon mot de passe : sinon il ne freine rien.
    assert client.get("/api/admin/verify", headers=ADMIN).status_code == 429


def test_force_brute_chat_verrouillee(client):
    codes = [client.post("/api/chat", json={"question": "x"},
                         headers={"X-API-Password": f"essai{i}"}).status_code
             for i in range(7)]
    assert codes[-1] == 429


def test_limite_de_debit_sur_les_routes_admin(client):
    """12/minute en test : la douzième passe, la treizième non."""
    codes = [client.get("/api/admin/verify", headers=ADMIN).status_code
             for _ in range(13)]
    assert codes[:12] == [200] * 12 and codes[12] == 429


# --------------------------------------------------------------------------- #
# 2. CORS
# --------------------------------------------------------------------------- #

def test_cors_domaine_autorise(client):
    r = client.options("/api/chat", headers={
        "Origin": "https://client-autorise.com",
        "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == "https://client-autorise.com"


def test_cors_domaine_pirate_bloque(client):
    r = client.options("/api/chat", headers={
        "Origin": "https://pirate.com",
        "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") != "https://pirate.com"


# --------------------------------------------------------------------------- #
# 3. Limite de débit
# --------------------------------------------------------------------------- #

def test_limite_de_debit(client):
    codes = [client.post("/api/chat", json={"question": f"q{i}"},
                         headers=CHAT).status_code for i in range(4)]
    assert codes[:3] == [200, 200, 200]
    assert codes[3] == 429
    r = client.post("/api/chat", json={"question": "x"}, headers=CHAT)
    assert r.status_code == 429 and r.json()["error"]


def test_x_forwarded_for_falsifie_ne_contourne_pas_la_limite(client):
    """Le proxy ajoute l'IP qu'il a vue à la FIN de X-Forwarded-For ; le début
    est écrit par l'appelant. En lisant le premier élément, il suffisait de le
    changer à chaque requête pour repartir avec un compteur neuf."""
    codes = [client.post("/api/chat", json={"question": f"q{i}"},
                         headers={**CHAT,
                                  "X-Forwarded-For": f"10.0.0.{i}, 203.0.113.7"}
                         ).status_code for i in range(4)]
    assert codes == [200, 200, 200, 429]


def test_ip_client_ignore_l_entete_sans_proxy(client, monkeypatch):
    """TRUSTED_PROXIES=0 : plus aucun proxy devant, l'en-tête n'est plus lu."""
    monkeypatch.setattr(server, "TRUSTED_PROXIES", 0)
    codes = [client.post("/api/chat", json={"question": f"q{i}"},
                         headers={**CHAT, "X-Forwarded-For": f"10.0.0.{i}"}
                         ).status_code for i in range(4)]
    assert codes == [200, 200, 200, 429]


# --------------------------------------------------------------------------- #
# 3 bis. Domaines autorisés : refus au démarrage plutôt qu'ouverture silencieuse
# --------------------------------------------------------------------------- #

def test_origines_etoile_refusee(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "*")
    with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS"):
        server._origines_autorisees()


def test_origines_vides_refusees(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", " , ")
    with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS"):
        server._origines_autorisees()


def test_origines_absentes_se_limitent_au_local(monkeypatch):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    assert server._origines_autorisees() == ["http://localhost:8000",
                                             "http://127.0.0.1:8000"]


def test_origines_listees(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.fr, https://www.a.fr")
    assert server._origines_autorisees() == ["https://a.fr", "https://www.a.fr"]


# --------------------------------------------------------------------------- #
# 4. Requêtes valides et malformées
# --------------------------------------------------------------------------- #

def test_reponse_complete(client):
    r = client.post("/api/chat", json={"question": "bonjour"}, headers=CHAT)
    assert r.status_code == 200
    d = r.json()
    assert d["answer"] and d["sources"] == ["Manuel-employe.pdf"] and d["chunks"]


def test_question_vide(client):
    for question in ("", "   "):
        r = client.post("/api/chat", json={"question": question}, headers=CHAT)
        assert r.status_code == 400 and r.json()["error"]


def test_corps_malforme(client):
    """Un corps sans le champ `question` doit donner un 422 propre, jamais un 500."""
    r = client.post("/api/chat", json={"pas_la_bonne_cle": 1}, headers=CHAT)
    assert r.status_code == 422
    assert "detail" in r.json()


def test_historique_malforme_est_rejete_proprement(client):
    r = client.post("/api/chat", json={"question": "salut", "history": "pas une liste"},
                    headers=CHAT)
    assert r.status_code == 422


def test_panne_interne_reste_presentable(client, monkeypatch):
    """Une exception inattendue ne doit jamais fuiter de trace technique."""
    def boum(*a, **k):
        raise RuntimeError("clé secrète sk-ant-XXXX dans le message")
    monkeypatch.setattr(rag_core, "answer_question", boum)
    r = client.post("/api/chat", json={"question": "test"}, headers=CHAT)
    assert r.status_code == 500
    corps = r.text
    assert "sk-ant" not in corps and "Traceback" not in corps
    assert r.json()["error"]


def test_panne_de_modele_message_clair(client, monkeypatch):
    """Une panne du fournisseur de LLM est expliquée en français."""
    def indisponible(*a, **k):
        raise rag_core.ModeleIndisponible("Le service est momentanément injoignable.")
    monkeypatch.setattr(rag_core, "answer_question", indisponible)
    r = client.post("/api/chat", json={"question": "test"}, headers=CHAT)
    assert r.status_code == 503
    assert "injoignable" in r.json()["error"]
