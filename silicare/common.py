"""Shared helpers: paths, JSON loading, schema validation, text splitting."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

import jsonschema

ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"

CONTENT_DIRS = ("reels", "posts", "telegram")

# Reference files are validated against a named $defs entry of schema.json.
SCHEMA_BY_PATH = {
    "glossary.json": "glossary",
    "forbidden.json": "forbidden",
    "bot/faq.json": "faq",
    "bot/handoff.json": "handoff",
    "bot/test_dialogs.json": "dialogs",
}

CONTENT_DEF_BY_FORMAT = {
    "reels": "reel",
    "carousel": "post",
    "single": "post",
    "telegram": "telegram_post",
}

STATUS_ORDER = ["draft", "approved", "scheduled", "published"]


def load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=None)
def _schema() -> dict:
    return load_json(ROOT / "schema.json")


def style() -> dict:
    return load_json(ROOT / "style.json")


def forbidden() -> dict:
    return load_json(ROOT / "forbidden.json")


def validate(data: Any, def_name: str) -> list[str]:
    """Validate ``data`` against ``#/$defs/<def_name>``; return readable errors."""
    schema = _schema()
    sub = {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": f"#/$defs/{def_name}"}
    validator = jsonschema.Draft202012Validator(sub)
    errors = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        where = "/".join(str(p) for p in err.absolute_path) or "(корень)"
        errors.append(f"схема: {where}: {err.message}")
    return errors


def content_files(root: Path = ROOT) -> Iterator[Path]:
    for d in CONTENT_DIRS:
        folder = root / d
        if folder.is_dir():
            yield from sorted(folder.glob("*.json"))


def find_content(item_id: str, root: Path = ROOT) -> Path:
    for path in content_files(root):
        if path.stem == item_id:
            return path
    raise FileNotFoundError(f"нет файла с id {item_id} в {', '.join(CONTENT_DIRS)}")


_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def sentences(text: str) -> list[str]:
    """Split text into sentences; keeps the terminal punctuation."""
    text = " ".join(text.split())
    if not text:
        return []
    out: list[str] = []
    for part in _SENTENCE_END.split(text):
        if out and re.fullmatch(r"\d+\.", out[-1]):
            out[-1] = f"{out[-1]} {part}"  # "1. Step" is one card, not two
        elif part:
            out.append(part)
    return out


def is_blank_title(text: str) -> bool:
    return text.strip() in {"", "—", "-", "–"}


def cards(text: str) -> list[str]:
    """Title cards for one shot: each sentence becomes its own card."""
    if is_blank_title(text):
        return []
    return sentences(text)


def word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", text.strip()) if w and not re.fullmatch(r"[—–\-·.]+", w)])


def texts_of(item: dict) -> dict[str, list[tuple[str, str]]]:
    """All human-facing text of an item, as (where, text) pairs per language."""
    out: dict[str, list[tuple[str, str]]] = {"ru": [], "uz": []}
    fmt = item.get("format")
    if fmt == "reels":
        for shot in item.get("shots", []):
            n = shot.get("n")
            out["ru"].append((f"кадр {n}, титры RU", shot.get("text_ru", "")))
            out["uz"].append((f"кадр {n}, титры UZ", shot.get("text_uz", "")))
        hook = item.get("hook") or {}
        out["ru"].append(("hook RU", hook.get("ru", "")))
        out["uz"].append(("hook UZ", hook.get("uz", "")))
    if fmt in ("carousel", "single"):
        for slide in item.get("slides", []):
            n = slide.get("n")
            out["ru"].append((f"слайд {n} RU", slide.get("text_ru", "")))
            if slide.get("text_uz"):
                out["uz"].append((f"слайд {n} UZ", slide["text_uz"]))
    if fmt == "telegram":
        out["ru"].append(("текст RU", item.get("text_ru", "")))
        out["uz"].append(("текст UZ", item.get("text_uz", "")))
    else:
        out["ru"].append(("подпись RU", item.get("caption_ru", "")))
        out["uz"].append(("подпись UZ", item.get("caption_uz", "")))
    return out


def publication_text(item: dict) -> str:
    """The text exactly as it is published.

    Instagram (strategy): RU block -> UZ block -> CTA -> disclaimer -> hashtags.
    Telegram: RU -> UZ -> disclaimer. Wound-topic items carry no price CTA,
    because the product is not shown there.
    """
    rules = forbidden()
    if item.get("format") == "telegram":
        parts = [item.get("text_ru", "").strip(), item.get("text_uz", "").strip()]
    else:
        parts = [item.get("caption_ru", "").strip(), item.get("caption_uz", "").strip()]
        cta = rules.get("cta")
        if cta and item.get("topic") == "scar":
            parts.append(f"{cta['ru']} / {cta['uz']}")
    if item.get("disclaimer"):
        parts.append(f"{rules['disclaimer']['ru']} / {rules['disclaimer']['uz']}")
    if item.get("hashtags"):
        parts.append(" ".join(item["hashtags"]))
    return "\n\n".join(p for p in parts if p)
