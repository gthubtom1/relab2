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
import textwrap
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

# ★ 2026-10-10：全部改为「优先探测，找不到就用当前解释器 / PATH」。
#   这个脚本要同时在 Windows（本机 D:\Tools）和 Linux（CI ubuntu）上跑，
#   原来硬编码 Windows 路径会让 CI 上所有工具都「找不到」-> 全部 ERROR。
import shutil as _shutil


def _find(*cands):
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


PY = _find(_shutil.which("python"), sys.executable) or sys.executable
YARA = _find(_shutil.which("yara"), _shutil.which("yara64"))
# ★ 2026-10-10 扩展：R2-DocCodeAudit 统计出 bash 1993 / js 444 / sql 300 /
#   c 293 / json 175 块，第一版只覆盖 python+yara+powershell，漏掉大头。
BASH_CHECKER = _find(r"C:\Program Files\Git\bin\bash.exe",
                   _shutil.which("bash"))
NODE_CHECKER = _find(_shutil.which("node"))
JSON_CHECKER = True   # python 自带

PS = (["powershell", "-NoProfile", "-Command"]
      if _shutil.which("powershell") or os.name == "nt" else None)

FENCE = re.compile(r"^```([a-zA-Z0-9_+-]*)[ \t]*\n(.*?)^```[ \t]*$",
                   re.S | re.M)

# ★ 行级围栏匹配。同时支持反引号与 CommonMark 合法的波浪号（~~~）。
FENCE_LINE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})[ \t]*([a-zA-Z0-9_+-]*)[ \t]*$")

# 围栏语言标记 -> 检查器种类
LANG_ALIASES = {
    "python": "python", "py": "python", "python3": "python",
    "yara": "yara", "yar": "yara",
    "powershell": "powershell", "ps1": "powershell", "pwsh": "powershell",
    "bash": "bash", "sh": "bash", "shell": "bash", "console": "bash",
    "zsh": "bash",
    "javascript": "javascript", "js": "javascript", "mjs": "javascript",
    "cjs": "javascript", "typescript": "javascript", "ts": "javascript",
    "json": "json", "jsonc": "json",
    "sql": "sql",
}

# 块首行若是这些关键字，说明它是从某个更大上下文里摘出来的片段
# 「从中间开始」的块 —— 片段的真信号。注意不含 def/class。
MID_BLOCK_START = re.compile(
    r"^\s*(from \S+ import |import \w+$|else\s*:|"
    r"elif\s|except\b|finally\s*:|@|yield\s|lambda\s)")

STARTS_AS_FRAGMENT = re.compile(
    r"^\s*(def |class |from \S+ import |import \w+$|else\s*:|"
    r"elif\s|except\b|finally\s*:|return\b|@|yield\b|lambda\s)")

# 「未闭合」信号
UNCLOSED = re.compile(r'(\(\s*$|\[\s*$|\{\s*$|"""\s*$|"""\s*|\'\'\'\s*$|'
                      r'f?\'\s*$|""\s*$)')
# ★ 2026-10-10 修正：原来带 `invalid \S+`，它把 **`invalid syntax`** 也算成
#   「块被截断」—— 而 `invalid syntax` 恰恰是**最普通**的语法错。后果：
#   对抗组里 `def f(:` / 大写 .MD / ~~~ 围栏 三个真绕过全靠这一条放行。
#   「非法字面量」必须限定具体类型，不能用通配。
TRUNCATE_MSG = re.compile(
    r"unterminated|was never closed|expected .* before end-of-file|"
    r"unexpected EOF|"
    r"invalid (?:decimal|hexadecimal|binary|octal) literal|"
    r"invalid escape sequence|"
    r"non-UTF-?8 code|"
    r"invalid character", re.I)

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


