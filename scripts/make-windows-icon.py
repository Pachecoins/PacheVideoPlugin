"""Create a multi-resolution Windows icon from the canonical PacheVideo logo."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


SIZES = (16, 24, 32, 48, 64, 128, 256)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    with Image.open(args.source) as source:
        image = source.convert("RGBA").resize((512, 512), Image.Resampling.LANCZOS)
        args.destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(args.destination, format="ICO", sizes=[(size, size) for size in SIZES])


if __name__ == "__main__":
    main()
