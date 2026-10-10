"""通过 GitHub API 提交 issue。

认证：从系统凭据管理器读取 github.com 的 HTTPS 凭据（不打印、不落盘、
不写入任何文件）。若取不到则退出，不做任何降级猜测。

用法：
    python scripts/post_issue.py --title "标题" --body-file docs/xxx.md
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request

REPO = "imgww/mcd-lucky-plate"
API = f"https://api.github.com/repos/{REPO}/issues"


def get_cred() -> tuple[str, str] | None:
    """从凭据管理器取 github.com 凭据。返回 (user, token)，取不到返回 None。"""
    try:
        r = subprocess.run(
            ["git-credential-manager", "get"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    user = pwd = None
    for line in (r.stdout or "").splitlines():
        if line.startswith("username="):
            user = line.split("=", 1)[1].strip()
        elif line.startswith("password="):
            pwd = line.split("=", 1)[1].strip()
    if not pwd:
        return None
    return user or "", pwd


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--labels", default="")
    args = ap.parse_args()

    cred = get_cred()
    if not cred:
        print("未能从凭据管理器取得 GitHub 凭据，无法提交 issue。", file=sys.stderr)
        print("请配置 gh CLI 或设置 GITHUB_TOKEN 环境变量后重试。", file=sys.stderr)
        return 2
    user, token = cred

    from pathlib import Path
    body = Path(args.body_file).read_text(encoding="utf-8")

    payload = {
        "title": args.title,
        "body": body,
        "labels": [x.strip() for x in args.labels.split(",") if x.strip()],
    }
    req = urllib.request.Request(
        API, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "mcd-lucky-plate-publisher",
            "Content-Type": "application/json",
        })
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            d = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"提交失败：HTTP {e.code}", file=sys.stderr)
        print(e.read().decode("utf-8", "replace")[:400], file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"网络不可达：{e.reason}", file=sys.stderr)
        return 1

    print(f"已提交 issue #{d['number']}: {d['html_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())