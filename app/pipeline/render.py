"""Rendu d'un clip vertical 1080x1920 (9:16) avec ffmpeg."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable

from ..config import BRAND_DIR, FONTS_DIR
from . import captions as cap
from . import overlays
from .ffmpeg import grab_frame, run_ffmpeg

log = logging.getLogger("noxp.render")

W, H = 1080, 1920
FPS = 30

FILLERS = {
    "euh", "euhh", "heu", "hum", "hmm", "hm", "bah", "ben", "beh", "uh", "um", "uhm", "erm", "eh",
    "ah", "mmh", "mh", "genre", "voila", "voilà", "bref",
}


def _is_filler(w: str) -> bool:
    return re.sub(r"[^\wà-ÿ]", "", w.lower()) in FILLERS


def keep_intervals(words: list[dict], dur: float, mode: str) -> list[tuple[float, float]]:
    """Plages conservées (relatives au clip) pour le nettoyage vocal."""
    if mode in ("", "off", None) or not words:
        return [(0.0, dur)]
    drop_fillers = mode in ("fillers", "both")
    cut_pauses = mode in ("pauses", "both")
    min_gap = 0.65 if cut_pauses else 99.0
    iv: list[list[float]] = []
    for w in words:
        if drop_fillers and _is_filler(w["w"]):
            continue
        a, b = max(0.0, w["s"] - 0.08), min(dur, w["e"] + 0.12)
        if iv and a - iv[-1][1] < min_gap:
            iv[-1][1] = max(iv[-1][1], b)
        else:
            iv.append([a, b])
    if not iv:
        return [(0.0, dur)]
    if not cut_pauses:  # on ne retire que les mots parasites : on garde le reste continu
        iv[0][0] = 0.0
        iv[-1][1] = dur
    else:
        iv[-1][1] = min(dur, iv[-1][1] + 0.25)
    return [(round(a, 3), round(b, 3)) for a, b in iv if b - a > 0.05]


def remapper(iv: list[tuple[float, float]]) -> Callable[[float], float | None]:
    def f(t: float) -> float | None:
        acc = 0.0
        for a, b in iv:
            if t < a:
                return acc  # dans une coupe : collé au début de la plage suivante
            if t <= b:
                return acc + (t - a)
            acc += b - a
        return acc
    return f


def _esc_path(p: Path) -> str:
    return str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def _even(x: float) -> int:
    return max(2, int(round(x / 2)) * 2)


def layout_filter(mode: str, sw: int, sh: int, cx: float, cam: list[float] | None) -> str:
    """Retourne une chaîne de filtres [vin] -> [vlay] (1080x1920)."""
    if mode == "split" and cam:
        bx, by, bw, bh = cam
        cw, ch = bw * sw, bh * sh
        top_aspect = W / (H * 0.4)
        if cw / max(ch, 1) > top_aspect:
            ch = cw / top_aspect
        else:
            cw = ch * top_aspect
        cw, ch = min(cw, sw), min(ch, sh)
        ccx, ccy = (bx + bw / 2) * sw, (by + bh / 2) * sh
        x0 = min(max(0, ccx - cw / 2), sw - cw)
        y0 = min(max(0, ccy - ch / 2), sh - ch)
        gw = min(sw, sh * (W / (H * 0.6)))
        gx = (sw - gw) / 2
        th, bh_px = int(H * 0.4), H - int(H * 0.4)
        return (
            f"[vin]split=2[c1][c2];"
            f"[c1]crop={_even(cw)}:{_even(ch)}:{int(x0)}:{int(y0)},scale={W}:{th},setsar=1[top];"
            f"[c2]crop={_even(gw)}:{sh}:{int(gx)}:0,scale={W}:{bh_px},setsar=1[bot];"
            f"[top][bot]vstack=inputs=2[vlay]"
        )
    if mode == "fit":
        return (
            f"[vin]split=2[b1][b2];"
            f"[b1]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=12:3,"
            f"scale={W}:{H},eq=brightness=-0.10:saturation=1.2[bg];"
            f"[b2]scale={W}:{H}:force_original_aspect_ratio=decrease,setsar=1[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[vlay]"
        )
    # fill (recadrage centré sur le visage / l'action)
    if sw / sh >= W / H:
        nw = _even(sw * H / sh)
        x = int(min(max(0, cx * nw - W / 2), nw - W))
        return f"[vin]scale={nw}:{H},crop={W}:{H}:{x}:0,setsar=1[vlay]"
    nh = _even(sh * W / sw)
    y = int(max(0, (nh - H) / 2))
    return f"[vin]scale={W}:{nh},crop={W}:{H}:0:{y},setsar=1[vlay]"


def zoom_peaks(loud: list[float], start: float, end: float, remap, max_peaks: int = 5) -> list[float]:
    """Instants (temps de sortie) des pics sonores pour le zoom automatique."""
    i0, i1 = int(start * 2), int(end * 2)
    seg = loud[i0:i1]
    if len(seg) < 6:
        return []
    import numpy as np

    arr = np.array(seg)
    thr = np.percentile(arr, 85)
    peaks = []
    for i in np.argsort(-arr):
        if arr[i] < thr or len(peaks) >= max_peaks:
            break
        t = start + i / 2
        if all(abs(t - p) > 4 for p in peaks) and t - start > 1.0:
            peaks.append(t)
    return sorted(x for x in (remap(p - start) for p in peaks) if x is not None)


def render_clip(
    src: Path,
    out: Path,
    work: Path,
    *,
    start: float,
    end: float,
    words_abs: list[dict],
    opts: dict,
    brand: dict,
    layout: dict,
    media: dict,
    loud: list[float],
    hook_text: str = "",
    translate_fn: Callable[[list[str]], list[str]] | None = None,
    encoder: str = "libx264",
    preset: str = "veryfast",
    progress: Callable[[float], None] | None = None,
    tag: str | None = None,
) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    dur = end - start
    rel_words = [{"s": w["s"] - start, "e": w["e"] - start, "w": w["w"]} for w in words_abs]

    iv = keep_intervals(rel_words, dur, opts.get("voice_cleanup", "off"))
    remap = remapper(iv)
    out_dur = sum(b - a for a, b in iv)
    cleaned = iv != [(0.0, dur)]

    kept_words = []
    for w in rel_words:
        if opts.get("voice_cleanup") in ("fillers", "both") and _is_filler(w["w"]):
            continue
        s2, e2 = remap(w["s"]), remap(w["e"])
        if s2 is None or e2 is None or e2 <= s2:
            continue
        kept_words.append({"s": s2, "e": min(e2, out_dur), "w": w["w"]})

    inputs: list[str] = ["-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src)]
    n_in = 1
    fc: list[str] = []

    # ---- vidéo : cadence fixe + nettoyage vocal
    sel = ""
    if cleaned:
        expr = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in iv)
        sel = f",select='{expr}',setpts=N/FRAME_RATE/TB"
    fc.append(f"[0:v]fps={FPS}{sel}[vin]")
    mode = opts.get("layout_mode") or layout.get("mode", "fill")
    cam = opts.get("cam_box") or layout.get("cam")
    if mode == "split" and not cam:
        from .faces import CORNERS

        cam = CORNERS.get(opts.get("cam_corner") or "top-left")
    fc.append(layout_filter(mode, media["width"], media["height"], float(opts.get("crop_cx", layout.get("cx", 0.5))), cam))
    cur = "vlay"

    def chain(f: str):
        nonlocal cur
        nxt = f"v{len(fc)}"
        fc.append(f"[{cur}]{f}[{nxt}]")
        cur = nxt

    if opts.get("color_correct"):
        chain("eq=contrast=1.07:saturation=1.20:brightness=0.015:gamma=0.98,unsharp=5:5:0.45")

    if opts.get("auto_zoom"):
        peaks = zoom_peaks(loud, start, end, remap)
        if peaks:
            bumps = [f"max(0,1-abs(in/{FPS}-{p:.2f})/0.9)" for p in peaks]
            expr = bumps[0]
            for b in bumps[1:]:
                expr = f"max({expr},{b})"
            chain(f"zoompan=z='1+0.13*{expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS}")

    # position des sous-titres / accroche selon la mise en page
    cap_y = None
    hook_y = 0.15
    if mode == "split":
        cap_y = 0.62
        hook_y = 0.40
    pos = opts.get("caption_position") or brand.get("caption_position") or "middle"

    groups: list[list[dict]] = []
    translation = ""
    if opts.get("captions", True) and kept_words:
        cap_kwargs = dict(
            style_id=opts.get("caption_style") or brand.get("caption_style") or "neon",
            position=pos,
            y_frac=cap_y if pos == "middle" else None,
            highlight=brand.get("highlight_color", ""),
            color=brand.get("text_color", ""),
            uppercase=None,
            font_override=brand.get("font", ""),
            duration=out_dur,
        )
        ass_txt, groups = cap.build_ass(kept_words, **cap_kwargs)
        if translate_fn and groups:
            try:
                lines = translate_fn([" ".join(w.get("o", w["w"]) for w in g) for g in groups])
                ass_txt, groups = cap.build_ass(kept_words, translated=lines, **cap_kwargs)
                translation = "ok"
            except Exception as e:  # noqa: BLE001
                log.warning("Traduction des sous-titres impossible : %s", e)
                translation = f"échec : {e}"
        ass_path = work / "captions.ass"
        ass_path.write_text(ass_txt, encoding="utf-8")
        (work / "captions.srt").write_text(cap.plain_srt(kept_words), encoding="utf-8")
        chain(f"ass='{_esc_path(ass_path)}':fontsdir='{_esc_path(FONTS_DIR)}'")

    # ---- emojis IA
    if opts.get("ai_emojis") and groups:
        y_frac = cap_y if (cap_y and pos == "middle") else cap.POSITIONS.get(pos, 0.66)
        last = -99.0
        count = 0
        for g in groups:
            text = " ".join(w["w"] for w in g)
            em = overlays.pick_emoji(text)
            if not em or g[0]["s"] - last < 3.5 or count >= 8:
                continue
            p = overlays.render_emoji_file(em, work / f"emoji{count}.png", 150)
            if not p:
                break
            inputs += ["-i", str(p)]
            a, b = g[0]["s"], min(out_dur, g[-1]["e"] + 0.4)
            y = int(H * y_frac) - 230
            nxt = f"v{len(fc)}"
            fc.append(f"[{cur}][{n_in}:v]overlay=x=(W-w)/2:y={y}:enable='between(t,{a:.2f},{b:.2f})'[{nxt}]")
            cur = nxt
            n_in += 1
            count += 1
            last = a

    # ---- accroche
    if opts.get("hook") and hook_text:
        hd = min(out_dur, float(opts.get("hook_duration") or 4.0))
        hp = overlays.render_hook(hook_text, opts.get("hook_style") or "punchy",
                                  brand.get("highlight_color") or "#FFD60A", work / "hook.png", y_center=hook_y)
        inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{hd:.2f}", "-i", str(hp)]
        nxt = f"v{len(fc)}"
        fc.append(f"[{n_in}:v]format=rgba,fade=t=in:st=0:d=0.2:alpha=1,"
                  f"fade=t=out:st={max(0, hd - 0.35):.2f}:d=0.35:alpha=1[hk{n_in}]")
        fc.append(f"[{cur}][hk{n_in}]overlay=0:0:eof_action=pass[{nxt}]")
        cur = nxt
        n_in += 1

    # ---- logo du kit de marque
    logo = brand.get("logo")
    if opts.get("brand_logo", True) and logo and (BRAND_DIR / logo).exists():
        lp = overlays.prepare_logo(BRAND_DIR / logo, work / "logo.png", int(W * float(brand.get("logo_size", 0.18))),
                                   float(brand.get("logo_opacity", 0.85)))
        inputs += ["-i", str(lp)]
        m = 48
        posmap = {
            "top-left": (f"{m}", f"{m + 60}"), "top-right": (f"W-w-{m}", f"{m + 60}"),
            "bottom-left": (f"{m}", f"H-h-{m + 220}"), "bottom-right": (f"W-w-{m}", f"H-h-{m + 220}"),
        }
        x, y = posmap.get(brand.get("logo_position", "top-right"), posmap["top-right"])
        nxt = f"v{len(fc)}"
        fc.append(f"[{cur}][{n_in}:v]overlay={x}:{y}[{nxt}]")
        cur = nxt
        n_in += 1

    if opts.get("transitions"):
        chain(f"fade=t=in:st=0:d=0.25,fade=t=out:st={max(0, out_dur - 0.35):.2f}:d=0.35")
    fc.append(f"[{cur}]format=yuv420p[vout]")

    # ---- audio
    if media.get("has_audio", True):
        a_chain = "[0:a]"
        parts = []
        if cleaned:
            expr = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in iv)
            parts.append(f"aselect='{expr}',asetpts=N/SR/TB")
        if opts.get("enhance_audio"):
            parts.append("highpass=f=70,afftdn=nf=-25,acompressor=threshold=-20dB:ratio=3:attack=5:release=120")
        parts.append("loudnorm=I=-14:TP=-1.5:LRA=11")
        if opts.get("transitions"):
            parts.append(f"afade=t=in:st=0:d=0.2,afade=t=out:st={max(0, out_dur - 0.35):.2f}:d=0.35")
        parts.append("aresample=44100")
        fc.append(a_chain + ",".join(parts) + "[aout]")
    else:
        inputs += ["-f", "lavfi", "-t", f"{out_dur:.2f}", "-i", "anullsrc=r=44100:cl=stereo"]
        fc.append(f"[{n_in}:a]anull[aout]")
        n_in += 1

    venc = ["-c:v", encoder]
    if encoder == "libx264":
        venc += ["-preset", preset, "-crf", "21", "-profile:v", "high"]
    elif "videotoolbox" in encoder:
        venc += ["-b:v", "9M"]
    else:
        venc += ["-b:v", "9M"]

    args = [
        *inputs,
        "-filter_complex", ";".join(fc),
        "-map", "[vout]", "-map", "[aout]",
        *venc, "-r", str(FPS), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k",
        "-t", f"{out_dur:.3f}",
        "-movflags", "+faststart",
        str(out),
    ]
    (work / "ffmpeg_args.txt").write_text("\n".join(args))
    run_ffmpeg(args, duration=out_dur, progress=progress, tag=tag)
    thumb = out.with_suffix(".jpg")
    grab_frame(out, min(1.2, out_dur / 2), thumb, width=540)
    return {"duration": round(out_dur, 2), "thumb": thumb.name, "groups": len(groups), "translation": translation}
