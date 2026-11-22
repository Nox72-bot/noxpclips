"""Transcription locale et gratuite avec faster-whisper (horodatage mot à mot)."""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Callable

log = logging.getLogger("noxp.transcribe")

_models: dict = {}
_lock = threading.Lock()


def _load(name: str):
    with _lock:
        if name not in _models:
            from faster_whisper import WhisperModel

            device = os.environ.get("NOXP_WHISPER_DEVICE", "auto")
            compute = os.environ.get("NOXP_WHISPER_COMPUTE", "int8")
            threads = int(os.environ.get("NOXP_WHISPER_THREADS", "0")) or max(1, (os.cpu_count() or 2))
            _models[name] = WhisperModel(name, device=device, compute_type=compute, cpu_threads=threads)
        return _models[name]


def transcribe(
    wav: Path,
    *,
    model: str = "small",
    language: str | None = None,
    duration: float = 0,
    progress: Callable[[float, str], None] | None = None,
) -> dict:
    """Retourne {language, segments:[{start,end,text,words:[{s,e,w}]}]}."""
    m = _load(model)
    lang = None if not language or language == "auto" else language
    segments, info = m.transcribe(
        str(wav),
        language=lang,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400},
        beam_size=1,
        condition_on_previous_text=False,
    )
    out = []
    for seg in segments:
        words = [
            {"s": round(w.start, 2), "e": round(w.end, 2), "w": w.word.strip()}
            for w in (seg.words or [])
            if w.word.strip()
        ]
        out.append({"start": round(seg.start, 2), "end": round(seg.end, 2),
                    "text": seg.text.strip(), "words": words})
        if progress and duration:
            progress(min(seg.end / duration, 0.999), f"Transcription… {int(seg.end // 60)} min analysées")
    return {"language": info.language, "segments": out}
