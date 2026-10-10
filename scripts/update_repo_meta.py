"""通过 GitHub API 更新仓库 description / topics。

认证：从系统凭据管理器读取 github.com 的 HTTPS 凭据，
不打印、不落盘、不写入任何文件。

用法：
    python scripts/update_repo_meta.py --description "..." --topics a,b,c
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request

REPO = "imgww/mcd-lucky-plate"
API = f"https://api.github.com/repos/{REPO}"


def get_cred() -> tuple[str, str] | None:
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


def req(method: str, url: str, token: str, payload: dict | None = None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    r = urllib.request.Request(
        url, data=data, method=method,
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": "mcd-lucky-plate-publisher",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--description")
    ap.add_argument("--topics", default="")
    ap.add_argument("--homepage")
    args = ap.parse_args()

    cred = get_cred()
    if not cred:
        print("未取得 GitHub 凭据", file=sys.stderr)
        return 2
    _, token = cred

    payload: dict = {}
    if args.description:
        payload["description"] = args.description
    if args.homepage:
        payload["homepage"] = args.homepage
    if payload:
        try:
            d = req("PATCH", API, token, payload)
            print("description:", d.get("description"))
            print("homepage:", d.get("homepage"))
        except urllib.error.HTTPError as e:
            print(f"更新失败 HTTP {e.code}", file=sys.stderr)
            print(e.read().decode("utf-8", "replace")[:300], file=sys.stderr)
            return 1

    topics = [x.strip() for x in args.topics.split(",") if x.strip()]
    if topics:
        try:
            d = req("PUT", f"{API}/topics", token, {"names": topics})
            print("topics:", d.get("names"))
        except urllib.error.HTTPError as e:
            print(f"topics 设置失败 HTTP {e.code}", file=sys.stderr)
            print(e.read().decode("utf-8", "replace")[:300], file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())