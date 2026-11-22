"""NOXPclips — serveur web (API + interface)."""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import shutil
import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import db, jobs, scheduler
from .config import (BRAND_DIR, DATA_DIR, FONTS_DIR, PASSWORD, PROJECTS_DIR, SECRET_KEY, SECRET_SETTING_KEYS, STATIC_DIR,
                     UPLOADS_DIR)
from .pipeline import analyze as an
from .pipeline import captions as cap
from .pipeline import download as dl
from .pipeline import ffmpeg as ff
from .pipeline import llm
from .social import platforms

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("noxp")

VERSION = "1.0.0"
app = FastAPI(title="NOXPclips", version=VERSION)

AUTH_COOKIE = "noxp_auth"
OPEN_PATHS = ("/api/login", "/api/auth", "/api/oauth/")


def _auth_token() -> str:
    return hmac.new(SECRET_KEY.encode(), b"noxp-ok", hashlib.sha256).hexdigest()


@app.middleware("http")
async def auth_mw(request: Request, call_next):
    path = request.url.path
    if PASSWORD and (path.startswith("/api/") or path.startswith("/media/")):
        open_ = any(path.startswith(p) for p in OPEN_PATHS) and not path.endswith("/start")
        if not open_ and not hmac.compare_digest(request.cookies.get(AUTH_COOKIE, ""), _auth_token()):
            return JSONResponse({"detail": "auth"}, status_code=401)
    return await call_next(request)


@app.on_event("startup")
def _startup():
    db.init()
    jobs.start_worker()
    scheduler.start()


def base_url(request: Request) -> str:
    s = db.get_settings()
    if s.get("public_url"):
        return s["public_url"].rstrip("/")
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}"


# ------------------------------------------------------------------ Auth

@app.get("/api/auth")
def auth_status(request: Request):
    ok = not PASSWORD or hmac.compare_digest(request.cookies.get(AUTH_COOKIE, ""), _auth_token())
    return {"required": bool(PASSWORD), "ok": ok}


@app.post("/api/login")
async def login(request: Request):
    body = await request.json()
    if not PASSWORD or not hmac.compare_digest(str(body.get("password", "")), PASSWORD):
        time.sleep(1)
        raise HTTPException(401, "Mot de passe incorrect")
    resp = JSONResponse({"ok": True})
    secure = (request.headers.get("x-forwarded-proto") or request.url.scheme) == "https"
    resp.set_cookie(AUTH_COOKIE, _auth_token(), max_age=3600 * 24 * 365, httponly=True,
                    samesite="lax", secure=secure)
    return resp


# ------------------------------------------------------------------ Système

@app.get("/api/system")
def system(request: Request):
    s = db.get_settings()
    usage = shutil.disk_usage(DATA_DIR)
    size = sum(f.stat().st_size for f in PROJECTS_DIR.rglob("*") if f.is_file())
    b = base_url(request)
    return {
        "version": VERSION,
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "ai_engine": llm.available_engine(s),
        "whisper_model": s.get("whisper_model"),
        "disk_free_gb": round(usage.free / 1e9, 1),
        "projects_size_gb": round(size / 1e9, 2),
        "base_url": b,
        "redirect_uris": {p: platforms.redirect_uri(b, p) for p in ("youtube", "tiktok", "instagram")},
    }


@app.post("/api/storage/cleanup")
def storage_cleanup():
    return jobs.free_space()


@app.get("/api/styles")
def styles():
    return {
        "captions": [{"id": k, **v} for k, v in cap.STYLES.items()],
        "categories": an.CATEGORY_LABELS,
        "lengths": list(an.LENGTH_PRESETS),
    }


@app.post("/api/ai/test")
def ai_test():
    s = db.get_settings()
    engine = llm.available_engine(s)
    if engine == "heuristic":
        msg = "Aucune IA joignable : NOXPclips utilise ses heuristiques locales (ça marche aussi !)."
        if s.get("ai_engine") == "ollama":
            msg = f"Ollama injoignable sur {s['ollama_url']} ou modèle {s['ollama_model']} absent (ollama pull {s['ollama_model']})."
        return {"ok": False, "engine": engine, "message": msg}
    try:
        out = llm.chat(s, 'Réponds en JSON {"answer": "..."}', "Dis bonjour en 3 mots.", engine=engine, timeout=60)
        data = llm.parse_json(out)
        return {"ok": True, "engine": engine, "answer": str(data.get("answer", out))[:80]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "engine": engine, "message": f"Erreur {engine} : {str(e)[:200]}"}


