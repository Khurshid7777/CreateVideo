"""Monthly report from Instagram Insights and Telegram exports.

    python -m silicare.report --month 2026-11 --month-index 1 \
        --instagram exports/instagram-2026-11.csv \
        --telegram exports/telegram-2026-11.csv \
        --enquiries exports/enquiries.csv --followers 340 --tg-subscribers 120

Instagram: the content CSV from Meta Business Suite (Insights → Content →
Export), English or Russian headers. Telegram: a CSV with date, views and
forwards per post (TGStat or a hand-kept table). Enquiries: the tracking table
(date, source, promo). The report states numbers; decisions are yours.
Output: silicare/reports/<month>.md
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from statistics import mean

from silicare import common

ALIASES = {
    "date": ["publish time", "время публикации", "date", "дата", "published", "дата публикации"],
    "type": ["post type", "тип публикации", "type", "тип", "format", "формат"],
    "link": ["permalink", "постоянная ссылка", "link", "ссылка"],
    "title": ["description", "описание", "caption", "подпись", "title", "post", "пост", "текст"],
    "reach": ["reach", "охват", "accounts reached"],
    "views": ["views", "plays", "просмотры", "воспроизведения", "impressions", "показы"],
    "likes": ["likes", "отметки нравится", "нравится", "лайки", "reactions", "реакции"],
    "shares": ["shares", "репосты", "поделились", "пересылки", "sends", "forwards"],
    "saves": ["saves", "сохранения"],
    "comments": ["comments", "комментарии"],
    "follows": ["follows", "подписки"],
    "subscribers": ["subscribers", "подписчики"],
    "source": ["source", "источник", "канал", "channel"],
    "promo": ["promo", "промокод", "promo code"],
}


def _norm_header(h: str) -> str:
    return re.sub(r"[«»\"'“”]", "", h or "").strip().lower()


def read_table(path: Path) -> list[dict]:
    """Rows keyed by canonical names; unknown columns are dropped."""
    text = path.read_text(encoding="utf-8-sig")
    dialect = csv.Sniffer().sniff(text.splitlines()[0], delimiters=",;\t")
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    mapping = {}
    for header in reader.fieldnames or []:
        h = _norm_header(header)
        for key, names in ALIASES.items():
            if h in names and key not in mapping.values():
                mapping[header] = key
                break
    return [{mapping[k]: v for k, v in row.items() if k in mapping} for row in reader]


def num(value) -> float:
    if value in (None, ""):
        return 0.0
    s = re.sub(r"[\s ]", "", str(value)).replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_date(value: str) -> date | None:
    """Date part of an export timestamp. Meta exports use MM/DD/YYYY."""
    head = (value or "").strip().replace("T", " ").split(" ")[0]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(head, fmt).date()
        except ValueError:
            continue
    return None


def in_month(d: date | None, month: str) -> bool:
    return d is not None and d.strftime("%Y-%m") == month


def kind(row: dict) -> str:
    t = (row.get("type") or "").lower()
    if "reel" in t or "рилс" in t or "видео" in t or "video" in t:
        return "Reels"
    if "carousel" in t or "карусел" in t or "album" in t:
        return "Карусель"
    if "stor" in t or "истори" in t or "сторис" in t:
        return "Сторис"
    return "Пост" if t else "—"


@dataclass
class Post:
    date: date | None
    kind: str
    title: str
    link: str
    reach: float
    shares: float
    saves: float
    comments: float
    likes: float
    follows: float

    @property
    def sends_per_1000(self) -> float:
        return self.shares / self.reach * 1000 if self.reach else 0.0

    @property
    def saves_per_1000(self) -> float:
        return self.saves / self.reach * 1000 if self.reach else 0.0

    def label(self) -> str:
        title = re.sub(r"\s+", " ", self.title).strip()[:60] or "без подписи"
        when = self.date.strftime("%d.%m") if self.date else "?"
        return f"[{when} · {self.kind}] {title}" + (f" ({self.link})" if self.link else "")


@dataclass
class Report:
    month: str
    lines: list[str] = field(default_factory=list)

    def add(self, *lines: str) -> None:
        self.lines.extend(lines)


def instagram_posts(path: Path, month: str) -> list[Post]:
    posts = []
    for row in read_table(path):
        d = parse_date(row.get("date", ""))
        if not in_month(d, month):
            continue
        posts.append(Post(d, kind(row), row.get("title", ""), row.get("link", ""), num(row.get("reach")),
                          num(row.get("shares")), num(row.get("saves")), num(row.get("comments")),
                          num(row.get("likes")), num(row.get("follows"))))
    return posts


def _fmt(x: float, digits: int = 0) -> str:
    return f"{x:,.{digits}f}".replace(",", " ")


def build_report(month: str, month_index: int | None, instagram: Path | None, telegram: Path | None,
                 enquiries: Path | None, followers: int | None, tg_subscribers: int | None) -> str:
    kpi = common.load_json(common.ROOT / "kpi.json")["targets"]
    r = Report(month)
    facts: dict[str, float | None] = {"followers": followers, "telegram_subscribers": tg_subscribers}
    r.add(f"# Отчёт Silicare за {month}", "", f"Собран {date.today().isoformat()} из экспортов. Цифры — факт; решения принимает владелец.", "")

    posts = instagram_posts(instagram, month) if instagram else []
    ig_lines: list[str] = []
    if instagram:
        feed = [p for p in posts if p.kind != "Сторис"]
        carousels = [p for p in feed if p.kind == "Карусель"]
        reels = [p for p in feed if p.kind == "Reels"]
        facts["saves_per_carousel"] = mean(p.saves for p in carousels) if carousels else None
        facts["reels_reach"] = mean(p.reach for p in reels) if reels else None
        total_reach = sum(p.reach for p in feed)
        total_shares = sum(p.shares for p in feed)
        ig_lines += ["## Instagram", ""]
        if not feed:
            ig_lines += ["За месяц в экспорте нет публикаций.", ""]
        else:
            ig_lines += [
                f"Публикаций: {len(feed)}. Охват суммарно: {_fmt(total_reach)}. "
                f"Пересылок на 1 000 охвата: {_fmt(total_shares / total_reach * 1000 if total_reach else 0, 1)}.",
                "",
                "| Формат | Публикаций | Средний охват | Сохранений в среднем | Пересылок на 1 000 охвата |",
                "| --- | --- | --- | --- | --- |",
            ]
            for k in sorted({p.kind for p in feed}):
                group = [p for p in feed if p.kind == k]
                reach = sum(p.reach for p in group)
                ig_lines.append(
                    f"| {k} | {len(group)} | {_fmt(mean(p.reach for p in group))} | {_fmt(mean(p.saves for p in group), 1)} | "
                    f"{_fmt(sum(p.shares for p in group) / reach * 1000 if reach else 0, 1)} |"
                )
            ig_lines.append("")
            ig_lines += ["### Топ-3 по сохранениям", ""]
            ig_lines += [f"{i}. {p.label()} — {_fmt(p.saves)} сохранений" for i, p in enumerate(sorted(feed, key=lambda p: -p.saves)[:3], 1)]
            ig_lines += ["", "### Топ-3 по пересылкам на 1 000 охвата", ""]
            ig_lines += [f"{i}. {p.label()} — {_fmt(p.sends_per_1000, 1)}" for i, p in enumerate(sorted(feed, key=lambda p: -p.sends_per_1000)[:3], 1)]
            ig_lines += ["", "### Что не сработало: наименьший охват", ""]
            ig_lines += [f"{i}. {p.label()} — охват {_fmt(p.reach)}" for i, p in enumerate(sorted(feed, key=lambda p: p.reach)[:3], 1)]
            ig_lines.append("")

    tg_lines: list[str] = []
    if telegram:
        rows = [row for row in read_table(telegram) if in_month(parse_date(row.get("date", "")), month)]
        tg_lines += ["## Telegram", ""]
        if rows:
            views = [num(x.get("views")) for x in rows]
            fwd = sum(num(x.get("shares")) for x in rows)
            tg_lines.append(f"Постов: {len(rows)}. Просмотров в среднем: {_fmt(mean(views))}. Пересылок всего: {_fmt(fwd)}.")
            subs = [num(x.get("subscribers")) for x in rows if x.get("subscribers")]
            if subs:
                diff = subs[-1] - subs[0]
                tg_lines.append(f"Подписчики: {_fmt(subs[0])} → {_fmt(subs[-1])} ({'+' if diff >= 0 else '−'}{_fmt(abs(diff))}).")
                if tg_subscribers is None:
                    facts["telegram_subscribers"] = subs[-1]
        else:
            tg_lines.append("За месяц в экспорте нет постов.")
        tg_lines.append("")

    enq_lines: list[str] = []
    if enquiries:
        rows = [row for row in read_table(enquiries) if in_month(parse_date(row.get("date", "")), month)]
        weeks = 4.345  # average weeks per month
        facts["enquiries_per_week"] = len(rows) / weeks if rows else 0
        enq_lines += ["## Обращения", "", f"Всего: {len(rows)}, в неделю в среднем: {_fmt(len(rows) / weeks, 1)}.", ""]
        by_source: dict[str, int] = {}
        for row in rows:
            src = (row.get("source") or "не указан").strip() or "не указан"
            by_source[src] = by_source.get(src, 0) + 1
        if by_source:
            enq_lines += ["| Источник | Обращений |", "| --- | --- |"]
            enq_lines += [f"| {s} | {n} |" for s, n in sorted(by_source.items(), key=lambda kv: -kv[1])]
            enq_lines.append("")
        promo = sum(1 for row in rows if (row.get("promo") or "").strip().upper() == "SILICARE")
        enq_lines += [f"С промокодом SILICARE: {promo}.", ""]

    r.add("## Цели месяца", "")
    col = f"M{month_index}" if month_index else None
    r.add(f"| Метрика | Факт | Цель {col or '—'} | Статус |", "| --- | --- | --- | --- |")
    for key, meta in kpi.items():
        fact = facts.get(key)
        target = meta.get(col) if col else None
        if fact is None:
            status, fact_s = "нет данных", "—"
        else:
            fact_s = _fmt(fact, 1 if fact % 1 else 0)
            status = "—" if target is None else ("достигнута" if fact >= target else "не достигнута")
        r.add(f"| {meta['label']} | {fact_s} | {_fmt(target) if target is not None else '—'} | {status} |")
    r.add("")
    r.add(*ig_lines, *tg_lines, *enq_lines)
    r.add("## Вопросы подписчиков", "", "Заполняет владелец: темы из Direct, комментариев и бота.", "",
          "## Решения на следующий месяц", "", "Заполняет владелец после чтения цифр.", "")
    return "\n".join(r.lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Месячный отчёт Silicare")
    parser.add_argument("--month", required=True, help="ГГГГ-ММ")
    parser.add_argument("--month-index", type=int, choices=[1, 2, 3], help="какой это месяц ведения, для целей M1–M3")
    parser.add_argument("--instagram", type=Path)
    parser.add_argument("--telegram", type=Path)
    parser.add_argument("--enquiries", type=Path)
    parser.add_argument("--followers", type=int, help="подписчики Instagram на конец месяца")
    parser.add_argument("--tg-subscribers", type=int, help="подписчики Telegram на конец месяца")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if not re.fullmatch(r"\d{4}-\d{2}", args.month):
        parser.error("--month в формате ГГГГ-ММ")
    text = build_report(args.month, args.month_index, args.instagram, args.telegram, args.enquiries,
                        args.followers, args.tg_subscribers)
    out = args.out or common.ROOT / "reports" / f"{args.month}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
