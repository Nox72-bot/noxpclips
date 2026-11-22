#!/bin/bash
# Installation unique à la création du Codespace (5 à 8 minutes).
set -e
echo "▶ Installation de ffmpeg et des polices…"
sudo apt-get update -qq
sudo apt-get install -y -qq --no-install-recommends ffmpeg fonts-noto-color-emoji fontconfig > /dev/null
echo "▶ Installation de NOXPclips…"
pip install --user -q -r requirements.txt
echo "▶ Téléchargement du modèle de transcription Whisper…"
python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"
echo "✅ Installation terminée"
