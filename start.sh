#!/bin/bash
# NOXPclips — lancement Linux / serveur (nécessite python3 et ffmpeg).
cd "$(dirname "$0")"
set -e
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'
