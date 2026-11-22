"""Sous-titres animés mot à mot (format ASS, gravés avec libass via ffmpeg)."""
from __future__ import annotations

import re

from .overlays import strip_emoji

# Styles de sous-titres. Les couleurs sont en #RRGGBB.
STYLES: dict[str, dict] = {
    "neon": {"label": "Néon", "font": "Poppins Black", "size": 112, "color": "#FFFFFF",
             "highlight": "#7CFF4F", "outline": 7, "shadow": 3, "upper": True, "words": 3, "effect": "pop"},
    "clean": {"label": "Épuré", "font": "Poppins Bold", "size": 95, "color": "#FFFFFF",
              "highlight": "#FFFFFF", "outline": 0, "shadow": 4, "upper": False, "words": 5, "effect": "fade"},
    "box": {"label": "Surligné", "font": "Poppins ExtraBold", "size": 102, "color": "#FFFFFF",
            "highlight": "#8B5CF6", "outline": 5, "shadow": 0, "upper": True, "words": 3, "effect": "box"},
    "beast": {"label": "Explosif", "font": "Luckiest Guy", "size": 126, "color": "#FFFFFF",
              "highlight": "#FFE01B", "outline": 9, "shadow": 4, "upper": True, "words": 2, "effect": "pop"},
    "anton": {"label": "Impact", "font": "Anton", "size": 134, "color": "#FFFFFF",
              "highlight": "#FF3B3B", "outline": 6, "shadow": 2, "upper": True, "words": 3, "effect": "color"},
    "bebas": {"label": "Cinéma", "font": "Bebas Neue", "size": 146, "color": "#F5F5F5",
              "highlight": "#FF9F1C", "outline": 4, "shadow": 3, "upper": True, "words": 3, "effect": "color"},
    "karaoke": {"label": "Karaoké", "font": "Poppins ExtraBold", "size": 100, "color": "#FFFFFF",
                "highlight": "#00E5FF", "outline": 6, "shadow": 2, "upper": False, "words": 5, "effect": "karaoke"},
    "comic": {"label": "BD", "font": "Bangers", "size": 136, "color": "#FFFFFF",
              "highlight": "#FF4FD8", "outline": 8, "shadow": 4, "upper": True, "words": 3, "effect": "pop"},
    "one": {"label": "Un mot", "font": "Archivo Black", "size": 158, "color": "#FFFFFF",
            "highlight": "#FFE01B", "outline": 9, "shadow": 3, "upper": True, "words": 1, "effect": "pop"},
}

POSITIONS = {"top": 0.24, "middle": 0.66, "bottom": 0.80}


def ass_color(hex_: str, alpha: int = 0) -> str:
    h = (hex_ or "#FFFFFF").lstrip("#")
    if len(h) != 6:
        h = "FFFFFF"
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _esc(t: str) -> str:
    return t.replace("\\", "").replace("{", "(").replace("}", ")")


