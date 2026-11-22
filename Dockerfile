# NOXPclips — image pour Hugging Face Spaces (gratuit) ou n'importe quel serveur Docker.
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg fonts-noto-color-emoji fontconfig ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Hugging Face exécute le conteneur avec l'utilisateur 1000
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/user/.cache/huggingface \
    NOXP_DATA_DIR=/home/user/app/data \
    NOXP_WHISPER_MODEL=small
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Modèle Whisper pré-téléchargé : le premier traitement démarre tout de suite
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"

COPY --chown=user . .
RUN mkdir -p data

EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers --forwarded-allow-ips='*'"]
