# Paper2PPT 📄➡️📊

将学术论文 PDF 自动转换为组会汇报 PPT（2-3页），适合 5 分钟快速分享。

## 前置要求

- [Claude Code](https://claude.ai/code)
- [Conda](https://docs.conda.io/en/latest/miniconda.html)
- [阿里云 DashScope API Key](https://dashscope.console.aliyun.com/)（用于 Qwen3.5-plus 视觉模型）

## 安装

```bash
# 克隆
git clone https://github.com/yourusername/paper2ppt.git
cd paper2ppt

# 创建 Conda 环境
conda create -n paper2ppt python=3.10 -y
conda activate paper2ppt
pip install -r requirements.txt

# 配置 API Key
cp .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY
```

## 使用

在 Claude Code 中打开项目，输入：

```
阅读论文 "PDFs/DeepSeek-OCR 2 Visual Causal Flow.pdf" 并生成组会汇报 PPTX 文档
```

Claude Code 将自动调用 `paper2ppt` subagent 完成完整流水线。

输出位于 `output/YYYY-MM-DD_HHMMSS/`：
- `paper_summary.md` - 论文摘要（中文，详细）
- `ppt_content.md` - PPT 结构内容（全英文幻灯片 + 中文讲稿）
- `asset/*.png` - 提取的图表
- `presentation.pptx` - **最终 PPT**

## 项目结构

```
paper2ppt/
├── .claude/
│   ├── agents/
│   │   └── paper2ppt.md              # 完整流水线 Subagent
│   └── skills/
│       ├── literature-review-ppt-generator/  # PPT 内容生成
│       ├── extract-pdf-figure/               # 图表提取 (Qwen3.5-plus)
│       └── literature-review-ppt-builder/    # PPTX 构建
├── PDFs/                     # 输入 PDF
├── output/                   # 输出目录
├── .env.example              # 环境变量模板
└── requirements.txt
```

## 架构

```
PDF 论文
    │
    ▼
[literature-review-ppt-generator]  ──→  paper_summary.md
    │                                   ppt_content.md
    ▼
[extract-pdf-figure]               ──→  asset/Figure_1.png
  (Qwen3.5-plus vision model)           asset/Table_1.png
  (O(n) 文本扫描 + 按需 AI 提取)
    │
    ▼
[literature-review-ppt-builder]    ──→  presentation.pptx
```

## License

MIT
