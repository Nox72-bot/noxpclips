"""Discussion avec le bot NOXPclips : idées de clips, résultats du scroll TikTok, tendances, commandes.

Le bot répond avec l'IA configurée (Gemini / Groq / Ollama) en s'appuyant sur ce que NOXPclips sait :
vidéos qui cartonnent repérées par le bot TikTok, tendances, tes projets et clips. Il peut aussi agir :
lancer un scroll TikTok (avec d'autres hashtags), changer les hashtags suivis, activer le passage quotidien.
Sans IA, il comprend les demandes simples (mots-clés).
"""
from __future__ import annotations

import json
import logging
import re
import time

from . import db, scout
from .config import DATA_DIR
from .pipeline import llm

log = logging.getLogger("noxp.bot")

HISTORY = DATA_DIR / "bot_chat.json"
MAX_HISTORY = 80

SYSTEM = """Tu es « NOX », l'assistant de NOXPclips, un outil qui transforme des vidéos YouTube / Twitch en clips
TikTok, YouTube Shorts et Instagram Reels. Tu parles français, en tutoyant, de façon courte, concrète et motivante.
Ton rôle : aider le créateur à trouver quoi poster pour devenir viral, à partir des données ci-dessous
(vidéos TikTok qui cartonnent repérées par le bot, tendances, ses propres clips).
Règles :
- Ne propose JAMAIS de republier les vidéos des autres : propose des idées ORIGINALES à faire avec SES vidéos / streams.
- Cite les chiffres utiles (vues, partages, score) quand tu parles d'une vidéo repérée.
- Si tu manques de données, propose de lancer un scroll TikTok.
Actions possibles (mets null si aucune) :
- {"type":"scan","tags":["gtarp",...]} : lancer le bot qui scrolle TikTok (tags facultatifs, sans #) ;
- {"type":"set_tags","tags":[...]} : changer les hashtags suivis par défaut ;
- {"type":"auto","on":true|false} : activer / couper le passage automatique quotidien.
Pour montrer des vidéos repérées, mets leurs id dans "show" (max 4).
Réponds UNIQUEMENT en JSON : {"reply":"texte (retours à la ligne autorisés)","action":null,"show":[]}"""


def load() -> list[dict]:
    try:
        return json.loads(HISTORY.read_text())
    except (OSError, ValueError):
        return []


def _save(h: list[dict]) -> None:
    HISTORY.write_text(json.dumps(h[-MAX_HISTORY:], ensure_ascii=False))


def clear() -> None:
    HISTORY.unlink(missing_ok=True)


def _context() -> str:
    s = db.get_settings()
    data = scout.load()
    items = scout.listing(niche_only=False, limit=12)
    vids = [{"id": i["id"], "desc": i["desc"][:160], "auteur": i["author"], "source": i["source"], "niche": i.get("niche"),
             "vues": i["plays"], "partages": i["shares"], "score": i["metrics"]["score"],
             "age_h": i["metrics"]["age_h"], "pourquoi": i.get("why", ""), "idee": i.get("idea", "")} for i in items]
    clips = db.query("SELECT title, score, category, hashtags FROM clips WHERE status='done' "
                     "ORDER BY created_at DESC LIMIT 12")
    trends = {}
    try:
        cache = json.loads((DATA_DIR / "trends_cache.json").read_text())
        latest = max(cache.values(), key=lambda t: t.get("updated", 0)) if cache else {}
        trends = {k: latest.get(k) for k in ("hashtags", "keywords", "formats") if latest.get(k)}
    except (OSError, ValueError):
        pass
    st = scout.status()
    return json.dumps({
        "date": time.strftime("%Y-%m-%d"),
        "hashtags_suivis": scout.niche_tags(s), "passage_auto": bool(s.get("scout_auto")),
        "bot_tiktok": {"etat": st.get("state"), "message": st.get("message"),
                       "dernier_passage": time.strftime("%d/%m %H:%M", time.localtime(data["last_run"])) if data.get("last_run") else "jamais"},
        "videos_qui_cartonnent": vids, "tendances": trends,
        "mes_clips": [{"titre": c["title"], "score": c["score"], "type": c["category"]} for c in clips],
    }, ensure_ascii=False)


def _tags(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"#([\wÀ-ÿ]+)", text)][:6]