def scan_fences(text):
    """行级扫围栏，报告未闭合围栏，并对列表内缩进围栏做 dedent。

    ★ 2026-10-10 对抗测试发现的假绿：旧实现只用一条正则匹配**成对**围栏
    (`^```([lang]*)\n(.*?)^```$`)。未闭合的围栏匹配不上，于是从开块那一行
    到文件末尾的**全部内容都不会被审计** —— 而那正是手滑最常发生的地方。
    实测：文件里一个未闭合 ```python + 后面一段真错代码 → 旧版报 exit 0。

    返回 (blocks, unclosed)；unclosed 是 [(相对路径, 行号, 语言)]。
    """
    lines = text.split("\n")
    blocks, unclosed = [], []
    stack = []          # [(char, ticks, open_line, lang, indent)]
    buf = []            # 当前块的正文
    for i, ln in enumerate(lines, 1):
        m = FENCE_LINE.match(ln)
        if not m:
            if stack:
                buf.append(ln)
            continue
        ticks, info = m.group(1), (m.group(2) or "").strip()
        indent = len(ln) - len(ln.lstrip())
        if stack:
            open_char, open_ticks, open_line, lang, _ind = stack[-1]
            # ★ 2026-10-10 修正：闭合必须**同字符类**。原来只比长度
            #   `len(ticks) >= open_ticks`，于是 ``` 块里的 ~~~ 会把块闭合掉
            #   —— CommonMark 明确规定不同字符的围栏不能互相闭合。
            #   后果是**整块代码连同其中的语法错一起消失**：
            #     ```python
            #     ~~~
            #     import os
            #     def lost(:
            #     ```
            #   实测抽出 0 个块、报「未闭合于第 7 行」、rc=0 —— 假绿。
            #   模糊测试实测这种组合造成 18/200 (9%) 的假绿。
            same_class = ticks[0] == open_char
            if same_class and len(ticks) >= open_ticks and not info:
                code = "\n".join(buf)
                # ★ 列表内缩进围栏：``` 前有空格时正文也带同样缩进。
                #   不处理直接喂编译器，整块会因「意外缩进」报语法错 ——
                #   那是 Markdown 排版，不是代码错。2026-10-10 实测 3 处此类误报。
                #
                #   ★ 关键：不能用 textwrap.dedent。它取所有非空行的**公共前缀**，
                #   而块内只要有一行顶格（很常见：Python 函数体外的那句调用），
                #   公共前缀就变成空字符串，dedent 变成**空操作**，缩进全部残留，
                #   整块依旧误报。模糊测试实测这一类必假红。
                #   正确做法：按**围栏自身的缩进量**逐行硬剥。
                if indent:
                    out_lines = []
                    for _l in code.split("\n"):
                        if _l[:indent].strip() == "":
                            out_lines.append(_l[indent:])
                        else:
                            out_lines.append(_l.lstrip())
                    code = "\n".join(out_lines)
                if code.strip():
                    blocks.append(Block(_CUR_PATH[0], open_line,
                                        lang.lower(), code, code))
                stack.pop()
                buf = []
            else:
                buf.append(ln)          # 嵌套 / 字面量 / 异类围栏
            continue
        stack.append((ticks[0], len(ticks), i, info, indent))
        buf = []
    for _c, _t, line_no, lang, _ind in stack:
        # ★ 保留语言标记：CI 输出会打「语言=(无)」，等于让人去猜。
        unclosed.append((line_no, lang))
    return blocks, unclosed


_CUR_PATH = [None]


