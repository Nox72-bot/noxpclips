"""Tendances actuelles (TikTok / web) pour choisir les clips qui surfent sur ce qui buzze en ce moment.

L'algorithme de TikTok n'est pas public et TikTok n'a pas d'API de tendances gratuite. NOXPclips combine donc :
  1. Gemini + recherche Google (gratuit avec la clé Gemini) : hashtags, sujets et formats tendance sur TikTok
     cette semaine pour la niche de la vidéo ;
  2. Google Trends (flux RSS public, sans clé) : ce que les gens recherchent aujourd'hui dans le pays ;
  3. des formats « toujours tendance » par niche, en secours.
Les résultats sont gardés 6 h en cache pour ne pas épuiser les quotas gratuits.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
import time
import unicodedata
import xml.etree.ElementTree as ET

import httpx

from ..config import DATA_DIR
from . import llm

log = logging.getLogger("noxp.trends")

CACHE = DATA_DIR / "trends_cache.json"
TTL = 6 * 3600

NICHES = {
    "gta": "GTA / GTA RP / GTA 6 (clips de stream)",
    "gaming": "gaming / clips de streamers",
    "concept": "vidéos concept YouTube entre potes (défis, jeux, réactions)",
    "entertainment": "divertissement / humour",
    "reaction": "vidéos de réaction",
    "sports": "sport",
    "lifestyle": "lifestyle / vlog",
    "podcast": "podcasts / interviews",
    "humor": "humour / sketchs",
    "irl": "streams IRL",
    "education": "éducation / vulgarisation",
    "news": "actualité",
    "marketing": "business / marketing",
}

# Formats qui marchent durablement sur TikTok, par niche (secours si aucune source en ligne ne répond)
EVERGREEN = {
    "gta": {"keywords": ["gta 6", "rp", "police", "course-poursuite", "braquage", "crash", "bug", "fail", "prison",
                         "trahison", "chase", "cops", "heist", "glitch"],
            "hashtags": ["#gta6", "#gtarp", "#gta5", "#gtaonline", "#gaming"],
            "formats": ["Fail ou bug absurde en 1 s", "Course-poursuite avec la police", "Réplique RP culte",
                        "Réaction exagérée du streamer"]},
    "gaming": {"keywords": ["clutch", "rage", "fail", "bug", "glitch", "one shot", "victoire", "top 1", "win"],
               "hashtags": ["#gaming", "#twitch", "#streamer", "#clip", "#fyp"],
               "formats": ["Clutch impossible", "Rage du streamer", "Fail inattendu"]},
    "concept": {"keywords": ["défi", "challenge", "perdu", "gage", "fou rire", "vs", "1 contre", "dernier"],
                "hashtags": ["#concept", "#challenge", "#humour", "#youtube", "#fyp"],
                "formats": ["Fou rire contagieux", "Retournement de situation", "Gage malaisant"]},
}
DEFAULT_EVERGREEN = {"keywords": [], "hashtags": ["#fyp", "#pourtoi", "#viral"], "formats": []}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9#]+", " ", s).strip()


def _load_cache() -> dict:
    try:
        return json.loads(CACHE.read_text())
    except (OSError, ValueError):
        return {}


def _save_cache(data: dict) -> None:
    try:
        CACHE.write_text(json.dumps(data, ensure_ascii=False))
    except OSError:
        pass


TRENDS_PROMPT = """Tu es analyste des tendances TikTok. Nous sommes le __DATE__.
Cherche sur le web (recherche Google) ce qui est TENDANCE SUR TIKTOK CETTE SEMAINE en __COUNTRY__ pour la niche :
« __NICHE__ ».
Je veux des éléments concrets et récents (sorties de jeux, mises à jour, mèmes, sons, défis, polémiques, créateurs
qui buzzent), pas des généralités. Réponds UNIQUEMENT en JSON :
{"hashtags":["#..", ...10 max], "keywords":["mot-clé ou expression courte qu'on pourrait entendre dans la vidéo", ...15 max],
 "formats":["format de clip qui marche en ce moment, 1 phrase courte", ...5 max]}"""


def _gemini_trends(settings: dict, niche: str, country: str) -> tuple[dict, list[str]]:
    """Gemini avec la recherche Google intégrée (« grounding »). Renvoie (tendances, sources)."""
    headers = {"x-goog-api-key": settings["gemini_api_key"]}
    prompt = (TRENDS_PROMPT.replace("__DATE__", dt.date.today().isoformat())
              .replace("__COUNTRY__", country).replace("__NICHE__", niche))
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "tools": [{"google_search": {}}], "generationConfig": {"temperature": 0.3}}
    models = [settings.get("gemini_model") or llm.GEMINI_DEFAULT]
    models += [m for m in llm._gemini_models(headers) if m not in models][:2]
    last = None
    for model in models:
        r = llm._with_retries(lambda m=model: httpx.post(f"{llm.GEMINI_BASE}/models/{m}:generateContent",
                                                         headers=headers, json=body, timeout=90), attempts=2)
        if r.status_code >= 400:
            last = r
            continue
        cand = (r.json().get("candidates") or [{}])[0]
        text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []))
        data = llm.parse_json(text)
        chunks = (cand.get("groundingMetadata") or {}).get("groundingChunks") or []
        sources = [c["web"].get("title", "") for c in chunks if isinstance(c, dict) and c.get("web")]
        return data if isinstance(data, dict) else {}, [s for s in sources if s][:8]
    if last is not None:
        llm._check(last, "Gemini (recherche)")
    return {}, []


def _google_trends(geo: str) -> list[str]:
    """Recherches du jour sur Google (flux RSS public, sans clé)."""
    r = httpx.get("https://trends.google.com/trending/rss", params={"geo": geo}, timeout=20,
                  headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for item in root.iter("item"):
        t = item.findtext("title")
        if t:
            out.append(t.strip())
    return out[:40]


def get_trends(settings: dict, genre: str, lang: str, force: bool = False) -> dict:
    """Tendances pour une niche : {hashtags, keywords, formats, web, sources, updated}."""
    key = f"{genre}:{lang}"
    cache = _load_cache()
    hit = cache.get(key)
    if hit and not force and time.time() - hit.get("updated", 0) < TTL:
        return hit
    country, geo = ("France", "FR") if lang == "fr" else ("États-Unis", "US")
    ever = EVERGREEN.get(genre, DEFAULT_EVERGREEN)
    res = {"hashtags": [], "keywords": [], "formats": [], "web": [], "sources": [], "errors": []}
    if settings.get("gemini_api_key"):
        try:
            data, sources = _gemini_trends(settings, NICHES.get(genre, genre), country)
            res["hashtags"] = [("#" + str(h).lstrip("#").replace(" ", ""))[:40] for h in data.get("hashtags") or []][:10]
            res["keywords"] = [str(k)[:60] for k in data.get("keywords") or []][:15]
            res["formats"] = [str(f)[:140] for f in data.get("formats") or []][:5]
            res["sources"] = ["TikTok (via recherche Google)"] + sources
        except Exception as e:  # noqa: BLE001
            log.warning("Tendances Gemini indisponibles : %s", e)
            res["errors"].append(f"Gemini : {str(e)[:160]}")
    try:
        res["web"] = _google_trends(geo)
        res["sources"].append(f"Google Trends {geo}")
    except Exception as e:  # noqa: BLE001
        log.warning("Google Trends indisponible : %s", e)
        res["errors"].append(f"Google Trends : {str(e)[:120]}")
    # « toujours tendance » de la niche : gardés à part (hashtags de secours), jamais comptés comme tendance du moment
    res["evergreen_hashtags"] = [h for h in ever["hashtags"] if h.lower() not in {x.lower() for x in res["hashtags"]}]
    if not res["formats"]:
        res["formats"] = list(ever["formats"])
    res["live"] = any(s.startswith(("TikTok", "Google")) for s in res["sources"])
    res["updated"] = time.time()
    if res["live"]:  # on ne garde pas en cache un résultat « hors ligne »
        cache[key] = res
        _save_cache(cache)
    return res


def _terms(trends: dict) -> list[tuple[str, str, float]]:
    """(terme normalisé, libellé affiché, poids)."""
    out = []
    for h in trends.get("hashtags", []):
        t = _norm(h.lstrip("#"))
        if len(t) >= 3:
            out.append((t, h, 1.0))
    for k in trends.get("keywords", []):
        t = _norm(k)
        if len(t) >= 3:
            out.append((t, k, 1.0))
    for w in trends.get("web", []):
        t = _norm(w)
        if len(t) >= 4:
            out.append((t, w, 1.2))  # recherche du jour : rare mais très fort quand ça matche
    return out


def match(text: str, trends: dict) -> tuple[float, list[str]]:
    """Force de la tendance (0..1) et libellés trouvés dans le texte d'un extrait."""
    if not trends or not text:
        return 0.0, []
    hay = f" {_norm(text)} "
    squeezed = hay.replace(" ", "")
    found, score = [], 0.0
    for term, label, w in _terms(trends):
        flat = term.replace(" ", "")
        long_enough = len(flat) >= 5 or (len(flat) >= 4 and any(ch.isdigit() for ch in flat))  # « gta6 » ≈ « gta 6 »
        hit = f" {term} " in hay or (long_enough and flat in squeezed)
        if hit and label not in found:
            found.append(label)
            score += w
    return min(1.0, score / 2.0), found[:4]


def hashtags_for(found: list[str], trends: dict) -> list[str]:
    """Hashtags tendance à ajouter à un clip (ceux qui collent à son contenu d'abord)."""
    tags = [f if f.startswith("#") else "#" + re.sub(r"\W+", "", f.lower()) for f in found]
    pool = (trends.get("hashtags") or [])[:2] + (trends.get("evergreen_hashtags") or [])[:2]
    out, seen = [], set()
    for t in [t for t in tags if len(t) > 2][:2] + pool:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out[:4]
