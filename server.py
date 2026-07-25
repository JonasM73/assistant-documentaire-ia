"""
server.py — Serveur de démo web.

Expose le RAG (rag_core) via une API et sert la page de démonstration
(web/) qui montre l'assistant en widget flottant, intégré ou plein écran.

Lancement :
    .\\venv\\Scripts\\python.exe -m uvicorn server:app --reload
puis ouvrir http://localhost:8000

Réutilise le même index vectoriel (chroma_db) que la version Streamlit —
aucune ré-indexation nécessaire.
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import rag_core
import recherche_hybride
recherche_hybride.activer()

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

app = FastAPI(title="Assistant documentaire — démo")


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
    except Exception as e:
        print(f"Préchargement ignoré ({e}). Avez-vous lancé `python ingest.py` ?")


@app.get("/api/health")
def health():
    return {"status": "ok",
            "embeddings": rag_core.resolve_embedding_provider(),
            "llm": rag_core.resolve_llm_provider()}


@app.post("/api/chat")
def chat(inp: ChatIn):
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