def extract_blocks(root):
    out = []
    unclosed_total = []
    for dp, dns, fs in os.walk(root):
        dns[:] = [d for d in dns
                  if d not in (".git", "node_modules",
                               "pyghidra_mcp_projects")]
        for f in fs:
            # ★ 大小写不敏感：Windows 上 .MD 就是 .md，
            #   endswith(".md") 只认小写会让大写扩展名整个逃过审计。
            if not f.lower().endswith(".md"):
                continue
            p = os.path.join(dp, f)
            try:
                t = io.open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            _CUR_PATH[0] = p
            blocks, unc = scan_fences(t)
            out.extend(blocks)
            rel_p = os.path.relpath(p, root).replace(os.sep, "/")
            for line_no, lang in unc:
                unclosed_total.append((rel_p, line_no, lang))
    return out, unclosed_total


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
    """★ 判据顺序：先排除片段，**再**解析。

    2026-10-10 修正：片段判据原先放在 ast.parse 之后，
    而片段块**本来就解析不过**（缺 def、缺 import），
    于是提前 return 到 SYNTAX_ERR，判据形同虚设 —— 实测 5 处误判全是这个原因。
    """
    # ---- 前置：这是不是本来就编不起来的片段 ----
    first = code.splitlines()[0] if code.splitlines() else ""
    if re.search(r"片段|伪代码|pseudo|示意|对照示例|省略", code[:500], re.I):
        return ("FRAGMENT", "文档已标注为片段/伪代码", 0)
    # 函数体片段：顶层 return/yield/raise 却没有 def 包裹
    if re.search(r"^\s*(return|yield|raise)\b", code, re.M) \
            and not re.search(r"^\s*(def|class)\s", code, re.M):
        return ("FRAGMENT", "函数体片段（顶层 return，缺 def）", 0)
    # 「从中间开始」的代码块才是片段信号（else:/except:/@/lambda/yield…）。
    # ★ 不能用 def/class 开头当信号 —— 回测实测 `def f(:` 这种真语法错会被放行。
    # ★ 也不能用 `import \w+$` 单行判 —— 正常脚本首行就是 `import os`，
    #   回测实测这会把 `import os\n\ndef f(:` 整块放行（漏报）。
    if MID_BLOCK_START.match(first) and not re.search(
            r"^\s*(def|class)\s", code, re.M):
        return ("FRAGMENT", "从中间开始的代码块（else/except/@/lambda）", 0)
    # 顶层裸赋值：sc_addr = VirtualAllocEx(h, ...) 这类
    #（有 def/class/import 包裹的正常脚本不受影响）
    if not re.search(r"^\s*(def|class|import |from \S+ import |if |for |"
                     r"while |with |try:|@)\s*", code, re.M):
        if re.search(r"^\s*[A-Za-z_]\w*\s*(=[^=]|\+=|\.)", code, re.M):
            return ("FRAGMENT", "顶层裸赋值片段（无 import / def 包裹）", 0)

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
    # 到这里 ast.parse 与 py_compile 都已通过 —— 块是**语法完整**的。
    # 「只有定义没有调用」因此可以放心用来判片段：残缺函数体早在上面
    # 的 ast.parse 分支就报 SYNTAX_ERR 了，不会走到这里。
    has_def = bool(re.search(r"^\s*(def|class)\s", code, re.M))
    has_call = bool(re.search(r"^\s*\w[\w\.]*\s*\(", code, re.M))
    if has_def and not has_call:
        return ("FRAGMENT", "只有定义没有调用", 0)
    return ("RUNS", "", 0)


def classify_yara(code, tmpdir, idx, sample):
    if not YARA:
        # CI（Linux）可能没装 yara —— 跳过而不是报 ERROR
        return ("SKIP", "no yara binary", 0)
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
    if not PS:
        # Linux CI 没有 PowerShell —— 跳过
        return ("SKIP", "no powershell", 0)
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



# ★ 2026-10-10 bash 判据（两次修正后定稿）。
#
# 第一版误报 23 处，第二版仍误报 25 处。逐条读原文后发现**根因是尖括号占位符**：
#     python3 jwt_tool.py <token> -X k -pk public.pem
#     ffuf -u https://FUZZ.<domain>
#     agent-browser open <url>
# bash 把 `<` 当重定向符 -> 必然报 syntax error。
# 而这些块是**命令清单/示例**，本就不该当脚本编译。
#
# 定稿判据（宁漏勿误 —— 门禁一旦误报就会被人绕过，比漏报更糟）：
#   只有「无占位符 + 有 shebang 或控制流」的才做 bash -n
#   其余（命令清单、片段、含 <占位符>、Android 方言）一律 FRAGMENT
BASH_DIALECT = re.compile(r"#!/system/bin/sh|#!/bin/busybox|/system/bin|"
                          r"\btoybox\b|\bbusybox\b")

# ★ 2026-10-10 三次修正后定稿。以下逐条都是实测误报：
#   Java.perform(function(){...})      Frida JS，不是 bash
#   objection / sqlite / env / file   Frida 控制台命令，不是 shell
#   POST /api/register {...}          HTTP 请求伪码
BASH_NOT_BASH = re.compile(
    r"\bJava\.(perform|use|choose|openClassLoader)\b|"
    r"\bInterceptor\.|"
    r"^(?:objection|sqlite|env|ls|file|process|UI|webview|DUMP|"
    r"rpc\.exports)\b",          # Frida 控制台内建命令
    re.M)

