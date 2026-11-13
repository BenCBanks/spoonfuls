"""Turn parsed recipe metadata into an honest reviewable draft."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .fetch import FetchError, FetchedPage, fetch_html
from .schema import RecipeParseError, read_recipe

def _missing(recipe: dict[str, Any] | None) -> list[str]:
    if recipe is None:
        return []
    missing: list[str] = []
    if not recipe.get("title"):
        missing.append("title")
    if not any(section.get("lines") for section in recipe.get("ingredients", [])):
        missing.append("ingredients")
    if not recipe.get("steps"):
        missing.append("steps")
    return missing


def make_draft(recipe: dict[str, Any] | None, *, reason: str | None = None, source_url: str | None = None) -> dict[str, Any]:
    """Return the import state consumed by review UI and persistence code."""
    if recipe is None:
        return {"state": "link", "missing": [], "reason": reason or "no_recipe", "recipe": None}
    if source_url and not recipe.get("source_url"):
        recipe = {**recipe, "source_url": source_url}
    missing = _missing(recipe)
    state = "partial" if missing else "imported"
    return {"state": state, "missing": missing, "reason": reason, "recipe": recipe}


def draft_from_html(html: str, *, source_url: str | None = None) -> dict[str, Any]:
    try:
        recipe = read_recipe(html, source_url=source_url)
    except RecipeParseError as exc:
        return make_draft(None, reason=exc.code, source_url=source_url)
    return make_draft(recipe, source_url=source_url)


def import_url(
    url: str,
    *,
    fetcher: Callable[..., FetchedPage] = fetch_html,
    **fetch_options: Any,
) -> dict[str, Any]:
    """Fetch and parse a recipe URL, converting expected failures to a link."""
    try:
        page = fetcher(url, **fetch_options)
    except FetchError as exc:
        return make_draft(None, reason=exc.code, source_url=url)
    return draft_from_html(page.body, source_url=page.url)
