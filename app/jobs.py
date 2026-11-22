"""File de traitement : un thread qui enchaîne téléchargement, transcription, analyse et rendu."""
from __future__ import annotations

import json
import re
import logging
import queue
import shutil
import threading
import time
import traceback
from pathlib import Path

from . import db
from .config import PROJECTS_DIR
from .pipeline import analyze as an
from .pipeline import download as dl
from .pipeline import faces, llm
from .pipeline import ffmpeg as ff
from .pipeline import render as rd

log = logging.getLogger("noxp.jobs")

_q: "queue.Queue[tuple[str, str]]" = queue.Queue()
_started = False

DEFAULT_OPTIONS = {
    "range_start": None,
    "range_end": None,
    "language": "auto",
    "genre": "auto",
    "clip_length": "auto",
    "clip_types": ["viral", "funny", "drama", "hype"],
    "prompt": "",
    "max_clips": 10,
    "ai_engine": "",  # vide = réglage global
    "layout_mode": "",  # vide = auto ; fill | fit | split
    "cam_corner": "top-left",
    "cam_box": None,  # [x, y, largeur, hauteur] (0..1) de la facecam, dessinée par l'utilisateur
    "captions": True,
    "caption_style": "neon",
    "caption_position": "middle",
    "hook": True,
    "hook_style": "punchy",
    "hook_duration": 4.0,
    "ai_emojis": False,
    "voice_cleanup": "off",  # off | pauses | fillers | both
    "enhance_audio": False,
    "auto_zoom": False,
    "transitions": False,
    "color_correct": False,
    "translate_to": "",
    "captions_fr": True,  # sous-titres toujours en français (traduits si la vidéo est dans une autre langue)
    "brand_logo": True,
    "split": True,  # False = pas de découpage : un seul clip sur toute la plage
    "progress_bar": True,  # barre de progression (incite à regarder jusqu'au bout)
}


def pdir(pid: str) -> Path:
    return PROJECTS_DIR / pid


def start_worker() -> None:
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_loop, name="noxp-worker", daemon=True).start()
    for p in db.query("SELECT id FROM projects WHERE status='queued' ORDER BY created_at"):
        _q.put(("project", p["id"]))
    for c in db.query("SELECT id FROM clips WHERE status='queued' AND project_id IN "
                      "(SELECT id FROM projects WHERE status='done')"):
        _q.put(("clip", c["id"]))


def enqueue_project(pid: str) -> None:
    _q.put(("project", pid))


def enqueue_clip(cid: str) -> None:
    _q.put(("clip", cid))


def _loop() -> None:
    while True:
        kind, id_ = _q.get()
        try:
            if kind == "project":
                process_project(id_)
            else:
                rerender_clip(id_)
        except Exception as e:  # noqa: BLE001
            log.error("Échec %s %s: %s", kind, id_, traceback.format_exc())
            if kind == "project":
                p = db.get("projects", id_) or {}
                if p.get("status") in ("downloading", "queued"):
                    cleanup_partial(id_)
                db.update("projects", id_, status="error", error=str(e)[:2000], message="Erreur")
            else:
                db.update("clips", id_, status="error", error=str(e)[:2000])


def _set(pid: str, status: str, progress: float, message: str) -> None:
    db.update("projects", pid, status=status, progress=round(progress, 3), message=message)


STAGES = {"downloading": (0.0, 0.25), "transcribing": (0.25, 0.55), "analyzing": (0.55, 0.62),
          "rendering": (0.62, 1.0)}


def _stage_cb(pid: str, stage: str):
    a, b = STAGES[stage]
    last = [0.0]

    def cb(frac: float, msg: str = ""):
        now = time.time()
        if now - last[0] < 1.0 and frac < 0.999:
            return
        last[0] = now
        _set(pid, stage, a + (b - a) * max(0.0, min(1.0, frac)), msg)
    return cb


