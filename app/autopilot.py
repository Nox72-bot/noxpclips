"""Pilote automatique : chaque vidéo ajoutée devient des clips qui se programment et se publient tout seuls.

Quand un projet est terminé, ses meilleurs clips sont placés sur les prochains créneaux libres de chaque compte
connecté (heures de publication choisies, N posts par jour et par compte). Le planificateur publie ensuite à l'heure.
Un clip n'est jamais programmé deux fois sur le même compte.
"""
from __future__ import annotations

import datetime as dt
import logging
import time
from zoneinfo import ZoneInfo

from . import db

log = logging.getLogger("noxp.autopilot")

DEFAULT = {
    "enabled": False,
    "accounts": [],          # vide = tous les comptes connectés
    "times": ["12:30", "18:30", "21:00"],  # heures de pointe TikTok / Reels / Shorts (heure locale)
    "per_day": 2,            # posts par jour et par compte
    "min_score": 70,         # ne publie que les clips assez viraux
    "max_per_video": 5,      # clips publiés au maximum par vidéo
    "timezone": "Europe/Paris",
}
PLATFORM_OFFSET_MIN = {"tiktok": 0, "youtube": 6, "instagram": 12}  # étale le travail du robot de publication


def config() -> dict:
    cfg = dict(DEFAULT)
    cfg.update(db.get_settings().get("autopilot") or {})
    return cfg


def _tz(cfg: dict) -> ZoneInfo:
    try:
        return ZoneInfo(cfg.get("timezone") or "Europe/Paris")
    except Exception:  # noqa: BLE001
        return ZoneInfo("Europe/Paris")


def _times(cfg: dict) -> list[tuple[int, int]]:
    out = []
    for t in cfg.get("times") or DEFAULT["times"]:
        try:
            h, m = str(t).split(":")
            out.append((max(0, min(23, int(h))), max(0, min(59, int(m)))))
        except ValueError:
            continue
    return sorted(set(out)) or [(12, 30), (18, 30), (21, 0)]


def target_accounts(cfg: dict | None = None) -> list[dict]:
    cfg = cfg or config()
    accs = db.query("SELECT * FROM accounts ORDER BY created_at")
    wanted = set(cfg.get("accounts") or [])
    return [a for a in accs if not wanted or a["id"] in wanted]


def _slots(cfg: dict, start: float, days: int = 60):
    """Créneaux à venir (horodatage UTC), dans l'ordre, à partir de `start`."""
    tz = _tz(cfg)
    day = dt.datetime.fromtimestamp(start, tz).date()
    times = _times(cfg)
    for d in range(days):
        date = day + dt.timedelta(days=d)
        for h, m in times:
            ts = dt.datetime(date.year, date.month, date.day, h, m, tzinfo=tz).timestamp()
            if ts >= start:
                yield ts


def _taken(account_id: str) -> list[float]:
    rows = db.query("SELECT scheduled_at FROM posts WHERE account_id=? AND status NOT IN ('failed')", (account_id,))
    return [r["scheduled_at"] for r in rows if r["scheduled_at"]]


def _day_key(ts: float, cfg: dict) -> str:
    return dt.datetime.fromtimestamp(ts, _tz(cfg)).strftime("%Y-%m-%d")


def schedule_clips(clips: list[dict], cfg: dict | None = None, reason: str = "") -> int:
    """Place des clips sur les prochains créneaux libres de chaque compte. Renvoie le nombre de posts créés."""
    cfg = cfg or config()
    accounts = target_accounts(cfg)
    if not accounts or not clips:
        return 0
    per_day = max(1, min(10, int(cfg.get("per_day") or 2)))
    created = 0
    start = time.time() + 20 * 60  # premier créneau au plus tôt dans 20 min
    for acc in accounts:
        taken = _taken(acc["id"])
        per_day_count: dict[str, int] = {}
        for t in taken:
            k = _day_key(t, cfg)
            per_day_count[k] = per_day_count.get(k, 0) + 1
        offset = PLATFORM_OFFSET_MIN.get(acc["platform"], 0) * 60
        already = {r["clip_id"] for r in db.query("SELECT clip_id FROM posts WHERE account_id=?", (acc["id"],))}
        queue = [c for c in clips if c["id"] not in already]
        slots = _slots(cfg, start)
        for clip in queue:
            for ts in slots:
                ts += offset
                k = _day_key(ts, cfg)
                if per_day_count.get(k, 0) >= per_day:
                    continue
                if any(abs(ts - t) < 15 * 60 for t in taken):
                    continue
                db.insert("posts", {"clip_id": clip["id"], "platform": acc["platform"], "account_id": acc["id"],
                                    "scheduled_at": ts, "caption": "", "privacy": "public", "status": "scheduled",
                                    "result": {"autopilot": True, "reason": reason}})
                taken.append(ts)
                per_day_count[k] = per_day_count.get(k, 0) + 1
                created += 1
                break
    if created:
        log.info("Pilote automatique : %d posts programmés (%s)", created, reason)
    return created


def best_clips(project_id: str | None = None, cfg: dict | None = None) -> list[dict]:
    cfg = cfg or config()
    min_score = int(cfg.get("min_score") or 0)
    sql = "SELECT * FROM clips WHERE status='done' AND score>=?"
    params: tuple = (min_score,)
    if project_id:
        sql += " AND project_id=?"
        params += (project_id,)
    clips = db.query(sql + " ORDER BY score DESC", params)
    if project_id:
        return clips[: max(1, int(cfg.get("max_per_video") or 5))]
    # tous les projets : les meilleurs de chaque vidéo, puis par score
    by_proj: dict[str, list] = {}
    for c in clips:
        by_proj.setdefault(c["project_id"], []).append(c)
    keep = [c for lst in by_proj.values() for c in lst[: max(1, int(cfg.get("max_per_video") or 5))]]
    return sorted(keep, key=lambda c: c["score"], reverse=True)


def on_project_done(project: dict) -> int:
    """Appelé à la fin du montage d'un projet."""
    cfg = config()
    opts = project.get("options") or {}
    if not cfg.get("enabled") or opts.get("autopost") is False:
        return 0
    n = schedule_clips(best_clips(project["id"], cfg), cfg, reason=project.get("title") or "")
    if n:
        meta = dict(project.get("meta") or {})
        meta["autopilot_posts"] = n
        db.update("projects", project["id"], meta=meta)
    return n


def fill_now() -> int:
    """Programme tous les bons clips existants qui ne le sont pas encore."""
    cfg = config()
    return schedule_clips(best_clips(None, cfg), cfg, reason="remplissage manuel")


def overview() -> dict:
    cfg = config()
    now = time.time()
    upcoming = db.query("SELECT * FROM posts WHERE account_id IS NOT NULL AND (status IN ('scheduled','publishing','failed') "
                        "OR (status IN ('published','scheduled_on_platform') AND COALESCE(published_at, scheduled_at)>?)) "
                        "ORDER BY scheduled_at LIMIT 200", (now - 3 * 86400,))
    targets = [a["id"] for a in target_accounts(cfg)]
    planned = {(r["clip_id"], r["account_id"]) for r in db.query("SELECT clip_id, account_id FROM posts")}
    waiting = sum(1 for c in best_clips(None, cfg) if any((c["id"], a) not in planned for a in targets))
    return {"config": cfg, "accounts": [{"id": a["id"], "platform": a["platform"], "name": a["name"]}
                                        for a in db.query("SELECT * FROM accounts ORDER BY created_at")],
            "posts": upcoming, "candidates": waiting}
