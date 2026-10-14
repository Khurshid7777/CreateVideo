"""Rule-based replies for the Direct / Telegram bot, and its test run.

The order is fixed by the strategy's hard rules: red flags and photos go to a
person before any FAQ answer is considered. The same knowledge base and the
same test dialogs apply when the bot is later built on ManyChat or an LLM.

    python -m silicare.bot "Как клеить пластырь?"
    python -m silicare.bot --photo "Посмотрите, это нормально?"
    python -m silicare.bot --test      # 20 test dialogs, exit 1 on any failure
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from silicare import common
from silicare.translit import to_latin

BOT_DIR = common.ROOT / "bot"
UZ_CYR = set("ўқғҳЎҚҒҲ")
UZ_CYR_WORDS = re.compile(
    r"\b(нарх\w*|қанча|қандай|қачон|қаерда|салом|ассалому|раҳмат|рахмат|чандиқ\w*|яра\w*|мумкинми|керак|нима|йўқ|бор|илтимос|пластир\w*)\b",
    re.IGNORECASE,
)
UZ_LAT_WORDS = re.compile(
    r"\b(narx\w*|qancha|qanday|qachon|qayerda|salom|assalomu|rahmat|chandiq\w*|yara\w*|mumkinmi|kerak|nima|yo.q|iltimos|plastir\w*|bormi)\b",
    re.IGNORECASE,
)


@dataclass
class Reply:
    action: str  # urgent_human | human | answer | checklist
    rule: str
    lang: str
    latin: bool
    text: str


def detect_lang(message: str) -> tuple[str, bool]:
    """('uz' | 'ru', is_latin_script)."""
    if any(ch in UZ_CYR for ch in message) or UZ_CYR_WORDS.search(message):
        return "uz", False
    if UZ_LAT_WORDS.search(message) or re.search(r"[oOgG][ʻ‘'`]", message):
        return "uz", True
    return "ru", False


@lru_cache(maxsize=None)
def _load(bot_dir: str) -> tuple[dict, dict]:
    d = Path(bot_dir)
    return common.load_json(d / "handoff.json"), common.load_json(d / "faq.json")


def _matches(patterns: list[str], text: str) -> bool:
    norm = text.lower().replace("ё", "е")
    return any(re.search(p.replace("ё", "е"), norm, re.IGNORECASE) for p in patterns)


def _has_placeholder(text: str) -> bool:
    return any(p in text for p in ("…", "TODO", "TBD"))


def respond(message: str, has_photo: bool = False, bot_dir: Path = BOT_DIR) -> Reply:
    handoff, faq = _load(str(bot_dir))
    lang, latin = detect_lang(message)

    def make(action: str, rule: str, texts: dict) -> Reply:
        text = texts[lang]
        if latin:
            text = to_latin(text)
        return Reply(action, rule, lang, latin, text)

    for rule in sorted(handoff["rules"], key=lambda r: -r["priority"]):
        when = rule["when"]
        if when.get("has_photo") and has_photo:
            return make(rule["action"], rule["id"], rule["reply"])
        if when.get("any") and _matches(when["any"], message):
            return make(rule["action"], rule["id"], rule["reply"])

    for item in faq["items"]:
        if _matches(item["triggers"], message):
            if item.get("needs_product_data") and _has_placeholder(item["answer"][lang]):
                # Price, stock and sizes are not known yet: a person answers.
                return make("human", f"{item['id']}:no_product_data", handoff["fallback"]["reply"])
            return make("answer", item["id"], item["answer"])

    return make(handoff["fallback"]["action"], "fallback", handoff["fallback"]["reply"])


def never_say_violations(text: str, bot_dir: Path = BOT_DIR) -> list[str]:
    handoff, _ = _load(str(bot_dir))
    rules = handoff.get("never_say", []) + common.load_json(bot_dir.parent / "forbidden.json")["phrases"]
    norm = text.lower().replace("ё", "е")
    return [r["reason"] for r in rules if re.search(r["pattern"].replace("ё", "е"), norm, re.IGNORECASE)]


def run_tests(bot_dir: Path = BOT_DIR) -> list[str]:
    """Run test_dialogs.json; return failures (empty list = all passed)."""
    dialogs = common.load_json(bot_dir / "test_dialogs.json")["dialogs"]
    failures = []
    for d in dialogs:
        r = respond(d["message"], d.get("has_photo", False), bot_dir)
        exp = d["expect"]
        problems = []
        if r.action != exp["action"]:
            problems.append(f"действие {r.action} ({r.rule}), ожидалось {exp['action']}")
        if exp.get("rule") and r.rule != exp["rule"]:
            problems.append(f"правило {r.rule}, ожидалось {exp['rule']}")
        if exp.get("lang") and r.lang != exp["lang"]:
            problems.append(f"язык {r.lang}, ожидался {exp['lang']}")
        for part in exp.get("contains", []):
            if part.lower() not in r.text.lower():
                problems.append(f"в ответе нет «{part}»")
        if d.get("has_photo") and r.action not in ("human", "urgent_human"):
            problems.append("фото не передано человеку")
        problems += [f"запрещено: {v}" for v in never_say_violations(r.text, bot_dir)]
        if problems:
            failures.append(f"{d['id']} «{d['message']}»: " + "; ".join(problems))
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Бот Silicare: ответ на сообщение или прогон тестов")
    parser.add_argument("message", nargs="?")
    parser.add_argument("--photo", action="store_true", help="сообщение с фото")
    parser.add_argument("--test", action="store_true", help="прогнать test_dialogs.json")
    args = parser.parse_args(argv)

    if args.test:
        failures = run_tests()
        total = len(common.load_json(BOT_DIR / "test_dialogs.json")["dialogs"])
        for f in failures:
            print(f"FAIL {f}")
        print(f"\nПройдено {total - len(failures)} из {total}")
        return 1 if failures else 0
    if not args.message:
        parser.error("нужно сообщение или --test")
    r = respond(args.message, args.photo)
    print(f"[{r.action} · {r.rule} · {r.lang}{'-latn' if r.latin else ''}]\n{r.text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