# ------------------------------------------------------------------ Réglages

@app.get("/api/settings")
def get_settings():
    s = db.get_settings()
    for k in SECRET_SETTING_KEYS:
        s[k] = "••••••••" if s.get(k) else ""
    return s


@app.put("/api/settings")
async def put_settings(request: Request):
    body = await request.json()
    clean = {}
    for k, v in body.items():
        if k in SECRET_SETTING_KEYS and (v == "••••••••"):
            continue
        clean[k] = v
    if "brand" in clean:
        brand = db.get_settings()["brand"]
        brand.update(clean["brand"] or {})
        clean["brand"] = brand
    db.set_settings(clean)
    return get_settings()


@app.post("/api/settings/cookies")
async def upload_cookies(file: UploadFile = File(...)):
    dest = DATA_DIR / "cookies.txt"
    with open(dest, "wb") as fh:
        shutil.copyfileobj(file.file, fh)
    db.set_settings({"ytdlp_cookies": str(dest)})
    return {"ok": True}


@app.delete("/api/settings/cookies")
def delete_cookies():
    (DATA_DIR / "cookies.txt").unlink(missing_ok=True)
    db.set_settings({"ytdlp_cookies": ""})
    return {"ok": True}


@app.post("/api/brand/logo")
async def upload_logo(file: UploadFile = File(...)):
    ext = Path(file.filename or "logo.png").suffix.lower() or ".png"
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(400, "Format d'image non supporté")
    name = f"logo_{int(time.time())}{ext}"
    with open(BRAND_DIR / name, "wb") as fh:
        shutil.copyfileobj(file.file, fh)
    s = db.get_settings()
    s["brand"]["logo"] = name
    db.set_settings({"brand": s["brand"]})
    return {"logo": name}


@app.delete("/api/brand/logo")
def delete_logo():
    s = db.get_settings()
    s["brand"]["logo"] = ""
    db.set_settings({"brand": s["brand"]})
    return {"ok": True}


@app.get("/media/brand/{name}")
def brand_file(name: str):
    p = (BRAND_DIR / name).resolve()
    if not p.is_relative_to(BRAND_DIR) or not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


# ------------------------------------------------------------------ Projets

@app.get("/api/info")
def info(url: str):
    try:
        s = db.get_settings()
        i = dl.probe(url, s.get("ytdlp_cookies") or None)
        i["kind"] = dl.detect_kind(url)
        return i
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, _friendly(str(e)))


def _friendly(msg: str) -> str:
    low = msg.lower()
    detail = " ".join(msg.replace("ERROR: ", "").split())[:260]
    if "sign in to confirm" in low or "not a bot" in low:
        return ("YouTube bloque le serveur (anti-robot), même après plusieurs tentatives. Solutions : "
                "un lien Twitch (VOD), un fichier cookies.txt dans Réglages > Téléchargement, "
                f"ou « Importer un fichier ». Détail technique : {detail}")
    if "private" in low:
        return "Cette vidéo est privée."
    if "unsupported url" in low:
        return "Lien non reconnu. Colle un lien YouTube, Twitch ou une vidéo publique."
    return msg.replace("ERROR: ", "")[:400]


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    uid = db.new_id()
    ext = Path(file.filename or "video.mp4").suffix.lower() or ".mp4"
    dest = UPLOADS_DIR / f"{uid}{ext}"
    with open(dest, "wb") as fh:
        while chunk := await file.read(8 * 1024 * 1024):
            fh.write(chunk)
    try:
        media = ff.probe(dest)
    except Exception:  # noqa: BLE001
        dest.unlink(missing_ok=True)
        raise HTTPException(400, "Fichier vidéo illisible")
    thumb = UPLOADS_DIR / f"{uid}.jpg"
    try:
        ff.grab_frame(dest, min(media["duration"] * 0.2, 10), thumb, 640)
    except ff.FFmpegError:
        pass
    return {"upload_id": uid, "filename": file.filename, "duration": media["duration"],
            "thumbnail": f"/media/upload/{uid}.jpg", "title": Path(file.filename or "Vidéo").stem}


