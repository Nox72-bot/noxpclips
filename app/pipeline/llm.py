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
        # La clé part dans un en-tête : elle n'apparaît jamais dans une adresse ni dans un message d'erreur
        headers = {"x-goog-api-key": settings["gemini_api_key"]}
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json"},
        }

        def call(model: str) -> httpx.Response:
            return httpx.post(f"{GEMINI_BASE}/models/{model}:generateContent",
                              headers=headers, json=body, timeout=timeout)

        model = settings.get("gemini_model") or GEMINI_DEFAULT
        r = _with_retries(lambda: call(model))
        if r.status_code in (400, 404):  # modèle retiré ou renommé par Google : on prend le bon tout seul
            found = _gemini_models(headers)
            if found:
                model = found[0]
                _remember(settings, "gemini_model", model)
                r = _with_retries(lambda: call(model))
        if r.status_code in (429, 500, 503):  # modèle saturé : on essaie un autre modèle gratuit, sans l'enregistrer
            for alt in [m for m in _gemini_models(headers, include_lite=True) if m != model][:3]:
                r = _with_retries(lambda alt=alt: call(alt), attempts=1)
                if r.status_code < 400:
                    log.info("Gemini %s saturé : réponse obtenue avec %s", model, alt)
                    break
        _check(r, "Gemini")
        parts = r.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    if engine == "groq":
        headers = {"Authorization": f"Bearer {settings['groq_api_key']}"}

        def call_groq(model: str) -> httpx.Response:
            return httpx.post(
                "https://api.groq.com/openai/v1/chat/completions", headers=headers, timeout=timeout,
                json={"model": model, "temperature": 0.4, "response_format": {"type": "json_object"},
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})

        r = _with_retries(lambda: call_groq(settings.get("groq_model") or GROQ_DEFAULT))
        if r.status_code in (400, 404) and "model" in r.text.lower():
            model = _discover_groq_model(headers)
            if model:
                _remember(settings, "groq_model", model)
                r = call_groq(model)
        _check(r, "Groq")
        return r.json()["choices"][0]["message"]["content"]
    raise NoLLM("Aucune IA disponible")


GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_DEFAULT = "gemini-flash-latest"
GROQ_DEFAULT = "llama-3.3-70b-versatile"


def _check(r: httpx.Response, name: str) -> None:
    """Erreur lisible, sans jamais recopier l'adresse appelée (pas de fuite de clé)."""
    if r.status_code < 400:
        return
    try:
        msg = (r.json().get("error") or {}).get("message") or r.text
    except ValueError:
        msg = r.text
    raise RuntimeError(f"{name} a répondu {r.status_code} : {str(msg)[:200]}")


def _remember(settings: dict, key: str, value: str) -> None:
    settings[key] = value
    try:
        from .. import db

        db.set_settings({key: value})
    except Exception:  # noqa: BLE001
        pass


def _with_retries(fn, attempts: int = 3) -> httpx.Response:
    """Réessaie quand le service est momentanément saturé (429 / 500 / 503)."""
    import time

    r = fn()
    for i in range(attempts - 1):
        if r.status_code not in (429, 500, 503):
            break
        time.sleep(3 * (i + 1))
        r = fn()
    return r


def _gemini_models(headers: dict, include_lite: bool = False) -> list[str]:
    """Modèles « flash » gratuits réellement disponibles pour cette clé, du meilleur au moins bon."""
    try:
        r = httpx.get(f"{GEMINI_BASE}/models", headers=headers, params={"pageSize": 200}, timeout=20)
        r.raise_for_status()
    except httpx.HTTPError:
        return []
    names = [m["name"].split("/", 1)[-1] for m in r.json().get("models", [])
             if "generateContent" in (m.get("supportedGenerationMethods") or [])]
    bad = ("image", "tts", "audio", "live", "embedding", "exp", "preview", "thinking", "8b")
    flash = sorted([n for n in names if "flash" in n and "lite" not in n and not any(b in n for b in bad)],
                   reverse=True)
    if "gemini-flash-latest" in names:
        flash = ["gemini-flash-latest"] + [n for n in flash if n != "gemini-flash-latest"]
    if include_lite:
        flash += sorted([n for n in names if "flash" in n and "lite" in n and not any(b in n for b in bad)],
                        reverse=True)
    return flash or [n for n in names if n.startswith("gemini")]


