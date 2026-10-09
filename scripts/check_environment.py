"""环境就绪检查：判定本 Skill 当前能否执行，以及能执行到哪一步。

只读，不安装、不登录、不授权、不修改配置，不输出任何凭据值。

用法：
    python scripts/check_environment.py           # 人类可读报告
    python scripts/check_environment.py --json    # 机器可读

退出码：
    0 ready / partial   可执行（partial 表示功能受限）
    1 needs_setup       缺必需配置
    2 unavailable       认证或服务不可用
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "samples" / "nutrition-foods.raw.json"

TOKEN_DOC = "https://open.mcd.cn/mcp → 登录 → 控制台 → 激活 → 同意服务协议 → 复制"
MIN_PY = (3, 10)
MCP_URL = os.environ.get("MCD_MCP_URL", "https://mcp.mcd.cn").rstrip("/")


def _py_ok() -> tuple[bool, str]:
    if sys.version_info < MIN_PY:
        return False, (f"Python {sys.version_info.major}.{sys.version_info.minor} "
                       f"低于要求的 {MIN_PY[0]}.{MIN_PY[1]}；"
                       f"源码使用 `X | None` 注解，需改写为 Optional[X]")
    return True, (f"Python {sys.version_info.major}.{sys.version_info.minor}."
                  f"{sys.version_info.micro} OK")


def _sample_state() -> tuple[bool, str]:
    if not SAMPLE.exists():
        return False, "samples/nutrition-foods.raw.json 不存在"
    size = SAMPLE.stat().st_size
    if size < 1000:
        return False, f"样本文件过小（{size} 字节），可能未完整拉取"
    return True, f"样本已就绪（{size:,} 字节），离线模式可用"


def _token_state() -> tuple[bool, str, bool]:
    """返回 (是否有 token, 描述, 是否可能是占位符)。不回显 token 内容。"""
    tok = os.environ.get("MCD_MCP_TOKEN", "").strip()
    if not tok:
        return False, "环境变量 MCD_MCP_TOKEN 未设置", False
    if len(tok) < 16:
        return False, f"MCD_MCP_TOKEN 长度仅 {len(tok)}，疑似无效", True
    placeholder = any(m in tok.upper() for m in
                      ("YOUR_", "TOKEN_HERE", "PLACEHOLDER", "XXXX", "<"))
    return True, f"MCD_MCP_TOKEN 已设置（长度 {len(tok)}，不回显内容）", placeholder


def _probe_network() -> tuple[bool, str]:
    """TCP 连通性探测。只验证端口可达，不发业务请求、不带凭据。"""
    try:
        with urllib.request.urlopen(MCP_URL, timeout=8):
            return True, f"{MCP_URL} 可达"
    except urllib.error.HTTPError as exc:
        # 有 HTTP 响应说明服务在线，只是这个路径不接受 GET
        return True, f"{MCP_URL} 可达（HTTP {exc.code}，正常，服务只接受 POST）"
    except urllib.error.URLError as exc:
        return False, f"{MCP_URL} 不可达：{exc.reason}"
    except Exception as exc:                      # noqa: BLE001
        return False, f"{MCP_URL} 探测异常：{exc}"


def _anchor_state() -> tuple[bool, str]:
    """谐音锚点自检：词库与真实菜单是否仍然一致。

    这是本 Skill 特有的检查项——菜单更新后锚点可能失效，
    而失效的锚点会静默削弱主题效果，因此必须在环境层就报出来。
    """
    if not SAMPLE.exists():
        return False, "无样本，无法核验锚点（不影响离线以外的流程）"
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from lucky import all_wishes
        from nutrition import load_offline
        foods = load_offline(SAMPLE)
        names = {f.name for f in foods}
        miss = [w.anchor for w in all_wishes()
                if not any(w.anchor in n for n in names)]
        if miss:
            return False, (f"有 {len(miss)} 个谐音锚点在当前菜单无匹配："
                           f"{'、'.join(miss[:5])}"
                           f"{'…' if len(miss) > 5 else ''}"
                           f"——请在 src/lucky.py 修正为真实在售品名")
        return True, f"谐音锚点全部命中（{len(all_wishes())} 条 / {len(foods)} 项餐品）"
    except Exception as exc:                      # noqa: BLE001
        return False, f"锚点核验失败：{exc}"


def main() -> int:
    ap = argparse.ArgumentParser(description="麦门幸运餐盘 · 环境就绪检查")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    args = ap.parse_args()

    py_ok, py_msg = _py_ok()
    sample_ok, sample_msg = _sample_state()
    token_ok, token_msg, placeholder = _token_state()
    anchor_ok, anchor_msg = _anchor_state()

    if not args.json:
        print("═" * 60)
        print("  麦门幸运餐盘 · 环境就绪检查")
        print("═" * 60)
        for mark, msg in (("✓" if py_ok else "✗", py_msg),
                          ("✓" if sample_ok else "✗", sample_msg),
                          ("·", token_msg),
                          ("✓" if anchor_ok else "✗", anchor_msg)):
            print(f"  {mark} {msg}")
        print("─" * 60)

    # ---- 状态判定 ----
    if not py_ok:
        status, why = "unavailable", f"Python 版本不满足最低要求：{py_msg}"
    elif not sample_ok and not token_ok:
        status, why = ("needs_setup",
                       "既无 MCD_MCP_TOKEN 也无离线样本，两条数据通路都不可用")
    elif not sample_ok:
        status, why = ("partial",
                       "离线样本缺失，但已配置 Token，可走联网模式")
    elif not token_ok:
        status, why = ("partial",
                       f"未配置 MCD_MCP_TOKEN，离线模式完全可用，"
                       f"仅联网取数不可用（配置方式：{TOKEN_DOC}）")
    else:
        net_ok, net_msg = _probe_network()
        if not net_ok:
            status, why = ("unavailable",
                           f"已配置 Token 但服务不可达：{net_msg}。"
                           f"可先跑离线模式："
                           f"python src/lucky_plate.py --theme exam "
                           f"--offline samples/nutrition-foods.raw.json")
        elif placeholder:
            status, why = ("unavailable",
                           f"MCD_MCP_TOKEN 疑似占位符而非真实 Token（{token_msg}）")
        else:
            status, why = "ready", "Python、样本、Token 与网络均已就绪"

    if not args.json:
        print(f"  状态：{status}")
        print(f"  说明：{why}")
        print("═" * 60)

    if args.json:
        print(json.dumps({
            "status": status, "reason": why,
            "checks": {
                "python": {"ok": py_ok, "detail": py_msg},
                "sample": {"ok": sample_ok, "detail": sample_msg},
                "token": {"ok": token_ok, "detail": token_msg,
                          "placeholder": placeholder},
                "anchors": {"ok": anchor_ok, "detail": anchor_msg},
            },
        }, ensure_ascii=False, indent=2))

    return {"ready": 0, "partial": 0, "needs_setup": 1, "unavailable": 2}[status]


if __name__ == "__main__":
    sys.exit(main())