@app.get("/media/upload/{name}")
def upload_thumb(name: str):
    p = (UPLOADS_DIR / name).resolve()
    if not p.is_relative_to(UPLOADS_DIR) or not p.exists() or p.suffix != ".jpg":
        raise HTTPException(404)
    return FileResponse(p)


@app.post("/api/projects")
async def create_project(request: Request):
    body = await request.json()
    opts = {k: v for k, v in (body.get("options") or {}).items() if k in jobs.DEFAULT_OPTIONS}
    title = body.get("title") or "Nouvelle vidéo"
    if body.get("upload_id"):
        uid = body["upload_id"]
        src = next((f for f in UPLOADS_DIR.glob(f"{uid}.*") if f.suffix != ".jpg"), None)
        if not src:
            raise HTTPException(400, "Fichier introuvable, réimporte-le.")
        rec = db.insert("projects", {"title": title, "source_url": "", "source_kind": "upload",
                                     "status": "queued", "progress": 0, "message": "En file d'attente",
                                     "options": opts, "meta": {"title": title}})
        d = jobs.pdir(rec["id"])
        dl.import_local_file(src, d)
        th = UPLOADS_DIR / f"{uid}.jpg"
        if th.exists():
            shutil.move(str(th), d / "thumb.jpg")
    else:
        url = (body.get("url") or "").strip()
        if not url.startswith("http"):
            raise HTTPException(400, "Lien invalide")
        meta = {k: body.get(k) for k in ("title", "thumbnail", "duration") if body.get(k)}
        rec = db.insert("projects", {"title": title, "source_url": url, "source_kind": dl.detect_kind(url),
                                     "status": "queued", "progress": 0, "message": "En file d'attente",
                                     "options": opts, "meta": meta})
    jobs.enqueue_project(rec["id"])
    return db.get("projects", rec["id"])


def _project_view(p: dict) -> dict:
    d = jobs.pdir(p["id"])
    p["thumb_url"] = f"/media/{p['id']}/thumb.jpg" if (d / "thumb.jpg").exists() else (p.get("meta") or {}).get("thumbnail")
    return p


@app.get("/api/projects")
def list_projects():
    rows = db.query("SELECT p.*, (SELECT COUNT(*) FROM clips c WHERE c.project_id=p.id AND c.status='done') "
                    "AS clip_count FROM projects p ORDER BY created_at DESC")
    return [_project_view(p) for p in rows]


def _clip_view(c: dict) -> dict:
    if c.get("file"):
        v = int((c.get("overrides") or {}).get("_v", 0))
        c["video_url"] = f"/media/{c['project_id']}/clips/{c['file']}?v={v}"
        c["thumb_url"] = f"/media/{c['project_id']}/clips/{c['thumb']}?v={v}" if c.get("thumb") else None
    c["duration"] = (c.get("overrides") or {}).get("_duration") or round(c["end"] - c["start"], 1)
    c["category_label"] = an.CATEGORY_LABELS.get(c.get("category"), "")
    return c


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    p = db.get("projects", pid)
    if not p:
        raise HTTPException(404)
    clips = db.query("SELECT * FROM clips WHERE project_id=? ORDER BY rank", (pid,))
    p = _project_view(p)
    p["clips"] = [_clip_view(c) for c in clips]
    p["options"] = jobs.project_options(p)
    return p


@app.delete("/api/projects/{pid}")
def delete_project(pid: str):
    jobs.delete_project(pid)
    return {"ok": True}


@app.post("/api/projects/{pid}/retry")
def retry_project(pid: str):
    p = db.get("projects", pid)
    if not p:
        raise HTTPException(404)
    db.update("projects", pid, status="queued", error=None, progress=0, message="En file d'attente")
    jobs.enqueue_project(pid)
    return {"ok": True}


