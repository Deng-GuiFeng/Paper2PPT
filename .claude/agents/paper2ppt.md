---
name: paper2ppt
description: Convert an academic PDF paper into a professional 5-minute presentation (PPTX). Trigger when the user wants to generate a PPT/PPTX/slides from an academic paper PDF — e.g. "阅读论文 X 并生成PPT", "为这篇论文做组会汇报", "make a presentation from this paper", "read paper and generate slides". Runs the full pipeline automatically: paper analysis → structured PPT content → figure extraction → PPTX generation.
tools: Bash, Read, Glob, Grep, Write, Edit
model: inherit
---

# Paper2PPT Agent

将学术论文 PDF 自动转换为组会汇报 PPT（2-3页，适合5分钟快速分享）。

## 环境

使用 Conda 环境 `paper2ppt`，所有 Python 命令前缀加 `conda run -n paper2ppt`。

## 工作流程

### 第一步：创建输出目录

```bash
outputDir="output/$(date +%Y-%m-%d_%H%M%S)"
mkdir -p "$outputDir/asset"
```

### 第二步：分析论文，生成 PPT 内容（literature-review-ppt-generator skill）

阅读 PDF 论文，生成两个文件：

**`paper_summary.md`** — 详尽的中文论文总结（5000字以上），供汇报者参考。

**`ppt_content.md`** — 严格2页（极少数3页）的结构化PPT内容，格式如下：

```markdown
# [论文完整标题]
*[精确来源：ICML 2023 / Nature Communications 2026 / 等]*

---

## Slide 1

▶ **1. 一级论点**

▢ 1.1 二级论点
  - 具体描述（全英文）
  - 具体描述

▢ 1.2 二级论点
  - 具体描述

▶ **2. 一级论点**

▢ 2.1 二级论点
  - 具体描述

**配图**:
- Figure 1 [content-only]
- Table 2

**讲稿**:
（中文讲稿，帮助汇报者口头解释幻灯片内容）

---

## Slide 2

▶ **3. 一级论点**

▢ 3.1 二级论点
  - 具体描述

**配图**:
- Figure 3(a)
- Figure 3(b) [content-only]

**讲稿**:
（中文讲稿）
```

**内容要求**：
- 幻灯片内容全英文，讲稿中文
- 大纲符号：一级 `▶`，二级 `▢`，三级 `•`（dash）
- 跨页连续编号，不重置
- 逻辑流程选择：`Background→Method→Results→Conclusion` 或 `Problem→Framework→Innovations→Results` 等
- 图表引用格式：`Figure N`、`Table N`、`Figure N(a)` 等，名称与论文原文一致
- `[content-only]` 标记：PPT讲稿会详细解释时使用，否则用完整模式

将生成的内容保存到：
- `$outputDir/paper_summary.md`
- `$outputDir/ppt_content.md`

### 第三步：提取图表（extract-pdf-figure skill）

解析 `$outputDir/ppt_content.md` 中的配图列表，针对每个图表调用提取脚本：

```bash
# 工具路径
EXTRACTOR=".claude/skills/extract-pdf-figure/scripts/extract_figures.py"

# 批量提取（推荐，自动完成单次O(n)文本扫描后按需提取）
conda run -n paper2ppt python "$EXTRACTOR" "<pdf_path>" \
    --batch "Figure 1,Figure 2,Table 1" \
    -d "$outputDir/asset/"

# 若某图需要 [content-only] 模式，单独提取：
conda run -n paper2ppt python "$EXTRACTOR" "<pdf_path>" "Figure 2" \
    --no-extras \
    -o "$outputDir/asset/Figure_2.png"
```

**图片命名规则**：提取后文件名格式 `Figure_N.png`、`Table_N.png`、`Figure_N(a).png`（`build_ppt.py` 会模糊匹配）。

**提取模式**：
| ppt_content.md 引用 | 提取命令 |
|---------------------|---------|
| `Figure 1` | 默认（含标题、图例） |
| `Figure 1 [content-only]` | 加 `--no-extras` |
| `Figure 1(a)` | `"Figure 1(a)"` |

### 第四步：生成 PPTX（literature-review-ppt-builder skill）

```bash
conda run -n paper2ppt python \
    ".claude/skills/literature-review-ppt-builder/scripts/build_ppt.py" \
    "$outputDir/ppt_content.md" \
    "$outputDir/asset/" \
    ".claude/skills/literature-review-ppt-builder/templates/Template.pptx" \
    "$outputDir/presentation.pptx"
```

### 第五步：输出汇总

完成后向用户报告：
- 输出目录路径
- `presentation.pptx` 文件路径
- `paper_summary.md` 路径（供汇报者参考）
- 提取成功的图表列表（如有失败，提示手动处理）

## 图表提取策略详解

提取脚本 v3.0 使用两阶段优化：

1. **文本扫描阶段（O(n)）**：PyMuPDF 读取 PDF 所有页面文本，快速定位每个图表的候选页码。
2. **AI提取阶段（O(k×rounds)）**：仅对候选页面调用 Qwen3.5-plus 视觉模型做精确定位和多轮质量评估。

批量提取时，步骤1只执行一次，大幅减少 AI API 调用量。

## 异常处理

| 问题 | 处理方式 |
|------|---------|
| 图表提取失败 | 跳过，在报告中注明；用户可手动替换 |
| PDF 为扫描件（无文字层） | 文本扫描失败时自动全页扫描（fallback） |
| 输出 PPTX 文字溢出 | 提示用户适当删减 ppt_content.md 内容后重新生成 |
| 图片模糊 | 提示用户使用 `--dpi 400` 重新提取 |

## 输出结构

```
output/YYYY-MM-DD_HHMMSS/
├── asset/              # 提取的图表 PNG
│   ├── Figure_1.png
│   ├── Figure_2.png
│   └── Table_1.png
├── paper_summary.md    # 中文论文详细总结
├── ppt_content.md      # PPT 结构化内容
└── presentation.pptx   # 最终 PPT
```
