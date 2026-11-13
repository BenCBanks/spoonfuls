from pathlib import Path

from app.importer.draft import draft_from_html, import_url, make_draft
from app.importer.fetch import FetchError, FetchedPage

FIXTURES = Path(__file__).parents[2] / "fixtures" / "import"


def test_draft_states_are_honest():
    imported = draft_from_html((FIXTURES / "01-wordpress-recipe.html").read_text(), source_url="https://recipes.example.test/toast")
    assert imported["state"] == "imported"
    partial = draft_from_html((FIXTURES / "12-partial.html").read_text())
    assert partial["state"] == "partial"
    assert partial["missing"] == ["steps"]
    link = draft_from_html((FIXTURES / "13-link-page.html").read_text(), source_url="https://video.example.test/1")
    assert link == {"state": "link", "missing": [], "reason": "no_recipe", "recipe": None}


def test_fetch_error_becomes_link_and_success_uses_final_url():
    def failing(url, **_):
        raise FetchError("blocked_address", "blocked", url=url)

    assert import_url("https://private.example.test/recipe", fetcher=failing)["reason"] == "blocked_address"

    def fake(url, **_):
        return FetchedPage("https://recipes.example.test/final", '<script type="application/ld+json">{"@type":"Recipe","name":"Tiny","recipeIngredient":["1 pear"],"recipeInstructions":["Eat."]}</script>', "text/html")

    result = import_url("https://recipes.example.test/start", fetcher=fake)
    assert result["state"] == "imported"
    assert result["recipe"]["source_url"] == "https://recipes.example.test/final"