@app.post("/api/projects/{pid}/reanalyze")
async def reanalyze(pid: str, request: Request):
    """Relance l'analyse avec d'autres options (sans retélécharger)."""
    p = db.get("projects", pid)
    if not p:
        raise HTTPException(404)
    body = await request.json()
    opts = jobs.project_options(p)
    opts.update({k: v for k, v in (body.get("options") or {}).items() if k in jobs.DEFAULT_OPTIONS})
    if body.get("retranscribe"):
        (jobs.pdir(pid) / "transcript.json").unlink(missing_ok=True)
    db.update("projects", pid, options=opts, status="queued", error=None, progress=0, message="En file d'attente")
    jobs.enqueue_project(pid)
    return {"ok": True}


@app.get("/media/{pid}/{path:path}")
def media(pid: str, path: str):
    base = jobs.pdir(pid).resolve()
    p = (base / path).resolve()
    if not p.is_relative_to(base) or not p.is_file() or p.name.startswith("source"):
        raise HTTPException(404)
    return FileResponse(p, headers={"Cache-Control": "private, max-age=3600"})


# ------------------------------------------------------------------ Clips

@app.patch("/api/clips/{cid}")
async def patch_clip(cid: str, request: Request):
    c = db.get("clips", cid)
    if not c:
        raise HTTPException(404)
    body = await request.json()
    vals = {k: body[k] for k in ("title", "hook", "description", "hashtags") if k in body}
    db.update("clips", cid, **vals)
    return _clip_view(db.get("clips", cid))


@app.post("/api/clips/{cid}/rerender")
async def rerender(cid: str, request: Request):
    c = db.get("clips", cid)
    if not c:
        raise HTTPException(404)
    body = await request.json()
    vals = {k: body[k] for k in ("title", "hook", "description", "hashtags") if k in body}
    p = db.get("projects", c["project_id"])
    dur = ((p.get("meta") or {}).get("media") or {}).get("duration") or c["end"]
    if "start" in body or "end" in body:
        s = max(0.0, float(body.get("start", c["start"])))
        e = min(float(dur), float(body.get("end", c["end"])))
        if e - s < 2:
            raise HTTPException(400, "Le clip doit durer au moins 2 secondes")
        vals.update(start=s, end=e)
    ov = dict(c.get("overrides") or {})
    ov.update({k: v for k, v in (body.get("options") or {}).items() if k in jobs.DEFAULT_OPTIONS})
    ov["_v"] = int(ov.get("_v", 0)) + 1
    vals["overrides"] = ov
    vals["status"] = "queued"
    db.update("clips", cid, **vals)
    jobs.enqueue_clip(cid)
    return _clip_view(db.get("clips", cid))


@app.delete("/api/clips/{cid}")
def delete_clip(cid: str):
    c = db.get("clips", cid)
    if c:
        d = jobs.pdir(c["project_id"]) / "clips"
        for ext in (".mp4", ".jpg", ".srt"):
            (d / f"{cid}{ext}").unlink(missing_ok=True)
        db.query("DELETE FROM posts WHERE clip_id=?", (cid,))
        db.delete("clips", cid)
    return {"ok": True}


@app.get("/api/clips/{cid}/transcript")
def clip_transcript(cid: str):
    c = db.get("clips", cid)
    if not c:
        raise HTTPException(404)
    import json

    tp = jobs.pdir(c["project_id"]) / "transcript.json"
    segs = json.loads(tp.read_text()).get("segments", []) if tp.exists() else []
    return {"words": an.clip_words(segs, c["start"], c["end"]), "start": c["start"], "end": c["end"]}


@app.get("/api/clips/{cid}/download")
def download_clip(cid: str, kind: str = "mp4"):
    c = db.get("clips", cid)
    if not c or not c.get("file"):
        raise HTTPException(404)
    d = jobs.pdir(c["project_id"]) / "clips"
    safe = "".join(ch for ch in (c.get("title") or "clip") if ch.isalnum() or ch in " -_")[:50].strip() or "clip"
    if kind == "srt":
        return FileResponse(d / f"{cid}.srt", filename=f"{safe}.srt", media_type="text/plain")
    return FileResponse(d / c["file"], filename=f"NOXPclips - {safe}.mp4", media_type="video/mp4")


