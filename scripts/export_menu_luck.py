"""生成「餐品幸运清单」文档与 CSV。

用法：
    python scripts/export_menu_luck.py

产出：
    docs/餐品幸运清单.md    按品类分组的可读清单
    docs/餐品幸运清单.csv    逐条寓意（utf-8-sig，Excel 双击不乱码）

清单数据源是 `src/menu_luck.py`，本脚本只负责渲染，不含主观内容。
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from menu_luck import MENU_LUCK, motifs_index          # noqa: E402
from nutrition import load_offline                     # noqa: E402

SAMPLE = ROOT / "samples" / "nutrition-foods.raw.json"
OUT_MD = ROOT / "docs" / "餐品幸运清单.md"
OUT_CSV = ROOT / "docs" / "餐品幸运清单.csv"

KIND_CN = {"homophone": "谐音", "literal": "字面",
           "brand": "官方", "reverse": "反向", "none": "无"}

CAT_ORDER = ["主食", "小食", "甜品", "饮品", "果蔬", "其他"]

HEADER = """# 餐品幸运清单

> 麦当劳真实在售 **{total}** 项餐品，逐项列出它能承载的幸运寓意。

数据源：`list-nutrition-foods` 实际响应（快照 `samples/nutrition-foods.raw.json`）
寓意词库：`src/menu_luck.py`　渲染：`scripts/export_menu_luck.py`

## 这份清单解决什么问题

早期版本只有「主题词库」——由主题定义关键词、再反查餐品。
那个方向有个结构性缺陷：**只有被某个主题用到的餐品才有寓意**，
其余一百多项白白浪费。用户问「我这杯燕麦奶有什么寓意」时答不上来。

本清单把方向反过来：**先穷举全部餐品，为每项标注它能承载的寓意**，主题再从清单里挑。

带来的改变：

| | 主题词库（旧） | 餐品幸运清单（本文件） |
|---|---|---|
| 覆盖 | 8 个主题用到的约 50 项 | 全部 {total} 项，覆盖率 100% |
| 方向 | 主题 → 关键词 → 反查餐品 | 餐品 → 寓意 → 主题引用 |
| 可查性 | 只能问「某主题吃什么」 | 能问「这道菜有什么寓意」「什么菜有大吉大利」 |
| 可审计| 寓意散落在主题里 | 寓意集中在一张表，可逐条复核 |

## 怎么用

```bash
# 看完整清单
python src/lucky_plate.py --menu-luck --offline samples/nutrition-foods.raw.json

# 反查某个寓意对应哪些餐品
python src/lucky_plate.py --menu-luck 大吉大利 --offline samples/nutrition-foods.raw.json
python src/lucky_plate.py --menu-luck 满分 --offline samples/nutrition-foods.raw.json
```

## 字段说明

| 字段 | 含义 |
|---|---|
| 餐品 | 官方在售品名，原样保留（含全角引号等命名符号） |
| 热量 | kcal，来自 MCP 营养数据 |
| 寓意标签 | 如「大吉大利」「牛气冲天」，主题词库引用的就是它 |
| 类型 | `谐音` / `字面` / `官方` / `反向` |
| 契合度 | 3 = 梗很硬一听就成立；2 = 成立但需解释一句；1 = 牵强，主题一般不取 |
| 说明 | 怎么念怎么解释 |
| 溯源 | 来源与边界，含「是否官方」「有无歧义」 |

**契合度只用于排序与人工判断，不参与求解。**
打分的权重在 `lucky_engine.py`，寓意本身不改变分数。

## 关于「牵强」的诚实处理

清单里有契合度 1 的条目（如「皮蛋 → 皮开得逞」「草莓拉明顿 → 拉你」）。
它们被保留下来并明确标注为牵强，而不是删掉或伪装成硬梗——
这样使用者可以自行判断要不要取用。

主题词库只取契合度 ≥2 的梗，避免污染输出。

---

## 完整清单（按品类）
"""

FOOTER = """
---

## 寓意索引

按寓意标签反查，共 **{motif_count}** 种寓意。

| 寓意 | 餐品数 | 示例 |
|---|---:|---|
{index_rows}

## 官方营销梗名（最可靠的素材）

菜单里有三个品名是麦当劳官方自带的营销梗，谐音天然工整，优先使用：

