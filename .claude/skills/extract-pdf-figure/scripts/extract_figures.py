#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PDF Figure/Table Extraction Tool v2.0

Uses Qwen3-VL model to locate figures and tables in academic PDFs and extract them precisely.
Supports multi-round quality assessment and coordinate refinement.

Features:
1. Convert PDF pages to high-resolution images
2. Use Qwen3-VL model to locate bounding boxes
3. Multi-round quality assessment with coordinate refinement
4. Support both complete figures and sub-figures (e.g., Figure 1(a))
5. Optional inclusion of extra elements (caption, legend, notes)

Usage:
    python extract_figures.py <pdf_path> <figure_name> [options]

Examples:
    python extract_figures.py "paper.pdf" "Figure 1"
    python extract_figures.py "paper.pdf" "Figure 1" --no-extras
    python extract_figures.py "paper.pdf" --batch "Figure 1,Figure 2,Table 1"
"""

import os
import re
import sys
import json
import base64
import argparse
import tempfile
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

# Load environment variables
try:
    from dotenv import load_dotenv
    # Load from project root .env file
    project_root = Path(__file__).resolve().parents[4]  # .claude/skills/extract-pdf-figure/scripts -> project root
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()  # Try default locations
except ImportError:
    pass  # python-dotenv not installed, rely on system env vars

# Dependency check
try:
    import fitz  # PyMuPDF
    from PIL import Image, ImageDraw
    from openai import OpenAI
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Please run: pip install PyMuPDF Pillow openai python-dotenv")
    sys.exit(1)


# ============== Configuration ==============
# API credentials from environment variables
API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
BASE_URL = os.environ.get("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
MODEL = os.environ.get("QWEN_VL_MODEL", "qwen3-vl-plus")

if not API_KEY:
    print("Error: DASHSCOPE_API_KEY environment variable is not set.")
    print("Please create a .env file with your API key or set the environment variable.")
    print("See .env.example for reference.")
    sys.exit(1)

# Default settings
DEFAULT_MAX_ROUNDS = 7  # Max refinement rounds
DEFAULT_QUALITY_THRESHOLD = 10  # Quality threshold (1-10), high value triggers multi-round refinement


# ============== Utility Functions ==============

def image_to_data_url(image_path: str) -> str:
    """Convert local image to data URL"""
    ext = os.path.splitext(image_path)[1].lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp"
    }
    mime = mime_map.get(ext, "image/png")
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def pdf_page_to_image(pdf_path: str, page_num: int, dpi: int = 300) -> Image.Image:
    """Convert a PDF page to PIL Image"""
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    
    return img


def get_pdf_page_count(pdf_path: str) -> int:
    """Get the number of pages in a PDF"""
    doc = fitz.open(pdf_path)
    count = len(doc)
    doc.close()
    return count


def normalize_figure_name(name: str) -> str:
    """Normalize figure/table name"""
    name = name.strip()
    name = re.sub(r'\s*\(\s*', '(', name)
    name = re.sub(r'\s*\)\s*', ')', name)
    return name


def is_subfigure(figure_name: str) -> bool:
    """Check if this is a sub-figure (e.g., Figure 1a)"""
    pattern = r'(Figure|Table|Fig\.?)\s*\d+\s*[\(\[]?[a-zA-Z][\)\]]?'
    return bool(re.match(pattern, figure_name, re.IGNORECASE))


# ============== Prompt Building ==============

def build_grounding_prompt(figure_name: str, is_sub: bool, include_extras: bool = True) -> str:
    """Build the grounding prompt for locating figures
    
    Args:
        figure_name: Name of the figure/table
        is_sub: Whether this is a sub-figure
        include_extras: Whether to include extra elements (caption, legend, notes)
    """
    normalized_name = normalize_figure_name(figure_name)
    
    if is_sub:
        # Sub-figure: only extract the specific sub-figure
        prompt = f"""Please locate "{normalized_name}" in this image and return ONLY its bounding box coordinates.

