"""Petites aides autour de ffmpeg / ffprobe."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Callable

import numpy as np


class FFmpegError(RuntimeError):
    pass


# ffmpeg en cours, par projet : permet d'arrêter vraiment un traitement quand on supprime le projet
RUNNING: dict[str, subprocess.Popen] = {}


def kill(tag: str) -> None:
    proc = RUNNING.pop(tag, None)
    if proc and proc.poll() is None:
        proc.kill()


def run_ffmpeg(args: list[str], *, duration: float | None = None,
               progress: Callable[[float], None] | None = None, tag: str | None = None) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-y", "-nostdin", "-loglevel", "error", "-stats_period", "1",
           "-progress", "pipe:1", *args]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if tag:
        RUNNING[tag] = proc
    assert proc.stdout is not None
    for line in proc.stdout:
        if progress and duration and line.startswith("out_time_us="):
            try:
                us = int(line.split("=", 1)[1])
                progress(max(0.0, min(1.0, us / 1e6 / duration)))
            except ValueError:
                pass
    err = proc.stderr.read() if proc.stderr else ""
    code = proc.wait()
    if tag and RUNNING.get(tag) is proc:
        RUNNING.pop(tag, None)
    if code != 0:
        if code < 0:
            raise FFmpegError("Traitement arrêté.")
        raise FFmpegError(err.strip()[-1500:] or "ffmpeg a échoué")


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    data = json.loads(out)
    v = next((s for s in data["streams"] if s.get("codec_type") == "video"), None)
    a = next((s for s in data["streams"] if s.get("codec_type") == "audio"), None)
    w = int(v["width"]) if v else 0
    h = int(v["height"]) if v else 0
    rot = 0
    if v:
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = int(sd["rotation"])
        rot = int((v.get("tags") or {}).get("rotate", rot))
    if abs(rot) in (90, 270):
        w, h = h, w
    fps = 30.0
    if v and v.get("avg_frame_rate") and v["avg_frame_rate"] != "0/0":
        n, d = v["avg_frame_rate"].split("/")
        fps = float(n) / float(d or 1) if float(d or 1) else 30.0
    return {
        "duration": float(data["format"].get("duration") or 0),
        "width": w,
        "height": h,
        "fps": fps,
        "has_audio": a is not None,
    }


def extract_audio(src: Path, dest: Path) -> Path:
    run_ffmpeg(["-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dest)])
    return dest


def loudness_curve(wav: Path, step: float = 0.5) -> list[float]:
    """Niveau sonore (dB RMS) par fenêtre de `step` secondes."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(wav), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True, check=True,
    ).stdout
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    n = int(16000 * step)
    if samples.size < n:
        return [-60.0]
    usable = samples[: samples.size // n * n].reshape(-1, n)
    rms = np.sqrt(np.mean(usable ** 2, axis=1) + 1e-10)
    return [round(float(x), 2) for x in 20 * np.log10(rms)]


def grab_frame(src: Path, t: float, dest: Path, width: int = 480) -> Path:
    run_ffmpeg(["-ss", f"{max(0, t):.2f}", "-i", str(src), "-frames:v", "1",
                "-vf", f"scale={width}:-2", "-q:v", "3", str(dest)])
    return dest


def has_encoder(name: str) -> bool:
    out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    return re.search(rf"\s{re.escape(name)}\s", out) is not None
