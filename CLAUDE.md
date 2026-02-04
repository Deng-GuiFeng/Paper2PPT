# Paper2PPT

## 工作流程

依次使用技能 (Skills) "literature-review-ppt-generator", "extract-pdf-figure" 和 "literature-review-ppt-builder"。

## 环境

使用 Conda 环境 `paper2ppt`，运行任何 Python 脚本前需先激活。

## 输出目录结构

每次任务在 `output/` 下创建时间戳目录，格式 `YYYY-MM-DD_HHMMSS`：

```
output/2026-02-04_203225/
├── asset/              # 从 PDF 提取的图表
├── paper_summary.md    # 论文摘要（中文）
├── ppt_content.md      # PPT 结构化内容
└── presentation.pptx   # 最终生成的 PPT
```

## 图表命名规则

`ppt_content.md` 中的图表引用与提取后的文件名对应关系：

| ppt_content.md 中的引用 | 提取后的文件名 | 说明 |
|------------------------|---------------|------|
| `Figure 1` | `Figure_1.png` | 完整提取（含标题、图例） |
| `Figure 1 [content-only]` | `Figure_1.png` | 仅主体内容，提取时加 `--no-extras` |
| `Figure 1(a)` | `Figure_1(a).png` | 子图 |
| `Table 2` | `Table_2.png` | 表格 |