def _fallback(msg: str) -> dict:
    low = msg.lower()
    if re.search(r"\b(lance|scan|scroll|cherche|regarde|analyse)\b", low):
        return {"reply": "C'est parti : je scrolle TikTok et je te ramène ce qui cartonne (≈ 6 min).",
                "action": {"type": "scan", "tags": _tags(msg)}, "show": []}
    if "auto" in low and re.search(r"(désactive|coupe|stop|arr[eê]te)", low):
        return {"reply": "Passage automatique coupé.", "action": {"type": "auto", "on": False}, "show": []}
    if "auto" in low:
        return {"reply": "Passage automatique activé : je scrolle TikTok une fois par jour.", "action": {"type": "auto", "on": True}, "show": []}
    items = scout.listing(niche_only=True, limit=3) or scout.listing(niche_only=False, limit=3)
    if items:
        lines = [f"• {i['desc'][:70] or '(sans description)'} — {i['plays']:,} vues".replace(",", " ")
                 + f", score {i['metrics']['score']}"
                 + (f"\n  💡 {i['idea']}" if i.get("idea") else "") for i in items]
        return {"reply": "Voici ce qui marche le mieux en ce moment :\n" + "\n".join(lines)
                + "\n\n(Ajoute une clé Gemini gratuite dans Réglages pour que je puisse vraiment discuter avec toi.)",
                "action": None, "show": [i["id"] for i in items]}
    return {"reply": "Je n'ai pas encore de vidéos TikTok à analyser. Dis-moi « lance un scan » (tu peux ajouter des "
                     "hashtags, ex. « lance un scan #gtarp #gta6 ») et je vais scroller TikTok pour toi.",
            "action": None, "show": []}


def _act(action: dict | None) -> str:
    if not isinstance(action, dict):
        return ""
    t = action.get("type")
    tags = [str(x).lstrip("#").strip().lower() for x in action.get("tags") or [] if str(x).strip()][:6]
    if t == "scan":
        s = db.get_settings()
        if tags:
            s = {**s, "scout_tags": ", ".join(tags)}
        try:
            scout.run_async(s)
            return "🤖 Scroll TikTok lancé" + (f" sur #{', #'.join(tags)}" if tags else "") + "."
        except RuntimeError as e:
            return f"⚠️ {e}"
    if t == "set_tags" and tags:
        db.set_settings({"scout_tags": ", ".join(tags)})
        return f"✔ Hashtags suivis : #{', #'.join(tags)}."
    if t == "auto":
        on = bool(action.get("on"))
        db.set_settings({"scout_auto": on})
        return "✔ Passage quotidien activé." if on else "✔ Passage quotidien coupé."
    return ""


def _cards(ids) -> list[dict]:
    if not ids:
        return []
    by_id = {i["id"]: i for i in scout.listing(niche_only=False, limit=300)}
    out = []
    for x in list(ids)[:4]:
        i = by_id.get(str(x))
        if i:
            out.append({k: i.get(k) for k in ("id", "url", "desc", "author", "plays", "shares", "cover", "idea")}
                       | {"score": i["metrics"]["score"]})
    return out


def chat(message: str) -> dict:
    message = (message or "").strip()[:1500]
    if not message:
        raise ValueError("Message vide")
    hist = load()
    settings = db.get_settings()
    engine = llm.available_engine(settings)
    res = None
    if engine != "heuristic":
        convo = "\n".join(f"{'Créateur' if m['role'] == 'user' else 'NOX'} : {m['text'][:600]}" for m in hist[-10:])
        user = f"DONNÉES NOXPCLIPS :\n{_context()}\n\nCONVERSATION RÉCENTE :\n{convo}\n\nNOUVEAU MESSAGE DU CRÉATEUR : {message}"
        try:
            data = llm.parse_json(llm.chat(settings, SYSTEM, user, engine=engine, timeout=90))
            if isinstance(data, dict) and isinstance(data.get("reply"), str):
                res = data
        except Exception as e:  # noqa: BLE001
            log.warning("Bot : IA indisponible (%s)", e)
    if res is None:
        res = _fallback(message)
    done = _act(res.get("action"))
    reply = res["reply"].strip() + (f"\n\n{done}" if done else "")
    now = time.time()
    bot_msg = {"role": "bot", "text": reply, "at": now, "cards": _cards(res.get("show"))}
    hist += [{"role": "user", "text": message, "at": now}, bot_msg]
    _save(hist)
    return bot_msg
