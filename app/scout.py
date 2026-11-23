"""Bot d'inspiration TikTok : il scrolle TikTok, repère les vidéos qui cartonnent et te suggère quoi en tirer.

Il NE republie RIEN : il lit le fil « Pour toi » et les pages des hashtags de ta niche dans un navigateur séparé
(non connecté à ton compte, donc sans risque pour lui), relève les statistiques que TikTok envoie à la page
(vues, likes, commentaires, partages, enregistrements, abonnés de l'auteur), calcule un score « ça marche »
et demande à l'IA pourquoi la vidéo fonctionne et quelle idée similaire tu pourrais faire.
"""
from __future__ import annotations

import json
import logging
import math
import os
import random
import re
import shutil
import subprocess
import threading
import time

from . import db, ytlogin
from .config import DATA_DIR
from .pipeline import llm

log = logging.getLogger("noxp.scout")

PROFILE = DATA_DIR / "scout-browser"
STORE = DATA_DIR / "scout.json"
COVERS = DATA_DIR / "scout_covers"
DISPLAY = ":97"
KEEP = 300

DEFAULT_TAGS = {
    "gta": "gta6, gtarp, gta5, gtaonline",
    "concept": "squeezie, concept, challenge, humour",
    "gaming": "gaming, twitchfr, streamer, clip",
}

_state: dict = {"state": "idle", "message": "", "progress": 0.0}
_lock = threading.Lock()


# ------------------------------------------------------------------ stockage

def load() -> dict:
    try:
        return json.loads(STORE.read_text())
    except (OSError, ValueError):
        return {"items": {}, "dismissed": [], "last_run": 0, "runs": []}


def save(data: dict) -> None:
    items = sorted(data["items"].values(), key=lambda i: i.get("seen_at", 0), reverse=True)[:KEEP]
    data["items"] = {i["id"]: i for i in items}
    data["dismissed"] = data.get("dismissed", [])[-1000:]
    STORE.write_text(json.dumps(data, ensure_ascii=False))


def status() -> dict:
    return dict(_state)


def niche_tags(settings: dict) -> list[str]:
    raw = settings.get("scout_tags") or DEFAULT_TAGS["gta"]
    return [t.strip().lstrip("#").lower() for t in re.split(r"[,\s]+", raw) if t.strip()][:8]


# ------------------------------------------------------------------ lecture des données TikTok

