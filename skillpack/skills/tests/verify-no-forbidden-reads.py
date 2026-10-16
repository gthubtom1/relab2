#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify-no-forbidden-reads.py —— 「一个字都不许读」这条禁令，必须有一道门在执行它。

================================================================================
为什么会需要这道门（2026-10-15 独立审查 P9：一个真实的越界事故）
================================================================================

主人在 `START-HERE.md` 的 ⛔ 段明写：`_归档-禁读-历史文档/` **一个字都不许读**，
那是前几轮 AI 自己写的方案、施工清单、复盘、"完成状态"报告，描述的是**当时那个版本**，
与现在的代码不一致。他为这个病吃过很多次亏（"每次都说完成了，一用就出问题"）。

但这条禁令**只写在给人的文档里**。仓库里两个会遍历全仓的门禁
（`skills/scripts/verify-doc-links.py`、`skills/tests/verify-project-requirements.py`）
的排除名单都比禁令更老，于是：

  · `verify-doc-links.py` 的文件集 = `git ls-files --cached --others --exclude-standard`
    → 打开禁读目录下 **49 个 .md** 的正文做链接解析；
  · `verify-project-requirements.py` 的 R12 从仓根 `os.walk`
    → 打开禁读目录下 **20 个** `.md/.py/.json`。

后果：**「照着 README 跑全套门禁」这个动作本身，就成了违反禁令的动作。**
一位外部独立审查员因此越界（他的报告 §4.4 如实披露了四次），
而一个按 `环境初始化.md` §7 门 5 干活的 agent 会静默越界 —— 没有报错、没有退出码、
没有任何提示。**最坏的一类失效：不是门坏了，是门在替你违反规矩。**

本门把这条禁令变成代码：
  1. 每条门禁脚本的**遍历/读取范围**不得包含禁读前缀（静态：读源码里的根路径与排除名单）；
  2. **动态**：用 Python 审计钩子跑一遍门禁，记录它真的 `open()` 过哪些文件，
     命中禁读目录即判红（这是唯一能证明"这次真的没读"的办法）。

用法：
    python skills/tests/verify-no-forbidden-reads.py              # 静态 + 动态
    python skills/tests/verify-no-forbidden-reads.py --static     # 只静态（快）
    python skills/tests/verify-no-forbidden-reads.py --json

退出码：0 全过 / 20 有门禁会读禁读区（blocked）
自带控制组（--selftest）：拿一份必然违规的样本源码，必须被判红。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

DQ = chr(34)  # double quote
SQ = chr(39)  # single quote
BS = chr(92)  # backslash

HERE = os.path.dirname(os.path.abspath(__file__))          # skillpack/skills/tests
SKILLS_ROOT = os.path.dirname(HERE)                         # skillpack/skills
PKG_ROOT = os.path.dirname(SKILLS_ROOT)                     # skillpack
# ⚡ WATCHED_SCRIPTS 的路径按什么根解析：与 ci-gates.json 一致（skillpack 根），
#   而不是仓库根。run-ci-gates.py:58 的 ROOT = parents[2] 就是这个口径；
#   本门第一版按仓库根解析，结果 9 条全报“脚本不存在”——
#   假红，而且正是“会让人把门关掉”的那一类。
MANIFEST_ROOT = PKG_ROOT

# 禁读前缀（与 verify-doc-links.py 的 FORBIDDEN_READ_PREFIXES 保持一致）
FORBIDDEN_PREFIXES = ("_归档-禁读-历史文档/",)
FORBIDDEN_DIRNAME = "_归档-禁读-历史文档"

# 需要被这道门看着的「会遍历仓库」的门禁脚本。
# 判据不是"我叫它门禁"，而是"它会不会自己走仓库树"——只有这类脚本能造成越界。
WATCHED_SCRIPTS = (
    "skills/scripts/verify-doc-links.py",
    "skills/tests/verify-project-requirements.py",
    "skills/scripts/audit-discovery-surface.py",
    "skills/scripts/verify-workflow-refs.py",
    "skills/scripts/audit-doc-code.py",
    "skills/scripts/check-fences.py",
    "skills/scripts/verify-doc-facts.ps1",
    "skills/scripts/scan-leaks.ps1",
    "skills/scripts/verify-repository-security.py",
)


