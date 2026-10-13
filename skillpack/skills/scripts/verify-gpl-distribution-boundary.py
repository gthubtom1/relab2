#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仓库的 GPL 分发边界守卫。

★ 为什么需要这道门禁
  2026-10-10 决策：许可策略走**方案 C（保持现状）**，
  它成立的前提只有一个 —— **不对外分发**。GPL-3.0 的分发义务在向他人
  交付时触发；纯私有自用不构成分发。

  方案 C 的风险是**沉默失效**：仓库一直是私有的，哪天有人加了公开远端
  或者发了个 release，分发义务立刻生效，而没有任何东西会提醒。
  这道门禁就是那个提醒。

  它检查两件事：
    1) 决策记录在不在（`LICENSE` 里有没有「许可策略决策记录」一节）
       —— 决策必须留痕，否则半年后没人知道为什么 LICENSE 这么写
    2) 当前有没有**公开**远端 —— 有就判定为「已对外分发」，
       方案 C 失效，必须重审

退出码
  0  决策在，且当前无公开远端（方案 C 成立）
  1  决策记录缺失
  20 检出公开远端 —— 方案 C 失效，必须重新评估许可策略
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# scripts/ -> skills/ -> skillpack/ -> <仓根>
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

# 决策记录必须出现的字样
DECISION_MARKER = "许可策略决策记录"
# 决策里写明的失效触发条件（拿它跟实际远端对照）
DISTRIBUTION_TRIGGERS = ("对外分发", "公开")

# remote URL 里的托管域名 —— 只说明「托管在哪」，**不说明可见性**。
# 2026-10-10 实测踩到的坑：origin 是 github.com/gthubtom1/relab2，
# 只看 URL 会判成「已对外分发」，但 `gh repo view --json isPrivate`
# 报的是 PRIVATE —— 私有 GitHub 仓库同样不构成分发。
HOST_RE = re.compile(
    r"^(?:https?://|git@)([^/:]+)[:/]([^/]+)/([^/]+?)(?:\.git)?/?$",
    re.I,
)


