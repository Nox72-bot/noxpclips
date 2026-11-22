"""Téléchargement des vidéos (YouTube, lives YouTube, Twitch VOD/clips, etc.) + chat."""
from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Callable

import httpx

log = logging.getLogger("noxp.download")

TWITCH_GQL = "https://gql.twitch.tv/gql"
# Client-ID public utilisé par le lecteur web de Twitch (aucun compte requis).
TWITCH_PUBLIC_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"


def detect_kind(url: str) -> str:
    u = url.lower()
    if "twitch.tv" in u:
        if "/clip/" in u or "clips.twitch.tv" in u:
            return "twitch_clip"
        if "/videos/" in u:
            return "twitch_vod"
        return "twitch_live"
    if "youtube.com" in u or "youtu.be" in u:
        if "/live/" in u:
            return "youtube_live"
        if "/shorts/" in u:
            return "youtube_short"
        return "youtube"
    return "other"


def _base_opts(cookies: str | None) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "retries": 5,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 4,
    }
    if cookies and Path(cookies).exists():
        opts["cookiefile"] = cookies
    return opts


def probe(url: str, cookies: str | None = None) -> dict:
    """Infos rapides sans télécharger (titre, durée, miniature, live ?)."""
    import yt_dlp

    with yt_dlp.YoutubeDL({**_base_opts(cookies), "skip_download": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    return {
        "title": info.get("title") or "Vidéo",
        "duration": info.get("duration") or 0,
        "thumbnail": info.get("thumbnail"),
        "uploader": info.get("uploader") or info.get("channel"),
        "is_live": bool(info.get("is_live")),
        "was_live": info.get("live_status") in ("was_live", "post_live"),
        "id": info.get("id"),
        "extractor": info.get("extractor_key"),
        "tags": (info.get("tags") or [])[:15],
        "language": info.get("language"),
        "has_live_chat": "live_chat" in (info.get("subtitles") or {}),
    }


def download(
    url: str,
    out_dir: Path,
    *,
    start: float | None = None,
    end: float | None = None,
    cookies: str | None = None,
    progress: Callable[[float, str], None] | None = None,
) -> dict:
    """Télécharge la vidéo en mp4 (≤1080p). Retourne {path, info, chat_path}."""
    import yt_dlp
    from yt_dlp.utils import download_range_func

    out_dir.mkdir(parents=True, exist_ok=True)

    def hook(d):
        if progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            frac = (done / total) if total else 0
            speed = d.get("_speed_str", "").strip()
            progress(min(frac, 0.99), f"Téléchargement… {speed}")

    opts = {
        **_base_opts(cookies),
        "format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b",
        "merge_output_format": "mp4",
        "outtmpl": str(out_dir / "source.%(ext)s"),
        "progress_hooks": [hook],
        "writesubtitles": True,
        "subtitleslangs": ["live_chat"],
        "overwrites": True,
    }

    info0 = probe(url, cookies)
    if info0["is_live"]:
        if start is None or end is None:
            raise RuntimeError(
                "Ce live est encore en cours. Attends la fin du live (rediffusion) "
                "ou choisis une plage précise (début/fin) à analyser."
            )
        opts["live_from_start"] = True
    if start is not None or end is not None:
        s = float(start or 0)
        e = float(end) if end else float(info0.get("duration") or 10**7)
        opts["download_ranges"] = download_range_func(None, [(s, e)])
        opts["force_keyframes_at_cuts"] = True

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

    path = None
    for cand in sorted(out_dir.glob("source.*")):
        if cand.suffix in (".mp4", ".mkv", ".webm", ".mov"):
            path = cand
            break
    if path is None:
        raise RuntimeError("Le téléchargement n'a produit aucun fichier vidéo.")
    if path.suffix != ".mp4":
        mp4 = out_dir / "source.mp4"
        from .ffmpeg import run_ffmpeg

        run_ffmpeg(["-i", str(path), "-c", "copy", str(mp4)])
        path.unlink(missing_ok=True)
        path = mp4

    chat_path = None
    offset = float(start or 0)
    # Chat YouTube (rediffusion de live)
    yt_chat = next(iter(out_dir.glob("*.live_chat.json")), None)
    if yt_chat:
        msgs = parse_youtube_live_chat(yt_chat, offset)
        if msgs:
            chat_path = out_dir / "chat.json"
            chat_path.write_text(json.dumps(msgs))
    # Chat Twitch (VOD)
    if chat_path is None and detect_kind(url) == "twitch_vod":
        try:
            if progress:
                progress(0.99, "Récupération du chat Twitch…")
            msgs = fetch_twitch_chat(info.get("id") or "", start, end)
            if msgs:
                chat_path = out_dir / "chat.json"
                chat_path.write_text(json.dumps(msgs))
        except Exception as e:  # le chat est un bonus, jamais bloquant
            log.warning("Chat Twitch indisponible: %s", e)

    # « Moments les plus revus » (YouTube) : vraie donnée d'audience
    heat = []
    for h in info.get("heatmap") or []:
        try:
            a, b = float(h["start_time"]) - offset, float(h["end_time"]) - offset
            if b > 0:
                heat.append({"start_time": max(0.0, a), "end_time": b, "value": float(h.get("value") or 0)})
        except (KeyError, TypeError, ValueError):
            continue
    if heat:
        (out_dir / "heatmap.json").write_text(json.dumps(heat))
    # Commentaires horodatés (« 4:32 mdr ») — vidéos YouTube classiques
    kind = detect_kind(url)
    if kind in ("youtube", "youtube_live") and not info0["is_live"]:
        try:
            if progress:
                progress(0.99, "Lecture des commentaires horodatés…")
            coms = fetch_timestamp_comments(url, cookies, offset)
            if coms:
                (out_dir / "comments.json").write_text(json.dumps(coms, ensure_ascii=False))
        except Exception as e:  # bonus, jamais bloquant
            log.warning("Commentaires indisponibles : %s", e)

    meta = {
        "title": info.get("title") or info0["title"],
        "duration": info.get("duration") or info0["duration"],
        "thumbnail": info.get("thumbnail") or info0["thumbnail"],
        "uploader": info.get("uploader") or info0["uploader"],
        "tags": info0["tags"],
        "language": info.get("language"),
        "range_offset": offset,
        "heatmap": bool(heat),
    }
    return {"path": path, "info": meta, "chat_path": chat_path}


TS_RE = re.compile(r"(?<![\d:])(?:(\d{1,2}):)?([0-5]?\d):([0-5]\d)(?![\d:])")


def fetch_timestamp_comments(url: str, cookies: str | None, offset: float = 0.0, max_comments: int = 400) -> list[dict]:
    """Commentaires populaires contenant un horodatage -> [{t, likes, text}]."""
    import yt_dlp

    opts = {
        **_base_opts(cookies), "skip_download": True, "getcomments": True,
        "extractor_args": {"youtube": {"max_comments": [str(max_comments), str(max_comments), "0", "0"],
                                       "comment_sort": ["top"]}},
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    out = []
    for c in info.get("comments") or []:
        text = c.get("text") or ""
        for m in TS_RE.finditer(text):
            h, mm, ss = int(m.group(1) or 0), int(m.group(2)), int(m.group(3))
            t = h * 3600 + mm * 60 + ss - offset
            if t >= 0:
                out.append({"t": t, "likes": int(c.get("like_count") or 0), "text": text[:200]})
    return out


def parse_youtube_live_chat(path: Path, offset: float = 0.0) -> list[dict]:
    """Convertit le .live_chat.json (JSON lines) de yt-dlp en [{t, m}]."""
    msgs = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        act = obj.get("replayChatItemAction") or {}
        try:
            t = int(act.get("videoOffsetTimeMsec", 0)) / 1000.0
        except (TypeError, ValueError):
            continue
        for a in act.get("actions", []):
            item = (a.get("addChatItemAction") or {}).get("item") or {}
            r = item.get("liveChatTextMessageRenderer") or item.get("liveChatPaidMessageRenderer")
            if not r:
                continue
            runs = (r.get("message") or {}).get("runs") or []
            text = "".join(
                x.get("text")
                or ((x.get("emoji") or {}).get("shortcuts") or [""])[0]
                for x in runs
            )
            msgs.append({"t": round(t - offset, 2), "m": text[:200]})
    return [m for m in msgs if m["t"] >= 0]


def fetch_twitch_chat(video_id: str, start: float | None, end: float | None, max_msgs: int = 60000) -> list[dict]:
    """Récupère le chat d'une VOD Twitch via l'API GraphQL publique."""
    vid = re.sub(r"\D", "", str(video_id))
    if not vid:
        return []
    headers = {"Client-Id": TWITCH_PUBLIC_CLIENT_ID, "Content-Type": "text/plain;charset=UTF-8"}
    offset = float(start or 0)
    msgs: list[dict] = []
    cursor = None
    with httpx.Client(timeout=20) as client:
        for _ in range(4000):
            variables = {"videoID": vid}
            if cursor:
                variables["cursor"] = cursor
            else:
                variables["contentOffsetSeconds"] = int(offset)
            body = [{
                "operationName": "VideoCommentsByOffsetOrCursor",
                "variables": variables,
                "extensions": {"persistedQuery": {
                    "version": 1,
                    "sha256Hash": "b70a3591ff0f4e0313d126c6a1502d79a1c02baebb288227c582044aa76adf6a",
                }},
            }]
            r = client.post(TWITCH_GQL, headers=headers, content=json.dumps(body))
            r.raise_for_status()
            data = r.json()[0].get("data") or {}
            comments = ((data.get("video") or {}).get("comments")) or {}
            edges = comments.get("edges") or []
            if not edges:
                break
            stop = False
            for e in edges:
                n = e.get("node") or {}
                t = float(n.get("contentOffsetSeconds") or 0)
                if end and t > end:
                    stop = True
                    break
                frags = ((n.get("message") or {}).get("fragments")) or []
                text = "".join(f.get("text", "") for f in frags)
                msgs.append({"t": round(t - offset, 2), "m": text[:200]})
            if stop or len(msgs) >= max_msgs:
                break
            if not (comments.get("pageInfo") or {}).get("hasNextPage"):
                break
            cursor = edges[-1].get("cursor")
            if not cursor:
                break
    return [m for m in msgs if m["t"] >= 0]


def import_local_file(src: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / ("source" + (src.suffix.lower() or ".mp4"))
    shutil.move(str(src), dest)
    if dest.suffix != ".mp4":
        from .ffmpeg import run_ffmpeg

        mp4 = out_dir / "source.mp4"
        run_ffmpeg(["-i", str(dest), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-c:a", "aac", "-b:a", "192k", str(mp4)])
        dest.unlink(missing_ok=True)
        dest = mp4
    return dest
