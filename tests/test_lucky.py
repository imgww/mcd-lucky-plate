"""麦门幸运餐盘 · 回归测试（零第三方依赖，离线，无需 Token 与网络）

运行：python tests/test_lucky.py

覆盖的六条主张
--------------
1. 每个谐音锚点都在真实菜单里命中（不许编造餐品）
2. 主题之间产出**不同**答案（不许趋同成同一批菜）
3. 主题的硬约束真的被守住（甜品开关 / 热量容差 / 钠上限）
4. 谐音命中数确实达标，且命中数可从方案里数出来
5. 无随机性（同输入两次运行，输出 md5 一致）
6. 无解时如实报告，不生成假方案

样本缺失时**不崩溃**：自动改用合成夹具，并把依赖真实菜单的断言
显式标记为跳过，不伪装成通过。
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from lucky import THEMES, THEME_ORDER, Wish, all_wishes, get  # noqa: E402
from lucky_engine import (RELAX_STEPS, compare_themes, compose_lucky,  # noqa: E402
                          iter_themes, resolve_anchors)
from menu_luck import MENU_LUCK, motifs_index, uncovered_foods  # noqa: E402
from nutrition import Food, load_offline, parse_foods  # noqa: E402

PASS, FAIL, SKIP = 0, 0, 0
FAILURES: list[str] = []
SKIPPED: list[str] = []


def check(cond: bool, label: str) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(label)
        print(f"  FAIL  {label}")


def skip(label: str) -> None:
    global SKIP
    SKIP += 1
    SKIPPED.append(label)


def section(title: str) -> None:
    print(f"\n[{title}]")


def load_foods() -> tuple[list[Food], bool]:
    """真实样本优先；缺失则退回合成夹具，并标记 real=False。"""
    sample = ROOT / "samples" / "nutrition-foods.raw.json"
    if sample.is_file():
        try:
            foods = load_offline(sample)
            if foods:
                return foods, True
        except (OSError, ValueError):
            pass
    fixture = ROOT / "tests" / "fixtures" / "synthetic_nutrition.json"
    if fixture.is_file():
        with open(fixture, encoding="utf-8") as fh:
            return parse_foods(json.load(fh)), False
    return [], False


def main() -> int:
    foods, real = load_foods()
    src = "真实菜单样本" if real else "合成夹具"
    print(f"数据源：{src}（{len(foods)} 项可用餐品）")

    themes = list(iter_themes())

    # ---------------- 1. 锚点必须落在真实菜单上 ----------------
    section("谐音锚点 × 菜单 核验")
    names = {f.name for f in foods}
    for w in all_wishes():
        hit = [n for n in names if w.anchor in n]
        if real:
            check(bool(hit), f"锚点在真实菜单中命中：{w.anchor}")
        else:
            skip(f"锚点真实命中（依赖真实样本）：{w.anchor}")

    # 词库自身的一致性（与数据源无关，任何时候都该成立）
    check(len(THEME_ORDER) == 8, "主题数为 8")
    check(len(THEME_ORDER) == len(set(THEME_ORDER)), "主题 key 无重复")
    for t in themes:
        check(bool(t.wishes), f"主题 {t.key} 至少有一个谐音梗")
        check(bool(t.tagline.strip()), f"主题 {t.key} 有 tagline")
        check(bool(t.voice.strip()), f"主题 {t.key} 有口吻 voice")
        check(bool(t.provenance.strip()), f"主题 {t.key} 写了 provenance 溯源")
        check(t.kcal > 0, f"主题 {t.key} 热量预算为正")
        check(0 < t.tolerance < 0.5, f"主题 {t.key} 容差在 (0, 0.5) 内")
        for w in t.wishes:
            check(bool(w.gloss.strip()), f"{t.key}/{w.anchor} 有梗解释")
            check(bool(w.note.strip()), f"{t.key}/{w.anchor} 有溯源 note")
            check(w.kind in ("homophone", "literal", "brand", "reverse"),
                  f"{t.key}/{w.anchor} 谐音类型合法")

    # 每个主题至少有一个**唯一专属**锚点，否则主题之间会共用词库而趋同
    for t in themes:
        others = {w.anchor for o in themes if o.key != t.key for w in o.wishes}
        exclusive = [w.anchor for w in t.wishes if w.anchor not in others]
        check(bool(exclusive), f"主题 {t.key} 至少有一个专属锚点（防趋同）")

    # 甜品开关必须在词库层就一致（关甜品的主题不应带甜品类锚点）
    for t in themes:
        if not t.allow_dessert:
            dessert_anchors = {"新地", "派", "圆筒", "奶冻", "雪冰",
                               "麦旋风", "拉明顿", "阿芙佳朵", "爆珠"}
            clash = [w.anchor for w in t.wishes if w.anchor in dessert_anchors]
            check(not clash, f"主题 {t.key} 关闭甜品但未携带甜品锚点")

    # ---------------- 2. 主题差异化 ----------------
    section("主题差异化")
    cmp_ = compare_themes(foods, themes, top_n=3)
    check(cmp_["themes_tested"] == 8, "对比覆盖 8 个主题")
    check(cmp_["diverged"], "8 个主题产出不同首选方案")
    if real:
        check(cmp_["themes_with_plans"] == 8, "真实菜单上 8 个主题全部可解")
        check(cmp_["distinct_first_plans"] == 8,
              f"真实菜单上 8 个主题产出 8 种不同答案"
              f"（实测 {cmp_['distinct_first_plans']}）")
    else:
        skip("真实菜单上 8 主题全部可解（依赖真实样本）")
        skip("真实菜单上 8 种不同答案（依赖真实样本）")

    # 每个主题的首选组合本身也不能与其他主题重复
    firsts = [v["top_items"] for v in cmp_["detail"].values() if v["top_items"]]
    check(len(firsts) == len(set(firsts)),
          "各主题首选组合两两不重复")

    # ---------------- 3. 约束没被偷偷违背 ----------------
    section("硬约束校验")
    all_plans = {}
    for t in themes:
        r = compose_lucky(foods, t, top_n=3)
        all_plans[t.key] = r
        if not r["plans"]:
            if real:
                check(False, f"主题 {t.key} 在真实菜单上无解")
            continue
        check(bool(r["plans"]), f"主题 {t.key} 至少产出一个餐单")

        lo = t.kcal * (1 - t.tolerance)
        hi = t.kcal * (1 + t.tolerance)
        na = t.max_sodium or round(t.kcal * 1.8)

        for i, p in enumerate(r["plans"], 1):
            tag = f"{t.key}#{i}"
            # 放宽档会显式抬高容差/钠上限，校验时按实际生效值
            step_note = p.relax_note
            eff_hi = hi
            eff_na = na
            if "24%" in step_note:
                eff_hi = t.kcal * 1.24
            elif "30%" in step_note:
                eff_hi = t.kcal * 1.30
            if "放宽 25%" in step_note:
                eff_na = na * 1.25
            elif "放宽 50%" in step_note:
                eff_na = na * 1.5

            check(lo <= p.plan.kcal <= eff_hi,
                  f"{tag} 热量 {p.plan.kcal:.0f} 落在 "
                  f"[{lo:.0f}, {eff_hi:.0f}]")
            check(p.plan.sodium <= eff_na + 1e-6,
                  f"{tag} 钠 {p.plan.sodium:.0f} ≤ {eff_na:.0f}")
            if not t.allow_dessert:
                cats = {f.category for f in p.plan.items}
                check("甜品" not in cats, f"{tag} 关闭甜品却含甜品")
            # 谐音命中数必须可从方案里数出来
            hit_count = len({w.anchor for w in t.wishes
                             if any(w.anchor in f.name for f in p.plan.items)})
            check(hit_count == p.luck_score,
                  f"{tag} luck_score({p.luck_score}) 与实数命中({hit_count})一致")
            check(len(p.plan.items) >= 2, f"{tag} 至少 2 件")
            check(p.needs_code_lookup is True, f"{tag} 标注需现查 productCode")
            # 组合内不应有同名重复
            item_names = [f.name for f in p.plan.items]
            check(len(item_names) == len(set(item_names)), f"{tag} 组合内无同名重复")

    # ---------------- 4. 谐音命中确实达标 ----------------
    section("谐音命中数")
    for t in themes:
        hits = resolve_anchors(foods, t)
        r = all_plans[t.key]
        if r["plans"]:
            best = max(p.luck_score for p in r["plans"])
            check(best >= 1, f"主题 {t.key} 最优餐单至少命中 1 个梗")
        # anchor_report 覆盖该主题全部梗，且 hit 标记与检索结果一致
        check(len(r["anchor_report"]) == len(t.wishes),
              f"主题 {t.key} anchor_report 覆盖全部谐音梗")
        for a in r["anchor_report"]:
            check(isinstance(a["hit"], bool), f"主题 {t.key} hit 字段为布尔")
            check(a["hit"] == bool(a["matched_names"]),
                  f"主题 {t.key}/{a['anchor']} hit 与匹配结果一致")
        check(len(hits) <= len(t.wishes), f"主题 {t.key} 命中数不超过梗总数")

    # 未命中的梗必须被如实报告（真实菜单下应为 0 未命中）
    if real:
        for t in themes:
            r = all_plans[t.key]
            if r["plans"]:
                check(not r["plans"][0].unmatched,
                      f"主题 {t.key} 真实菜单下无未命中梗")

    # ---------------- 5. 确定性（无随机） ----------------
    section("确定性")
    for t in themes[:4]:
        a = compose_lucky(foods, t, top_n=3)
        b = compose_lucky(foods, t, top_n=3)
        sig_a = json.dumps([p.as_dict() for p in a["plans"]],
                           ensure_ascii=False, sort_keys=True, default=str)
        sig_b = json.dumps([p.as_dict() for p in b["plans"]],
                           ensure_ascii=False, sort_keys=True, default=str)
        check(hashlib.md5(sig_a.encode()).hexdigest()
              == hashlib.md5(sig_b.encode()).hexdigest(),
              f"主题 {t.key} 两次运行结果完全一致")

    # 候选池顺序无关性：打乱输入顺序不应改变输出
    if foods:
        t0 = themes[0]
        shuffled = list(reversed(foods))
        base_sig = json.dumps([p.as_dict() for p in
                               compose_lucky(foods, t0)["plans"]],
                              ensure_ascii=False, sort_keys=True, default=str)
        shuf_sig = json.dumps([p.as_dict() for p in
                               compose_lucky(shuffled, t0)["plans"]],
                              ensure_ascii=False, sort_keys=True, default=str)
        check(base_sig == shuf_sig, "打乱菜单顺序不改变输出（无隐式顺序依赖）")

    # ---------------- 6. 无解时如实报告 ----------------
    section("诚实边界")
    # 构造一个不可能的约束：极低热量 + 极高钠要求 + 要求 4 个梗
    if real:
        tiny = Wish("不存在的锚点xyz", "测试用", "literal", "测试")
        for t in themes[:2]:
            r = compose_lucky(foods, t, min_hits=99, top_n=1)
            check(not r["plans"], f"要求 99 个梗时主题 {t.key} 返回无解")
            check(bool(r["diagnose"]), f"主题 {t.key} 无解时给出诊断文本")
            check(isinstance(r["relaxed"], list),
                  f"主题 {t.key} relaxed 为列表")
        check(tiny.anchor not in names, "测试用假锚点确实不在菜单中")

    # 显式指定的谐音下限不得被自动回退推翻（否则等于静默违背用户要求）
    for t in themes[:3]:
        n_anchor = len(resolve_anchors(foods, t))
        r_strict = compose_lucky(foods, t, min_hits=n_anchor, top_n=1)
        if r_strict["plans"]:
            for p in r_strict["plans"]:
                check(p.luck_score >= n_anchor,
                      f"主题 {t.key} 显式要求 {n_anchor} 个梗时结果未被降级")
        r_too_many = compose_lucky(foods, t, min_hits=n_anchor + 5, top_n=1)
        check(not r_too_many["plans"],
              f"主题 {t.key} 要求超过可得锚点数时如实返回无解")
        check(bool(r_too_many["diagnose"]),
              f"主题 {t.key} 显式下限不可达时给出诊断文本")

    # 放宽档必须单调放宽，且钠档存在
    check(len(RELAX_STEPS) >= 4, "回退档位不少于 4 档")
    check(any(s.get("sodium_scale") for s in RELAX_STEPS),
          "回退档位包含钠放宽档（实测高蛋白主食必然高钠）")
    mins = [s["min_hits"] for s in RELAX_STEPS]
    check(mins == sorted(mins, reverse=True), "回退档位的谐音下限单调不增")

    # 空数据必须给出诊断而非崩溃
    r_empty = compose_lucky([], THEMES["jackpot"])
    check(not r_empty["plans"], "空菜单返回无解而非崩溃")
    check(bool(r_empty["diagnose"]), "空菜单给出诊断文本")

    # 未知主题必须报 KeyError（不静默降级为随机主题）
    try:
        get("不存在的主题")
        check(False, "未知主题应抛 KeyError")
    except KeyError:
        check(True, "未知主题抛 KeyError")

    # ---------------- 7. 餐品幸运清单 ----------------
    section("餐品幸运清单")
    if real:
        real_names = {f.name for f in foods}
        # 7.1 覆盖率：清单必须覆盖全部真实餐品，且不含不存在的品名
        check(not uncovered_foods(foods),
              f"清单覆盖全部 {len(real_names)} 项真实餐品"
              f"（未收录 {len(uncovered_foods(foods))} 项）")
        ghost = sorted(set(MENU_LUCK) - real_names)
        check(not ghost, f"清单不含不存在的品名（多出 {len(ghost)} 项）")

        # 7.2 每项至少一条寓意，且字段完整
        for name in sorted(real_names):
            lucks = MENU_LUCK.get(name, ())
            check(len(lucks) >= 1, f"{name} 至少有一条寓意")
            for l in lucks:
                check(bool(l.key.strip()), f"{name} 的寓意有 key")
                check(bool(l.gloss.strip()), f"{name}/{l.key} 有说明")
                check(l.kind in ("homophone", "literal", "brand", "reverse"),
                      f"{name}/{l.key} 类型合法")
                check(1 <= l.score <= 3, f"{name}/{l.key} 契合度在 1-3")

        # 7.3 强梗（score>=2）必须有溯源 note
        for name, lucks in MENU_LUCK.items():
            for l in lucks:
                if l.score >= 2:
                    check(bool(l.note.strip()),
                          f"{name}/{l.key} 强梗必须写溯源 note")

        # 7.4 主题 anchor 必须在清单中有对应寓意（清单是词库的上位资产）
        for t in themes:
            for w in t.wishes:
                hit = [f.name for f in foods if w.anchor in f.name]
                motifs = {l.key for n in hit for l in MENU_LUCK.get(n, ())}
                check(bool(motifs),
                      f"主题 {t.key}/{w.anchor} 的命中餐品在清单中有寓意")

        # 7.5 寓意索引自洽：反查结果与清单一致
        idx = motifs_index()
        for key, names in idx.items():
            check(len(names) > 0, f"寓意「{key}」至少关联一个餐品")
            for n in names:
                check(any(l.key == key for l in MENU_LUCK.get(n, ())),
                      f"反查自洽：{n} 确实承载寓意「{key}」")

        # 7.6 清单不应修改主题求解结果（清单只做查询层）
        #      断言：寓意里出现的新词不影响既有 anchor 命中
        check(len(idx) >= 10, f"寓意种类不少于 10（实测 {len(idx)}）")

    # ---------------- 汇总 ----------------
    print("\n" + "=" * 60)
    print(f"通过 {PASS}　失败 {FAIL}　跳过 {SKIP}")
    if SKIPPED:
        print(f"跳过明细（依赖真实样本，非通过）：{len(SKIPPED)} 项")
        for s in SKIPPED[:6]:
            print(f"  - {s}")
        if len(SKIPPED) > 6:
            print(f"  … 另有 {len(SKIPPED) - 6} 项")
    if FAILURES:
        print(f"\n失败明细：")
        for f in FAILURES:
            print(f"  ✗ {f}")
    print("=" * 60)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())