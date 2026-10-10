# -*- coding: utf-8 -*-
"""全库代码围栏配对体检 —— 第三版（修正嵌套围栏判定）。

## 前两版的问题
v1：闭合行也压栈 -> 大量假报
v2：把「块内字面围栏」当闭合吃掉
    典型：markdown 示例里演示 ```` ```[language] ```` 这种嵌套写法，
    v2 看到栈非空 + 反引号数相同就 pop，但 info（`[language]`）非空
    说明它是**字面量**不是闭合标记。

## v3 的正确规则（CommonMark GFM §4.5 Code Fence）
1. 围栏行 = 行首（≤3空格）+ ≥3 个反引号 + 可选 info string
2. **开块**只发生在栈空时
3. **闭合**必须满足：反引号数 ≥ 开块数，且 **info string 为空**
4. 块内出现的其它围栏行（含 info 非空的）一律视为字面量，忽略
5. 扫描结束栈非空 = 未闭合

另外要处理：连续两个开块（文档里写了 ``` ```python ``` ``` 这种）
"""
import io
import os
import re
import sys
from collections import defaultdict

def default_root():
    """默认扫仓内 skillpack/skills；可被 --root 覆盖（CI 与负控需要）。

    ★ 2026-10-10 修正：原来数了 5 层 dirname，
      __file__=<仓根>/skillpack/skills/scripts/check-fences.py 上溯 5 层
      会跑到 <仓根> 的**父目录**去，默认根变成 `C:\\skillpack\\skills`
      （因为仓根在 C:\\），门禁直接 rc=2 全红。
      正确层数：从 scripts/ 上溯 4 层才是仓根。
    """
    env = os.environ.get("REVERSE_SKILL_ROOT")
    if env:
        cand = os.path.join(env, "skillpack", "skills")
        if os.path.isdir(cand):
            return cand
    # scripts/ -> skills/ -> skillpack/ -> <仓根>：4 层
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    return os.path.join(repo, "skillpack", "skills")

ROOT = default_root()
FENCE = re.compile(r"^[ ]{0,3}(`{3,})[ \t]*(.*?)[ \t]*$")


def scan(path):
    lines = io.open(path, encoding="utf-8", errors="replace").read().split("\n")
    stack = []
    events = []
    for i, ln in enumerate(lines, 1):
        m = FENCE.match(ln)
        if not m:
            continue
        ticks, info = m.group(1), m.group(2)
        if stack:
            # 闭合：反引号数足够 且 info 为空
            if len(ticks) >= stack[-1][0] and info.strip() == "":
                stack.pop()
                events.append((i, "close"))
            else:
                events.append((i, "literal"))
            continue
        stack.append((len(ticks), i, info))
        events.append((i, "open:" + info[:12]))
    return stack, events


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=ROOT,
                    help="要扫描的目录（默认仓内 skillpack/skills）")
    args = ap.parse_args()
    SK = args.root

    if not os.path.isdir(SK):
        print("扫描根不存在: %s" % SK)
        sys.exit(2)

    print("=== md 代码围栏配对体检 ===\n")
    print("扫描根: %s\n" % SK)
    files = []
    for dp, dns, fs in os.walk(SK):
        dns[:] = [d for d in dns if d not in (".git", "node_modules",
                                              "pyghidra_mcp_projects",
                                              "_archive", "work")]
        for f in fs:
            # ★ 大小写不敏感：Windows 上 .MD / .Md 与 .md 是同一个文件，
            #   但 f.endswith(".md") 只认小写 —— 会让大写扩展名的文件整个逃过体检。
            if f.lower().endswith(".md"):
                files.append(os.path.join(dp, f))

    bad = []
    by_lang = defaultdict(int)
    for p in files:
        stack, _ = scan(p)
        if stack:
            rel = os.path.relpath(p, SK).replace(os.sep, "/")
            bad.append((rel, stack))
            for _, ln, info in stack:
                by_lang[info or "(无标注)"] += 1

    print("扫描 %d 个 md" % len(files))
    # ★ 扫到 0 个文件时必须报出来 —— 「扫了 0 个」和「扫了 627 个全过」
    #   在汇总上长得一样，但前者意味着路径写错了、门禁根本没生效。
    if not files:
        print("★ 一个 md 都没扫到 —— 扫描根或扩展名匹配有问题，本门禁等于没跑")
        sys.exit(2)
    print("未闭合围栏的文件：%d\n" % len(bad))
    for rel, stack in bad:
        print("  ★ %s" % rel)
        for _, ln, info in stack:
            print("      未闭合：开块于行 %d  语言=%s" % (ln, info or "(无)"))

    print("\n=== 未闭合的语言分布 ===")
    for k, v in sorted(by_lang.items(), key=lambda x: -x[1])[:12]:
        print("   %-18s %d" % (k, v))

    sys.exit(1 if bad else 0)