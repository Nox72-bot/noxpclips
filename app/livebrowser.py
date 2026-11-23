"""Connexion rapide aux réseaux, directement dans NOXPclips (sans page externe ni téléchargement).

Un navigateur tourne sur le serveur (même profil que le robot de publication). L'utilisateur tape son identifiant
et son mot de passe dans NOXPclips : le robot les saisit sur la vraie page de connexion. La page s'affiche en
direct dans la fenêtre de NOXPclips (captures d'écran rafraîchies) : l'utilisateur peut toucher / glisser sur
l'image (captcha) et taper un code de vérification. Dès que la connexion est détectée, le compte est enregistré.
Le mot de passe n'est ni enregistré ni journalisé : il est seulement saisi dans la page du réseau.
"""
from __future__ import annotations

import logging
import os
import queue
import shutil
import subprocess
import threading
import time

from . import ytlogin

log = logging.getLogger("noxp.live")

DISPLAY = ":96"
VIEW = {"width": 1024, "height": 768}
IDLE_CLOSE = 5 * 60      # libère le navigateur (et la publication) après 5 min sans action
WARM_CLOSE = 3 * 60      # navigateur préchauffé mais pas utilisé
URLS = {
    "tiktok": "https://www.tiktok.com/login/phone-or-email/email",
    "instagram": "https://www.instagram.com/accounts/login/",
    "youtube": "https://accounts.google.com/ServiceLogin?service=youtube&continue=https%3A%2F%2Fwww.youtube.com%2F",
}
SESSION_COOKIES = {
    "tiktok": ("tiktok.com", {"sessionid", "sessionid_ss", "sid_tt"}),
    "instagram": ("instagram.com", {"sessionid"}),
    "youtube": ("google.com", {"SAPISID", "__Secure-3PAPISID", "SID"}),
}
TEST_HOOK = None  # tests : fonction appelée avec le contexte Playwright (pages simulées)


class Session:
    def __init__(self, target: str | None, name: str = ""):
        self.target = target
        self.name = name
        self.q: queue.Queue = queue.Queue()
        self.state = "starting"
        self.message = "Démarrage du navigateur…"
        self.shot = b""
        self.url = ""
        self.logged_in = False
        self.last_use = time.time()
        self.used = target is not None
        self.thread = threading.Thread(target=self._run, name="noxp-live", daemon=True)
        self.thread.start()

    # -------- commandes depuis l'API (exécutées dans le fil du navigateur)
    def do(self, fn, timeout: float = 60):
        self.last_use = time.time()
        self.used = True
        done: queue.Queue = queue.Queue()
        self.q.put((fn, done))
        try:
            ok, val = done.get(timeout=timeout)
        except queue.Empty:
            raise RuntimeError("Le navigateur met trop de temps à répondre.") from None
        if not ok:
            raise val
        return val

    def stop(self):
        self.q.put((None, None))

    # -------- fil du navigateur
    def _run(self):
        xvfb = None
        locked = False
        try:
            if not ytlogin.browser_lock.acquire(timeout=10):
                raise RuntimeError("Une publication automatique est en cours : réessaie dans une minute.")
            locked = True
            chrome = _ensure_browser(self)
            from playwright.sync_api import sync_playwright

            if shutil.which("Xvfb"):
                xvfb = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x900x24", "-nolisten", "tcp"],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                time.sleep(1.2)
            ytlogin.PROFILE.mkdir(parents=True, exist_ok=True)
            for f in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
                (ytlogin.PROFILE / f).unlink(missing_ok=True)
            with sync_playwright() as pw:
                self.ctx = pw.chromium.launch_persistent_context(
                    str(ytlogin.PROFILE), executable_path=chrome, headless=xvfb is None,
                    env={**os.environ, "DISPLAY": DISPLAY} if xvfb else None,
                    args=["--password-store=basic", "--no-sandbox", "--disable-dev-shm-usage", "--lang=fr-FR"],
                    ignore_default_args=["--enable-automation"], viewport=VIEW, locale="fr-FR")
                if TEST_HOOK:
                    TEST_HOOK(self.ctx)
                self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
                self.page.set_default_timeout(20_000)
                if self.target:  # sinon : navigateur préchauffé, la page s'ouvrira au premier clic
                    try:
                        self.page.goto(URLS[self.target], wait_until="domcontentloaded", timeout=45_000)
                    except Exception as e:  # noqa: BLE001
                        log.warning("Connexion %s : page lente (%s)", self.target, str(e)[:120])
                self.state, self.message = "ready", "Page de connexion ouverte." if self.target else "Navigateur prêt."
                last_shot = last_check = 0.0
                while True:
                    try:
                        item = self.q.get(timeout=0.25)
                    except queue.Empty:
                        item = None
                    if item is not None:
                        fn, done = item
                        if fn is None:  # demande d'arrêt
                            break
                        try:
                            done.put((True, fn(self)))
                        except Exception as e:  # noqa: BLE001
                            done.put((False, e))
                        last_shot = 0
                    now = time.time()
                    if now - last_shot > 0.9:
                        try:
                            self.shot = self.page.screenshot(type="jpeg", quality=62)
                            self.url = self.page.url
                        except Exception:  # noqa: BLE001
                            pass
                        last_shot = now
                    if now - last_check > 2.5:
                        self.logged_in = self._check_login()
                        last_check = now
                    if now - self.last_use > (IDLE_CLOSE if self.used else WARM_CLOSE):
                        self.message = "Fermé après 12 minutes sans activité."
                        break
                self.ctx.close()
        except Exception as e:  # noqa: BLE001
            log.exception("Connexion rapide")
            self.state, self.message = "error", str(e)[:300]
        finally:
            if xvfb:
                xvfb.terminate()
            if locked:
                ytlogin.browser_lock.release()
            if self.state != "error":
                self.state = "closed"

    def _check_login(self) -> bool:
        if not self.target:
            return False
        domain, names = SESSION_COOKIES[self.target]
        try:
            return any(c["name"] in names and c["domain"].lstrip(".").endswith(domain) for c in self.ctx.cookies())
        except Exception:  # noqa: BLE001
            return False