IMPORTANT RULES for sub-figure extraction:
1. "{normalized_name}" is a SUB-FIGURE (part of a larger figure)
2. You must locate ONLY the specific sub-figure "{normalized_name}", NOT the entire figure
3. Include the sub-figure's own label if visible (like "(a)" or "a)")
4. Do NOT include the main figure's title, caption, or other sub-figures
5. The bounding box should tightly fit ONLY the sub-figure content

Return the coordinates in this exact JSON format:
{{"bbox": [x1, y1, x2, y2], "found": true}}

Coordinates are in 0-1000 scale (will be normalized later).

If "{normalized_name}" is not found, return:
{{"bbox": null, "found": false}}

Return ONLY the JSON, no other text. Do NOT use <think> tags."""

    elif include_extras:
        # Complete figure: include caption, legend, notes, etc.
        prompt = f"""Please locate "{normalized_name}" in this image and return its bounding box coordinates.

## CRITICAL: MUST INCLUDE THE COMPLETE CAPTION!

The most common error is missing the caption text. You MUST:

1. **FIND THE CAPTION FIRST**:
   - For FIGURES: Look BELOW the diagram for text starting with "{normalized_name}:" or "{normalized_name} |"
   - For TABLES: Look ABOVE the table for the caption
   - Captions often span 2-3 lines - include ALL lines!
   - The caption typically ends before the next section heading or paragraph

2. **THEN INCLUDE**:
   - The main diagram/chart/table content
   - Legends and color keys
   - Axis labels and tick marks
   - Sub-figure labels (a), (b), (c) if composite
   - Notes and footnotes belonging to this figure

3. **BOUNDING BOX TIPS**:
   - Better to include slightly more than to cut off caption text!
   - Add 20-30 units of margin below captions to ensure full text inclusion
   - Captions need approximately 40-60 units of vertical space per line

Return the coordinates in this exact JSON format:
{{"bbox": [x1, y1, x2, y2], "found": true}}

Coordinates are in 0-1000 scale.

If "{normalized_name}" is not found, return:
{{"bbox": null, "found": false}}

Return ONLY the JSON, no other text. Do NOT use <think> tags."""

    else:
        # Main content only: exclude caption, legend, notes
        prompt = f"""Please locate "{normalized_name}" in this image and return its bounding box coordinates.

IMPORTANT: Extract ONLY the MAIN CONTENT, excluding extras:

INCLUDE:
- The actual chart, diagram, image, or table data
- Axis labels and tick marks if part of the visual
- Sub-figure panels (a), (b), etc. if this is a composite figure

DO NOT INCLUDE:
- Figure/Table number and caption text (e.g., "Figure 1: ...")
- External legends or color keys
- Footnotes or source attributions
- Any text that describes the figure but is not part of it

Return the coordinates in this exact JSON format:
{{"bbox": [x1, y1, x2, y2], "found": true}}

Coordinates are in 0-1000 scale.

If "{normalized_name}" is not found, return:
{{"bbox": null, "found": false}}

Return ONLY the JSON, no other text. Do NOT use <think> tags."""

    return prompt


def build_quality_assessment_prompt(
    figure_name: str, 
    prev_bbox: List[float], 
    is_sub: bool, 
    include_extras: bool
) -> str:
    """Build quality assessment prompt"""
    normalized_name = normalize_figure_name(figure_name)
    
    if is_sub:
        # 子图评估
        prompt = f"""You are evaluating a SUB-FIGURE extraction. The red rectangle shows the CURRENT extraction boundary.

Target: "{normalized_name}" (this is a SUB-FIGURE, part of a larger composite figure)
Current bounding box (0-1000 scale): {prev_bbox}

## EVALUATION TASK

Carefully examine the image and answer:
1. Does the red rectangle capture ONLY the sub-figure "{normalized_name}"?
2. Is the sub-figure label (like "(a)") included?
3. Are other sub-figures or the main caption EXCLUDED?

## SCORING (be strict)
- 10: Perfect - only this sub-figure, properly bounded
- 8-9: Good - minor boundary issues
- 5-7: Includes parts of other sub-figures or misses content
- 1-4: Wrong sub-figure or major errors

Return JSON:
{{
    "quality_score": <1-10>,
    "issues": ["specific issues"],
    "needs_refinement": true/false,
    "refined_bbox": [x1, y1, x2, y2] or null
}}