def project_options(p: dict) -> dict:
    o = dict(DEFAULT_OPTIONS)
    o.update(p.get("options") or {})
    return o


def process_project(pid: str) -> None:
    p = db.get("projects", pid)
    if not p:
        return
    opts = project_options(p)
    settings = db.get_settings()
    d = pdir(pid)
    d.mkdir(parents=True, exist_ok=True)
    meta = dict(p.get("meta") or {})

    # 1. Téléchargement
    src = d / "source.mp4"
    chat_path = d / "chat.json"
    if not src.exists():
        _set(pid, "downloading", 0.01, "Récupération de la vidéo…")
        res = dl.download(
            p["source_url"], d,
            start=opts.get("range_start"), end=opts.get("range_end"),
            cookies=settings.get("ytdlp_cookies") or None,
            progress=_stage_cb(pid, "downloading"), tag=pid,
        )
        src = res["path"]
        meta.update({k: v for k, v in res["info"].items() if v})
        if res["chat_path"]:
            meta["chat"] = True
        db.update("projects", pid, title=meta.get("title") or p["title"], meta=meta)
    media = ff.probe(src)
    meta["media"] = media
    # Fichier importé : la plage choisie s'applique ici
    if p["source_kind"] == "upload" and (opts.get("range_start") or opts.get("range_end")) and not meta.get("trimmed"):
        s = float(opts.get("range_start") or 0)
        e = float(opts.get("range_end") or media["duration"])
        tmp = d / "trim.mp4"
        ff.run_ffmpeg(["-ss", f"{s}", "-to", f"{e}", "-i", str(src), "-c", "copy", str(tmp)])
        tmp.replace(src)
        media = ff.probe(src)
        meta.update({"media": media, "trimmed": True, "range_offset": s})
    db.update("projects", pid, meta=meta)
    duration = media["duration"]

    thumb = d / "thumb.jpg"
    if not thumb.exists():
        try:
            ff.grab_frame(src, min(duration * 0.3, 30), thumb, 640)
        except ff.FFmpegError:
            pass

    # 2. Audio + transcription
    tpath = d / "transcript.json"
    lpath = d / "loud.json"
    if not tpath.exists() or not lpath.exists():
        _set(pid, "transcribing", STAGES["transcribing"][0], "Analyse de l'audio…")
        wav = d / "audio.wav"
        if media["has_audio"]:
            ff.extract_audio(src, wav)
            lpath.write_text(json.dumps(ff.loudness_curve(wav)))
            try:
                tr = transcribe_audio(wav, settings, opts, duration, _stage_cb(pid, "transcribing"), tag=pid)
            except Exception as e:  # noqa: BLE001
                log.warning("Transcription impossible : %s", e)
                tr = {"language": None, "segments": [], "warning": f"Transcription indisponible : {e}"}
            wav.unlink(missing_ok=True)
        else:
            lpath.write_text(json.dumps([-60.0] * int(duration * 2)))
            tr = {"language": None, "segments": []}
        tpath.write_text(json.dumps(tr, ensure_ascii=False))
    tr = json.loads(tpath.read_text())
    loud = json.loads(lpath.read_text())
    segments = tr.get("segments", [])
    if tr.get("warning"):
        meta["warning"] = tr["warning"]
    meta["language"] = tr.get("language")
    chat = json.loads(chat_path.read_text()) if chat_path.exists() else []

    # 3. Analyse
    _set(pid, "analyzing", STAGES["analyzing"][0], "Recherche des moments viraux…")
    genre = opts.get("genre") or "auto"
    if genre == "auto":
        genre = guess_genre(meta, segments)
        meta["genre_detected"] = genre
    lang = "fr" if (meta.get("language") or "fr") == "fr" else "en"  # langue des titres / accroches
    meta["text_language"] = lang
    heatmap = json.loads((d / "heatmap.json").read_text()) if (d / "heatmap.json").exists() else []
    comments = json.loads((d / "comments.json").read_text()) if (d / "comments.json").exists() else []
    meta["audience_signals"] = {"heatmap": bool(heatmap), "comments": len(comments)}
    signals = an.build_signals(duration, segments, loud, chat, opts.get("prompt", ""), genre=genre,
                               heatmap=heatmap, comments=comments)
    max_clips = max(1, min(30, int(opts.get("max_clips") or 10)))
    if opts.get("split", True):
        length = opts.get("clip_length", "auto")
        if length == "auto" and genre in ("gaming", "gta", "concept"):
            length = "tiktok"
        cands = an.find_candidates(duration, segments, signals, length=length,
                                   clip_types=opts.get("clip_types"), max_clips=max_clips)
    else:  # recette « sous-titres / recadrage » : toute la plage devient un seul clip (max 10 min)
        whole = an.find_candidates(duration, segments, signals, length="auto", max_clips=1)[:1]
        base = whole[0] if whole else {"scores": {"viral": 0.5, "funny": 0.3, "drama": 0.3, "hype": 0.3},
                                        "category": "hype", "composite": 0.5}
        cands = [{**base, "start": 0.0, "end": min(duration, 600.0), "score": an.to_score(base["composite"])}]
    for i, c in enumerate(cands):
        c["id"] = f"c{i}"
        if opts.get("split", True):
            c["start"], c["end"] = an.snap(c, segments, duration)
        c["text"] = an.clip_text(segments, c["start"], c["end"])
        c["chat_peak"] = bool(chat) and float(signals["chat_z"][int(c["start"]):int(c["end"]) + 1].max(initial=0)) > 2.5

    engine = settings["ai_engine"] if not opts.get("ai_engine") else opts["ai_engine"]
    engine = llm.available_engine({**settings, "ai_engine": engine})
    meta["ai_engine_used"] = engine
    ranked: dict = {}
    if engine != "heuristic" and cands:
        _set(pid, "analyzing", 0.58, f"L'IA ({engine}) classe les meilleurs moments…")
        ranked = llm.rank_clips(settings, cands, genre=genre, prompt=opts.get("prompt", ""),
                                source_title=meta.get("title", ""), engine=engine, lang=lang)
        if not ranked:
            meta["ai_engine_used"] = f"{engine} (échec → heuristiques)"

    wanted = [t for t in opts.get("clip_types") or [] if t in ("funny", "drama", "hype")]
    final = []
    for c in cands:
        r = ranked.get(c["id"])
        scores = {k: round(v * 100) for k, v in c["scores"].items()}
        if r:
            for k in ("viral", "funny", "drama", "hype"):
                try:
                    scores[k] = round(0.6 * float(r.get(k, scores[k])) + 0.4 * scores[k])
                except (TypeError, ValueError):
                    pass
        # une seule catégorie fait foi : celle de l'IA si elle a noté le clip, sinon celle de l'analyse
        cat = max(("funny", "drama", "hype"), key=lambda k: scores[k]) if r else c["category"]
        c["category"] = cat
        texts = an.fallback_texts(c, c["text"], genre=genre, source_title=meta.get("title", ""),
                                  source_tags=meta.get("tags") or [], lang=lang)
        if r:
            for k in ("title", "hook", "description", "reason"):
                if isinstance(r.get(k), str) and r[k].strip():
                    texts[k] = r[k].strip()
            if isinstance(r.get("hashtags"), list) and r["hashtags"]:
                texts["hashtags"] = ["#" + str(h).lstrip("#").replace(" ", "") for h in r["hashtags"]][:8]
            try:
                if not opts.get("split", True):
                    raise ValueError("pas de raccourcissement sans découpage")
                ts_, te_ = float(r.get("trim_start") or 0), float(r.get("trim_end") or 0)
                dur = c["end"] - c["start"]
                if 0 <= ts_ < dur * 0.3 and 0 <= te_ < dur * 0.3 and dur - ts_ - te_ >= 8:
                    c["start"] += ts_
                    c["end"] -= te_
                    c["start"], c["end"] = an.snap(c, segments, duration)
            except (TypeError, ValueError):
                pass
        composite = 0.6 * scores["viral"] + 0.4 * max([scores[w] for w in wanted] or [scores["viral"]])
        final.append({**c, "scores": scores, "category": cat, "composite": composite, **texts})
    final.sort(key=lambda c: c["composite"], reverse=True)
    final = final[:max_clips]

    # 4. Mise en page (visage / facecam)
    layout_path = d / "layout.json"
    if layout_path.exists():
        layout = json.loads(layout_path.read_text())
    else:
        _set(pid, "analyzing", 0.6, "Détection du visage / de la facecam…")
        layout = faces.analyze_layout(src, duration, media["width"], media["height"], genre)
        layout_path.write_text(json.dumps(layout))
    meta["layout"] = layout
    meta["genre"] = genre
    db.update("projects", pid, meta=meta)

    # 5. Création des clips + rendu
    db.query("DELETE FROM clips WHERE project_id=?", (pid,))
    clips = []
    for rank, c in enumerate(final, 1):
        rec = db.insert("clips", {
            "project_id": pid, "rank": rank, "start": c["start"], "end": c["end"],
            "score": int(round(max(55, min(99, 55 + 0.44 * c["composite"])))),
            "scores": c["scores"], "category": c["category"], "title": c["title"], "hook": c["hook"],
            "description": c["description"], "hashtags": c["hashtags"], "reason": c["reason"],
            "transcript": c["text"], "status": "queued", "overrides": {},
        })
        clips.append(rec)
    (d / "clips").mkdir(exist_ok=True)
    for i, rec in enumerate(clips):
        if not db.get("projects", pid):  # projet supprimé pendant le montage
            return
        a, b = STAGES["rendering"]
        base = a + (b - a) * i / max(1, len(clips))
        step = (b - a) / max(1, len(clips))
        _set(pid, "rendering", base, f"Montage du clip {i + 1}/{len(clips)}…")

        def cb(frac, base=base, step=step, i=i):
            _set(pid, "rendering", base + step * frac, f"Montage du clip {i + 1}/{len(clips)}…")
        try:
            _render(rec, p | {"meta": meta}, opts, settings, segments, loud, media, layout, cb)
        except Exception as e:  # noqa: BLE001
            log.error("Rendu clip échoué: %s", traceback.format_exc())
            db.update("clips", rec["id"], status="error", error=str(e)[:2000])
    _set(pid, "done", 1.0, f"{len(clips)} clips prêts")


