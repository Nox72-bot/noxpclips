"""Images incrustées : accroche (titre à l'écran), emojis, logo. Rendu avec Pillow."""
from __future__ import annotations

import logging
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..config import DATA_DIR, FONTS_DIR

log = logging.getLogger("noxp.overlays")

W, H = 1080, 1920

EMOJI_FONT_CANDIDATES = [
    DATA_DIR / "NotoColorEmoji.ttf",
    Path("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"),
    Path("/usr/share/fonts/noto/NotoColorEmoji.ttf"),
    Path("/System/Library/Fonts/Apple Color Emoji.ttc"),
]
EMOJI_URL = "https://raw.githubusercontent.com/googlefonts/noto-emoji/main/fonts/NotoColorEmoji.ttf"


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    p = FONTS_DIR / name
    try:
        return ImageFont.truetype(str(p), size)
    except OSError:
        return ImageFont.load_default(size)


@lru_cache(maxsize=1)
def _emoji_font_spec() -> tuple[str, int] | None:
    for p in EMOJI_FONT_CANDIDATES:
        if p.exists():
            for size in (109, 160, 96, 64):
                try:
                    f = ImageFont.truetype(str(p), size)
                    im = Image.new("RGBA", (size * 2, size * 2))
                    ImageDraw.Draw(im).text((0, 0), "😂", font=f, embedded_color=True)
                    if im.getbbox():
                        return str(p), size
                except OSError:
                    continue
    # Téléchargement unique de la police emoji libre (OFL)
    try:
        dest = DATA_DIR / "NotoColorEmoji.ttf"
        with httpx.stream("GET", EMOJI_URL, timeout=60, follow_redirects=True) as r:
            r.raise_for_status()
            with open(dest, "wb") as fh:
                for chunk in r.iter_bytes():
                    fh.write(chunk)
        return str(dest), 109
    except Exception as e:
        log.warning("Police emoji indisponible : %s", e)
        return None


def is_emoji(ch: str) -> bool:
    cp = ord(ch)
    return (
        0x1F000 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x27BF or 0x2B00 <= cp <= 0x2BFF
        or cp in (0x200D, 0xFE0F, 0x203C, 0x2049, 0x2122, 0x2139, 0x3030, 0x303D)
    )


def split_runs(text: str) -> list[tuple[bool, str]]:
    runs: list[tuple[bool, str]] = []
    for ch in text:
        e = is_emoji(ch)
        if runs and runs[-1][0] == e:
            runs[-1] = (e, runs[-1][1] + ch)
        else:
            runs.append((e, ch))
    return runs


def strip_emoji(text: str) -> str:
    return re.sub(r"\s+", " ", "".join(c for c in text if not is_emoji(c))).strip()


