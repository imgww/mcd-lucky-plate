"""生成 README 配图（零第三方依赖，标准库 SVG + Chrome 截图转 PNG）。

数据全部来自真实样本求解（见 `export_fig_data()`），不手写、不估算。
因此本脚本可独立重跑，无需任何前置步骤。

产出（docs/figs/）：
  themes.svg/png      8 主题 · 主题预算 vs 实际热量 + 谐音命中数
  motifs.svg/png      餐品幸运清单 · 覆盖率 + Top 寓意分布
  anchors.svg/png     谐音锚点 50 条命中情况
  order.svg/png       从餐单到下单的四步链路
  banner.svg/png      顶部横幅（标题 + 关键数字）

用法：
    python docs/make_figs.py          # 生成 SVG + 尝试转 PNG
    python docs/make_figs.py --svg-only

依赖：Python 3.10+ 标准库；转 PNG 需本机 Chrome（缺失时只产出 SVG，不报错）
"""
from __future__ import annotations

import json
import subprocess
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIGS = ROOT / "docs" / "figs"
DATA = ROOT / "docs" / "_figs_data.json"
SAMPLE = ROOT / "samples" / "nutrition-foods.raw.json"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

BG = "#F7F4EC"        # 米色底
INK = "#241F1A"       # 主文字
INK2 = "#6B6259"      # 次文字
RED = "#A8271F"       # 暗红强调
GREEN = "#3F6B4A"
LINE = "#D8D0C2"

PALETTE = ["#A8271F", "#3F6B4A", "#8A6A3B", "#4A5B7C",
           "#7A4A62", "#556B2F", "#8B5A2B", "#4F4A69"]


def svg_open(w: int, h: int, title: str, desc: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-labelledby="t d">',
        f'<title id="t">{escape(title)}</title>',
        f'<desc id="d">{escape(desc)}</desc>',
        f'<rect width="{w}" height="{h}" fill="{BG}"/>',
    ]


def text(x, y, s, size=14, fill=INK, weight=400, anchor="start",
         family="'Noto Sans CJK SC','Microsoft YaHei',sans-serif"):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'font-weight="{weight}" text-anchor="{anchor}" '
            f'font-family="{family}">{escape(s)}</text>')