| 品名 | 梗 | 说明 |
|---|---|---|
| 牛气满满 | 牛气冲天 | 官方命名自带「牛气」，非本项目原创 |
| 专“薯鱼”你 | 专薯鱼你 | 「薯鱼/属你」为极工整的谐音 |
| “苹板”支撑Pro | 平安 | 「苹板/平板」双关，取「平安有支撑」 |

## 统计

- 餐品总数：**{total}** 项，清单收录 **{total}** 项，覆盖率 **100%**
- 寓意种类：**{motif_count}** 种
- 寓意条数：**{luck_count}** 条（平均每道菜 {avg:.1f} 条）

## 边界与免责

- 谐音仅限**官方在售品名本身**，不涉及谐音梗的二次创作
- 所有谐音与吉祥话是**文案玩法**，不构成任何运势或效果承诺
- 餐品信息、价格及供应状态以麦当劳官方渠道实时结果为准
- 本项目为参赛作品，非麦当劳官方产品；输出不构成医疗或营养建议
"""


def main() -> int:
    if not SAMPLE.is_file():
        print(f"样本不存在：{SAMPLE}", file=sys.stderr)
        return 1
    foods = load_offline(SAMPLE)
    by_name = {f.name: f for f in foods}

    missing = [f.name for f in foods if f.name not in MENU_LUCK]
    if missing:
        print(f"⚠ 有 {len(missing)} 项未收录寓意，将按「未收录」列出：", file=sys.stderr)
        for n in missing:
            print(f"    {n}", file=sys.stderr)

    # ---------- Markdown ----------
    lines = [HEADER.format(total=len(foods))]
    for cat in CAT_ORDER:
        items = [f for f in foods if f.category == cat]
        if not items:
            continue
        lines.append(f"\n### {cat}（{len(items)} 项）\n")
        lines.append("| 餐品 | 热量 | 寓意（类型·契合） | 说明 |")
        lines.append("|---|---:|---|---|")
        for f in items:
            lucks = MENU_LUCK.get(f.name)
            if not lucks:
                lines.append(f"| {f.name} | {f.kcal:.0f} kcal | — |"
                             "**未收录寓意** |")
                continue
            cells = []
            for l in lucks:
                flag = "" if l.score >= 2 else "（牵强）"
                cells.append(f"**{l.key}**{flag}<br>"
                             f"{KIND_CN.get(l.kind, l.kind)}·{l.score}")
            lines.append(
                f"| {f.name} | {f.kcal:.0f} kcal | " + "<br>".join(cells)
                + " | " + "；".join(l.gloss for l in lucks) + " |")
    lines.append("")

    idx = motifs_index()
    rows = []
    for key, names in sorted(idx.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        # 按 key 精确匹配该寓意自己的 gloss，不用该餐品的第一条
        gloss = next((l.gloss for n in names
                      for l in MENU_LUCK.get(n, ()) if l.key == key), "")
        rows.append(f"| {key} | {len(names)} | {gloss} |")
    lines.append(FOOTER.format(
        total=len(foods), motif_count=len(idx),
        luck_count=sum(len(v) for v in MENU_LUCK.values()),
        avg=sum(len(v) for v in MENU_LUCK.values()) / max(1, len(MENU_LUCK)),
        index_rows="\n".join(rows)))

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    # ---------- CSV ----------
    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["品类", "餐品", "热量kcal", "钠mg", "寓意标签",
                    "类型", "契合度", "说明", "溯源"])
        for f in foods:
            lucks = MENU_LUCK.get(f.name)
            if not lucks:
                w.writerow([f.category, f.name, f"{f.kcal:.0f}", f"{f.sodium:.0f}",
                            "", "", "", "未收录寓意", ""])
                continue
            for l in lucks:
                w.writerow([f.category, f.name, f"{f.kcal:.0f}", f"{f.sodium:.0f}",
                            l.key, KIND_CN.get(l.kind, l.kind), l.score,
                            l.gloss, l.note])

    print(f"已生成 {OUT_MD.relative_to(ROOT)}  ({len(foods)} 项)")
    print(f"已生成 {OUT_CSV.relative_to(ROOT)}"
          f"  ({sum(len(v) for v in MENU_LUCK.values())} 条寓意)")
    print(f"覆盖率 {len(MENU_LUCK) / len(foods) * 100:.1f}%"
          f"　寓意种类 {len(idx)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())