Do NOT use <think> tags. Return ONLY JSON."""
    
    elif include_extras:
        # 完整图表（含附加元素）评估 - 简化且更准确
        prompt = f"""Evaluate this figure/table extraction. The RED RECTANGLE shows the current boundary.

Target: {normalized_name}
Current bbox: {prev_bbox}

## YOUR TASK

1. FIND THE CAPTION: Look for "{normalized_name}:" or "{normalized_name}." text
   - For Figure: typically BELOW the diagram
   - For Table: typically ABOVE the table

2. CHECK: Is the ENTIRE caption text (may be multi-line) inside the red rectangle?

3. CHECK: Is the main figure/table content fully included?

4. CHECK: Are legends, axis labels, notes included?

5. CHECK: Does it accidentally include OTHER figures/tables or unrelated text?

## SCORING (0-10)
- 10: Perfect! All content + full caption + no extras
- 8-9: Minor issues (slight boundary imprecision)
- 6-7: Caption partially cut off OR missing legend
- 1-5: Major problems

## RESPONSE FORMAT
Return JSON only:
{{
    "quality_score": <1-10>,
    "caption_status": "fully_included" | "partially_cut" | "missing" | "cannot_find_caption",
    "caption_text_visible": "<write the caption text you can see inside the red box, or 'none'>",
    "issues": ["list specific issues"],
    "needs_refinement": true/false,
    "refined_bbox": [x1, y1, x2, y2] or null
}}

NOTE: If caption_status is "partially_cut", extend y2 by 40-60 units. If you see significant whitespace below the content but caption is still "partially_cut", reconsider - maybe the caption IS fully included.

Do NOT use <think> tags. ONLY return JSON."""
    
    else:
        # 仅主体内容评估
        prompt = f"""You are evaluating a figure/table extraction (MAIN CONTENT ONLY, no caption). The red rectangle shows the CURRENT extraction boundary.

Target: "{normalized_name}" (extracting main visual content only)
Current bounding box (0-1000 scale): {prev_bbox}

## EVALUATION TASK

Check that the boundary captures:
- The main diagram/chart/table DATA
- Axis labels if part of the visual
- Internal legends if embedded in the figure

Check that it EXCLUDES:
- The caption text (e.g., "Figure 1: ...")
- External notes and footnotes

## SCORING
- 10: Perfect extraction of main content only
- 8-9: Minor issues
- 5-7: Includes caption or misses content
- 1-4: Major errors

Return JSON:
{{
    "quality_score": <1-10>,
    "issues": ["specific issues"],
    "needs_refinement": true/false,
    "refined_bbox": [x1, y1, x2, y2] or null
}}

