"""麦门幸运餐盘 · CLI 入口

用法
----
    # 列出全部幸运主题与谐音词库
    python src/lucky_plate.py --themes

    # 指定主题出餐单（默认离线模式，无需 Token）
    python src/lucky_plate.py --theme 一夜暴富
    python src/lucky_plate.py --theme exam --top 3

    # 逐条核验谐音梗在真实菜单里的命中情况
    python src/lucky_plate.py --anchors

    # 同一天不同主题给出不同答案（本 Skill 的核心证明）
    python src/lucky_plate.py --compare

    # 机器可读输出（含下单引导所需的品名清单）
    python src/lucky_plate.py --theme jackpot --json

    # 在线模式（需 MCD_MCP_TOKEN）
    python src/lucky_plate.py --theme jackpot

下单说明：本 Skill **只出餐单、不下单**。产出的是品名级方案；
productCode 需由 MCP `query-meals` 在确定门店后现查，详见 README 与
`--order-help` 的输出。

免责声明：输出仅供参考，不构成医疗、营养或其他专业建议。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lucky import THEMES, THEME_ORDER, all_wishes, get
from lucky_engine import compare_themes, compose_lucky, iter_themes
from menu_luck import MENU_LUCK, motifs_index, uncovered_foods
from nutrition import detect_unknown_fields, fetch_foods, load_offline

DISCLAIMER = ("本项目为麦当劳程序员节创意开发大赛参赛作品，非麦当劳官方产品。"
              "输出仅供参考，不构成医疗、营养或其他专业建议；"
              "餐品信息、价格及供应状态以麦当劳官方渠道的实时结果为准。"
              "谐音与吉祥话仅为文案玩法，不构成任何运势或效果承诺。")

BAR = "═" * 68
SUB = "─" * 68

ORDER_HELP = """\
从餐单到下单：还差一步「名称 → productCode」

本 Skill 停在品名级，这是刻意的。原因：
  list-nutrition-foods 返回营养成分，**不含 productCode**；
  productCode 只能由 query-meals 在**确定门店后**取得，
  因此它天然依赖 storeCode（门店/地理位置），而这会让餐单无法离线复现。

在 MCP 客户端里完成下单的顺序：
  1. query-nearby-stores   选门店，拿到 storeCode
                           （beType=1 到店自取 / beType=5 得来速）
  2. query-meals           按 storeCode 拉该店在售餐品，取得 productCode 与价格
  3. calculate-price       用 productCode 试算总价，确认金额
                           （返回的 takeWayList[].code 才是下单要传的 takeWayCode）
  4. create-order          用户明确确认后再下单

要点：
  * 到店自取（beType=1）：orderType=1，不传 beCode
  * 得来速（beType=5）  ：orderType=1，**必传** beCode
  * 外送（orderType=2）  ：必传 addressId 与 beCode
  * 价格单位是**分**，展示需 ÷100
  * 本 Skill 不代你调用上述任何一步；下单是有资损的动作，须由用户确认