# (gdb) / (lldb) / (gdbserver) 前缀 —— 调试器命令行，不是 shell 脚本
GDB_CONSOLE = re.compile(r"^\s*\((?:gdb|lldb|gdbserver|qemu|gdb-mi)\)\s",
                         re.M | re.I)

# <token> / <url> / <path> / <N> 形态的占位符（排除 <<heredoc 与 2>&1 这类真重定向）
ANGLE_PLACEHOLDER = re.compile(
    r"(?<!<)(?<!<<)(?<!2>&)(?<!&)(?:(?<=\s)|(?<=\")|(?<='))"
    r"<[A-Za-z_][\w.:/-]*>",
    re.M)


def _looks_like_script(code):
    """像完整 shell 脚本吗？（而不是命令清单 / 片段 / 含占位符的示例）

    ★ 关键：含尖括号占位符的**一定不是可运行脚本** —— bash 会把 < 当重定向。
    """
    lines = [l for l in code.split("\n") if l.strip()]
    # ★ shebang 是「完整脚本」的强信号，必须在行数判断**之前**判 ——
    #   否则 `#!/bin/bash\ncurl http://x/` 这种两行脚本会被误判成片段。
    if len(lines) <= 2 and not code.lstrip().startswith("#!"):
        return False
    if ANGLE_PLACEHOLDER.search(code):
        return False
    # 非 bash 方言：Frida JS / HTTP 伪码 / 控制台命令 / gdb 控制台
    if BASH_NOT_BASH.search(code):
        return False
    if GDB_CONSOLE.search(code):
        return False
    if re.match(r"^[A-Z]+\s+/\S+.*\{", code.strip()):
        return False        # HTTP 请求伪码: POST /api/... {json}
    # 裸 HTTP 动词行 —— 必须扫**每一行**（多行伪码块首行常是 `# 1. 抓包`）
    if re.search(r"^(?:GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+/\S",
                 code, re.M):
        return False        # HTTP 伪码：POST /api/register {...}
    # JSON 体后紧跟 `}` 收尾 = 请求伪码
    if re.search(r"^\s*\}\s*$", code, re.M) and \
            re.search(r'^\s*"[^"]+"\s*:', code, re.M):
        return False        # 请求体伪码
    # 编号步骤伪码（"1. Load binary" 这类，不是 shell）
    # 注意：shell 的 for 循环体也常用数字缩进，所以这里只排除「行首 1. 」形态
    steps = len(re.findall(r"^\d+\.\s+\S", code, re.M))
    if steps >= 2 and not code.lstrip().startswith("#!") \
            and not re.search(r"^\s*(for|while|if|case)\b", code, re.M):
        return False        # 操作步骤清单
    has_shebang = code.lstrip().startswith("#!")
    has_ctrl = re.search(r"^\s*(for|while|if|then|else|fi|do|done|"
                         r"function|case|esac)\b", code, re.M)
    cmd_lines = [l for l in lines
                 if re.match(r"^\s*[\w./-]+\s+\S", l)
                 and not l.strip().startswith("#")]
    return bool(has_shebang or has_ctrl or len(cmd_lines) >= 4)


