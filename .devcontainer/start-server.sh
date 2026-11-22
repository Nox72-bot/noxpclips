#!/bin/bash
# Démarre NOXPclips en arrière-plan à chaque ouverture du Codespace.
cd "$(dirname "$0")/.."
if [ -n "$CODESPACE_NAME" ]; then
  export NOXP_PUBLIC_URL="https://${CODESPACE_NAME}-8000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
fi
pkill -f "uvicorn app.main:app" 2>/dev/null || true
setsid nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  --proxy-headers --forwarded-allow-ips='*' > /tmp/noxpclips.log 2>&1 < /dev/null &
echo "✅ NOXPclips démarre sur le port 8000 (onglet « Ports » → globe 🌐 pour l'ouvrir)"
echo "   Journal : tail -f /tmp/noxpclips.log"
