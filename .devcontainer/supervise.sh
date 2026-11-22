#!/bin/bash
# Gardien : relance NOXPclips automatiquement s'il s'arrête (plantage, manque de mémoire…).
cd "$(dirname "$0")/.."
while true; do
  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
  code=$?
  echo "⚠️ $(date '+%H:%M:%S') NOXPclips s'est arrêté (code $code) — redémarrage dans 3 s"
  sleep 3
done
