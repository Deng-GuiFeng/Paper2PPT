---
name: paper-to-slides
description: 将学术论文 PDF 转换为组会/文献汇报幻灯片（.pptx），并生成配套的中文论文总结。
---

# paper-to-slides

把一篇学术论文 PDF 做成组会汇报 PPTX（英文幻灯片 + 中文讲稿），并附一份详尽的中文论文总结。

脚本依赖 PyMuPDF、Pillow、python-pptx。脚本与模板在 `$SKILL`（本 SKILL.md 所在目录）下，命令里以 `$SKILL/scripts/…`、`$SKILL/assets/Template.pptx` 引用；本次所有产物放进一个工作目录 `$outdir`。

## 页数（硬规则）

默认严格 2 页：论文内容再多，也压缩进 2 页、不擅自加页。只有用户明确要求"详细些/多页/N 页"时，才用 2-5 页（上限 5）。

## 分析论文，生成内容

产出两份文件到 `$outdir`：`paper_summary.md`（详尽中文总结，≥5000 字，供读稿）与 `ppt_content.md`（幻灯片内容）。`ppt_content.md` 的格式规则——大纲符号、每页篇幅预算、图表引用写法、逻辑流程——全部见 [`references/ppt_content_format.md`](references/ppt_content_format.md)，严格遵循。图表引用名要与论文原文一致，提取时靠它在 PDF 里定位。

## 提取图表

对 `ppt_content.md` 里 `**配图**:` 的每个图表：渲染候选页 → 读网格坐标 → 裁剪 → 对照校验图精修。模式规则、质检与完整示例见 [`references/figure_extraction.md`](references/figure_extraction.md)。

```bash
# 渲染候选页：得到干净图，和一张叠了 0-1000 网格的图（用于读 bbox）
python $SKILL/scripts/locate_figure.py "<pdf>" "<figure_name>" -d "$outdir/pages" --dpi 200
# 裁剪；子图加 --sub。会附带生成 *_check.png（把所选 bbox 画在整页上）
python $SKILL/scripts/crop_figure.py "$outdir/pages/_<name>_p<N>.png" --bbox x1,y1,x2,y2 -o "$outdir/asset/<name>.png"
```

两处必须靠看图把关、不能只凭坐标：① 文本扫描会命中正文里的图表引用，命中的页常常并不含图本身，要逐候选页确认真正画着图的那页；② 裁剪图看着"完整"也可能切了标题或带进邻近内容，`*_check.png` 能一眼暴露，据此调 bbox 重裁。输出文件名把图表名的空格转下划线、括号保留（`Figure 1(a)` → `Figure_1(a).png`），存入 `$outdir/asset/`，构建时靠它匹配。

## 构建

```bash
PYTHONIOENCODING=utf-8 python $SKILL/scripts/build_ppt.py \
    "$outdir/ppt_content.md" "$outdir/asset/" "$SKILL/assets/Template.pptx" "$outdir/presentation.pptx"
```

构建器按 `## Slide N` 段落数生成对应页数（首页用标题版式，其余用模板空白页），套用模板的字体与配色，正文按默认分栏摆放。这只是排版的起点，好坏由下一步把关。

## 排版精修（必做循环）
 
默认分栏未必好看。构建后**必须**把成品渲染成逐页图片查看，不满意就调整后重渲，循环到排版满意为止。调整手段不限于改 `ppt_content.md`——`build_ppt.py` 的摆放逻辑（分栏比例、图片尺寸与位置）也是可改的默认参考，可按需改它来消除留白或失衡。
 
看图时除了排版，还要核这几处 Markdown 起草 + 模板渲染容易留下的毛病，见到即修，修法你自己判断：
- 文字溢出页面
- 图表裁剪不准
- 大纲层级缩进错乱
- 漏出 `*` / `` ` `` / `·` / `—` 等不适合 PPTX 展示的符号
- 数学符号没在 PPTX 正确处理和渲染
边界：忠于论文、不超出既定页数；`$SKILL/assets/Template.pptx` 是固定视觉外框（页眉两个 logo、"Contents" 标题栏、配色），只套用、绝不修改或绕过——排版只在模板正文区内调整，logo 与标题栏原样保留。

## 交付

交付 `presentation.pptx` 与 `paper_summary.md`；若有图表没能提取出来，注明并建议用户手动替换。
