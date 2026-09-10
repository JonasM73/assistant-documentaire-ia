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
     La valeur "*" est refusée au démarrage : une variable oubliée ne doit pas
     ouvrir l'assistant d'un client à n'importe quel site.
  4. Limite de débit : RATE_LIMIT requêtes par minute et par IP sur /api/chat,
     ADMIN_RATE_LIMIT sur /api/admin/*. Derrière un proxy (Railway), l'IP réelle
     est lue dans X-Forwarded-For en remontant de TRUSTED_PROXIES crans depuis la
     fin : le début de cet en-tête est écrit par l'appelant, donc falsifiable.
     Lancer uvicorn avec --proxy-headers --forwarded-allow-ips='*' (railway.json).
  5. Verrou anti-force brute : au-delà de ECHECS_MAX mots de passe faux dans la
     fenêtre, l'IP est refusée, sur le chat comme sur l'administration.
  6. La documentation interactive (/docs, /redoc, /openapi.json) est fermée :
     elle décrivait publiquement toutes les routes d'administration.

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
import hmac
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
RATE_LIMIT = os.environ.get("RATE_LIMIT", "30/minute").strip()
ADMIN_RATE_LIMIT = os.environ.get("ADMIN_RATE_LIMIT", "60/minute").strip()
# Nombre de proxys de confiance devant le service (Railway en place un).
try:
    TRUSTED_PROXIES = max(0, int(os.environ.get("TRUSTED_PROXIES", "1")))
except ValueError:
    TRUSTED_PROXIES = 1
# Verrou anti-force brute : essais tolérés par IP, et durée de la fenêtre.
ECHECS_MAX = 5
ECHECS_FENETRE = 300.0


def _origines_autorisees() -> list[str]:
    """Domaines autorisés à appeler l'API depuis un navigateur.

    Deux refus explicites plutôt qu'une ouverture silencieuse : « * » laisserait
    n'importe quel site interroger l'assistant du client avec le navigateur d'un
    visiteur, et une liste vide ne servirait à rien. Variable absente : on se
    limite à la machine locale, ce qui suffit au développement."""
    brut = os.environ.get("ALLOWED_ORIGINS")
    if brut is None:
        return ["http://localhost:8000", "http://127.0.0.1:8000"]
    origines = [o.strip() for o in brut.split(",") if o.strip()]
    if "*" in origines:
        raise RuntimeError(
            "ALLOWED_ORIGINS=* est refusé : n'importe quel site pourrait alors "
            "interroger cet assistant depuis le navigateur d'un visiteur. "
            "Indiquez les domaines du client, séparés par des virgules "
            "(ex. ALLOWED_ORIGINS=https://client.fr,https://www.client.fr).")
    if not origines:
        raise RuntimeError(
            "ALLOWED_ORIGINS est vide : indiquez au moins un domaine, "
            "ou retirez la variable pour n'autoriser que la machine locale.")
    return origines


ALLOWED_ORIGINS = _origines_autorisees()

ALLOWED_EXT = {".pdf", ".md", ".txt", ".docx"}
try:
    MAX_UPLOAD_MB = max(1, int(os.environ.get("MAX_UPLOAD_MB", "20")))
except ValueError:
    MAX_UPLOAD_MB = 20

FORMATS_LISIBLES = "PDF, Word, texte, Markdown"

log = logging.getLogger("assistant")

# --- Limiteur de débit par IP --------------------------------------------- #
def _ip_client(request: Request) -> str:
    """IP réelle du client, sans laquelle toutes les requêtes partagent l'IP du
    proxy et la limite de débit devient globale.

    X-Forwarded-For se lit par la FIN : chaque proxy traversé ajoute l'adresse
    qu'il a vue, alors que le début de l'en-tête est écrit par l'appelant lui-
    même. Prendre le premier élément revenait à laisser n'importe qui changer
    d'identité à chaque requête et contourner la limite avec un simple en-tête.
    On remonte donc d'autant de crans qu'il y a de proxys de confiance
    (TRUSTED_PROXIES) — mal réglé, ce nombre rend la limite trop stricte, jamais
    contournable."""
    directe = get_remote_address(request)
    if TRUSTED_PROXIES <= 0:
        return directe
    chaine = [p.strip() for p in
              request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    if not chaine:
        return directe
    return chaine[max(0, len(chaine) - TRUSTED_PROXIES)]


limiter = Limiter(key_func=_ip_client)

# La documentation interactive publierait la liste complète des routes, dont
# celles qui gèrent les documents du client : elle reste fermée.
app = FastAPI(title="Assistant documentaire", docs_url=None, redoc_url=None,
              openapi_url=None)
app.state.limiter = limiter


def _erreur_debit(request: Request, exc: RateLimitExceeded):
    """Même corps JSON que les autres erreurs, et une phrase en français."""
    return _erreur("Trop de requêtes en peu de temps. Patientez une minute.", 429)


app.add_exception_handler(RateLimitExceeded, _erreur_debit)


@app.middleware("http")
async def _entetes_securite(request: Request, call_next):
    """En-têtes de sécurité sur toutes les réponses. `setdefault` : une route qui
    a déjà posé l'en-tête garde sa valeur."""
    reponse = await call_next(request)
    reponse.headers.setdefault("X-Content-Type-Options", "nosniff")
    reponse.headers.setdefault("X-Frame-Options", "DENY")
    reponse.headers.setdefault("Referrer-Policy", "no-referrer")
    reponse.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
    if request.url.path.startswith("/api/"):
        reponse.headers.setdefault("Cache-Control", "no-store")
    if request.headers.get("x-forwarded-proto") == "https" or request.url.scheme == "https":
        reponse.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return reponse

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


# --- Mots de passe : comparaison et verrou anti-force brute --------------- #
# Essais infructueux récents, par (porte, IP). En mémoire du processus : il n'y
# a qu'une instance par client, et un redémarrage remet le compteur à zéro —
# suffisant pour rendre l'essai systématique impraticable.
_echecs: dict[tuple[str, str], list[float]] = {}


def _mot_de_passe_valide(fourni: str | None, attendu: str) -> bool:
    """Comparaison à durée constante. Avec `!=`, le temps de réponse varie selon
    le nombre de caractères déjà corrects : le mot de passe se devine alors
    lettre par lettre, sans jamais avoir à l'essayer en entier."""
    if not attendu or not fourni:
        return False
    return hmac.compare_digest(fourni.encode("utf-8"), attendu.encode("utf-8"))


def _verrou(porte: str, ip: str) -> None:
    """Refuse la requête quand cette IP a déjà accumulé trop d'essais faux.
    Sans ce verrou, /api/admin/* accepte un nombre illimité de tentatives sur le
    mot de passe qui commande les documents du client."""
    maintenant = time.time()
    recents = [t for t in _echecs.get((porte, ip), [])
               if maintenant - t < ECHECS_FENETRE]
    _echecs[(porte, ip)] = recents
    if len(recents) >= ECHECS_MAX:
        raise HTTPException(
            status_code=429,
            detail="Trop de tentatives infructueuses. "
                   "Réessayez dans quelques minutes.")


def _echec(porte: str, ip: str) -> None:
    """Enregistre un essai faux, et purge les IP devenues inactives pour que le
    dictionnaire ne grossisse pas indéfiniment."""
    maintenant = time.time()
    for cle, essais in list(_echecs.items()):
        if not essais or maintenant - essais[-1] >= ECHECS_FENETRE:
            _echecs.pop(cle, None)
    _echecs.setdefault((porte, ip), []).append(maintenant)


def reinitialiser_verrous() -> None:
    """Vide les compteurs d'essais (utilisé par les tests)."""
    _echecs.clear()


# --- Authentification chat (DEMO_PASSWORD) -------------------------------- #
def verifier_mot_de_passe(request: Request,
                          x_api_password: str | None = Header(default=None)):
    """Rejette la requête si le mot de passe du chat est absent ou faux.
    Si DEMO_PASSWORD est vide, l'authentification est désactivée (local/démo)."""
    if not DEMO_PASSWORD:
        return
    ip = _ip_client(request)
    _verrou("chat", ip)
    if not _mot_de_passe_valide(x_api_password, DEMO_PASSWORD):
        _echec("chat", ip)
        raise HTTPException(
            status_code=401,
            detail="Non autorisé : mot de passe manquant ou incorrect "
                   "(en-tête X-API-Password).")


# --- Authentification admin (ADMIN_PASSWORD) ------------------------------ #
def verifier_admin(request: Request,
                   x_api_password: str | None = Header(default=None)):
    """Protège les routes admin avec ADMIN_PASSWORD (distinct du mot de passe du
    chat). Si le chat est protégé mais qu'ADMIN_PASSWORD manque, l'administration
    est fermée : le mot de passe du chat ne donne jamais l'accès admin."""
    if not ADMIN_PASSWORD:
        if DEMO_PASSWORD:
            raise HTTPException(status_code=403, detail="Administration désactivée : "
                                "définissez ADMIN_PASSWORD sur le serveur.")
        return  # ni chat ni admin protégés : usage local
    ip = _ip_client(request)
    _verrou("admin", ip)
    if not _mot_de_passe_valide(x_api_password, ADMIN_PASSWORD):
        _echec("admin", ip)
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
        print(f"Limite de débit : /api/chat {RATE_LIMIT}, /api/admin/* {ADMIN_RATE_LIMIT}")
        print(f"Proxys de confiance devant le service : {TRUSTED_PROXIES}")
        print("Journal des questions : "
              + (f"actif → {journal.chemin()}" if journal.actif() else "désactivé (LOG_QUESTIONS)"))
    except Exception as e:
        print(f"Préchargement ignoré ({e}). Avez-vous lancé `python ingest.py` ?")


@app.get("/api/health")
def health(x_api_password: str | None = Header(default=None)):
    """Sonde de vie, publique parce que l'hébergeur l'interroge sans mot de passe
    (railway.json). Elle ne dit donc plus QUE le service tourne : la
    configuration — fournisseurs, état des protections — dressait autrement la
    carte du service pour n'importe qui. Le détail reste lisible avec le mot de
    passe admin, et au démarrage dans les journaux du serveur."""
    if not _mot_de_passe_valide(x_api_password, ADMIN_PASSWORD):
        return {"status": "ok"}
    return {"status": "ok",
            "embeddings": rag_core.resolve_embedding_provider(),
            "llm": rag_core.resolve_llm_provider(),
            "auth": "activée" if DEMO_PASSWORD else "désactivée",
            "admin": "séparé" if ADMIN_PASSWORD else ("FERMÉ (ADMIN_PASSWORD manquant)" if DEMO_PASSWORD else "ouvert (usage local)"),
            "rate_limit": RATE_LIMIT,
            "admin_rate_limit": ADMIN_RATE_LIMIT,
            "trusted_proxies": TRUSTED_PROXIES,
            "origines": ALLOWED_ORIGINS,
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


# --- Routes admin : gestion des documents (ADMIN_PASSWORD, débit limité) -- #
@app.get("/api/admin/verify")
@limiter.limit(ADMIN_RATE_LIMIT)
def admin_verify(request: Request, _=Depends(verifier_admin)):
    """Protégé (mot de passe admin) : renvoie 200 si bon, 401 sinon."""
    return {"ok": True}


@app.get("/api/admin/files")
@limiter.limit(ADMIN_RATE_LIMIT)
def admin_files(request: Request, _=Depends(verifier_admin)):
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
@limiter.limit(ADMIN_RATE_LIMIT)
def admin_upload(request: Request, file: UploadFile = File(...),
                 _=Depends(verifier_admin)):
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
@limiter.limit(ADMIN_RATE_LIMIT)
def admin_stats(request: Request, _=Depends(verifier_admin)):
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
@limiter.limit(ADMIN_RATE_LIMIT)
def admin_questions(request: Request, debut: str = "", fin: str = "", q: str = "",
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
@limiter.limit(ADMIN_RATE_LIMIT)
def admin_delete(request: Request, name: str = Form(...),
                 _=Depends(verifier_admin)):
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