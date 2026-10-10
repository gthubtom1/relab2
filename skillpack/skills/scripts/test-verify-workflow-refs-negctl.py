#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify-workflow-refs.py 的负控：证明它该红的时候红。

★ 为什么需要
  这道门禁本身就是为了抓「CI 引用不存在的文件」而写的。
  如果它自己有一天也变成「什么都查不出来还报绿」，
  那它就成了它本该防的那类东西 —— 所以它也得有负控。

做法：在一份**真实 workflow 的副本**上注入三种坏引用，
每一种都必须被抓到；再确认一份干净副本必须放行。

退出码
  0  全部符合期望
  1  有漏报或误报
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(HERE, "verify-workflow-refs.py")
PY = sys.executable

# (说明, 注入的 run: 行, 期望被报告为不存在)
BAD = [
    ("引用一个从未存在的 .sh",
     "      - name: bogus\n        run: bash skillpack/kali/scripts/test-nope.sh"),
    ("引用一个不存在的 .py",
     "      - name: bogus\n        run: python3 skillpack/skills/scripts/nope-xyz.py"),
    ("引用一个只有 PS 孪生、没有 .sh 的路径",
     "      - name: bogus\n        shell: bash\n"
     "        run: /bin/bash skillpack/skills/scripts/test-client-neutral-bootstrap.sh"),
]

# 干净基线：**不引用任何仓库内文件**。
# 早先这里写的是「引用真实存在的 verify-workflow-refs.py」，
# 但合成根下并没有那个文件 -> 门禁正确地报了不存在 -> 干净基线误报。
# 负控自己的夹具写错也会 NG，这本身就是负控在工作。
CLEAN = """name: synthetic
on: [push]
jobs:
  probe:
    runs-on: ubuntu-latest
    steps:
      - name: no repo references
        run: echo hello
"""


def run(root: str, timeout: int = 120) -> tuple[int, str]:
    p = subprocess.run([PY, "-B", GATE, "--root", root],
                       capture_output=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")


def make_repo(tmp: str, name: str, body: str) -> str:
    root = os.path.join(tmp, name)
    wf = os.path.join(root, ".github", "workflows")
    os.makedirs(wf, exist_ok=True)
    # 门禁用 git ls-files 加速；给它一个真的 git 仓库更接近 CI 实况
    subprocess.run(["git", "init", "-q", root], check=False,
                   capture_output=True)
    io.open(os.path.join(wf, "synthetic.yml"), "w",
            encoding="utf-8", newline="\n").write(body)
    return root


def main() -> int:
    print("=" * 74)
    print("verify-workflow-refs.py 负控")
    print("=" * 74)
    tmp = tempfile.mkdtemp(prefix="vwr-negctl-")
    failures: list[str] = []
    try:
        # 1) 干净副本必须放行
        clean = make_repo(tmp, "clean", CLEAN)
        rc, out = run(clean)
        if rc != 0:
            failures.append("干净副本必须 rc=0（实得 %d）: %s"
                            % (rc, out.strip()[:200]))
        print("  %-44s %s" % ("干净副本 -> 放行", "OK" if rc == 0 else "NG"))

        # 2) 三种坏引用必须被抓
        for i, (desc, step) in enumerate(BAD, 1):
            body = CLEAN + "\n" + step + "\n"
            root = make_repo(tmp, "bad%d" % i, body)
            rc, out = run(root)
            # 未跟踪的 .sh 不在 git ls-files 里，会被报成不存在 —— 正是期望
            good = rc == 1 and "引用指向不存在的文件" in out
            if not good:
                failures.append("%s 未被抓（rc=%d）" % (desc, rc))
            print("  %-44s %s" % (desc[:42],
                                   "OK" if good else "NG(rc=%d)" % rc))

        # 3) 根不存在必须 rc=2
        rc, _ = run(os.path.join(tmp, "no-such-root"))
        good = (rc == 2)
        if not good:
            failures.append("不存在的根必须 rc=2（实得 %d）" % rc)
        print("  %-44s %s" % ("不存在的根 -> 门禁自身失效",
                               "OK" if good else "NG"))

        print()
        print("=" * 74)
        if failures:
            print("NG：%d 项" % len(failures))
            for f in failures:
                print("   - " + f)
            return 1
        print("OK：漏报 0 / 误报 0 —— verify-workflow-refs.py 确实在工作")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())