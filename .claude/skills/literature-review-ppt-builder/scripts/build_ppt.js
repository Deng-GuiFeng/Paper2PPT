#!/usr/bin/env node
/**
 * Literature Review PPT Builder
 * 
 * 将 ppt_content.md 转换为 .pptx 演示文稿
 * 
 * Usage:
 *   node build_ppt.js <ppt_content.md> <figures_dir> <output.pptx>
 * 
 * Example:
 *   node build_ppt.js ppt_content.md ./figures/ output.pptx
 */

const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

// ============================================
// 配色方案
// ============================================
const COLORS = {
  primary: "1E3A5F",      // 深蓝 - 标题
  background: "FFFFFF",   // 白色背景
  titleBg: "1E3A5F",      // 标题页背景
  text: "333333",         // 正文
  secondary: "666666",    // 次要文字
  accent: "2E86AB",       // 强调色
  bullet1: "1E3A5F",      // 一级大纲颜色
  bullet2: "444444"       // 二级大纲颜色
};

// ============================================
// 解析 ppt_content.md
// ============================================
function parseMarkdown(content) {
  const lines = content.split("\n");
  const result = {
    title: "",
    source: "",
    slides: []
  };

  let currentSlide = null;
  let inNotes = false;
  let notesBuffer = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // 解析标题（第一个 # 开头）
    if (!result.title && trimmed.startsWith("# ")) {
      result.title = trimmed.replace(/^#\s*\[?/, "").replace(/\]?$/, "");
      continue;
    }

    // 解析来源（*...* 格式）
    if (!result.source && trimmed.startsWith("*") && trimmed.endsWith("*")) {
      result.source = trimmed.replace(/^\*\[?/, "").replace(/\]?\*$/, "");
      continue;
    }

    // 新幻灯片开始
    if (trimmed.startsWith("## Slide")) {
      if (currentSlide) {
        if (notesBuffer.length > 0) {
          currentSlide.notes = notesBuffer.join("\n").trim();
        }
        result.slides.push(currentSlide);
      }
      currentSlide = {
        bullets: [],
        figures: [],
        notes: ""
      };
      inNotes = false;
      notesBuffer = [];
      continue;
    }

    if (!currentSlide) continue;

    // 解析配图
    if (trimmed.startsWith("**配图**:") || trimmed.startsWith("**Figures**:")) {
      const figureStr = trimmed.replace(/^\*\*配图\*\*:\s*/, "").replace(/^\*\*Figures\*\*:\s*/, "");
      currentSlide.figures = figureStr.split(",").map(f => f.trim()).filter(f => f);
      continue;
    }

    // 解析讲稿
    if (trimmed.startsWith("**讲稿**:") || trimmed.startsWith("**Notes**:")) {
      inNotes = true;
      const noteStart = trimmed.replace(/^\*\*讲稿\*\*:\s*/, "").replace(/^\*\*Notes\*\*:\s*/, "");
      if (noteStart) notesBuffer.push(noteStart);
      continue;
    }

    // 收集讲稿内容
    if (inNotes && !trimmed.startsWith("---")) {
      notesBuffer.push(line);
      continue;
    }

    // 分隔符重置讲稿状态
    if (trimmed === "---") {
      inNotes = false;
      continue;
    }

    // 解析一级大纲 ▶
    if (trimmed.startsWith("▶")) {
      const text = trimmed.replace(/^▶\s*\*\*[\d.]+\s*/, "").replace(/\*\*$/, "").trim();
      currentSlide.bullets.push({ level: 1, text: text });
      continue;
    }

    // 解析二级大纲 ▢
    if (trimmed.startsWith("▢")) {
      const text = trimmed.replace(/^▢\s*[\d.]+\s*/, "").trim();
      currentSlide.bullets.push({ level: 2, text: text });
      continue;
    }

    // 解析三级内容（- 开头）
    if (trimmed.startsWith("- ") && currentSlide.bullets.length > 0) {
      const text = trimmed.replace(/^-\s*/, "");
      currentSlide.bullets.push({ level: 3, text: text });
      continue;
    }
  }

  // 添加最后一个幻灯片
  if (currentSlide) {
    if (notesBuffer.length > 0) {
      currentSlide.notes = notesBuffer.join("\n").trim();
    }
    result.slides.push(currentSlide);
  }

  return result;
}

