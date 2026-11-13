"""Read Recipe schema data without executing page content."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any, Iterable

from .ingredients import parse_ingredient

MAX_DOCUMENT_BYTES = 2_000_000
MAX_SCRIPT_BYTES = 256_000
MAX_DEPTH = 20
MAX_NODES = 10_000


class RecipeParseError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str]
    children: list["_Node"] = field(default_factory=list)
    data: list[str] = field(default_factory=list)


class _HTMLTree(HTMLParser):
    _void = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("#document", {})
        self.stack = [self.root]
        self.scripts: list[str] = []
        self._script_node: _Node | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(tag.lower(), {key.lower(): value or "" for key, value in attrs})
        self.stack[-1].children.append(node)
        if tag.lower() not in self._void:
            self.stack.append(node)
            if tag.lower() == "script" and "ld+json" in node.attrs.get("type", "").lower():
                self._script_node = node

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in self._void and len(self.stack) > 1:
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break
        if tag == "script":
            self._script_node = None

    def handle_data(self, data: str) -> None:
        self.stack[-1].data.append(data)


def _walk(node: _Node) -> Iterable[_Node]:
    yield node
    for child in node.children:
        yield from _walk(child)


def _text(node: _Node) -> str:
    return re.sub(r"\s+", " ", "".join(node.data + [_text(child) for child in node.children])).strip()


def _value(node: _Node) -> str:
    if node.tag in {"meta", "audio", "embed", "iframe", "img", "source", "track", "video"}:
        return node.attrs.get("content") or node.attrs.get("src") or node.attrs.get("href") or node.attrs.get("alt", "")
    if node.tag == "time":
        return node.attrs.get("datetime") or _text(node)
    if node.tag == "a":
        return node.attrs.get("href") or _text(node)
    return _text(node)


def _type_is(value: Any, wanted: str) -> bool:
    values = value if isinstance(value, list) else [value]
    return any(str(item).rsplit("/", 1)[-1].rsplit("#", 1)[-1].lower() == wanted.lower() for item in values)


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        values = [_as_text(item) for item in value]
        return ", ".join(item for item in values if item) or None
    if isinstance(value, dict):
        return _as_text(value.get("name") or value.get("text") or value.get("url"))
    value = str(value).strip()
    return value or None


def _duration(value: Any) -> int | None:
    text = _as_text(value)
    if not text:
        return None
    match = re.fullmatch(r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?", text.upper())
    if not match:
        return None
    return int(match.group("days") or 0) * 1440 + int(match.group("hours") or 0) * 60 + int(match.group("minutes") or 0) + (1 if int(match.group("seconds") or 0) >= 30 else 0)


def _servings(value: Any) -> int | float | None:
    text = _as_text(value)
    if not text:
        return None
    match = re.search(r"\d+(?:[.,]\d+)?", text)
    if not match:
        return None
    number = float(match.group().replace(",", "."))
    return int(number) if number.is_integer() else number


def _images(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    result: list[str] = []
    for item in values:
        text = _as_text(item)
        if text and text not in result:
            result.append(text)
    return result


def _instruction_steps(value: Any) -> list[dict[str, str | None]]:
    values = value if isinstance(value, list) else [value]
    steps: list[dict[str, str | None]] = []
    for item in values:
        if isinstance(item, dict) and _type_is(item.get("@type"), "HowToSection"):
            section = _as_text(item.get("name"))
            children = item.get("itemListElement") or item.get("steps") or []
            for child in (children if isinstance(children, list) else [children]):
                text = _as_text(child)
                if isinstance(child, dict):
                    text = _as_text(child.get("text") or child.get("name"))
                if text:
                    steps.append({"section": section, "text": text})
        elif isinstance(item, dict):
            text = _as_text(item.get("text") or item.get("name"))
            if text:
                steps.append({"section": None, "text": text})
        else:
            text = _as_text(item)
            if text:
                steps.append({"section": None, "text": text})
    return steps


def _ingredients(value: Any) -> list[dict[str, Any]]:
    values = value if isinstance(value, list) else [value]
    lines = [parse_ingredient(text) for item in values if (text := _as_text(item))]
    return [{"section": None, "lines": lines}] if lines else []


def _author(value: Any) -> str | None:
    if isinstance(value, list):
        return ", ".join(item for item in (_author(child) for child in value) if item) or None
    if isinstance(value, dict):
        return _as_text(value.get("name"))
    return _as_text(value)


def _normalise(node: dict[str, Any], source_url: str | None = None) -> dict[str, Any]:
    yield_text = _as_text(node.get("recipeYield"))
    publisher = node.get("publisher")
    recipe: dict[str, Any] = {
        "title": _as_text(node.get("name")),
        "summary": _as_text(node.get("description")),
        "yield_text": yield_text,
        "servings": _servings(node.get("recipeYield")),
        "prep_minutes": _duration(node.get("prepTime")),
        "cook_minutes": _duration(node.get("cookTime")),
        "total_minutes": _duration(node.get("totalTime")),
        "ingredients": _ingredients(node.get("recipeIngredient") or node.get("ingredients")),
        "steps": _instruction_steps(node.get("recipeInstructions")),
        "tags": [tag.strip() for tag in (_as_text(node.get("keywords")) or "").split(",") if tag.strip()],
        # The URL we fetched is the source record.  A page's canonical URL is
        # useful only when callers did not provide the fetched URL.
        "source_url": source_url or _as_text(node.get("url") or node.get("mainEntityOfPage")),
        "source_name": _as_text(publisher),
        "source_author": _author(node.get("author")),
        "nutrition": node.get("nutrition") if isinstance(node.get("nutrition"), dict) else None,
        "images": _images(node.get("image")),
    }
    return recipe


def _json_recipe(scripts: list[str], source_url: str | None) -> dict[str, Any] | None:
    for script in scripts:
        if len(script.encode("utf-8")) > MAX_SCRIPT_BYTES:
            continue
        try:
            payload = json.loads(script)
        except (TypeError, json.JSONDecodeError):
            continue
        count = 0

        def walk(value: Any, depth: int = 0) -> dict[str, Any] | None:
            nonlocal count
            if depth > MAX_DEPTH:
                raise RecipeParseError("too_deep", "Recipe metadata is nested too deeply.")
            count += 1
            if count > MAX_NODES:
                raise RecipeParseError("too_large", "Recipe metadata contains too many nodes.")
            if isinstance(value, dict):
                if _type_is(value.get("@type"), "Recipe"):
                    return value
                for child in value.values():
                    found = walk(child, depth + 1)
                    if found:
                        return found
            elif isinstance(value, list):
                for child in value:
                    found = walk(child, depth + 1)
                    if found:
                        return found
            return None

        found = walk(payload)
        if found:
            return _normalise(found, source_url)
    return None


def _microdata_recipe(root: _Node, source_url: str | None) -> dict[str, Any] | None:
    for scope in _walk(root):
        if "itemscope" not in scope.attrs or "itemtype" not in scope.attrs:
            continue
        if not any("recipe" in value.lower() for value in scope.attrs["itemtype"].split()):
            continue
        fields: dict[str, Any] = {}
        for node in _walk(scope):
            if node is scope or "itemprop" not in node.attrs or "itemscope" in node.attrs:
                continue
            props = node.attrs["itemprop"].split()
            value = _value(node)
            for prop in props:
                if not value:
                    continue
                if prop in fields:
                    existing = fields[prop] if isinstance(fields[prop], list) else [fields[prop]]
                    existing.append(value)
                    fields[prop] = existing
                else:
                    fields[prop] = value
        return _normalise(fields, source_url)
    return None


def read_recipe(html: str, *, source_url: str | None = None) -> dict[str, Any] | None:
    """Return normalized Recipe data from JSON-LD or microdata, if present."""
    if not isinstance(html, str):
        raise TypeError("recipe document must be text")
    if len(html.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        raise RecipeParseError("too_large", "Recipe page is larger than the importer limit.")
    parser = _HTMLTree()
    try:
        parser.feed(html)
        parser.close()
    except Exception as exc:  # HTMLParser is permissive, but keep a stable API.
        raise RecipeParseError("invalid_html", "Recipe page could not be read.") from exc
    recipe = _json_recipe([_text(node) for node in _walk(parser.root) if node.tag == "script" and "ld+json" in node.attrs.get("type", "").lower()], source_url)
    return recipe or _microdata_recipe(parser.root, source_url)
