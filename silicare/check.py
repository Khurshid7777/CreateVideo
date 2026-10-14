"""Autocheck: blocks publication of texts that break the Silicare rules.

Usage (from the repository root):
    python -m silicare.check                 # all files, draft rules
    python -m silicare.check --publish       # publication rules for everything
    python -m silicare.check silicare/reels/reel-01-how-to-apply.json

Errors stop a commit (pre-commit hook) and publication. Warnings point at work
that is still pending (sources, native-speaker review, lawyer) and become
errors once an item's status is above draft or --publish is given.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from silicare import common
from silicare.common import ROOT

SCHEDULE_STATUSES = {"ждёт проверки", "утверждено", "опубликовано"}
_NUM = r"\d+(?:[,.]\d+)?(?:\s*[–—-]\s*\d+(?:[,.]\d+)?)?"
_UNIT_AFTER = r"(?:час|ч\b|дн|день|дня|недел|месяц|мес\b|год|лет|см\b|мм\b|%|раз\b|spf)"
_UNIT_BEFORE = r"(?:день|дни|дня|дней|недел\w*|месяц\w*|spf)"
# A number counts as a medical fact when a unit of time, size or dose is next to it.
MEASURED_RE = re.compile(
    rf"(?P<a>{_NUM})\s*(?:до\s+\d+\s*)?{_UNIT_AFTER}|{_UNIT_BEFORE}\s+(?P<b>{_NUM})",
    re.IGNORECASE,
)
STEP_RE = re.compile(r"^\s*\d+\.\s")


def measured_numbers(text: str) -> list[str]:
    return [m.group("a") or m.group("b") for m in MEASURED_RE.finditer(text.replace("ё", "е"))]


@dataclass
class Finding:
    level: str  # "error" | "warning"
    file: str
    message: str

    def __str__(self) -> str:
        mark = "ОШИБКА" if self.level == "error" else "предупр."
        return f"[{mark}] {self.file}: {self.message}"


def _norm(text: str, lang: str) -> str:
    text = text.lower()
    return text.replace("ё", "е") if lang == "ru" else text


def _compile(rule: dict, lang: str) -> re.Pattern:
    pattern = rule["pattern"]
    if lang == "ru":
        pattern = pattern.replace("ё", "е")
    return re.compile(pattern, re.IGNORECASE)


def _rules_for(rules: list[dict], lang: str, topic: str | None = None) -> list[dict]:
    out = []
    for rule in rules:
        if rule.get("lang", "any") not in (lang, "any"):
            continue
        if rule.get("scope") == "product" and topic != "scar":
            continue
        out.append(rule)
    return out


def _search(rules: list[dict], text: str, lang: str):
    norm = _norm(text, lang)
    for rule in rules:
        m = _compile(rule, lang).search(norm)
        if m:
            yield rule, m.group(0)


def _norm_dash(s: str) -> str:
    return re.sub(r"\s*[–—-]\s*", "–", s)


class Checker:
    def __init__(self, publish: bool = False, root: Path = ROOT):
        self.publish = publish
        self.root = root
        self.rules = common.load_json(root / "forbidden.json")
        self.style = common.load_json(root / "style.json")
        glossary_path = root / "glossary.json"
        self.glossary = common.load_json(glossary_path) if glossary_path.exists() else {"terms": []}
        self.findings: list[Finding] = []

    # -- reporting -------------------------------------------------------
    def err(self, file: str, msg: str) -> None:
        self.findings.append(Finding("error", file, msg))

    def warn(self, file: str, msg: str) -> None:
        self.findings.append(Finding("warning", file, msg))

    def pending(self, file: str, msg: str, publication: bool) -> None:
        """Pending work: warning for drafts, error for publication."""
        (self.err if publication else self.warn)(file, msg)

    # -- entry points ----------------------------------------------------
    def check_all(self) -> list[Finding]:
        for rel, def_name in common.SCHEMA_BY_PATH.items():
            path = self.root / rel
            if path.exists():
                for e in common.validate(common.load_json(path), def_name):
                    self.err(rel, e)
        self.check_bot_texts()
        for path in common.content_files(self.root):
            self.check_file(path)
        schedule = self.root / "schedule.csv"
        if schedule.exists():
            self.check_schedule(schedule)
        return self.findings

    def check_file(self, path: Path) -> list[Finding]:
        rel = str(path.relative_to(self.root)) if path.is_relative_to(self.root) else str(path)
        try:
            item = common.load_json(path)
        except ValueError as exc:
            self.err(rel, f"не JSON: {exc}")
            return self.findings
        self.check_item(item, rel, path.stem)
        return self.findings

    # -- content ---------------------------------------------------------
    def check_item(self, item: dict, rel: str, stem: str | None = None) -> None:
        fmt = item.get("format")
        def_name = common.CONTENT_DEF_BY_FORMAT.get(fmt)
        if def_name is None:
            self.err(rel, f"неизвестный format: {fmt!r}")
            return
        schema_errors = common.validate(item, def_name)
        for e in schema_errors:
            self.err(rel, e)
        if schema_errors:
            return
        if stem and item["id"] != stem:
            self.err(rel, f"id «{item['id']}» не совпадает с именем файла «{stem}»")

        topic = item["topic"]
        status = item["status"]
        publication = self.publish or status != "draft"
        texts = common.texts_of(item)

        self._phrases(item, rel, texts, topic)
        self._currency(item, rel, texts)
        self._uz_present(item, rel, texts)
        self._wound(item, rel, texts, topic)
        self._claims(item, rel, texts, publication)
        self._status(item, rel)
        self._disclaimer(item, rel, topic, publication)
        self._glossary(rel, texts)
        if fmt != "telegram":
            self._hashtags(item, rel)
            self._search_phrase(item, rel)
        if fmt == "reels":
            self._reel_structure(item, rel)
            self._font_coverage(item, rel)
        if publication:
            self._placeholders(item, rel)

    def _phrases(self, item, rel, texts, topic):
        groups = [("запрещённая фраза", self.rules["phrases"]), ("обращение к состоянию", self.rules.get("second_person", []))]
        for lang, pairs in texts.items():
            for where, text in pairs:
                for label, rules in groups:
                    for rule, hit in _search(_rules_for(rules, lang, topic), text, lang):
                        self.err(rel, f"{where}: {label} «{hit}» — {rule['reason']}")

    def _currency(self, item, rel, texts):
        rules = self.rules["currency"]["forbidden"]
        units = [u.lower() for u in self.rules["currency"]["allowed_units"]]
        price_re = re.compile(r"\d[\d\s]*\s*(" + "|".join(re.escape(u) for u in units) + r")", re.IGNORECASE)
        for lang, pairs in texts.items():
            for where, text in pairs:
                for rule, hit in _search(_rules_for(rules, lang), text, lang):
                    self.err(rel, f"{where}: валюта «{hit}» — {rule['reason']}")
                if item["format"] != "telegram" and price_re.search(text):
                    self.warn(rel, f"{where}: цена в Instagram; по стратегии цену не публикуем, CTA «{self.rules['cta']['ru']}»")

    def _uz_present(self, item, rel, texts):
        uz_text = " ".join(t for _, t in texts["uz"])
        if not uz_text.strip():
            self.err(rel, "нет текста UZ")
            return
        ru_caption = item.get("caption_ru") or item.get("text_ru", "")
        uz_caption = item.get("caption_uz") or item.get("text_uz", "")
        if ru_caption.strip() == uz_caption.strip():
            self.err(rel, "текст UZ совпадает с RU: перевода нет")
        if item["format"] == "reels":
            for shot in item["shots"]:
                ru_blank = common.is_blank_title(shot["text_ru"])
                uz_blank = common.is_blank_title(shot["text_uz"])
                if ru_blank != uz_blank:
                    self.err(rel, f"кадр {shot['n']}: титры есть только на одном языке")

    def _wound(self, item, rel, texts, topic):
        wound = self.rules["wound"]
        visuals = []
        if item["format"] == "reels":
            visuals = [(f"кадр {s['n']}, что в кадре", s["visual"]) for s in item["shots"]]
        elif item["format"] in ("carousel", "single"):
            visuals = [(f"слайд {s['n']}, визуал", s.get("visual", "")) for s in item["slides"]]
        for where, text in visuals:
            for rule, hit in _search(_rules_for(wound["forbidden_visual"], "ru"), text, "ru"):
                self.err(rel, f"{where}: «{hit}» — {rule['reason']}")

        if topic == "scar":
            for lang, pairs in texts.items():
                words = _rules_for(wound["words"], lang)
                context = _rules_for(wound["allowed_context"], lang)
                for where, text in pairs:
                    for sentence in common.sentences(text):
                        hits = list(_search(words, sentence, lang))
                        if hits and not list(_search(context, sentence, lang)):
                            self.err(rel, f"{where}: «{sentence}» — о ране только «после заживления» или в предупреждении «не клеить на открытую рану»")
            return

        # topic == "wound": an entry point to the funnel, not an ad.
        for where, text in visuals:
            if re.search(r"silicare|упаковк|пластыр\w* silicare", text, re.IGNORECASE):
                self.err(rel, f"{where}: в роликах про раны продукт не показываем")
        doctor = self.rules["doctor_line"]
        last_ru, last_uz = self._last_texts(item)
        if doctor["ru"].lower() not in last_ru.lower():
            self.err(rel, f"финал RU должен содержать «{doctor['ru']}»")
        if doctor["uz"].lower() not in last_uz.lower():
            self.err(rel, f"финал UZ должен содержать «{doctor['uz']}»")

    @staticmethod
    def _last_texts(item) -> tuple[str, str]:
        fmt = item["format"]
        if fmt == "reels":
            last = item["shots"][-1]
            return last["text_ru"], last["text_uz"]
        if fmt in ("carousel", "single"):
            last = item["slides"][-1]
            return last["text_ru"] + " " + item["caption_ru"], last.get("text_uz", "") + " " + item["caption_uz"]
        return item["text_ru"], item["text_uz"]

    def _claims(self, item, rel, texts, publication):
        placeholders = self.rules["placeholders"]
        claims = item.get("claims", [])
        for i, claim in enumerate(claims, 1):
            source = claim["source"]
            if any(p.lower() in source.lower() for p in placeholders):
                self.pending(rel, f"утверждение {i} «{claim['text']}»: источник не уточнён ({source})", publication)
            if "source_type" not in claim:
                self.warn(rel, f"утверждение {i} «{claim['text']}»: не указан source_type (instruction или study)")
            elif claim["source_type"] == "study" and not claim.get("quote", "").strip():
                self.pending(rel, f"утверждение {i} «{claim['text']}»: нет точной формулировки из источника (quote)", publication)
        claimed = " ".join(_norm_dash(c["text"]) for c in claims)
        for where, text in texts["ru"]:
            for card in common.sentences(text):
                body = STEP_RE.sub("", card)
                for num in measured_numbers(body):
                    if _norm_dash(num) not in claimed:
                        self.warn(rel, f"{where}: «{num}» не подтверждено ни одним claims")

    def _status(self, item, rel):
        if item["status"] != "draft" and not (item["reviewed_by_native_uz"] and item["approved_by_owner"]):
            self.err(rel, f"статус «{item['status']}» без проверки носителем и утверждения владельцем: допустим только draft")

    def _disclaimer(self, item, rel, topic, publication):
        d = self.rules["disclaimer"]
        if topic == "scar" and not item["disclaimer"]:
            self.err(rel, "Silicare в кадре: нужен дисклеймер (disclaimer: true)")
        if item["disclaimer"]:
            if not d["ru"].strip() or not d["uz"].strip():
                self.err(rel, "дисклеймер в forbidden.json пуст на RU или UZ")
            if not d["approved_by_lawyer"]:
                self.pending(rel, "текст дисклеймера не утверждён юристом", publication)

    def _glossary(self, rel, texts):
        for term in self.glossary.get("terms", []):
            for bad in term.get("avoid_uz", []):
                for where, text in texts["uz"]:
                    if bad.lower() in text.lower():
                        self.warn(rel, f"{where}: «{bad}» — по словарю «{term['uz']}» ({term['ru']})")

    def _hashtags(self, item, rel):
        cfg = self.rules["hashtags"]
        n = len(item["hashtags"])
        if not cfg["min"] <= n <= cfg["max"]:
            self.err(rel, f"хэштегов {n}, нужно от {cfg['min']} до {cfg['max']}")
        pool = {h.lower() for h in cfg.get("pool", [])}
        for tag in item["hashtags"]:
            if pool and tag.lower() not in pool:
                self.warn(rel, f"хэштег {tag} не из пула стратегии")

    def _search_phrase(self, item, rel):
        for lang in ("ru", "uz"):
            phrase = item["search_phrase"][lang]
            head = " ".join(common.sentences(item[f"caption_{lang}"])[:2])
            if _norm(phrase, lang) not in _norm(head, lang):
                self.err(rel, f"поисковой фразы «{phrase}» нет в первых двух предложениях подписи {lang.upper()}")

    def _reel_structure(self, item, rel):
        video = self.style["video"]
        titles = self.style["titles"]
        shots = item["shots"]
        length = item["length_sec"]
        if not video["min_sec"] <= length <= video["max_sec"]:
            self.warn(rel, f"длина {length} с вне {video['min_sec']}–{video['max_sec']} с")
        if not video["min_shots"] <= len(shots) <= video["max_shots"]:
            self.warn(rel, f"кадров {len(shots)}, по стилю {video['min_shots']}–{video['max_shots']}")
        prev_end = 0.0
        for i, shot in enumerate(shots, 1):
            if shot["n"] != i:
                self.err(rel, f"кадр {shot['n']}: ожидался номер {i}")
            if abs(shot["start"] - prev_end) > 1e-6:
                self.err(rel, f"кадр {shot['n']}: начало {shot['start']} не совпадает с концом предыдущего {prev_end}")
            if shot["end"] <= shot["start"]:
                self.err(rel, f"кадр {shot['n']}: конец раньше начала")
            prev_end = shot["end"]
            for lang in ("ru", "uz"):
                for card in common.cards(shot[f"text_{lang}"]):
                    if common.word_count(card) > titles["max_words_per_card"]:
                        self.warn(rel, f"кадр {shot['n']} {lang.upper()}: «{card}» длиннее {titles['max_words_per_card']} слов на карточку")
        if abs(prev_end - length) > 1e-6:
            self.err(rel, f"последний кадр заканчивается на {prev_end} с, а length_sec = {length}")
        if common.is_blank_title(shots[0]["text_ru"]):
            self.warn(rel, "в первом кадре нет титра-зацепки")

    def _font_coverage(self, item, rel):
        missing = font_missing_chars(self.root / self.style["titles"]["font_file"],
                                     " ".join(s["text_uz"] + " " + s["text_ru"] for s in item["shots"]))
        if missing is None:
            self.warn(rel, "fontTools не установлен: покрытие шрифта не проверено (pip install fonttools)")
        elif missing:
            self.warn(rel, f"шрифт {self.style['titles']['font_family']} не содержит {' '.join(sorted(missing))}: "
                           "титры с этими буквами не собрать (см. style.json, font_note)")

    def _placeholders(self, item, rel):
        texts = common.texts_of(item)
        for lang, pairs in texts.items():
            for where, text in pairs:
                for p in self.rules["placeholders"]:
                    if p in text:
                        self.err(rel, f"{where}: заглушка «{p}» в тексте к публикации")

    # -- bot ---------------------------------------------------------------
    def check_bot_texts(self) -> None:
        """Bot answers obey the same forbidden phrases and currency rules as posts."""
        sources = []
        faq_path, handoff_path = self.root / "bot" / "faq.json", self.root / "bot" / "handoff.json"
        if faq_path.exists():
            sources += [(f"bot/faq.json: {i['id']}", i["answer"]) for i in common.load_json(faq_path)["items"]]
        if handoff_path.exists():
            handoff = common.load_json(handoff_path)
            sources += [(f"bot/handoff.json: {r['id']}", r["reply"]) for r in handoff["rules"]]
            sources.append(("bot/handoff.json: fallback", handoff["fallback"]["reply"]))
        rules = self.rules["phrases"] + self.rules["currency"]["forbidden"]
        for where, answer in sources:
            for lang in ("ru", "uz"):
                for rule, hit in _search(_rules_for(rules, lang), answer[lang], lang):
                    self.err(where.split(":")[0], f"{where} {lang.upper()}: «{hit}» — {rule['reason']}")

    # -- schedule ----------------------------------------------------------
    def check_schedule(self, path: Path) -> None:
        rel = str(path.relative_to(self.root))
        with open(path, encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            expected = ["date", "time", "format", "file", "status"]
            if reader.fieldnames != expected:
                self.err(rel, f"колонки {reader.fieldnames}, нужно {expected}")
                return
            for line, row in enumerate(reader, 2):
                where = f"строка {line}"
                try:
                    date.fromisoformat(row["date"])
                except ValueError:
                    self.err(rel, f"{where}: дата «{row['date']}» не в формате ГГГГ-ММ-ДД")
                if row["status"] not in SCHEDULE_STATUSES:
                    self.err(rel, f"{where}: статус «{row['status']}», допустимы {sorted(SCHEDULE_STATUSES)}")
                target = self.root / row["file"]
                if not target.exists():
                    self.err(rel, f"{where}: нет файла {row['file']}")
                    continue
                item = common.load_json(target)
                if item.get("format") != row["format"]:
                    self.err(rel, f"{where}: формат «{row['format']}», в файле «{item.get('format')}»")
                if row["status"] in ("утверждено", "опубликовано") and not (
                    item.get("approved_by_owner") and item.get("reviewed_by_native_uz") and item.get("status") != "draft"
                ):
                    self.err(rel, f"{where}: «{row['status']}» в расписании, но {row['file']} не утверждён владельцем и носителем")


def font_missing_chars(font_path: Path, text: str) -> set[str] | None:
    """Characters of ``text`` the font cannot draw; None if fontTools is absent."""
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return None
    if not font_path.exists():
        return {f"(нет файла {font_path.name})"}
    cmap = TTFont(str(font_path)).getBestCmap()
    return {ch for ch in set(text) if not ch.isspace() and ord(ch) not in cmap}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Автопроверка текстов Silicare")
    parser.add_argument("paths", nargs="*", type=Path, help="файлы; без них проверяется всё")
    parser.add_argument("--publish", action="store_true", help="правила публикации для всех файлов")
    parser.add_argument("--errors-only", action="store_true", help="не печатать предупреждения")
    args = parser.parse_args(argv)

    checker = Checker(publish=args.publish)
    if args.paths:
        for p in args.paths:
            checker.check_file(p.resolve())
    else:
        checker.check_all()

    errors = [f for f in checker.findings if f.level == "error"]
    warnings = [f for f in checker.findings if f.level == "warning"]
    for f in errors + ([] if args.errors_only else warnings):
        print(f)
    print(f"\nОшибок: {len(errors)}, предупреждений: {len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
