"""Publication automatique par navigateur (YouTube Shorts, TikTok).

Utilise le navigateur où l'utilisateur s'est connecté (Réglages / Comptes > Connexion par navigateur) et
reproduit ce qu'il ferait à la main sur YouTube Studio et TikTok Studio. Avantage : publication en public sans
« audit » des API. Limites : les sites changent leurs pages de temps en temps (il faut alors mettre NOXPclips à
jour) et l'automatisation n'est pas officiellement autorisée par ces réseaux.
En cas d'échec, une capture d'écran est enregistrée pour comprendre ce qui a bloqué.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from .. import ytlogin
from ..config import DATA_DIR

log = logging.getLogger("noxp.browser_post")

SHOTS = DATA_DIR / "browser_shots"
DISPLAY = ":98"  # écran virtuel du robot (distinct de celui de la connexion)


class BrowserBusy(RuntimeError):
    """Le navigateur est utilisé (connexion en cours) : on réessaiera plus tard."""


class PublishError(RuntimeError):
    pass


def _caption(post: dict, clip: dict) -> str:
    if post.get("caption"):
        return post["caption"]
    tags = " ".join(clip.get("hashtags") or [])
    return f"{clip.get('title', '')}\n\n{clip.get('description', '')}\n\n{tags}".strip()


def _start_display() -> subprocess.Popen | None:
    if not shutil.which("Xvfb"):
        return None
    p = subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1280x900x24", "-nolisten", "tcp"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    time.sleep(1.2)
    return p


def _dismiss(page, names: str, timeout: int = 1500) -> None:
    """Ferme les fenêtres gênantes (cookies, astuces…) si elles sont là."""
    try:
        page.get_by_role("button", name=re.compile(names, re.I)).first.click(timeout=timeout)
    except Exception:  # noqa: BLE001
        pass


def _type(page, locator, text: str) -> None:
    locator.click()
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    page.keyboard.insert_text(text)


def publish(post: dict, clip: dict, account: dict, video: Path) -> dict:
    platform = account["platform"]
    if ytlogin.running():
        raise BrowserBusy("Le navigateur de connexion est ouvert : la publication attend qu'il soit fermé.")
    if not ytlogin.browser_lock.acquire(timeout=5):
        raise BrowserBusy("Une autre publication est en cours.")
    xvfb = None
    try:
        from playwright.sync_api import sync_playwright

        chrome = ytlogin._chromium()
        if not chrome:
            raise PublishError("Navigateur absent : refais la « Connexion par navigateur » dans Comptes sociaux.")
        for f in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            (ytlogin.PROFILE / f).unlink(missing_ok=True)
        xvfb = _start_display()
        env = {**os.environ, "DISPLAY": DISPLAY} if xvfb else None
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                str(ytlogin.PROFILE), executable_path=chrome, headless=xvfb is None, env=env,
                args=["--password-store=basic", "--no-sandbox", "--disable-dev-shm-usage", "--lang=fr-FR"],
                ignore_default_args=["--enable-automation"], viewport={"width": 1280, "height": 860},
                locale="fr-FR")
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.set_default_timeout(60_000)
            try:
                if platform == "tiktok":
                    res = _tiktok(page, post, clip, video)
                elif platform == "youtube":
                    res = _youtube(page, post, clip, video)
                elif platform == "instagram":
                    res = _instagram(page, post, clip, video)
                else:
                    raise PublishError("Plateforme non prise en charge par le navigateur")
            except Exception as e:
                shot = _screenshot(page, post)
                msg = str(e).split("Call log:")[0].strip()
                if "Timeout" in msg and not isinstance(e, PublishError):
                    msg = (f"{platform.capitalize()} n'a pas réagi comme prévu (page modifiée, connexion expirée ou "
                           f"réseau lent). Détail : {msg[:160]}")
                raise PublishError(msg[:600] + (f" (capture : {shot})" if shot else "")) from e
            finally:
                ctx.close()
        if platform == "youtube":
            try:  # YouTube renouvelle ses cookies : on garde les téléchargements à jour
                ytlogin.export_youtube_cookies()
            except Exception:  # noqa: BLE001
                pass
        return res
    finally:
        if xvfb:
            xvfb.terminate()
        ytlogin.browser_lock.release()


def _screenshot(page, post: dict) -> str:
    try:
        SHOTS.mkdir(parents=True, exist_ok=True)
        name = f"{post.get('id', 'post')}_{int(time.time())}.png"
        page.screenshot(path=str(SHOTS / name))
        return name
    except Exception:  # noqa: BLE001
        return ""


# ------------------------------------------------------------------ TikTok

def _tiktok(page, post: dict, clip: dict, video: Path) -> dict:
    page.goto("https://www.tiktok.com/tiktokstudio/upload?from=upload", wait_until="domcontentloaded")
    time.sleep(3)
    if "/login" in page.url:
        raise PublishError("TikTok est déconnecté : refais la « Connexion par navigateur » dans Comptes sociaux.")
    _dismiss(page, r"^(Tout accepter|Accepter tout|Accept all|Autoriser tous les cookies|Allow all)")
    page.locator('input[type="file"]').first.set_input_files(str(video), timeout=60_000)
    editor = page.locator('div[contenteditable="true"]').first
    editor.wait_for(state="visible", timeout=180_000)
    _dismiss(page, r"^(Annuler|Cancel|Plus tard|Not now|Compris|Got it|OK)$")
    _type(page, editor, _caption(post, clip)[:2100])
    page.keyboard.press("Escape")  # ferme la liste de suggestions de hashtags
    btn = page.locator('button[data-e2e="post_video_button"]')
    if not btn.count():
        btn = page.get_by_role("button", name=re.compile(r"^(Publier|Post)$", re.I))
    # attendre la fin de l'envoi : le bouton « Publier » devient cliquable
    end = time.time() + 15 * 60
    while time.time() < end:
        try:
            if btn.first.is_enabled() and btn.first.get_attribute("aria-disabled") != "true" \
                    and btn.first.get_attribute("data-disabled") != "true":
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(3)
    else:
        raise PublishError("TikTok n'a pas fini de recevoir la vidéo (15 min).")
    time.sleep(2)
    btn.first.click()
    # fenêtre « Continuer à publier ? » (vérification du contenu)
    _dismiss(page, r"^(Publier maintenant|Post now|Publier quand même|Continuer|Continue)$", timeout=6000)
    try:
        page.wait_for_url(re.compile(r"tiktokstudio/content|/manage|/profile"), timeout=180_000)
    except Exception:  # noqa: BLE001
        body = page.locator("body").inner_text(timeout=5000).lower()
        if not any(k in body for k in ("publiée", "publié", "posted", "your video has been", "en cours de publication")):
            raise PublishError("TikTok n'a pas confirmé la publication.")
    return {"id": "", "url": "", "status": "published", "note": "Publié sur TikTok (navigateur)."}


# ------------------------------------------------------------------ YouTube Shorts

def _youtube(page, post: dict, clip: dict, video: Path) -> dict:
    title = (clip.get("title") or "Short")[:95]
    if "#shorts" not in title.lower():
        title = (title[:90] + " #Shorts")[:100]
    page.goto("https://www.youtube.com/upload", wait_until="domcontentloaded")
    time.sleep(4)
    if "accounts.google.com" in page.url or "ServiceLogin" in page.url:
        raise PublishError("YouTube est déconnecté : refais la « Connexion par navigateur » dans Comptes sociaux.")
    _dismiss(page, r"^(Tout accepter|Accept all)$")
    page.locator('input[type="file"]').first.set_input_files(str(video), timeout=90_000)
    box = page.locator("#title-textarea #textbox")
    box.wait_for(state="visible", timeout=180_000)
    time.sleep(2)
    _type(page, box, title)
    desc = page.locator("#description-textarea #textbox")
    if desc.count():
        _type(page, desc.first, _caption(post, clip)[:4900])
    page.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]').click()
    for _ in range(3):
        page.locator("#next-button").click()
        time.sleep(1.5)
    privacy = (post.get("privacy") or "public").upper()
    page.locator(f'tp-yt-paper-radio-button[name="{privacy if privacy in ("PUBLIC", "UNLISTED", "PRIVATE") else "PUBLIC"}"]').click()
    # attendre la fin de l'envoi (plus de pourcentage affiché)
    end = time.time() + 20 * 60
    while time.time() < end:
        try:
            txt = page.locator("ytcp-video-upload-progress").first.inner_text(timeout=5000)
        except Exception:  # noqa: BLE001
            txt = ""
        if not re.search(r"\d+\s?%", txt):
            break
        time.sleep(4)
    else:
        raise PublishError("YouTube n'a pas fini de recevoir la vidéo (20 min).")
    link = ""
    try:
        link = page.locator("a.ytcp-video-info, #share-url a, a[href*='youtu']").first.get_attribute("href", timeout=10_000) or ""
    except Exception:  # noqa: BLE001
        pass
    page.locator("#done-button").click()
    page.locator("ytcp-video-share-dialog, ytcp-uploads-still-processing-dialog, #close-button").first.wait_for(
        state="visible", timeout=180_000)
    vid = link.rstrip("/").rsplit("/", 1)[-1] if link else ""
    return {"id": vid, "url": f"https://youtube.com/shorts/{vid}" if vid else link, "status": "published",
            "note": "Publié sur YouTube (navigateur)."}


# ------------------------------------------------------------------ Instagram Reels

def _click_button(page, names: str, timeout: int = 30_000) -> None:
    page.get_by_role("button", name=re.compile(names, re.I)).first.click(timeout=timeout)


def _instagram(page, post: dict, clip: dict, video: Path) -> dict:
    page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
    time.sleep(4)
    if "/accounts/login" in page.url:
        raise PublishError("Instagram est déconnecté : refais la connexion dans Connecteurs.")
    _dismiss(page, r"^(Autoriser tous les cookies|Allow all cookies|Tout accepter)$")
    _dismiss(page, r"^(Plus tard|Pas maintenant|Not now)$", timeout=2500)
    # bouton « Créer » du menu, puis « Publication » s'il y a un sous-menu
    page.locator('svg[aria-label="Nouvelle publication"], svg[aria-label="New post"], '
                 'svg[aria-label="Créer"], svg[aria-label="Create"]').first.click(timeout=30_000)
    time.sleep(1.5)
    try:
        page.get_by_role("link", name=re.compile(r"^(Publication|Post)$", re.I)).first.click(timeout=3000)
    except Exception:  # noqa: BLE001
        _dismiss(page, r"^(Publication|Post)$", timeout=2000)
    page.locator('input[type="file"]').first.set_input_files(str(video), timeout=60_000)
    time.sleep(3)
    _dismiss(page, r"^OK$", timeout=4000)  # « Les vidéos sont désormais partagées en tant que reels »
    # recadrage : format d'origine (9:16)
    try:
        page.locator('svg[aria-label="Sélectionner le recadrage"], svg[aria-label="Select crop"]').first.click(timeout=5000)
        page.get_by_role("button", name=re.compile(r"^(Original|Format original|Original size)", re.I)).first.click(timeout=3000)
    except Exception:  # noqa: BLE001
        pass
    for _ in range(2):  # recadrage → retouches → légende
        _click_button(page, r"^(Suivant|Next)$")
        time.sleep(2)
    cap = page.locator('div[aria-label^="Écrivez une légende"], div[aria-label^="Write a caption"], '
                       'div[contenteditable="true"][role="textbox"]').first
    cap.wait_for(state="visible", timeout=60_000)
    _type(page, cap, _caption(post, clip)[:2100])
    _click_button(page, r"^(Partager|Share)$")
    # attendre le message de confirmation (texte affiché uniquement, pas le code de la page)
    page.wait_for_function(
        "re => new RegExp(re, 'i').test(document.body.innerText)",
        arg=r"(reel a été partagé|publication a été partagée|reel has been shared|post has been shared|"
            r"reel partagé|publication partagée)",
        timeout=600_000, polling=2000)
    return {"id": "", "url": "", "status": "published", "note": "Publié sur Instagram (navigateur)."}
