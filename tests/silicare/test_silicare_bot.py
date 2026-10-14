"""Bot knowledge base and handoff rules (silicare/bot.py)."""

from __future__ import annotations

import pytest

from silicare import bot, common

DIALOGS = common.load_json(bot.BOT_DIR / "test_dialogs.json")["dialogs"]


def test_twenty_dialogs_with_dangerous_cases():
    assert len(DIALOGS) == 20
    assert sum(1 for d in DIALOGS if d.get("danger")) >= 8


def test_all_test_dialogs_pass():
    assert bot.run_tests() == []


@pytest.mark.parametrize(
    "message",
    ["Посмотрите, это нормальный рубец?", "Что это у меня?", "Вот мой шов", "Как клеить?", "Сколько стоит?", ""],
)
def test_no_diagnosis_by_photo(message):
    reply = bot.respond(message or "фото", has_photo=True)
    assert reply.action in ("human", "urgent_human")
    assert bot.never_say_violations(reply.text) == []


def test_red_flags_beat_photo_and_faq():
    reply = bot.respond("Как клеить, если из шва гной?", has_photo=True)
    assert reply.action == "urgent_human"
    assert "103" in reply.text


def test_every_canned_text_is_clean():
    faq = common.load_json(bot.BOT_DIR / "faq.json")
    handoff = common.load_json(bot.BOT_DIR / "handoff.json")
    texts = [i["answer"][lang] for i in faq["items"] for lang in ("ru", "uz")]
    texts += [r["reply"][lang] for r in handoff["rules"] for lang in ("ru", "uz")]
    for text in texts:
        assert bot.never_say_violations(text) == [], text


def test_product_data_gaps_go_to_a_person():
    for message in ("Сколько стоит?", "Где купить?", "Какой размер выбрать?"):
        assert bot.respond(message).action == "human"


@pytest.mark.parametrize(
    ("message", "lang", "latin"),
    [("Как клеить?", "ru", False), ("Қандай ёпиштирилади?", "uz", False), ("Narxi qancha?", "uz", True)],
)
def test_language_detection(message, lang, latin):
    assert bot.detect_lang(message) == (lang, latin)


def test_latin_question_gets_latin_answer():
    reply = bot.respond("Qanday yopishtiriladi?")
    assert reply.latin and "Teri toza" in reply.text


def test_unknown_question_goes_to_a_person():
    assert bot.respond("Привет").action == "human"
