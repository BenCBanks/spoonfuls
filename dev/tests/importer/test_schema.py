from pathlib import Path

import pytest

from app.importer.schema import RecipeParseError, read_recipe

FIXTURES = Path(__file__).parents[2] / "fixtures" / "import"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_json_ld_wordpress_recipe_is_normalized():
    recipe = read_recipe(fixture("01-wordpress-recipe.html"), source_url="https://recipes.example.test/toast")
    assert recipe["title"] == "Moonlit Tomato Toast"
    assert recipe["servings"] == 2
    assert recipe["ingredients"][0]["lines"][1]["unit"] == "cup"
    assert recipe["steps"][1]["text"] == "Top with tomatoes and salt."
    assert recipe["source_url"] == "https://recipes.example.test/toast"


def test_graph_microdata_and_howto_sections():
    graph = read_recipe(fixture("02-graph.html"))
    assert graph["title"] == "Graph Garden Soup"
    microdata = read_recipe(fixture("03-microdata.html"))
    assert microdata["source_author"] == "Jo Rowan"
    sections = read_recipe(fixture("07-howto-section.html"))
    assert [step["section"] for step in sections["steps"]] == ["Sauce", "Finish"]


def test_duration_nutrition_images_and_non_english_text():
    duration = read_recipe(fixture("08-iso-duration.html"))
    assert duration["prep_minutes"] == 65
    assert duration["total_minutes"] == 1590
    nutrition = read_recipe(fixture("09-nutrition.html"))
    assert nutrition["nutrition"]["calories"] == "120 calories"
    images = read_recipe(fixture("10-multiple-images.html"))
    assert len(images["images"]) == 2
    french = read_recipe(fixture("11-non-english.html"))
    assert french["title"] == "Tarte du matin"
    assert french["ingredients"][0]["lines"][1]["raw"] == "1 pincée de sel"


def test_invalid_or_missing_recipe_returns_none():
    assert read_recipe(fixture("04-no-recipe.html")) is None
    assert read_recipe(fixture("05-broken-json.html")) is None


def test_document_and_metadata_limits():
    with pytest.raises(RecipeParseError, match="larger"):
        read_recipe("x" * 2_000_001)
    nested = "{\"a\":" * 25 + "null" + "}" * 25
    html = f'<script type="application/ld+json">{nested}</script>'
    # Invalid JSON is ignored, while a valid deeply nested graph is rejected.
    valid = "{\"a\":" * 21 + "{\"@type\":\"Recipe\"}" + "}" * 21
    with pytest.raises(RecipeParseError, match="deeply"):
        read_recipe(f'<script type="application/ld+json">{valid}</script>')