def _num(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def parse_item(it: dict, source: str) -> dict | None:
    """Une vidéo telle que TikTok l'envoie à sa page web → fiche simplifiée."""
    if not isinstance(it, dict) or not it.get("id"):
        return None
    st = it.get("stats") or {}
    st2 = it.get("statsV2") or {}
    stat = lambda k: max(_num(st.get(k)), _num(st2.get(k)))  # noqa: E731
    author = it.get("author") or {}
    vid = it.get("video") or {}
    tags = [t.get("hashtagName") for t in it.get("textExtra") or [] if isinstance(t, dict) and t.get("hashtagName")]
    tags += [c.get("title") for c in it.get("challenges") or [] if isinstance(c, dict) and c.get("title")]
    uid = author.get("uniqueId") or ""
    return {
        "id": str(it["id"]),
        "url": f"https://www.tiktok.com/@{uid}/video/{it['id']}" if uid else f"https://www.tiktok.com/video/{it['id']}",
        "desc": (it.get("desc") or "")[:400],
        "author": uid, "author_name": author.get("nickname") or uid,
        "followers": _num((it.get("authorStats") or {}).get("followerCount")),
        "created": _num(it.get("createTime")),
        "duration": _num(vid.get("duration")),
        "cover_src": vid.get("cover") or vid.get("originCover") or vid.get("dynamicCover") or "",
        "music": ((it.get("music") or {}).get("title") or "")[:80],
        "plays": stat("playCount"), "likes": stat("diggCount"), "comments": stat("commentCount"),
        "shares": stat("shareCount"), "saves": stat("collectCount"),
        "tags": list(dict.fromkeys(t.lower() for t in tags))[:12],
        "source": source,
    }


def extract_items(payload, source: str) -> list[dict]:
    """Trouve les listes de vidéos dans une réponse JSON de TikTok (fil, hashtag, recherche…)."""
    found: list[dict] = []

    def walk(o, depth=0):
        if depth > 8:
            return
        if isinstance(o, dict):
            if "stats" in o and "id" in o and ("video" in o or "author" in o):
                p = parse_item(o, source)
                if p:
                    found.append(p)
                return
            for v in o.values():
                if isinstance(v, (dict, list)):
                    walk(v, depth + 1)
        elif isinstance(o, list):
            for x in o:
                walk(x, depth + 1)

    walk(payload)
    return found


# ------------------------------------------------------------------ score « ça marche »

def score(i: dict, now: float | None = None) -> dict:
    now = now or time.time()
    plays = max(i["plays"], 1)
    age_h = max(1.0, (now - i["created"]) / 3600) if i.get("created") else 24 * 7
    er = (i["likes"] + 2 * i["comments"] + 3 * i["shares"] + 2 * i["saves"]) / plays
    velocity = i["plays"] / age_h
    over = i["plays"] / max(i.get("followers") or 0, 1000)
    v = min(1.0, math.log10(velocity + 1) / 5)          # 100 000 vues / heure → max
    e = min(1.0, er / 0.15)                                # 15 % d'engagement pondéré → max
    o = min(1.0, math.log10(over + 1) / 2)                 # 100× ses abonnés → max
    s = round(100 * (0.4 * v + 0.35 * e + 0.25 * o))
    return {"score": s, "er": round(er * 100, 1), "velocity": int(velocity), "over": round(over, 1),
            "age_h": int(age_h), "share_rate": round(100 * i["shares"] / plays, 2)}


def is_niche(i: dict, tags: list[str]) -> bool:
    if i.get("source", "").startswith("#"):
        return True
    hay = " ".join([i.get("desc", ""), " ".join(i.get("tags", []))]).lower()
    return any(t in hay for t in tags)


# ------------------------------------------------------------------ analyse IA

ANALYZE_SYSTEM = """Tu es un stratège TikTok pour un créateur francophone (niche : __NICHE__).
Pour chaque vidéo virale fournie (description, hashtags, durée, son, statistiques), explique en français :
- why : pourquoi elle marche (accroche, format, émotion, tendance, son…) en 1-2 phrases concrètes ;
- idea : une idée de clip SIMILAIRE mais ORIGINALE que le créateur peut faire avec SES propres vidéos / streams
  (jamais reprendre la vidéo des autres) ;
- hook : une accroche à afficher à l'écran (max 7 mots, MAJUSCULES) ;
- format : le format en 3-5 mots (ex. « réaction + zoom », « fail en 3 s »).
Réponds UNIQUEMENT en JSON : {"videos":[{"id":"..","why":"..","idea":"..","hook":"..","format":".."}]}"""


def _fallback_text(i: dict, m: dict) -> dict:
    why = []
    if m["share_rate"] >= 1:
        why.append(f"énormément partagée ({m['share_rate']} % des vues)")
    if m["over"] >= 10:
        why.append(f"{m['over']:.0f}× plus de vues que d'abonnés : l'algorithme la pousse")
    if m["velocity"] >= 5000:
        why.append(f"{m['velocity']:,} vues par heure".replace(",", " "))
    if i["duration"] and i["duration"] <= 20:
        why.append(f"très courte ({i['duration']} s) : revue en boucle")
    return {"why": ("Ça marche : " + ", ".join(why) + ".") if why else "Bon engagement pour sa taille.",
            "idea": "Cherche dans tes streams un moment avec la même émotion et la même accroche dès la 1re seconde.",
            "hook": "", "format": ""}


def analyze(items: list[dict], settings: dict, niche: str) -> None:
    engine = llm.available_engine(settings)
    todo = [i for i in items if not i.get("why")]
    if engine == "heuristic" or not todo:
        for i in todo:
            i.update(_fallback_text(i, i["metrics"]))
        return
    system = ANALYZE_SYSTEM.replace("__NICHE__", niche)
    for k in range(0, len(todo), 10):
        chunk = todo[k:k + 10]
        user = json.dumps([{"id": i["id"], "description": i["desc"], "hashtags": i["tags"], "duree_s": i["duration"],
                            "son": i["music"], "vues": i["plays"], "likes": i["likes"], "partages": i["shares"],
                            "commentaires": i["comments"], "abonnes_auteur": i["followers"],
                            "age_heures": i["metrics"]["age_h"]} for i in chunk], ensure_ascii=False)
        try:
            data = llm.parse_json(llm.chat(settings, system, user, engine=engine))
            res = {str(v.get("id")): v for v in (data.get("videos") if isinstance(data, dict) else data) or []
                   if isinstance(v, dict)}
        except Exception as e:  # noqa: BLE001
            log.warning("Analyse IA des vidéos TikTok impossible : %s", e)
            res = {}
        for i in chunk:
            r = res.get(i["id"]) or {}
            fb = _fallback_text(i, i["metrics"])
            i.update({k2: str(r.get(k2) or fb[k2])[:300] for k2 in ("why", "idea", "hook", "format")})


def match_my_clips(i: dict) -> dict | None:
    """Un de tes clips existants qui colle à cette vidéo (mots en commun)."""
    words = {w for w in re.findall(r"[a-zà-ÿ0-9]{4,}", (i.get("desc", "") + " " + " ".join(i.get("tags", []))).lower())}
    words -= {"pour", "avec", "dans", "this", "that", "fyp", "foryou", "pourtoi", "viral", "tiktok"}
    if not words:
        return None
    best, best_n = None, 1
    for c in db.query("SELECT id, project_id, title, transcript, hashtags FROM clips WHERE status='done' "
                      "ORDER BY created_at DESC LIMIT 300"):
        hay = f"{c.get('title') or ''} {c.get('transcript') or ''} {' '.join(c.get('hashtags') or [])}".lower()
        n = sum(1 for w in words if w in hay)
        if n > best_n:
            best, best_n = c, n
    return {"id": best["id"], "project_id": best["project_id"], "title": best["title"]} if best else None


# ------------------------------------------------------------------ le bot

def _dismiss(page) -> None:
    for name in (r"^(Tout accepter|Accepter tout|Accept all|Autoriser tous les cookies|Allow all)",
                 r"(Continuer en tant qu'invité|Continue as guest|Pas maintenant|Not now)"):
        try:
            page.get_by_role("button", name=re.compile(name, re.I)).first.click(timeout=1200)
        except Exception:  # noqa: BLE001
            pass
    try:
        page.keyboard.press("Escape")
    except Exception:  # noqa: BLE001
        pass


def _scroll(page, kind: str, seconds: float, stop) -> None:
    end = time.time() + seconds
    while time.time() < end and not stop():
        if kind == "foryou":
            page.keyboard.press("ArrowDown")
        else:
            page.mouse.wheel(0, random.randint(1400, 2600))
        time.sleep(random.uniform(2.2, 4.5))  # rythme humain


def _run(settings: dict) -> None:
    from playwright.sync_api import sync_playwright

    data = load()
    tags = niche_tags(settings)
    per_source = max(30, min(240, int(settings.get("scout_seconds") or 75)))
    sources = [("Pour toi", "https://www.tiktok.com/foryou", "foryou")]
    sources += [(f"#{t}", f"https://www.tiktok.com/tag/{t}", "tag") for t in tags[:4]]
    collected: dict[str, dict] = {}
    xvfb = None
    if not ytlogin.browser_lock.acquire(timeout=10):
        raise RuntimeError("Une publication automatique est en cours : réessaie dans quelques minutes.")
    try:
        chrome = ytlogin._chromium()
        if not chrome:
            raise RuntimeError("Navigateur absent : connecte d'abord YouTube ou TikTok une fois (Comptes sociaux), "
                               "ça l'installe sur le serveur.")
        if shutil.which("Xvfb"):
            xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x900x24", "-nolisten", "tcp"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            time.sleep(1.2)
        PROFILE.mkdir(parents=True, exist_ok=True)
        for f in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            (PROFILE / f).unlink(missing_ok=True)
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                str(PROFILE), executable_path=chrome, headless=xvfb is None,
                env={**os.environ, "DISPLAY": DISPLAY} if xvfb else None,
                args=["--password-store=basic", "--no-sandbox", "--disable-dev-shm-usage", "--lang=fr-FR", "--mute-audio"],
                ignore_default_args=["--enable-automation"], viewport={"width": 1280, "height": 860}, locale="fr-FR")
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            current = {"src": ""}

            def on_response(resp):
                u = resp.url
                if "tiktok.com/api/" not in u or not any(k in u for k in ("item_list", "search", "recommend", "related")):
                    return
                try:
                    for it in extract_items(resp.json(), current["src"]):
                        collected.setdefault(it["id"], it)
                except Exception:  # noqa: BLE001
                    pass

            page.on("response", on_response)
            for n, (label, url, kind) in enumerate(sources):
                current["src"] = label
                _state.update(message=f"Scroll de {label}… ({len(collected)} vidéos vues)", progress=n / (len(sources) + 1))
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                    time.sleep(4)
                    _dismiss(page)
                    # vidéos déjà présentes dans la page (avant tout scroll)
                    try:
                        raw = page.locator("#__UNIVERSAL_DATA_FOR_REHYDRATION__, #SIGI_STATE").first.text_content(timeout=3000)
                        for it in extract_items(json.loads(raw or "{}"), label):
                            collected.setdefault(it["id"], it)
                    except Exception:  # noqa: BLE001
                        pass
                    if kind == "foryou":
                        try:
                            page.locator("video").first.click(timeout=3000)
                            page.keyboard.press("Space")  # met en pause, on garde le focus pour les flèches
                        except Exception:  # noqa: BLE001
                            pass
                    _scroll(page, kind, per_source, lambda: _state.get("cancel"))
                except Exception as e:  # noqa: BLE001
                    log.warning("Bot TikTok : %s inaccessible (%s)", label, str(e)[:120])
                if _state.get("cancel"):
                    break
            # miniatures (les liens TikTok expirent vite : on les garde en local)
            COVERS.mkdir(parents=True, exist_ok=True)
            ranked = sorted(collected.values(), key=lambda i: score(i)["score"], reverse=True)[:40]
            for it in ranked:
                dest = COVERS / f"{it['id']}.jpg"
                if it.get("cover_src") and not dest.exists():
                    try:
                        r = ctx.request.get(it["cover_src"], timeout=15_000)
                        if r.ok:
                            dest.write_bytes(r.body())
                    except Exception:  # noqa: BLE001
                        pass
            ctx.close()
    finally:
        if xvfb:
            xvfb.terminate()
        ytlogin.browser_lock.release()

    _state.update(message="Analyse des vidéos qui marchent…", progress=0.9)
    now = time.time()
    new = []
    for it in collected.values():
        it["metrics"] = score(it, now)
        it["niche"] = is_niche(it, tags)
        it["seen_at"] = now
        old = data["items"].get(it["id"])
        if old:  # on garde l'analyse déjà faite, on met à jour les chiffres
            it.update({k: old[k] for k in ("why", "idea", "hook", "format") if old.get(k)})
        data["items"][it["id"]] = it
        new.append(it)
    good = [i for i in new if i["plays"] >= int(settings.get("scout_min_views") or 20000)
            and i["metrics"]["age_h"] <= 24 * 30 and i["id"] not in data["dismissed"]]
    good.sort(key=lambda i: (i["niche"], i["metrics"]["score"]), reverse=True)
    analyze(good[:20], settings, ", ".join("#" + t for t in tags))
    for i in good[:20]:
        i["my_clip"] = match_my_clips(i)
    data["last_run"] = now
    data.setdefault("runs", []).append({"at": now, "seen": len(collected), "good": len(good)})
    data["runs"] = data["runs"][-30:]
    save(data)
    if not collected:
        raise RuntimeError("TikTok n'a renvoyé aucune vidéo (page bloquée ou modifiée). Réessaie plus tard ; "
                           "si ça persiste, envoie une capture à ton développeur.")
    _state.update(message=f"{len(collected)} vidéos regardées, {len(good)} qui cartonnent.", progress=1.0)


