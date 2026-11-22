"""Connexion OAuth et publication : YouTube Shorts, TikTok, Instagram Reels.

Tout passe par les API officielles et gratuites des plateformes. Chaque réseau demande
de créer une « application développeur » (gratuite) et d'en copier les identifiants dans
Réglages > Comptes sociaux.
"""
from __future__ import annotations

import math
import time
import urllib.parse
from pathlib import Path

import httpx

from .. import db

GRAPH_VERSION = "v23.0"
TIMEOUT = httpx.Timeout(60, connect=20)


class PublishError(RuntimeError):
    pass


def redirect_uri(base_url: str, platform: str) -> str:
    return f"{base_url.rstrip('/')}/api/oauth/{platform}/callback"


# ------------------------------------------------------------------ OAuth

def auth_url(platform: str, settings: dict, base_url: str, state: str) -> str:
    ru = redirect_uri(base_url, platform)
    if platform == "youtube":
        if not settings.get("youtube_client_id"):
            raise PublishError("Renseigne d'abord le Client ID / Secret Google (YouTube).")
        q = {
            "client_id": settings["youtube_client_id"], "redirect_uri": ru, "response_type": "code",
            "scope": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly",
            "access_type": "offline", "prompt": "consent", "include_granted_scopes": "true", "state": state,
        }
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(q)
    if platform == "tiktok":
        if not settings.get("tiktok_client_key"):
            raise PublishError("Renseigne d'abord le Client Key / Secret TikTok.")
        q = {
            "client_key": settings["tiktok_client_key"], "redirect_uri": ru, "response_type": "code",
            "scope": "user.info.basic,video.upload,video.publish", "state": state,
        }
        return "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(q)
    if platform == "instagram":
        if not settings.get("instagram_app_id"):
            raise PublishError("Renseigne d'abord l'App ID / Secret Instagram.")
        q = {
            "client_id": settings["instagram_app_id"], "redirect_uri": ru, "response_type": "code",
            "scope": "instagram_business_basic,instagram_business_content_publish", "state": state,
        }
        return "https://www.instagram.com/oauth/authorize?" + urllib.parse.urlencode(q)
    raise PublishError("Plateforme inconnue")


def exchange_code(platform: str, settings: dict, base_url: str, code: str) -> dict:
    """Échange le code OAuth, récupère le profil et enregistre le compte."""
    ru = redirect_uri(base_url, platform)
    with httpx.Client(timeout=TIMEOUT) as c:
        if platform == "youtube":
            r = c.post("https://oauth2.googleapis.com/token", data={
                "code": code, "client_id": settings["youtube_client_id"],
                "client_secret": settings["youtube_client_secret"], "redirect_uri": ru,
                "grant_type": "authorization_code"})
            _check(r)
            tok = r.json()
            tok["expires_at"] = time.time() + tok.get("expires_in", 3600) - 60
            me = c.get("https://www.googleapis.com/youtube/v3/channels",
                       params={"part": "snippet", "mine": "true"},
                       headers={"Authorization": f"Bearer {tok['access_token']}"})
            _check(me)
            items = me.json().get("items") or []
            if not items:
                raise PublishError("Aucune chaîne YouTube sur ce compte Google.")
            sn = items[0]["snippet"]
            return _save_account("youtube", items[0]["id"], sn.get("title", "YouTube"),
                                 (sn.get("thumbnails", {}).get("default") or {}).get("url", ""), tok)
        if platform == "tiktok":
            r = c.post("https://open.tiktokapis.com/v2/oauth/token/", data={
                "client_key": settings["tiktok_client_key"], "client_secret": settings["tiktok_client_secret"],
                "code": code, "grant_type": "authorization_code", "redirect_uri": ru},
                headers={"Content-Type": "application/x-www-form-urlencoded"})
            _check(r)
            tok = r.json()
            if "access_token" not in tok:
                raise PublishError(f"TikTok : {tok}")
            tok["expires_at"] = time.time() + tok.get("expires_in", 86400) - 60
            tok["mode"] = "inbox"
            me = c.get("https://open.tiktokapis.com/v2/user/info/",
                       params={"fields": "open_id,avatar_url,display_name"},
                       headers={"Authorization": f"Bearer {tok['access_token']}"})
            u = (me.json().get("data") or {}).get("user") or {}
            return _save_account("tiktok", tok.get("open_id") or u.get("open_id", ""),
                                 u.get("display_name") or "TikTok", u.get("avatar_url", ""), tok)
        if platform == "instagram":
            r = c.post("https://api.instagram.com/oauth/access_token", data={
                "client_id": settings["instagram_app_id"], "client_secret": settings["instagram_app_secret"],
                "grant_type": "authorization_code", "redirect_uri": ru, "code": code.split("#")[0]})
            _check(r)
            short = r.json()
            r2 = c.get("https://graph.instagram.com/access_token", params={
                "grant_type": "ig_exchange_token", "client_secret": settings["instagram_app_secret"],
                "access_token": short["access_token"]})
            _check(r2)
            tok = r2.json()
            tok["expires_at"] = time.time() + tok.get("expires_in", 5184000) - 3600
            me = c.get(f"https://graph.instagram.com/{GRAPH_VERSION}/me",
                       params={"fields": "user_id,username,profile_picture_url", "access_token": tok["access_token"]})
            _check(me)
            u = me.json()
            tok["ig_user_id"] = u.get("user_id") or u.get("id") or short.get("user_id")
            return _save_account("instagram", str(tok["ig_user_id"]), "@" + u.get("username", "instagram"),
                                 u.get("profile_picture_url", ""), tok)
    raise PublishError("Plateforme inconnue")


