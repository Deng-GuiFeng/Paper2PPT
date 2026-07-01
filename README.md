# paper-to-slides

把一篇学术论文 PDF 做成用于组会或文献汇报的 PPTX 幻灯片，并生成一份详细的中文论文总结。它是一个 Skill（技能），遵循开放的 Agent Skills 标准，可在众多支持该标准的 AI 助手中使用。

## 它能做什么

输入一篇论文 PDF，生成以下文件：

- `presentation.pptx`：幻灯片。正文为英文，中文讲稿写在每页的备注里，套用内置模板的排版与配色。默认精简为 2 页，需要时可要求更多，最多 5 页。
- `paper_summary.md`：详细的中文论文总结，帮你读懂全文、准备讲稿。
- `ppt_content.md`：幻灯片的结构化文字内容。
- `asset/` 里的图片：从 PDF 中裁出的图表。

其中图表由 AI 自己识别：脚本把 PDF 每一页渲染成图片，AI 看图定位并裁下每张图表，全程不依赖外部识别服务。

## 什么是 Skill

Skill（技能）是 Agent Skills 这一开放标准里的一个单元：它由 Anthropic 提出并开源，已被很多 AI 助手支持（名单见 [agentskills.io](https://agentskills.io)）。一个技能就是一个含 `SKILL.md` 的文件夹，`SKILL.md` 用自然语言写清这个技能做什么、怎么做。助手在需要时读取这些说明并照做，其间自行运行技能自带的脚本。同一个技能，在任意支持该标准的助手里都能用。

## 安装

先拿到技能本体，也就是 `paper-to-slides` 这一个文件夹：在本仓库网页上把整个仓库下载为 ZIP，解压后取出该文件夹；或用 `git clone` 克隆本仓库，在其中找到它。

再按你所用的助手把它装进去：

- **Claude（网页版或桌面版）**：先在 Settings 的 Capabilities 中开启 Code execution and file creation（Team、Enterprise 计划在 Organization settings 的 Skills 中开启），再到 Customize 的 Skills 里新建并上传技能。上传的 ZIP 内应是 `paper-to-slides` 文件夹本身，解开后为 `paper-to-slides/SKILL.md` 的结构，而不是整个仓库。
- **Claude Code**：把 `paper-to-slides` 文件夹放到 `~/.claude/skills/`（对所有项目生效），或项目内的 `.claude/skills/`（只对该项目生效）。
- **Codex**：把 `paper-to-slides` 文件夹放到 `~/.agents/skills/`，或仓库内的 `.agents/skills/`。
- **其他助手**：做法类似，具体位置见各自官方文档。

> 官方参考：[Claude Code Skills](https://code.claude.com/docs/en/skills)、[在 Claude 中使用 Skills](https://support.claude.com/en/articles/12512180-use-skills-in-claude)、[Codex Skills](https://developers.openai.com/codex/skills)。

## 使用

把论文 PDF 交给助手：用 Claude 时直接在对话里上传，用 Claude Code 或 Codex 时把它放到工作目录或给出文件路径。然后说明你的需求，例如：

> 用 paper-to-slides 把这篇论文做成组会汇报幻灯片。

助手会调用本技能，依次完成分析论文、生成内容、提取图表、套用模板生成幻灯片、逐页检查排版。产物统一放在一个工作目录里，即上面列出的几个文件。

## 版本演进：从 v1 到 v2

paper-to-slides 现在是 v2，由更早的 v1 重写而来。两代做同一件事，差别在于怎样在 PDF 里定位图表。

| 对比项 | v1 | v2（当前） |
|---|---|---|
| 怎么定位图表 | 调用外部的图像识别服务 | 由助手自己看渲染出的页面图来定位 |
| 使用前的准备 | 要申请该服务的密钥，并配置专门的运行环境 | 装好技能即可，无需密钥与专门环境 |
| 结构 | 拆成多个部件协作 | 合并为一个技能，可导入任意支持该标准的助手 |

这次重写的核心，是把定位图表从依赖外部付费服务，改成让助手自己看页面。正因如此，密钥和专门环境都不再需要，原本的多个部件也并成了一个技能。v1 的完整代码保留在 `v1.0.0` 标签，执行 `git checkout v1.0.0` 可以取回。

## 仓库结构

```
paper-to-slides/          技能本体
  SKILL.md                技能说明书，供助手读取执行
  references/             供助手参考的详细规则
  scripts/                技能调用的脚本
  assets/Template.pptx    幻灯片模板
PDFs/                     示例输入 PDF
output/                   示例输出，可看到成品的样子
```

## 许可

采用 [MIT 许可证](LICENSE)。
