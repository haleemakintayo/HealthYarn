"""Tests for red-flag safety rule engine (including diacritic-free & mixed-language)."""

import pytest

from app.services.redflag import check_red_flags, normalize_text


@pytest.mark.parametrize(
    "lang,text",
    [
        ("en", "My child is having convulsions right now"),
        ("en", "She is pregnant and bleeding heavily"),
        ("en", "He passed out and is unconscious"),
        ("en", "My baby cannot breathe properly"),
        ("en", "Child is unable to breastfeed and vomiting everything"),
        ("en", "Severe chest pain going to left arm"),
        ("en", "My toddler swallowed bleach"),
        ("en", "High fever with stiff neck and bloody stool"),
        ("yo", "Ọmọ mi ń ṣe gìrì ó sì ń gbọ̀n"),
        ("yo", "Omo mi n se giri bayi"),  # diacritic-free Yoruba
        ("yo", "Ẹ̀jẹ̀ ń dà nínú oyún mi"),
        ("yo", "Eje n da ninu oyun mi"),  # diacritic-free Yoruba
        ("pcm", "My pikin body dey shake and e no fit breathe"),
        ("pcm", "Blood dey comot from my belle during pregnancy"),
        ("pcm", "E don faint no dey wake up"),
        ("en", "My child is having a fit right now"),
        ("yo", "Please help, my child is having convulsions"),  # code-switched English inside yo
    ],
)
def test_red_flags_fire(seeded_session, lang, text):
    hit = check_red_flags(seeded_session, text, lang)
    assert hit is not None, f"Expected red flag for ({lang}): {text}"


@pytest.mark.parametrize(
    "lang,text",
    [
        ("en", "How do I prepare ORS for my child?"),
        ("en", "Should I finish my malaria ACT tablets?"),
        ("yo", "Bawo ni a se n po omi iyo ORS?"),
        ("pcm", "How I go mix ORS water for my pikin?"),
        ("pcm", "I fit buy malaria drug without test?"),
        ("pcm", "Which food dey give strong blood for belle during pregnancy?"),
        ("yo", "Dákun báwo ni a ṣe ń pò ORS?"),
        ("yo", "Kọ́ mi nípa oògùn ibà"),
        ("en", "Where should I store paracetamol safely away from children?"),
    ],
)
def test_ordinary_questions_do_not_fire_red_flags(seeded_session, lang, text):
    hit = check_red_flags(seeded_session, text, lang)
    assert hit is None, f"False positive red flag for ({lang}): {text}"


def test_diacritic_normalization():
    raw, folded = normalize_text("  Ọmọ  MÌ  ń  ṣe  Gìrì  ")
    assert raw == "ọmọ mì ń ṣe gìrì"
    assert folded == "omo mi n se giri"
