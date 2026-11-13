from app.importer.ingredients import parse_ingredient, parse_quantity


def test_fraction_range_and_note_keep_source_line():
    result = parse_ingredient("1 1/2–2 cups flour (sifted)")
    assert result == {
        "raw": "1 1/2–2 cups flour (sifted)",
        "qty": "1 1/2–2",
        "unit": "cups",
        "item": "flour",
        "note": "sifted",
    }


def test_words_and_cook_writers_phrases():
    assert parse_ingredient("a pinch of salt") == {
        "raw": "a pinch of salt",
        "qty": "a pinch",
        "unit": None,
        "item": "salt",
        "note": None,
    }
    assert parse_ingredient("pepper, to taste")["note"] == "to taste"
    assert parse_ingredient("2 tbsp. olive oil")["unit"] == "tbsp"


def test_numeric_helper_is_optional_and_best_effort():
    assert parse_quantity("1 1/2") == 1.5
    assert parse_quantity("2–3") == 2
    assert parse_quantity("a pinch") is None
