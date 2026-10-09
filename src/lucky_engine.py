"""幸运餐盘引擎：把「幸运主题」翻译成一餐可下单的麦当劳组合。

三段式流水线（全确定性，无随机数）
--------------------------------
1. **锚点检索**（`resolve_anchors`）
   拿主题的每个 anchor 去真实菜单里做 `anchor in name` 精确子串匹配。
   命不中就是命不中——不退回模糊匹配、不编造餐品名。
   输出 `AnchorHit(anchor, foods)`，是后续一切的数据基础。

2. **谐音配平**（`compose_lucky`）
   在「至少命中 N 个 anchor」的硬约束下穷举组合。主题差异作用在四处：
   热量预算 / 容差 / 钠上限 / 甜品开关与权重（见 `lucky.Theme`）。
   打分 = 谐音命中 + 热量贴合 + 蛋白达成 + 钠控制 + 品类多样。

3. **可下单性标注**（`annotate_orderable`）
   关键诚实边界：`list-nutrition-foods` **不返回 productCode**，
   productCode 只能由 `query-meals`（需 storeCode）取得。
   因此本引擎只产出**品名级**方案，并显式标记每道菜是否需要
   在下单前做一次「名称 → productCode」映射，绝不假装已拿到编码。

主题差异作用在何处（缺一层就会趋同）
------------------------------------
| # | 作用点 | 缺了会怎样 |
|---|--------|-----------|
| 1 | 锚点集合 | 所有主题都推同一批「万金油」餐品 |
| 2 | 热量预算/容差 | 主题间热量与钠完全一致，只有文案不同 |
| 3 | 甜品开关与权重 | 「轻装上阵」会拿到一份甜品餐，叙事崩塌 |
| 4 | 命中数下限 | 强约束主题（面试）被稀释成随便凑一顿 |

诚实边界
--------
* **命中数可能达不到下限**：此时按 `RELAX_STEPS` 逐级下调下限，
  并把「放宽到第几档、当前主题至少能命中几个梗」显式打印。
* **营养表不含编码**：方案到得了「点得着」这一步的前提是门店在售，
  编码需 `query-meals` 现查。本引擎不猜编码。
* **不承诺运势**：所有吉祥话是文案与谐音玩法，不是效果保证。
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Sequence

from composer import Constraints, Plan, compose
from lucky import Theme, THEMES
from nutrition import Food

# 打分权重：谐音命中优先（这是本 Skill 的主张），营养为约束保障
W_LUCK = 0.46
W_KCAL_FIT = 0.24
W_PROTEIN = 0.14
W_SODIUM = 0.10
W_VARIETY = 0.06

# 每个 100 kcal 期望蛋白克数（与 composer 同口径，保证跨 Skill 数值一致）
PROTEIN_PER_100KCAL = 3.2
# 钠满意线：低于此值得满分
SODIUM_COMFORT_PER_100KCAL = 260.0

# 谐音命中数不足时的逐级回退：先降下限，再放宽热量容差，最后放钠上限。
#
# 钠这一档不是可有可无的补丁：实测「一夜暴富」主题的候选池全是高蛋白主食，
# 单品钠 728-1373mg，而按 260mg/100kcal 推导的上限只有 1368mg——
# 两件主食必然超钠。所以钠放宽是**求解真实菜单的必要档位**，不是为了让输出好看。
RELAX_STEPS: tuple[dict, ...] = (
    {"min_hits": 3, "kcal_tolerance": None, "sodium_scale": None, "note": "谐音下限 3 个"},
    {"min_hits": 2, "kcal_tolerance": None, "sodium_scale": None, "note": "谐音下限 2 个"},
    {"min_hits": 1, "kcal_tolerance": None, "sodium_scale": None, "note": "谐音下限 1 个"},
    {"min_hits": 1, "kcal_tolerance": 0.24, "sodium_scale": None,
     "note": "谐音下限 1 个 + 热量容差放宽至 24%"},
    {"min_hits": 1, "kcal_tolerance": 0.24, "sodium_scale": 1.25,
     "note": "谐音下限 1 个 + 热量容差 24% + 钠上限放宽 25%"},
    {"min_hits": 1, "kcal_tolerance": 0.30, "sodium_scale": 1.5,
     "note": "谐音下限 1 个 + 热量容差 30% + 钠上限放宽 50%"},
)

# 下单时可选项的品类（非必选，仅用于标注建议）
DRINK_CATS = ("饮品",)
DESSERT_CAT = "甜品"


@dataclass
class AnchorHit:
    """一个 anchor 在真实菜单里的命中结果。"""

    anchor: str
    foods: tuple[Food, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.foods)


@dataclass
class LuckyPlan:
    """一份幸运餐单：组合 + 命中了哪些梗 + 可下单性标注。"""

    theme: Theme
    plan: Plan
    hits: tuple[str, ...]            # 命中的 anchor 列表（去重、保序）
    glosses: tuple[str, ...]        # 对应的谐音解释
    unmatched: tuple[str, ...]      # 该主题里没命中的 anchor
    needs_code_lookup: bool = True   # 恒为 True：营养表无 productCode
    relax_note: str = ""             # 若发生过放宽，写明放宽了什么

    @property
    def luck_score(self) -> float:
        return len(set(self.hits))

    def as_dict(self) -> dict:
        return {
            "theme": {"key": self.theme.key, "name": self.theme.name,
                      "tagline": self.theme.tagline},
            "items": [
                {"name": f.name, "category": f.category, "kcal": f.kcal,
                 "protein": f.protein, "sodium": f.sodium,
                 "hits": [a for a in self.hits if a in f.name]}
                for f in self.plan.items
            ],
            "totals": {"kcal": round(self.plan.kcal, 1),
                       "protein": round(self.plan.protein, 1),
                       "fat": round(self.plan.fat, 1),
                       "carb": round(self.plan.carb, 1),
                       "sodium": round(self.plan.sodium, 1),
                       "calcium": round(self.plan.calcium, 1)},
            "hits": list(self.hits),
            "glosses": list(self.glosses),
            "unmatched_anchors": list(self.unmatched),
            "luck_score": self.luck_score,
            "needs_code_lookup": self.needs_code_lookup,
            "relax_note": self.relax_note,
            "blessing": self.theme.blessing,
        }


def resolve_anchors(foods: Sequence[Food], theme: Theme) -> tuple[AnchorHit, ...]:
    """按 anchor 精确子串匹配真实菜单。

    命不中的 anchor 直接不产出 AnchorHit——上层据此告知用户
    「这个梗在真实菜单里没有对应餐品」，而不是拿别的菜凑数。
    """
    hits: list[AnchorHit] = []
    for w in theme.wishes:
        matched = tuple(
            f for f in foods if w.anchor in f.name
        )
        if matched:
            hits.append(AnchorHit(anchor=w.anchor, foods=matched))
    return tuple(hits)


def _hit_foods(hits: Sequence[AnchorHit]) -> list[Food]:
    """把所有命中 anchor 的餐品汇成候选池（同名去重）。"""
    seen: dict[str, Food] = {}
    for h in hits:
        for f in h.foods:
            seen.setdefault(f.name, f)
    return [seen[k] for k in sorted(seen)]


def _anchor_of(food: Food, theme: Theme) -> tuple[str, ...]:
    return tuple(w.anchor for w in theme.wishes if w.anchor in food.name)


def _hits_of(combo: Sequence[Food], theme: Theme) -> tuple[str, ...]:
    """该组合命中的 anchor 集合（保序去重）。"""
    out: list[str] = []
    for w in theme.wishes:
        if any(w.anchor in f.name for f in combo):
            if w.anchor not in out:
                out.append(w.anchor)
    return tuple(out)


def _score(combo: tuple[Food, ...], theme: Theme, c: Constraints,
           min_hits: int) -> float | None:
    """主题感知的打分。返回 None 表示违反硬约束。"""
    kcal = sum(f.kcal for f in combo)
    if kcal <= 0:
        return None
    sodium = sum(f.sodium for f in combo)
    if sodium > c.max_sodium:
        return None
    dev = abs(kcal - theme.kcal) / theme.kcal
    tol = c.tolerance
    if dev > tol:
        return None

    hits = _hits_of(combo, theme)
    if len(hits) < min_hits:
        return None

    # 主题的甜品开关：关闭时任何甜品都不许进方案
    if not theme.allow_dessert and any(f.category == DESSERT_CAT for f in combo):
        return None

    s_luck = len(hits) / max(1, len(theme.wishes))

    s_kcal = 1.0 - dev / tol
    protein_target = theme.kcal / 100.0 * PROTEIN_PER_100KCAL
    protein = sum(f.protein for f in combo)
    s_protein = min(1.0, protein / protein_target) if protein_target else 1.0
    comfort = theme.kcal / 100.0 * SODIUM_COMFORT_PER_100KCAL
    s_sodium = min(1.0, comfort / sodium) if sodium > 0 else 1.0
    cats = {f.category for f in combo}
    s_variety = len(cats) / len(combo)

    # 甜品权重：主题越重视甜品，甜品入局加分越多（仍受 allow_dessert 硬开关）
    dessert_count = sum(1 for f in combo if f.category == DESSERT_CAT)
    s_dessert = (dessert_count / max(1, len(combo))) * theme.dessert_bias * 2.0

    total = (W_LUCK * s_luck + W_KCAL_FIT * s_kcal + W_PROTEIN * s_protein
             + W_SODIUM * s_sodium + W_VARIETY * s_variety + s_dessert * 0.08)
    return total


def _build_combos(theme: Theme, hits: Sequence[AnchorHit],
                  min_size: int, max_size: int) -> list[tuple[Food, ...]]:
    """穷举候选池的组合。

    候选池只含「至少命中一个 anchor」的餐品，因此池子比全菜单小得多，
    组合枚举规模可控。品类内先按热量与钠排序后截断，保证覆盖主食品类。
    """
    pool = _hit_foods(hits)
    if not pool:
        return []
    # 每个品类保留若干代表（优先低钠、高蛋白密度），避免大品类淹没解空间
    by_cat: dict[str, list[Food]] = {}
    for f in pool:
        by_cat.setdefault(f.category, []).append(f)
    kept: list[Food] = []
    for cat in sorted(by_cat):
        ranked = sorted(by_cat[cat], key=lambda f: (-f.macro_pdr(), f.sodium_load(), f.name))
        kept.extend(ranked[:6])
    return list(itertools.combinations(kept, max_size))


def compose_lucky(foods: Sequence[Food], theme: Theme, *,
                  top_n: int = 3, min_size: int = 2, max_size: int = 4,
                  min_hits: int | None = None) -> dict:
    """主入口：返回 {plans, relaxed, anchor_report, pool_size, total_size}。

    约束达不到时按 `RELAX_STEPS` 逐级放宽，并把放宽事实写进 `relaxed`。
    """
    hits = resolve_anchors(foods, theme)
    matched_anchors = {h.anchor for h in hits}
    unmatched = tuple(w.anchor for w in theme.wishes if w.anchor not in matched_anchors)

    anchor_report = [
        {"anchor": w.anchor, "gloss": w.gloss, "kind": w.kind,
         "hit": w.anchor in matched_anchors,
         "matched_names": list(next((h.names for h in hits
                                     if h.anchor == w.anchor), ())),
         "note": w.note}
        for w in theme.wishes
    ]

    if not hits:
        return {"plans": [], "relaxed": [],
                "anchor_report": anchor_report,
                "pool_size": 0, "total_size": len(foods),
                "diagnose": f"主题「{theme.name}」的全部 anchor 在当前菜单中均无匹配餐品，"
                            f"无法配出带梗的餐单。可换一个主题，或用 --kcal/--top 调整。",
                "theme": theme}

    want = min_hits if min_hits is not None else min(3, len(hits))

    # 用户显式指定的谐音下限是**硬约束**，不参与自动放宽。
    # 否则「我要 99 个梗」会被回退逻辑一路降到 1 个，等于悄悄推翻用户的要求。
    explicit_floor = min_hits is not None
    if explicit_floor and min_hits > len(hits):
        return {"plans": [], "relaxed": [],
                "anchor_report": anchor_report,
                "pool_size": len(_hit_foods(hits)), "total_size": len(foods),
                "diagnose": (
                    f"主题「{theme.name}」在当前菜单只命中 {len(hits)} 个谐音锚点，"
                    f"少于你要求的 {min_hits} 个，因此无解。"
                    f"可把 --min-hits 调到 {len(hits)} 或更低，"
                    f"或换一个谐音锚点更多的主题。"
                ),
                "theme": theme}

    relaxed: list[str] = []
    combos = _build_combos(theme, hits, min_size, max_size)

    for step_idx, step in enumerate(RELAX_STEPS):
        # 回退档位可以把下限往下走，但**不得低于用户显式指定的值**
        step_hits = min(want, step["min_hits"])
        if explicit_floor and step_hits < min_hits:
            continue
        tol = step["kcal_tolerance"] or theme.tolerance
        base_sodium = theme.max_sodium or round(theme.kcal * 1.8, 0)
        scale = step["sodium_scale"]
        max_sodium = round(base_sodium * scale, 0) if scale else base_sodium
        c = Constraints(target_kcal=theme.kcal, tolerance=tol,
                        max_sodium=max_sodium,
                        min_size=min_size, max_size=max_size,
                        max_per_category=1, top_n=top_n)
        scored: list[tuple[float, str, tuple[Food, ...], tuple[str, ...]]] = []
        for combo in combos:
            s = _score(combo, theme, c, step_hits)
            if s is None:
                continue
            scored.append((s, "|".join(sorted(f.name for f in combo)), combo,
                           _hits_of(combo, theme)))
        if scored:
            scored.sort(key=lambda x: (-x[0], -len(x[3]), x[1]))
            plans: list[LuckyPlan] = []
            seen: set[str] = set()
            for s, key, combo, hh in scored:
                if key in seen:
                    continue
                seen.add(key)
                kcal = sum(f.kcal for f in combo)
                dev = abs(kcal - theme.kcal) / theme.kcal
                base = Plan(items=combo, kcal=kcal,
                            protein=sum(f.protein for f in combo),
                            fat=sum(f.fat for f in combo),
                            carb=sum(f.carb for f in combo),
                            sodium=sum(f.sodium for f in combo),
                            calcium=sum(f.calcium for f in combo),
                            score=s,
                            kcal_fit_pct=1.0 - dev,
                            protein_target=theme.kcal / 100.0 * PROTEIN_PER_100KCAL,
                            sodium_limit=c.max_sodium)
                glosses = tuple(w.gloss for w in theme.wishes if w.anchor in hh)
                plans.append(LuckyPlan(
                    theme=theme, plan=base, hits=hh, glosses=glosses,
                    unmatched=unmatched,
                    relax_note="" if step_idx == 0 else f"已放宽：{step['note']}",
                ))
                if len(plans) >= top_n:
                    break
            note = "" if step_idx == 0 else f"已放宽：{step['note']}"
            return {"plans": plans, "relaxed": relaxed,
                    "anchor_report": anchor_report,
                    "pool_size": len(_hit_foods(hits)), "total_size": len(foods),
                    "diagnose": "", "theme": theme}

        relaxed.append(
            f"档位 {step_idx + 1}（{step['note']}）下无解，已继续放宽。"
        )

    max_reachable = min(want, len(hits))
    return {"plans": [], "relaxed": relaxed,
            "anchor_report": anchor_report,
            "pool_size": len(_hit_foods(hits)), "total_size": len(foods),
            "diagnose": (
                f"主题「{theme.name}」在当前约束下无解："
                f"该主题共命中 {len(hits)} 个 anchor，"
                f"但要求至少命中 {want} 个且热量需落在 "
                f"{theme.kcal:.0f}±{theme.tolerance:.0%} kcal 内，"
                f"两者在真实菜单上无法同时满足。"
                f"可试：放宽 --top、放宽 --max-sodium、"
                f"或改用热量预算更接近的主题（如 --theme travel）。"
            ),
            "theme": theme}


def compare_themes(foods: Sequence[Food], themes: Sequence[Theme] | None = None,
                   **kw) -> dict:
    """同一天、同预算下不同主题给出不同答案（核心证明）。"""
    from lucky import THEME_ORDER
    themes = themes or [THEMES[k] for k in THEME_ORDER]
    detail: dict[str, dict] = {}
    for t in themes:
        r = compose_lucky(foods, t, **kw)
        plans = r["plans"]
        detail[t.key] = {
            "theme": t.name,
            "plans": len(plans),
            "top_hits": plans[0].luck_score if plans else 0,
            "top_kcal": plans[0].plan.kcal if plans else 0.0,
            "top_sodium": plans[0].plan.sodium if plans else 0.0,
            "top_items": tuple(f.name for f in plans[0].plan.items) if plans else (),
            "pool_size": r["pool_size"],
        }
    firsts = {v["top_items"] for v in detail.values() if v["top_items"]}
    return {
        "themes_tested": len(themes),
        "themes_with_plans": sum(1 for v in detail.values() if v["plans"]),
        "distinct_first_plans": len(firsts),
        "diverged": len(firsts) >= 2,
        "detail": detail,
    }


def diagnose(foods: Sequence[Food], theme: Theme, **kw) -> str:
    """无解时的人话解释。"""
    r = compose_lucky(foods, theme, **kw)
    return r.get("diagnose") or "有解。"


def iter_themes() -> tuple[Theme, ...]:
    from lucky import THEME_ORDER
    return tuple(THEMES[k] for k in THEME_ORDER)