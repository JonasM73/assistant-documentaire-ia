"""Teste les 3 protections de server.py sans appeler d'API réelle."""
import os
os.environ["DEMO_PASSWORD"] = "secret123"
os.environ["ALLOWED_ORIGINS"] = "https://client-autorise.com"
os.environ["RATE_LIMIT"] = "3/minute"

from fastapi.testclient import TestClient
import server

ok = True
def verdict(nom, cond):
    global ok
    print(f"  [{'PASS' if cond else 'FAIL'}] {nom}")
    if not cond: ok = False

H = {"X-API-Password": "secret123"}

# --- Auth : on utilise un client neuf pour ne pas polluer le compteur ---
c = TestClient(server.app)

print("TEST 1 — sans mot de passe → 401")
r = c.post("/api/chat", json={"question": "test"})
verdict("401 sans mot de passe", r.status_code == 401)

print("TEST 2 — mauvais mot de passe → 401")
r = c.post("/api/chat", json={"question": "test"}, headers={"X-API-Password": "faux"})
verdict("401 mauvais mot de passe", r.status_code == 401)

print("TEST 3 — CORS domaine autorisé vs pirate")
r_ok = c.options("/api/chat", headers={"Origin":"https://client-autorise.com","Access-Control-Request-Method":"POST"})
verdict("domaine autorisé accepté", r_ok.headers.get("access-control-allow-origin")=="https://client-autorise.com")
r_no = c.options("/api/chat", headers={"Origin":"https://pirate.com","Access-Control-Request-Method":"POST"})
verdict("domaine pirate bloqué", r_no.headers.get("access-control-allow-origin")!="https://pirate.com")

# --- Limite de débit : client TOUT NEUF, compteur repart de zéro ---
# (le limiter compte par IP ; on réinitialise le storage pour un test propre)
server.limiter.reset()
c2 = TestClient(server.app)
print("TEST 4 — limite 3/minute : 4e requête → 429")
codes = [c2.post("/api/chat", json={"question": f"q{i}"}, headers=H).status_code for i in range(4)]
print(f"       codes = {codes}")
verdict("3 premières = 200", codes[:3] == [200,200,200])
verdict("4e = 429", codes[3] == 429)

# message clair du 429
r429 = c2.post("/api/chat", json={"question":"x"}, headers=H)
verdict("429 renvoie un message", r429.status_code==429 and len(r429.text)>0)
print(f"       message 429 = {r429.text[:80]}")

# --- Requête pleinement valide après reset ---
server.limiter.reset()
c3 = TestClient(server.app)
print("TEST 5 — requête autorisée complète → 200 + answer")
r = c3.post("/api/chat", json={"question":"bonjour"}, headers=H)
verdict("200 avec answer", r.status_code==200 and "answer" in r.json())

print("\nRÉSULTAT :", "TOUS LES TESTS PASSENT" if ok else "DES TESTS ÉCHOUENT")
import sys; sys.exit(0 if ok else 1)