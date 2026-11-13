"""Small, lossless ingredient-line parser."""

from __future__ import annotations

import re
from fractions import Fraction

# Keep the source spelling in ``raw``.  These aliases cover common metric and
# imperial forms without trying to turn a cook's wording into a canonical unit.
_UNITS = (
    "teaspoons?|tsp\\.?|tablespoons?|tbsp\\.?|cups?|ounces?|oz\\.?|pounds?|lbs?\\.?|lb\\.?|"
    "stones?|grams?|g\\.?|kilograms?|kg\\.?|milligrams?|mg\\.?|millilit(?:er|re)s?|ml\\.?|"
    "lit(?:er|re)s?|l\\.?|cl\\.?|pinches?|dashes?|handfuls?|cans?|jars?|packages?|pkgs?\\.?|"
    "sticks?|sprigs?|cloves?|slices?|pieces?|large|medium|small"
)
_UNIT_RE = re.compile(rf"^(?P<unit>{_UNITS})(?:\s+|$)", re.IGNORECASE)
_NUMBER = r"(?:\d+(?:[.,]\d+)?(?:\s+\d+/\d+)?|\d+/\d+|[¼½¾⅐⅑⅒⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞])"
_RANGE = rf"{_NUMBER}(?:\s*[-–—]\s*{_NUMBER})?"
_QTY_RE = re.compile(rf"^(?P<qty>{_RANGE})(?:\s+|$)", re.IGNORECASE)
_WORD_QTY_RE = re.compile(r"^(?P<qty>a|an|one|two|three|four|five|half|a half)(?:\s+|$)", re.IGNORECASE)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value).strip(" ,;.")
    return value or None


def parse_ingredient(raw: str) -> dict[str, str | None]:
    """Split one line while retaining the exact original in ``raw``.

    The parser is intentionally conservative: anything it cannot confidently
    classify remains in ``item`` instead of being discarded.
    """
    if not isinstance(raw, str):
        raise TypeError("ingredient line must be text")
    text = raw.strip()
    qty = unit = None
    rest = text

    special = re.match(r"^(?P<qty>a\s+(?:pinch|dash|handful|drizzle|splash)|to\s+taste)(?:\s+of)?\s+", rest, re.I)
    if special:
        qty = _clean(special.group("qty"))
        rest = rest[special.end() :]
    else:
        match = _QTY_RE.match(rest) or _WORD_QTY_RE.match(rest)
        if match:
            qty = _clean(match.group("qty"))
            rest = rest[match.end() :]
        unit_match = _UNIT_RE.match(rest)
        if unit_match:
            unit = _clean(unit_match.group("unit"))
            rest = rest[unit_match.end() :]

    # Parentheses and a trailing comma are the conventions most recipe sites
    # use for preparation notes.  Keep all note text, including "to taste".
    note = None
    paren = re.search(r"\s*\(([^()]*)\)\s*$", rest)
    if paren:
        note = _clean(paren.group(1))
        rest = rest[: paren.start()]
    comma = re.search(r"\s*,\s*(.+)$", rest)
    if comma:
        tail = _clean(comma.group(1))
        note = f"{note}; {tail}" if note else tail
        rest = rest[: comma.start()]
    if note is None and re.search(r"\bto\s+taste$", rest, re.I):
        rest = re.sub(r"\s*[,;]?\s*to\s+taste$", "", rest, flags=re.I)
        note = "to taste"
    return {"raw": raw, "qty": qty, "unit": unit, "item": _clean(rest), "note": note}


def parse_quantity(value: str | None) -> float | None:
    """Best-effort numeric helper for callers that need scaling."""
    if not value:
        return None
    normalized = value.replace("–", "-").replace("—", "-").replace(",", ".")
    if "-" in normalized:
        normalized = normalized.split("-", 1)[0].strip()
    total = 0.0
    for part in normalized.split():
        if part in {"¼", "½", "¾", "⅐", "⅑", "⅒", "⅓", "⅔", "⅕", "⅖", "⅗", "⅘", "⅙", "⅚", "⅛", "⅜", "⅝", "⅞"}:
            total += float(Fraction(part))
        else:
            try:
                total += float(Fraction(part))
            except ValueError:
                return None
    return total
