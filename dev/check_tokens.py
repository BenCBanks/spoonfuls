"""Check token contrast and reject the retired warm palette."""

from __future__ import annotations

import sys

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
        ("secondary", "background"),
        ("secondary", "surface"),
        ("accent", "background"),
        ("text-on-accent", "accent"),
    )
    failures: list[str] = []
    for theme, colors in tokens["colors"].items():
        for foreground, background in pairs:
            ratio = contrast(colors[foreground], colors[background])
            if ratio < minimum:
                failures.append(f"{theme}: {foreground} on {background} is {ratio:.2f}:1, needs {minimum:.1f}:1")
    retired = {"#FBF8F3", "#1F1B16", "#B8432A", "#E0775C", "#E9E2D8", "#151311", "#1E1B18", "#2C2824"}
    for theme, colors in tokens["colors"].items():
        for name, value in colors.items():
            if value.upper() in retired:
                failures.append(f"{theme}: retired warm color remains in {name}: {value}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Blueberry token contrast passed ({minimum:.1f}:1 minimum)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