def _read(p: str) -> str:
    try:
        with open(p, encoding="utf-8-sig", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


# ---------------------------------------------------------------- 静态检查
# 判据不是「有没有 os.walk」（那会误报），而是「遍历根能不能到达禁读目录」。
#   · 只扫 skillpack 子树的（check-fences / audit-doc-code）到不了仓根的禁读目录 → 不红；
#   · 从仓根遍历、或用 `git ls-files` 取跟踪集合的 → 红（除非已排除）。
# 第一版本门按「有 os.walk 就红」，一下子报了 5 个假红 —— 假红正是会让人把门关掉的那种。
FORBIDDEN_DIRNAME = "_归档-禁读-历史文档"


# 认可的“真排除”写法（看到禁读名字之后，还得看到它被用在排除上）
_EXCLUDE_HINTS = (
    "dirs[:]",
    "startswith(FORBIDDEN",
    "startswith(_",
    "!= FORBIDDEN",
    "not in",
    "SKIPPED_PREFIXES",
    "FORBIDDEN_READ_PREFIXES",
    "FORBIDDEN_READ_PREFIX",
    "-Exclude",
    "--exclude",
    "Where-Object",
    "-notlike",
    "-notmatch",
)


def _exclusion_names(src: str) -> set:
    """找出被赋成禁读目录名字的常量/变量名。

    识别两种写法：
      DENY   = ("_归档-禁读-历史文档",)      # 字面量直接含名字
      DENY   = (FORBIDDEN_DIRNAME,)                  # 引用本模块常量
      F      = "_归档-禁读-历史文档"
    """
    names = set()
    import re as _re
    for ln in src.splitlines():
        s = ln.strip()
        if s.startswith("#"):
            continue
        m = _re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", s)
        if not m:
            continue
        var, rhs = m.group(1), m.group(2)
        if FORBIDDEN_DIRNAME in rhs or "FORBIDDEN_DIRNAME" in rhs:
            names.add(var)
    return names


def _actually_excludes(src: str) -> bool:
    """这段源码是否真的把禁读目录排除掉（而不是只在注释里提到它）。

    判据（满足任一）：
      A. 某行非注释代码里同时出现 `dirs[:]` 与禁读目录名字（内联写法）；
      B. 某行非注释代码里同时出现 `dirs[:]` 与“被赋成禁读名字的那个变量”
         （象限名写法：DENY = (...); dirs[:] = [d for d in dirs if d not in DENY]）。

    不算的：`dirs[:] = list(dirs)`、`dirs.sort()`、`dirs[:] = dirs[:3]` ——都没有过滤禁读名字。
    """
    excl_names = _exclusion_names(src)
    excl_lower = {n.lower() for n in excl_names}
    import re as _re
    for ln in src.splitlines():
        s = ln.strip()
        if s.startswith("#"):
            continue
        if "dirs[:]" not in s:
            continue
        # A. 内联：同行出现禁读名字
        if FORBIDDEN_DIRNAME in s:
            return True
        # B. 象限名：同行出现那个变量（单词边界匹配，避免 DENY 命中 DENYLIST 之类）
        for tok in _re.findall(r"[A-Za-z_][A-Za-z0-9_]*", s):
            if tok.lower() in excl_lower:
                return True
    # C. 行内过滤：出现 `startswith(FORBIDDEN...)` / `!= 禁名` / `禁名 not in`
    #    —— 这是仓库里份真实写法（verify-doc-links / verify-workflow-refs /
    #    verify-repository-security 都是这样），不需要 `dirs[:]` 那个形状。
    import re as _re2
    for ln in src.splitlines():
        s = ln.strip()
        if s.startswith("#"):
            continue
        low = s.lower()
        mentions = (FORBIDDEN_DIRNAME in s) or any(n in s for n in ("FORBIDDEN_DIRNAME", "FORBIDDEN_READ_PREFIX", "FORBIDDEN_PREFIX"))
        if not mentions:
            continue
        if (".startswith(" in low or "!= " in s or "not in " in s or "-notlike" in low
                or "-notmatch" in low or "exclude" in low):
            return True

    return False


def _reaches_forbidden(src):
    """这段源码的遍历，能不能到达仓根的禁读目录？

    ★ 2026-10-15 外部审计追问：旧版第一行就是
    `if FORBIDDEN_DIRNAME in src: return False` ——只要源码里出现过这个名字
    （包括只在注释里写「我不读它」）就整段放行。
    现在要求“真排除”：名字得出现在一条非注释且含排除写法的代码里。
    """
    walks = ("os.walk" in src) or ("ls-files" in src) or ("Get-ChildItem" in src)
    if not walks:
        return False
    if _actually_excludes(src):
        return False
    walks_repo_root = ("os.walk(ROOT" in src) or ("os.walk(REPO_ROOT" in src) or ("ls-files" in src)
    if walks_repo_root:
        return True
    pinned = [
        DQ + "skills" + DQ,
        SQ + "skills" + SQ,
        "skills/",
        "skills" + BS + BS,
    ]
    return not any(tok in src for tok in pinned)


def static_check():
    errs = []
    for rel in WATCHED_SCRIPTS:
        p = os.path.join(MANIFEST_ROOT, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            errs.append("%s: 脚本不存在（watched 名单过期了，删掉它或补文件）" % rel)
            continue
        txt = _read(p)
        if _reaches_forbidden(txt):
            errs.append(
                "%s: 会遍历到仓根，但源码里没有 %s 排除 —— 它会读到禁读目录"
                "（正是 2026-10-15 审查 P9 那个越界）" % (rel, FORBIDDEN_DIRNAME))
    return errs


# ---------------------------------------------------------------- 动态检查
# 用 Python 审计钩子记录门禁真的 open() 过哪些文件。
# 这是唯一能证明「这次真的没读」的手段：源码排除只能证明"写了排除"，
# 不能证明"没读"（排除项可能写错、可能被别处的读取绕过）。
_HOOK_SRC = r'''
import sys, os, json
_log = os.environ.get("FORBIDDEN_READ_LOG")
if _log:
    _abs = os.path.abspath(_log)
    def _hook(event, args):
        if event != "open":
            return
        try:
            p = str(args[0])
        except Exception:
            return
        if os.path.abspath(p) == _abs:
            return
        try:
            with open(_abs, "a", encoding="utf-8") as f:
                f.write(json.dumps({"pid": os.getpid(), "pid_ppid": os.getppid(), "path": p}) + "\n")
        except Exception:
            pass
    sys.addaudithook(_hook)
'''


def dynamic_check(timeout: int = 300, full: bool = False) -> tuple[list[str], int]:
    """实跑门禁，记录它 open 过的文件，禁读命中即报错。"""
    errs: list[str] = []
    log = os.path.join(tempfile.mkdtemp(prefix="forbidden-read-"), "opens.jsonl")
    hook_dir = tempfile.mkdtemp(prefix="forbidden-hook-")
    with open(os.path.join(hook_dir, "sitecustomize.py"), "w", encoding="utf-8") as f:
        f.write(_HOOK_SRC)

    env = dict(os.environ)
    env["FORBIDDEN_READ_LOG"] = log
    env["PYTHONPATH"] = hook_dir + os.pathsep + env.get("PYTHONPATH", "")

    python = sys.executable
    pwsh = None
    import shutil as _sh
    for cand in ("pwsh", "powershell"):
        found = _sh.which(cand)
        if found:
            pwsh = found
            break

    # ★ 2026-10-15 外部审计追问：以前这里只手按两个脚本跑，而 WATCHED_SCRIPTS 有 9 个——
    #   “其余的门禁可能静默读禁区却不红”。现在全部跑：.py 用当前解释器，
    #   .ps1 跑 pwsh（没有就明说“未覆盖”，不伪装覆盖过）。
    # ★ 2026-10-15 外部审计追问：以前动态跑全部 9 个 WATCHED，其中两个本踨极慢
    #   （audit-doc-code 编译文档代码块、verify-repository-security 扫全仓密钥），
    #   把整轮 run-ci-gates 拖超时 —— 结果“全量门禁”跑不完、缺 summary，反而成了新的假绿来源。
    #   现在动态只跑快速且真正遍历仓库的三个门（覆盖 git 集合与 os.walk 两种遍历方式）；
    #   其余 WATCHED 靠静态（_reaches_forbidden）——不减覆盖，只不再用运行期兜。
    #   慢门想要运行期证据：--full（人工或夜间 CI 用）。
    FAST_DYNAMIC = {
        "skills/scripts/verify-doc-links.py": ["--json"],
        "skills/scripts/verify-workflow-refs.py": [],
        "skills/tests/verify-project-requirements.py": ["--selftest"],
    }
    targets = []
    for rel, extra in FAST_DYNAMIC.items():
        ap = os.path.join(MANIFEST_ROOT, rel.replace("/", os.sep))
        if os.path.isfile(ap):
            targets.append((rel, [python, ap] + extra))
    if full:
        for rel in WATCHED_SCRIPTS:
            if rel in FAST_DYNAMIC:
                continue
            ap = os.path.join(MANIFEST_ROOT, rel.replace("/", os.sep))
            if not os.path.isfile(ap):
                continue
            if rel.endswith(".py"):
                targets.append((rel, [python, ap]))
            elif rel.endswith(".ps1") and pwsh:
                targets.append((rel, [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ap]))
    static_only = [rel for rel in WATCHED_SCRIPTS if rel not in {t[0] for t in targets}]
    if static_only:
        print("[P9] 仅静态覆盖（运行期证据见 --full）："
              + ", ".join(os.path.basename(r) for r in static_only))

    ran = 0
    for rel, argv in targets:
        name = os.path.basename(argv[1])
        try:
            # 慢门禁（audit-doc-code 要编译文档里每个代码块）给更长预算；
            # 否则整道门会因为它一个超时而报“未覆盖”。
            # 逐个预算：这两个门本身就慢（audit-doc-code 编译文档代码块、verify-repository-security 扫全仓密钥），给它们 900s；其余门禁用默认。
            budget = 900 if rel.endswith(("audit-doc-code.py", "verify-repository-security.py")) else timeout
            subprocess.run(argv, capture_output=True, timeout=budget, env=env, cwd=SKILLS_ROOT)
            ran += 1
        except (OSError, subprocess.TimeoutExpired) as exc:
            errs.append(f"{name}: 动态跑不起来（{type(exc).__name__}）—— 本次只证明了静态，没证明运行期")

    rows = []
    if os.path.isfile(log):
        with open(log, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    hits = [r["path"] for r in rows if FORBIDDEN_DIRNAME in str(r.get("path", ""))]
    total = len(rows)
    for h in hits[:10]:
        errs.append(f"运行期读了禁读文件：{h}")
    if len(hits) > 10:
        errs.append(f"……另有 {len(hits) - 10} 个禁读文件被读")
    meta = {"scripts_ran": ran, "opens_recorded": total, "forbidden_hits": len(hits)}
    print(f"[动态] 跑了 {ran}/{len(targets)} 个 WATCHED 脚本，记录 {total} 次 open()，禁读命中 {len(hits)} 次")
    return errs, meta


# ---------------------------------------------------------------- 控制组
# 没有控制组的门 = 没有门（本仓两次教训：一个假红、一个假绿）。
# 控制组要求：一份必然违规的样本代码（会遍历仓库且不排除禁读目录），
# 静态检查必须把它判红。
CONTROL_SOURCE = """# -*- coding: utf-8 -*-
import os

def scan():
    for dirpath, dirs, files in os.walk("."):
        for fn in files:
            if fn.endswith(".md"):
                open(os.path.join(dirpath, fn), encoding="utf-8").read()
"""

# 否对组：同样遍历，但排除了禁读目录 → 不该红。
CONTROL_CLEAN_SOURCE = """# -*- coding: utf-8 -*-
import os

DENY = ("_归档-禁读-历史文档",)

def scan():
    for dirpath, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in DENY]
        for fn in files:
            if fn.endswith(".md"):
                open(os.path.join(dirpath, fn), encoding="utf-8").read()
"""


def _static_check_source(src: str) -> bool:
    """对一段源码做与 static_check 同样的判定；True = 会被判红。"""
    return _reaches_forbidden(src)


# ★ 2026-10-15 外部审计追问：注释里提了禁读名字、但 `os.walk(REPO_ROOT)` 没有任何排除。
#   旧判据的第一行就是“出现过这个名字就放行”，所以这份样本会被判为安全
#   —— 而它其实会读禁区。这就是“静态全覆盖是假的”的具体形状。
CONTROL_COMMENT_MENTIONS_BUT_NO_EXCLUDE = """# -*- coding: utf-8 -*-
# NOTE: we must never read _归档-禁读-历史文档/ (forbidden dir)
import os

def scan():
    for dirpath, dirs, files in os.walk(REPO_ROOT):
        for fn in files:
            open(os.path.join(dirpath, fn), encoding="utf-8").read()
"""



# ★ 2026-10-15 外部审计追问（第二轮）：`dirs[:]` 本身不等于“排除”。
#   我先前的容错写法（看到 dirs[:] 就认为已排除）被这一条打穽：
#       for dirpath, dirs, files in os.walk(REPO_ROOT):
#           dirs[:] = list(dirs)          # 没有任何过滤，但含 dirs[:]
#   现在判据要求禁读名字（或被赋成它的变量）真的出现在过滤表达式里。
CONTROL_DIRS_SLICE_NO_FILTER = """# -*- coding: utf-8 -*-
import os

def scan():
    for dirpath, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = list(dirs)
        for fn in files:
            open(os.path.join(dirpath, fn), encoding="utf-8").read()
"""

CONTROL_DENY_CONST_OK = """# -*- coding: utf-8 -*-
import os

DENY = ("_归档-禁读-历史文档",)

def scan():
    for dirpath, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in DENY]
        for fn in files:
            open(os.path.join(dirpath, fn), encoding="utf-8").read()
"""



def run_selftest() -> list[str]:
    fails: list[str] = []
    if not _static_check_source(CONTROL_SOURCE):
        fails.append("控制组未转红：一份遍历仓库且不排除禁读目录的样本，静态检查没抓到")
    if _static_check_source(CONTROL_CLEAN_SOURCE):
        fails.append("反例被误判为红：同样遍历但已排除禁读目录的样本，不该红")
    # 还要有一条：一份不遍历的脚本不该被覆盖到
    # ★ 外部审计追问的第三种形态：注释提名+无排除 → 必须转红。
    # 第四种形态：dirs[:] 无过滤 → 必须转红。
    if not _static_check_source(CONTROL_DIRS_SLICE_NO_FILTER):
        fails.append("控制组未转红：dirgs[:] = list(dirs) 无过滤被当成已排除"
                     "——“dirs[:] 出现”不等于“禁读名字被过滤”")
    # 第五种形态：真的用象限名排除 → 不该红。
    if _static_check_source(CONTROL_DENY_CONST_OK):
        fails.append("反例被误判为红：DENY=(禁名,); dirs[:] = [d for d in dirs if d not in DENY] 是合规写法")

    if not _static_check_source(CONTROL_COMMENT_MENTIONS_BUT_NO_EXCLUDE):
        fails.append("控制组未转红：注释里提了禁读名字、\u4f46 os.walk(REPO_ROOT) 没排除——正是旧判据放过的那种假绿")

    if _static_check_source("print('hello')\n"):
        fails.append("反例被误判为红：不遍历的脚本也被判红")
    return fails


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--static", action="store_true", help="只做静态检查（不跑门禁，快）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true", help="只跑控制组")
    ap.add_argument("--full", action="store_true",
                    help="动态跑全部 WATCHED（含两个慢门，十分钟级）；默认只跑快速三个，其余靠静态")
    a = ap.parse_args(argv)

    st = run_selftest()
    if st:
        # 控制组不通 = 本门自身不可信，不能再报别的结果。
        print("verify-no-forbidden-reads: FAIL（控制组失效：%d 项）——本门自身不可信"
              % len(st))
        for s in st:
            print("  " + s)
        return 20
    if a.selftest:
        print("verify-no-forbidden-reads: 控制组 PASS（必然违规样本转红 / 合规样本不误红）")
        return 0

    errs = static_check()
    meta: dict = {"mode": "static"}
    if not a.static:
        dyn, m = dynamic_check(full=a.full)
        errs += dyn
        meta.update(m)
        meta["mode"] = "static+dynamic"

    if a.json:
        print(json.dumps({"errors": errs, "meta": meta}, ensure_ascii=False, indent=2))
    else:
        if errs:
            print("verify-no-forbidden-reads: FAIL（%d 项）" % len(errs))
            for e in errs:
                print("  " + e)
        else:
            print("verify-no-forbidden-reads: PASS（门禁不会读禁读目录；运行期实测 0 次命中）")
    return 20 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
