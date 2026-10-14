"""Autocheck rules (silicare/check.py) on the real content and on broken copies."""

from __future__ import annotations

import copy
import shutil
from pathlib import Path

import pytest

from silicare import common
from silicare.check import Checker, measured_numbers

REEL = common.load_json(common.ROOT / "reels" / "reel-01-how-to-apply.json")
POST = common.load_json(common.ROOT / "posts" / "post-01-meet-silicare.json")


def errors_for(item: dict, publish: bool = False) -> list[str]:
    checker = Checker(publish=publish)
    checker.check_item(item, "test.json", item["id"])
    return [f.message for f in checker.findings if f.level == "error"]


def warnings_for(item: dict) -> list[str]:
    checker = Checker()
    checker.check_item(item, "test.json", item["id"])
    return [f.message for f in checker.findings if f.level == "warning"]


def reel(**changes) -> dict:
    item = copy.deepcopy(REEL)
    item.update(changes)
    return item


def test_repository_content_has_no_errors():
    findings = Checker().check_all()
    errors = [str(f) for f in findings if f.level == "error"]
    assert errors == []


def test_every_content_file_is_checked():
    assert len(list(common.content_files())) >= 7 + 9 + 3


def test_publication_mode_blocks_pending_sources_and_lawyer():
    errs = errors_for(REEL, publish=True)
    assert any("источник не уточнён" in e for e in errs)
    assert any("не утверждён юристом" in e for e in errs)


@pytest.mark.parametrize(
    "phrase",
    ["Рубец уйдёт навсегда", "Результат 100%", "Одобрено Минздравом", "Разрешено Минздравом",
     "Единственное эффективное средство", "Полностью уберёт рубец", "95% пациентов довольны",
     "Рубец станет мягче и светлее", "Рубец созревает до 12 месяцев"],
)
def test_forbidden_phrases_in_caption(phrase):
    item = reel(caption_ru=REEL["caption_ru"] + "\n" + phrase + ".")
    assert any("запрещённая фраза" in e for e in errors_for(item))


def test_hedged_effect_is_allowed():
    item = reel(caption_ru=REEL["caption_ru"] + "\nСиликон может помочь рубцу стать мягче.")
    assert errors_for(item) == []


def test_uzbek_forbidden_phrase():
    item = reel(caption_uz=REEL["caption_uz"] + "\nЧандиқ абадий йўқолади.")
    assert any("абадий" in e for e in errors_for(item))


def test_second_person_condition_is_an_error():
    item = reel(caption_ru=REEL["caption_ru"] + "\nУ вас рана? Читайте.")
    assert any("обращение к состоянию" in e for e in errors_for(item))


@pytest.mark.parametrize("price", ["Цена 10$", "Всего 12 USD", "Стоит 900 рублей", "Цена 9 евро"])
def test_foreign_currency_is_an_error(price):
    item = reel(caption_ru=REEL["caption_ru"] + "\n" + price + ".")
    assert any("валюта" in e for e in errors_for(item))


def test_price_in_sums_is_only_a_warning_on_instagram():
    item = reel(caption_ru=REEL["caption_ru"] + "\nЦена 120 000 сум.")
    assert errors_for(item) == []
    assert any("цена в Instagram" in w for w in warnings_for(item))


@pytest.mark.parametrize("n", [2, 6])
def test_hashtag_count(n):
    item = reel(hashtags=[f"#tag{i}" for i in range(n)])
    assert any("хэштегов" in e for e in errors_for(item))


def test_disclaimer_required_when_product_shown():
    assert any("дисклеймер" in e for e in errors_for(reel(disclaimer=False)))


def test_missing_uzbek_title():
    item = reel()
    item["shots"][1]["text_uz"] = "—"
    assert any("только на одном языке" in e for e in errors_for(item))


def test_uzbek_caption_must_differ_from_russian():
    item = reel(caption_uz=REEL["caption_ru"])
    assert any("перевода нет" in e for e in errors_for(item))


def test_search_phrase_in_first_two_sentences():
    item = reel(caption_ru="Первое. Второе. " + REEL["caption_ru"])
    assert any("поисковой фразы" in e for e in errors_for(item))


def test_wound_word_needs_after_healing_context():
    bad = reel(caption_ru=REEL["caption_ru"] + "\nКлейте пластырь прямо на рану.")
    assert any("о ране только" in e for e in errors_for(bad))
    good = reel(caption_ru=REEL["caption_ru"] + "\nНе клейте на открытую рану.")
    assert errors_for(good) == []


def test_wound_or_blood_in_frame():
    item = reel()
    item["shots"][0]["visual"] = "Крупный план: свежий шов и кровь"
    assert any("в кадре нет раны" in e for e in errors_for(item))


def test_status_above_draft_needs_reviews():
    assert any("допустим только draft" in e for e in errors_for(reel(status="approved")))
    ok = reel(status="approved", reviewed_by_native_uz=True, approved_by_owner=True)
    assert not any("допустим только draft" in e for e in errors_for(ok))


def test_pending_source_is_warning_for_draft_and_error_for_publication():
    assert any("источник не уточнён" in w for w in warnings_for(REEL))
    assert not any("источник не уточнён" in e for e in errors_for(REEL))
    approved = reel(status="approved", reviewed_by_native_uz=True, approved_by_owner=True)
    assert any("источник не уточнён" in e for e in errors_for(approved))


def test_shot_timeline_must_be_contiguous():
    item = reel()
    item["shots"][2]["start"] = 6.5
    assert any("не совпадает с концом" in e for e in errors_for(item))


def test_wound_topic_rules():
    item = reel(topic="wound", disclaimer=False)
    item["shots"][0]["visual"] = "Упаковка Silicare на льне"
    errs = errors_for(item)
    assert any("продукт не показываем" in e for e in errs)
    assert any("При сомнениях обратитесь к врачу" in e for e in errs)


def test_schema_error_is_reported():
    item = reel()
    del item["claims"]
    assert any(e.startswith("схема:") for e in errors_for(item))


def test_carousel_rules_apply():
    post = copy.deepcopy(POST)
    post["caption_ru"] += "\nГарантируем результат."
    assert any("запрещённая фраза" in e for e in errors_for(post))


def test_measured_numbers():
    assert measured_numbers("Носить 12–24 часа в день") == ["12–24"]
    assert measured_numbers("Дни 14–21: рана закрыта") == ["14–21"]
    assert measured_numbers("Как клеить за 20 секунд") == []


def test_schedule_approved_needs_approved_file(tmp_path: Path):
    root = tmp_path / "silicare"
    shutil.copytree(common.ROOT, root, ignore=shutil.ignore_patterns("build", "*.py", "__pycache__", "assets"))
    schedule = root / "schedule.csv"
    text = schedule.read_text(encoding="utf-8").replace("ждёт проверки", "утверждено", 1)
    schedule.write_text(text, encoding="utf-8")
    checker = Checker(root=root)
    checker.check_schedule(schedule)
    assert any("не утверждён владельцем" in f.message for f in checker.findings)
