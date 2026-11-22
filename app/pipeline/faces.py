"""Recadrage intelligent : détection de visage / facecam avec OpenCV (local, gratuit)."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import numpy as np

log = logging.getLogger("noxp.faces")

_cascade = None


def _detector():
    global _cascade
    if _cascade is None:
        import cv2

        _cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    return _cascade


def _frame(src: Path, t: float, width: int = 640):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{max(0, t):.2f}", "-i", str(src), "-frames:v", "1",
         "-vf", f"scale={width}:-2", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True,
    ).stdout
    if not raw:
        return None
    h = len(raw) // width
    if h <= 0:
        return None
    return np.frombuffer(raw[: width * h], dtype=np.uint8).reshape(h, width)


def detect_faces(src: Path, times: list[float]) -> list[list[tuple[float, float, float, float]]]:
    """Pour chaque instant : liste de visages (x, y, w, h) normalisés 0..1."""
    try:
        det = _detector()
    except Exception as e:  # OpenCV absent
        log.warning("OpenCV indisponible : %s", e)
        return []
    res = []
    for t in times:
        img = _frame(src, t)
        if img is None:
            res.append([])
            continue
        h, w = img.shape
        faces = det.detectMultiScale(img, scaleFactor=1.1, minNeighbors=6, minSize=(max(18, w // 40),) * 2)
        res.append([(x / w, y / h, fw / w, fh / h) for (x, y, fw, fh) in faces])
    return res


def analyze_layout(src: Path, duration: float, width: int, height: int, genre: str) -> dict:
    """Choisit la mise en page auto : split (facecam + jeu), fill (visage suivi) ou fit (flou)."""
    portrait = height > width
    if portrait:
        return {"mode": "fill", "cx": 0.5}
    n = 14
    times = [duration * (i + 0.5) / n for i in range(n)]
    found = detect_faces(src, times)
    frames_with = [f for f in found if f]
    if not found or len(frames_with) < max(3, int(0.45 * len(found))):
        return {"mode": "fill" if genre == "gaming" else "fit", "cx": 0.5}
    # on garde le plus grand visage de chaque image
    main = [max(f, key=lambda b: b[2] * b[3]) for f in frames_with]
    cxs = np.array([b[0] + b[2] / 2 for b in main])
    cys = np.array([b[1] + b[3] / 2 for b in main])
    ws = np.array([b[2] for b in main])
    cx, cy, fw = float(np.median(cxs)), float(np.median(cys)), float(np.median(ws))
    stable = float(np.std(cxs)) < 0.08 and float(np.std(cys)) < 0.08
    corner = (cx < 0.33 or cx > 0.67) and (cy < 0.38 or cy > 0.62)
    if stable and corner and fw < 0.16:
        # facecam : la webcam fait ~3,2x la largeur du visage
        bw = min(0.45, fw * 3.2)
        bh = min(0.5, bw * width / height * 0.75)
        bx = min(max(0.0, cx - bw / 2), 1 - bw)
        by = min(max(0.0, cy - bh / 2), 1 - bh)
        return {"mode": "split", "cam": [bx, by, bw, bh], "cx": 0.5}
    return {"mode": "fill", "cx": cx}


def clip_center(src: Path, start: float, end: float, default: float = 0.5) -> float:
    """Centre horizontal du visage principal sur la durée du clip (recadrage suivi)."""
    times = [start + (end - start) * (i + 0.5) / 5 for i in range(5)]
    found = [f for f in detect_faces(src, times) if f]
    if len(found) < 2:
        return default
    xs = [max(f, key=lambda b: b[2] * b[3]) for f in found]
    return float(np.median([b[0] + b[2] / 2 for b in xs]))


CORNERS = {
    "top-left": [0.0, 0.0, 0.28, 0.34],
    "top-right": [0.72, 0.0, 0.28, 0.34],
    "bottom-left": [0.0, 0.66, 0.28, 0.34],
    "bottom-right": [0.72, 0.66, 0.28, 0.34],
}