@lru_cache(maxsize=256)
def emoji_image(seq: str, size: int) -> Image.Image | None:
    spec = _emoji_font_spec()
    if not spec:
        return None
    path, native = spec
    f = ImageFont.truetype(path, native)
    im = Image.new("RGBA", (native * 3, native * 2), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((0, 0), seq, font=f, embedded_color=True)
    bbox = im.getbbox()
    if not bbox:
        return None
    im = im.crop(bbox)
    ratio = size / im.height
    return im.resize((max(1, int(im.width * ratio)), size), Image.LANCZOS)


def hex_rgb(h: str, default=(255, 255, 255)) -> tuple[int, int, int]:
    h = (h or "").lstrip("#")
    if len(h) != 6:
        return default
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


# ---------- Accroche ----------

def _wrap(words: list[str], f: ImageFont.FreeTypeFont, max_w: int, emoji_size: int) -> list[list[str]]:
    lines: list[list[str]] = []
    cur: list[str] = []
    for w in words:
        test = cur + [w]
        if cur and _measure(" ".join(test), f, emoji_size) > max_w:
            lines.append(cur)
            cur = [w]
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def _measure(text: str, f: ImageFont.FreeTypeFont, emoji_size: int) -> int:
    total = 0
    for is_e, run in split_runs(text):
        if is_e:
            em = emoji_image(run, emoji_size)
            total += (em.width + int(emoji_size * 0.1)) if em else 0
        else:
            total += int(f.getlength(run))
    return total


def _draw_line(img: Image.Image, text: str, f: ImageFont.FreeTypeFont, x: int, y: int,
               fill, stroke: int, stroke_fill, emoji_size: int, accent_words: set[str] | None = None,
               accent=None) -> None:
    d = ImageDraw.Draw(img)
    cx = x
    for is_e, run in split_runs(text):
        if is_e:
            em = emoji_image(run, emoji_size)
            if em:
                img.alpha_composite(em, (cx, y + int(f.size * 0.08)))
                cx += em.width + int(emoji_size * 0.1)
            continue
        for tok in re.split(r"(\s+)", run):
            if not tok:
                continue
            col = accent if accent_words and tok.strip().lower().strip(".,!?…") in accent_words else fill
            d.text((cx, y), tok, font=f, fill=col, stroke_width=stroke, stroke_fill=stroke_fill)
            cx += int(f.getlength(tok))


def render_hook(text: str, style: str, accent_hex: str, out: Path, *, y_center: float = 0.16) -> Path:
    """Image 1080x1920 transparente avec l'accroche."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    accent = hex_rgb(accent_hex, (255, 214, 10)) + (255,)
    text = (text or "").strip()
    if style == "editorial":
        f = font("DMSerifDisplay-Italic.ttf", 92)
        words = text.replace("\n", " ").split()
        words = [w if any(is_emoji(c) for c in w) else w[:1].upper() + w[1:].lower() if i == 0 else w.lower()
                 for i, w in enumerate(words)]
        lines = _wrap(words, f, 880, 84)
        longest = max((w for w in words if not any(is_emoji(c) for c in w)), key=len, default="")
        acc = {longest.lower().strip(".,!?…")}
        lh = int(f.size * 1.08)
        y = int(H * y_center) - lh * len(lines) // 2
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for i, ln in enumerate(lines):
            s = " ".join(ln)
            x = (W - _measure(s, f, 84)) // 2
            _draw_line(shadow, strip_emoji(s), f, x + 3, y + i * lh + 4, (0, 0, 0, 170), 0, None, 84)
        img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(6)))
        for i, ln in enumerate(lines):
            s = " ".join(ln)
            x = (W - _measure(s, f, 84)) // 2
            _draw_line(img, s, f, x, y + i * lh, (255, 255, 255, 255), 3, (0, 0, 0, 200), 84, acc, accent)
    elif style == "classic":
        f = font("Poppins-ExtraBold.ttf", 64)
        words = text.upper().split()
        lines = _wrap(words, f, 860, 60)
        lh = int(f.size * 1.2)
        widths = [_measure(" ".join(ln), f, 60) for ln in lines]
        bw = max(widths) + 90
        bh = lh * len(lines) + 60
        bx = (W - bw) // 2
        by = int(H * y_center) - bh // 2
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle((bx + 4, by + 10, bx + bw + 4, by + bh + 10), 28, fill=(0, 0, 0, 120))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)))
        ImageDraw.Draw(img).rounded_rectangle((bx, by, bx + bw, by + bh), 28, fill=(255, 255, 255, 255))
        for i, ln in enumerate(lines):
            s = " ".join(ln)
            x = (W - widths[i]) // 2
            _draw_line(img, s, f, x, by + 26 + i * lh, (12, 12, 12, 255), 0, None, 60)
    else:  # punchy
        f = font("Poppins-Black.ttf", 96)
        words = text.upper().split()
        lines = _wrap(words, f, 940, 90)
        lh = int(f.size * 1.1)
        y = int(H * y_center) - lh * len(lines) // 2
        plain = [w for w in words if not any(is_emoji(c) for c in w)]
        acc = {plain[-1].lower().strip(".,!?…")} if plain else set()
        for i, ln in enumerate(lines):
            s = " ".join(ln)
            x = (W - _measure(s, f, 90)) // 2
            _draw_line(img, s, f, x, y + i * lh, (255, 255, 255, 255), 9, (0, 0, 0, 255), 90,
                       {w.lower() for w in acc}, accent)
    img.save(out)
    return out


# ---------- Emojis IA ----------

EMOJI_MAP = [
    (r"\b(mdr|ptdr|haha\w*|ahah\w*|rire|rigol\w*|drole|marrant|lol|lmao|funny)\b", "😂"),
    (r"\b(mort|dead|crane|💀)\b", "💀"),
    (r"\b(feu|fire|chaud|incroyable|dingue|ouf|fou|folle|insane|crazy|masterclass)\b", "🔥"),
    (r"\b(quoi|what|choc\w*|omg|mon dieu|pas possible|wtf|hallucin\w*)\b", "😱"),
    (r"\b(argent|money|euros?|dollars?|riche|paye\w*|prix)\b", "💰"),
    (r"\b(gagn\w*|victoire|top 1|win\w*|champion\w*|trophee)\b", "🏆"),
    (r"\b(amour|love|coeur|aime|bisou)\b", "❤️"),
    (r"\b(triste|pleur\w*|cry\w*|sad)\b", "😭"),
    (r"\b(colere|enerv\w*|vener|angry|rage)\b", "😡"),
    (r"\b(idee|astuce|conseil|tip|secret)\b", "💡"),
    (r"\b(manger|faim|bouffe|food|pizza|burger)\b", "🍔"),
    (r"\b(voiture|car|vitesse|rapide|speed)\b", "🏎️"),
    (r"\b(peur|flipp\w*|scared|horreur)\b", "😨"),
    (r"\b(kill|tue\w*|elimin\w*|headshot|tir\w*|snipe\w*)\b", "🎯"),
    (r"\b(mal|douleur|aie|ouch)\b", "🤕"),
    (r"\b(pense|reflechi\w*|hmm|bizarre)\b", "🤔"),
    (r"\b(muscle|fort|force|sport|gym)\b", "💪"),
    (r"\b(fete|party|bravo|felicit\w*|gg)\b", "🎉"),
]


def pick_emoji(text: str) -> str | None:
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    for pat, em in EMOJI_MAP:
        if re.search(pat, t):
            return em
    return None


def render_emoji_file(seq: str, out: Path, size: int = 150) -> Path | None:
    im = emoji_image(seq, size)
    if im is None:
        return None
    im.save(out)
    return out


def prepare_logo(src: Path, out: Path, width: int, opacity: float) -> Path:
    im = Image.open(src).convert("RGBA")
    ratio = width / im.width
    im = im.resize((width, max(1, int(im.height * ratio))), Image.LANCZOS)
    if opacity < 1:
        a = im.getchannel("A").point(lambda v: int(v * opacity))
        im.putalpha(a)
    im.save(out)
    return out