WHISPER_FALLBACK = ["large-v3-turbo", "medium", "small", "base", "tiny"]


def transcribe_audio(wav: Path, settings: dict, opts: dict, duration: float, cb, tag: str | None = None) -> dict:
    """Transcription dans un processus séparé, avec repli sur des modèles plus légers en cas d'échec."""
    import subprocess
    import sys

    first = settings.get("whisper_model") or "small"
    lighter = WHISPER_FALLBACK[WHISPER_FALLBACK.index(first) + 1:] if first in WHISPER_FALLBACK else ["base", "tiny"]
    chain = [first] + lighter[:2]
    out = wav.with_suffix(".transcript.json")
    errors = []
    for model in chain:
        cb(0.0, f"Transcription (modèle {model})…")
        cmd = [sys.executable, "-m", "app.pipeline.transcribe", str(wav), str(out), model,
               opts.get("language") or "auto", str(duration)]
        errlog = wav.with_suffix(".whisper.log")
        errfh = open(errlog, "w")  # fichier (et pas un tube) : évite tout blocage si Whisper écrit beaucoup
        proc = subprocess.Popen(cmd, cwd=str(Path(__file__).resolve().parent.parent), stdout=subprocess.PIPE,
                                stderr=errfh, text=True)
        if tag:
            ff.RUNNING[tag] = proc
        assert proc.stdout is not None
        for line in proc.stdout:
            if line.startswith("PROGRESS "):
                parts = line.rstrip("\n").split(" ", 2)
                try:
                    cb(float(parts[1]), parts[2] if len(parts) > 2 else "")
                except ValueError:
                    pass
        code = proc.wait()
        errfh.close()
        err = errlog.read_text(errors="ignore")
        errlog.unlink(missing_ok=True)
        if tag and ff.RUNNING.get(tag) is proc:
            ff.RUNNING.pop(tag, None)
        if code == 0 and out.exists():
            res = json.loads(out.read_text())
            out.unlink(missing_ok=True)
            if model != first:
                res["warning"] = (f"Le modèle de transcription « {first} » a échoué sur ce serveur : "
                                  f"« {model} » a été utilisé à la place (un peu moins précis).")
            return res
        if code == -9:
            reason = "mémoire insuffisante (processus arrêté par le système)"
        elif code < 0:
            reason = "arrêtée"
        else:
            reason = (err.strip().splitlines() or ["erreur inconnue"])[-1][:200]
        errors.append(f"{model} : {reason}")
        log.warning("Transcription %s échouée : %s", model, reason)
        if code < 0 and code != -9:  # projet supprimé : on n'insiste pas
            break
    raise RuntimeError(" ; ".join(errors))