def _save_account(platform: str, ext_id: str, name: str, avatar: str, tokens: dict) -> dict:
    existing = db.query("SELECT * FROM accounts WHERE platform=? AND external_id=?", (platform, ext_id))
    if existing:
        old = existing[0].get("tokens") or {}
        if platform == "youtube" and "refresh_token" not in tokens and old.get("refresh_token"):
            tokens["refresh_token"] = old["refresh_token"]
        if old.get("mode"):
            tokens["mode"] = old["mode"]
        db.update("accounts", existing[0]["id"], name=name, avatar=avatar, tokens=tokens)
        return db.get("accounts", existing[0]["id"])
    return db.insert("accounts", {"platform": platform, "external_id": ext_id, "name": name,
                                  "avatar": avatar, "tokens": tokens})


def _check(r: httpx.Response) -> None:
    if r.status_code >= 400:
        try:
            detail = r.json()
        except ValueError:
            detail = r.text[:500]
        raise PublishError(f"Erreur {r.status_code} : {detail}")


# ------------------------------------------------------------------ Jetons

def fresh_token(account: dict, settings: dict) -> str:
    tok = dict(account.get("tokens") or {})
    if tok.get("expires_at", 0) > time.time() + 120:
        return tok["access_token"]
    p = account["platform"]
    with httpx.Client(timeout=TIMEOUT) as c:
        if p == "youtube":
            if not tok.get("refresh_token"):
                raise PublishError("Session YouTube expirée : reconnecte le compte.")
            r = c.post("https://oauth2.googleapis.com/token", data={
                "client_id": settings["youtube_client_id"], "client_secret": settings["youtube_client_secret"],
                "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"})
            _check(r)
            new = r.json()
            tok["access_token"] = new["access_token"]
            tok["expires_at"] = time.time() + new.get("expires_in", 3600) - 60
        elif p == "tiktok":
            r = c.post("https://open.tiktokapis.com/v2/oauth/token/", data={
                "client_key": settings["tiktok_client_key"], "client_secret": settings["tiktok_client_secret"],
                "grant_type": "refresh_token", "refresh_token": tok.get("refresh_token", "")},
                headers={"Content-Type": "application/x-www-form-urlencoded"})
            _check(r)
            new = r.json()
            if "access_token" not in new:
                raise PublishError("Session TikTok expirée : reconnecte le compte.")
            tok.update({k: new[k] for k in ("access_token", "refresh_token") if k in new})
            tok["expires_at"] = time.time() + new.get("expires_in", 86400) - 60
        elif p == "instagram":
            r = c.get("https://graph.instagram.com/refresh_access_token",
                      params={"grant_type": "ig_refresh_token", "access_token": tok["access_token"]})
            _check(r)
            new = r.json()
            tok["access_token"] = new["access_token"]
            tok["expires_at"] = time.time() + new.get("expires_in", 5184000) - 3600
    db.update("accounts", account["id"], tokens=tok)
    return tok["access_token"]


# ------------------------------------------------------------------ Publication

def publish(post: dict, clip: dict, account: dict, video: Path, settings: dict) -> dict:
    p = account["platform"]
    token = fresh_token(account, settings)
    if p == "youtube":
        return _youtube(post, clip, token, video)
    if p == "tiktok":
        return _tiktok(post, clip, account, token, video)
    if p == "instagram":
        return _instagram(post, clip, account, token, video)
    raise PublishError("Plateforme inconnue")


def _caption(post: dict, clip: dict) -> str:
    if post.get("caption"):
        return post["caption"]
    tags = " ".join(clip.get("hashtags") or [])
    return f"{clip.get('title', '')}\n\n{clip.get('description', '')}\n\n{tags}".strip()