// ============================================
// 查找图片文件
// ============================================
function findFigureFile(figuresDir, figureName) {
  // figureName 格式如 "Figure 1" 或 "Table 2"
  const normalized = figureName.toLowerCase().replace(/\s+/g, "_");
  const possibleNames = [
    normalized + ".jpg",
    normalized + ".jpeg", 
    normalized + ".png",
    normalized.replace("figure_", "fig_") + ".jpg",
    normalized.replace("figure_", "fig_") + ".png",
    normalized.replace("table_", "tab_") + ".jpg",
    normalized.replace("table_", "tab_") + ".png"
  ];

  for (const name of possibleNames) {
    const filePath = path.join(figuresDir, name);
    if (fs.existsSync(filePath)) {
      return filePath;
    }
  }

  // 尝试数字匹配
  const match = figureName.match(/(\d+)/);
  if (match) {
    const num = match[1];
    const patterns = [
      `fig${num}.jpg`, `fig${num}.png`,
      `figure${num}.jpg`, `figure${num}.png`,
      `fig_${num}.jpg`, `fig_${num}.png`,
      `fig-${num}.jpg`, `fig-${num}.png`
    ];
    for (const pattern of patterns) {
      const filePath = path.join(figuresDir, pattern);
      if (fs.existsSync(filePath)) {
        return filePath;
      }
    }
  }

  return null;
}

