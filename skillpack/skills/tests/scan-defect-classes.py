#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan-defect-classes.py —— 把「已经吃过亏的缺陷类型」逐类变成检查，扫出**实数**。

为什么存在
----------
主人说过上百次「每次都说完成了，一用就出问题」，并明确说「**我担心还有其他类型的 bug**」。
信任不该建立在任何模型的自述上，只能建立在**别人能复跑的输出**上。
本脚本把已知吃亏过的缺陷类型逐条机械化，每条给出 `文件:行` 证据；输出是
"每一类发现多少处",而不是"没问题"。它**不做修复**，只负责让问题藏不住。

已知吃亏过的类型（每一条都在本仓真实发生过）
-------------------------------------------
  D1 文档里的工具命令行 与 真实可用参数不一致（`diec --extended` → 进程永不返回，卡满 240s）
  D2 PowerShell 跨版本行为差异（`2>&1` 混流：pwsh 7 与 PS 5.1 结论不同 → CI 红、本机绿）
  D3 本机绝对路径混进受版本控制的文档/技能卡（换机即过期）
  D4 调外部命令却不检查退出码（沉默失败）
  D5 静默吞异常（`except: pass` / 空 `catch {}`）
  D6 子进程调用缺 timeout（挂死没有上限）
  D7 被登记的工具/配方从未真跑过（只在文本里存在）

2026-10-16 二次收口：余项只有三种归宿，每种都留痕
----------------------------------------------
D1/D4/D5/D6 是**启发式**，它们同时打中「真缺陷」和「有意为之」，机器分不出来、人能。
所以每一条候选只允许三种处置：

  ① 真错 → 修（补退出码检查 / 补 timeout / 把静默改成记日志）
  ② 有意 → 在**那行代码旁边**写 `# scan-ok: <为什么这样是安全的>`，扫描器认账但**不吞掉**：
           输出里单独报「另有 N 处已登记豁免」，`--show-exempt` 逐条列理由
           （理由少于 8 个字符 = 不算豁免，照报 —— 空话登记不了任何东西）
  ③ 误报 → 收紧判据（`except: pass` 写在字符串/文档里不算；`Popen` 不吃 `timeout`
           参数，它的上限在随后的 `wait/communicate` 上；外部命令的语句常跨多行）

全量判定台账（逐条结论 + 证据）见 `docs/KNOWN-BOUNDARIES.md` §11。

用法
----
    python skills/tests/scan-defect-classes.py
    python skills/tests/scan-defect-classes.py --json
    python skills/tests/scan-defect-classes.py --only D3
    python skills/tests/scan-defect-classes.py --show-exempt     # 只列已登记豁免 + 理由
