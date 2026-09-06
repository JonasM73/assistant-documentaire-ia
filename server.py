"""
server.py — Serveur de démo web, avec protections de production.

Expose le RAG (rag_core) via une API et sert la page de démonstration (web/).

Protections, configurables via .env :
  1. Authentification chat : mot de passe partagé (DEMO_PASSWORD) dans l'en-tête
     X-API-Password. Désactivée si DEMO_PASSWORD est vide (local/démo).
  2. Authentification admin : mot de passe séparé (ADMIN_PASSWORD) pour la
     gestion des documents. Si DEMO_PASSWORD est défini sans ADMIN_PASSWORD,
     l'administration est DÉSACTIVÉE (jamais de repli sur le mot de passe du chat).
  3. CORS : seuls les domaines listés dans ALLOWED_ORIGINS peuvent appeler l'API.
  4. Limite de débit : RATE_LIMIT requêtes par minute et par IP sur /api/chat.
     Derrière un proxy (Railway), l'IP réelle est lue dans X-Forwarded-For :
     lancer uvicorn avec --proxy-headers --forwarded-allow-ips='*' (railway.json).

Option tableau de bord (LOG_QUESTIONS) : journal des questions opt-in (JSONL :
date, question, sources, refus — rien d'autre) et statistiques d'usage servies
par /api/admin/stats, affichées dans gestion.html.

Lancement :
    python -m uvicorn server:app --reload
puis ouvrir http://localhost:8000
"""

import os
import re
import glob
import logging
import sys
import time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))

from fastapi import FastAPI, Request, Header, HTTPException, Depends
from fastapi import UploadFile, File, Form
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
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
import journal
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
try:
    MAX_UPLOAD_MB = max(1, int(os.environ.get("MAX_UPLOAD_MB", "20")))
except ValueError:
    MAX_UPLOAD_MB = 20

FORMATS_LISIBLES = "PDF, Word, texte, Markdown"

log = logging.getLogger("assistant")

# --- Limiteur de débit par IP --------------------------------------------- #
def _ip_client(request: Request) -> str:
    """IP réelle du client : premier X-Forwarded-For derrière un proxy (Railway),
    sinon l'adresse de la connexion. Sans cela, toutes les requêtes partagent
    l'IP du proxy et la limite devient globale."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_ip_client)

app = FastAPI(title="Assistant documentaire — démo")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- CORS : liste blanche de domaines ------------------------------------- #
# L'API s'authentifie par en-tête (X-API-Password), jamais par cookie : pas de
# credentials CORS. (Un "*" avec allow_credentials=True serait de toute façon refusé
# par les navigateurs.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _safe_name(name: str) -> str:
    """Nom de fichier sûr : pas de chemin, caractères contrôlés."""
    name = os.path.basename((name or "").replace("\\", "/"))
    name = re.sub(r"[^A-Za-z0-9 ._()+-]", "_", name).strip(" .")
    return name or "document"


def _data_dir() -> str:
    """Dossier des documents, créé au besoin. Lu à chaque appel : la variable
    peut changer entre deux déploiements (volume persistant)."""
    d = os.environ.get("DATA_DIR", "data")
    os.makedirs(d, exist_ok=True)
    return d


def _erreur(message: str, code: int = 500) -> JSONResponse:
    """Réponse d'erreur unique pour toute l'API.

    Contient `error` (lu par le widget) ET `detail` (lu par gestion.html), pour
    que les deux interfaces affichent toujours une phrase en français plutôt
    qu'un statut nu."""
    return JSONResponse({"error": message, "detail": message}, status_code=code)


# --- Filet de sécurité : aucune trace technique ne sort de l'API ----------- #
@app.exception_handler(StarletteHTTPException)
def _erreur_http(request: Request, exc: StarletteHTTPException):
    """Uniformise les erreurs HTTP volontaires (401, 400, 404…) : même corps
    JSON partout, message déjà rédigé en français à la levée."""
    detail = exc.detail if isinstance(exc.detail, str) and exc.detail else "Requête refusée."
    return JSONResponse({"error": detail, "detail": detail},
                        status_code=exc.status_code,
                        headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
def _erreur_validation(request: Request, exc: RequestValidationError):
    """Requête malformée : on garde `detail` (contrat FastAPI) et on ajoute une
    phrase compréhensible."""
    return JSONResponse(
        {"error": "Requête invalide : le format des données envoyées est incorrect.",
         "detail": exc.errors()},
        status_code=422)


@app.exception_handler(Exception)
def _erreur_inattendue(request: Request, exc: Exception):
    """Dernier rempart : la cause exacte part dans les journaux du serveur,
    l'utilisateur reçoit une phrase neutre (jamais de clé ni de pile d'appels)."""
    log.exception("Erreur non gérée sur %s", request.url.path)
    return _erreur("Une erreur interne est survenue. Réessayez dans quelques instants.")


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
    chat). Si le chat est protégé mais qu'ADMIN_PASSWORD manque, l'administration
    est fermée : le mot de passe du chat ne donne jamais l'accès admin."""
    if not ADMIN_PASSWORD:
        if DEMO_PASSWORD:
            raise HTTPException(status_code=403, detail="Administration désactivée : "
                                "définissez ADMIN_PASSWORD sur le serveur.")
        return  # ni chat ni admin protégés : usage local
    if x_api_password != ADMIN_PASSWORD:
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
        print("Journal des questions : "
              + (f"actif → {journal.chemin()}" if journal.actif() else "désactivé (LOG_QUESTIONS)"))
    except Exception as e:
        print(f"Préchargement ignoré ({e}). Avez-vous lancé `python ingest.py` ?")


