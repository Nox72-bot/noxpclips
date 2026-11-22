---
title: NOXPclips
emoji: 🎬
colorFrom: green
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# NOXPclips

Transforme tes vidéos YouTube, lives YouTube et VOD Twitch en **clips viraux au format TikTok 9:16**,
avec sous-titres animés, accroche, emojis, zoom auto… puis **publie-les ou programme-les** sur TikTok,
Instagram Reels et YouTube Shorts depuis un calendrier.

**0 crédit, 0 token, illimité** : tout tourne sur ton propre serveur, avec des outils libres et gratuits.

## Ce que fait NOXPclips

| Étape | Comment (gratuit) |
|---|---|
| Récupère la vidéo (YouTube, live terminé, Twitch VOD/clip, ou fichier importé) | `yt-dlp` |
| Récupère le chat du live (Twitch / rediffusion YouTube) pour repérer les pics de réactions | API publique |
| Transcrit la parole mot à mot | Whisper (local, `faster-whisper`) |
| Trouve les moments **viraux, drôles, dramatiques, épiques** | Volume, cris, rires, mots-clés FR/EN, pics du chat + IA optionnelle (Ollama local, Gemini ou Groq gratuits) |
| Donne un **score viral** /99, un titre, une accroche, une description et des hashtags | IA ou heuristiques |
| Monte le clip en **1080×1920** | `ffmpeg` : recadrage sur le visage, fond flou, ou **facecam + jeu** (écran partagé) |
| Ajoute sous-titres animés (9 styles), accroche (3 styles), emojis IA, zoom auto, transitions, couleurs, nettoyage vocal, audio amélioré, logo | `ffmpeg` + `libass` + Pillow |
| Publie / programme | API officielles YouTube, TikTok, Instagram, ou partage manuel en 1 tap depuis l'iPhone/iPad |

**Langues** : vidéo en français → titres, accroches et sous-titres en français. Vidéo dans une autre
langue → titres et accroches en anglais, **sous-titres toujours traduits en français** (désactivable).

**Spécialités** :
- *Concept YouTube* (défis entre potes, jeux, réactions) : repère les fous rires et cris (même sans parole),
  les phrases cultes, et garde tout le groupe dans le cadre (fond flou) quand plusieurs personnes sont à l'écran.
- *GTA / GTA RP* : courses-poursuites, crashs, fails physiques, braquages, arrestations, clashs RP.
- Vidéos YouTube classiques : utilise la courbe **« Moments les plus revus »** de YouTube et les
  **commentaires horodatés** (« 4:32 mdr ») — les vrais avis des spectateurs.

Pas encore disponibles (affichés « Bientôt ») : motion design, B-roll IA, Auto SFX, doublage vocal,
correction du contact visuel.

---

## Option A : en ligne et gratuit, depuis ton iPad (GitHub Codespaces)

Un petit ordinateur dans le cloud fourni par GitHub, piloté depuis Safari. Gratuit : **60 heures par mois**
(2 processeurs, 8 Go de mémoire), sans carte bancaire. Tes clips et réglages sont conservés.

1. Sur la page du dépôt GitHub : bouton vert **Code** → onglet **Codespaces** → **Create codespace on main**.
2. La première fois, l'installation dure 5 à 8 minutes (ffmpeg, Whisper…). Laisse l'onglet ouvert.
3. Quand c'est prêt, ouvre l'onglet **Ports** en bas, ligne **NOXPclips (8000)** → icône globe 🌐.
   NOXPclips s'ouvre dans un nouvel onglet : **Partager → Sur l'écran d'accueil** pour l'installer.
