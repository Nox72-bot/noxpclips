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


def _frame(src: Path, t: float, width: int = 960):
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
        import cv2

        img = cv2.equalizeHist(img)  # webcams sombres / éclairage RGB des streamers
        h, w = img.shape
        faces = det.detectMultiScale(img, scaleFactor=1.08, minNeighbors=5, minSize=(max(20, w // 48),) * 2)
        res.append([(x / w, y / h, fw / w, fh / h) for (x, y, fw, fh) in faces])
    return res


def analyze_layout(src: Path, duration: float, width: int, height: int, genre: str) -> dict:
    """Choisit la mise en page auto : split (facecam + jeu), fill (visage suivi) ou fit (flou)."""
    portrait = height > width
    if portrait:
        return {"mode": "fill", "cx": 0.5}
    n = 18
    times = [duration * (i + 0.5) / n for i in range(n)]
    found = detect_faces(src, times)
    frames_with = [f for f in found if f]
    if not found or len(frames_with) < max(3, int(0.35 * len(found))):
        # gaming sans facecam : on montre tout le gameplay (fond flou), rien n'est coupé
        return {"mode": "full" if genre in ("gaming", "gta") else "fit", "cx": 0.5}
    # Plusieurs personnes bien écartées (vidéo concept entre potes, plateau) : on garde tout le monde
    wide_groups = sum(1 for f in frames_with
                      if len(f) >= 2 and max(b[0] + b[2] / 2 for b in f) - min(b[0] + b[2] / 2 for b in f) > 0.35)
    if wide_groups >= max(3, int(0.4 * len(frames_with))):
        return {"mode": "fit", "cx": 0.5, "group": True}
    # Facecam : petit visage qui reste au même endroit, n'importe où hors du centre de l'image
    # (coin, côté gauche/droit à mi-hauteur…). On cherche le groupe de visages le plus stable.
    small = [b for f in frames_with for b in f if b[2] < 0.2]
    best = None
    for ref in small:
        rx, ry = ref[0] + ref[2] / 2, ref[1] + ref[3] / 2
        near = [b for b in small if abs(b[0] + b[2] / 2 - rx) < 0.05 and abs(b[1] + b[3] / 2 - ry) < 0.06]
        if best is None or len(near) > len(best):
            best = near
    if best and len(best) >= max(3, int(0.3 * len(found))):
        cx = float(np.median([b[0] + b[2] / 2 for b in best]))
        cy = float(np.median([b[1] + b[3] / 2 for b in best]))
        fw = float(np.median([b[2] for b in best]))
        off_center = abs(cx - 0.5) > 0.18 or abs(cy - 0.5) > 0.22
    else:
        off_center = False
    if off_center:
        # facecam : la webcam fait ~3,2x la largeur du visage
        bw = min(0.45, fw * 2.9)
        bh = min(0.5, bw * width / height * 0.75)
        bx = min(max(0.0, cx - bw / 2), 1 - bw)
        by = min(max(0.0, cy - bh / 2), 1 - bh)
        box = [round(bx, 4), round(by, 4), round(bw, 4), round(bh, 4)]
        # gaming : facecam en haut + gameplay entier ; autres vidéos : facecam + image recadrée
        return {"mode": "full" if genre in ("gaming", "gta") else "split", "cam": box, "cx": 0.5}
    # sinon : visage principal suivi (vlog, podcast…)
    main = [max(f, key=lambda b: b[2] * b[3]) for f in frames_with]
    cx = float(np.median([b[0] + b[2] / 2 for b in main]))
    if genre in ("gaming", "gta") and float(np.median([b[2] for b in main])) < 0.12:
        return {"mode": "full", "cx": 0.5}  # petits visages instables = personnages du jeu
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
