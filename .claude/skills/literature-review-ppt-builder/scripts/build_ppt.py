#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Literature Review PPT Builder

将 ppt_content.md 转换为 .pptx 演示文稿，使用指定模板。

Usage:
    python build_ppt.py <ppt_content.md> <figures_dir> <template.pptx> <output.pptx>

Example:
    python build_ppt.py output/ppt_content.md output/ Template.pptx output/presentation.pptx
"""

import os
import re
import sys
import copy
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.dml.color import RGBColor
from PIL import Image


# ============================================
# 配置常量
# ============================================

# 幻灯片尺寸 (16:9 标准)
SLIDE_WIDTH_INCH = 13.333  # 标准 16:9 宽度
SLIDE_HEIGHT_INCH = 7.5    # 标准 16:9 高度

# 布局配置
LAYOUT_CONFIG = {
    # 第一页（含标题）：从 3/10 开始
    "first_slide": {
        "content_start_ratio": 0.30,  # 3/10
    },
    # 后续页：从 1/5 开始
    "normal_slide": {
        "content_start_ratio": 0.20,  # 1/5
    },
    # 左右分割：3:2
    "left_ratio": 0.60,   # 左侧文字区域占 60%
    "right_ratio": 0.40,  # 右侧图片区域占 40%
    # 边距
    "margin_left": 0.04,   # 左边距 4%
    "margin_right": 0.04,  # 右边距 4%
    "gap": 0.02,           # 文字和图片之间间隙 2%
}

# 字体配置
FONT_CONFIG = {
    "family": "Times New Roman",
    "title_size": Pt(16),      # 论文标题
    "heading1_size": Pt(14),   # 一级大纲
    "heading2_size": Pt(14),   # 二级大纲
    "body_size": Pt(12),       # 其他内容
    "source_size": Pt(12),     # 来源信息
}

# 颜色配置
COLORS = {
    "title": RGBColor(0x1E, 0x3A, 0x5F),      # 深蓝
    "heading1": RGBColor(0x1E, 0x3A, 0x5F),   # 深蓝
    "heading2": RGBColor(0x33, 0x33, 0x33),   # 深灰
    "body": RGBColor(0x44, 0x44, 0x44),       # 灰色
    "source": RGBColor(0x66, 0x66, 0x66),     # 浅灰
}


# ============================================
# 数据结构
# ============================================

@dataclass
class BulletItem:
    """大纲项"""
    level: int  # 1=一级, 2=二级, 3=三级
    text: str
    is_bold: bool = False


@dataclass
class SlideContent:
    """幻灯片内容"""
    bullets: List[BulletItem] = field(default_factory=list)
    figures: List[str] = field(default_factory=list)  # 图片名称列表
    figure_modes: List[bool] = field(default_factory=list)  # True=content-only
    notes: str = ""


@dataclass
class PresentationData:
    """演示文稿数据"""
    title: str = ""
    source: str = ""
    slides: List[SlideContent] = field(default_factory=list)


# ============================================
# 解析 ppt_content.md
# ============================================

def parse_markdown(content: str) -> PresentationData:
    """解析 ppt_content.md 文件"""
    lines = content.split("\n")
    result = PresentationData()
    
    current_slide: Optional[SlideContent] = None
    in_notes = False
    notes_buffer = []
    in_figures = False
    
    for line in lines:
        trimmed = line.strip()
        
        # 解析标题（第一个 # 开头）
        if not result.title and trimmed.startswith("# "):
            result.title = trimmed[2:].strip()
            continue
        
        # 解析来源（*...* 格式）
        if not result.source and trimmed.startswith("*") and trimmed.endswith("*"):
            result.source = trimmed[1:-1].strip()
            continue
        
        # 新幻灯片开始
        if trimmed.startswith("## Slide"):
            if current_slide:
                if notes_buffer:
                    current_slide.notes = "\n".join(notes_buffer).strip()
                result.slides.append(current_slide)
            current_slide = SlideContent()
            in_notes = False
            in_figures = False
            notes_buffer = []
            continue
        
        if not current_slide:
            continue
        
        # 解析配图（多行格式）
        if trimmed.startswith("**配图**:") or trimmed.startswith("**Figures**:"):
            in_figures = True
            in_notes = False
            # 检查同一行是否有内容
            rest = trimmed.split(":", 1)[1].strip() if ":" in trimmed else ""
            if rest and not rest.startswith("-"):
                # 旧格式：单行逗号分隔
                parse_figure_line(rest, current_slide)
                in_figures = False
            continue
        
        # 解析配图列表项
        if in_figures and trimmed.startswith("- "):
            fig_text = trimmed[2:].strip()
            # 移除注释
            if "#" in fig_text:
                fig_text = fig_text.split("#")[0].strip()
            parse_figure_line(fig_text, current_slide)
            continue
        
        # 配图区域结束
        if in_figures and trimmed and not trimmed.startswith("-"):
            in_figures = False
        
        # 解析讲稿
        if trimmed.startswith("**讲稿**:") or trimmed.startswith("**Notes**:"):
            in_notes = True
            in_figures = False
            rest = trimmed.split(":", 1)[1].strip() if ":" in trimmed else ""
            if rest:
                notes_buffer.append(rest)
            continue
        
        # 收集讲稿内容
        if in_notes and not trimmed.startswith("---"):
            notes_buffer.append(line)
            continue
        
        # 分隔符
        if trimmed == "---":
            in_notes = False
            in_figures = False
            continue
        
        # 解析一级大纲 ▶
        if trimmed.startswith("▶"):
            in_figures = False
            # 提取文本，移除 **数字. 和结尾的 **
            text = re.sub(r"^▶\s*\*\*[\d.]+\s*", "", trimmed)
            text = re.sub(r"\*\*$", "", text).strip()
            current_slide.bullets.append(BulletItem(level=1, text=text, is_bold=True))
            continue
        
        # 解析二级大纲 ▢
        if trimmed.startswith("▢"):
            in_figures = False
            text = re.sub(r"^▢\s*[\d.]+\s*", "", trimmed).strip()
            current_slide.bullets.append(BulletItem(level=2, text=text))
            continue
        
        # 解析三级内容（- 开头，但不在配图区域）
        if trimmed.startswith("- ") and not in_figures and current_slide.bullets:
            text = trimmed[2:].strip()
            current_slide.bullets.append(BulletItem(level=3, text=text))
            continue
    
    # 添加最后一个幻灯片
    if current_slide:
        if notes_buffer:
            current_slide.notes = "\n".join(notes_buffer).strip()
        result.slides.append(current_slide)
    
    return result


def parse_figure_line(text: str, slide: SlideContent):
    """解析单个图片引用"""
    # 处理逗号分隔的多个图片
    parts = [p.strip() for p in text.split(",")]
    for part in parts:
        if not part:
            continue
        # 检查是否有 [content-only] 标记
        content_only = "[content-only]" in part.lower()
        # 提取图片名称
        fig_name = re.sub(r"\s*\[content-only\]", "", part, flags=re.IGNORECASE).strip()
        if fig_name:
            slide.figures.append(fig_name)
            slide.figure_modes.append(content_only)


# ============================================
# 图片处理
# ============================================

def find_figure_file(figures_dir: str, figure_name: str) -> Optional[str]:
    """查找图片文件
    
    支持多种命名格式以兼容 extract-pdf-figure 的输出：
    - Figure_1.png (空格转下划线)
    - <pdf_name>_Figure_1.png (带 PDF 名称前缀)
    - figure_1.png (小写)
    """
    if not figures_dir or not os.path.isdir(figures_dir):
        return None
    
    # 标准化名称: "Figure 1" -> "Figure_1", "Figure 1(a)" -> "Figure_1(a)"
    normalized = figure_name.replace(" ", "_")
    
    # 构建所有可能的文件名模式
    possible_names = [
        # 直接匹配
        normalized + ".png",
        normalized + ".jpg",
        normalized + ".jpeg",
        # 小写
        normalized.lower() + ".png",
        normalized.lower() + ".jpg",
        # 无括号版本 Figure_1a
        normalized.replace("(", "").replace(")", "") + ".png",
    ]
    
    # 先尝试精确匹配
    for name in possible_names:
        filepath = os.path.join(figures_dir, name)
        if os.path.exists(filepath):
            return filepath
    
    # 如果精确匹配失败，搜索目录中包含图片名称的文件
    # 这样可以匹配 "<pdf_name>_Figure_1.png" 格式
    try:
        for filename in os.listdir(figures_dir):
            filename_lower = filename.lower()
            normalized_lower = normalized.lower()
            
            # 检查文件名是否包含图片名称
            if normalized_lower in filename_lower:
                ext = os.path.splitext(filename)[1].lower()
                if ext in ['.png', '.jpg', '.jpeg']:
                    return os.path.join(figures_dir, filename)
            
            # 检查无空格版本
            normalized_no_space = normalized_lower.replace("_", "")
            filename_no_sep = filename_lower.replace("_", "").replace("-", "")
            if normalized_no_space in filename_no_sep:
                ext = os.path.splitext(filename)[1].lower()
                if ext in ['.png', '.jpg', '.jpeg']:
                    return os.path.join(figures_dir, filename)
    except:
        pass
    
    return None


def get_image_size(image_path: str) -> Tuple[int, int]:
    """获取图片尺寸 (width, height)"""
    with Image.open(image_path) as img:
        return img.size


def calculate_image_layout(
    images: List[Tuple[str, int, int]],  # [(path, width, height), ...]
    area_width: float,   # 可用区域宽度 (inches)
    area_height: float,  # 可用区域高度 (inches)
) -> List[Tuple[str, float, float, float, float]]:
    """
    计算多张图片的布局
    
    Returns:
        [(path, x, y, w, h), ...] 相对于区域左上角的位置和尺寸 (inches)
    """
    if not images:
        return []
    
    n = len(images)
    gap = 0.1  # 图片间隙 (inches)
    
    if n == 1:
        # 单张图片：居中显示
        path, img_w, img_h = images[0]
        ratio = img_w / img_h
        
        # 计算最佳尺寸
        if ratio > area_width / area_height:
            # 宽图：以宽度为准
            w = area_width
            h = w / ratio
        else:
            # 高图：以高度为准
            h = area_height
            w = h * ratio
        
        x = (area_width - w) / 2
        y = (area_height - h) / 2
        return [(path, x, y, w, h)]
    
    elif n == 2:
        # 两张图片：根据宽高比决定横排还是竖排
        path1, w1, h1 = images[0]
        path2, w2, h2 = images[1]
        ratio1 = w1 / h1
        ratio2 = w2 / h2
        avg_ratio = (ratio1 + ratio2) / 2
        
        if avg_ratio > 1.2:
            # 偏宽的图：竖排（上下）
            cell_h = (area_height - gap) / 2
            results = []
            for i, (path, img_w, img_h) in enumerate(images):
                ratio = img_w / img_h
                if ratio > area_width / cell_h:
                    w = area_width
                    h = w / ratio
                else:
                    h = cell_h
                    w = h * ratio
                x = (area_width - w) / 2
                y = i * (cell_h + gap) + (cell_h - h) / 2
                results.append((path, x, y, w, h))
            return results
        else:
            # 偏高的图：横排（左右）
            cell_w = (area_width - gap) / 2
            results = []
            for i, (path, img_w, img_h) in enumerate(images):
                ratio = img_w / img_h
                if ratio > cell_w / area_height:
                    w = cell_w
                    h = w / ratio
                else:
                    h = area_height
                    w = h * ratio
                x = i * (cell_w + gap) + (cell_w - w) / 2
                y = (area_height - h) / 2
                results.append((path, x, y, w, h))
            return results
    
    else:
        # 3-4张图片：2x2 网格
        cols = 2
        rows = (n + 1) // 2
        cell_w = (area_width - gap * (cols - 1)) / cols
        cell_h = (area_height - gap * (rows - 1)) / rows
        
        results = []
        for i, (path, img_w, img_h) in enumerate(images):
            row = i // cols
            col = i % cols
            ratio = img_w / img_h
            
            if ratio > cell_w / cell_h:
                w = cell_w
                h = w / ratio
            else:
                h = cell_h
                w = h * ratio
            
            x = col * (cell_w + gap) + (cell_w - w) / 2
            y = row * (cell_h + gap) + (cell_h - h) / 2
            results.append((path, x, y, w, h))
        
        return results


# ============================================
# Markdown 文本格式处理
# ============================================

def add_formatted_text(paragraph, text: str, base_font_name: str, base_font_size, 
                       base_color, base_bold: bool = False):
    """
    解析并添加带格式的文本到段落
    支持 **粗体** 格式
    """
    # 匹配 **text** 模式
    pattern = r'\*\*(.+?)\*\*'
    last_end = 0
    
    for match in re.finditer(pattern, text):
        # 添加匹配前的普通文本
        if match.start() > last_end:
            normal_text = text[last_end:match.start()]
            if normal_text:
                run = paragraph.add_run()
                run.text = normal_text
                run.font.name = base_font_name
                run.font.size = base_font_size
                run.font.bold = base_bold
                run.font.color.rgb = base_color
        
        # 添加粗体文本
        bold_text = match.group(1)
        run = paragraph.add_run()
        run.text = bold_text
        run.font.name = base_font_name
        run.font.size = base_font_size
        run.font.bold = True  # 强制粗体
        run.font.color.rgb = base_color
        
        last_end = match.end()
    
    # 添加剩余的普通文本
    if last_end < len(text):
        remaining = text[last_end:]
        if remaining:
            run = paragraph.add_run()
            run.text = remaining
            run.font.name = base_font_name
            run.font.size = base_font_size
            run.font.bold = base_bold
            run.font.color.rgb = base_color


# ============================================
# 幻灯片复制工具
# ============================================

def duplicate_slide(prs, template_slide):
    """
    复制模板幻灯片（保留所有背景和元素）
    
    Args:
        prs: Presentation 对象
        template_slide: 要复制的模板幻灯片
    
    Returns:
        新复制的幻灯片
    """
    from copy import deepcopy
    from pptx.util import Inches
    import copy
    
    # 使用模板幻灯片的布局创建新幻灯片
    slide_layout = template_slide.slide_layout
    new_slide = prs.slides.add_slide(slide_layout)
    
    # 复制模板幻灯片的所有形状
    for shape in template_slide.shapes:
        # 跳过占位符（它们已经通过布局继承了）
        if shape.is_placeholder:
            continue
            
        # 复制图片
        if shape.shape_type == 13:  # MSO_SHAPE_TYPE.PICTURE
            try:
                # 获取图片数据
                image_blob = shape.image.blob
                image_content_type = shape.image.content_type
                
                # 添加图片到新幻灯片
                from io import BytesIO
                image_stream = BytesIO(image_blob)
                new_slide.shapes.add_picture(
                    image_stream,
                    shape.left,
                    shape.top,
                    shape.width,
                    shape.height
                )
            except Exception as e:
                print(f"  警告: 复制图片失败: {e}")
        
        # 复制直线和连接器
        elif shape.shape_type in (9, 21):  # LINE=9, STRAIGHT_CONNECTOR=21
            try:
                # 获取直线的起点和终点坐标
                connector = new_slide.shapes.add_connector(
                    1,  # MSO_CONNECTOR.STRAIGHT
                    shape.begin_x, shape.begin_y,
                    shape.end_x, shape.end_y
                )
                # 复制线条样式
                if shape.line.color.type is not None:
                    try:
                        connector.line.color.rgb = shape.line.color.rgb
                    except:
                        pass
                if shape.line.width:
                    connector.line.width = shape.line.width
            except Exception as e:
                # 如果连接器方式失败，尝试用自选形状方式
                try:
                    from pptx.enum.shapes import MSO_SHAPE
                    # 计算线条的位置和尺寸
                    left = min(shape.left, shape.left + shape.width)
                    top = min(shape.top, shape.top + shape.height)
                    width = abs(shape.width) if shape.width else shape.left
                    height = abs(shape.height) if shape.height else 1
                    
                    # 添加一个矩形作为替代线条
                    line_shape = new_slide.shapes.add_shape(
                        MSO_SHAPE.RECTANGLE,
                        shape.left, shape.top,
                        shape.width, shape.height
                    )
                    # 设置为无填充、有边框
                    line_shape.fill.background()
                    if shape.line.width:
                        line_shape.line.width = shape.line.width
                except Exception as e2:
                    print(f"  警告: 复制直线失败: {e}, {e2}")
        
        # 复制自选形状（矩形、圆形等）
        elif shape.shape_type == 1:  # MSO_SHAPE_TYPE.AUTO_SHAPE
            try:
                from pptx.enum.shapes import MSO_SHAPE
                new_shape = new_slide.shapes.add_shape(
                    shape.auto_shape_type,
                    shape.left, shape.top,
                    shape.width, shape.height
                )
                # 复制填充
                if shape.fill.type is not None:
                    try:
                        if shape.fill.type == 1:  # SOLID
                            new_shape.fill.solid()
                            new_shape.fill.fore_color.rgb = shape.fill.fore_color.rgb
                        elif shape.fill.type == 0:  # BACKGROUND
                            new_shape.fill.background()
                    except:
                        pass
                # 复制线条
                try:
                    if shape.line.color.type is not None:
                        new_shape.line.color.rgb = shape.line.color.rgb
                    if shape.line.width:
                        new_shape.line.width = shape.line.width
                except:
                    pass
            except Exception as e:
                print(f"  警告: 复制形状失败: {e}")
        
        # 复制文本框
        elif shape.has_text_frame:
            try:
                new_shape = new_slide.shapes.add_textbox(
                    shape.left, shape.top,
                    shape.width, shape.height
                )
                # 复制文本内容
                new_tf = new_shape.text_frame
                for para_idx, para in enumerate(shape.text_frame.paragraphs):
                    if para_idx == 0:
                        new_para = new_tf.paragraphs[0]
                    else:
                        new_para = new_tf.add_paragraph()
                    
                    new_para.alignment = para.alignment
                    new_para.level = para.level
                    
                    for run in para.runs:
                        new_run = new_para.add_run()
                        new_run.text = run.text
                        if run.font.name:
                            new_run.font.name = run.font.name
                        if run.font.size:
                            new_run.font.size = run.font.size
                        if run.font.bold is not None:
                            new_run.font.bold = run.font.bold
                        if run.font.italic is not None:
                            new_run.font.italic = run.font.italic
                        # 安全检查颜色类型
                        try:
                            if run.font.color and run.font.color.type is not None:
                                color_rgb = run.font.color.rgb
                                if color_rgb:
                                    new_run.font.color.rgb = color_rgb
                        except:
                            pass  # 忽略无法获取的颜色
            except Exception as e:
                print(f"  警告: 复制文本框失败: {e}")
    
    return new_slide


# ============================================
# PPT 生成
# ============================================

def create_presentation(
    data: PresentationData,
    figures_dir: str,
    template_path: str,
    output_path: str
):
    """创建演示文稿"""
    
    # 加载模板
    prs = Presentation(template_path)
    
    # 获取幻灯片尺寸
    slide_width = prs.slide_width
    slide_height = prs.slide_height
    slide_width_inch = slide_width.inches
    slide_height_inch = slide_height.inches
    
    print(f"  幻灯片尺寸: {slide_width_inch:.2f}\" x {slide_height_inch:.2f}\"")
    
    # 获取模板中的版式
    # 假设：第一张幻灯片是封面模板，第二张是内容页模板
    if len(prs.slides) < 2:
        print("错误: 模板至少需要2张幻灯片")
        sys.exit(1)
    
    # 保存模板幻灯片引用（在删除前）
    template_first_slide = prs.slides[0]
    template_normal_slide = prs.slides[1]
    first_slide_layout = template_first_slide.slide_layout
    normal_slide_layout = template_normal_slide.slide_layout
    
    # 计算布局参数
    margin_left = LAYOUT_CONFIG["margin_left"] * slide_width_inch
    margin_right = LAYOUT_CONFIG["margin_right"] * slide_width_inch
    gap = LAYOUT_CONFIG["gap"] * slide_width_inch
    
    # 分界线位置（3:2 分割）
    divider_x = slide_width_inch * LAYOUT_CONFIG["left_ratio"]
    
    # 左侧文字区域
    text_x = margin_left
    text_width = divider_x - margin_left - gap
    
    # 右侧图片区域
    image_x = divider_x + gap
    image_width = slide_width_inch - divider_x - margin_right - gap
    
    # 创建新的演示文稿来保存结果（从模板复制整个文件）
    # 但是直接修改现有的幻灯片
    # 策略：先复制所有需要的模板幻灯片，然后删除原模板
    
    # 先为每个内容幻灯片复制对应的模板
    slides_to_create = len(data.slides)
    
    # 复制模板幻灯片
    for slide_idx in range(slides_to_create):
        is_first = (slide_idx == 0)
        template_slide = template_first_slide if is_first else template_normal_slide
        # 使用 duplicate_slide 复制模板
        duplicate_slide(prs, template_slide)
    
    # 现在删除原始的两个模板幻灯片
    # 删除时从后往前删除，避免索引问题
    for _ in range(2):
        rId = prs.slides._sldIdLst[0].rId
        prs.part.drop_rel(rId)
        del prs.slides._sldIdLst[0]
    
    # 遍历每个 Slide 并填充内容
    for slide_idx, slide_data in enumerate(data.slides):
        is_first = (slide_idx == 0)
        slide = prs.slides[slide_idx]
        
        # 计算内容起始位置
        if is_first:
            content_start = LAYOUT_CONFIG["first_slide"]["content_start_ratio"] * slide_height_inch
        else:
            content_start = LAYOUT_CONFIG["normal_slide"]["content_start_ratio"] * slide_height_inch
        
        content_height = slide_height_inch - content_start - 0.3  # 底部留一点边距
        
        # === 第一页：替换标题和来源文本框 ===
        if is_first:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    text = shape.text_frame.text.strip().upper()
                    if "TITLE" in text:
                        # 替换标题
                        shape.text_frame.clear()
                        p = shape.text_frame.paragraphs[0]
                        run = p.add_run()
                        run.text = data.title
                        run.font.name = FONT_CONFIG["family"]
                        run.font.size = FONT_CONFIG["title_size"]
                        run.font.bold = True
                        run.font.color.rgb = COLORS["title"]
                        p.alignment = PP_ALIGN.CENTER
                    elif "SOURCE" in text:
                        # 替换来源
                        shape.text_frame.clear()
                        p = shape.text_frame.paragraphs[0]
                        run = p.add_run()
                        run.text = data.source
                        run.font.name = FONT_CONFIG["family"]
                        run.font.size = FONT_CONFIG["source_size"]
                        run.font.italic = True
                        run.font.color.rgb = COLORS["source"]
                        p.alignment = PP_ALIGN.CENTER
        
        # === 添加大纲内容 ===
        if slide_data.bullets:
            # 创建文本框
            txBox = slide.shapes.add_textbox(
                Inches(text_x),
                Inches(content_start),
                Inches(text_width),
                Inches(content_height)
            )
            tf = txBox.text_frame
            tf.word_wrap = True
            
            for i, bullet in enumerate(slide_data.bullets):
                if i == 0:
                    p = tf.paragraphs[0]
                else:
                    p = tf.add_paragraph()
                
                # 设置缩进和项目符号
                if bullet.level == 1:
                    p.level = 0
                    bullet_char = "▶ "
                    font_size = FONT_CONFIG["heading1_size"]
                    font_color = COLORS["heading1"]
                    is_bold = True
                    space_before = Pt(12) if i > 0 else Pt(0)
                elif bullet.level == 2:
                    p.level = 1
                    bullet_char = "▢ "
                    font_size = FONT_CONFIG["heading2_size"]
                    font_color = COLORS["heading2"]
                    is_bold = False
                    space_before = Pt(6)
                else:
                    p.level = 2
                    bullet_char = "• "
                    font_size = FONT_CONFIG["body_size"]
                    font_color = COLORS["body"]
                    is_bold = False
                    space_before = Pt(3)
                
                p.space_before = space_before
                
                # 添加带格式的文本（先添加符号，再添加内容）
                run = p.add_run()
                run.text = bullet_char
                run.font.name = FONT_CONFIG["family"]
                run.font.size = font_size
                run.font.bold = is_bold
                run.font.color.rgb = font_color
                
                # 添加内容（支持 **粗体** 格式）
                add_formatted_text(p, bullet.text, FONT_CONFIG["family"], 
                                   font_size, font_color, is_bold)
        
        # === 添加配图 ===
        if slide_data.figures:
            # 收集图片信息
            images_info = []
            for fig_name in slide_data.figures:
                fig_path = find_figure_file(figures_dir, fig_name)
                if fig_path:
                    w, h = get_image_size(fig_path)
                    images_info.append((fig_path, w, h))
                else:
                    print(f"  警告: 找不到图片 '{fig_name}'")
            
            if images_info:
                # 计算布局
                layout_result = calculate_image_layout(
                    images_info, image_width, content_height
                )
                
                # 添加图片
                for path, x, y, w, h in layout_result:
                    slide.shapes.add_picture(
                        path,
                        Inches(image_x + x),
                        Inches(content_start + y),
                        Inches(w),
                        Inches(h)
                    )
        
        # === 添加 Speaker Notes ===
        if slide_data.notes:
            notes_slide = slide.notes_slide
            notes_tf = notes_slide.notes_text_frame
            notes_tf.text = slide_data.notes
    
    # 保存文件
    prs.save(output_path)
    print(f"[OK] PPT 生成成功: {output_path}")
    print(f"   总页数: {len(data.slides)}")


# ============================================
# 主函数
# ============================================

def main():
    if len(sys.argv) < 5:
        print("Usage: python build_ppt.py <ppt_content.md> <figures_dir> <template.pptx> <output.pptx>")
        print("")
        print("Example:")
        print("  python build_ppt.py output/ppt_content.md output/ Template.pptx output/presentation.pptx")
        sys.exit(1)
    
    content_file = sys.argv[1]
    figures_dir = sys.argv[2]
    template_file = sys.argv[3]
    output_file = sys.argv[4]
    
    # 检查文件
    if not os.path.exists(content_file):
        print(f"错误: 找不到内容文件: {content_file}")
        sys.exit(1)
    
    if not os.path.exists(template_file):
        print(f"错误: 找不到模板文件: {template_file}")
        sys.exit(1)
    
    # 读取内容
    print(f"[*] 读取内容文件: {content_file}")
    with open(content_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 解析
    data = parse_markdown(content)
    print(f"[*] 解析结果:")
    print(f"   标题: {data.title}")
    print(f"   来源: {data.source}")
    print(f"   幻灯片数: {len(data.slides)}")
    for i, slide in enumerate(data.slides):
        print(f"   Slide {i+1}: {len(slide.bullets)} 个要点, {len(slide.figures)} 张配图")
    
    # 生成 PPT
    print(f"[*] 生成 PPT...")
    create_presentation(data, figures_dir, template_file, output_file)


if __name__ == "__main__":
    main()