// ============================================
// 创建 PPT
// ============================================
function createPresentation(data, figuresDir, outputPath) {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = data.title;
  pres.author = "Literature Review";

  // ----------------------------------------
  // 标题页
  // ----------------------------------------
  const titleSlide = pres.addSlide();
  titleSlide.background = { color: COLORS.titleBg };

  // 论文标题
  titleSlide.addText(data.title, {
    x: 0.5, y: 1.8, w: 9, h: 1.8,
    fontSize: 32,
    fontFace: "Arial",
    color: "FFFFFF",
    bold: true,
    align: "center",
    valign: "middle",
    wrap: true
  });

  // 来源信息
  if (data.source) {
    titleSlide.addText(data.source, {
      x: 0.5, y: 4, w: 9, h: 0.5,
      fontSize: 18,
      fontFace: "Arial",
      color: "CCCCCC",
      italic: true,
      align: "center"
    });
  }

  // 底部装饰线
  titleSlide.addShape(pres.shapes.RECTANGLE, {
    x: 3, y: 4.8, w: 4, h: 0.05,
    fill: { color: COLORS.accent }
  });

  // ----------------------------------------
  // 内容页
  // ----------------------------------------
  data.slides.forEach((slideData, index) => {
    const slide = pres.addSlide();
    slide.background = { color: COLORS.background };

    // 查找配图
    let hasImage = false;
    let imagePath = null;
    if (slideData.figures.length > 0 && figuresDir) {
      imagePath = findFigureFile(figuresDir, slideData.figures[0]);
      hasImage = imagePath !== null;
    }

    // 内容区域宽度（有图片时缩小）
    const contentWidth = hasImage ? 5.2 : 9;
    const contentX = 0.5;

    // 页面标题（使用幻灯片序号）
    slide.addText(`Slide ${index + 1}`, {
      x: contentX, y: 0.25, w: contentWidth, h: 0.5,
      fontSize: 12,
      fontFace: "Arial",
      color: COLORS.secondary
    });

    // 顶部装饰线
    slide.addShape(pres.shapes.RECTANGLE, {
      x: contentX, y: 0.6, w: 1.5, h: 0.04,
      fill: { color: COLORS.accent }
    });

    // 大纲内容
    if (slideData.bullets.length > 0) {
      const bulletText = slideData.bullets.map((b, idx) => {
        let bulletChar = "";
        let indentLevel = 0;
        let fontSize = 14;
        let isBold = false;
        let color = COLORS.text;

        if (b.level === 1) {
          bulletChar = "25B6"; // ▶
          fontSize = 17;
          isBold = true;
          color = COLORS.bullet1;
        } else if (b.level === 2) {
          bulletChar = "25A2"; // ▢
          indentLevel = 1;
          fontSize = 14;
          color = COLORS.bullet2;
        } else {
          bulletChar = "2022"; // •
          indentLevel = 2;
          fontSize = 13;
          color = COLORS.secondary;
        }

        return {
          text: b.text,
          options: {
            bullet: { code: bulletChar },
            indentLevel: indentLevel,
            fontSize: fontSize,
            bold: isBold,
            color: color,
            breakLine: true,
            paraSpaceAfter: b.level === 1 ? 8 : 4
          }
        };
      });

      slide.addText(bulletText, {
        x: contentX,
        y: 0.8,
        w: contentWidth,
        h: 4.5,
        fontFace: "Arial",
        valign: "top"
      });
    }

    // 添加配图
    if (hasImage) {
      slide.addImage({
        path: imagePath,
        x: 5.9,
        y: 0.8,
        w: 3.8,
        h: 4,
        sizing: { type: "contain", w: 3.8, h: 4 }
      });

      // 图片标注
      slide.addText(slideData.figures.join(", "), {
        x: 5.9, y: 4.9, w: 3.8, h: 0.3,
        fontSize: 10,
        fontFace: "Arial",
        color: COLORS.secondary,
        italic: true,
        align: "center"
      });
    } else if (slideData.figures.length > 0) {
      // 没有找到图片时显示占位符
      slide.addShape(pres.shapes.RECTANGLE, {
        x: 5.9, y: 0.8, w: 3.8, h: 4,
        fill: { color: "F0F0F0" },
        line: { color: "CCCCCC", width: 1, dashType: "dash" }
      });
      slide.addText(`[${slideData.figures.join(", ")}]\n\n请手动插入图片`, {
        x: 5.9, y: 2, w: 3.8, h: 1.5,
        fontSize: 12,
        fontFace: "Arial",
        color: COLORS.secondary,
        align: "center",
        valign: "middle"
      });
    }

    // 添加讲稿（Speaker Notes）
    if (slideData.notes) {
      slide.addNotes(slideData.notes);
    }
  });

  // ----------------------------------------
  // 保存文件
  // ----------------------------------------
  pres.writeFile({ fileName: outputPath })
    .then(() => {
      console.log(`✅ PPT 生成成功: ${outputPath}`);
      console.log(`   - 总页数: ${data.slides.length + 1} (含标题页)`);
    })
    .catch(err => {
      console.error("❌ PPT 生成失败:", err);
      process.exit(1);
    });
}

// ============================================
// 主函数
// ============================================
function main() {
  const args = process.argv.slice(2);

  if (args.length < 2) {
    console.log("Usage: node build_ppt.js <ppt_content.md> <output.pptx> [figures_dir]");
    console.log("");
    console.log("Examples:");
    console.log("  node build_ppt.js ppt_content.md output.pptx");
    console.log("  node build_ppt.js ppt_content.md output.pptx ./figures/");
    process.exit(1);
  }

  const contentFile = args[0];
  const outputFile = args[1];
  const figuresDir = args[2] || null;

  // 检查输入文件
  if (!fs.existsSync(contentFile)) {
    console.error(`❌ 找不到内容文件: ${contentFile}`);
    process.exit(1);
  }

  // 检查图片目录
  if (figuresDir && !fs.existsSync(figuresDir)) {
    console.warn(`⚠️ 图片目录不存在: ${figuresDir}，将跳过图片插入`);
  }

  // 读取并解析内容
  console.log(`📖 读取内容文件: ${contentFile}`);
  const content = fs.readFileSync(contentFile, "utf-8");
  const data = parseMarkdown(content);

  console.log(`📊 解析结果:`);
  console.log(`   - 标题: ${data.title}`);
  console.log(`   - 来源: ${data.source}`);
  console.log(`   - 幻灯片数: ${data.slides.length}`);

  // 生成 PPT
  console.log(`🔨 生成 PPT...`);
  createPresentation(data, figuresDir, outputFile);
}

main();
