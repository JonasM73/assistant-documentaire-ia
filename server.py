"""
server.py — Serveur de démo web, avec protections de production.

Expose le RAG (rag_core) via une API et sert la page de démonstration (web/).

Protections, configurables via .env :
  1. Authentification chat : mot de passe partagé (DEMO_PASSWORD) dans l'en-tête
     X-API-Password. Désactivée si DEMO_PASSWORD est vide (local/démo).
  2. Authentification admin : mot de passe séparé (ADMIN_PASSWORD) pour la
     gestion des documents. Repli sur DEMO_PASSWORD s'il n'est pas défini.
  3. CORS : seuls les domaines listés dans ALLOWED_ORIGINS peuvent appeler l'API.
  4. Limite de débit : RATE_LIMIT requêtes par minute et par IP sur /api/chat.

Lancement :
    python -m uvicorn server:app --reload
puis ouvrir http://localhost:8000
"""

import os
import re
import glob
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))

from fastapi import FastAPI, Request, Header, HTTPException, Depends
from fastapi import UploadFile, File, Form
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
import ingest_ameliore
recherche_hybride.activer()

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

# --- Configuration lue depuis .env ---------------------------------------- #
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "").strip()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "").strip()
# Domaines autorisés à appeler l'API depuis un navigateur, séparés par des virgules.
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get(
    "ALLOWED_ORIGINS", "*").split(",") if o.strip()]
RATE_LIMIT = os.environ.get("RATE_LIMIT", "30/minute").strip()

ALLOWED_EXT = {".pdf", ".md", ".txt", ".docx"}
MAX_UPLOAD_MB = 20

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


def _safe_name(name: str) -> str:
    """Nom de fichier sûr : pas de chemin, caractères contrôlés."""
    name = os.path.basename(name or "")
    return re.sub(r"[^A-Za-z0-9 ._()+-]", "_", name).strip() or "document"


# --- Authentification chat (DEMO_PASSWORD) -------------------------------- #
def verifier_mot_de_passe(x_api_password: str | None = Header(default=None)):
    """Rejette la requête si le mot de passe du chat est absent ou faux.
    Si DEMO_PASSWORD est vide, l'authentification est désactivée (local/démo)."""
    if not DEMO_PASSWORD:
        return
    if x_api_password != DEMO_PASSWORD:
        raise HTTPException(
            status_code=401,
            detail="Non autorisé : mot de passe manquant ou incorrect "
                   "(en-tête X-API-Password).")


# --- Authentification admin (ADMIN_PASSWORD) ------------------------------ #
def verifier_admin(x_api_password: str | None = Header(default=None)):
    """Protège les routes admin avec ADMIN_PASSWORD (distinct du mot de passe du
    chat). Repli sur DEMO_PASSWORD si ADMIN_PASSWORD n'est pas défini."""
    attendu = ADMIN_PASSWORD or DEMO_PASSWORD
    if not attendu:
        return
    if x_api_password != attendu:
        raise HTTPException(status_code=401, detail="Accès admin refusé.")


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
        if not (ADMIN_PASSWORD or DEMO_PASSWORD):
            print("ATTENTION : aucune protection admin (ni ADMIN_PASSWORD ni DEMO_PASSWORD).")
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
            "admin": "séparé" if ADMIN_PASSWORD else ("repli chat" if DEMO_PASSWORD else "désactivé"),
            "rate_limit": RATE_LIMIT}


@app.get("/api/verify")
def verify(_=Depends(verifier_mot_de_passe)):
    """Protégé (mot de passe chat) : renvoie 200 si bon, 401 sinon."""
    return {"ok": True}


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


# --- Routes admin : gestion des documents (ADMIN_PASSWORD) ---------------- #
@app.get("/api/admin/verify")
def admin_verify(_=Depends(verifier_admin)):
    """Protégé (mot de passe admin) : renvoie 200 si bon, 401 sinon."""
    return {"ok": True}


@app.get("/api/admin/files")
def admin_files(_=Depends(verifier_admin)):
    d = os.environ.get("DATA_DIR", "data")
    os.makedirs(d, exist_ok=True)
    files = []
    for ext in ALLOWED_EXT:
        for p in glob.glob(os.path.join(d, f"*{ext}")):
            files.append({"name": os.path.basename(p), "size": os.path.getsize(p)})
    files.sort(key=lambda f: f["name"].lower())
    return {"files": files}


@app.post("/api/admin/upload")
def admin_upload(file: UploadFile = File(...), _=Depends(verifier_admin)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Format non supporté ({ext}). Acceptés : PDF, Word, texte, Markdown.")
    d = os.environ.get("DATA_DIR", "data")
    os.makedirs(d, exist_ok=True)
    name = _safe_name(file.filename)
    dest = os.path.join(d, name)
    size = 0
    with open(dest, "wb") as out:
        while True:
            buf = file.file.read(1024 * 1024)
            if not buf:
                break
            size += len(buf)
            if size > MAX_UPLOAD_MB * 1024 * 1024:
                out.close(); os.remove(dest)
                raise HTTPException(400, f"Fichier trop volumineux (> {MAX_UPLOAD_MB} Mo).")
            out.write(buf)
    try:
        n = ingest_ameliore.index_file(dest)
    except Exception as e:
        raise HTTPException(500, f"Enregistré mais indexation échouée : {e}")
    return {"ok": True, "name": name, "chunks": n}


@app.post("/api/admin/delete")
def admin_delete(name: str = Form(...), _=Depends(verifier_admin)):
    d = os.environ.get("DATA_DIR", "data")
    safe = _safe_name(name)
    dest = os.path.join(d, safe)
    if os.path.exists(dest):
        os.remove(dest)
    try:
        ingest_ameliore.deindex_file(safe)
    except Exception as e:
        raise HTTPException(500, f"Fichier supprimé mais désindexation échouée : {e}")
    return {"ok": True, "name": safe}


# La page web est servie en dernier (catch-all) pour ne pas masquer /api/*.
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")