def _ensure_browser(s: Session) -> str:
    chrome = ytlogin._chromium()
    if chrome:
        return chrome
    s.message = "Installation du navigateur sur le serveur (1 à 3 min, une seule fois)…"
    s.state = "installing"
    sudo = [] if os.geteuid() == 0 else ["sudo", "-n"]
    env = {**os.environ, "DEBIAN_FRONTEND": "noninteractive"}
    subprocess.run(sudo + ["apt-get", "update", "-qq"], capture_output=True, env=env, timeout=600)
    r = subprocess.run(sudo + ["apt-get", "install", "-y", "-qq", "--no-install-recommends", "chromium", "xvfb"],
                       capture_output=True, text=True, env=env, timeout=1200)
    chrome = ytlogin._chromium()
    if not chrome:
        raise RuntimeError("Installation du navigateur impossible : " + (r.stderr or r.stdout).strip()[-200:])
    s.state = "starting"
    return chrome


# ------------------------------------------------------------------ session unique

_session: Session | None = None
_lock = threading.Lock()


def current() -> Session | None:
    s = _session
    return s if s and s.thread.is_alive() else None


def start(target: str, name: str = "", resume: bool = False) -> dict:
    global _session
    if target not in URLS:
        raise RuntimeError("Réseau inconnu")
    with _lock:
        if ytlogin.running():
            ytlogin.stop()
        s = current()
        if s and s.state in ("starting", "installing"):  # préchauffage en cours : il ouvrira directement ce réseau
            s.target, s.used, s.last_use = target, True, time.time()
            return status()
        if s and s.state == "ready":
            if resume and s.target == target:
                s.last_use = time.time()
                return status()

            def go(sess: Session):
                sess.target, sess.logged_in, sess.shot = target, False, b""
                sess.message = "Page de connexion ouverte."
                try:
                    sess.page.goto(URLS[target], wait_until="domcontentloaded", timeout=45_000)
                except Exception as e:  # noqa: BLE001
                    log.warning("Connexion %s : page lente (%s)", target, str(e)[:120])
                sess.logged_in = sess._check_login()  # déjà connecté (session encore valide) ?
                return True

            s.do(go, timeout=60)
            return status()
        if s:
            close(s)
        _session = Session(target, name)
    return status()


def warm() -> dict:
    """Préchauffe le navigateur (ouverture de la page Connecteurs) : la connexion démarre ensuite sans attente."""
    global _session
    with _lock:
        if not current() and not ytlogin.running() and not ytlogin.browser_lock.locked():
            _session = Session(None)
    return status()


def status() -> dict:
    s = _session
    if not s:
        return {"state": "idle"}
    return {"state": s.state if s.thread.is_alive() or s.state == "error" else "closed", "message": s.message,
            "target": s.target, "url": s.url, "logged_in": s.logged_in, "has_shot": bool(s.shot)}


def screenshot() -> bytes:
    s = current()
    return s.shot if s else b""


def close(s: Session | None = None) -> None:
    s = s or current()
    if not s:
        return
    s.q.put((None, None))
    s.thread.join(timeout=20)


# ------------------------------------------------------------------ actions

def _need() -> Session:
    s = current()
    if not s or s.state not in ("ready",):
        raise RuntimeError("Le navigateur n'est pas prêt.")
    return s


def act(action: dict) -> dict:
    s = _need()
    kind = action.get("type")
    w, h = VIEW["width"], VIEW["height"]

    def run(sess: Session):
        p = sess.page
        if kind == "click":
            p.mouse.click(float(action["x"]) * w, float(action["y"]) * h)
        elif kind == "drag":
            pts = action.get("points") or []
            if len(pts) >= 2:
                p.mouse.move(pts[0][0] * w, pts[0][1] * h)
                p.mouse.down()
                for x, y in pts[1:]:
                    p.mouse.move(x * w, y * h, steps=3)
                p.mouse.up()
        elif kind == "type":
            p.keyboard.type(str(action.get("text") or "")[:500], delay=40)
            if action.get("enter"):
                p.keyboard.press("Enter")
        elif kind == "key":
            key = str(action.get("key") or "")
            if key in ("Enter", "Tab", "Backspace", "Escape", "ArrowDown", "ArrowUp"):
                p.keyboard.press(key)
        elif kind == "scroll":
            p.mouse.wheel(0, float(action.get("dy") or 300))
        elif kind == "back":
            p.go_back()
        elif kind == "reload":
            p.goto(URLS[sess.target], wait_until="domcontentloaded")
        time.sleep(0.6)
        return True

    s.do(run)
    return status()