@app.get("/api/health")
def health():
    """Non protégé : sert à vérifier que le service tourne."""
    return {"status": "ok",
            "embeddings": rag_core.resolve_embedding_provider(),
            "llm": rag_core.resolve_llm_provider(),
            "auth": "activée" if DEMO_PASSWORD else "désactivée",
            "admin": "séparé" if ADMIN_PASSWORD else ("FERMÉ (ADMIN_PASSWORD manquant)" if DEMO_PASSWORD else "ouvert (usage local)"),
            "rate_limit": RATE_LIMIT,
            "journal": "actif" if journal.actif() else "désactivé"}


@app.get("/api/verify")
def verify(_=Depends(verifier_mot_de_passe)):
    """Protégé (mot de passe chat) : renvoie 200 si bon, 401 sinon."""
    return {"ok": True}


@app.post("/api/chat")
@limiter.limit(RATE_LIMIT)
def chat(request: Request, inp: ChatIn, _=Depends(verifier_mot_de_passe)):
    question = (inp.question or "").strip()
    if not question:
        return _erreur("Question vide.", 400)
    try:
        history = [{"role": t.role, "content": t.content} for t in inp.history]
        t0 = time.time()
        res = rag_core.answer_question(question, history=history)
    except rag_core.ModeleIndisponible as e:
        # Panne côté fournisseur de modèle : message déjà rédigé pour l'utilisateur.
        log.warning("Modèle indisponible : %s", e)
        return _erreur(str(e), 503)
    except Exception:
        log.exception("Échec de la réponse à une question")
        return _erreur("L'assistant n'a pas pu traiter votre question. "
                       "Réessayez dans quelques instants.")
    # Journal des questions (option tableau de bord) : opt-in via LOG_QUESTIONS —
    # question/date/sources/refus + durée de réponse. Fail-safe par construction.
    journal.enregistrer(question, res.sources, journal.est_refus(res.answer),
                        duree=time.time() - t0)
    return {"answer": res.answer, "sources": res.sources, "chunks": res.chunks}


# --- Routes admin : gestion des documents (ADMIN_PASSWORD) ---------------- #
@app.get("/api/admin/verify")
def admin_verify(_=Depends(verifier_admin)):
    """Protégé (mot de passe admin) : renvoie 200 si bon, 401 sinon."""
    return {"ok": True}


@app.get("/api/admin/files")
def admin_files(_=Depends(verifier_admin)):
    try:
        d = _data_dir()
    except OSError:
        log.exception("Dossier des documents inaccessible")
        raise HTTPException(500, "Le dossier des documents est inaccessible.")
    files = []
    for ext in ALLOWED_EXT:
        for p in glob.glob(os.path.join(d, f"*{ext}")):
            try:
                taille = os.path.getsize(p)
            except OSError:
                continue          # fichier supprimé entre-temps : on l'ignore
            files.append({"name": os.path.basename(p), "size": taille})
    files.sort(key=lambda f: f["name"].lower())
    return {"files": files}


def _ecrire_televersement(fichier: UploadFile, dest: str) -> int:
    """Écrit le fichier reçu sur disque par blocs, en refusant les dépassements
    de taille. Retourne la taille écrite. En cas d'échec, le fichier partiel
    est supprimé — jamais de document tronqué dans le corpus."""
    taille = 0
    limite = MAX_UPLOAD_MB * 1024 * 1024
    try:
        with open(dest, "wb") as out:
            while True:
                buf = fichier.file.read(1024 * 1024)
                if not buf:
                    break
                taille += len(buf)
                if taille > limite:
                    raise HTTPException(
                        400, f"Fichier trop volumineux (> {MAX_UPLOAD_MB} Mo).")
                out.write(buf)
    except HTTPException:
        _supprimer_silencieux(dest)
        raise
    except OSError:
        _supprimer_silencieux(dest)
        log.exception("Écriture impossible : %s", dest)
        raise HTTPException(500, "Impossible d'enregistrer le fichier sur le serveur "
                                 "(espace disque ou permissions).")
    return taille