Do NOT use <think> tags. Return ONLY JSON."""

    return prompt


# ============== API Calls ==============

def call_qwen_vl(
    image_path: str,
    prompt: str,
    temperature: float = 0.1
) -> Optional[Dict[str, Any]]:
    """Call Qwen3-VL model"""
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_to_data_url(image_path)}},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    
    try:
        completion = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=800,
        )
        
        response_text = completion.choices[0].message.content.strip()
        
        # Clean up markdown code blocks and think tags
        if "<think>" in response_text:
            response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL).strip()
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        result = json.loads(response_text)
        return result
        
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"  API call failed: {e}")
        return None


def call_qwen_vl_for_grounding(
    image_path: str,
    figure_name: str,
    is_sub: bool = False,
    include_extras: bool = True
) -> Optional[Dict[str, Any]]:
    """Call Qwen3-VL to get figure bounding box coordinates"""
    prompt = build_grounding_prompt(figure_name, is_sub, include_extras)
    return call_qwen_vl(image_path, prompt)


def call_qwen_vl_for_quality_assessment(
    image_with_bbox_path: str,
    figure_name: str,
    prev_bbox: List[float],
    is_sub: bool,
    include_extras: bool
) -> Optional[Dict[str, Any]]:
    """Call Qwen3-VL to assess extraction quality"""
    prompt = build_quality_assessment_prompt(figure_name, prev_bbox, is_sub, include_extras)
    return call_qwen_vl(image_with_bbox_path, prompt, temperature=0.2)


# ============== Image Processing ==============

def draw_bbox_on_image(image: Image.Image, bbox: List[float]) -> Image.Image:
    """Draw bounding box on image for quality assessment"""
    img_copy = image.copy()
    draw = ImageDraw.Draw(img_copy)
    width, height = image.size
    
    # 转换坐标
    x1, y1, x2, y2 = bbox
    if max(bbox) > 1:  # 1000-based
        x1, y1, x2, y2 = x1/1000*width, y1/1000*height, x2/1000*width, y2/1000*height
    else:  # normalized
        x1, y1, x2, y2 = x1*width, y1*height, x2*width, y2*height
    
    # Draw red bounding box
    draw.rectangle([x1, y1, x2, y2], outline="red", width=3)
    
    return img_copy


def crop_image_by_bbox(
    image: Image.Image,
    bbox: List[float],
    padding_percent: float = 0.01
) -> Image.Image:
    """Crop image by bounding box coordinates"""
    width, height = image.size
    
    x1, y1, x2, y2 = bbox
    
    # 检测坐标格式并归一化
    max_coord = max(x1, y1, x2, y2)
    if max_coord > 1:
        if max_coord <= 1000:
            # 1000-based coordinate system
            x1, y1, x2, y2 = x1/1000.0, y1/1000.0, x2/1000.0, y2/1000.0
        else:
            # Pixel coordinates
            x1, y1, x2, y2 = x1/width, y1/height, x2/width, y2/height
    
    # 确保坐标顺序正确
    if x1 > x2:
        x1, x2 = x2, x1
    if y1 > y2:
        y1, y2 = y2, y1
    
    # 添加 padding
    x1 = max(0, x1 - padding_percent)
    y1 = max(0, y1 - padding_percent)
    x2 = min(1.0, x2 + padding_percent)
    y2 = min(1.0, y2 + padding_percent)
    
    # 转换为像素坐标
    left = int(x1 * width)
    top = int(y1 * height)
    right = int(x2 * width)
    bottom = int(y2 * height)
    
    if right <= left or bottom <= top:
        print(f"  Warning: Invalid crop area ({left}, {top}, {right}, {bottom})")
        return image
    
    return image.crop((left, top, right, bottom))


# ============== Multi-round Extraction Core Logic ==============

def extract_with_refinement(
    page_image: Image.Image,
    figure_name: str,
    is_sub: bool,
    include_extras: bool,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    quality_threshold: int = DEFAULT_QUALITY_THRESHOLD
) -> Optional[Tuple[List[float], int]]:
    """Extract with multi-round quality assessment
    
    Returns:
        Tuple of (final_bbox, quality_score) or None if failed
    """
    quality_score = 5  # Default value
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name
        page_image.save(tmp_path, "PNG")
    
    try:
        # Round 1: Initial grounding
        print(f"    [Round 1/{max_rounds}] Initial grounding...")
        result = call_qwen_vl_for_grounding(tmp_path, figure_name, is_sub, include_extras)
        
        if not result or not result.get("found") or not result.get("bbox"):
            return None
        
        current_bbox = result["bbox"]
        print(f"    Initial bbox: {current_bbox}")
        
        # Multi-round quality assessment and refinement
        for round_num in range(2, max_rounds + 1):
            # Draw current bounding box
            img_with_bbox = draw_bbox_on_image(page_image, current_bbox)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_bbox:
                tmp_bbox_path = tmp_bbox.name
                img_with_bbox.save(tmp_bbox_path, "PNG")
            
            try:
                # Quality assessment
                print(f"    [Round {round_num}/{max_rounds}] Quality assessment...")
                assessment = call_qwen_vl_for_quality_assessment(
                    tmp_bbox_path, figure_name, current_bbox, is_sub, include_extras
                )
                
                if not assessment:
                    print(f"    Assessment failed, using current bbox")
                    break
                
                quality_score = assessment.get("quality_score", 0)
                issues = assessment.get("issues", [])
                needs_refinement = assessment.get("needs_refinement", False)
                refined_bbox = assessment.get("refined_bbox")
                
                print(f"    Quality score: {quality_score}/10")
                caption_status = assessment.get("caption_status", "N/A")
                caption_text = assessment.get("caption_text_visible", "")
                if include_extras and not is_sub:
                    print(f"    Caption status: {caption_status}")
                    if caption_text:
                        # Truncate long caption text for display
                        display_text = caption_text[:100] + "..." if len(caption_text) > 100 else caption_text
                        print(f"    Visible caption: {display_text}")
                if issues:
                    print(f"    Issues:")
                    for issue in issues:  # Show all issues, no truncation
                        print(f"      - {issue}")
                
                # Check if quality meets threshold
                if quality_score >= quality_threshold:
                    print(f"    Quality meets threshold (>={quality_threshold})")
                    return (current_bbox, quality_score)
                
                # Need refinement
                if needs_refinement and refined_bbox:
                    # Calculate refinement delta
                    delta = max(
                        abs(refined_bbox[0] - current_bbox[0]),
                        abs(refined_bbox[1] - current_bbox[1]),
                        abs(refined_bbox[2] - current_bbox[2]),
                        abs(refined_bbox[3] - current_bbox[3])
                    )
                    
                    # If delta is too small (<5 units), consider converged
                    if delta < 5:
                        print(f"    Delta too small ({delta:.1f}<5), considered converged")
                        return (current_bbox, quality_score)
                    
                    print(f"    Refine bbox: {current_bbox} -> {refined_bbox} (delta: {delta:.1f})")
                    current_bbox = refined_bbox
                else:
                    print(f"    No refinement suggested, using current bbox")
                    return (current_bbox, quality_score)
                    
            finally:
                os.unlink(tmp_bbox_path)
        
        # Max rounds reached
        print(f"    Max rounds reached, using final bbox")
        return (current_bbox, quality_score)
        
    finally:
        os.unlink(tmp_path)


def search_figure_in_pdf(
    pdf_path: str,
    figure_name: str,
    dpi: int = 300,
    include_extras: bool = True,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    start_page: int = 0,
    max_pages: Optional[int] = None
) -> Optional[Tuple[int, List[float], Image.Image, int]]:
    """Search for a figure/table in PDF and return (page_num, bbox, image, quality_score)"""
    page_count = get_pdf_page_count(pdf_path)
    is_sub = is_subfigure(figure_name)
    
    if max_pages is None:
        max_pages = page_count
    
    end_page = min(start_page + max_pages, page_count)
    
    print(f"Searching for '{figure_name}' in PDF...")
    print(f"Search range: page {start_page + 1} to {end_page}")
    print(f"Mode: {'sub-figure' if is_sub else ('complete with extras' if include_extras else 'main content only')}")
    
    for page_num in range(start_page, end_page):
        print(f"  Checking page {page_num + 1}...")
        
        page_image = pdf_page_to_image(pdf_path, page_num, dpi)
        
        # Use multi-round assessment extraction
        result = extract_with_refinement(
            page_image, figure_name, is_sub, include_extras, max_rounds
        )
        
        if result:
            bbox, quality_score = result
            print(f"  Found '{figure_name}' on page {page_num + 1}")
            print(f"    Final bbox: {bbox}, quality: {quality_score}/10")
            return (page_num, bbox, page_image, quality_score)
    
    print(f"  Not found: '{figure_name}'")
    return None


# ============== Main Extraction Functions ==============

def extract_figure(
    pdf_path: str,
    figure_name: str,
    output_path: Optional[str] = None,
    dpi: int = 300,
    include_extras: bool = True,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    start_page: int = 0,
    max_pages: Optional[int] = None
) -> Optional[str]:
    """Extract a figure/table from PDF
    
    Args:
        pdf_path: Path to PDF file
        figure_name: Name of figure/table to extract
        output_path: Output image path
        dpi: Rendering resolution
        include_extras: Include extra elements (caption, legend, notes)
        max_rounds: Max quality assessment rounds
        start_page: Starting page number
        max_pages: Max pages to search
    
    Returns:
        Output file path, or None if failed
    """
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found: {pdf_path}")
        return None
    
    result = search_figure_in_pdf(
        pdf_path, figure_name, dpi, include_extras, max_rounds, start_page, max_pages
    )
    
    if result is None:
        print(f"Error: '{figure_name}' not found in PDF")
        return None
    
    page_num, bbox, page_image, quality_score = result
    
    # Crop image
    is_sub = is_subfigure(figure_name)
    padding = 0.005 if is_sub else 0.01
    cropped = crop_image_by_bbox(page_image, bbox, padding)
    
    # Generate output path
    if output_path is None:
        pdf_name = Path(pdf_path).stem
        safe_figure_name = re.sub(r'[^\w\-_]', '_', figure_name)
        output_dir = Path(pdf_path).parent / "extracted_figures"
        output_dir.mkdir(exist_ok=True)
        output_path = str(output_dir / f"{pdf_name}_{safe_figure_name}.png")
    else:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    cropped.save(output_path, "PNG", optimize=True)
    print(f"Saved to: {output_path}")
    print(f"  Image size: {cropped.size[0]} x {cropped.size[1]}")
    
    return output_path


def batch_extract_figures(
    pdf_path: str,
    figure_names: List[str],
    output_dir: Optional[str] = None,
    dpi: int = 300,
    include_extras: bool = True,
    max_rounds: int = DEFAULT_MAX_ROUNDS
) -> Dict[str, Optional[str]]:
    """Batch extract multiple figures/tables"""
    results = {}
    
    if output_dir is None:
        output_dir = str(Path(pdf_path).parent / "extracted_figures")
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    pdf_name = Path(pdf_path).stem
    
    for i, figure_name in enumerate(figure_names):
        print(f"\n[{i + 1}/{len(figure_names)}] Extracting '{figure_name}'...")
        
        safe_name = re.sub(r'[^\w\-_]', '_', figure_name)
        output_path = str(Path(output_dir) / f"{pdf_name}_{safe_name}.png")
        
        result = extract_figure(
            pdf_path, figure_name, output_path, dpi, include_extras, max_rounds
        )
        results[figure_name] = result
    
    # Summary
    print("\n" + "=" * 50)
    print("Extraction Summary:")
    success_count = sum(1 for v in results.values() if v is not None)
    print(f"  Success: {success_count}/{len(figure_names)}")
    
    if success_count < len(figure_names):
        print("  Failed:")
        for name, path in results.items():
            if path is None:
                print(f"    - {name}")
    
    return results


# ============== CLI Entry Point ==============

def main():
    parser = argparse.ArgumentParser(
        description="Extract figures/tables from PDF with multi-round quality assessment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python extract_figures.py paper.pdf "Figure 1"
  python extract_figures.py paper.pdf "Figure 1" --no-extras
  python extract_figures.py paper.pdf "Table 2" --output output/table2.png
  python extract_figures.py paper.pdf --batch "Figure 1,Figure 2,Table 1"
  python extract_figures.py paper.pdf --batch "Figure 1,Figure 2" --no-extras
        """
    )
    
    parser.add_argument("pdf_path", help="PDF file path")
    parser.add_argument("figure_name", nargs="?", help="Figure/table name, e.g., 'Figure 1' or 'Table 2'")
    parser.add_argument("--output", "-o", help="Output image path")
    parser.add_argument("--dpi", type=int, default=300, help="Rendering DPI (default: 300)")
    parser.add_argument("--batch", "-b", help="Batch extract, comma-separated figure names")
    parser.add_argument("--output-dir", "-d", help="Output directory for batch extraction")
    parser.add_argument(
        "--no-extras", 
        action="store_true",
        help="Exclude extra elements (caption, legend, notes), extract main content only"
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=DEFAULT_MAX_ROUNDS,
        help=f"Max quality assessment rounds (default: {DEFAULT_MAX_ROUNDS})"
    )
    
    args = parser.parse_args()
    
    include_extras = not args.no_extras
    
    if args.batch:
        figure_names = [name.strip() for name in args.batch.split(",")]
        batch_extract_figures(
            args.pdf_path, figure_names, args.output_dir, 
            args.dpi, include_extras, args.max_rounds
        )
    elif args.figure_name:
        extract_figure(
            args.pdf_path, args.figure_name, args.output, 
            args.dpi, include_extras, args.max_rounds
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
