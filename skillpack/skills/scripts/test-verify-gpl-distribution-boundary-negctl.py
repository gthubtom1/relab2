#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify-gpl-distribution-boundary.py 的负控。

★ 为什么需要
  这道门禁保护的是一条**会沉默失效**的决策：方案 C（保持现状）
  只在不对外分发时成立。仓库一直是私有的，哪天有人把 remote 改成公开，
  GPL 分发义务立刻生效 —— 如果门禁此时也不响，那它等于不存在。

  它必须能在这三种情况下变红：
    1) LICENSE 里没有决策记录      -> 决策没留痕，半年后没人知道前提
    2) 远端被判为公开             -> 方案 C 失效，必须重新评估
    3) 远端可见性查不到却当成公开 -> 那是另一种形式的假绿

  可见性靠 `gh repo view --json visibility`。负控用一个**假 gh**
  （放在 PATH 最前、返回预设可见性）来驱动全部三种情形 ——
  不碰网络，也不碰真实远端。

退出码
  0  全部符合期望
  1  有漏报或误报
"""
from __future__ import annotations

import io
import os
import shutil
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(HERE, "verify-gpl-distribution-boundary.py")
PY = sys.executable

# 一段最小的 LICENSE（含决策记录标记）
LICENSE_WITH_DECISION = """MIT License

Copyright (c) 2026 someone

## 许可策略决策记录（2026-10-10）

