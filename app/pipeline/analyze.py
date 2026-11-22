"""Détection des meilleurs moments : viral, drôle, dramatique, hype.

100 % local et gratuit : combine le volume sonore, le débit de parole, des mots-clés
(FR + EN), les pics d'activité du chat (Twitch / YouTube live) et la demande de
l'utilisateur. Un LLM (Ollama / Gemini / Groq) peut ensuite affiner le classement.
"""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata

import numpy as np

CATEGORIES = ("funny", "drama", "hype")
CATEGORY_LABELS = {
    "viral": "🔥 Viral",
    "funny": "😂 Drôle",
    "drama": "🎭 Dramatique",
    "hype": "⚡ Épique",
}

LENGTH_PRESETS = {
    "auto": (15, 90, 40),
    "lt30": (8, 30, 22),
    "30_59": (30, 59, 45),
    "60_89": (60, 89, 72),
    "90_180": (90, 180, 120),
    "180_300": (180, 300, 220),
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^\w\s'!?😂🤣💀🔥😱😭]", " ", s)


FUNNY_WORDS = [
    "mdr", "ptdr", "xptdr", "jpp", "haha", "hahaha", "ahah", "ahahah", "hihi", "lol", "lmao", "rofl",
    "rire", "rires", "rigole", "marrant", "drole", "debile", "trop fort", "je suis mort",
    "chui mort", "jsuis mort", "pete", "hilarant", "blague", "nul", "wesh", "bouffon", "clown",
    "laughs", "laughing", "funny", "hilarious", "dead", "im dead", "bruh", "lmfao", "joke", "stupid",
    "[rires]", "(rires)", "[laughter]", "(laughs)", "😂", "🤣", "💀",
]
HYPE_WORDS = [
    "oh mon dieu", "omg", "c'est pas possible", "cest pas possible", "pas possible", "incroyable",
    "dingue", "de fou", "ouf", "masterclass", "let's go", "lets go", "letsgo", "go go",
    "victoire", "top 1", "top un", "gagne", "gg", "clutch", "insane", "no way", "oh my god", "wtf",
    "jamais vu", "record", "monstre", "trop chaud", "enorme", "legendaire", "folie", "fou", "dinguerie", "pepite",
    "headshot", "elimine", "kill", "one shot", "triple", "quadruple", "1v4", "1v3", "1v2", "wipe",
    "victory", "winner", "crazy", "unbelievable", "lets gooo", "sheesh", "🔥", "😱",
]
DRAMA_WORDS = [
    "serieux", "grave", "choque", "choquee", "clash", "menteur", "mensonge", "trahi",
    "trahison", "honte", "dispute", "embrouille", "drama", "polemique", "excuse", "excuses",
    "pleure", "pleurer", "triste", "enerve", "vener", "colere", "manque de respect",
    "c'est fini", "cest fini", "je quitte", "arrete", "tais toi", "ferme la", "degage",
    "injuste", "arnaque", "scandale", "verite", "avoue", "secret", "rupture", "toxique", "insulte",
    "beef", "fight", "liar", "betrayed", "shut up", "angry", "crying", "seriously", "toxic",
    "exposed", "😭",
]
CHAT_FUNNY = ["kekw", "lul", "lol", "lmao", "omegalul", "icant", "ptdr", "mdr", "xd", "😂", "🤣",
              "💀", "haha", "jpp", "kekl", "pepelaugh", "laughing"]
CHAT_HYPE = ["pog", "pogchamp", "poggers", "pogu", "letsgo", "lets go", "gg", "omg", "insane",
             "🔥", "😱", "wtf", "clip", "clip it", "clipped", "ez", "goat", "sheesh", "w", "!!!"]
CHAT_DRAMA = ["monkas", "sadge", "pepehands", "😭", "rip", "f", "ratio", "malaise", "gene",
              "aie", "oof", "yikes", "drama", "clash", "😳"]

# Vocabulaire spécifique à certains types de vidéos (normalisé : minuscules, sans accents)
GENRE_WORDS = {
    # Vidéos concept YouTube (défis entre potes, jeux, réactions…)
    "concept": {
        "funny": ["j'en peux plus", "jen peux plus", "je pleure", "je suis plie", "plie", "mort de rire",
                  "c'est horrible", "cest horrible", "malaise", "genant", "la honte", "beurk", "degueulasse",
                  "vomir", "oh non", "non non non", "c'est quoi ca", "cest quoi ca", "t'es serieux", "tes serieux",
                  "aie", "ouille", "cringe", "mais pourquoi", "il est fou", "elle est folle", "n'importe quoi",
                  "nimporte quoi", "pitie", "au secours", "j'ai peur", "jai peur"],
        "hype": ["il l'a fait", "il la fait", "elle l'a fait", "gagne", "victoire", "le gagnant", "la gagnante",
                 "finale", "dernier", "derniere", "elimine", "bravo", "trop fort", "chef d'oeuvre", "mais oui",
                 "record", "reussi", "c'est valide", "cest valide", "incroyable"],
        "drama": ["tricheur", "triche", "c'est pas juste", "cest pas juste", "injuste", "j'abandonne", "jabandonne",
                  "abandon", "vexe", "boude", "contre moi", "vote", "eliminee", "perdu", "j'ai perdu", "jai perdu",
                  "c'est fini pour", "trahi", "menteur"],
    },
    # GTA / GTA RP
    "gta": {
        "hype": ["poursuite", "course poursuite", "police", "flic", "keuf", "condes", "braquage", "braque",
                 "banque", "fusillade", "explosion", "explose", "crash", "drift", "wheeling", "helico", "avion",
                 "parachute", "tank", "etoiles", "wanted", "fonce", "accelere", "go go go", "cache toi",
                 "ils arrivent", "il m'a tue", "il ma tue", "headshot", "abattu", "semer", "on les a semes",
                 "on les a perdus", "plein gaz"],
        "funny": ["ragdoll", "il s'envole", "il senvole", "ecrase", "renverse", "bug", "beug", "glitch", "pnj",
                  "fail", "il est tombe", "tombe", "dans l'eau", "le poteau", "tonneau", "il a glisse"],
        "drama": ["menottes", "prison", "garde a vue", "les mains en l'air", "pose ton arme", "gang",
                  "balance", "mouchard", "dette", "rancon", "otage", "kidnapping", "enleve", "le boss", "patron",
                  "territoire", "t'es qui", "tes qui", "degage", "wallah", "sur la tete", "tu vas payer",
                  "je vais te", "trahison"],
    },
}

STOPWORDS = set("""le la les un une des de du et en a au aux ce ces cette pour par sur dans avec
sans plus moins tres trop que qui quoi ou mais donc car ne pas je tu il elle on nous vous ils
elles mon ma mes ton ta tes son sa ses leur leurs est sont etre avoir fait faire trouve trouver
moments moment meilleurs meilleur les plus the a an of to and in on for with is are best
most find clips clip video""".split())


def _count_hits(text_norm: str, vocab: list[str]) -> int:
    padded = f" {text_norm} "
    hits = 0
    for w in vocab:
        if len(w) <= 2 and w.isalpha():
            hits += padded.count(f" {w} ")
        else:
            hits += padded.count(w if not w.isalpha() else f" {w}")
    return hits


def _zscore(x: np.ndarray) -> np.ndarray:
    if x.size == 0:
        return x
    med = np.median(x)
    mad = np.median(np.abs(x - med)) * 1.4826 + 1e-6
    return np.clip((x - med) / mad, -4, 6)


def _smooth(x: np.ndarray, w: int = 3) -> np.ndarray:
    if x.size == 0 or w <= 1:
        return x
    k = np.ones(w) / w
    return np.convolve(x, k, mode="same")


def build_signals(duration: float, segments: list[dict], loud: list[float],
                  chat: list[dict], prompt: str = "", *, genre: str = "",
                  heatmap: list[dict] | None = None, comments: list[dict] | None = None) -> dict[str, np.ndarray]:
    n = max(1, int(math.ceil(duration)))
    extra = GENRE_WORDS.get(genre, {})
    v_funny = FUNNY_WORDS + extra.get("funny", [])
    v_hype = HYPE_WORDS + extra.get("hype", [])
    v_drama = DRAMA_WORDS + extra.get("drama", [])
    multi = {k: [p for p in v if " " in p] for k, v in (("funny", v_funny), ("hype", v_hype), ("drama", v_drama))}
    funny = np.zeros(n)
    hype = np.zeros(n)
    drama = np.zeros(n)
    words_ps = np.zeros(n)
    prompt_hit = np.zeros(n)

    prompt_terms = [t for t in norm(prompt).split() if len(t) > 3 and t not in STOPWORDS]

    for seg in segments:
        words = seg.get("words") or [{"s": seg["start"], "e": seg["end"], "w": seg["text"]}]
        for w in words:
            i = min(n - 1, max(0, int(w["s"])))
            words_ps[i] += 1
        # mots-clés évalués par fenêtres de ~3 mots pour attraper les expressions
        for k in range(len(words)):
            chunk = norm(" ".join(x["w"] for x in words[k:k + 3]))
            first = norm(words[k]["w"])
            i = min(n - 1, max(0, int(words[k]["s"])))
            funny[i] += _count_hits(first, v_funny) + 0.5 * _count_hits(chunk, multi["funny"])
            hype[i] += _count_hits(first, v_hype) + 0.5 * _count_hits(chunk, multi["hype"])
            drama[i] += _count_hits(first, v_drama) + 0.5 * _count_hits(chunk, multi["drama"])
            if prompt_terms and any(t in first for t in prompt_terms):
                prompt_hit[i] += 1
        # rire répété (« ahahah », « hahaha ») = indicateur fort
        txt = norm(seg.get("text", ""))
        if re.search(r"(ha){3,}|(ah){3,}|(hi){3,}|x?ptdr+", txt):
            i = min(n - 1, max(0, int(seg["start"])))
            funny[i] += 2
        if txt.count("!") >= 2 or "?!" in seg.get("text", ""):
            i = min(n - 1, max(0, int(seg["start"])))
            hype[i] += 1

    # Volume sonore (0,5 s -> 1 s)
    loud_arr = np.array(loud or [-60.0], dtype=float)
    per_sec = np.full(n, float(np.median(loud_arr)))
    m = min(n, loud_arr.size // 2)
    if m:
        per_sec[:m] = loud_arr[: m * 2].reshape(-1, 2).max(axis=1)
    loud_z = _smooth(_zscore(per_sec), 3)

    # Chat
    chat_rate = np.zeros(n)
    chat_f = np.zeros(n)
    chat_h = np.zeros(n)
    chat_d = np.zeros(n)
    for msg in chat or []:
        i = int(msg["t"])
        if 0 <= i < n:
            chat_rate[i] += 1
            t = norm(msg.get("m", ""))
            chat_f[i] += min(2, _count_hits(t, CHAT_FUNNY))
            chat_h[i] += min(2, _count_hits(t, CHAT_HYPE))
            chat_d[i] += min(2, _count_hits(t, CHAT_DRAMA))
    has_chat = chat_rate.sum() > 20
    # Le chat réagit avec quelques secondes de retard : on décale de -6 s
    lag = 6

    def shift(a):
        return np.concatenate([a[lag:], np.zeros(min(lag, a.size))])[: a.size]

    chat_z = _smooth(_zscore(_smooth(shift(chat_rate), 5)), 3) if has_chat else np.zeros(n)
    rate_norm = max(1.0, float(np.percentile(chat_rate, 90))) if has_chat else 1.0

    speech = _smooth(words_ps, 5)
    speech_z = _zscore(speech) if speech.any() else np.zeros(n)

    # Réactions sans parole : fou rire, cri, hurlement (Whisper ne les transcrit pas)
    has_speech = bool(words_ps.sum() > 10)
    react = np.clip(loud_z - 1.0, 0, None) * (_smooth(words_ps, 3) < 0.34) if has_speech else np.zeros(n)
    react = _smooth(react, 3)

    # Audience : courbe « Moments les plus revus » de YouTube + commentaires horodatés
    heat = np.zeros(n)
    for h in heatmap or []:
        a, b = int(max(0, h.get("start_time", 0))), int(min(n, math.ceil(h.get("end_time", 0))))
        if b > a:
            heat[a:b] = np.maximum(heat[a:b], float(h.get("value") or 0))
    if heat.any():
        med = float(np.median(heat))
        heat = np.clip((heat - med) / max(1e-6, float(heat.max()) - med), 0, 1)
    com = np.zeros(n)
    com_f = np.zeros(n)
    for cm in comments or []:
        t = int(cm.get("t", -1))
        if 0 <= t < n:
            w = 1.0 + math.log1p(max(0, int(cm.get("likes") or 0)))
            com[t:t + 10] += w  # on horodate le début du moment : il dure ~10 s
            if _count_hits(norm(cm.get("text", "")), CHAT_FUNNY + FUNNY_WORDS) > 0:
                com_f[t:t + 10] += w
    if com.any():
        com = com / max(1e-6, float(np.percentile(com[com > 0], 95)))
        com_f = com_f / max(1e-6, float(com_f.max() or 1))
    audience = np.clip(0.65 * heat + 0.5 * np.clip(com, 0, 1.5), 0, 1.5)

    sig = {
        "funny": _smooth(funny, 4) * 1.6 + react * 0.6 + com_f * 1.2
                 + (_smooth(shift(chat_f), 5) / rate_norm * 3 if has_chat else 0),
        "hype": _smooth(hype, 4) * 1.2 + np.clip(loud_z, 0, None) * 0.55 + react * 0.4
                + (_smooth(shift(chat_h), 5) / rate_norm * 3 if has_chat else 0),
        "drama": _smooth(drama, 4) * 1.5
                 + (_smooth(shift(chat_d), 5) / rate_norm * 3 if has_chat else 0),
        "energy": np.clip(loud_z, 0, None) * 0.6 + np.clip(speech_z, 0, None) * 0.25
                  + np.clip(chat_z, 0, None) * (0.9 if has_chat else 0) + react * 0.5 + audience * 1.2,
        "prompt": _smooth(prompt_hit, 6) * 2.0,
        "audience": audience,
        "speech": words_ps,
        "loud_z": loud_z,
        "chat_z": chat_z,
    }
    return sig


def _units(segments: list[dict], duration: float) -> list[tuple[float, float]]:
    """Unités de découpe = phrases (on coupe les segments trop longs aux pauses)."""
    units = []
    for seg in segments:
        words = seg.get("words") or []
        if seg["end"] - seg["start"] <= 12 or len(words) < 4:
            units.append((seg["start"], seg["end"]))
            continue
        cur = words[0]["s"]
        for a, b in zip(words, words[1:]):
            punct = a["w"].endswith((".", "!", "?", ","))
            if (b["s"] - a["e"] > 0.35 or punct) and a["e"] - cur >= 3:
                units.append((cur, a["e"]))
                cur = b["s"]
        units.append((cur, words[-1]["e"]))
    # Les passages sans parole (action, gameplay, musique) deviennent des unités de 4 s
    step = 4.0
    filled: list[tuple[float, float]] = []
    cursor = 0.0
    for a, b in sorted(units):
        while a - cursor > step + 1:
            filled.append((cursor, cursor + step))
            cursor += step
        filled.append((a, b))
        cursor = max(cursor, b)
    while duration - cursor > 1:
        filled.append((cursor, min(duration, cursor + step)))
        cursor += step
    return filled


def _pct_rank(x: np.ndarray) -> np.ndarray:
    """Normalisation robuste 0..1 qui conserve l'écart entre un moment fort et le bruit."""
    if x.size <= 1:
        return np.ones_like(x)
    lo = float(np.median(x))
    hi = float(np.percentile(x, 99.5))
    if hi - lo < 1e-6:
        return np.zeros_like(x) if hi <= 1e-6 else np.full_like(x, 0.5)
    return np.clip((x - lo) / (hi - lo), 0.0, 1.0)


def find_candidates(duration: float, segments: list[dict], signals: dict, *,
                    length: str = "auto", clip_types: list[str] | None = None,
                    max_clips: int = 10) -> list[dict]:
    lo, hi, ideal = LENGTH_PRESETS.get(length, LENGTH_PRESETS["auto"])
    if duration < lo:  # vidéo très courte : un seul clip
        lo, hi, ideal = max(3, duration * 0.5), duration, duration
    hi = min(hi, duration)
    units = _units(segments, duration)
    n = len(signals["energy"])

    cums = {k: np.concatenate([[0.0], np.cumsum(v)]) for k, v in signals.items() if isinstance(v, np.ndarray)}

    def mean(k, a, b):
        a_i, b_i = max(0, int(a)), min(n, max(int(a) + 1, int(math.ceil(b))))
        return (cums[k][b_i] - cums[k][a_i]) / max(1, b_i - a_i)

    def peak(k, a, b):
        a_i, b_i = max(0, int(a)), min(n, max(int(a) + 1, int(math.ceil(b))))
        return float(signals[k][a_i:b_i].max()) if b_i > a_i else 0.0

    raw = []
    for i in range(len(units)):
        s = units[i][0]
        for j in range(i, len(units)):
            e = units[j][1]
            d = e - s
            if d > hi + 1:
                break
            if d < lo:
                continue
            raw.append((s, e))
    if not raw:
        raw = [(0.0, min(duration, hi))]

    feats = []
    for s, e in raw:
        d = e - s
        f = {
            "start": s, "end": e,
            "funny": mean("funny", s, e) + 0.35 * peak("funny", s, e),
            "hype": mean("hype", s, e) + 0.35 * peak("hype", s, e),
            "drama": mean("drama", s, e) + 0.35 * peak("drama", s, e),
            "energy": mean("energy", s, e) + 0.4 * peak("energy", s, e),
            "hook": mean("energy", s, s + 3) + mean("hype", s, s + 3) + mean("funny", s, s + 3),
            "payoff": peak("energy", s + d * 0.5, e) - mean("energy", s, s + d * 0.5) * 0.3,
            "prompt": mean("prompt", s, e),
            "speech": mean("speech", s, e),
            "audience": mean("audience", s, e) + 0.5 * peak("audience", s, e),
            "fit": math.exp(-((d - ideal) / (ideal * 0.6)) ** 2),
        }
        feats.append(f)

    keys = ["funny", "hype", "drama", "energy", "hook", "payoff", "prompt", "speech", "audience"]
    ranks = {k: _pct_rank(np.array([f[k] for f in feats])) for k in keys}
    wanted = [c for c in (clip_types or ["viral", "funny", "drama", "hype"]) if c in ("viral", *CATEGORIES)]
    if not wanted:
        wanted = ["viral", "funny", "drama", "hype"]
    has_prompt = any(f["prompt"] > 0 for f in feats)
    has_audience = bool(signals.get("audience") is not None and signals["audience"].any())

    for idx, f in enumerate(feats):
        r = {k: float(ranks[k][idx]) for k in keys}
        cat_scores = {c: r[c] * 0.75 + r["energy"] * 0.25 for c in CATEGORIES}
        viral = (0.28 * max(cat_scores.values()) + 0.22 * r["energy"] + 0.18 * r["hook"]
                 + 0.12 * r["payoff"] + 0.10 * f["fit"] + 0.10 * r["speech"])
        if has_audience:  # données réelles des spectateurs : signal le plus fiable
            viral = viral * 0.65 + 0.35 * r["audience"]
        if has_prompt:
            viral = viral * 0.75 + 0.25 * r["prompt"]
        f["scores"] = {"viral": viral, **cat_scores}
        sel = [f["scores"][c] for c in wanted]
        f["composite"] = 0.6 * viral + 0.4 * max(sel)
        f["category"] = max(CATEGORIES, key=lambda c: r[c])
        if max(r[c] for c in CATEGORIES) < 0.12:  # aucun signal clair : moment d'action
            f["category"] = "hype"
        f["hook_strength"] = r["hook"]
        f["audience_rank"] = r["audience"] if has_audience else 0.0

    def overlap(a, b):
        inter = max(0.0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
        return inter / max(1e-6, min(a["end"] - a["start"], b["end"] - b["start"]))

    chosen: list[dict] = []

    def take(pool_sorted, limit):
        got = 0
        for f in pool_sorted:
            if got >= limit or len(chosen) >= max_clips * 2:
                break
            if all(overlap(f, c) < 0.25 for c in chosen):
                chosen.append(f)
                got += 1

    # Diversité : quelques places réservées à chaque catégorie demandée
    per_cat = max(1, (max_clips * 2) // (len(wanted) + 2))
    for c in wanted:
        if c == "viral":
            continue
        take(sorted(feats, key=lambda f: f["scores"][c], reverse=True), per_cat)
    take(sorted(feats, key=lambda f: f["composite"], reverse=True), max_clips * 2)

    # Ne jamais couper en plein pic : on prolonge de quelques secondes si l'action continue
    e_sig = signals["energy"]
    base = float(np.median(e_sig)) if e_sig.size else 0.0
    for f in chosen:
        a, b = int(max(0, f["end"] - 2)), int(min(n, f["end"]))
        if b > a and float(e_sig[a:b].mean()) > base + 0.5:
            room = max(0.0, hi - (f["end"] - f["start"]))
            f["end"] = min(duration, f["end"] + min(4.0, room))
        f["score"] = to_score(f["composite"])
    chosen.sort(key=lambda f: f["composite"], reverse=True)
    return chosen


def to_score(x: float) -> int:
    """0..1 -> score viral affiché (55..99, comme les outils pro)."""
    return int(round(55 + 44 * max(0.0, min(1.0, x)) ** 1.3))


def clip_text(segments: list[dict], s: float, e: float) -> str:
    parts = []
    for seg in segments:
        if seg["end"] < s or seg["start"] > e:
            continue
        ws = [w["w"] for w in seg.get("words") or [] if s - 0.05 <= w["s"] <= e]
        parts.append(" ".join(ws) if ws else seg["text"])
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def clip_words(segments: list[dict], s: float, e: float) -> list[dict]:
    out = []
    for seg in segments:
        if seg["end"] < s or seg["start"] > e:
            continue
        for w in seg.get("words") or []:
            if w["s"] >= s - 0.05 and w["e"] <= e + 0.3:
                out.append(w)
    return out


def snap(c: dict, segments: list[dict], duration: float) -> tuple[float, float]:
    words = clip_words(segments, c["start"], c["end"])
    s, e = c["start"], c["end"]
    # on cale les bords sur la parole seulement s'ils tombent dedans (sinon on garde l'action)
    if words and words[0]["s"] - s < 2.0:
        s = max(0.0, words[0]["s"] - 0.15)
    if words and e - words[-1]["e"] < 2.0:
        e = min(duration, words[-1]["e"] + 0.45)
    return round(s, 2), round(e, 2)


# ---------- Textes sans LLM ----------

GAMES = {
    "gta rp": "#gtarp", "gtarp": "#gtarp", "gta 6": "#gta6", "gta6": "#gta6", "gta vi": "#gta6",
    "gta 5": "#gta5", "gta v": "#gta5", "gta": "#gta", "fortnite": "#fortnite", "minecraft": "#minecraft",
    "valorant": "#valorant", "fifa": "#fifa", "eafc": "#eafc", "fc 2": "#eafc", "warzone": "#warzone",
    "call of duty": "#callofduty", "apex": "#apexlegends", "rocket league": "#rocketleague",
    "league of legends": "#leagueoflegends", "lol ": "#leagueoflegends", "cs2": "#cs2",
    "counter strike": "#cs2", "roblox": "#roblox", "pokemon": "#pokemon", "zelda": "#zelda",
    "mario": "#mario", "elden ring": "#eldenring",
}
GENRE_TAGS = {
    "fr": {
        "gaming": ["#gaming", "#gamer", "#twitch"], "gta": ["#gta", "#gtarp", "#gaming"],
        "concept": ["#youtube", "#concept", "#defi"], "lifestyle": ["#lifestyle", "#vlog"],
        "sports": ["#sport", "#football"], "marketing": ["#business", "#marketing"],
        "entertainment": ["#divertissement", "#humour"], "news": ["#actu", "#info"],
        "education": ["#apprendre", "#astuce"], "podcast": ["#podcast", "#interview"],
        "irl": ["#irl", "#streamer"], "reaction": ["#reaction", "#streamer"], "humor": ["#humour", "#drole"],
    },
    "en": {
        "gaming": ["#gaming", "#gamer", "#twitch"], "gta": ["#gta", "#gtarp", "#gaming"],
        "concept": ["#youtube", "#challenge", "#funny"], "lifestyle": ["#lifestyle", "#vlog"],
        "sports": ["#sports", "#football"], "marketing": ["#business", "#marketing"],
        "entertainment": ["#entertainment", "#funny"], "news": ["#news"], "education": ["#learn", "#tips"],
        "podcast": ["#podcast", "#interview"], "irl": ["#irl", "#streamer"], "reaction": ["#reaction"],
        "humor": ["#funny", "#comedy"],
    },
}
HOOKS = {
    "fr": {
        "funny": ["J'AI PAS PU M'ARRÊTER DE RIRE 😂", "LE MOMENT LE PLUS DRÔLE 😂", "IL S'Y ATTENDAIT PAS 😭",
                  "REGARDE JUSQU'À LA FIN 😂", "PERSONNE N'A COMPRIS 💀"],
        "drama": ["ÇA A DÉGÉNÉRÉ… 😳", "IL A PAS OSÉ DIRE ÇA", "LE MOMENT OÙ TOUT A BASCULÉ",
                  "TOUT LE MONDE EN PARLE 😳", "PERSONNE NE S'Y ATTENDAIT"],
        "hype": ["LE MOMENT LE PLUS FOU 🔥", "C'EST PAS POSSIBLE 😱", "PERSONNE NE PEUT REFAIRE ÇA",
                 "ATTENDS LA FIN… 🔥", "ILS ONT TOUS HALLUCINÉ 😱"],
    },
    "en": {
        "funny": ["I CAN'T STOP LAUGHING 😂", "THE FUNNIEST MOMENT 😂", "HE DID NOT SEE THAT COMING 😭",
                  "WAIT FOR THE END 😂", "NOBODY UNDERSTOOD 💀"],
        "drama": ["IT ESCALATED FAST… 😳", "HE REALLY SAID THAT", "THE MOMENT EVERYTHING CHANGED",
                  "EVERYONE IS TALKING ABOUT THIS 😳", "NOBODY EXPECTED THIS"],
        "hype": ["THE CRAZIEST MOMENT 🔥", "THIS IS IMPOSSIBLE 😱", "NOBODY CAN DO THIS",
                 "WAIT FOR IT… 🔥", "THEY ALL LOST IT 😱"],
    },
}
GENRE_HOOKS = {
    ("fr", "gta"): {
        "hype": ["LA POURSUITE LA PLUS FOLLE 🚔", "LA POLICE N'A RIEN PU FAIRE 🚔", "LE BRAQUAGE A MAL TOURNÉ 💰"],
        "funny": ["LE PIRE FAIL DE GTA 😂", "LA PHYSIQUE DE GTA EST CASSÉE 💀", "IL S'EST ENVOLÉ 😭"],
        "drama": ["IL S'EST FAIT TRAHIR 😳", "LE RP A DÉGÉNÉRÉ… 😳", "IL A BALANCÉ TOUT LE GANG"],
    },
    ("en", "gta"): {
        "hype": ["THE CRAZIEST POLICE CHASE 🚔", "THE COPS COULDN'T STOP HIM 🚔", "THE HEIST WENT WRONG 💰"],
        "funny": ["THE WORST GTA FAIL 😂", "GTA PHYSICS ARE BROKEN 💀", "HE LITERALLY FLEW AWAY 😭"],
        "drama": ["HE GOT BETRAYED 😳", "THE RP ESCALATED… 😳", "HE SNITCHED ON THE WHOLE GANG"],
    },
    ("fr", "concept"): {
        "funny": ["ILS ONT PAS TENU 😂", "LE CONCEPT A DÉGÉNÉRÉ 😂", "FOU RIRE GÉNÉRAL 😭"],
        "hype": ["LA FIN EST INCROYABLE 😱", "PERSONNE NE PENSAIT QU'IL GAGNERAIT", "LE RETOURNEMENT DE SITUATION 🔥"],
        "drama": ["IL A TRICHÉ ?! 😳", "ÇA A MAL FINI… 😳", "IL A PAS DIGÉRÉ 😳"],
    },
    ("en", "concept"): {
        "funny": ["THEY COULDN'T HOLD IT 😂", "THIS CHALLENGE WENT WRONG 😂", "EVERYONE WAS CRYING LAUGHING 😭"],
        "hype": ["THE ENDING IS INSANE 😱", "NOBODY THOUGHT HE'D WIN", "WHAT A PLOT TWIST 🔥"],
        "drama": ["DID HE JUST CHEAT?! 😳", "IT ENDED BADLY… 😳", "HE DID NOT TAKE IT WELL 😳"],
    },
}
CTAS = {
    "fr": {
        "funny": ["Je suis encore mort de rire 😂 Abonne-toi pour plus de moments comme ça !",
                  "Tag quelqu'un qui ferait exactement ça 😂", "Le meilleur moment de la vidéo 😂 Tu en penses quoi ?"],
        "drama": ["Qui avait raison selon toi ? 👀 Dis-le en commentaire", "Ça a vite dégénéré… 😳 Team qui ?",
                  "Personne ne s'attendait à ça 😳 Abonne-toi pour la suite"],
        "hype": ["Dis-moi en commentaire si tu aurais fait mieux 🔥", "Le moment le plus fou 🔥 Abonne-toi !",
                 "Regarde jusqu'à la fin… 😱🔥"],
    },
    "en": {
        "funny": ["Still crying laughing 😂 Follow for more moments like this!", "Tag someone who would do this 😂",
                  "Best moment of the video 😂 What do you think?"],
        "drama": ["Who was right? 👀 Tell me in the comments", "That escalated quickly… 😳 Whose side are you on?",
                  "Nobody saw this coming 😳 Follow for part 2"],
        "hype": ["Comment if you could do better 🔥", "The craziest moment 🔥 Follow for more!", "Watch till the end… 😱🔥"],
    },
}
CAT_TAGS = {
    "fr": {"funny": ["#drole", "#humour"], "drama": ["#drama", "#clash"], "hype": ["#epique", "#incroyable"]},
    "en": {"funny": ["#funny", "#lol"], "drama": ["#drama", "#crazy"], "hype": ["#epic", "#insane"]},
}
BASE_TAGS = {"fr": ["#fyp", "#pourtoi", "#viral"], "en": ["#fyp", "#foryou", "#viral"]}


def _pick(options: list[str], key: str) -> str:
    h = int(hashlib.md5(key.encode()).hexdigest(), 16)
    return options[h % len(options)]


def fallback_texts(c: dict, text: str, *, genre: str, source_title: str, source_tags: list[str],
                   lang: str = "fr") -> dict:
    """Titre, accroche, description, hashtags sans IA — en français si la vidéo est en français, sinon en anglais."""
    lang = "fr" if lang == "fr" else "en"
    cat = c["category"]
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", text) if len(x.strip()) > 8]
    best = sentences[0] if sentences else text
    extra = GENRE_WORDS.get(genre, {})
    vocab = HYPE_WORDS + FUNNY_WORDS + DRAMA_WORDS + sum(extra.values(), [])
    if sentences:
        best = max(sentences[:8], key=lambda x: _count_hits(norm(x), vocab) + min(len(x), 80) / 80)
    title = best.strip(" .,")
    if len(title) > 70:
        title = title[:67].rsplit(" ", 1)[0] + "…"
    if not title:
        m, sec = divmod(int(c["start"]), 60)
        title = f"{source_title[:48]} ({m}:{sec:02d})"
    pool = GENRE_HOOKS.get((lang, genre), {}).get(cat, []) + HOOKS[lang][cat]
    hook = _pick(pool, f"{c['start']}{source_title}")
    tags = []
    low = f" {source_title.lower()} {' '.join(source_tags).lower()} "
    for k, v in GAMES.items():
        if k in low and v not in tags:
            tags.append(v)
    g = genre if genre in GENRE_TAGS[lang] else ("gaming" if tags else "entertainment")
    tags += GENRE_TAGS[lang].get(g, [])[:2] + CAT_TAGS[lang][cat] + BASE_TAGS[lang]
    seen = []
    for t in tags:
        if t not in seen:
            seen.append(t)
    desc = _pick(CTAS[lang][cat], f"{c['end']}{source_title}")
    return {"title": title, "hook": hook, "description": desc, "hashtags": seen[:8],
            "reason": reason_for(c)}


def reason_for(c: dict) -> str:
    s = c["scores"]
    bits = []
    if s.get("funny", 0) > 0.75:
        bits.append("rires / réactions drôles détectés")
    if s.get("hype", 0) > 0.75:
        bits.append("pic d'intensité (voix + volume)")
    if s.get("drama", 0) > 0.75:
        bits.append("tension / clash dans les propos")
    if c.get("audience_rank", 0) > 0.6:
        bits.insert(0, "moment parmi les plus revus / commentés par les spectateurs")
    if c.get("hook_strength", 0) > 0.7:
        bits.append("accroche forte dès les 3 premières secondes")
    if not bits:
        bits.append("moment le plus dense en parole et en énergie")
    return ", ".join(bits).capitalize() + "."