退出码：恒为 0（它是**扫描器**不是门）—— 是否要把某一类升级成会红的门，是人的决定。
"""
from __future__ import annotations

import argparse
import ast
import glob
import io
import json
import os
import re
import sys
import tokenize
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent
REPO = SKILLS.parent.parent

SKIP_PARTS = ("_归档-禁读-历史文档", os.sep + "work" + os.sep, "community-raw",
              "node_modules", "__pycache__", ".git", "_history")


def _files(patterns, roots=(REPO,)):
    out = []
    for root in roots:
        for pat in patterns:
            for f in glob.glob(str(Path(root) / pat), recursive=True):
                if any(s in f for s in SKIP_PARTS):
                    continue
                out.append(Path(f))
    return sorted(set(out))


def _read(p: Path) -> str:
    try:
        return io.open(p, encoding="utf-8-sig", errors="replace").read()
    except OSError:
        return ""


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(REPO)).replace(os.sep, "/")
    except ValueError:
        return str(p)


def _lines(txt: str) -> list[str]:
    """按**代码行**切分，行号与 `ast` 完全一致。

    ★ 2026-10-16 修：原来用 `str.splitlines()` —— 它还会在 \\v / \\f / \\x85 / U+2028 / U+2029
    上断开，而 Python 的 tokenizer 只认 \\n / \\r\\n / \\r。`parse-skill-frontmatter.py` 里就有
    一个 U+2028 和一个 U+2029，于是该文件的行号整体偏移 2 行：`# scan-ok:` 永远定位不到
    （实测：写了理由却被当成没写），报告出来的行号也会指错行。
    """
    return txt.replace("\r\n", "\n").replace("\r", "\n").split("\n")


# ---------------------------------------------------------------- D1
def d1_doc_vs_recipe() -> list[tuple[str, str]]:
    """文档里出现的「已登记工具 + 参数」是否与 tool-recipes.json 一致。

    启发式：找出 md 里形如 `diec <args>` / `capa <args>` 的行，把参数规范化后与配方比对；
    不一致的列为候选（人工复核；有些是示意而非可执行命令，故只报不判）。
    """
    hits: list[tuple[str, str]] = []
    try:
        rec = json.loads((SKILLS / "config" / "tool-recipes.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [("D1", "读不到 tool-recipes.json")]
    canon = {}
    for r in rec.get("recipes", []):
        canon.setdefault(r["tool"], []).append(" ".join(a for a in r.get("args", [])))
    for p in _files(("skillpack/skills/**/*.md",)):
        for i, line in enumerate(_lines(_read(p)), 1):
            for tool, arglists in canon.items():
                # 只认「命令位置的工具名 + 以 - 开头的选项」；这样 `r2 = s.post(` 这类变量名不会误报
                m = re.search(rf"(?:^|[`\s&;|])(?:{re.escape(tool)})(?:\.exe)?\s+(--?[A-Za-z][^\s`\"'|)]*)", line)
                if not m:
                    continue
                got = m.group(1)
                if any(got.split()[0] in a for a in arglists):
                    continue
                hits.append((rel(p), f"L{i} 文档写法 `{tool} {got}` 与配方 `{tool} {arglists[0]}` 不同 —— 需人工确认"))
    return hits, []


# ---------------------------------------------------------------- D2
def d2_cross_shell() -> list[tuple[str, str]]:
    """`2>&1` 把 stderr 合成 ErrorRecord，顺序在 pwsh 7 下不保证（本仓已因此红过一次）。"""
    hits = []
    for p in _files(("skillpack/skills/**/*.ps1",)):
        txt = _read(p)
        for i, line in enumerate(_lines(txt), 1):
            if "2>&1" not in line or line.strip().startswith("#"):
                continue
            # 只报"外部命令 + 2>&1 且随后按行序取用"的形态（纯日志转发不算）
            if re.search(r"@\(&\s*\S+\s+.*2>&1\)|=\s*&\s*\S+.*2>&1", line):
                hits.append((rel(p), f"L{i} `2>&1` 混流：{line.strip()[:90]}"))
    return hits, []


# ---------------------------------------------------------------- D3
def d3_abs_paths() -> list[tuple[str, str]]:
    """受版本控制的文档里出现**约定之外**的本机绝对路径。

    ★ 2026-10-16 主人当场纠正（我犯的错，记在这里）：
      `C:\\relab2` 与 `D:\\Tools` 是**定死的约定路径** —— 换机之后依然是这两个，
      所以文档/技能卡里写它们**不是缺陷**。我曾把它们当成"本机读数过期"批量改成 `<仓根>`，
      283 处，被主人一句「我换机后的地址也是 C:\\relab2 和 D:\\Tools，是定死的」打回，已全部回滚。
      本检查从此只报**约定之外**的机器路径（别人的用户名、别的盘、别的工具根）。
    """
    ALLOW = ("C:\\relab2", "D:\\Tools", "C:/relab2", "D:/Tools")
    allow_files = {"skillpack/skills/scripts/lib/toolmap.default.json", "docs/KNOWN-BOUNDARIES.md"}
    hits = []
    # ★ 2026-10-16 第二轮收窄：约定路径（C:\relab2 / D:\Tools）与**示例路径**
    #   （`D:\DOWNLOAD\app.apk`、"你的样本放这"这类示意）都不算缺陷；
    #   真正换机就会变、且会**指错地方**的是**用户目录**（用户名不同 / 别的机器）。
    pat = re.compile(r"[A-Za-z]:\\Users\\[^\\\s`\"']+", re.I)
    for p in _files(("skillpack/skills/**/*.md", "docs/**/*.md", "*.md")):
        r = rel(p)
        if r in allow_files or r.endswith("CHANGELOG.md"):
            continue
        for i, line in enumerate(_lines(_read(p)), 1):
            if not pat.search(line):
                continue
            if any(a in line for a in ALLOW):
                continue          # 约定路径 —— 跳过（不是缺陷）
            hits.append((r, f"L{i} 非约定机器路径：{line.strip()[:90]}"))
    return hits, []


# ---------------------------------------------------------------- 豁免登记（scan-ok）
# 缺陷类扫描是**启发式**：它同时打中「真缺陷」和「有意的静默」，机器分不出来、人能。
# 对后者的处置不是把判据放宽到打不中真缺陷，也不是把那行删掉 —— 而是在**那行代码旁边**
# 写清「为什么这样是安全的」，由扫描器认账：
#
#     & $cmd ...                      # scan-ok: <理由>
#     try { $p.Kill() } catch { }     # scan-ok: <理由>
#     except ValueError:
#         pass                        # scan-ok: <理由>
#
# 三条硬规矩（写成代码，不是口号）：
#   1. 理由**必填**且 ≥ MIN_REASON_LEN 个字符 —— 空理由/占位理由不豁免，照报；
#   2. 豁免不是「消失」：输出里单独报「另有 N 处已登记豁免」，`--show-exempt` 逐条列理由；
#   3. 只认注释（`#`）里的 `scan-ok:`，不认字符串里的（避免把文档正文当成豁免）。
MARKER_RE = re.compile(r"#\s*scan-ok:\s*(\S[^\n]*?)\s*$")
MIN_REASON_LEN = 8


def _marker(lines: list[str], start: int, end: int) -> str | None:
    """在 lines[start:end]（0-based 半开区间）里找**带理由**的 scan-ok 注释，没有返回 None。"""
    for line in lines[max(0, start):max(0, end)]:
        m = MARKER_RE.search(line)
        if m and len(m.group(1)) >= MIN_REASON_LEN:
            return m.group(1)
    return None


def _record(hits: list, exempt: list, path: str, why: str, reason: str | None) -> None:
    """一条候选的归宿：写了理由进 exempt，没写进 hits。豁免在输出里照样看得见。"""
    if reason:
        exempt.append((path, f"{why}｜scan-ok: {reason}"))
    else:
        hits.append((path, why))


# ---------------------------------------------------------------- 不可改文件的登记
# 有些命中落在**本任务不许改**的文件里（父代理在维护）：既不能在代码旁写 scan-ok，
# 也不能当没看见。这类条目在这里登记 —— 必须与命中**同一行**命中 needle，理由随
# `--show-exempt` 逐条打印。登记表自己也被检查（见 main）：没被任何命中用上的条目
# 会被当缺陷报出来，免得它变成一块长期遮丑的补丁。
JUDGED_ELSEWHERE: tuple[tuple[str, str, str], ...] = (
    ("skillpack/skills/tests/test-tool-recipes.py",
     "except Exception:  # noqa: BLE001",
     "该文件由父代理维护（本任务禁改）：这是 HANG 分支 —— 已经 taskkill 了整棵进程树，"
     "再 communicate 收尸；收不到不影响结论，紧接着就 return status=fail（失败不会变成成功）"),
)
_elsewhere_used: set[tuple[str, str]] = set()


def _elsewhere(relpath: str, line_text: str) -> str | None:
    """命中行是否落在 JUDGED_ELSEWHERE 里；命中则记一笔并返回理由。"""
    for path, needle, reason in JUDGED_ELSEWHERE:
        if relpath == path and needle in line_text:
            _elsewhere_used.add((path, needle))
            return reason
    return None


# ---------------------------------------------------------------- D4
def _ps_call_end(lines: list[str], i: int) -> int:
    """PowerShell 一条语句的真实边界：反引号续行、以 `|` 结尾的管道续行都算**同一条**。"""
    j = i
    while j + 1 < len(lines):
        body = lines[j].rstrip()
        if body.endswith("`") or body.endswith("|"):
            j += 1
            continue
        break
    return j


def _ps_noise(line: str) -> bool:
    return not line.strip() or line.strip().startswith("#")


def d4_exit_code() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """调用外部命令后 3 行内没有任何退出码检查（$LASTEXITCODE / $? / try-catch）。

    ★ 2026-10-16 收紧（原先会误报的两类形态）：
      · `& $x -a ` + 反引号续行 + `2>&1 | Tee-Object ...` 是**一条**语句，旧判据只看固定
        4 行窗口，于是把「语句结束后的第一行就取 $LASTEXITCODE」的 `smoke.ps1` 误报；
        现在按**整条语句**取窗口。
      · 注释行不吃行数（`apk-debug.ps1` 的 `$script:AdbRc = $LASTEXITCODE` 前面隔了两行注释）。
    """
    hits: list[tuple[str, str]] = []
    exempt: list[tuple[str, str]] = []
    for p in _files(("skillpack/skills/**/*.ps1",)):
        lines = _lines(_read(p))
        for i, line in enumerate(lines):
            # 只认 PowerShell 的调用运算符 `& $xxx`（那才是真的在执行外部程序；赋值不算）
            if line.strip().startswith("#") or not re.search(r"^\s*&\s+\$\w+", line):
                continue
            end = _ps_call_end(lines, i)
            window = list(lines[i:end + 1])
            j, seen = end + 1, 0
            while j < len(lines) and seen < 3:
                if not _ps_noise(lines[j]):
                    window.append(lines[j])
                    seen += 1
                j += 1
            if re.search(r"LASTEXITCODE|\$\?|try\s*\{|ExitCode", "\n".join(window)):
                continue
            why = f"L{i+1} 调外部命令后未见退出码检查：{line.strip()[:80]}"
            _record(hits, exempt, rel(p), why, _marker(lines, i - 1, end + 2))
    return hits, exempt


# ---------------------------------------------------------------- D5
# ★ 2026-10-16 降噪：只有「**数据/解析类**异常被静默吞掉」才是真危险 ——
#   那等于"错误被当成成功"（解析失败却继续跑）。而这两类静默是**合理**的：
#   · `KeyboardInterrupt` / `SystemExit`：Ctrl-C 退出不该报错
#   · `OSError` / `PermissionError` / `FileNotFoundError`：清理临时文件、写日志失败不该崩主流程
D5_DANGEROUS = ("ValueError", "KeyError", "IndexError", "JSONDecodeError", "UnicodeDecodeError",
                "AttributeError", "TypeError", "Exception", "ExceptionGroup")
D5_SAFE = ("KeyboardInterrupt", "SystemExit", "BrokenPipeError", "PermissionError",
           "FileNotFoundError", "OSError", "TimeoutExpired", "CalledProcessError")


def _d5_python(txt: str) -> list[tuple[int, str, int]]:
    """真的 `try/except` + 处理器体里**只有** `pass` 的位置（行号、异常类型、结束行）。

    ★ 2026-10-16 改用 AST：旧正则把**文档字符串里的 `except: pass`** 也算成缺陷 ——
    本脚本自己的 docstring、`verify-no-forbidden-reads.py` 里注入给子进程的审计钩子源码
    都是字符串。字符串不是调用，这类误报一刀切掉（顺带拿到准确行号）。
    """
    found: list[tuple[int, str, int]] = []
    try:
        tree = ast.parse(txt)
    except (SyntaxError, ValueError):
        return found
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if len(handler.body) != 1 or not isinstance(handler.body[0], ast.Pass):
                continue
            exc = ast.unparse(handler.type) if handler.type is not None else ""
            if any(s in exc for s in D5_SAFE) and not any(d in exc for d in D5_DANGEROUS):
                continue
            found.append((handler.lineno, exc, handler.body[0].end_lineno or handler.lineno))
    return found


def d5_swallow() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """静默吞异常：只报**数据/解析类**（真危险）；清理/日志/键盘中断类不报（合理静默）。"""
    hits: list[tuple[str, str]] = []
    exempt: list[tuple[str, str]] = []
    for p in _files(("skillpack/skills/**/*.py", "skills/**/*.py")):
        txt = _read(p)
        lines = _lines(txt)
        for lineno, exc, endline in _d5_python(txt):
            why = f"L{lineno} 静默吞**数据/解析类**异常：except {exc}: pass"
            reason = _marker(lines, lineno - 2, endline + 1)
            if not reason and 0 <= lineno - 1 < len(lines):
                reason = _elsewhere(rel(p), lines[lineno - 1])
            _record(hits, exempt, rel(p), why, reason)
    for p in _files(("skillpack/skills/**/*.ps1",)):
        txt = _read(p)
        lines = _lines(txt)
        for m in re.finditer(r"catch\s*\{\s*\}", txt):
            start = txt.count("\n", 0, m.start())
            end = txt.count("\n", 0, m.end())
            why = f"L{start + 1} 空 catch 块"
            _record(hits, exempt, rel(p), why, _marker(lines, start - 1, end + 2))
    return hits, exempt


# ---------------------------------------------------------------- D6
def _subprocess_calls(tree) -> list:
    """AST 里所有 subprocess.run/Popen/check_output/call 调用节点。"""
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
                and f.value.id == "subprocess"
                and f.attr in ("run", "Popen", "check_output", "call")):
            out.append(node)
    return out


def _enclosing_func(tree, target):
    """找 target 所在的最内层函数定义（拿不到就 None）。"""
    best = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(node):
                if sub is target:
                    best = node
    return best


def _has_wait_timeout(fn) -> bool:
    """函数体里有没有 `…wait(timeout=…)` 或 `…kill(`（Popen 正确写法）。"""
    if fn is None:
        return False
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "kill":
                return True
            if node.func.attr == "wait" and any(k.arg == "timeout" for k in node.keywords):
                return True
    return False


def d6_no_timeout() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """subprocess.run/Popen 不带 timeout（挂死无上限）。

    ★ 2026-10-16 判据 = **AST**（父代理改的，我沿用；别改回正则 —— 会复活一批误报）：
      · 正则会把 **docstring / 注释 / 字符串**里的 `subprocess.run(` 当成代码（实测
        `relab2-tools-mcp.py` 的改造说明 docstring 就被抓了）。AST 天然只看真代码。
      · `Popen` **没有** `timeout=` 参数 —— 用 `proc.wait(timeout=…)`(+`kill()`) 管超时是
        **正确**写法。旧版只看"同一括号里有没有 timeout"，把正确写法全报了。
        现在：`Popen` 所在函数里出现 `wait(timeout=)` 或 `kill(` → 不报。
    """
    hits: list[tuple[str, str]] = []
    exempt: list[tuple[str, str]] = []
    for p in _files(("skillpack/skills/**/*.py", "skills/**/*.py")):
        txt = _read(p)
        try:
            tree = ast.parse(txt)
        except (SyntaxError, ValueError):
            continue
        lines = _lines(txt)
        for node in _subprocess_calls(tree):
            if any(k.arg == "timeout" for k in node.keywords):
                continue
            f = node.func
            if f.attr == "Popen" and _has_wait_timeout(_enclosing_func(tree, node)):
                continue                              # Popen 正确写法：wait(timeout=)/kill 管超时
            why = f"L{node.lineno} subprocess.{f.attr} 调用未见 timeout"
            endline = getattr(node, "end_lineno", node.lineno) or node.lineno
            _record(hits, exempt, rel(p), why, _marker(lines, node.lineno - 2, endline + 1))
    return hits, exempt


# ---------------------------------------------------------------- D7
def d7_never_run() -> tuple[list[tuple[str, str]], list[str]]:
    """配方表里的工具，是否有真跑过它（本门跑一次就知道；这里只报"没有配方"的已登记工具）。

    ★ 2026-10-16 工具层审计后收口：配方表新增 `_no_recipe`（探测层 / `KNOWN_TOOLS` 里存在、
    **故意不给配方**的 id + 理由）。于是每个已登记 id 只剩三种归宿，缺一即报：
      ① 有配方            → 真跑过（`test-tool-recipes.py` 每次把每条配方真跑一遍）
      ② 在 `_no_recipe`   → 有理由（GUI/启动器、本机实测不可用、别名孪生、本机没装）
      ③ 都没有            → **漏项**，报出来
    另外两条自相矛盾也报：既在 `_no_recipe` 里又有配方；`_no_recipe` 的理由短于 8 字（空话登记不了任何东西）。
    """
    hits: list[tuple[str, str]] = []
    exempt: list[str] = []
    rec_path = "skillpack/skills/config/tool-recipes.json"
    try:
        rec = json.loads((SKILLS / "config" / "tool-recipes.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], []
    have = {r["tool"] for r in rec.get("recipes", [])}
    norec = rec.get("_no_recipe") or {}
    tb = _read(SKILLS / "scripts" / "relab2-tools-mcp.py")
    m = re.search(r"KNOWN_TOOLS\s*=\s*\[(.*?)\]", tb, re.S)
    known = set(re.findall(r'"([^"]+)"', m.group(1))) if m else set()
    for t in sorted(known - have):
        if t in norec:
            exempt.append((rec_path, f"已登记工具 `{t}` 无配方但已在 `_no_recipe` 登记理由："
                                     f"{str(norec[t])[:80]}"))
            continue
        hits.append((rec_path, f"已登记工具 `{t}` 既没有配方、也没进 `_no_recipe` —— "
                               "从没被真跑过，参数形态未知，连『为什么不用跑』都没写"))
    for t in sorted(set(norec) & have):
        hits.append((rec_path, f"`{t}` 既在 `_no_recipe` 里写了不跑的理由、又有配方 —— 自相矛盾，删一边"))
    for t, why in sorted(norec.items()):
        if len(str(why).strip()) < 8:
            hits.append((rec_path, f"`_no_recipe` 里 `{t}` 的理由只有 {len(str(why).strip())} 字（<8）—— 空话登记不了任何东西"))
    return hits, exempt


CHECKS = [
    ("D1", "文档命令行 vs 配方表", d1_doc_vs_recipe),
    ("D2", "PowerShell 跨版本混流", d2_cross_shell),
    ("D3", "本机绝对路径混入文档", d3_abs_paths),
    ("D4", "外部命令不查退出码", d4_exit_code),
    ("D5", "静默吞异常", d5_swallow),
    ("D6", "子进程缺 timeout", d6_no_timeout),
    ("D7", "登记了却从未真跑", d7_never_run),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-show", type=int, default=8)
    ap.add_argument("--show-exempt", action="store_true",
                    help="只列已登记豁免（`# scan-ok: <理由>`）—— 看理由，不看结论")
    a = ap.parse_args()

    result = {}
    for cid, title, fn in CHECKS:
        if a.only and cid != a.only:
            continue
        try:
            hits, exempt = fn()
            result[cid] = {"title": title, "hits": hits, "exempt": exempt}
        except Exception as e:  # noqa: BLE001
            result[cid] = {"title": title, "hits": [("scan", f"扫描自身报错：{type(e).__name__}: {e}")],
                           "exempt": []}

    # 登记表不能烂：带 --only 时只看了一部分类，判不出失效，所以只在全量扫描时查。
    if not a.only:
        stale = [f"{p} :: {n}" for p, n, _r in JUDGED_ELSEWHERE if (p, n) not in _elsewhere_used]
        if stale:
            result["JUDGED"] = {"title": "不可改文件的豁免登记已失效（对应行/代码已变）",
                                "hits": [("skillpack/skills/tests/scan-defect-classes.py", s) for s in stale],
                                "exempt": []}

    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print("缺陷类型扫描（**扫描器不是门**：它只负责把问题列出来，是否升级成会红的门由人决定）")
    print(f"范围: {rel(REPO)}（已排除 禁读区 / work / community-raw / _history）\n")
    total = 0
    for cid, data in result.items():
        hits = data["hits"]
        total += len(hits)
        if a.show_exempt:
            print(f"[{cid}] {data['title']}: 已登记豁免 {len(data['exempt'])} 处")
            for f, why in data["exempt"][:a.max_show]:
                print(f"      {f} :: {why}")
            if len(data["exempt"]) > a.max_show:
                print(f"      … 另有 {len(data['exempt']) - a.max_show} 处（--max-show N 可看全）")
            continue
        print(f"[{cid}] {data['title']}: {len(hits)} 处")
        for f, why in hits[:a.max_show]:
            print(f"      {f} :: {why}")
        if len(hits) > a.max_show:
            print(f"      … 另有 {len(hits) - a.max_show} 处（--max-show N 可看全）")
        if data["exempt"]:
            print(f"      （另有 {len(data['exempt'])} 处**已登记豁免**：注释里写明了"
                  f"「为什么这样是安全的」，--show-exempt 可逐条核对理由）")
    print(f"\n合计 {total} 处候选。**每一条都要人工复核**（D1/D4/D6 是启发式，会有误报）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