def guess_genre(meta: dict, segments: list[dict]) -> str:
    text = (meta.get("title", "") + " " + " ".join(meta.get("tags") or [])).lower()
    if re.search(r"\bgta\b|grand theft auto|gtarp|gta ?rp|los santos", text):
        return "gta"
    if re.search(r"concept|défi|defi|challenge|24 ?h|dernier (à|a|qui)|qui (sera|va)|tier ?list|"
                 r"vs\b|contre \d+|on a test|j'ai test|nos? abonnés|blind ?test", text):
        return "concept"
    for k in an.GAMES:
        if k.strip() in text:
            return "gaming"
    rules = {
        "gaming": ["gameplay", "game", "jeu", "ranked", "stream", "twitch", "speedrun", "let's play"],
        "podcast": ["podcast", "interview", "épisode", "episode", "talk"],
        "sports": ["match", "football", "foot", "nba", "ufc", "boxe", "highlights"],
        "news": ["actu", "news", "journal", "info"],
        "education": ["tuto", "tutorial", "comment", "how to", "cours", "explique"],
        "reaction": ["réaction", "reaction", "react"],
        "lifestyle": ["vlog", "routine", "lifestyle", "voyage"],
    }
    for g, kws in rules.items():
        if any(k in text for k in kws):
            return g
    return "entertainment"