决定：方案 C —— 保持现状。
"""

# 不含决策记录标记的 LICENSE
LICENSE_WITHOUT_DECISION = "MIT License\n\nCopyright (c) 2026 someone\n"


def make_fake_gh(directory: str, visibility: str | None) -> str:
    """造一个假 gh，返回它的路径（给门禁的 GH_BIN 用）。

    ★ 为什么用 GH_BIN 而不是改 PATH
      Windows 上 shutil.which 按 PATHEXT 解析，无扩展名的 shell 脚本会被跳过，
      which 会直接落到 D:\\Tools\\gh\\bin\\gh.exe（真 gh）。
      实测踩过这个坑：假 gh 放进 PATH 也没被用上，负控于是用真 gh 去查
      真的 GitHub 仓库，拿到的是真实结果 —— 负控变成了在测网络而不是在测门禁。
      显式传路径没有这个歧义。
    """
    # ★ 每次调用必须写**不同的文件名**。
    #   第一版三次调用都写 fake-gh.bat，后两次覆盖前一次，
    #   于是三个「假 gh」指向同一路径、内容是最后写的那个 ——
    #   负控的 5 个用例实际只测了 1 种状态，还测错了那一种。
    tag = {"PRIVATE": "private", "PUBLIC": "public"}.get(visibility, "none")
    if sys.platform.startswith("win"):
        path = os.path.join(directory, "fake-gh-%s.bat" % tag)
        if visibility:
            body = "@echo %s\n" % visibility
        else:
            body = "@echo error: not logged in 1>&2\r\nexit /b 1\r\n"
    else:
        path = os.path.join(directory, "fake-gh-%s" % tag)
        if visibility:
            body = '#!/bin/sh\necho "%s"\n' % visibility
        else:
            body = '#!/bin/sh\necho "error: not logged in" >&2\nexit 1\n'
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP)
    return path


def make_repo(tmp: str, name: str, license_text: str,
              remote: str | None, visibility: str | None) -> str:
    root = os.path.join(tmp, name)
    os.makedirs(root, exist_ok=True)
    with io.open(os.path.join(root, "LICENSE"), "w",
                 encoding="utf-8", newline="\n") as fh:
        fh.write(license_text)
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = env["GIT_COMMITTER_NAME"] = "t"
    env["GIT_AUTHOR_EMAIL"] = env["GIT_COMMITTER_EMAIL"] = "t@e.invalid"
    env["GIT_CONFIG_GLOBAL"] = os.path.join(tmp, "gitconfig")
    env["GIT_CONFIG_SYSTEM"] = os.path.join(tmp, "gitconfig")
    subprocess.run(["git", "init", "-q", root], check=False,
                   capture_output=True, env=env, timeout=60)
    if remote:
        subprocess.run(["git", "-C", root, "remote", "add", "origin", remote],
                       check=False, capture_output=True, env=env, timeout=60)
    return root


def run(root: str, gh_bin: str, timeout: int = 120) -> tuple[int, str]:
    env = dict(os.environ)
    env["GH_BIN"] = gh_bin
    p = subprocess.run([PY, "-B", GATE, "--root", root],
                       capture_output=True, timeout=timeout, env=env)
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")


def main() -> int:
    print("=" * 74)
    print("verify-gpl-distribution-boundary.py 负控")
    print("=" * 74)
    tmp = tempfile.mkdtemp(prefix="gpl-negctl-")
    failures: list[str] = []
    try:
        # --- 1) 私有远端 + 决策在位 -> rc=0（方案 C 成立）---
        gh_private = make_fake_gh(tmp, "PRIVATE")
        gh_public = make_fake_gh(tmp, "PUBLIC")
        gh_none = make_fake_gh(tmp, None)
        r1 = make_repo(tmp, "private_ok", LICENSE_WITH_DECISION,
                       "https://github.com/o/r", "PRIVATE")
        rc, out = run(r1, gh_private)
        good = rc == 0
        if not good:
            failures.append("私有远端应 rc=0（实得 %d）" % rc)
        print("  %-46s %s" % ("私有远端 + 决策在位 -> rc=0",
                               "OK" if good else "NG"))

        # --- 2) 公开远端 -> rc=20（方案 C 失效）---
        r2 = make_repo(tmp, "public", LICENSE_WITH_DECISION,
                       "https://github.com/o/r", "PUBLIC")
        rc, out = run(r2, gh_public)
        good = rc == 20 and "方案 C 已失效" in out
        if not good:
            failures.append("公开远端应 rc=20（实得 %d）" % rc)
        print("  %-46s %s" % ("公开远端 -> rc=20 阻断",
                               "OK" if good else "NG"))

        # --- 3) 决策记录缺失 -> rc=1 ---
        r3 = make_repo(tmp, "nodecision", LICENSE_WITHOUT_DECISION,
                       "https://github.com/o/r", "PRIVATE")
        rc, out = run(r3, gh_private)
        good = rc == 1 and "没有留痕" in out
        if not good:
            failures.append("缺决策记录应 rc=1（实得 %d）" % rc)
        print("  %-46s %s" % ("决策记录缺失 -> rc=1",
                               "OK" if good else "NG"))

        # --- 4) 可见性查不到 -> 必须**不**当成公开（不得误阻断）---
        r4 = make_repo(tmp, "unknown", LICENSE_WITH_DECISION,
                       "https://github.com/o/r", None)
        rc, out = run(r4, gh_none)
        good = rc == 0 and "不**把它当成公开" in out
        if not good:
            failures.append(
                "查不到可见性时应放行并提示（rc=%d）；"
                "当成公开就是另一种形式的假绿" % rc)
        print("  %-46s %s" % ("可见性查不到 -> 放行并提示，不得误阻断",
                               "OK" if good else "NG"))

        # --- 5) 无远端 -> rc=0（本地开发态）---
        r5 = make_repo(tmp, "noremote", LICENSE_WITH_DECISION, None, "PRIVATE")
        rc, _ = run(r5, gh_private)
        good = rc == 0
        if not good:
            failures.append("无远端应 rc=0（实得 %d）" % rc)
        print("  %-46s %s" % ("无远端（本地开发态）-> rc=0",
                               "OK" if good else "NG"))

        print()
        print("=" * 74)
        if failures:
            print("NG：%d 项" % len(failures))
            for f in failures:
                print("   - " + f)
            return 1
        print("OK：漏报 0 / 误报 0 —— 许可边界守卫确实在工作")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())