def run_async(settings: dict | None = None) -> dict:
    with _lock:
        if _state["state"] == "running":
            return status()
        if ytlogin.running():
            raise RuntimeError("Le navigateur de connexion est ouvert : ferme-le avant de lancer le bot.")
        _state.update(state="running", message="Démarrage du bot…", progress=0.0, cancel=False)

    def work():
        try:
            _run(settings or db.get_settings())
            _state["state"] = "done"
        except Exception as e:  # noqa: BLE001
            log.exception("Bot TikTok")
            _state.update(state="error", message=str(e)[:300])

    threading.Thread(target=work, name="noxp-scout", daemon=True).start()
    return status()


def cancel() -> None:
    _state["cancel"] = True


def maybe_auto_run() -> None:
    """Appelé par le planificateur : un passage par jour si l'option est activée."""
    s = db.get_settings()
    if not s.get("scout_auto") or _state["state"] == "running" or ytlogin.running():
        return
    if time.time() - load().get("last_run", 0) > 20 * 3600:
        try:
            run_async(s)
        except RuntimeError:
            pass


def listing(niche_only: bool = True, limit: int = 60) -> list[dict]:
    data = load()
    s = db.get_settings()
    min_views = int(s.get("scout_min_views") or 20000)
    out = [i for i in data["items"].values() if i["id"] not in data["dismissed"] and i["plays"] >= min_views
           and (not niche_only or i.get("niche"))]
    out.sort(key=lambda i: i["metrics"]["score"], reverse=True)
    for i in out:
        i["cover"] = f"/api/scout/cover/{i['id']}" if (COVERS / f"{i['id']}.jpg").exists() else ""
    return out[:limit]


def dismiss(item_id: str) -> None:
    data = load()
    if item_id not in data["dismissed"]:
        data["dismissed"].append(item_id)
    save(data)
