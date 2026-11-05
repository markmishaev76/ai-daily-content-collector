"""
Share image for a day's brief: a 1200x627 PNG with the story of the day, used as the page's og:image so links
posted to LinkedIn, Slack or X show the day's headline instead of the generic site card.
"""

import re
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps

SITE_DIR = Path(__file__).resolve().parent.parent / "site"
FONTS = {"bold": SITE_DIR / "fonts" / "Inter-Bold.ttf", "regular": SITE_DIR / "fonts" / "Inter-Regular.ttf"}
PHOTO = SITE_DIR / "static" / "mark.jpg"
WIDTH, HEIGHT = 1200, 627
MARGIN = 72
TEXT_WIDTH = WIDTH - 2 * MARGIN
INK, MUTED, BACKGROUND = "#16161d", "#5b6270", "#ffffff"
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


@lru_cache(maxsize=None)
def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS[weight]), size)


def wrap(text: str, face: ImageFont.FreeTypeFont, width: int, max_lines: int) -> List[str]:
    """Greedy word wrap to `width` pixels; the last kept line ends in an ellipsis when text is cut."""
    lines, current = [], ""
    words = text.split()
    for i, word in enumerate(words):
        candidate = f"{current} {word}".strip()
        if face.getlength(candidate) <= width or not current:
            current = candidate
            continue
        lines.append(current)
        current = word
        if len(lines) == max_lines:
            break
    else:
        if current:
            lines.append(current)
        return lines
    last = lines[-1]
    while last and face.getlength(last + "…") > width:
        last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
    lines[-1] = last + "…"
    return lines


def _circle(path: Path, size: int) -> Image.Image:
    with Image.open(path) as img:
        photo = ImageOps.fit(img.convert("RGB"), (size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    photo.putalpha(mask)
    return photo


def render(out: Path, title: str, kicker: str, take: Optional[str] = None, color: str = "#5a4fcf") -> None:
    """Write the card to `out`. `kicker` is the small line above the title (e.g. "Story of the day · Thu, Oct 22")."""
    if not HEX.match(color):
        raise ValueError(f"share card color must be #rrggbb, got {color!r}")
    img = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 16, HEIGHT), fill=color)

    img.paste(photo := _circle(PHOTO, 64), (MARGIN, 52), photo)
    draw.text((MARGIN + 84, 58), "The Daily Brief", font=font("bold", 30), fill=INK)
    draw.text((MARGIN + 84, 94), "thedailybrief.dev · Mark Mishaev", font=font("regular", 22), fill=MUTED)

    y = 170
    draw.text((MARGIN, y), kicker.upper(), font=font("bold", 22), fill=color)
    y += 44
    size = 58 if len(wrap(title, font("bold", 58), TEXT_WIDTH, 5)) <= 3 else 50
    for line in wrap(title, font("bold", size), TEXT_WIDTH, 4 if take else 5):
        draw.text((MARGIN, y), line, font=font("bold", size), fill=INK)
        y += int(size * 1.2)
    if take:
        y = max(y + 18, HEIGHT - 150)
        for line in wrap(f"Mark's take: {take}", font("regular", 26), TEXT_WIDTH, 2):
            draw.text((MARGIN, y), line, font=font("regular", 26), fill=MUTED)
            y += 36
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
