# Paper2PPT

> 请使用中文与我交流。

## 工作流程

### 推荐：使用 Subagent（一键运行完整流水线）

当用户要求"读论文生成PPT"时，使用 **`paper2ppt` subagent**（位于 `.claude/agents/paper2ppt.md`），它自动执行完整三阶段流水线。

### 分步：逐一使用 Skills

依次使用技能 (Skills) "literature-review-ppt-generator", "extract-pdf-figure" 和 "literature-review-ppt-builder"。

## 环境

使用 Conda 环境 `paper2ppt`，运行任何 Python 脚本前需先激活：

```bash
conda run -n paper2ppt python <script> [args]
```

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

## 提取性能说明（extract-pdf-figure v3.0）

脚本采用两阶段优化：
1. **文本扫描（O(n)）**：PyMuPDF 一次性扫描所有页面，定位各图表的候选页码，无需 API 调用。
2. **AI 提取（O(k×rounds)）**：仅对候选页调用 Qwen3.5-plus 视觉模型，批量提取时只扫描一次，大幅减少 API 调用。