def _render(clip: dict, project: dict, opts: dict, settings: dict, segments: list[dict], loud: list[float],
            media: dict, layout: dict, cb) -> None:
    pid = project["id"]
    d = pdir(pid)
    o = {**opts, **(clip.get("overrides") or {})}
    db.update("clips", clip["id"], status="rendering", error=None)
    words = an.clip_words(segments, clip["start"], clip["end"])
    if o.get("layout_mode") in ("fill", "") and layout.get("mode") == "fill" and layout.get("cx", 0.5) != 0.5:
        try:
            o["crop_cx"] = faces.clip_center(d / "source.mp4", clip["start"], clip["end"], layout.get("cx", 0.5))
        except Exception:  # noqa: BLE001
            pass

    translate_fn = None
    src_lang = (project.get("meta") or {}).get("language")
    target = o.get("translate_to") or ("français" if o.get("captions_fr", True) else "")
    if target and src_lang and llm.lang_code(target) == src_lang:
        target = ""  # déjà dans la bonne langue
    if target and src_lang:
        def translate_fn(lines, target=target, src_lang=src_lang):
            return llm.translate_groups(settings, lines, target, src_lang)

    out = d / "clips" / f"{clip['id']}.mp4"
    tmp = d / "clips" / f"{clip['id']}.tmp.mp4"
    res = rd.render_clip(
        d / "source.mp4", tmp, d / "work" / clip["id"],
        start=clip["start"], end=clip["end"], words_abs=words, opts=o, brand=settings["brand"],
        layout=layout, media=media, loud=loud, hook_text=clip.get("hook") or "",
        translate_fn=translate_fn, encoder=_encoder(settings.get("video_encoder") or "libx264"),
        preset=settings.get("render_preset") or "veryfast", progress=cb, tag=pid,
    )
    tmp.replace(out)
    thumb_src = tmp.with_suffix(".jpg")
    thumb = out.with_suffix(".jpg")
    if thumb_src.exists():
        thumb_src.replace(thumb)
    srt = d / "work" / clip["id"] / "captions.srt"
    if srt.exists():
        shutil.copy(srt, out.with_suffix(".srt"))
    db.update("clips", clip["id"], status="done", file=out.name, thumb=thumb.name,
              overrides={**(clip.get("overrides") or {}), "_duration": res["duration"],
                         "_translation": f"{target}: {res['translation']}" if res.get("translation") else ""})


