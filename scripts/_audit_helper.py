"""审查辅助：只读检查 SKILL.md 的 description 长度、纪律项与引用拓扑。

审查阶段使用，不修改包体。
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
t = (ROOT / "SKILL.md").read_text(encoding="utf-8")

fm = t.split("---")[1]
m = re.search(r"description: (.+)", fm)
d = m.group(1) if m else ""
print("description 长度:", len(d), "字符（要求 20-1024）")
print("  含四要素检查:")
for key, kw in (("做什么", "餐单"), ("何时用", "适用于"),
                ("关键能力", "谐音"), ("触发短语", "这类请求")):
    print(f"    {key}: {'有' if kw in d else '缺'}")
print()

print("=== 纪律项扫描（占位/修改注释/历史 log）===")
bad_kw = ["TODO", "FIXME", "待补充", "占位符", "已调整", "已验证",
          "更新日志", "变更记录", "changelog", "版本历史", "XXX"]
found = False
for kw in bad_kw:
    hits = [i + 1 for i, l in enumerate(t.splitlines()) if kw in l]
    if hits:
        found = True
        print(f"  ⚠ 命中「{kw}」行 {hits}")
if not found:
    print("  无违规痕迹")

print()
print("=== 引用拓扑（SKILL.md 提及的文件）===")
refs = sorted(set(re.findall(r"`([a-zA-Z0-9_./-]+\.(?:md|py|json|html|csv))`", t)))
for r in refs:
    p = ROOT / r if not r.startswith(("src/", "scripts/", "tests/", "docs/",
                                      "references/", "samples/")) else ROOT / r
    p2 = ROOT / r
    mark = "OK " if p2.exists() else "!! 缺失"
    print(f"  {mark} {r}")
missing = [r for r in refs if not (ROOT / r).exists()]
print(f"\n引用总数 {len(refs)}，缺失 {len(missing)}")
if missing:
    print("缺失:", missing)