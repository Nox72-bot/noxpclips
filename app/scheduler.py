"""Planificateur : publie les posts programmés à l'heure prévue."""
from __future__ import annotations

import logging
import threading
import time
import traceback

from . import db
from .config import PROJECTS_DIR
from .social import platforms
from .social.browser_post import BrowserBusy

log = logging.getLogger("noxp.scheduler")
_started = False
_publish_lock = threading.Lock()


def start() -> None:
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_loop, name="noxp-scheduler", daemon=True).start()


def _loop() -> None:
    while True:
        try:
            tick()
        except Exception:  # noqa: BLE001
            log.error("Planificateur : %s", traceback.format_exc())
        time.sleep(20)


def tick() -> None:
    now = time.time()
    # Posts manuels (réseau non connecté) : on les passe en « à publier »
    db.query("UPDATE posts SET status='due' WHERE status='reminder' AND scheduled_at<=?", (now,))
    # YouTube programmé nativement : marqué publié une fois l'heure passée
    db.query("UPDATE posts SET status='published', published_at=scheduled_at "
             "WHERE status='scheduled_on_platform' AND scheduled_at<=?", (now,))
    # YouTube : on envoie tout de suite les posts lointains (YouTube publiera à l'heure dite,
    # même si NOXPclips est éteint)
    early = db.query("SELECT * FROM posts WHERE status='scheduled' AND platform='youtube' AND scheduled_at>? "
                     "AND account_id NOT IN (SELECT id FROM accounts WHERE tokens LIKE '%\"method\": \"browser\"%')",
                     (now + 20 * 60,))
    due = db.query("SELECT * FROM posts WHERE status='scheduled' AND scheduled_at<=? ORDER BY scheduled_at",
                   (now,))
    for post in early + due:
        publish_post(post["id"])
    # Bot d'inspiration TikTok : un passage par jour si activé
    from . import scout

    scout.maybe_auto_run()


def publish_post(post_id: str) -> dict:
    with _publish_lock:
        post = db.get("posts", post_id)
        if not post or post["status"] not in ("scheduled", "failed", "due", "reminder"):
            return post or {}
        clip = db.get("clips", post["clip_id"])
        account = db.get("accounts", post["account_id"]) if post.get("account_id") else None
        if not clip or clip.get("status") != "done":
            db.update("posts", post_id, status="failed", error="Clip introuvable ou pas encore prêt.")
            return db.get("posts", post_id)
        if not account:
            db.update("posts", post_id, status="due")
            return db.get("posts", post_id)
        db.update("posts", post_id, status="publishing", error=None)
        video = PROJECTS_DIR / clip["project_id"] / "clips" / clip["file"]
        try:
            res = platforms.publish(post, clip, account, video, db.get_settings())
            db.update("posts", post_id, status=res.get("status", "published"), result=res,
                      published_at=time.time() if res.get("status") == "published" else None)
        except BrowserBusy as e:  # navigateur occupé (connexion en cours) : nouvel essai au prochain passage
            db.update("posts", post_id, status="scheduled", error=str(e))
        except Exception as e:  # noqa: BLE001
            log.warning("Publication échouée %s : %s", post_id, e)
            db.update("posts", post_id, status="failed", error=str(e)[:1500])
        return db.get("posts", post_id)
