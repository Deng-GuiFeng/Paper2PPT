#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
locate_figure.py  —  locate and render the page(s) containing a figure/table.

Two deterministic preparation steps before cropping:

  1. O(n) text scan (PyMuPDF) to find the candidate page(s) where the figure or
     table caption appears.
  2. Render those page(s) to PNG, and also emit a *_grid.png copy with a 0-1000
     coordinate ruler overlaid so the crop region can be read off accurately.
     The bounding box is decided by viewing the rendered page, then handed to
     crop_figure.py.

Usage:
    python locate_figure.py <pdf_path> <figure_name> [options]

Examples:
    python locate_figure.py paper.pdf "Figure 1"
    python locate_figure.py paper.pdf "Table 2" -d work/pages --dpi 200
    python locate_figure.py paper.pdf "Figure 3(a)" --max-pages 2

Output (printed as a small JSON block + human log):
    candidate pages (1-indexed), and for each rendered page:
      - clean image path   (use this for cropping)
      - grid  image path   (read coordinates from this)
      - pixel width/height
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict

try:
    import fitz  # PyMuPDF
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Run: pip install PyMuPDF Pillow")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Figure-name normalization + search variants
# ---------------------------------------------------------------------------

def normalize_figure_name(name: str) -> str:
    name = name.strip()
    name = re.sub(r"\s*\(\s*", "(", name)
    name = re.sub(r"\s*\)\s*", ")", name)
    return name


def build_figure_search_variants(figure_name: str) -> List[str]:
    """Build text-search variants. "Figure 1(a)" -> {"Figure 1(a)","Figure 1",
    "Fig. 1(a)","Fig 1", ...} so the caption is found regardless of notation."""
    normalized = normalize_figure_name(figure_name)
    variants = {normalized}

    sub_match = re.match(
        r"^((?:Figure|Table|Fig\.?)\s*\d+)\s*[\(\[]\s*[a-zA-Z]\s*[\)\]]",
        normalized, re.IGNORECASE,
    )
    if sub_match:
        variants.add(sub_match.group(1))

    for v in list(variants):
        if re.match(r"(?i)^figure\s", v):
            suffix = re.sub(r"(?i)^figure\s+", "", v)
            variants.add(f"Fig. {suffix}")
            variants.add(f"Fig {suffix}")
        elif re.match(r"(?i)^fig\.\s", v):
            suffix = re.sub(r"(?i)^fig\.\s+", "", v)
            variants.add(f"Figure {suffix}")
            variants.add(f"Fig {suffix}")
        elif re.match(r"(?i)^fig\s", v) and not re.match(r"(?i)^fig\.", v):
            suffix = re.sub(r"(?i)^fig\s+", "", v)
            variants.add(f"Figure {suffix}")
            variants.add(f"Fig. {suffix}")
    return list(variants)


def detect_candidate_pages(pdf_path: str, figure_name: str) -> List[int]:
    """Return 0-indexed candidate page numbers via a single O(n) text scan.
    Last occurrence first (captions usually come after in-text references)."""
    doc = fitz.open(pdf_path)
    variants = build_figure_search_variants(figure_name)
    hits: List[int] = []
    for page_num in range(len(doc)):
        text_lower = doc[page_num].get_text().lower()
        for variant in variants:
            if variant.lower() in text_lower:
                hits.append(page_num)
                break
    doc.close()
    return list(reversed(hits)) if len(hits) > 1 else hits


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_page(pdf_path: str, page_num: int, dpi: int) -> Image.Image:
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img


def add_coordinate_grid(img: Image.Image) -> Image.Image:
    """Overlay a 0-1000 coordinate ruler for reading bbox coords precisely.
    Minor lines every 50 units (very faint), major every 100 (faint + labeled),
    bold at 500. The crop is ALWAYS taken from the CLEAN image, never this one."""
    g = img.copy().convert("RGB")
    draw = ImageDraw.Draw(g, "RGBA")
    w, h = g.size

    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            max(13, w // 95),
        )
    except Exception:
        font = ImageFont.load_default()

    minor = (255, 0, 0, 32)    # every 50
    major = (255, 0, 0, 80)    # every 100
    strong = (255, 0, 0, 140)  # 0 / 500 / 1000
    for u in range(0, 1001, 50):
        x = int(u / 1000 * w)
        y = int(u / 1000 * h)
        if u % 100 == 0:
            col = strong if u in (0, 500, 1000) else major
            lw = 2 if u in (0, 500, 1000) else 1
        else:
            col, lw = minor, 1
        draw.line([(x, 0), (x, h)], fill=col, width=lw)   # vertical
        draw.line([(0, y), (w, y)], fill=col, width=lw)   # horizontal
        if u % 100 == 0 and u not in (0, 1000):
            draw.text((x + 3, 3), str(u), fill=(200, 0, 0, 255), font=font)
            draw.text((3, y + 2), str(u), fill=(200, 0, 0, 255), font=font)
    draw.text((6, h - max(20, w // 70) - 4),
              "(0,0) top-left  (1000,1000) bottom-right  | minor lines = 50",
              fill=(160, 0, 0, 255), font=font)
    return g


def main():
    ap = argparse.ArgumentParser(description="Locate + render PDF figure pages (no API)")
    ap.add_argument("pdf_path")
    ap.add_argument("figure_name", help='e.g. "Figure 1", "Table 2", "Figure 3(a)"')
    ap.add_argument("-d", "--output-dir", default="pages", help="dir for rendered pages")
    ap.add_argument("--dpi", type=int, default=200, help="render DPI (default 200; use 300 for dense figures)")
    ap.add_argument("--max-pages", type=int, default=2,
                    help="max candidate pages to render (default 2)")
    ap.add_argument("--no-grid", action="store_true", help="skip the coordinate-grid copy")
    args = ap.parse_args()

    if not os.path.exists(args.pdf_path):
        print(f"Error: PDF not found: {args.pdf_path}")
        sys.exit(1)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(args.pdf_path)
    total_pages = len(doc)
    doc.close()

    candidates = detect_candidate_pages(args.pdf_path, args.figure_name)
    fallback = not candidates
    if fallback:
        # No text layer / not found: hand back the first chunk of pages to scan.
        candidates = list(range(min(total_pages, max(args.max_pages, 4))))

    pages_to_render = candidates[: args.max_pages]
    safe = re.sub(r"[^\w\-_\(\)]", "_", args.figure_name)

    rendered = []
    for p in pages_to_render:
        img = render_page(args.pdf_path, p, args.dpi)
        clean_path = out_dir / f"_{safe}_p{p + 1}.png"
        img.save(clean_path, "PNG")
        entry = {"page": p + 1, "clean": str(clean_path),
                 "width": img.width, "height": img.height}
        if not args.no_grid:
            grid_path = out_dir / f"_{safe}_p{p + 1}_grid.png"
            add_coordinate_grid(img).save(grid_path, "PNG")
            entry["grid"] = str(grid_path)
        rendered.append(entry)

    print(f"[locate] figure='{args.figure_name}'  total_pages={total_pages}")
    print(f"[locate] candidate pages (1-indexed): {[p + 1 for p in candidates]}"
          + ("  (FALLBACK: no text hit, scan these)" if fallback else ""))
    for e in rendered:
        print(f"  page {e['page']}: {e['width']}x{e['height']}px")
        print(f"    clean (crop from this): {e['clean']}")
        if "grid" in e:
            print(f"    grid  (read coords from this): {e['grid']}")

    print("\nRESULT_JSON " + json.dumps(
        {"figure": args.figure_name, "fallback": fallback, "pages": rendered}))


if __name__ == "__main__":
    main()