# ------------------------------------------------------------------ Comptes sociaux

_oauth_states: dict[str, tuple[str, float]] = {}


@app.get("/api/accounts")
def accounts():
    rows = db.query("SELECT id, platform, name, avatar, external_id, tokens, created_at FROM accounts "
                    "ORDER BY created_at")
    for r in rows:
        tok = r.pop("tokens") or {}
        r["mode"] = tok.get("mode")
        r["expires_at"] = tok.get("expires_at")
    return rows


@app.patch("/api/accounts/{aid}")
async def patch_account(aid: str, request: Request):
    a = db.get("accounts", aid)
    if not a:
        raise HTTPException(404)
    body = await request.json()
    tok = a.get("tokens") or {}
    if body.get("mode") in ("inbox", "direct"):
        tok["mode"] = body["mode"]
    db.update("accounts", aid, tokens=tok)
    return {"ok": True}


@app.delete("/api/accounts/{aid}")
def delete_account(aid: str):
    db.delete("accounts", aid)
    return {"ok": True}


@app.get("/api/oauth/{platform}/start")
def oauth_start(platform: str, request: Request):
    state = secrets.token_urlsafe(24)
    _oauth_states[state] = (platform, time.time())
    try:
        url = platforms.auth_url(platform, db.get_settings(), base_url(request), state)
    except platforms.PublishError as e:
        return RedirectResponse(f"/#/accounts?error={_q(str(e))}")
    return RedirectResponse(url)


def _q(s: str) -> str:
    import urllib.parse

    return urllib.parse.quote(s[:300])


@app.get("/api/oauth/{platform}/callback")
def oauth_callback(platform: str, request: Request, code: str = "", state: str = "", error: str = "",
                   error_description: str = ""):
    st = _oauth_states.pop(state, None)
    if error:
        return RedirectResponse(f"/#/accounts?error={_q(error_description or error)}")
    if not st or st[0] != platform or time.time() - st[1] > 900:
        return RedirectResponse(f"/#/accounts?error={_q('Session de connexion expirée, réessaie.')}")
    try:
        acc = platforms.exchange_code(platform, db.get_settings(), base_url(request), code)
    except Exception as e:  # noqa: BLE001
        log.warning("OAuth %s : %s", platform, e)
        return RedirectResponse(f"/#/accounts?error={_q(str(e))}")
    return RedirectResponse(f"/#/accounts?connected={_q(acc['name'])}")


# ------------------------------------------------------------------ Publications / calendrier

def _post_view(p: dict) -> dict:
    c = db.get("clips", p["clip_id"])
    if c:
        c = _clip_view(c)
        p["clip"] = {k: c.get(k) for k in ("id", "title", "thumb_url", "video_url", "category", "score",
                                           "project_id", "hashtags", "description", "duration")}
    if p.get("account_id"):
        a = db.get("accounts", p["account_id"])
        p["account_name"] = a["name"] if a else "Compte supprimé"
    return p


@app.get("/api/posts")
def list_posts(start: float = 0, end: float = 0):
    if end:
        rows = db.query("SELECT * FROM posts WHERE scheduled_at BETWEEN ? AND ? ORDER BY scheduled_at",
                        (start, end))
    else:
        rows = db.query("SELECT * FROM posts ORDER BY scheduled_at DESC LIMIT 500")
    return [_post_view(r) for r in rows]


def _make_posts(clip_id: str, targets: list[dict], when: float | None, caption: str, privacy: str) -> list[dict]:
    clip = db.get("clips", clip_id)
    if not clip:
        raise HTTPException(404, "Clip introuvable")
    out = []
    now = time.time()
    for t in targets:
        platform = t.get("platform")
        if platform not in ("youtube", "tiktok", "instagram", "facebook", "x", "other"):
            continue
        acc = t.get("account_id") or None
        if acc and not db.get("accounts", acc):
            acc = None
        ts = float(when) if when else now
        status = "scheduled" if acc else ("reminder" if ts > now else "due")
        out.append(db.insert("posts", {
            "clip_id": clip_id, "platform": platform, "account_id": acc, "scheduled_at": ts,
            "caption": caption or "", "privacy": privacy or "public", "status": status,
        }))
    return out


