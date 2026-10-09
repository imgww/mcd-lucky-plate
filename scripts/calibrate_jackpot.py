"""一次性校准探针：为 jackpot 主题找能在严格档解出的热量预算。

只服务开发期校准，不属于 Skill 运行时。结论回写进 lucky.py 的 provenance。
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "src")

from composer import Constraints          # noqa: E402
from lucky import THEMES                  # noqa: E402
from lucky_engine import _build_combos, _score, resolve_anchors  # noqa: E402
from nutrition import load_offline         # noqa: E402

foods = load_offline("samples/nutrition-foods.raw.json")
t = THEMES["jackpot"]
hits = resolve_anchors(foods, t)
combos = _build_combos(t, hits, 2, 4)
print("jackpot anchors hit:", len(hits), "combos:", len(combos))
print()

print("kcal   tol   NaScale minHits  solved  bestKcal  bestHits")
for kcal in (600, 620, 640, 660, 680, 700, 720, 740, 760, 780):
    found = None
    for tol in (0.18, 0.20, 0.24):
        for sc in (1.0, 1.25, 1.5):
            base = round(kcal * 1.8 * sc)
            for mh in (3, 2, 1):
                c = Constraints(target_kcal=kcal, tolerance=tol,
                                max_sodium=base, min_size=2, max_size=4,
                                max_per_category=1)
                ok = []
                for cb in combos:
                    s = _score(cb, t, c, mh)
                    if s is not None:
                        ok.append((s, cb))
                if ok:
                    ok.sort(key=lambda x: -x[0])
                    top = ok[0][1]
                    nh = len({w.anchor for w in t.wishes
                              if any(w.anchor in f.name for f in top)})
                    found = (tol, sc, mh, len(ok),
                             sum(f.kcal for f in top), nh)
                    break
            if found:
                break
        if found:
            break
    if found:
        print("%-6d %-5.2f %-7.2f %-8d %-7d %-9.0f %d" % (
            kcal, found[0], found[1], found[2], found[3],
            found[4], found[5]))
    else:
        print("%-6d %-5s %-7s %-8s %-7d" % (kcal, "-", "-", "-", 0))