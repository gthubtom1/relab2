# -*- coding: utf-8 -*-
"""修 auditor 的误报启发式，并区分真错/截断。

## 问题
第一版把「函数的一截」误判为 SYNTAX_ERR：
```
def fill_iat_in_target(...):
    ...
    while True:
        ilt_rva, ... = struct.unpack_from(...)   <- 块在这里被截断
```
报错是「unterminated triple-quoted string」—— 真实的语法错，
但根因是**文档只贴了片段**，不是文档写错了。

## 区分判据
真正的「写错了」vs「本来就只贴一段」：
  A. 报错行在块**末尾 3 行内** 且 块以「未闭合结构」结束（括号/引号/缩进悬空）
     -> 截断，标 TRUNCATED
  B. 报错行在块**中部** 且 该行本身语法就不成立
     -> 真错，标 SYNTAX_ERR
  C. 块首行以关键字开头（def/class/from/import/else/except/finally/return）
     -> 片段，标 FRAGMENT（除非块内有完整顶层调用）

## PowerShell 的「< 运算符保留」
那是 PowerShell 解析器把 `a < b` 当成了重定向符 —— 说明块内容
在文档里被改成了解析器不认的形态。这条是真错，要单独归类。
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

PY = r"D:\EXE\python\python.exe"
YARA = r"D:\Tools\yara\yara64.exe"
PS = ["powershell", "-NoProfile", "-Command"]

FENCE = re.compile(r"^```([a-zA-Z0-9_+-]*)[ \t]*\n(.*?)^```[ \t]*$",
                   re.S | re.M)

# 块首行若是这些关键字，说明它是从某个更大上下文里摘出来的片段
STARTS_AS_FRAGMENT = re.compile(
    r"^\s*(def |class |from \S+ import |import \w+$|else\s*:|"
    r"elif\s|except\b|finally\s*:|return\b|@|yield\b|lambda\s)")

# 「未闭合」信号
UNCLOSED = re.compile(r'(\(\s*$|\[\s*$|\{\s*$|"""\s*$|"""\s*|\'\'\'\s*$|'
                      r'f?\'\s*$|""\s*$)')
TRUNCATE_MSG = re.compile(
    r"unterminated|was never closed|expected .* before end-of-file|"
    r"unexpected EOF|invalid \S+", re.I)

PS_RESERVED_LT = re.compile(r"“[<]”运算符|“<”")

# 文档常用的尖括号占位符：<中文> / <IDENTIFIER> / <路径>
PLACEHOLDER = re.compile(r"<[^<>\n]{1,40}>")


def dec(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp936", errors="replace")


class Block:
    __slots__ = ("path", "line", "lang", "code", "raw")

    def __init__(self, path, line, lang, code, raw):
        self.path, self.line, self.lang = path, line, lang
        self.code, self.raw = code, raw


def extract_blocks(root):
    out = []
    for dp, dns, fs in os.walk(root):
        dns[:] = [d for d in dns
                  if d not in (".git", "node_modules",
                               "pyghidra_mcp_projects")]
        for f in fs:
            if not f.endswith(".md"):
                continue
            p = os.path.join(dp, f)
            try:
                t = io.open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            for m in FENCE.finditer(t):
                lang = (m.group(1) or "").lower()
                code = m.group(2)
                if not code.strip():
                    continue
                out.append(Block(p, t[:m.start()].count("\n") + 1,
                                lang, code, m.group(0)))
    return out


def _is_truncated(code, err_line, msg):
    """判断这个语法错是不是「块被截断」造成的。"""
    lines = [l for l in code.splitlines()]
    if err_line <= 0:
        return False
    total = len(lines)
    # 报错在末尾 3 行内
    near_end = err_line >= max(1, total - 2)
    # 且块末尾看起来没闭合
    tail = "\n".join(lines[max(0, total - 4):])
    looks_open = bool(UNCLOSED.search(tail))
    # 且报错信息本身像「没闭合」
    trunc_like = bool(TRUNCATE_MSG.search(msg))
    return near_end and (looks_open or trunc_like)


def classify_python(code, tmpdir, idx):
    f = os.path.join(tmpdir, "b%d.py" % idx)
    io.open(f, "w", encoding="utf-8", newline="\n").write(code)
    r = subprocess.run(
        [PY, "-c",
         "import ast,sys;"
         "src=open(sys.argv[1],encoding='utf-8').read();"
         "ast.parse(src);print('PARSE_OK')", f],
        capture_output=True, timeout=60)
    if r.returncode != 0:
        err = r.stderr.decode("utf-8", "replace")
        m = re.search(r"line (\d+)", err)
        rel = int(m.group(1)) if m else 0
        msg = ([l for l in err.splitlines() if "Error" in l]
               or [err.splitlines()[-1]])[0][:130]
        if _is_truncated(code, rel, msg):
            return ("TRUNCATED", msg, rel)
        # 块首行就是 def/class/else 等 -> 本来就是片段
        if STARTS_AS_FRAGMENT.match(code.splitlines()[0] if code.splitlines()
                                    else ""):
            return ("FRAGMENT", msg, rel)
        return ("SYNTAX_ERR", msg, rel)
    # 能解析 -> 编译
    r2 = subprocess.run([PY, "-m", "py_compile", f],
                        capture_output=True, timeout=60)
    if r2.returncode != 0:
        err = r2.stderr.decode("utf-8", "replace")
        m = re.search(r"line (\d+)", err)
        msg = ([l for l in err.splitlines() if "Error" in l]
               or [err.splitlines()[-1]])[0][:130]
        return ("COMPILE_ERR", msg, int(m.group(1)) if m else 0)
    has_def = bool(re.search(r"^\s*(def|class)\s", code, re.M))
    has_call = bool(re.search(r"^\s*\w[\w\.]*\s*\(", code, re.M))
    if has_def and not has_call:
        return ("FRAGMENT", "只有定义没有调用", 0)
    if not has_call and STARTS_AS_FRAGMENT.match(code.splitlines()[0]
                                                if code.splitlines() else ""):
        return ("FRAGMENT", "片段首行", 0)
    return ("RUNS", "", 0)


def classify_yara(code, tmpdir, idx, sample):
    f = os.path.join(tmpdir, "b%d.yar" % idx)
    io.open(f, "w", encoding="utf-8", newline="\n").write(code)
    r = subprocess.run([YARA, f, sample], capture_output=True, timeout=60)
    if r.returncode == 0:
        return ("RUNS", "", 0)
    err = dec(r.stderr).strip()
    last = err.splitlines()[-1][:130] if err else ""
    if not re.search(r"^\s*rule\s+\w+", code, re.M):
        return ("FRAGMENT", last or "无 rule 头", 0)
    if _is_truncated(code, 0, last):
        return ("TRUNCATED", last, 0)
    return ("SYNTAX_ERR", last, 0)


def classify_powershell(code, tmpdir, idx):
    f = os.path.join(tmpdir, "b%d.ps1" % idx)
    io.open(f, "w", encoding="utf-8-sig", newline="\r\n").write(code)
    script = (
        "$t=$null;$e=$null;"
        "[System.Management.Automation.Language.Parser]::ParseFile("
        "'%s',[ref]$t,[ref]$e)|Out-Null;"
        "if($e.Count -gt 0){"
        "  Write-Output ('ERR|line=' + $e[0].Extent.StartLineNumber "
        "+ '|' + $e[0].Message) } else { Write-Output 'PARSE_OK' }"
    ) % f.replace("'", "''")
    r = subprocess.run(PS + [script], capture_output=True, timeout=60)
    out = dec(r.stdout + r.stderr)
    if "PARSE_OK" in out:
        return ("RUNS", "", 0)
    m = re.search(r"ERR\|line=(\d+)\|(.*)", out)
    if m:
        rel, msg = int(m.group(1)), m.group(2).strip()[:130]
        # 「< 运算符保留」几乎总是**文档的尖括号占位符**（<异常项的名字片段>），
        # 不是写错了 —— PowerShell 把 < 当重定向符才报这个。
        # 判据：块里存在 <中文或标识符> 形态的占位符。
        if PS_RESERVED_LT.search(msg):
            if PLACEHOLDER.search(code):
                return ("FRAGMENT", "含尖括号占位符（文档惯例，非错误）", rel)
            return ("SYNTAX_ERR", "内容被改坏：" + msg, rel)
        if _is_truncated(code, rel, msg):
            return ("TRUNCATED", msg, rel)
        return ("SYNTAX_ERR", msg, rel)
    first = [l.strip() for l in out.splitlines() if l.strip()]
    return ("SYNTAX_ERR", first[0][:130] if first else out[:130], 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=r"C:\relab2\skillpack\skills")
    ap.add_argument("--sample", default=None)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix="docaudit2_")
    sample = args.sample
    if not sample or not os.path.exists(sample):
        sample = os.path.join(tmp, "s.bin")
        io.open(sample, "wb").write(
            b"MZ" + b"\x00" * 60 +
            b"This program cannot be run in DOS mode.")

    blocks = extract_blocks(args.root)
    by_lang = {}
    for b in blocks:
        by_lang[b.lang] = by_lang.get(b.lang, 0) + 1
    print("=== 抽取代码块（%s）===" % args.root)
    print("   共 %d 块" % len(blocks))

    targets = [b for b in blocks
               if b.lang in ("python", "py", "python3", "yara", "yar",
                             "powershell", "ps1")]
    print("\n=== 逐块检测 %d 块 ===" % len(targets))

    results = []
    done = [0]

    def work(item):
        i, b = item
        if b.lang in ("python", "py", "python3"):
            return classify_python(b.code, tmp, i)
        if b.lang in ("yara", "yar"):
            return classify_yara(b.code, tmp, i, sample)
        return classify_powershell(b.code, tmp, i)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(work, (i, b)): b for i, b in enumerate(targets)}
        for fut in as_completed(futs):
            b = futs[fut]
            done[0] += 1
            try:
                v, m, rel = fut.result()
            except Exception as e:
                v, m, rel = "ERROR", str(e)[:100], 0
            results.append({
                "path": os.path.relpath(b.path, args.root).replace(os.sep, "/"),
                "line": b.line, "lang": b.lang, "verdict": v, "msg": m,
                "rel_line": rel,
            })
            if done[0] % 300 == 0:
                print("   %d/%d" % (done[0], len(targets)))

    agg = {}
    for r in results:
        agg.setdefault(r["verdict"], []).append(r)

    print("\n=== 汇总 ===")
    for v in ("RUNS", "FRAGMENT", "TRUNCATED", "SYNTAX_ERR",
              "COMPILE_ERR", "ERROR"):
        n = len(agg.get(v, []))
        print("   %-12s %5d  (%.1f%%)"
              % (v, n, n / len(results) * 100 if results else 0))

    real = agg.get("SYNTAX_ERR", []) + agg.get("COMPILE_ERR", [])
    print("\n=== 真错（已排除片段/截断）: %d ===" % len(real))
    for r in real[:80]:
        print("   %s:%d  [%s]" % (r["path"], r["line"], r["lang"]))
        print("      %s" % r["msg"])

    trunc = agg.get("TRUNCATED", [])
    print("\n=== 截断片段（不算错，但建议标注）: %d ===" % len(trunc))
    for r in trunc[:20]:
        print("   %s:%d" % (r["path"], r["line"]))

    if args.json:
        with io.open(args.json, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "total_blocks": len(blocks), "by_lang": by_lang,
                "tested": len(results),
                "verdicts": {k: len(v) for k, v in agg.items()},
                "real_bugs": real, "truncated": trunc,
            }, ensure_ascii=False, indent=1))
        print("\n机读: %s" % args.json)
    print("\nTMP: %s" % tmp)
    return 1 if real else 0


if __name__ == "__main__":
    sys.exit(main())