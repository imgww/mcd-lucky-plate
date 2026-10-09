"""终端文本排版工具：显示宽度感知的对齐与进度条。

单独成模块的原因：`render.py` 依赖 `composer`/`week_planner`，若排版函数放在 render 里，
composer 反向引用就会形成循环导入。这里保持零依赖，两侧都可安全引用。

为什么需要 display_width：CJK 字符与 emoji 在终端里占 2 列，Python 的 `str.ljust`
按码点数补齐，导致「猪柳蛋麦满分」和「板烧鸡腿堡」混排时整列错位——这是之前终端
输出可读性差的主因。
"""

from __future__ import annotations


def char_width(ch: str) -> int:
    """单个字符的终端显示宽度（东亚宽字符与 emoji 记 2，其余记 1）。"""
    o = ord(ch)
    if (0x1100 <= o <= 0x115F          # 韩文字母
            or 0x2E80 <= o <= 0x303E    # CJK 符号与标点
            or 0x3041 <= o <= 0x33FF    # 假名 / CJK 兼容
            or 0x3400 <= o <= 0x4DBF    # 扩展 A
            or 0x4E00 <= o <= 0x9FFF    # 基本汉字
            or 0xA000 <= o <= 0xA4CF    # 彝文
            or 0xAC00 <= o <= 0xD7A3    # 韩文音节
            or 0xF900 <= o <= 0xFAFF    # 兼容表意文字
            or 0xFE30 <= o <= 0xFE6F    # 兼容形式
            or 0xFF00 <= o <= 0xFF60    # 全角字符
            or 0xFFE0 <= o <= 0xFFE6
            or 0x1F300 <= o <= 0x1FAFF  # 表情与图形符号
            or 0x20000 <= o <= 0x3FFFD):
        return 2
    return 1


def display_width(s: str) -> int:
    return sum(char_width(ch) for ch in str(s))


def pad(s: str, width: int, align: str = "left") -> str:
    """按显示宽度补齐。align: left / right / center。"""
    s = str(s)
    gap = max(0, width - display_width(s))
    if align == "right":
        return " " * gap + s
    if align == "center":
        left = gap // 2
        return " " * left + s + " " * (gap - left)
    return s + " " * gap


def truncate(s: str, width: int) -> str:
    """按显示宽度截断，超出补省略号。"""
    s = str(s)
    if display_width(s) <= width:
        return s
    out, used = "", 0
    for ch in s:
        w = char_width(ch)
        if used + w > width - 1:
            break
        out += ch
        used += w
    return out + "…"


def bar(value: float, cap: float, cells: int = 10) -> str:
    """块字符进度条。超过上限时末格标 '!'，避免看起来仍有余量。"""
    if cap <= 0:
        return " " * (cells + 1)
    ratio = max(0.0, min(1.0, value / cap))
    filled = int(round(ratio * cells))
    return "█" * filled + "░" * (cells - filled) + ("!" if value > cap else " ")


def rule(ch: str = "─", width: int = 72) -> str:
    return ch * width


# 品类图标。放在零依赖的排版模块里，供终端与 HTML 两侧共用，
# 避免 composer -> render 的反向依赖形成循环导入。
CATEGORY_ICON: dict[str, str] = {
    "主食": "🍔",   # 🍔
    "小食": "🍟",   # 🍟
    "饮品": "🥤",   # 🥤
    "甜品": "🍦",   # 🍦
    "果蔬": "🌽",   # 🌽
    "其他": "🍽",   # 🍽
}


def icon(category: str) -> str:
    return CATEGORY_ICON.get(category, "🍽")