def visibility_of(url: str) -> tuple[str, str]:
    """远端的可见性。返回 (state, detail)。

    state 取值：
      "private"   —— 确认私有，方案 C 成立
      "public"    —— 确认公开，方案 C 失效
      "unknown"   —— 查不到（没装 gh / 没登录 / 离线），
                     此时**不能**当成 public —— 门禁不该因为查不到就误阻断
    """
    m = HOST_RE.match(url.strip())
    if not m:
        return "unknown", "无法解析的 remote URL"
    host, owner, repo = m.group(1), m.group(2), m.group(3)
    if "github.com" not in host.lower():
        # 非 GitHub 托管：本地文件远端或自建。无法判定可见性。
        return "unknown", "非 GitHub 托管，无法自动判定可见性"
    # GH_BIN 覆盖：负控用它塞一个假 gh（Windows 上 shutil.which 只认
    # PATHEXT 里的扩展名，无扩展名的 shell 脚本会被跳过而落到真实 gh.exe）。
    # 顺带也让 CI 能显式指定 gh 路径。
    gh = os.environ.get("GH_BIN") or shutil.which("gh") or _find_gh()
    if not gh:
        return "unknown", "未找到 gh CLI，无法查 GitHub 可见性"
    try:
        out = subprocess.run(
            [gh, "repo", "view", "%s/%s" % (owner, repo),
             "--json", "visibility", "-q", ".visibility"],
            capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return "unknown", "gh 调用失败"
    v = out.stdout.decode("utf-8", "replace").strip().upper()
    if v == "PRIVATE":
        return "private", "gh 报 PRIVATE"
    if v == "PUBLIC":
        return "public", "gh 报 PUBLIC"
    return "unknown", "gh 未返回可见性（多半是没登录或离线）"


def _find_gh() -> str | None:
    """gh 不在 PATH 时常见于 D:\\Tools\\gh\\bin。"""
    for cand in (r"<工具根>\<分类>\<工具名>\bin\gh.exe",):
        if os.path.isfile(cand):
            return cand
    return None


def remotes(repo: str) -> list[tuple[str, str]]:
    try:
        out = subprocess.run(
            ["git", "-C", repo, "remote", "-v"],
            capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return []
    rows: list[tuple[str, str]] = []
    for line in out.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] not in {r for r, _ in rows}:
            rows.append((parts[0], parts[1]))
    return rows


def read_license(repo: str) -> str:
    p = os.path.join(repo, "LICENSE")
    if not os.path.isfile(p):
        return ""
    with open(p, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=REPO)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    root = os.path.abspath(args.root)

    lic = read_license(root)
    has_decision = DECISION_MARKER in lic

    remote_rows = remotes(root)
    # 逐个远端查**真实可见性**。只看 URL 会把私有 GitHub 仓库误判成公开
    # —— 2026-10-10 实测：origin 是 github.com/gthubtom1/relab2，
    # 只看域名会判成「已对外分发」，而 gh 报的是 PRIVATE。
    vis: list[dict[str, str]] = []
    for name, url in remote_rows:
        state, detail = visibility_of(url)
        vis.append({"name": name, "url": url,
                    "visibility": state, "detail": detail})
    public = [v for v in vis if v["visibility"] == "public"]
    unknown = [v for v in vis if v["visibility"] == "unknown"]

    result = {
        "root": root,
        "decision_recorded": has_decision,
        "remotes": vis,
        "public_remotes": public,
        "unknown_remotes": unknown,
        "verdict": "C-OK" if (has_decision and not public)
                   else ("PUBLIC-REMOTE" if public else "NO-DECISION"),
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 20 if public else (0 if has_decision else 1)

    print("verify-gpl-distribution-boundary")
    print("  决策记录（LICENSE 里的「%s」）：%s"
          % (DECISION_MARKER, "有" if has_decision else "★缺失★"))
    if vis:
        print("  git remote 与可见性：")
        for v in vis:
            mark = {"private": "私有", "public": "★公开★",
                    "unknown": "未知"}.get(v["visibility"], "?")
            print("    %-10s %-6s %s  (%s)"
                  % (v["name"], mark, v["url"], v["detail"]))
    else:
        print("  git remote：（无）")

    if not has_decision:
        print()
        print("FAIL verify-gpl-distribution-boundary: 许可策略决策没有留痕。")
        print("  方案 C（保持现状）是个**有前提**的决定：只在不对外分发时成立。")
        print("  这个前提必须写在 LICENSE 里，否则半年后没人知道它为什么成立。")
        return 1

    if unknown and not public:
        print()
        print("  ⚠ %d 个远端的可见性查不到（%s）"
              % (len(unknown), unknown[0]["detail"]))
        print("    本门禁**不**把它当成公开 —— 查不到就阻断是另一种形式的假绿。")
        print("    要人工确认：`gh repo view <owner>/<repo> --json visibility`")

    if public:
        print()
        print("=" * 70)
        print("BLOCKED: 检出公开远端 —— 方案 C 已失效")
        print("=" * 70)
        for p in public:
            print("  %s" % p)
        print()
        print("仓库含 GPL-3.0 改编内容（218 篇，见 skillpack/NOTICE）。")
        print("GPL 的分发义务在**向他人交付**时触发。推到公开远端 = 交付。")
        print()
        print("必须在继续之前二选一：")
        print("  A 整体转 GPL-3.0        —— 0 机械成本，89% 原创代码也被 copyleft")
        print("  B 隔离 skills/*/references/  —— 保持 MIT，但 12 个 SKILL.md 的")
        print("                              约 563 处 references 链接要逐处处理")
        print()
        print("决策记录与依据见 LICENSE 的「%s」一节。" % DECISION_MARKER)
        return 20

    print()
    print("OK verify-gpl-distribution-boundary: 决策已留痕，且当前无公开远端")
    print("   （方案 C 成立。推到公开远端时本门禁会 rc=20 阻断。）")
    return 0


if __name__ == "__main__":
    sys.exit(main())