"""Build subtitles (SRT, ASS) and publication texts from the content JSON.

    python -m silicare.build                      # everything
    python -m silicare.build reel-01-how-to-apply # one item
    python -m silicare.build --uz-script latn     # Uzbek in Latin script

Output goes to silicare/build/<id>/ (git-ignored):
    <id>.ru.srt  <id>.uz.srt   subtitles for upload or review
    <id>.ru.ass  <id>.uz.ass   styled titles that assemble.py burns in
    caption.txt                the caption or Telegram text exactly as published
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from silicare import common
from silicare.translit import to_latin


@dataclass
class Cue:
    start: float
    end: float
    text: str


def _split_time(span: float, weights: list[int], min_card: float) -> list[float]:
    """Durations proportional to text length, none shorter than ``min_card``."""
    fixed: dict[int, float] = {}
    while True:
        free = [i for i in range(len(weights)) if i not in fixed]
        rest = span - sum(fixed.values())
        total = sum(max(weights[i], 1) for i in free)
        shares = {i: rest * max(weights[i], 1) / total for i in free}
        short = [i for i, s in shares.items() if s < min_card]
        if not short:
            return [fixed.get(i, shares.get(i)) for i in range(len(weights))]
        for i in short:
            fixed[i] = min_card


def reel_cues(reel: dict, lang: str, min_card: float = 1.2) -> list[Cue]:
    """One cue per title card. Sentences of a shot share its time by length."""
    cues: list[Cue] = []
    for shot in reel["shots"]:
        cards = common.cards(shot[f"text_{lang}"])
        if not cards:
            continue
        start, end = float(shot["start"]), float(shot["end"])
        span = end - start
        if len(cards) == 1 or span < min_card * len(cards):
            cues.append(Cue(start, end, " ".join(cards)))
            continue
        t = start
        for card, dur in zip(cards, _split_time(span, [len(c) for c in cards], min_card)):
            cues.append(Cue(round(t, 3), round(t + dur, 3), card))
            t += dur
        cues[-1].end = end
    return cues


def _srt_time(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _ass_time(sec: float) -> str:
    cs = int(round(sec * 100))
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def to_srt(cues: list[Cue]) -> str:
    blocks = [f"{i}\n{_srt_time(c.start)} --> {_srt_time(c.end)}\n{c.text}\n" for i, c in enumerate(cues, 1)]
    return "\n".join(blocks)


def _ass_color(hex_rgb: str, alpha: int = 0) -> str:
    h = hex_rgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def font_family_name(font_file: Path, fallback: str) -> str:
    """Family name libass matches on; read from the font when fontTools is present."""
    try:
        from fontTools.ttLib import TTFont

        name = TTFont(str(font_file))["name"]
        return name.getDebugName(1) or fallback
    except Exception:
        return fallback


def to_ass(cues: list[Cue], style: dict, font_name: str) -> str:
    v, t = style["video"], style["titles"]
    side = 90
    # BorderStyle 3: an opaque box in OutlineColour behind each line.
    box = _ass_color(t["box_color"], round(255 * (1 - t["box_opacity"])))
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {v['width']}
PlayResY: {v['height']}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,{font_name},{t['font_size']},{_ass_color(t['color'])},{_ass_color(t['color'])},{box},{box},0,0,0,0,100,100,0,0,3,{t['box_padding_px']},0,2,{side},{side},{t['bottom_margin_px']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    fade = f"{{\\fad({t['fade_in_ms']},{t['fade_out_ms']})}}"
    lines = [
        f"Dialogue: 0,{_ass_time(c.start)},{_ass_time(c.end)},Title,,0,0,0,,{fade}{c.text.replace(chr(10), ' ')}"
        for c in cues
    ]
    return header + "\n".join(lines) + "\n"


def localize(item: dict, uz_script: str, apostrophe: str) -> dict:
    """Return a copy with Uzbek text converted to Latin when asked."""
    if uz_script != "latn":
        return item
    conv = lambda s: to_latin(s, apostrophe)  # noqa: E731
    out = dict(item)
    for key in ("caption_uz", "text_uz"):
        if key in out:
            out[key] = conv(out[key])
    if "hook" in out:
        out["hook"] = {**out["hook"], "uz": conv(out["hook"]["uz"])}
    if "shots" in out:
        out["shots"] = [{**s, "text_uz": conv(s["text_uz"])} for s in out["shots"]]
    if "slides" in out:
        out["slides"] = [{**s, **({"text_uz": conv(s["text_uz"])} if s.get("text_uz") else {})} for s in out["slides"]]
    return out


def build_item(path: Path, out_root: Path, uz_script: str = "cyrl", apostrophe: str = "ʻ") -> list[Path]:
    item = localize(common.load_json(path), uz_script, apostrophe)
    style = common.style()
    out = out_root / item["id"]
    out.mkdir(parents=True, exist_ok=True)
    written = []
    if item["format"] == "reels":
        font_file = common.ROOT / style["titles"]["font_file"]
        font = font_family_name(font_file, style["titles"]["font_family"])
        for lang in ("ru", "uz"):
            cues = reel_cues(item, lang, style["titles"]["min_card_sec"])
            for ext, text in (("srt", to_srt(cues)), ("ass", to_ass(cues, style, font))):
                p = out / f"{item['id']}.{lang}.{ext}"
                p.write_text(text, encoding="utf-8")
                written.append(p)
    caption = out / "caption.txt"
    caption.write_text(common.publication_text(item) + "\n", encoding="utf-8")
    written.append(caption)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Субтитры и подписи Silicare")
    parser.add_argument("ids", nargs="*", help="id файлов; без них — все")
    parser.add_argument("--out", type=Path, default=common.BUILD_DIR)
    parser.add_argument("--uz-script", choices=["cyrl", "latn"], default="cyrl")
    parser.add_argument("--apostrophe", default="ʻ", help="ʻ (U+02BB, официально) или ‘ (U+2018)")
    args = parser.parse_args(argv)

    paths = [common.find_content(i) for i in args.ids] if args.ids else list(common.content_files())
    for path in paths:
        for p in build_item(path, args.out, args.uz_script, args.apostrophe):
            print(p.relative_to(common.ROOT) if p.is_relative_to(common.ROOT) else p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
