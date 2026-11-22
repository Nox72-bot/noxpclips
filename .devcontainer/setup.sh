#!/bin/bash
# Installation unique à la création du Codespace (5 à 8 minutes).
# Chaque étape continue même si la précédente échoue, pour ne jamais bloquer le démarrage.
cd "$(dirname "$0")/.."
echo "▶ Installation de NOXPclips (Python)…"
pip install --user -q -r requirements.txt || echo "⚠️ pip a rencontré une erreur"
echo "▶ Installation de ffmpeg et des polices…"
sudo apt-get update -qq || echo "⚠️ apt-get update incomplet (on continue)"
sudo apt-get install -y -qq --no-install-recommends ffmpeg fonts-noto-color-emoji fontconfig > /dev/null \
  || echo "⚠️ ffmpeg non installé"
echo "▶ Téléchargement du modèle de transcription Whisper…"
python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')" \
  || echo "⚠️ modèle Whisper non téléchargé (il le sera au premier projet)"
if command -v ffmpeg >/dev/null; then
  echo "✅ Installation terminée"
else
  echo "❌ ffmpeg manquant : relance bash .devcontainer/setup.sh"
fi
