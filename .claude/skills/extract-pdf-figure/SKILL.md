---
name: extract-pdf-figure
description: Extract figures and tables from academic PDF papers with precise bounding box detection using Qwen3.5-plus vision model. Supports extracting complete figures (with title, legend, notes) or main content only. Can extract sub-figures like Figure 1(a). Use when user asks to extract, crop, or get figures/tables from PDF papers.
argument-hint: <pdf_path> <figure_name> [--no-extras]
allowed-tools: Bash(python *), Bash(conda *)
---

# PDF Figure & Table Extraction Skill

Extract figures and tables from academic PDF papers with pixel-perfect precision using the Qwen3.5-plus vision-language model. Features fast text-based page detection (O(n) scan) followed by AI-powered multi-round quality assessment, dramatically reducing API calls compared to brute-force page scanning.

## Quick Start

```bash
# Extract a complete figure (including title, legend, notes)
python .claude/skills/extract-pdf-figure/scripts/extract_figures.py "<pdf_path>" "<figure_name>"

# Extract main content only (no title, legend, notes)
python .claude/skills/extract-pdf-figure/scripts/extract_figures.py "<pdf_path>" "<figure_name>" --no-extras

# Batch extraction with output directory
python .claude/skills/extract-pdf-figure/scripts/extract_figures.py "<pdf_path>" --batch "Figure 1,Figure 2,Table 1" -d "output/asset/"
```

## Features

### 1. Extraction Modes

| Mode | Flag | Description |
|------|------|-------------|
| **Complete** | (default) | Includes figure number, caption, legend, notes, and main content |
| **Content Only** | `--no-extras` | Only the chart/diagram/table data, without surrounding text |

### 2. Multi-Round Quality Assessment

The tool uses an iterative refinement process:
1. **Round 1**: Initial figure detection and bounding box estimation
2. **Round 2+**: Quality assessment with visual feedback (red bounding box overlay)
3. **Refinement**: If quality score < 8/10, coordinates are automatically adjusted
4. **Termination**: Stops when quality is satisfactory or max rounds reached (default: 3)

### 3. Supported Figure Types

- `Figure 1`, `Figure 2`, etc.
- `Table 1`, `Table 2`, etc.
- `Fig. 1`, `Fig 1` (abbreviated)
- `Figure 1(a)`, `Figure 1 (a)`, `Figure 1a` (sub-figures)
- `Table 1(a)` (sub-tables)

## Usage Examples

### Single Figure Extraction

```bash
# Complete figure with all elements
python .claude/skills/extract-pdf-figure/scripts/extract_figures.py "PDFs/paper.pdf" "Figure 1"

# Only the chart content (no caption)
python .claude/skills/extract-pdf-figure/scripts/extract_figures.py "PDFs/paper.pdf" "Figure 1" --no-extras

# With custom output path
python .claude/skills/extract-pdf-figure/scripts/extract_figures.py "PDFs/paper.pdf" "Table 2" -o "output/asset/Table_2.png"

# Higher resolution
python .claude/skills/extract-pdf-figure/scripts/extract_figures.py "PDFs/paper.pdf" "Figure 3" --dpi 400
```

### Sub-Figure Extraction

```bash
# Extract only Figure 1(a) from a composite figure
python .claude/skills/extract-pdf-figure/scripts/extract_figures.py "PDFs/paper.pdf" "Figure 1(a)"

# Sub-figure with custom output
python .claude/skills/extract-pdf-figure/scripts/extract_figures.py "PDFs/paper.pdf" "Figure 2(b)" -o "output/asset/Figure_2b.png"
```

### Batch Extraction

```bash
# Extract multiple figures/tables at once
python .claude/skills/extract-pdf-figure/scripts/extract_figures.py "PDFs/paper.pdf" --batch "Figure 1,Figure 2,Figure 3,Table 1,Table 2" -d "output/asset/"

# Batch without extras
python .claude/skills/extract-pdf-figure/scripts/extract_figures.py "PDFs/paper.pdf" --batch "Figure 1,Figure 2" --no-extras -d "output/asset/"
```

## Command Line Options

| Option | Short | Description |
|--------|-------|-------------|
| `pdf_path` | | PDF file path (required) |
| `figure_name` | | Figure/Table name (required for single extraction) |
| `--output` | `-o` | Output image path |
| `--dpi` | | Rendering resolution (default: 300) |
| `--batch` | `-b` | Comma-separated figure names for batch extraction |
| `--output-dir` | `-d` | Output directory for batch extraction |
| `--no-extras` | | Exclude title, legend, notes (extract main content only) |
| `--max-rounds` | | Max quality refinement rounds (default: 3) |

## Output

- Format: PNG images
- Default location: `extracted_figures/` directory next to the PDF
- Naming: `<pdf_name>_<figure_name>.png`

## Dependencies

依赖已在项目 `requirements.txt` 中定义，安装方法请参考 `README.md`。

主要依赖：
- `PyMuPDF` - PDF 解析
- `Pillow` - 图像处理  
- `openai` - API 客户端
- `python-dotenv` - 环境变量加载

## How It Works

1. **Text-Based Page Detection (O(n))**: PyMuPDF scans all PDF pages once to locate candidate pages for each figure via text search — no API calls needed for this step.
2. **Targeted Rendering**: Only the candidate pages are rendered at high resolution (300 DPI default), skipping the rest.
3. **AI Detection**: Qwen3.5-plus model locates the target figure on the candidate page and returns bounding box coordinates.
4. **Quality Check**: The extraction is visually assessed with a red bounding box overlay; if needed, coordinates are refined iteratively.
5. **Precise Cropping**: The image is cropped with minimal padding to capture the exact figure.
6. **Output**: Saved as an optimized PNG file.

**Performance**: Single extraction — O(n) text scan + O(rounds) API calls. Batch extraction — O(n) text scan once + O(k×rounds) API calls, instead of the naïve O(n×k×rounds).

## Tips for Best Results

1. **Figure Names**: Use exact names as they appear in the paper (e.g., "Figure 1", not "fig 1")
2. **Composite Figures**: 
   - Use `"Figure 1"` to get all sub-figures with the main caption
   - Use `"Figure 1(a)"` to get only that specific sub-figure
3. **Tables**: Caption is typically above, so the tool searches upward
4. **Quality**: Use `--dpi 400` for very detailed figures
5. **Content Only**: Use `--no-extras` when you only need the visual data without surrounding text

## Additional Resources

- Script location: [scripts/extract_figures.py](scripts/extract_figures.py)