def classify_bash(code, tmpdir, idx):
    """bash -n 只做语法检查，不执行；片段与非 bash 方言直接跳过。"""
    if not BASH_CHECKER:
        return ("SKIP", "no bash", 0)
    if BASH_DIALECT.search(code):
        return ("FRAGMENT", "Android/busybox shell 方言，非本机 bash", 0)
    if GDB_CONSOLE.search(code):
        return ("FRAGMENT", "gdb/lldb 调试器命令行，非 shell 脚本", 0)
    if BASH_NOT_BASH.search(code):
        return ("FRAGMENT", "Frida JS / 工具控制台命令，非 shell 脚本", 0)
    if not _looks_like_script(code):
        return ("FRAGMENT", "单行命令或片段，非完整脚本", 0)
    f = os.path.join(tmpdir, "b%d.sh" % idx)
    with io.open(f, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(code)
    r = subprocess.run([BASH_CHECKER, "-n", f], capture_output=True, timeout=60)
    if r.returncode == 0:
        return ("RUNS", "", 0)
    err = dec(r.stderr).strip()
    last = err.splitlines()[-1][:130] if err else ""
    m = re.search(r":(\d+):", err)
    rel = int(m.group(1)) if m else 0
    return ("SYNTAX_ERR", last, rel)


def classify_js(code, tmpdir, idx):
    """node --check 只解析不执行。"""
    if not NODE_CHECKER:
        return ("SKIP", "no node", 0)
    f = os.path.join(tmpdir, "b%d.js" % idx)
    with io.open(f, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(code)
    r = subprocess.run([NODE_CHECKER, "--check", f],
                       capture_output=True, timeout=60)
    if r.returncode == 0:
        return ("RUNS", "", 0)
    err = dec(r.stderr).strip()
    last = err.splitlines()[-1][:130] if err else ""
    # ★ 反混淆文档里大量出现「片段」：只贴一个 IIFE、只贴一个函数体、
    #   只贴一段 hook 包装。这些本就不该能独立解析。
    s = code.strip()
    if not re.search(r"\b(require|import|export|module\.exports)\b", s) \
            and not s.startswith("#!"):
        return ("FRAGMENT", "JS 片段（无模块系统调用），非完整程序", 0)
    return ("SYNTAX_ERR", last, 0)


def classify_json(code, tmpdir, idx):
    """json.loads 纯解析。

    ★ 2026-10-10 二次修正（前两版各误判一批）：
      1. `//` 出现在**字符串值里**（https://、http://attacker.com）不是注释
         -> 不能用 `'//' in code` 判 jsonc，会把 4 个正常 JSON 误判。
      2. 配置模板里的 `<占位符>`（"<tool-name>"）本来就不是合法 JSON
         -> 归 FRAGMENT，不是「语法错」。
      3. 含 `...` 省略号的示例同样归 FRAGMENT。
    """
    import json as _json
    # 真 jsonc：注释必须在字符串**之外**。逐字符扫，跳过字符串字面量。
    in_str = False
    esc = False
    has_comment = False
    for ch in code:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "/" and code.find("//", 0) >= 0:
            pass  # 具体判断见下
    for m in re.finditer(r'"(?:[^"\\]|\\.)*"|//|/\*', code):
        tok = m.group(0)
        if not tok.startswith('"') and tok in ("//", "/*"):
            has_comment = True
            break
    if has_comment:
        return ("FRAGMENT", "jsonc（行外注释），非严格 JSON", 0)
    # 多个 JSON 文档连写（示例常见）
    if re.search(r"\}\s*\n\s*\{", code) or re.search(r"\]\s*\n\s*\[", code):
        return ("FRAGMENT", "多个 JSON 文档连写", 0)
    s = code.strip()
    if not (s.startswith("{") or s.startswith("[")):
        return ("FRAGMENT", "单个 JSON 值，示例片段", 0)
    # 配置模板占位符
    if re.search(r':\s*"(?:<[^"]*>|\.\.\.)"', code):
        return ("FRAGMENT", "配置模板（<占位符> / ... 省略）", 0)
    try:
        _json.loads(code)
        return ("RUNS", "", 0)
    except Exception as e:
        return ("SYNTAX_ERR", str(e)[:130], 0)


def classify_sql(code, tmpdir, idx):
    """无本地 SQL 解析器 —— 只做启发式检查。

    ★ 2026-10-10 修正：判据顺序原本是「先查括号配平、再判是否 SQL 语句」，
      结果「闭合符号速查表」这种没有 SELECT/INSERT 的对照块，
      因为含裸 `')` `"))--` 就先被判成「括号不配平」（实测误报 4 处）。
      现在**先判是不是完整 SQL 语句**，不是就直接归 FRAGMENT。
    """
    stripped = re.sub(r"--[^\n]*", "", code)
    stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.S)
    stripped = re.sub(r'"(?:[^"\\]|\\.)*"', '""', stripped)
    stripped = re.sub(r"'(?:[^'\\]|\\.)*'", "''", stripped)

    # 1) 先看有没有完整 SQL 语句的骨架
    if not re.search(r"\b(SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM|"
                     r"CREATE|DROP|ALTER|WITH)\b", stripped, re.I):
        return ("FRAGMENT", "非完整 SQL 语句（对照表/片段/闭合速查）", 0)
    # 2) 文档自述为片段/伪代码
    if re.search(r"片段|伪代码|pseudo|示意|对照|速查", code[:500], re.I):
        return ("FRAGMENT", "文档已标注为片段/对照表", 0)
    # 3) 括号配平（此时字符串已剔除）
    #    ★ 但 SQL **注入示例**本来就是故意不配平的（'admin'-- 吃掉后半段），
    #      括号不配平恰恰是这类示例的教学要点，不能当语法错。
    if re.search(r"--\s*$|--'", code, re.M) or \
            re.search(r"UNION\s+SELECT|WAITFOR\s+DELAY|extractvalue|"
                       r"updatexml|db_link|LOAD_FILE|INTO\s+OUTFILE|"
                       r"INFORMATION_SCHEMA|pg_sleep|BENCHMARK\s*\(", code, re.I):
        return ("FRAGMENT", "SQL 注入示例（语法错误本身是示例要点）", 0)
    if stripped.count("(") != stripped.count(")"):
        return ("SYNTAX_ERR",
                "括号不配平 ( %d vs ) %d"
                % (stripped.count("("), stripped.count(")")), 0)
    # 4) 必须有分号结尾才是完整语句
    if not re.search(r";\s*$", stripped.strip()):
        return ("FRAGMENT", "SQL 语句片段（无分号结尾）", 0)
    return ("RUNS", "", 0)



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

    blocks, unclosed = extract_blocks(args.root)
    by_lang = {}
    for b in blocks:
        by_lang[b.lang] = by_lang.get(b.lang, 0) + 1
    print("=== 抽取代码块（%s）===" % args.root)
    print("   共 %d 块" % len(blocks))

    # ★ 未闭合围栏 = 从开块那一行到文件末尾**全部内容逃过审计**。
    #   对抗测试实测的假绿：未闭合围栏 + 后面一段真错代码 -> 旧版报 exit 0。
    if unclosed:
        print("\n!! 未闭合围栏 %d 处 —— 这些行往后的内容**没有被审计**："
              % len(unclosed))
        for rel_p, line_no, lang in unclosed[:40]:
            print("   %s:%d  语言=%s" % (rel_p, line_no, lang or "(无)"))
        print("   修法：补上闭合围栏，或改成文字/列表。")

    if not blocks:
        print("!! 一个可审计的代码块都没抽到 —— 扫描根或扩展名匹配有问题")
        return 2

    targets = [b for b in blocks if b.lang in LANG_ALIASES]
    print("   可审计 %d 块（其余为纯文本块）\n" % len(targets))
    work_queue = list(enumerate(targets))
    done = [0]

    def run_one(item):
        i, b = item
        L = LANG_ALIASES.get(b.lang)
        try:
            if L == "python":
                return classify_python(b.code, tmp, i)
            if L == "yara":
                return classify_yara(b.code, tmp, i, sample)
            if L == "powershell":
                return classify_powershell(b.code, tmp, i)
            if L == "bash":
                return classify_bash(b.code, tmp, i)
            if L == "javascript":
                return classify_js(b.code, tmp, i)
            if L == "json":
                return classify_json(b.code, tmp, i)
            if L == "sql":
                return classify_sql(b.code, tmp, i)
            return ("SKIP", "no checker", 0)
        except Exception as e:
            return ("ERROR", str(e)[:100], 0)

    results = []
    for n, item in enumerate(work_queue, 1):
        i, b = item
        v, m, rel = run_one(item)
        results.append({
            "path": os.path.relpath(b.path, args.root).replace(os.sep, "/"),
            "line": b.line, "lang": b.lang, "verdict": v, "msg": m,
            "rel_line": rel,
        })
        if n % 300 == 0:
            print("   %d/%d" % (n, len(targets)))

    agg = {}
    for r in results:
        agg.setdefault(r["verdict"], []).append(r)

    print("\n=== 汇总 ===")
    for v in ("RUNS", "FRAGMENT", "TRUNCATED", "SYNTAX_ERR",
              "COMPILE_ERR", "SKIP", "ERROR"):
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
                "unclosed": unclosed,
            }, ensure_ascii=False, indent=1))
        print("\n机读: %s" % args.json)
    print("\nTMP: %s" % tmp)
    # ★ 未闭合围栏也算失败：它让整段内容逃过审计，旧版当无事发生 -> 假绿。
    return 1 if (real or unclosed) else 0


if __name__ == "__main__":
    sys.exit(main())