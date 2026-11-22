#!/bin/bash
# NOXPclips — lancement sur Mac (double-clique sur ce fichier).
cd "$(dirname "$0")"
set -e
echo "▶ NOXPclips"
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew n'est pas installé. Installe-le depuis https://brew.sh puis relance ce fichier."
  read -r -p "Appuie sur Entrée pour fermer…"; exit 1
fi
command -v ffmpeg >/dev/null 2>&1 || brew install ffmpeg
command -v python3.12 >/dev/null 2>&1 || brew install python@3.12
if [ ! -d .venv ]; then
  python3.12 -m venv .venv
fi
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
# Encodage vidéo matériel de la puce Apple (bien plus rapide)
export NOXP_ENCODER="${NOXP_ENCODER:-h264_videotoolbox}"
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "IP-du-Mac")
echo ""
echo "✅ NOXPclips est lancé !"
echo "   Sur ce Mac        : http://localhost:8000"
echo "   iPhone / iPad     : http://$IP:8000  (même Wi-Fi)"
echo "   Laisse cette fenêtre ouverte pendant que tu utilises NOXPclips."
echo ""
(sleep 2 && open "http://localhost:8000") &
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
