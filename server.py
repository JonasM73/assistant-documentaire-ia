"""
server.py — Serveur de démo web, avec protections de production.

Expose le RAG (rag_core) via une API et sert la page de démonstration (web/).

Trois protections, toutes configurables via .env :
  1. Authentification : mot de passe partagé dans l'en-tête X-API-Password.
     Désactivée si DEMO_PASSWORD est vide (pratique en local, à NE PAS faire
     en production).
  2. CORS : seuls les domaines listés dans ALLOWED_ORIGINS peuvent appeler
     l'API depuis un navigateur.
  3. Limite de débit : RATE_LIMIT requêtes par minute et par IP sur /api/chat,
     pour protéger la clé API du client contre les abus.

Lancement :
    python -m uvicorn server:app --reload
puis ouvrir http://localhost:8000
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))

from fastapi import FastAPI, Request, Header, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Charge le .env s'il existe (python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import rag_core
import recherche_hybride
recherche_hybride.activer()

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

# --- Configuration lue depuis .env ---------------------------------------- #
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "").strip()
# Domaines autorisés à appeler l'API depuis un navigateur, séparés par des virgules.
# Ex : "https://client.com,https://www.client.com". "*" = tout (démo uniquement).
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get(
    "ALLOWED_ORIGINS", "*").split(",") if o.strip()]
# Limite de débit sur /api/chat, ex : "30/minute".
RATE_LIMIT = os.environ.get("RATE_LIMIT", "30/minute").strip()

# --- Limiteur de débit par IP --------------------------------------------- #
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Assistant documentaire — démo")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- CORS : liste blanche de domaines ------------------------------------- #
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# --- Authentification par mot de passe partagé ---------------------------- #
def verifier_mot_de_passe(x_api_password: str | None = Header(default=None)):
    """Rejette la requête si le mot de passe est absent ou faux.
    Si DEMO_PASSWORD est vide, l'authentification est désactivée (local/démo)."""
    if not DEMO_PASSWORD:
        return  # auth désactivée
    if x_api_password != DEMO_PASSWORD:
        raise HTTPException(
            status_code=401,
            detail="Non autorisé : mot de passe manquant ou incorrect "
                   "(en-tête X-API-Password).")


class Turn(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    question: str
    history: list[Turn] = []


@app.on_event("startup")
def _warmup():
    """Précharge le modèle d'embedding et la collection pour éviter la latence
    au premier message."""
    try:
        rag_core.get_collection()
        print("Modèle d'embedding et index chargés.")
        if not DEMO_PASSWORD:
            print("ATTENTION : DEMO_PASSWORD vide → API non protégée (OK en local, "
                  "à définir en production).")
        print(f"CORS autorisé pour : {ALLOWED_ORIGINS}")
        print(f"Limite de débit /api/chat : {RATE_LIMIT}")
    except Exception as e:
        print(f"Préchargement ignoré ({e}). Avez-vous lancé `python ingest.py` ?")


@app.get("/api/health")
def health():
    """Non protégé : sert à vérifier que le service tourne."""
    return {"status": "ok",
            "embeddings": rag_core.resolve_embedding_provider(),
            "llm": rag_core.resolve_llm_provider(),
            "auth": "activée" if DEMO_PASSWORD else "désactivée",
            "rate_limit": RATE_LIMIT}


@app.post("/api/chat")
@limiter.limit(RATE_LIMIT)
def chat(request: Request, inp: ChatIn, _=Depends(verifier_mot_de_passe)):
    question = (inp.question or "").strip()
    if not question:
        return JSONResponse({"error": "Question vide."}, status_code=400)
    try:
        history = [{"role": t.role, "content": t.content} for t in inp.history]
        res = rag_core.answer_question(question, history=history)
        return {"answer": res.answer, "sources": res.sources, "chunks": res.chunks}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# La page web est servie en dernier (catch-all) pour ne pas masquer /api/*.
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")