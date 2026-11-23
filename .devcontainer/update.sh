#!/bin/bash
# Met NOXPclips à jour (dernière version de GitHub) puis le redémarre.
# Usage : bash .devcontainer/update.sh
cd "$(dirname "$0")/.."
echo "▶ Récupération de la dernière version…"
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "  (modifications locales mises de côté avec git stash)"
  git stash push -m "noxp-update-$(date +%s)" >/dev/null
fi
git checkout -q main 2>/dev/null || true
if git pull -q origin main; then
  echo "✅ Version : $(git log -1 --format='%h — %s' | cut -c1-90)"
else
  echo "❌ git pull a échoué : envoie une capture de ce terminal."
  exit 1
fi
bash .devcontainer/start-server.sh
