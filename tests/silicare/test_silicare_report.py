"""Monthly report (silicare/report.py)."""

from __future__ import annotations

from pathlib import Path

from silicare import report

FIX = Path(__file__).parent / "fixtures"


def test_russian_export_and_targets():
    text = report.build_report("2026-11", 1, FIX / "instagram_ru.csv", FIX / "telegram.csv",
                               FIX / "enquiries.csv", followers=320, tg_subscribers=None)
    assert "Публикаций: 4." in text  # the October post is filtered out
    assert "| Подписчики Instagram | 320 | 300 | достигнута |" in text
    assert "| Сохранений на карусель (среднее) | 11.5 | 10 | достигнута |" in text
    assert "| Подписчики Telegram | 141 | 150 | не достигнута |" in text
    top_saves = text.split("### Топ-3 по сохранениям")[1].split("###")[0]
    assert top_saves.strip().startswith("1. [03.11 · Reels] Как клеить")
    assert "Подписчики: 95 → 141 (+46)." in text
    assert "С промокодом SILICARE: 2." in text


def test_english_export():
    posts = report.instagram_posts(FIX / "instagram_en.csv", "2026-11")
    assert [p.kind for p in posts] == ["Карусель", "Reels"]
    assert posts[1].sends_per_1000 == 10.0


def test_missing_sources_say_no_data():
    text = report.build_report("2026-11", 2, None, None, None, None, None)
    assert "нет данных" in text
    assert "Цель M2" in text


def test_number_parsing():
    assert report.num("2 400") == 2400
    assert report.num("1,5") == 1.5
    assert report.num("") == 0
