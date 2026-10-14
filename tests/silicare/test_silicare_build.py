"""Subtitles, publication text and transliteration (silicare/build.py, translit.py)."""

from __future__ import annotations

import re

import pytest

from silicare import build, common
from silicare.translit import to_latin


@pytest.mark.parametrize("path", sorted(common.ROOT.glob("reels/*.json")), ids=lambda p: p.stem)
def test_cues_cover_every_titled_shot(path):
    reel = common.load_json(path)
    for lang in ("ru", "uz"):
        cues = build.reel_cues(reel, lang, min_card=1.2)
        for shot in reel["shots"]:
            inside = [c for c in cues if shot["start"] <= c.start < shot["end"]]
            if common.is_blank_title(shot[f"text_{lang}"]):
                assert not inside
                continue
            assert inside, f"кадр {shot['n']} без титра"
            assert inside[0].start == pytest.approx(shot["start"])
            assert inside[-1].end == pytest.approx(shot["end"])
        for a, b in zip(cues, cues[1:]):
            assert a.end <= b.start + 1e-6
        assert all(c.end - c.start >= 1.2 - 1e-6 or c.end - c.start == pytest.approx(
            next(s["end"] - s["start"] for s in reel["shots"] if s["start"] <= c.start < s["end"])) for c in cues)


def test_sentence_cards_keep_step_numbers():
    assert common.cards("1. Кожа чистая и сухая") == ["1. Кожа чистая и сухая"]
    assert common.cards("Рубец пройдёт сам за месяц. Миф: созревает 12–18 месяцев") == [
        "Рубец пройдёт сам за месяц.", "Миф: созревает 12–18 месяцев"]
    assert common.cards("—") == []


def test_srt_format():
    reel = common.load_json(common.ROOT / "reels" / "reel-02-myth-or-fact.json")
    srt = build.to_srt(build.reel_cues(reel, "ru"))
    first = srt.split("\n\n")[0].splitlines()
    assert first[0] == "1"
    assert re.fullmatch(r"\d\d:\d\d:\d\d,\d{3} --> \d\d:\d\d:\d\d,\d{3}", first[1])
    assert first[2] == "Миф или факт?"


def test_ass_is_vertical_and_keeps_bottom_safe_zone():
    style = common.style()
    reel = common.load_json(common.ROOT / "reels" / "reel-01-how-to-apply.json")
    ass = build.to_ass(build.reel_cues(reel, "ru"), style, "Manrope SemiBold")
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
    style_line = next(line for line in ass.splitlines() if line.startswith("Style: Title,"))
    margin_v = int(style_line.split(",")[-2])
    assert margin_v >= style["safe_zone"]["bottom_px"]
    assert "\\fad(" in ass


def test_publication_text_order_and_disclaimer():
    item = common.load_json(common.ROOT / "reels" / "reel-01-how-to-apply.json")
    text = common.publication_text(item)
    rules = common.forbidden()
    order = [item["caption_ru"][:20], item["caption_uz"][:20], rules["cta"]["ru"], rules["disclaimer"]["ru"],
             rules["disclaimer"]["uz"], item["hashtags"][0]]
    positions = [text.index(part) for part in order]
    assert positions == sorted(positions)


def test_telegram_text_has_disclaimer_and_no_hashtags():
    item = common.load_json(common.ROOT / "telegram" / "tg-02-how-to-apply.json")
    text = common.publication_text(item)
    assert common.forbidden()["disclaimer"]["uz"] in text
    assert "#" not in text


def test_build_writes_files(tmp_path):
    written = build.build_item(common.ROOT / "reels" / "reel-07-asmr.json", tmp_path)
    names = sorted(p.name for p in written)
    assert names == sorted(["reel-07-asmr.ru.srt", "reel-07-asmr.ru.ass", "reel-07-asmr.uz.srt",
                            "reel-07-asmr.uz.ass", "caption.txt"])


@pytest.mark.parametrize(
    ("cyr", "lat"),
    [
        ("Чандиқ 12–18 ой пишади", "Chandiq 12–18 oy pishadi"),
        ("Сақлаб қўйинг", "Saqlab qoʻying"),
        ("Ёпишқоқ томонга тегманг", "Yopishqoq tomonga tegmang"),
        ("Ғалаба", "Gʻalaba"),
        ("Ер ва ерга", "Yer va yerga"),
        ("Ҳимоя плёнкаси", "Himoya plyonkasi"),
        ("ШАРТ", "SHART"),
        ("Шифокор", "Shifokor"),
        ("Цех ва концерт", "Sex va konsert"),
    ],
)
def test_translit(cyr, lat):
    assert to_latin(cyr) == lat


def test_translit_apostrophe_option():
    assert to_latin("қўл", apostrophe="‘") == "qo‘l"


def test_localize_latin_changes_only_uzbek():
    item = common.load_json(common.ROOT / "reels" / "reel-01-how-to-apply.json")
    out = build.localize(item, "latn", "ʻ")
    assert out["caption_ru"] == item["caption_ru"]
    assert out["shots"][1]["text_uz"] == "1. Teri toza va quruq"
    assert item["shots"][1]["text_uz"] == "1. Тери тоза ва қуруқ"
