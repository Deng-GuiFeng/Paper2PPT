#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
crop_figure.py  —  crop a figure/table from a rendered page by bounding box.

The bounding box is read off the 0-1000 grid produced by locate_figure.py and
passed here. The crop handles three coordinate systems and adds a small margin.

PRECISION AID — every run also writes a "<output>_check.png": the chosen bbox
drawn as a bold box on the page (using the grid copy when available). Inspect that
check image to verify each edge before trusting the crop — it makes "caption
cut off" or "next section bled in" obvious. Adjust --bbox and re-run until the
box is tight.

Coordinate systems accepted for --bbox x1,y1,x2,y2:
    * 0-1000 scale   (default, matches the grid)   e.g. 120,150,880,560
    * normalized 0-1 (if all values <= 1)          e.g. 0.12,0.15,0.88,0.56
    * raw pixels     (if any value > 1000)         e.g. 340,420,2100,1500

Usage:
    python crop_figure.py <page_image.png> --bbox x1,y1,x2,y2 -o <out.png> [--sub] [--no-check]

Examples:
    python crop_figure.py work/pages/_Figure_1_p1.png --bbox 120,558,885,880 \
        -o work/asset/Figure_1.png
    python crop_figure.py work/pages/_Figure_2_p4.png --bbox 60,300,500,720 \
        --sub -o "work/asset/Figure_2(a).png"
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Optional

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Run: pip install Pillow")
    sys.exit(1)


def _to_normalized(bbox: List[float], width: int, height: int) -> List[float]:
    """Auto-detect coordinate system and return normalized 0-1 [x1,y1,x2,y2]."""
    x1, y1, x2, y2 = bbox
    max_coord = max(x1, y1, x2, y2)
    if max_coord > 1:
        if max_coord <= 1000:
            x1, y1, x2, y2 = x1 / 1000.0, y1 / 1000.0, x2 / 1000.0, y2 / 1000.0
        else:
            x1, y1, x2, y2 = x1 / width, y1 / height, x2 / width, y2 / height
    if x1 > x2:
        x1, x2 = x2, x1
    if y1 > y2:
        y1, y2 = y2, y1
    return [x1, y1, x2, y2]


def crop_image_by_bbox(image: "Image.Image", bbox: List[float],
                       padding_percent: float = 0.01) -> "Image.Image":
    """Crop by bbox (auto-detects 0-1000 / normalized / pixel)."""
    width, height = image.size
    x1, y1, x2, y2 = _to_normalized(bbox, width, height)

    x1 = max(0.0, x1 - padding_percent)
    y1 = max(0.0, y1 - padding_percent)
    x2 = min(1.0, x2 + padding_percent)
    y2 = min(1.0, y2 + padding_percent)

    left, top = int(x1 * width), int(y1 * height)
    right, bottom = int(x2 * width), int(y2 * height)
    if right <= left or bottom <= top:
        print(f"  Warning: invalid crop area ({left},{top},{right},{bottom}); returning full page")
        return image
    return image.crop((left, top, right, bottom))


def find_grid_sibling(page_image: str) -> Optional[str]:
    """If page is '_X_pN.png', return '_X_pN_grid.png' when it exists."""
    p = Path(page_image)
    if p.stem.endswith("_grid"):
        return str(p)
    cand = p.with_name(p.stem + "_grid" + p.suffix)
    return str(cand) if cand.exists() else None


def make_check_overlay(base_image_path: str, bbox: List[float], out_path: str) -> None:
    """Draw the chosen bbox as a bold box on the (gridded) page for verification."""
    img = Image.open(base_image_path).convert("RGB")
    w, h = img.size
    x1, y1, x2, y2 = _to_normalized(bbox, w, h)
    px = [int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h)]
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle(px, fill=(0, 120, 255, 28))            # faint fill = captured region
    draw.rectangle(px, outline=(0, 120, 255, 255), width=max(3, w // 350))
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", max(14, w // 80))
    except Exception:
        font = ImageFont.load_default()
    if max(bbox) > 1:
        label = "bbox " + ",".join(str(int(v)) for v in bbox)
    else:
        label = "bbox " + ",".join(f"{v:.3f}" for v in bbox)
    draw.text((px[0] + 4, max(0, px[1] - max(18, w // 70))), label,
              fill=(0, 90, 220, 255), font=font)
    img.save(out_path, "PNG")


def main():
    ap = argparse.ArgumentParser(description="Crop a figure from a rendered page image")
    ap.add_argument("page_image")
    ap.add_argument("--bbox", required=True, help="x1,y1,x2,y2 (0-1000 scale by default)")
    ap.add_argument("-o", "--output", required=True, help="output PNG path")
    ap.add_argument("--padding", type=float, default=None,
                    help="extra margin fraction (default 0.01; 0.005 with --sub)")
    ap.add_argument("--sub", action="store_true", help="sub-figure mode: tighter padding")
    ap.add_argument("--no-check", action="store_true", help="skip the check-overlay image")
    args = ap.parse_args()

    if not os.path.exists(args.page_image):
        print(f"Error: page image not found: {args.page_image}")
        sys.exit(1)
    try:
        bbox = [float(v) for v in args.bbox.split(",")]
        assert len(bbox) == 4
    except Exception:
        print('Error: --bbox must be "x1,y1,x2,y2"')
        sys.exit(1)

    padding = args.padding if args.padding is not None else (0.005 if args.sub else 0.01)

    img = Image.open(args.page_image).convert("RGB")
    cropped = crop_image_by_bbox(img, bbox, padding)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(out, "PNG", optimize=True)
    print(f"[crop] saved: {out}  ({cropped.size[0]}x{cropped.size[1]}px)")

    if not args.no_check:
        base = find_grid_sibling(args.page_image) or args.page_image
        check_path = str(out.with_name(out.stem + "_check.png"))
        make_check_overlay(base, bbox, check_path)
        print(f"[crop] CHECK overlay (inspect to verify edges): {check_path}")


if __name__ == "__main__":
    main()
