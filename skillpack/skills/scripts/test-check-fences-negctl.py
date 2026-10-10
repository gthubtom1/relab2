# -*- coding: utf-8 -*-
"""check-fences.py 的负控：证明这个门禁该红的时候红。

★ 为什么必须有
  2026-10-10 全项目审查查出：check-fences.py 报绿但**从来没真正工作过** ——
    1) 硬编码扫描根，`--root` 参数被完全忽略（所以任何指向其他目录的测试都无效）
    2) default_root 少上溯一层，默认根变成 C:\\skillpack\\skills（直接 rc=2 全红）
    3) 只收小写 `.md`，大写 `.MD` 整个逃过体检
    4) 扫到 0 个文件时报绿（在空目录 / 路径写错时假装通过）
  修完之后必须有负控，否则下一次改弱它又会静默通过。
  本文件是 test-audit-doc-code-negctl.py 之外的**第二道**负控。

退出码
  0  全部符合期望
  1  有漏报（该红没红）或误报（不该红却红了）
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(HERE, "check-fences.py")
PY = sys.executable

# (说明, 文件名, 文件内容 或 None, 期望退出码)
#   期望 0 = 通过；1 = 有未闭合围栏；2 = 门禁自身失效（根不存在/扫到 0 个文件）
CASES = [
    ("正常配对的围栏 -> rc=0", "ok.md",
     "# t\n\n```python\nx = 1\n```\n", 0),
    ("未闭合围栏 -> rc=1", "unclosed.md",
     "# t\n\n```python\nx = 1\n", 1),
    ("闭合围栏带语言标注 -> rc=0", "lang.md",
     "# t\n\n~~~powershell\nWrite-Host 1\n~~~\n", 0),
    ("嵌套围栏（4 反引号包 3 反引号）-> rc=0", "nested.md",
     "# t\n\n````markdown\n```python\nx = 1\n```\n````\n", 0),
    ("大写 .MD 扩展名 -> 未闭合必须被抓 rc=1", "UP.MD",
     "# t\n\n```python\nx = 1\n", 1),
    ("多个文件，只有一个坏 -> rc=1", "mixed.md",
     "# t\n\n```js\nconsole.log(1)\n", 1),
    ("无围栏的纯文档 -> rc=0", "plain.md",
     "# 标题\n\n正文里有 `行内代码` 和 [链接](a.md)。\n", 0),
]


def run(root, timeout=300):
    p = subprocess.run([PY, "-B", GATE, "--root", root],
                       capture_output=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")


def main():
    print("=" * 74)
    print("check-fences.py 负控：%d 个用例" % len(CASES))
    print("=" * 74)
    print("%-44s %-8s %-8s %s" % ("用例", "期望", "实际", "结论"))
    print("-" * 74)

    root = tempfile.mkdtemp(prefix="fences-negctl-")
    try:
        for _desc, name, content, _want in CASES:
            io.open(os.path.join(root, name), "w",
                    encoding="utf-8", newline="\n").write(content)
        rc, out = run(root)
        got = rc
        ok = (got == 1)  # 集合里有坏文件，整体必须红
        print("%-44s %-8s %-8s %s" % ("混合集合（含 3 个未闭合）",
                                       "rc=1", "rc=%d" % got, "OK" if ok else "NG"))
        miss = [] if ok else ["混合集合：整体必须 rc=1"]

        # 逐个用例：每建一个干净目录只放该文件
        for desc, name, content, want in CASES:
            one = tempfile.mkdtemp(prefix="fences-one-")
            try:
                io.open(os.path.join(one, name), "w",
                        encoding="utf-8", newline="\n").write(content)
                rc2, _ = run(one)
                good = (rc2 == want)
                if not good:
                    miss.append("%s（期望 rc=%d 实得 %d）" % (desc, want, rc2))
                print("%-44s %-8s %-8s %s" % (
                    desc[:42], "rc=%d" % want, "rc=%d" % rc2,
                    "OK" if good else "NG"))
            finally:
                shutil.rmtree(one, ignore_errors=True)

        # 门禁自身失效的两个出口
        empty = tempfile.mkdtemp(prefix="fences-empty-")
        try:
            rc3, out3 = run(empty)
            good = (rc3 == 2 and "一个 md 都没扫到" in out3)
            if not good:
                miss.append("空目录必须 rc=2 且明确说明（实得 rc=%d）" % rc3)
            print("%-44s %-8s %-8s %s" % ("空目录 -> 门禁自身失效",
                                           "rc=2", "rc=%d" % rc3,
                                           "OK" if good else "NG"))
        finally:
            shutil.rmtree(empty, ignore_errors=True)

        rc4, out4 = run(os.path.join(root, "no-such-dir-xyz"))
        good = (rc4 == 2 and "不存在" in out4)
        if not good:
            miss.append("不存在的根必须 rc=2 且明确说明（实得 rc=%d）" % rc4)
        print("%-44s %-8s %-8s %s" % ("不存在的根 -> 门禁自身失效",
                                       "rc=2", "rc=%d" % rc4,
                                       "OK" if good else "NG"))

        print()
        print("=" * 74)
        if miss:
            print("NG：%d 项不符合" % len(miss))
            for m in miss:
                print("   - " + m)
            return 1
        print("OK：漏报 0 / 误报 0 —— check-fences.py 确实在工作")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())