"""


def _load(args):
    """按 --offline / 联网两种模式取营养数据。"""
    if args.offline:
        path = Path(args.offline)
        if not path.is_file():
            print(f"离线数据文件不存在：{args.offline}", file=sys.stderr)
            print("仓库自带样本位于 samples/nutrition-foods.raw.json，"
                  "也可配置 MCD_MCP_TOKEN 走联网模式。", file=sys.stderr)
            sys.exit(2)
        try:
            foods = load_offline(path)
        except (OSError, ValueError) as exc:
            print(f"离线数据无法解析：{exc}", file=sys.stderr)
            sys.exit(3)
        if not foods:
            print("离线数据归一化后为 0 项，判定字段结构已变更。", file=sys.stderr)
            sys.exit(3)
        return foods
    from mcp_client import StreamableHTTPClient, mask_secret
    try:
        client = StreamableHTTPClient()
        foods, payload = fetch_foods(
            client, args.probe_dump if args.probe_dump else None)
        if not foods:
            print("归一化结果为 0 项，判定字段未校准。真实键名：", file=sys.stderr)
            print(detect_unknown_fields(payload), file=sys.stderr)
            sys.exit(3)
        return foods
    except SystemExit:
        raise
    except Exception as exc:                      # noqa: BLE001
        print(mask_secret(str(exc)), file=sys.stderr)
        sys.exit(2)


def _fmt_themes() -> None:
    print(BAR)
    print("  麦门幸运餐盘 · 8 个幸运主题与谐音词库".center(66))
    print(BAR)
    for k in THEME_ORDER:
        t = THEMES[k]
        print(f"  【{t.name}】{t.key}    {t.tagline}")
        print(f"     {t.voice}")
        print(f"     预算 {t.kcal:.0f} kcal ±{t.tolerance:.0%}"
              f"   钠上限 {t.max_sodium or round(t.kcal * 1.8):.0f} mg"
              f"   甜品{'开' if t.allow_dessert else '关'}"
              f"   谐音梗 {len(t.wishes)} 个")
        print(f"     梗：{' / '.join(w.gloss.split(' → ')[0] for w in t.wishes)}")
    print(SUB)
    print(f"  合计 {len(all_wishes())} 条谐音单元，全部锚定真实在售餐品。")
    print(BAR)


def _fmt_menu_luck(foods, motif: str | None) -> None:
    """餐品幸运清单：每一道菜能承载什么寓意。"""
    idx = motifs_index()
    covered = sum(1 for f in foods if f.name in MENU_LUCK)
    print(BAR)
    print(f"  餐品幸运清单 · {covered}/{len(foods)} 项已收录寓意".center(66))
    print(BAR)

    if motif:
        names = idx.get(motif)
        if not names:
            print(f"  未找到寓意「{motif}」。可用寓意共 {len(idx)} 种，例：")
            print("  " + "、".join(list(idx)[:12]))
            print(BAR)
            return
        print(f"  寓意「{motif}」→ {len(names)} 项餐品")
        print(SUB)
        for n in names:
            for l in MENU_LUCK[n]:
                if l.key == motif:
                    print(f"     · {n:<32} [{l.kind}] {l.gloss}")
        print(BAR)
        return

    if motif is None:
        by_cat: dict[str, list] = {}
        for f in foods:
            if f.name in MENU_LUCK:
                by_cat.setdefault(f.category, []).append(f)
        for cat in sorted(by_cat):
            print(f"  ── {cat}（{len(by_cat[cat])} 项）")
            for f in by_cat[cat]:
                lucks = MENU_LUCK[f.name]
                bestl = max(lucks, key=lambda x: x.score)
                tags = " ".join(f"{l.key}[{l.score}]" for l in lucks)
                print(f"     {f.name:<30} {f.kcal:>5.0f}kcal  {tags}")
            print()
    miss = uncovered_foods(foods)
    print(SUB)
    print(f"  寓意种类 {len(idx)} 种   已收录 {covered}/{len(foods)} 项")
    if miss:
        print(f"  ⚠ 未收录寓意 {len(miss)} 项：{'、'.join(miss[:5])}")
    else:
        print("  全部餐品均已收录至少一条寓意（无「无解」项）")
    print("  用 --menu-luck <寓意> 可反查某寓意对应哪些餐品")
    print(BAR)


def _fmt_anchors(foods) -> None:
    print(BAR)
    print("  谐音锚点 × 真实菜单 逐条核验".center(66))
    print(BAR)
    print(f"  数据源：{len(foods)} 项可用餐品")
    print(SUB)
    names = {f.name for f in foods}
    miss = 0
    for k in THEME_ORDER:
        t = THEMES[k]
        print(f"  【{t.name}】{t.key}")
        for w in t.wishes:
            hit = sorted(n for n in names if w.anchor in n)
            if hit:
                print(f"     ✓ {w.anchor:<14} → {len(hit)} 项  例：{hit[0]}")
            else:
                miss += 1
                print(f"     ✗ {w.anchor:<14} → 真实菜单无匹配（如实报告，不编造）")
            print(f"       {w.gloss}")
            print(f"       [{w.kind}] {w.note}")
    print(SUB)
    print(f"  锚点总数 {len(all_wishes())}，未命中 {miss}。")
    if miss:
        print("  未命中的锚点不会被任何主题使用——词库与菜单不一致时应先修词库。")
    print(BAR)


def _fmt_one(foods, theme, top: int, args) -> None:
    r = compose_lucky(foods, theme, top_n=top,
                      min_size=args.min_size, max_size=args.max_size,
                      min_hits=args.min_hits)
    print(BAR)
    print(f"  【{theme.name} · {theme.key}】{theme.tagline}")
    print(f"  “{theme.voice}”")
    print(BAR)
    print(f"  预算 {theme.kcal:.0f} kcal ±{theme.tolerance:.0%}"
          f"   钠上限 {theme.max_sodium or round(theme.kcal * 1.8):.0f} mg"
          f"   甜品{'放开' if theme.allow_dessert else '关闭'}")
    print(f"  候选池 {r['pool_size']} / {r['total_size']} 项"
          f"（只含能命中谐音锚点的餐品）")

    hit = sum(1 for a in r["anchor_report"] if a["hit"])
    print(f"  谐音锚点 {hit} / {len(r['anchor_report'])} 命中")
    print(SUB)

    for msg in r.get("relaxed") or []:
        print(f"  ⚠ {msg}")
    if r.get("relaxed"):
        print(SUB)

    if not r["plans"]:
        print(f"  {r.get('diagnose') or '当前约束下无解。'}")
        print(SUB)
        print(DISCLAIMER)
        return

    for i, p in enumerate(r["plans"][:top], 1):
        flag = f"   ({p.relax_note})" if p.relax_note else ""
        print(f"  餐单 {i}   谐音命中 {p.luck_score} 个   "
              f"{p.plan.kcal:.0f} kcal   {p.plan.protein:.0f}g 蛋白{flag}")
        for f in sorted(p.plan.items, key=lambda x: (-x.kcal, x.name)):
            tag = []
            for w in theme.wishes:
                if w.anchor in f.name:
                    tag.append(w.anchor)
            mark = ("  ← " + " / ".join(tag)) if tag else ""
            print(f"     · {f.name:<32} [{f.category:<4}] "
                  f"{f.kcal:>5.0f} kcal  钠 {f.sodium:>5.0f} mg{mark}")
        print(f"     合计 {p.plan.kcal:.0f} kcal  蛋白 {p.plan.protein:.1f} g  "
              f"脂肪 {p.plan.fat:.1f} g  碳水 {p.plan.carb:.1f} g  "
              f"钠 {p.plan.sodium:.0f} mg")
        for g in p.glosses:
            print(f"       梗：{g}")
        if p.unmatched:
            print(f"       未命中：{'、'.join(p.unmatched)}"
                  f"（该梗在真实菜单里没有对应餐品，如实标注）")
        print(SUB)

    print(f"  {theme.blessing}")
    print(SUB)
    print("  下一步：以上为品名级餐单。productCode 需在确定门店后由")
    print("  query-meals 现查（营养表不含编码）。用 --order-help 看完整下单链路。")
    print(BAR)
    print(DISCLAIMER)


def _fmt_compare(foods, args) -> None:
    themes = list(iter_themes())
    v = compare_themes(foods, themes, top_n=args.top)
    print(BAR)
    print("  同一天 · 同菜单 · 8 个主题给出 8 种不同答案".center(66))
    print(BAR)
    print(f"  {'主题':<12}{'谐音':<6}{'餐单':<6}{'热量':<8}{'钠':<9}  推荐组合")
    print(SUB)
    for k in THEME_ORDER:
        d = v["detail"][k]
        if not d["plans"]:
            print(f"  {d['theme']:<12}{'无解':<6}")
            continue
        items = " + ".join(n[:15] for n in d["top_items"])
        print(f"  {d['theme']:<12}{d['top_hits']:<6}{d['plans']:<6}"
              f"{d['top_kcal']:<8.0f}{d['top_sodium']:<9.0f}  {items}")
    print(SUB)
    print(f"  主题总数        {v['themes_tested']}")
    print(f"  出餐单主题数    {v['themes_with_plans']}")
    print(f"  不同首选方案数  {v['distinct_first_plans']}")
    print(f"  差异化是否成立  {'是' if v['diverged'] else '否 ← 方案失效'}")
    print(BAR)
    print(DISCLAIMER)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="麦门幸运餐盘：用谐音寓意解出可下单的麦当劳幸运餐单")
    ap.add_argument("--theme", "-t", help="主题 key 或中文名，如 jackpot / 一夜暴富")
    ap.add_argument("--themes", action="store_true", help="列出全部幸运主题")
    ap.add_argument("--anchors", action="store_true",
                    help="逐条核验谐音锚点在真实菜单中的命中情况")
    ap.add_argument("--menu-luck", nargs="?", const="", default=None,
                    metavar="寓意",
                    help="餐品幸运清单：列出每道菜的寓意；"
                         "给参数则反查某寓意对应哪些餐品")
    ap.add_argument("--compare", action="store_true", help="对比全部主题")
    ap.add_argument("--order-help", action="store_true", help="打印下单链路指引")
    ap.add_argument("--top", type=int, default=3, help="展示前 N 个餐单")
    ap.add_argument("--min-size", type=int, default=2, help="最少件数")
    ap.add_argument("--max-size", type=int, default=4, help="最多件数")
    ap.add_argument("--min-hits", type=int, default=None, help="最少谐音命中数")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    ap.add_argument("--offline", help="离线数据路径，无需 Token")
    ap.add_argument("--probe-dump", help="落盘 MCP 原始响应（校准用）")
    ap.add_argument("--list-tools", action="store_true", help="MCP 自检")
    args = ap.parse_args()

    if args.themes:
        _fmt_themes()
        return
    if args.order_help:
        print(ORDER_HELP)
        return
    if args.list_tools:
        from mcp_client import StreamableHTTPClient, mask_secret
        try:
            tools = StreamableHTTPClient().list_tools()
        except Exception as exc:                  # noqa: BLE001
            print(mask_secret(str(exc)), file=sys.stderr)
            sys.exit(2)
        print(f"MCP 连通正常，共 {len(tools)} 个工具。")
        for t in tools:
            print("  -", t.get("name"))
        return

    foods = _load(args)

    if args.menu_luck is not None:
        _fmt_menu_luck(foods, args.menu_luck or None)
        return
    if args.anchors:
        _fmt_anchors(foods)
        return
    if args.compare:
        _fmt_compare(foods, args)
        return

    if args.theme:
        try:
            theme = get(args.theme)
        except KeyError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
        if args.json:
            r = compose_lucky(foods, theme, top_n=args.top,
                              min_size=args.min_size, max_size=args.max_size,
                              min_hits=args.min_hits)
            print(json.dumps({
                "theme": theme.as_dict(),
                "pool": {"usable": r["pool_size"], "total": r["total_size"]},
                "anchor_report": r["anchor_report"],
                "plans": [p.as_dict() for p in r["plans"]],
                "relaxed": r["relaxed"],
                "diagnose": r["diagnose"],
                "order_note": ("营养表不含 productCode；下单前需 query-meals 现查"),
                "disclaimer": DISCLAIMER,
            }, ensure_ascii=False, indent=2))
        else:
            _fmt_one(foods, theme, args.top, args)
        return

    print("未指定主题。试试：")
    print("  --theme 一夜暴富    （或 exam / lovestruck / interview / no-carb /"
          " heal / win-lottery / travel）")
    print("  --themes            列出全部主题")
    print("  --compare           对比全部主题")
    print("  --anchors           核验谐音锚点命中情况")
    print("  --menu-luck         查看餐品幸运清单（每道菜有什么寓意）")
    print()


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print(f"参数不合法：{exc}", file=sys.stderr)
        print("请用 --help 查看可用参数及其取值范围。", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n已中断。", file=sys.stderr)
        sys.exit(130)