def _discover_groq_model(headers: dict) -> str | None:
    try:
        r = httpx.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=20)
        r.raise_for_status()
    except httpx.HTTPError:
        return None
    ids = [m["id"] for m in r.json().get("data", []) if m.get("active", True)]
    for pref in ("llama-3.3-70b", "llama-4", "qwen", "llama"):
        cands = sorted([i for i in ids if pref in i and "guard" not in i and "whisper" not in i], reverse=True)
        if cands:
            return cands[0]
    return None


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
de vidéos YouTube et de lives. Tu notes chaque extrait honnêtement (0-100) selon 4 axes :
- viral : potentiel de vues (accroche immédiate, émotion, moment partageable, se comprend sans contexte)
- funny : à quel point c'est drôle
- drama : tension, clash, révélation, émotion forte
- hype : moment épique, exploit, réaction folle
__GENRE__
Tu écris en __LANG__ un titre court et accrocheur (max 60 caractères), une accroche à afficher
à l'écran (max 7 mots, en MAJUSCULES, 1 emoji max), une description courte (1 phrase) et 5 hashtags
pertinents. Tu peux proposer de raccourcir l'extrait (trim_start / trim_end en secondes à retirer au
début / à la fin) pour démarrer directement sur l'action.
Réponds UNIQUEMENT en JSON : {"clips":[{"id":..,"viral":..,"funny":..,"drama":..,"hype":..,
"title":"..","hook":"..","description":"..","hashtags":["#.."],"reason":"pourquoi ce clip va marcher (en français)",
"trend":"tendance actuelle exploitée par l'extrait, ou vide","trend_fit":0,"trim_start":0,"trim_end":0}]}"""

GENRE_HINTS = {
    "concept": ("Type de vidéo : concept YouTube entre potes (défis, jeux, réactions, style grandes chaînes "
                "françaises). Privilégie les fous rires, réactions exagérées, retournements de situation, "
                "phrases cultes et moments malaisants, avec une mise en place ET une chute compréhensibles "
                "sans avoir vu la vidéo."),
    "gta": ("Type de vidéo : GTA / GTA RP. Privilégie les courses-poursuites, crashs, fails physiques absurdes, "
            "braquages, arrestations, trahisons et clashs RP, répliques cultes. L'action doit démarrer dès "
            "la première seconde."),
    "gaming": "Type de vidéo : gaming. Privilégie les actions spectaculaires, fails, rages et réactions fortes.",
}


def _trends_block(trends: dict | None) -> str:
    if not trends:
        return ""
    parts = []
    if trends.get("hashtags"):
        parts.append("hashtags : " + " ".join(trends["hashtags"][:10]))
    if trends.get("keywords"):
        parts.append("sujets : " + ", ".join(trends["keywords"][:15]))
    if trends.get("formats"):
        parts.append("formats qui marchent : " + " | ".join(trends["formats"][:5]))
    if trends.get("web"):
        parts.append("recherches Google du jour : " + ", ".join(trends["web"][:15]))
    return ("TENDANCES ACTUELLES (TikTok / web, cette semaine) — un extrait qui colle à une tendance a beaucoup plus "
            "de chances d'être poussé par l'algorithme : augmente sa note viral, indique la tendance dans « trend », "
            "sa pertinence 0-100 dans « trend_fit » (0 si aucun lien réel, n'invente pas), et reprends les hashtags "
            "tendance pertinents. " + " ; ".join(parts) + "\n")


def rank_clips(settings: dict, candidates: list[dict], *, genre: str, prompt: str,
               source_title: str, engine: str, lang: str = "fr", trends: dict | None = None) -> dict[str, dict]:
    """Retourne {id: {...}} pour les candidats évalués par le LLM."""
    out: dict[str, dict] = {}
    system = (RANK_SYSTEM
              .replace("__LANG__", "FRANÇAIS" if lang == "fr" else "ANGLAIS (English)")
              .replace("__GENRE__", GENRE_HINTS.get(genre, "")))
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
            + _trends_block(trends)
            + "Extraits candidats :\n" + json.dumps(items, ensure_ascii=False)
        )
        try:
            data = parse_json(chat(settings, system, user, engine=engine))
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


LANG_CODES = {"français": "fr", "anglais": "en", "espagnol": "es", "allemand": "de", "italien": "it",
              "portugais": "pt", "arabe": "ar", "néerlandais": "nl", "japonais": "ja"}


def lang_code(name: str) -> str:
    return LANG_CODES.get((name or "").lower(), (name or "")[:2].lower())


def _mymemory(text: str, src: str, tgt: str) -> str:
    """Traduction gratuite sans clé (MyMemory, ~5 000 caractères / jour)."""
    r = httpx.get("https://api.mymemory.translated.net/get",
                  params={"q": text[:480], "langpair": f"{src or 'en'}|{tgt}"}, timeout=20)
    r.raise_for_status()
    data = r.json()
    out = (data.get("responseData") or {}).get("translatedText") or ""
    if "MYMEMORY WARNING" in out.upper() or int(data.get("responseStatus") or 200) != 200:
        raise RuntimeError("quota de traduction gratuite atteint pour aujourd'hui")
    return out


def translate_groups(settings: dict, lines: list[str], target: str, src: str | None) -> list[str]:
    """Traduit des lignes de sous-titres en gardant leur nombre.

    On regroupe les lignes en phrases (meilleure traduction), puis on répartit les mots traduits
    sur les lignes d'origine. Utilise l'IA configurée, sinon le service gratuit MyMemory.
    """
    tgt = lang_code(target)
    buckets: list[list[int]] = []
    cur: list[int] = []
    for i, line in enumerate(lines):
        cur.append(i)
        if line.rstrip().endswith((".", "!", "?", "…")) or len(cur) >= 4:
            buckets.append(cur)
            cur = []
    if cur:
        buckets.append(cur)
    sentences = [" ".join(lines[i] for i in b) for b in buckets]
    translated = None
    engine = available_engine(settings)
    if engine != "heuristic":
        try:
            translated = translate_lines(settings, sentences, target, engine)
        except Exception as e:  # noqa: BLE001
            log.warning("Traduction IA impossible (%s) : %s", engine, e)
    if translated is None:
        translated = [_mymemory(x, src or "en", tgt) for x in sentences]
    out = [""] * len(lines)
    for b, tr in zip(buckets, translated):
        toks = str(tr).split()
        counts = [max(1, len(lines[i].split())) for i in b]
        total = sum(counts)
        pos = 0
        for k, i in enumerate(b):
            if k == len(b) - 1:
                take = toks[pos:]
            else:
                n = max(1, round(len(toks) * counts[k] / total)) if pos < len(toks) else 0
                take = toks[pos:pos + n]
                pos += n
            out[i] = " ".join(take)
    return out