def _supprimer_silencieux(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        log.warning("Suppression impossible : %s", path)


@app.post("/api/admin/upload")
def admin_upload(file: UploadFile = File(...), _=Depends(verifier_admin)):
    nom_recu = (file.filename or "").strip()
    if not nom_recu:
        raise HTTPException(400, "Fichier sans nom : impossible à enregistrer.")
    ext = os.path.splitext(nom_recu)[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(
            400, f"Format non supporté ({ext or 'sans extension'}). "
                 f"Acceptés : {FORMATS_LISIBLES}.")
    try:
        d = _data_dir()
    except OSError:
        log.exception("Dossier des documents inaccessible")
        raise HTTPException(500, "Le dossier des documents est inaccessible.")

    name = _safe_name(nom_recu)
    dest = os.path.join(d, name)
    taille = _ecrire_televersement(file, dest)
    if taille == 0:
        _supprimer_silencieux(dest)
        raise HTTPException(400, "Le fichier est vide.")

    try:
        n = ingest_ameliore.index_file(dest)
    except Exception as e:
        # Le fichier est conservé (il est valide du point de vue du stockage),
        # mais on dit franchement que l'assistant ne s'en sert pas encore.
        log.exception("Indexation échouée : %s", name)
        raise HTTPException(500, f"« {name} » a été enregistré, mais son indexation "
                                 f"a échoué : {e}")
    if n == 0:
        raise HTTPException(
            422, f"« {name} » a été enregistré, mais aucun texte n'a pu en être "
                 f"extrait. S'il s'agit d'un document scanné, il faut d'abord le "
                 f"passer à l'OCR.")
    return {"ok": True, "name": name, "chunks": n}


@app.get("/api/admin/stats")
def admin_stats(_=Depends(verifier_admin)):
    """Protégé (mot de passe admin) : statistiques d'usage tirées du journal
    des questions. Les questions sont regroupées par SENS grâce au modèle
    d'embedding local (déjà chargé pour l'index — coût zéro, rien ne sort de
    l'instance) ; repli sur un regroupement par formulation si le modèle est
    indisponible. Renvoie actif=false si le journal n'est pas activé."""
    try:
        ef = rag_core.get_embedding_function()
    except Exception:
        ef = None
    try:
        return journal.stats(embed_fn=ef)
    except Exception:
        # Le tableau de bord ne doit jamais tomber en panne à cause du journal.
        log.exception("Calcul des statistiques impossible")
        return {"actif": journal.actif(), "erreur": True, "total": 0, "refus": 0,
                "taux_refus": 0.0, "duree_moyenne": None, "groupement": "lexical",
                "par_jour": [], "par_heure": [0] * 24, "par_semaine": [0] * 7,
                "sujets": [], "nb_sujets": 0, "sans_reponse": [], "sources": [],
                "dernieres": []}


@app.get("/api/admin/questions")
def admin_questions(debut: str = "", fin: str = "", q: str = "",
                    limite: int = 100, _=Depends(verifier_admin)):
    """Protégé (mot de passe admin) : recherche dans le journal des questions.
    Filtres : debut/fin (AAAA-MM-JJ, bornes incluses) et q (texte contenu
    dans la question). Sert l'explorateur de la page gestion.html."""
    try:
        return journal.rechercher(debut=debut, fin=fin, texte=q, limite=limite)
    except Exception:
        log.exception("Recherche impossible dans le journal")
        return {"total": 0, "questions": []}


@app.post("/api/admin/delete")
def admin_delete(name: str = Form(...), _=Depends(verifier_admin)):
    safe = _safe_name(name)
    if not (name or "").strip():
        raise HTTPException(400, "Aucun document indiqué.")
    dest = os.path.join(_data_dir(), safe)
    existait = os.path.exists(dest)
    if existait:
        try:
            os.remove(dest)
        except OSError:
            log.exception("Suppression impossible : %s", dest)
            raise HTTPException(500, f"« {safe} » n'a pas pu être supprimé du serveur.")
    try:
        ingest_ameliore.deindex_file(safe)
    except rag_core.IndexIntrouvable:
        pass                      # rien à désindexer : l'index n'existe pas encore
    except Exception as e:
        log.exception("Désindexation échouée : %s", safe)
        raise HTTPException(500, f"« {safe} » a été supprimé du serveur, mais sa "
                                 f"désindexation a échoué : {e}")
    return {"ok": True, "name": safe, "existait": existait}


# La page web est servie en dernier (catch-all) pour ne pas masquer /api/*.
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")