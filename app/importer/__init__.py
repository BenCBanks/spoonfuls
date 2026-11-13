"""Safe, offline-friendly recipe importing primitives.

The importer has no web framework or database dependency.  Applications can
compose ``fetch_html``, ``read_recipe`` and ``make_draft`` at their boundary.
"""

from .draft import draft_from_html, import_url, make_draft
from .fetch import FetchError, FetchedPage, fetch_html
from .ingredients import parse_ingredient
from .schema import RecipeParseError, read_recipe

__all__ = [
    "FetchError",
    "FetchedPage",
    "RecipeParseError",
    "draft_from_html",
    "fetch_html",
    "import_url",
    "make_draft",
    "parse_ingredient",
    "read_recipe",
]