def autologin(username: str, password: str) -> dict:
    """Saisit identifiant + mot de passe sur la page du réseau (le mot de passe n'est jamais enregistré)."""
    s = _need()
    if not username or not password:
        raise RuntimeError("Identifiant et mot de passe requis.")
    s.name = s.name or username

    def first(p, sels: list[str], timeout=12_000):
        loc = p.locator(", ".join(sels)).first
        loc.wait_for(state="visible", timeout=timeout)
        return loc

    def dismiss(p):
        import re

        try:  # bandeau de cookies, s'il est là (on ne l'attend pas)
            p.get_by_role("button", name=re.compile(
                r"^(Tout accepter|Accepter tout|Accept all|Autoriser tous les cookies|Allow all cookies|"
                r"Refuser les cookies optionnels|Decline optional cookies)$", re.I)).first.click(timeout=600)
        except Exception:  # noqa: BLE001
            pass

    def run(sess: Session):
        p = sess.page
        dismiss(p)
        start_url = p.url
        if sess.target == "youtube":
            first(p, ['input[type="email"]', 'input[name="identifier"]']).fill(username)
            p.keyboard.press("Enter")
            first(p, ['input[type="password"]', 'input[name="Passwd"]'], timeout=25_000).fill(password)
            p.keyboard.press("Enter")
        else:
            first(p, ['input[name="username"]', 'input[autocomplete="username"]', 'input[type="email"]',
                      'input[type="text"]']).fill(username)
            first(p, ['input[type="password"]', 'input[name="password"]']).fill(password)
            try:
                first(p, ['button[data-e2e="login-button"]', 'button[type="submit"]'], timeout=4000).click()
            except Exception:  # noqa: BLE001
                p.keyboard.press("Enter")
        end = time.time() + 10
        while time.time() < end:  # connexion réussie ou page suivante (code, captcha…)
            p.wait_for_timeout(300)
            sess.logged_in = sess._check_login()
            if sess.logged_in or p.url != start_url:
                break
        p.wait_for_timeout(400)
        sess.logged_in = sess._check_login()
        return True

    sess_msg = "Identifiants saisis. Si une vérification apparaît, fais-la sur l'image ci-dessous."
    try:
        s.do(run, timeout=90)
        s.message = sess_msg
    except Exception as e:  # noqa: BLE001
        s.message = ("Je n'ai pas trouvé les champs de connexion automatiquement : touche les champs sur l'image "
                     "et utilise la zone « Taper » pour écrire.")
        log.info("Saisie automatique impossible (%s) : %s", s.target, str(e)[:160])
    return status()


def _write_cookies_txt(cookies: list[dict]) -> int:
    """cookies.txt (format Netscape) pour les téléchargements YouTube, à partir de la session ouverte."""
    from . import db

    keep = [c for c in cookies if c["domain"].lstrip(".").endswith(("youtube.com", "google.com"))]
    lines = ["# Netscape HTTP Cookie File"]
    for c in keep:
        dom = c["domain"]
        exp = int(c.get("expires") or 0)
        lines.append("\t".join([dom, "TRUE" if dom.startswith(".") else "FALSE", c.get("path") or "/",
                                 "TRUE" if c.get("secure") else "FALSE", str(max(exp, 0)), c["name"], c["value"]]))
    ytlogin.COOKIES.write_text("\n".join(lines) + "\n")
    db.set_settings({"ytdlp_cookies": str(ytlogin.COOKIES)})
    return len(keep)


def finish(name: str = "") -> dict:
    """Enregistre le compte connecté. Le navigateur reste ouvert pour connecter le réseau suivant sans attente."""
    from .social.platforms import _save_account

    s = current()
    if not s or not s.target:
        raise RuntimeError("Aucune connexion en cours.")
    labels = {"tiktok": "TikTok", "instagram": "Instagram", "youtube": "YouTube"}

    def run(sess: Session):
        if not sess._check_login():
            raise RuntimeError(f"Tu n'es pas encore connecté à {labels[sess.target]} : termine la connexion sur l'image.")
        extra = {}
        if sess.target == "youtube":
            extra["count"] = _write_cookies_txt(sess.ctx.cookies())
        default = {"tiktok": "Mon compte TikTok", "instagram": "Mon compte Instagram", "youtube": "Ma chaîne YouTube"}
        acc = _save_account(sess.target, "browser", (name or sess.name or default[sess.target])[:60], "",
                            {"method": "browser"})
        sess.last_use = time.time() - IDLE_CLOSE + 90  # se ferme tout seul 90 s après (libère la publication)
        return {"ok": True, "account": acc["name"], **extra}

    return s.do(run, timeout=30)
