"""Check token contrast and reject the retired warm palette."""

from __future__ import annotations

import colorsys
import re
import sys
from pathlib import Path

from generate_tokens import load_tokens


def luminance(value: str) -> float:
    channels = [int(value[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(first: str, second: str) -> float:
    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def main() -> int:
    tokens = load_tokens()
    minimum = float(tokens["contrast-minimum"])
    pairs = (
        ("text", "background"),
        ("text", "surface"),
        ("text", "surface-soft"),
        ("secondary", "background"),
        ("secondary", "surface"),
        ("secondary", "surface-soft"),
        ("accent", "background"),
        ("accent", "surface"),
        ("text-on-accent", "accent"),
    )
    failures: list[str] = []
    for theme, colors in tokens["colors"].items():
        for foreground, background in pairs:
            ratio = contrast(colors[foreground], colors[background])
            if ratio < minimum:
                failures.append(f"{theme}: {foreground} on {background} is {ratio:.2f}:1, needs {minimum:.1f}:1")
            hue, saturation, _value = colorsys.rgb_to_hsv(
                int(colors[foreground][1:3], 16) / 255,
                int(colors[foreground][3:5], 16) / 255,
                int(colors[foreground][5:7], 16) / 255,
            )
            if 10 <= hue * 360 <= 50 and saturation > 0.35:
                failures.append(f"{theme}: orange-family hue is not allowed in {foreground}: {colors[foreground]}")
    for theme, colors in tokens["colors"].items():
        for name, value in colors.items():
            hue, saturation, _value = colorsys.rgb_to_hsv(
                int(value[1:3], 16) / 255,
                int(value[3:5], 16) / 255,
                int(value[5:7], 16) / 255,
            )
            if 10 <= hue * 360 <= 50 and saturation > 0.35:
                failures.append(f"{theme}: orange-family hue is not allowed in {name}: {value}")
    for stylesheet in (Path(__file__).resolve().parents[1] / "app" / "static").glob("*.css"):
        if stylesheet.name == "tokens.css":
            continue
        raw = stylesheet.read_text(encoding="utf-8")
        if re.search(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla)\s*\(", raw):
            failures.append(f"{stylesheet}: raw color found; use generated token variables")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Blueberry token contrast passed ({minimum:.1f}:1 minimum)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
