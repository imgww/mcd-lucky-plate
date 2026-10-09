"""一次性校准探针：为 travel 主题找一个能让「牛气满满」（牛气冲天梗）
进入首选餐单的热量预算。

开发期使用，结论回写进 lucky.py 的 provenance。不属于 Skill 运行时。

背景：travel 主题原用「牛」anchor，实测会命中 6 款牛堡；而牛堡钠负荷
121-205mg/100kcal，与本主题 1296mg 钠上限存在结构性冲突。收窄为「牛气」
后只剩牛气满满（495kcal/钠 764），但 495 低于 720±15% 窗口下沿 612，
需搭配低热量项才能入局。本脚本扫描预算，找回既含「牛气冲天」梗、
又不触发放宽档的取值。
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "src")

from composer import Constraints              # noqa: E402
from lucky import THEMES                       # noqa: E402
from lucky_engine import _build_combos, _score, resolve_anchors  # noqa: E402
from nutrition import load_offline             # noqa: E402

foods = load_offline("samples/nutrition-foods.raw.json")
t = THEMES["travel"]
hits = resolve_anchors(foods, t)
combos = _build_combos(t, hits, 2, 4)
print(f"travel 候选组合 {len(combos)} 个（锚点命中 {len(hits)} 个）\n")

print("kcal   Na上限  strict3  含牛气方案  首选是否含牛气  首选组合")
for kcal in (640, 660, 680, 700, 720, 740):
    na_cap = round(kcal * 1.8)
    c = Constraints(target_kcal=kcal, tolerance=0.15, max_sodium=na_cap,
                    min_size=2, max_size=4, max_per_category=1)
    scored = []
    for cb in combos:
        s = _score(cb, t, c, 3)          # 严格档：要求 3 个梗
        if s is not None:
            hh = len({w.anchor for w in t.wishes
                      if any(w.anchor in f.name for f in cb)})
            scored.append((s, hh, cb))
    scored.sort(key=lambda x: (-x[0], -x[1],
                              "|".join(sorted(f.name for f in x[2]))))
    with_ox = [x for x in scored if any("牛气" in f.name for f in x[2])]
    top_has = bool(scored and any("牛气" in f.name for f in scored[0][2]))
    top = (" + ".join(f.name for f in scored[0][2])[:44] if scored else "-")
    print("%-6d %-7d %-9s %-12s %-17s %s" % (
        kcal, na_cap, len(scored), len(with_ox),
        "是" if top_has else "否", top))