@app.post("/api/posts")
async def create_posts(request: Request):
    body = await request.json()
    created = _make_posts(body["clip_id"], body.get("targets") or [], body.get("scheduled_at"),
                          body.get("caption", ""), body.get("privacy", "public"))
    if not body.get("scheduled_at"):
        for p in created:
            if p["status"] == "scheduled":
                scheduler.publish_post(p["id"])
    return [_post_view(db.get("posts", p["id"])) for p in created]


@app.post("/api/posts/bulk")
async def bulk_posts(request: Request):
    """Planifie une série : [{clip_id, scheduled_at}] x cibles."""
    body = await request.json()
    created = []
    for item in body.get("items") or []:
        created += _make_posts(item["clip_id"], body.get("targets") or [], item.get("scheduled_at"),
                               item.get("caption", ""), body.get("privacy", "public"))
    return {"count": len(created)}


@app.patch("/api/posts/{post_id}")
async def patch_post(post_id: str, request: Request):
    p = db.get("posts", post_id)
    if not p:
        raise HTTPException(404)
    body = await request.json()
    vals = {}
    if "scheduled_at" in body:
        if p["status"] not in ("scheduled", "reminder", "due", "failed"):
            raise HTTPException(400, "Ce post est déjà publié.")
        vals["scheduled_at"] = float(body["scheduled_at"])
        vals["status"] = "scheduled" if p.get("account_id") else ("reminder" if vals["scheduled_at"] > time.time() else "due")
    for k in ("caption", "privacy"):
        if k in body:
            vals[k] = body[k]
    if body.get("status") == "published" and not p.get("account_id"):
        vals.update(status="published", published_at=time.time())
    db.update("posts", post_id, **vals)
    return _post_view(db.get("posts", post_id))


@app.post("/api/posts/{post_id}/publish")
def publish_now(post_id: str):
    p = db.get("posts", post_id)
    if not p:
        raise HTTPException(404)
    if p["status"] == "failed":
        db.update("posts", post_id, status="scheduled")
    return _post_view(scheduler.publish_post(post_id))


@app.delete("/api/posts/{post_id}")
def delete_post(post_id: str):
    db.delete("posts", post_id)
    return {"ok": True}


@app.get("/api/stats")
def stats():
    def one(sql, params=()):
        r = db.query(sql, params)
        return list(r[0].values())[0] if r else 0

    by_platform = db.query("SELECT platform, status, COUNT(*) AS n FROM posts GROUP BY platform, status")
    by_cat = db.query("SELECT category, COUNT(*) AS n, AVG(score) AS avg FROM clips WHERE status='done' "
                      "GROUP BY category")
    return {
        "projects": one("SELECT COUNT(*) FROM projects"),
        "clips": one("SELECT COUNT(*) FROM clips WHERE status='done'"),
        "avg_score": round(one("SELECT COALESCE(AVG(score),0) FROM clips WHERE status='done'") or 0),
        "published": one("SELECT COUNT(*) FROM posts WHERE status IN ('published','scheduled_on_platform')"),
        "upcoming": one("SELECT COUNT(*) FROM posts WHERE status IN ('scheduled','reminder','scheduled_on_platform') "
                        "AND scheduled_at>?", (time.time(),)),
        "failed": one("SELECT COUNT(*) FROM posts WHERE status='failed'"),
        "by_platform": by_platform,
        "by_category": by_cat,
        "recent": [_post_view(p) for p in db.query(
            "SELECT * FROM posts WHERE status IN ('published','scheduled_on_platform') "
            "ORDER BY COALESCE(published_at, scheduled_at) DESC LIMIT 10")],
    }


# ------------------------------------------------------------------ Interface

@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/sw.js")
def sw():
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript",
                        headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/fonts", StaticFiles(directory=FONTS_DIR), name="fonts")