_enc_ok: dict[str, bool] = {}


def _encoder(name: str) -> str:
    """Repli sur libx264 si l'encodeur matériel demandé n'existe pas sur cette machine."""
    if name not in _enc_ok:
        _enc_ok[name] = ff.has_encoder(name)
    return name if _enc_ok[name] else "libx264"


def rerender_clip(cid: str) -> None:
    clip = db.get("clips", cid)
    if not clip:
        return
    p = db.get("projects", clip["project_id"])
    if not p:
        return
    d = pdir(p["id"])
    if not (d / "source.mp4").exists():
        raise RuntimeError("La vidéo source a été supprimée pour libérer de la place : "
                           "relance un nouveau projet pour remonter ce clip.")
    opts = project_options(p)
    settings = db.get_settings()
    tr = json.loads((d / "transcript.json").read_text())
    loud = json.loads((d / "loud.json").read_text())
    meta = p.get("meta") or {}
    layout = meta.get("layout") or {"mode": "fill", "cx": 0.5}
    media = meta.get("media") or ff.probe(d / "source.mp4")

    def cb(frac):
        pass
    _render(clip, p, opts, settings, tr.get("segments", []), loud, media, layout, cb)


def cleanup_partial(pid: str) -> None:
    """Supprime un téléchargement interrompu (fichiers .part, flux séparés, source incomplète)."""
    d = pdir(pid)
    for f in d.glob("*"):
        if f.is_file() and (f.name.startswith("source") or f.suffix in (".part", ".ytdl", ".temp")
                            or ".part" in f.name or ".f" in f.stem):
            f.unlink(missing_ok=True)


def free_space() -> dict:
    """Libère de la place : vidéos sources et fichiers de travail des projets terminés."""
    freed = 0
    for p in db.query("SELECT id, status FROM projects"):
        d = pdir(p["id"])
        if p["status"] == "done":
            for f in [*d.glob("source.*"), *d.rglob("work/*/*")]:
                if f.is_file():
                    freed += f.stat().st_size
                    f.unlink(missing_ok=True)
        elif p["status"] == "error":
            for f in d.rglob("*"):
                if f.is_file() and f.suffix not in (".jpg", ".json"):
                    freed += f.stat().st_size
                    f.unlink(missing_ok=True)
    return {"freed_gb": round(freed / 1e9, 2)}


def delete_project(pid: str) -> None:
    ff.kill(pid)  # arrête le téléchargement / montage en cours de ce projet
    db.query("DELETE FROM posts WHERE clip_id IN (SELECT id FROM clips WHERE project_id=?)", (pid,))
    db.query("DELETE FROM clips WHERE project_id=?", (pid,))
    db.delete("projects", pid)
    shutil.rmtree(pdir(pid), ignore_errors=True)
