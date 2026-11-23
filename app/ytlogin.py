"""Connexion YouTube depuis l'iPad : un vrai navigateur tourne sur le serveur et s'affiche à distance (noVNC).

YouTube bloque souvent les serveurs (« Sign in to confirm you're not a bot »). La parade fiable est
d'utiliser les cookies d'un compte YouTube connecté. Sur iPad on ne peut pas exporter ses cookies :
on ouvre donc Chromium sur le serveur, l'utilisateur s'y connecte via une page web (noVNC), puis
NOXPclips enregistre les cookies dans cookies.txt pour yt-dlp.
"""
from __future__ import annotations

import logging
import os
import secrets
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path

from . import db
from .config import DATA_DIR

log = logging.getLogger("noxp.ytlogin")

PROFILE = DATA_DIR / "yt-browser"
COOKIES = DATA_DIR / "cookies.txt"
DISPLAY = ":99"
VNC_PORT = 5901
WEB_PORT = int(os.environ.get("NOXP_VNC_PORT", "6080"))
LOGIN_URL = "https://accounts.google.com/ServiceLogin?service=youtube&continue=https%3A%2F%2Fwww.youtube.com%2F"
APT_PACKAGES = ["chromium", "xvfb", "x11vnc", "novnc", "websockify"]
NOVNC_DIRS = ["/usr/share/novnc", "/usr/share/webapps/novnc"]

_state: dict = {"state": "idle", "message": "", "pw": ""}
_procs: dict[str, subprocess.Popen] = {}
_lock = threading.Lock()


def _chromium() -> str | None:
    for c in (os.environ.get("NOXP_CHROMIUM"), "chromium", "chromium-browser", "google-chrome"):
        if c and shutil.which(c):
            return shutil.which(c)
    return None


def _novnc_dir() -> str | None:
    return next((d for d in NOVNC_DIRS if Path(d, "vnc.html").exists()), None)


def _missing() -> list[str]:
    miss = []
    if not _chromium():
        miss.append("chromium")
    for exe, pkg in (("Xvfb", "xvfb"), ("x11vnc", "x11vnc"), ("websockify", "websockify")):
        if not shutil.which(exe):
            miss.append(pkg)
    if not _novnc_dir():
        miss.append("novnc")
    return miss


def viewer_url() -> str:
    """Adresse de la page de connexion (même serveur, port 6080)."""
    name = os.environ.get("CODESPACE_NAME")
    if name:
        dom = os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev")
        base = f"https://{name}-{WEB_PORT}.{dom}"
    else:
        base = ""  # le navigateur complète avec son propre nom d'hôte
    return f"{base}/vnc.html?autoconnect=1&resize=scale&reconnect=1&show_dot=1&password={_state['pw']}"


def status() -> dict:
    s = {k: v for k, v in _state.items() if k != "pw"}
    s["url"] = viewer_url() if s["state"] == "running" else ""
    s["port"] = WEB_PORT
    s["has_cookies"] = bool(db.get_settings().get("ytdlp_cookies")) and COOKIES.exists()
    return s


def _set(state: str, message: str = "") -> None:
    _state.update(state=state, message=message)


def _install(miss: list[str]) -> None:
    _set("installing", "Installation du navigateur sur le serveur (1 à 3 minutes, une seule fois)…")
    sudo = [] if os.geteuid() == 0 else ["sudo", "-n"]
    env = {**os.environ, "DEBIAN_FRONTEND": "noninteractive"}
    subprocess.run(sudo + ["apt-get", "update", "-qq"], capture_output=True, env=env, timeout=600)
    pkgs = [p for p in APT_PACKAGES if p in miss or (p == "websockify" and "novnc" in miss)]
    r = subprocess.run(sudo + ["apt-get", "install", "-y", "-qq", "--no-install-recommends", *pkgs],
                       capture_output=True, text=True, env=env, timeout=1200)
    if r.returncode != 0:
        raise RuntimeError("Installation impossible : " + (r.stderr or r.stdout).strip()[-300:])


