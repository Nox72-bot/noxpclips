"""IA gratuite optionnelle : Ollama (local), Gemini ou Groq (paliers gratuits).

Si rien n'est disponible, NOXPclips fonctionne quand même avec ses heuristiques.
"""
from __future__ import annotations

import json
import logging
import re

import httpx

log = logging.getLogger("noxp.llm")


class NoLLM(RuntimeError):
    pass


def _ollama_ok(settings: dict) -> bool:
    try:
        r = httpx.get(settings["ollama_url"].rstrip("/") + "/api/tags", timeout=2)
        if r.status_code != 200:
            return False
        names = [m.get("name", "") for m in r.json().get("models", [])]
        want = settings["ollama_model"]
        return any(n == want or n.split(":")[0] == want.split(":")[0] for n in names)
    except httpx.HTTPError:
        return False


def available_engine(settings: dict) -> str:
    eng = settings.get("ai_engine", "auto")
    if eng == "heuristic":
        return "heuristic"
    if eng == "ollama":
        return "ollama" if _ollama_ok(settings) else "heuristic"
    if eng == "gemini":
        return "gemini" if settings.get("gemini_api_key") else "heuristic"
    if eng == "groq":
        return "groq" if settings.get("groq_api_key") else "heuristic"
    # auto : local d'abord, puis cloud gratuit
    if _ollama_ok(settings):
        return "ollama"
    if settings.get("gemini_api_key"):
        return "gemini"
    if settings.get("groq_api_key"):
        return "groq"
    return "heuristic"


def chat(settings: dict, system: str, user: str, engine: str | None = None, timeout: float = 180) -> str:
    engine = engine or available_engine(settings)
    if engine == "ollama":
        r = httpx.post(
            settings["ollama_url"].rstrip("/") + "/api/chat",
            json={"model": settings["ollama_model"], "stream": False, "format": "json",
                  "options": {"temperature": 0.4, "num_ctx": 8192},
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()["message"]["content"]
    if engine == "gemini":
        model = settings.get("gemini_model") or "gemini-2.5-flash"
        r = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": settings["gemini_api_key"]},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json"},
            },
            timeout=timeout,
        )
        r.raise_for_status()
        parts = r.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    if engine == "groq":
        r = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings['groq_api_key']}"},
            json={"model": settings.get("groq_model") or "llama-3.3-70b-versatile", "temperature": 0.4,
                  "response_format": {"type": "json_object"},
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    raise NoLLM("Aucune IA disponible")


def parse_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except ValueError:
        m = re.search(r"(\{.*\}|\[.*\])", text, re.S)
        if m:
            return json.loads(m.group(1))
        raise


RANK_SYSTEM = """Tu es un expert TikTok / YouTube Shorts / Reels qui sélectionne les extraits les plus viraux
de lives et de vidéos. Tu notes chaque extrait honnêtement (0-100) selon 4 axes :
- viral : potentiel de vues (accroche immédiate, émotion, moment partageable, se comprend sans contexte)
- funny : à quel point c'est drôle
- drama : tension, clash, révélation, émotion forte
- hype : moment épique, exploit, réaction folle
Tu écris en FRANÇAIS un titre court et accrocheur (max 60 caractères), une accroche à afficher
à l'écran (max 7 mots, en MAJUSCULES, 1 emoji max), une description courte (1 phrase) et 5 hashtags
pertinents. Tu peux proposer de raccourcir l'extrait (trim_start / trim_end en secondes à retirer au
début / à la fin) pour démarrer directement sur l'action.
Réponds UNIQUEMENT en JSON : {"clips":[{"id":..,"viral":..,"funny":..,"drama":..,"hype":..,
"title":"..","hook":"..","description":"..","hashtags":["#.."],"reason":"pourquoi ce clip va marcher",
"trim_start":0,"trim_end":0}]}"""


def rank_clips(settings: dict, candidates: list[dict], *, genre: str, prompt: str,
               source_title: str, engine: str) -> dict[str, dict]:
    """Retourne {id: {...}} pour les candidats évalués par le LLM."""
    out: dict[str, dict] = {}
    batch = 8 if engine == "ollama" else 12
    for i in range(0, len(candidates), batch):
        chunk = candidates[i:i + batch]
        items = []
        for c in chunk:
            items.append({
                "id": c["id"],
                "duree_s": round(c["end"] - c["start"]),
                "transcription": c["text"][:1500] or "(pas de parole — gameplay / action)",
                "signaux": {"energie": round(c["scores"]["viral"], 2), "pic_chat": c.get("chat_peak", False)},
            })
        user = (
            f"Vidéo source : « {source_title} »\nCatégorie : {genre}\n"
            + (f"Demande du créateur : {prompt}\n" if prompt else "")
            + "Extraits candidats :\n" + json.dumps(items, ensure_ascii=False)
        )
        try:
            data = parse_json(chat(settings, RANK_SYSTEM, user, engine=engine))
            clips = data.get("clips", data) if isinstance(data, dict) else data
            for item in clips or []:
                if isinstance(item, dict) and str(item.get("id")) in {c["id"] for c in chunk}:
                    out[str(item["id"])] = item
        except Exception as e:  # on garde les heuristiques en cas d'erreur
            log.warning("Classement IA indisponible (%s) : %s", engine, e)
            break
    return out


def translate_lines(settings: dict, lines: list[str], target: str, engine: str) -> list[str]:
    system = ("Tu traduis des sous-titres de vidéos courtes. Garde le ton oral et le même nombre "
              'de lignes. Réponds en JSON : {"lines":[...]}')
    user = f"Langue cible : {target}\n" + json.dumps({"lines": lines}, ensure_ascii=False)
    data = parse_json(chat(settings, system, user, engine=engine))
    res = data.get("lines") if isinstance(data, dict) else data
    if not isinstance(res, list) or len(res) != len(lines):
        raise ValueError("traduction incomplète")
    return [str(x) for x in res]
