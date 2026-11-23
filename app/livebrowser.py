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
IDLE_CLOSE = 12 * 60
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
    def __init__(self, target: str, name: str = ""):
        self.target = target
        self.name = name
        self.q: queue.Queue = queue.Queue()
        self.state = "starting"
        self.message = "Démarrage du navigateur…"
        self.shot = b""
        self.url = ""
        self.logged_in = False
        self.last_use = time.time()
        self.thread = threading.Thread(target=self._run, name="noxp-live", daemon=True)
        self.thread.start()

    # -------- commandes depuis l'API (exécutées dans le fil du navigateur)
    def do(self, fn, timeout: float = 60):
        self.last_use = time.time()
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
                try:
                    self.page.goto(URLS[self.target], wait_until="domcontentloaded", timeout=45_000)
                except Exception as e:  # noqa: BLE001
                    log.warning("Connexion %s : page lente (%s)", self.target, str(e)[:120])
                self.state, self.message = "ready", "Page de connexion ouverte."
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
                    if now - self.last_use > IDLE_CLOSE:
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


def start(target: str, name: str = "") -> dict:
    global _session
    if target not in URLS:
        raise RuntimeError("Réseau inconnu")
    with _lock:
        if ytlogin.running():
            ytlogin.stop()
        old = current()
        if old:
            close(old)
        _session = Session(target, name)
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

        for n in (r"^(Tout accepter|Accepter tout|Accept all|Autoriser tous les cookies|Allow all cookies)$",
                  r"^(Refuser les cookies optionnels|Decline optional cookies)$"):
            try:
                p.get_by_role("button", name=re.compile(n, re.I)).first.click(timeout=1500)
                break
            except Exception:  # noqa: BLE001
                pass

    def run(sess: Session):
        p = sess.page
        dismiss(p)
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
        time.sleep(3)
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


def finish(name: str = "") -> dict:
    """Ferme le navigateur (cookies écrits sur le disque) et enregistre le compte."""
    s = current() or _session
    if not s:
        raise RuntimeError("Aucune connexion en cours.")
    target = s.target
    name = name or s.name
    close(s)
    return ytlogin.finish(target, name)