def _youtube(post: dict, clip: dict, token: str, video: Path) -> dict:
    title = (clip.get("title") or "Short")[:95]
    if "#shorts" not in title.lower():
        title = (title[:90] + " #Shorts")[:100]
    status = {"privacyStatus": post.get("privacy") or "public", "selfDeclaredMadeForKids": False}
    native = post.get("scheduled_at") and post["scheduled_at"] > time.time() + 15 * 60
    if native:
        status["privacyStatus"] = "private"
        status["publishAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(post["scheduled_at"]))
    body = {
        "snippet": {
            "title": title, "description": _caption(post, clip)[:4900],
            "tags": [h.lstrip("#") for h in clip.get("hashtags") or []][:15],
            "categoryId": "20" if any("gaming" in h for h in clip.get("hashtags") or []) else "24",
        },
        "status": status,
    }
    size = video.stat().st_size
    with httpx.Client(timeout=httpx.Timeout(600, connect=30)) as c:
        r = c.post("https://www.googleapis.com/upload/youtube/v3/videos",
                   params={"uploadType": "resumable", "part": "snippet,status"},
                   headers={"Authorization": f"Bearer {token}", "X-Upload-Content-Type": "video/mp4",
                            "X-Upload-Content-Length": str(size)}, json=body)
        _check(r)
        loc = r.headers["Location"]
        with open(video, "rb") as fh:
            r2 = c.put(loc, content=fh.read(), headers={"Content-Type": "video/mp4"})
        _check(r2)
        vid = r2.json()["id"]
    return {"id": vid, "url": f"https://youtube.com/shorts/{vid}",
            "status": "scheduled_on_platform" if native else "published"}


def _tiktok(post: dict, clip: dict, account: dict, token: str, video: Path) -> dict:
    size = video.stat().st_size
    if size <= 64 * 1024 * 1024:
        chunk, count = size, 1
    else:
        chunk = 10 * 1024 * 1024
        count = math.floor(size / chunk)
    source = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": count}
    mode = (account.get("tokens") or {}).get("mode", "inbox")
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}
    base = "https://open.tiktokapis.com/v2/post/publish"
    with httpx.Client(timeout=httpx.Timeout(600, connect=30)) as c:
        if mode == "direct":
            ci = c.post(f"{base}/creator_info/query/", headers=h)
            _check(ci)
            levels = (ci.json().get("data") or {}).get("privacy_level_options") or ["SELF_ONLY"]
            want = {"public": "PUBLIC_TO_EVERYONE", "private": "SELF_ONLY",
                    "unlisted": "MUTUAL_FOLLOW_FRIENDS"}.get(post.get("privacy") or "public", "PUBLIC_TO_EVERYONE")
            privacy = want if want in levels else levels[0]
            body = {"post_info": {"title": _caption(post, clip)[:2200], "privacy_level": privacy,
                                  "disable_duet": False, "disable_comment": False, "disable_stitch": False},
                    "source_info": source}
            r = c.post(f"{base}/video/init/", headers=h, json=body)
        else:
            r = c.post(f"{base}/inbox/video/init/", headers=h, json={"source_info": source})
        _check(r)
        data = r.json().get("data") or {}
        if not data.get("upload_url"):
            raise PublishError(f"TikTok : {r.json().get('error')}")
        with open(video, "rb") as fh:
            for i in range(count):
                start = i * chunk
                end = size - 1 if i == count - 1 else start + chunk - 1
                fh.seek(start)
                part = fh.read(end - start + 1)
                up = c.put(data["upload_url"], content=part, headers={
                    "Content-Type": "video/mp4", "Content-Length": str(len(part)),
                    "Content-Range": f"bytes {start}-{end}/{size}"})
                _check(up)
    note = ("Envoyé dans tes brouillons TikTok : ouvre l'app (notification) pour publier."
            if mode != "direct" else "Publié sur TikTok.")
    return {"id": data.get("publish_id"), "url": "", "status": "published", "note": note}


def _instagram(post: dict, clip: dict, account: dict, token: str, video: Path) -> dict:
    ig = (account.get("tokens") or {}).get("ig_user_id") or account["external_id"]
    base = f"https://graph.instagram.com/{GRAPH_VERSION}"
    size = video.stat().st_size
    with httpx.Client(timeout=httpx.Timeout(600, connect=30)) as c:
        r = c.post(f"{base}/{ig}/media", params={
            "media_type": "REELS", "upload_type": "resumable", "caption": _caption(post, clip)[:2200],
            "share_to_feed": "true", "access_token": token})
        _check(r)
        cont = r.json()
        cid = cont["id"]
        uri = cont.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{GRAPH_VERSION}/{cid}"
        with open(video, "rb") as fh:
            up = c.post(uri, content=fh.read(), headers={
                "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)})
        _check(up)
        for _ in range(90):  # Instagram traite la vidéo (jusqu'à ~5 min)
            st = c.get(f"{base}/{cid}", params={"fields": "status_code,status", "access_token": token})
            _check(st)
            code = st.json().get("status_code")
            if code == "FINISHED":
                break
            if code in ("ERROR", "EXPIRED"):
                raise PublishError(f"Instagram a refusé la vidéo : {st.json().get('status')}")
            time.sleep(4)
        pub = c.post(f"{base}/{ig}/media_publish", params={"creation_id": cid, "access_token": token})
        _check(pub)
        mid = pub.json()["id"]
        link = c.get(f"{base}/{mid}", params={"fields": "permalink", "access_token": token})
        url = link.json().get("permalink", "") if link.status_code == 200 else ""
    return {"id": mid, "url": url, "status": "published"}