def _stop_procs() -> None:
    # Chromium d'abord, proprement, pour qu'il écrive ses cookies sur le disque
    for name in ("chromium", "websockify", "x11vnc", "xvfb"):
        p = _procs.pop(name, None)
        if not p or p.poll() is not None:
            continue
        try:
            os.killpg(p.pid, signal.SIGTERM)
            p.wait(timeout=15)
        except Exception:  # noqa: BLE001
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except Exception:  # noqa: BLE001
                pass


def _spawn(name: str, args: list[str], env: dict | None = None) -> None:
    _procs[name] = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    stdin=subprocess.DEVNULL, env=env, start_new_session=True)


def _run_start() -> None:
    try:
        miss = _missing()
        if miss:
            _install(miss)
            miss = _missing()
            if miss:
                raise RuntimeError("Composants manquants : " + ", ".join(miss))
        _stop_procs()
        PROFILE.mkdir(parents=True, exist_ok=True)
        for f in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            (PROFILE / f).unlink(missing_ok=True)
        _set("starting", "Démarrage du navigateur…")
        _spawn("xvfb", ["Xvfb", DISPLAY, "-screen", "0", "1280x860x24", "-nolisten", "tcp"])
        time.sleep(1.5)
        env = {**os.environ, "DISPLAY": DISPLAY}
        _spawn("chromium", [_chromium(), f"--user-data-dir={PROFILE}", "--no-first-run", "--no-default-browser-check",
                            "--password-store=basic", "--no-sandbox", "--disable-dev-shm-usage", "--start-maximized",
                            "--window-position=0,0", "--window-size=1280,860", "--lang=fr-FR", LOGIN_URL], env)
        _state["pw"] = secrets.token_hex(4)  # mot de passe VNC propre à cette session (8 caractères max)
        _spawn("x11vnc", ["x11vnc", "-display", DISPLAY, "-forever", "-shared", "-passwd", _state["pw"], "-localhost",
                          "-rfbport", str(VNC_PORT), "-quiet"])
        time.sleep(1.5)
        _spawn("websockify", ["websockify", "--web", _novnc_dir(), str(WEB_PORT), f"localhost:{VNC_PORT}"])
        time.sleep(1.5)
        dead = [n for n, p in _procs.items() if p.poll() is not None]
        if dead:
            raise RuntimeError("Le programme suivant n'a pas démarré : " + ", ".join(dead))
        _set("running", "Navigateur prêt : connecte-toi à YouTube.")
    except Exception as e:  # noqa: BLE001
        log.exception("Connexion YouTube : démarrage impossible")
        _stop_procs()
        _set("error", str(e)[:400])


def start() -> dict:
    with _lock:
        if _state["state"] in ("installing", "starting"):
            return status()
        if _state["state"] == "running" and all(p.poll() is None for p in _procs.values()):
            return status()
        _set("starting", "Préparation…")
        threading.Thread(target=_run_start, daemon=True).start()
    return status()


def finish() -> dict:
    """Ferme le navigateur, enregistre les cookies YouTube dans cookies.txt."""
    with _lock:
        _stop_procs()
        _set("idle")
        from yt_dlp.cookies import extract_cookies_from_browser

        jar = extract_cookies_from_browser("chromium", str(PROFILE), keyring="BASICTEXT")
        keep = [c for c in jar if c.domain.lstrip(".").endswith(("youtube.com", "google.com"))]
        names = {c.name for c in keep}
        if not names & {"SAPISID", "__Secure-3PAPISID", "__Secure-3PSID", "SID", "LOGIN_INFO"}:
            raise RuntimeError("Aucune connexion YouTube trouvée : relance la connexion et va jusqu'à la page "
                               "d'accueil de YouTube avec ton compte avant d'appuyer sur « J'ai terminé ».")
        from yt_dlp.cookies import YoutubeDLCookieJar

        out = YoutubeDLCookieJar(str(COOKIES))
        for c in keep:
            if c.expires and c.expires > 10**12:  # format Chrome (µs depuis 1601) → secondes Unix
                c.expires = int(c.expires / 1_000_000 - 11_644_473_600)
            out.set_cookie(c)
        out.save(ignore_discard=True, ignore_expires=True)
        db.set_settings({"ytdlp_cookies": str(COOKIES)})
        return {"ok": True, "count": len(keep)}


def stop() -> dict:
    with _lock:
        _stop_procs()
        _set("idle")
    return status()