def _ts(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def group_words(words: list[dict], max_words: int, max_chars: int) -> list[list[dict]]:
    groups: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        if cur:
            gap = w["s"] - cur[-1]["e"]
            chars = sum(len(x["w"]) + 1 for x in cur) + len(w["w"])
            punct = cur[-1]["w"].endswith((".", "!", "?", "…"))
            if len(cur) >= max_words or chars > max_chars or gap > 0.6 or punct:
                groups.append(cur)
                cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    return groups


def build_ass(words: list[dict], *, style_id: str = "neon", position: str = "middle",
              y_frac: float | None = None, highlight: str = "", color: str = "",
              uppercase: bool | None = None, font_override: str = "", duration: float = 0,
              translated: list[str] | None = None) -> tuple[str, list[dict]]:
    """Construit le fichier ASS. Retourne (texte_ass, groupes) — les groupes servent aux emojis.

    `words` : [{s, e, w}] en secondes relatives au début du clip.
    `translated` : texte traduit par groupe (même nombre que les groupes), optionnel.
    """
    st = dict(STYLES.get(style_id, STYLES["neon"]))
    if highlight:
        st["highlight"] = highlight
    if color:
        st["color"] = color
    if uppercase is not None:
        st["upper"] = uppercase
    if font_override:
        st["font"] = font_override
    y = int(1920 * (y_frac if y_frac is not None else POSITIONS.get(position, 0.66)))
    max_chars = 16 if st["size"] >= 100 else 22 if st["upper"] else 30

    clean = []
    for w in words:
        txt = strip_emoji(w["w"]).strip()
        if txt:
            clean.append({**w, "w": txt.upper() if st["upper"] else txt})
    groups = group_words(clean, st["words"], max_chars)

    if translated and len(translated) == len(groups):
        new_groups = []
        for g, tr in zip(groups, translated):
            toks = (tr.upper() if st["upper"] else tr).split() or [g[0]["w"]]
            gs, ge = g[0]["s"], g[-1]["e"]
            step = (ge - gs) / len(toks)
            new_groups.append([{"s": gs + i * step, "e": gs + (i + 1) * step, "w": t} for i, t in enumerate(toks)])
        groups = new_groups

    hl = ass_color(st["highlight"])
    base = ass_color(st["color"])
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{st['font']},{st['size']},{base},{hl},&H00000000,&H80000000,0,0,0,0,100,100,1,0,1,{st['outline']},{st['shadow']},5,70,70,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    pos = f"\\pos(540,{y})"
    for gi, g in enumerate(groups):
        g_end = g[-1]["e"]
        if gi + 1 < len(groups) and groups[gi + 1][0]["s"] - g_end < 0.35:
            g_end = groups[gi + 1][0]["s"]
        if duration:
            g_end = min(g_end, duration)
        eff = st["effect"]
        if eff == "fade":
            text = " ".join(_esc(w["w"]) for w in g)
            lines.append(f"Dialogue: 0,{_ts(g[0]['s'])},{_ts(g_end)},Cap,,0,0,0,,{{{pos}\\fad(80,60)}}{text}")
            continue
        if eff == "karaoke":
            parts = []
            for w in g:
                k = max(1, int(round((w["e"] - w["s"]) * 100)))
                parts.append(f"{{\\kf{k}}}{_esc(w['w'])}")
            # \kf remplit de SecondaryColour vers PrimaryColour : on inverse les couleurs
            lines.append(
                f"Dialogue: 0,{_ts(g[0]['s'])},{_ts(g_end)},Cap,,0,0,0,,{{{pos}\\1c{hl}\\2c{base}}}" + " ".join(parts)
            )
            continue
        for wi, w in enumerate(g):
            start = w["s"] if wi else g[0]["s"]
            end = g[wi + 1]["s"] if wi + 1 < len(g) else g_end
            if end <= start:
                continue
            toks = []
            for wj, x in enumerate(g):
                t = _esc(x["w"])
                if wj == wi:
                    if eff == "box":
                        toks.append(f"{{\\3c{hl}\\bord{st['outline'] + 13}\\shad0}}{t}{{\\r}}")
                    elif eff == "pop":
                        toks.append(f"{{\\1c{hl}\\fscx88\\fscy88\\t(0,90,\\fscx112\\fscy112)\\t(90,160,\\fscx106\\fscy106)}}{t}{{\\r}}")
                    else:
                        toks.append(f"{{\\1c{hl}}}{t}{{\\r}}")
                else:
                    toks.append(t)
            lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Cap,,0,0,0,,{{{pos}}}" + " ".join(toks))
    return header + "\n".join(lines) + "\n", groups


def plain_srt(words: list[dict], max_words: int = 7) -> str:
    groups = group_words(words, max_words, 42)

    def ts(t):
        h, m = int(t // 3600), int(t % 3600 // 60)
        s = t % 60
        return f"{h:02d}:{m:02d}:{int(s):02d},{int((s % 1) * 1000):03d}"

    out = []
    for i, g in enumerate(groups, 1):
        out.append(f"{i}\n{ts(g[0]['s'])} --> {ts(g[-1]['e'])}\n{' '.join(w['w'] for w in g)}\n")
    return "\n".join(out)


def words_from_text(text: str, start: float, end: float) -> list[dict]:
    toks = re.findall(r"\S+", text)
    if not toks:
        return []
    step = (end - start) / len(toks)
    return [{"s": start + i * step, "e": start + (i + 1) * step, "w": t} for i, t in enumerate(toks)]
