#!/bin/bash
# Démarre NOXPclips en arrière-plan à chaque ouverture du Codespace.
cd "$(dirname "$0")/.."
if [ -n "$CODESPACE_NAME" ]; then
  export NOXP_PUBLIC_URL="https://${CODESPACE_NAME}-8000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
fi
# Installation manquante (création interrompue) : on la termine d'abord
if ! command -v ffmpeg >/dev/null || ! python -c "import fastapi, faster_whisper" 2>/dev/null; then
  bash .devcontainer/setup.sh
fi
# yt-dlp suit les changements de YouTube : on prend toujours la dernière version
pip install --user -q -U yt-dlp 2>/dev/null || true
pkill -f "uvicorn app.main:app" 2>/dev/null || true
setsid nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  --proxy-headers --forwarded-allow-ips='*' > /tmp/noxpclips.log 2>&1 < /dev/null &
sleep 4
if pgrep -f "uvicorn app.main:app" >/dev/null; then
  echo "✅ NOXPclips tourne sur le port 8000 (onglet « Ports » → lien de la ligne 8000)"
else
  echo "❌ NOXPclips n'a pas démarré. Voici l'erreur :"
  tail -20 /tmp/noxpclips.log
fi