4. Une seule fois : sur [github.com/settings/codespaces](https://github.com/settings/codespaces), règle
   **Default idle timeout** sur **240 minutes** (sinon le Codespace s'arrête après 30 min sans activité).

Les fois suivantes : va sur [github.com/codespaces](https://github.com/codespaces) et rouvre ton Codespace ;
NOXPclips redémarre tout seul, à la même adresse.

À savoir :
- Le port est **privé** : seul ton compte GitHub peut ouvrir NOXPclips. Pas besoin de mot de passe.
- Quand le Codespace est arrêté, rien ne tourne. Les vidéos programmées sur **YouTube** partent quand même
  (envoyées à l'avance avec une date de publication) ; pour TikTok et Instagram, rouvre le Codespace à l'heure prévue.
- Pense à arrêter le Codespace quand tu as fini (il s'arrête aussi tout seul) pour économiser tes 60 h.
- YouTube bloque parfois les téléchargements depuis les serveurs cloud : ajoute un `cookies.txt`
  (Réglages → Téléchargement) ou utilise **Importer un fichier**. Twitch fonctionne généralement.

Le `Dockerfile` permet aussi d'héberger NOXPclips sur n'importe quel serveur (Oracle Cloud Always Free,
VPS…). Hugging Face Spaces le permet aussi, mais les Spaces Docker y sont devenus payants.

## Option B : sur ton Mac (plus rapide, rien n'est effacé)

1. Installe [Homebrew](https://brew.sh) (une seule fois).
2. Télécharge ce dépôt (bouton **Code → Download ZIP**), décompresse-le.
3. Double-clique sur **`start-mac.command`** (la première fois : clic droit → Ouvrir).
4. NOXPclips s'ouvre sur `http://localhost:8000`. Depuis l'iPhone ou l'iPad sur le même Wi-Fi : l'adresse `http://IP-du-Mac:8000` s'affiche dans la fenêtre.

Sur Mac, l'encodage utilise la puce Apple (`h264_videotoolbox`), c'est très rapide.

Pour l'utiliser **hors de chez toi** et connecter TikTok/Instagram (qui exigent une adresse `https://`),
installe [Tailscale](https://tailscale.com) (gratuit) sur le Mac et l'iPhone, puis lance `tailscale serve 8000` sur le Mac :
tu obtiens une adresse `https://ton-mac.ts.net` privée. Mets-la dans **Réglages → Adresse publique**.

## Docker / autre serveur

```bash
docker build -t noxpclips .
docker run -p 7860:7860 -e NOXP_PASSWORD=motdepasse -v $PWD/data:/home/user/app/data noxpclips
```

Ou `./start.sh` sur Linux (nécessite `python3` et `ffmpeg`).

---

## IA gratuite (facultatif mais recommandé)

Sans rien configurer, NOXPclips utilise ses **heuristiques locales** (volume, cris, rires, mots-clés, chat).
Pour des titres et un classement plus malins, dans **Réglages** :

- **Ollama** (local, illimité, Mac avec 16 Go de RAM conseillés) : installe [ollama.com](https://ollama.com), puis `ollama pull qwen2.5:7b`.
- **Gemini** : clé gratuite sur [aistudio.google.com](https://aistudio.google.com/apikey).
- **Groq** : clé gratuite sur [console.groq.com](https://console.groq.com/keys).

En mode *Auto*, NOXPclips prend la première disponible. Ces IA servent aussi à **traduire les sous-titres**.

**Si tu n'as qu'un iPad** (hébergement Hugging Face), Ollama n'est pas disponible : ajoute une **clé Gemini
gratuite** dans Réglages. Elle améliore les titres et traduit les sous-titres en français sans limite
pratique. Sans clé, la traduction passe par le service gratuit MyMemory (~5 000 caractères par jour,
soit une dizaine de clips).

## Connecter TikTok, Instagram, YouTube

Page **Comptes sociaux** : chaque réseau a un guide pas à pas pour créer ton « application développeur »
(gratuite) et l'adresse de redirection à copier. À savoir :

- **YouTube** : tant que ton projet Google n'a pas passé l'audit gratuit de l'API YouTube, les vidéos envoyées par API sont mises en *privé* (tu les passes en public en un clic dans YouTube Studio).
- **TikTok** : sans validation de ton appli par TikTok, la publication directe est forcée en privé. Le **mode brouillon** (par défaut) envoie la vidéo dans ton appli TikTok, tu la publies en un tap.
- **Instagram** : il faut un compte professionnel (Créateur, gratuit).
- **Sans connexion** : programme un *rappel* dans le calendrier ; à l'heure prévue, le bouton **Partager** envoie le clip directement dans TikTok, Instagram, Snapchat… (iPhone / iPad).

## Structure du code

```
app/
  main.py            API FastAPI + interface
  jobs.py            file de traitement (téléchargement → transcription → analyse → montage)
  scheduler.py       publications programmées
  pipeline/
    download.py      yt-dlp + chat Twitch / YouTube
    transcribe.py    Whisper local
    analyze.py       détection des moments viraux / drôles / dramatiques / épiques
    llm.py           Ollama / Gemini / Groq (optionnels)
    faces.py         détection visage / facecam (recadrage)
    captions.py      sous-titres animés (ASS)
    overlays.py      accroche, emojis, logo (Pillow)
    render.py        montage 9:16 ffmpeg
  social/platforms.py  OAuth + publication YouTube / TikTok / Instagram
static/              interface web (PWA installable)
assets/fonts/        polices libres (licences OFL / Apache incluses)
```

Utilise NOXPclips uniquement sur des vidéos dont tu as les droits ou l'autorisation du créateur.