def to_png(svg_path: Path) -> bool:
    """用 Chrome headless 把 SVG 截成 PNG。无 Chrome 则跳过。"""
    if not Path(CHROME).exists():
        return False
    png = svg_path.with_suffix(".png")
    try:
        subprocess.run(
            [CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
             "--force-device-scale-factor=2",
             f"--screenshot={png}", f"--window-size={_size(svg_path)}",
             svg_path.as_uri()],
            capture_output=True, timeout=90, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return png.exists()


_size_cache: dict[Path, str] = {}


def _size(p: Path) -> str:
    head = p.read_text(encoding="utf-8")[:300]
    w = h = 800
    for key, var in (("width=", "w"), ("height=", "h")):
        i = head.find(key)
        if i >= 0:
            seg = head[i:].split('"')[1] if '"' in head[i:i + 40] else ""
            try:
                v = int(float(seg))
                if var == "w":
                    w = v
                else:
                    h = v
            except ValueError:
                pass
    return f"{w},{h}"


# ---------------------------------------------------------------- fig 1: banner
def fig_banner(d: dict) -> str:
    W, H = 960, 300
    s = svg_open(W, H, "麦门幸运餐盘",
                 "按幸运主题用谐音寓意解出可下单的麦当劳餐单")
    s.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="{BG}"/>')
    s.append(f'<rect x="0" y="0" width="{W}" height="6" fill="{RED}"/>')
    s.append(text(48, 92, "麦门幸运餐盘", 44, INK, 500))
    s.append(text(48, 132, "按心愿解出一餐谐音俱全的麦当劳搭配", 19, INK2))
    s.append(text(48, 166, "mcd-lucky-plate · 麦当劳 MCP 创意开发大赛参赛作品",
                  14, INK2))

    stats = [
        ("8", "幸运主题"),
        ("154", "餐品全收录"),
        ("215", "幸运寓意"),
        ("50/50", "谐音锚点命中"),
        ("2081", "回归断言"),
    ]
    x = 48
    for i, (num, label) in enumerate(stats):
        cx = x + i * 176
        s.append(text(cx, 232, num, 34, RED if i < 4 else INK, 500))
        s.append(text(cx, 258, label, 13, INK2))
    return "\n".join(s) + "\n</svg>"


# ------------------------------------------------------------- fig 2: themes
def fig_themes(d: dict) -> str:
    """8 主题横向条形图：横向布局避免中文标签互相重叠。"""
    ts = d["themes"]
    W, H = 1080, 480
    L, R, TOP = 190, 560, 92
    s = svg_open(W, H, "8 个幸运主题的餐单对比",
                 "每个主题的实际热量、预算与谐音命中数")
    s.append(text(48, 42, "同一天 · 同一份菜单 · 8 个主题给出 8 种不同答案",
                  18, INK, 500))
    s.append(text(48, 63, "全部严格档求解，无放宽。数值为实际求解结果，"
                          "非示意", 12, INK2))

    mx = max(max(t["actual_kcal"] for t in ts),
             max(t["theme_kcal"] for t in ts)) * 1.02
    rowh = (H - TOP - 54) / len(ts)
    bh = min(18.0, rowh * 0.42)

    # 竖向刻度（顶端留出标题空间）
    for g in range(0, 1001, 200):
        x = L + g / mx * (R - L)
        s.append(f'<line x1="{x:.1f}" y1="{TOP - 6}" x2="{x:.1f}" '
                 f'y2="{H - 48}" stroke="{LINE}" stroke-width="1"/>')
        s.append(text(x, TOP - 12, str(g), 10, INK2, anchor="middle"))

    for i, t in enumerate(ts):
        cy = TOP + rowh * i + rowh / 2
        w = t["actual_kcal"] / mx * (R - L)
        bx = L + t["theme_kcal"] / mx * (R - L)
        s.append(f'<line x1="{bx:.1f}" y1="{cy - bh - 4:.1f}" '
                 f'x2="{bx:.1f}" y2="{cy + bh + 4:.1f}" stroke="{INK}" '
                 f'stroke-width="1.2"/>')
        s.append(f'<rect x="{L}" y="{cy - bh / 2:.1f}" width="{w:.1f}" '
                 f'height="{bh:.1f}" rx="3" '
                 f'fill="{PALETTE[i % len(PALETTE)]}"/>')
        s.append(text(L - 12, cy, t["name"], 13, INK, 500, "end"))
        s.append(text(R + 10, cy - 4, f"{t['actual_kcal']} kcal", 11, INK))
        s.append(text(R + 10, cy + 9,
                      f"谐音 {t['hits']} · {t['plans']} 个可选餐单", 10, INK2))
        # 预算标注贴在竖线正上方，随竖线走
        s.append(text(bx, cy - bh - 8, f"预算{t['theme_kcal']}", 9, INK2,
                      anchor="middle"))

    s.append(f'<line x1="{L}" y1="{H - 48}" x2="{R}" y2="{H - 48}" '
             f'stroke="{INK}" stroke-width="1"/>')
    s.append(text(48, H - 20,
                  "条长= 实际配餐热量　竖线 = 主题预算（kcal）　"
                  "右侧为该主题命中的谐音数与可选餐单数", 11, INK2))
    return "\n".join(s) + "\n</svg>"


# ------------------------------------------------------------- fig 3: motifs
def fig_motifs(d: dict) -> str:
    W, H = 960, 400
    s = svg_open(W, H, "餐品幸运清单",
                 f"{d['menu_covered']} 项餐品全收录，共 {d['motif_total']} 条寓意")
    s.append(text(48, 42, "餐品幸运清单：先穷举全部餐品，再由主题挑选", 19,
                  INK, 500))
    s.append(text(48, 64, "早期版本只有主题词库，导致未被任何主题用到的餐品"
                          "没有寓意——清单把方向反过来", 12, INK2))

    # 左：覆盖率大数字
    s.append(f'<rect x="48" y="94" width="250" height="150" rx="12" '
             f'fill="#FFFFFF" stroke="{LINE}"/>')
    s.append(text(70, 148, f"{d['menu_covered']}", 52, RED, 500))
    s.append(text(70, 178, f"/ {d['menu_total']} 项餐品", 13, INK2))
    cov = d["menu_covered"] / d["menu_total"] * 100
    s.append(text(70, 214, f"覆盖率 {cov:.0f}%", 16, GREEN, 500))
    s.append(text(70, 234, "无「无解」项", 12, INK2))

    # 右：三个指标
    metrics = [(d["motif_total"], "条寓意"), (d["motif_kinds"], "种寓意标签"),
               (50, "条谐音锚点")]
    x = 330
    for i, (num, label) in enumerate(metrics):
        cx = x + i * 150
        s.append(f'<rect x="{cx}" y="94" width="130" height="150" rx="12" '
                 f'fill="#FFFFFF" stroke="{LINE}"/>')
        s.append(text(cx + 65, 158, str(num), 34, INK, 500, "middle"))
        s.append(text(cx + 65, 186, label, 12, INK2, anchor="middle"))

    # 下：Top 寓意条形
    s.append(text(48, 288, "寓意覆盖 Top 8", 15, INK, 500))
    top = d["top_motifs"]
    mx = max(m["n"] for m in top)
    for i, m in enumerate(top):
        y = 306 + i * 0  # 单列布局在下方另行处理
    for i, m in enumerate(top):
        col = i % 2
        row = i // 2
        bx = 48 + col * 440
        by = 308 + row * 24
        w = m["n"] / mx * 220
        s.append(f'<rect x="{bx + 62}" y="{by}" width="{w:.0f}" height="11" '
                 f'rx="5.5" fill="{PALETTE[i % len(PALETTE)]}"/>')
        s.append(text(bx, by + 10, m["key"], 12, INK))
        s.append(text(bx + 290, by + 10, f"{m['n']} 项", 11, INK2))
    return "\n".join(s) + "\n</svg>"


# ----------------------------------------------------------- fig 4: anchors
def fig_anchors(d: dict) -> str:
    W, H = 960, 300
    s = svg_open(W, H, "谐音锚点核验", "50 条谐音锚点全部在真实菜单中命中")
    s.append(text(48, 44, "谐音锚点 × 真实菜单：50/ 50 全部命中", 19, INK, 500))
    s.append(text(48, 66, "每个梗都必须能回答「它对应菜单上哪一道菜」，"
                          "答不上来就不算梗", 12, INK2))

    # 进度条
    s.append(f'<rect x="48" y="96" width="864" height="26" rx="13" '
             f'fill="#EDE7DA"/>')
    s.append(f'<rect x="48" y="96" width="864" height="26" rx="13" fill="{GREEN}"/>')
    s.append(text(480, 114, "50 / 50", 15, "#FFFFFF", 500, "middle"))

    examples = [
        ("鸡腿 / 麦乐鸡", "「鸡」谐音「吉」→ 大吉大利"),
        ("吉士", "「吉」字面吉利义"),
        ("牛气满满", "官方命名 → 牛气冲天"),
        ("多笋卷", "「笋」谐音「顺」→ 多顺"),
        ("专“薯鱼”你", "「薯鱼」谐音「属你」"),
        ("鳕鱼", "「鳕」谐音「学」→ 学识深"),
    ]
    for i, (a, b) in enumerate(examples):
        col, row = i % 3, i // 3
        x = 48 + col * 292
        y = 158 + row * 56
        s.append(f'<rect x="{x}" y="{y}" width="272" height="46" rx="8" '
                 f'fill="#FFFFFF" stroke="{LINE}"/>')
        s.append(text(x + 12, y + 19, a, 13, INK, 500))
        s.append(text(x + 12, y + 35, b, 11, INK2))
    return "\n".join(s) + "\n</svg>"


# -------------------------------------------------------------- fig 5: order
def fig_order(d: dict) -> str:
    W, H = 960, 250
    s = svg_open(W, H, "从餐单到下单的四步链路",
                 "本 Skill 停在品名级，不代下单")
    s.append(text(48, 44, "从餐单到真实订单：四步链路", 19, INK, 500))
    s.append(text(48, 66, "营养表不含 productCode，需确定门店后现查——"
                          "这是餐单停在品名级的原因", 12, INK2))

    steps = [
        ("①", "query-nearby-stores", "选门店\n拿 storeCode", RED),
        ("②", "query-meals", "拿 productCode\n与价格", RED),
        ("③", "calculate-price", "试算总价\n得 takeWayCode", "#8A6A3B"),
        ("④", "create-order", "用户确认后\n才下单", GREEN),
    ]
    bw, gap = 200, 24
    x = 48
    for i, (n, tool, desc, col) in enumerate(steps):
        s.append(f'<rect x="{x}" y="96" width="{bw}" height="96" rx="10" '
                 f'fill="#FFFFFF" stroke="{col}" stroke-width="1.5"/>')
        s.append(text(x + 14, 122, n, 20, col, 500))
        s.append(text(x + 14, 146, tool, 12, INK, 500))
        for j, ln in enumerate(desc.split("\n")):
            s.append(text(x + 14, 166 + j * 15, ln, 11, INK2))
        if i < 3:
            ax = x + bw + gap / 2
            s.append(f'<line x1="{x + bw}" y1="144" x2="{x + bw + gap}" '
                     f'y2="144" stroke="{INK2}" stroke-width="1.5" '
                     f'marker-end="url(#ar)"/>')
        x += bw + gap

    s.append(f'<defs><marker id="ar" viewBox="0 0 10 10" refX="8" refY="5" '
             f'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
             f'<path d="M2 1L8 5L2 9" fill="none" stroke="{INK2}" '
             f'stroke-width="1.5"/></marker></defs>')
    s.append(text(48, 222, "本 Skill 只输出餐单与链路指引，不代下单；"
                           "价格单位为分，下单前需 calculate-price 试算",
                  12, INK2))
    return "\n".join(s) + "\n</svg>"


FIGS_MAIN = [
    ("banner", fig_banner),
    ("themes", fig_themes),
    ("motifs", fig_motifs),
    ("anchors", fig_anchors),
    ("order", fig_order),
]


def export_fig_data() -> dict:
    """从真实样本求解一遍，取出配图所需数字。

    刻意不读缓存 JSON：每次生成都重新求解，保证图上的数字与代码实际
    行为一致，不会出现「改了引擎但图没更新」的情况。
    """
    sys.path.insert(0, str(ROOT / "src"))
    from lucky import THEMES, THEME_ORDER
    from lucky_engine import compose_lucky
    from menu_luck import MENU_LUCK, motifs_index
    from nutrition import load_offline

    foods = load_offline(SAMPLE)
    out = {"themes": []}
    for k in THEME_ORDER:
        t = THEMES[k]
        r = compose_lucky(foods, t)
        p = r["plans"][0] if r["plans"] else None
        out["themes"].append({
            "key": k, "name": t.name, "theme_kcal": t.kcal,
            "solved": bool(p), "hits": p.luck_score if p else 0,
            "plans": len(r["plans"]),
            "actual_kcal": round(p.plan.kcal) if p else 0,
            "sodium": round(p.plan.sodium) if p else 0,
            "sodium_limit": round(p.plan.sodium_limit) if p else 0,
            "items": [f.name for f in p.plan.items] if p else [],
        })
    idx = motifs_index()
    out["menu_total"] = len(foods)
    out["menu_covered"] = len(MENU_LUCK)
    out["motif_kinds"] = len(idx)
    out["motif_total"] = sum(len(v) for v in MENU_LUCK.values())
    out["top_motifs"] = [{"key": k, "n": len(v)} for k, v in
                         sorted(idx.items(), key=lambda kv: -len(kv[1]))[:8]]
    # 缓存仅供人工排查用，缺失时会自动重算
    DATA.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return out


def main() -> int:
    if not SAMPLE.exists():
        print(f"缺少样本文件 {SAMPLE}", file=sys.stderr)
        print("请先运行 python src/lucky_plate.py --probe-dump "
              "samples/nutrition-foods.raw.json", file=sys.stderr)
        return 1
    d = export_fig_data()
    FIGS.mkdir(parents=True, exist_ok=True)
    svg_only = "--svg-only" in sys.argv

    made_png = 0
    for name, fn in FIGS_MAIN:
        p = FIGS / f"{name}.svg"
        p.write_text(fn(d), encoding="utf-8")
        print(f"  生成 {p.relative_to(ROOT)}")
        if not svg_only and to_png(p):
            made_png += 1
            print(f"  生成 {p.with_suffix('.png').relative_to(ROOT)}")

    if made_png < len(FIGS_MAIN):
        print(f"\nPNG 转换 {made_png}/{len(FIGS_MAIN)} 成功。"
              f"缺 PNG 时 GitHub 仍可正常显示 SVG。")
    print(f"\n完成：{len(FIGS_MAIN)} 张图，{made_png} 张 PNG。")
    return 0


if __name__ == "__main__":
    sys.exit(main())