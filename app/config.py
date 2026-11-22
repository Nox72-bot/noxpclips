"""Chemins et réglages globaux de NOXPclips."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("NOXP_DATA_DIR", ROOT / "data")).resolve()
PROJECTS_DIR = DATA_DIR / "projects"
UPLOADS_DIR = DATA_DIR / "uploads"
BRAND_DIR = DATA_DIR / "brand"
DB_PATH = DATA_DIR / "noxpclips.db"
STATIC_DIR = ROOT / "static"
FONTS_DIR = ROOT / "assets" / "fonts"

for d in (DATA_DIR, PROJECTS_DIR, UPLOADS_DIR, BRAND_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Mot de passe d'accès (fortement conseillé quand le site est en ligne)
PASSWORD = os.environ.get("NOXP_PASSWORD", "")
SECRET_KEY = os.environ.get("NOXP_SECRET", "") or (PASSWORD + "-noxp-secret")

# Réglages modifiables depuis l'interface (stockés en base), avec valeurs par défaut.
DEFAULT_SETTINGS: dict = {
    # IA
    "ai_engine": "auto",  # auto | heuristic | ollama | gemini | groq
    "ollama_url": os.environ.get("OLLAMA_URL", "http://localhost:11434"),
    "ollama_model": "qwen2.5:7b",
    "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
    "gemini_model": "gemini-2.5-flash",
    "groq_api_key": os.environ.get("GROQ_API_KEY", ""),
    "groq_model": "llama-3.3-70b-versatile",
    # Transcription
    "whisper_model": os.environ.get("NOXP_WHISPER_MODEL", "small"),
    # Rendu
    "video_encoder": os.environ.get("NOXP_ENCODER", "libx264"),
    "render_preset": "veryfast",
    # Téléchargement
    "ytdlp_cookies": "",  # chemin vers cookies.txt (contournement anti-bot YouTube)
    # URL publique (pour les redirections OAuth des réseaux sociaux)
    "public_url": os.environ.get("NOXP_PUBLIC_URL", ""),
    # Applis développeur des réseaux
    "youtube_client_id": os.environ.get("YOUTUBE_CLIENT_ID", ""),
    "youtube_client_secret": os.environ.get("YOUTUBE_CLIENT_SECRET", ""),
    "tiktok_client_key": os.environ.get("TIKTOK_CLIENT_KEY", ""),
    "tiktok_client_secret": os.environ.get("TIKTOK_CLIENT_SECRET", ""),
    "instagram_app_id": os.environ.get("INSTAGRAM_APP_ID", ""),
    "instagram_app_secret": os.environ.get("INSTAGRAM_APP_SECRET", ""),
    # Kit de marque
    "brand": {
        "name": "Mon kit de marque",
        "logo": "",  # chemin relatif dans data/brand
        "logo_position": "top-right",  # top-left | top-right | bottom-left | bottom-right
        "logo_opacity": 0.85,
        "logo_size": 0.18,  # fraction de la largeur
        "caption_style": "neon",
        "highlight_color": "",  # vide = couleur du style choisi
        "text_color": "",
        "caption_position": "middle",  # top | middle | bottom
        "font": "",  # vide = police du style
        "uppercase": True,
        "outro_text": "",
    },
}

SECRET_SETTING_KEYS = {
    "gemini_api_key",
    "groq_api_key",
    "youtube_client_secret",
    "tiktok_client_secret",
    "instagram_app_secret",
}
