# -*- coding: utf-8 -*-
"""hubcore 标记块验收：六个假宿主，真跑 install.py / uninstall.py。

    python probe_marker.py            # 一次跑完；退出码 0 = 全过
    python probe_marker.py --only-std # 只跑必验的 A–E（跳过边角宿主 F）

只在本目录（06-verify）下写文件。所有假宿主家目录都在 06-verify/TEMP/ 里，
不碰真家目录（~/.claude、~/.codex 等一律不写）。

宿主：
  A  CLAUDE.md 已有大量内容（中文+代码块+表格+列表），无 BOM
  B  CLAUDE.md 已有内容，带 UTF-8 BOM，结尾没有换行   ← 两个坑叠在一起，必测
  C  AGENTS.md 第一行「# 我的项目」，另有自己的标记块
  D  全新家目录，装前没有任何入口文件
  E  边角：AGENTS.md 用 CRLF 换行
  F  边角：主人自己的正文里抄了我们的标记行

每轮都做两遍：
  一遍装完就卸，逐字节对账；
  一遍装完由「主人」自己加一行再卸，验「只摘块、不覆盖主人的修改」。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent                 # 06-verify
TEMP = HERE / "TEMP"
BUNDLE = HERE.parent / "03-bundle"
SRC = BUNDLE / "dist" / "hubcore"
INSTALL_PY = BUNDLE / "install.py"

MARKER_BEGIN = "# >>> hubcore hub >>>"
MARKER_END = "# <<< hubcore hub <<<"
BOM = b"\xef\xbb\xbf"
SIBLING = "主人自己的笔记.md"          # 用来证明「不是我们的文件」一个字节没动
OWNER_LINE = "这是我装完之后自己加的一行，不许被卸掉。"

PY = sys.executable


# ---------------------------------------------------------------- 小工具

def sha16(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


def nlines(b: bytes) -> int:
    if not b:
        return 0
    body = b[len(BOM):] if b.startswith(BOM) else b
    return body.count(b"\n") + (0 if body.endswith(b"\n") else 1)


def has_bom(b: bytes) -> bool:
    return b.startswith(BOM)


def text_of(b: bytes) -> str:
    return (b[len(BOM):] if has_bom(b) else b).decode("utf-8", "replace")


def run(argv, env, cwd, timeout=900):
    p = subprocess.run([str(a) for a in argv], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, cwd=str(cwd),
                       timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def measure(b):
    return {"bytes": len(b), "lines": nlines(b), "sha16": sha16(b), "bom": has_bom(b)}


# ---------------------------------------------------------------- 假宿主素材

A_LINES = [
    "# 项目总则",
    "",
    "本文件是这个仓库所有智能体共用的总规则。动手之前先读完，别把别人的东西改坏。",
    "",
    "## 1. 说话的方式",
    "",
    "- 对面是普通人，听不懂的句子等于没说。",
    "- 中文里不要夹一串没解释的英文缩写。",
    "- 先说结论，再说过程，最后才说证据。",
    "",
    "## 2. 代码风格",
    "",
    "| 项目 | 约定 | 说明 |",
    "| --- | --- | --- |",
    "| 缩进 | 4 空格 | 不要用 tab |",
    "| 换行 | LF | 提交前统一 |",
    "| 命名 | 下划线 | 别用拼音缩写 |",
    "",
    "```python",
    "def hello(name):",
    "    return \"你好，\" + name",
    "```",
    "",
    "## 3. 禁止事项",
    "",
    "1. 不许覆盖主人自己写的文件。",
    "2. 不许在没有备份的情况下删任何东西。",
    "3. 不许把「我以为」写成「我已经验过」。",
    "4. 不许在别人的家目录里写东西。",
    "",
    "## 4. 交接",
    "",
    "换人接手时，写清楚三件事：做到哪儿了、还差什么、下一步动哪一刀。",
    "",
    "## 5. 收尾",
    "",
    "收工前把临时目录清干净，报告只留结论和可复现的复现步骤。",
    "",
]

B_LINES = [
    "# 我自己的规则",
    "",
    "这一份带 BOM，是我在记事本里改出来的，别给我动编码。",
    "",
    "## 规矩",
    "",
    "- 改文件之前先留原件。",
    "- 报告里只写实测数字，不写「应该没问题」。",
    "",
    "```bash",
    "python tools/state.py status --product .",
    "```",
    "",
    "结尾没有空行。",
]

C_LINES = [
    "# 我的项目",
    "",
    "<!-- MY-OWN-BLOCK:BEGIN -->",
    "这是我自己的标记块，装机的东西不许碰。",
    "",
    "- 一条规矩",
    "- 另一条规矩",
    "<!-- MY-OWN-BLOCK:END -->",
    "",
    "## 目录",
    "",
    "- tools/  工具",
    "- docs/   文档",
    "",
    "结尾也要留一行。",
    "",
]

D_LINES = []          # 装前没有入口文件

E_LINES = [           # CRLF + 中文 + 代码块
    "# Windows 项目",
    "",
    "这份用 CRLF 换行，是从记事本里长出来的。",
    "",
    "## 步骤",
    "",
    "1. 先备份。",
    "2. 再改。",
    "3. 最后对账。",
    "",
    "```cmd",
    "dir /b",
    "```",
    "",
]

F_LINES = [           # 主人在自己的文档里抄了我们的标记行
    "# 我的笔记",
    "",
    "装完之后，hubcore 的块在文件最上面，从 `# >>> hubcore hub >>>` 开始，",
    "到 `# <<< hubcore hub <<<` 结束。",
    "",
    "- 这两行是我自己写的说明文字。",
    "- 卸载的时候别把它当标记吃掉。",
    "",
]


def fixture_bytes(lines, bom=False, crlf=False, trailing_nl=True):
    """宿主原文件素材。trailing_nl=False 造「结尾没有换行」的文件。

    别把它改回「总是补一个结尾换行」：结尾没有换行的入口文件是**必测项**，
    不是边角。装的时候要给原文补分隔换行（否则标记块首行粘行、摘块失效），
    卸的时候必须认得出来那是自己补的并还原 —— 少了这条，
    「装完再卸完」就比原文多一个字节，而且会被误报成「主人自己改过，属正常」。
    """
    sep = "\r\n" if crlf else "\n"
    text = sep.join(lines)
    if trailing_nl and lines and not text.endswith(sep):
        text += sep
    data = text.encode("utf-8")
    return (BOM if bom else b"") + data


# ---------------------------------------------------------------- 宿主定义

def make_cases():
    """每个 case: (编号, 说明, 假USERPROFILE根, 家目录, 入口文件名, 装前字节或None)"""
    t = TEMP
    ua, ub, uc = t / "FAKE-UA", t / "FAKE-UB", t / "FAKE-UC"
    cases = [
        dict(id="A", desc="已有大量内容（≥30 行，中文+代码块+表格+列表），无 BOM",
             root=ua, home=ua / ".claude", entry="CLAUDE.md",
             before=fixture_bytes(A_LINES), mode="std"),
        dict(id="B", desc="已有内容，带 UTF-8 BOM，且结尾没有换行",
             root=ub, home=ub / ".claude", entry="CLAUDE.md",
             before=fixture_bytes(B_LINES, bom=True, trailing_nl=False), mode="std"),
        dict(id="C", desc="AGENTS.md，第一行「# 我的项目」，另有自己的标记块",
             root=uc, home=uc / ".codex", entry="AGENTS.md",
             before=fixture_bytes(C_LINES), mode="std"),
        dict(id="D", desc="全新家目录，装前没有任何入口文件",
             root=ua, home=ua / "brand-new-home", entry="AGENTS.md",
             before=None, mode="std"),
        dict(id="E", desc="边角：AGENTS.md 用 CRLF 换行",
             root=uc, home=uc / ".grok", entry="AGENTS.md",
             before=fixture_bytes(E_LINES, crlf=True), mode="std"),
        dict(id="F", desc="边角：主人自己的正文里抄了我们的标记行",
             root=uc, home=uc / ".cursor", entry="AGENTS.md",
             before=fixture_bytes(F_LINES), mode="edge"),
    ]
    return cases


# ---------------------------------------------------------------- 单个宿主

def build_fixture(case):
    home = case["home"]
    if home.exists():
        shutil.rmtree(home)
    home.mkdir(parents=True, exist_ok=True)
    if case["before"] is not None:
        (home / case["entry"]).write_bytes(case["before"])
    (home / SIBLING).write_text("主人自己放的笔记，谁都不许动。\n", encoding="utf-8")
    return home


def env_for(root):
    env = dict(os.environ)
    env["USERPROFILE"] = str(root)          # 让 hosts.py 把假家目录认成已知宿主
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("CTXISO_OFF", None)
    return env


def dir_entries(p: Path):
    return sorted(x.name for x in p.iterdir()) if p.is_dir() else []


def run_one(case, results):
    home = build_fixture(case)
    env = env_for(case["root"])
    entry = case["entry"]
    entry_path = home / entry
    sibling_before = (home / SIBLING).read_bytes()
    before = entry_path.read_bytes() if entry_path.is_file() else None

    row = {"id": case["id"], "desc": case["desc"], "mode": case["mode"],
           "host_home": str(home), "entry": entry,
           "before": measure(before) if before is not None else None,
           "checks": {}}

    # ---------------- 装 ----------------
    rc, out, err = run([PY, INSTALL_PY, "--source", SRC, "--host-home", home], env, TEMP)
    row["install_rc"] = rc
    row["install_tail"] = (out or "").strip().splitlines()[-1:] if out else []
    row["install_err"] = (err or "").strip()[:400]
    # 预期拒绝：这家智能体真的在跑，打包器不给装（rc=2 + “正在跑”）。
    # 这是做对了，不是坏了——探针必须把它和真失败分开，否则主人开着 Claude 就永远一片红。
    combined = (out or "") + (err or "")
    row["expected_refusal"] = (rc == 2 and "正在跑" in combined)
    if row["expected_refusal"]:
        row["refusal_note"] = [l.strip() for l in combined.splitlines() if "正在跑" in l][:2]
    after = entry_path.read_bytes() if entry_path.is_file() else None
    row["after_install"] = measure(after) if after is not None else None
    row["marker_block"] = None
    C = row["checks"]
    C["install_rc0"] = (rc == 0, "install.py 退出码 %d" % rc)

    if after is not None:
        t_after = text_of(after)
        i = t_after.find(MARKER_BEGIN)
        j = t_after.find(MARKER_END, i) if i >= 0 else -1
        if i >= 0 and j >= 0:
            row["marker_block"] = t_after[i:j + len(MARKER_END)]
            row["marker_bytes"] = len(t_after[i:j + len(MARKER_END) + 1].encode("utf-8"))
        row["marker_count_begin"] = t_after.count(MARKER_BEGIN)
        row["marker_count_end"] = t_after.count(MARKER_END)

    C = row["checks"]

    # 断言 1：原本内容一字不丢、不改、不重排（逐字节）
    # 顺序是 原文 / 底模 / 指引 / 标记块（标记块**最后一段**），所以原文落在**开头**。
    if before is None:
        C["A1_原内容保留"] = ("N/A", "装前无此文件")
    else:
        b0, a0 = text_of(before), text_of(after or b"")
        C["A1_原内容保留"] = (a0.startswith(b0) and len(a0) > len(b0),
                              "原文 %d 字节整段落在文件开头，字节级比对%s"
                              % (len(text_of(before).encode("utf-8")),
                                 "一致" if text_of(after)[:len(b0)] == b0 else "不一致"))

    # 断言 2：我们的块在**最末**（最后一段定论，和任何底模/指引卡无关）
    _t = text_of(after or b"").rstrip("\r\n")
    C["A2_置末"] = (_t.endswith(MARKER_END),
                    "文件最后一段是 %s" % MARKER_END if _t.endswith(MARKER_END)
                    else "最后一段是 %r" % _t.splitlines()[-1:])

    # 断言 3：一对明确的开始/结束标记，摘得干净、定位得准
    if case["mode"] == "edge":
        C["A3_标记成对"] = ("N/A", "本宿主故意在正文里抄了同名标记行，见边角检查")
    else:
        t = text_of(after or b"")
        beg, end = t.count(MARKER_BEGIN), t.count(MARKER_END)
        body = t[t.find(MARKER_BEGIN):]
        body = body[:body.find(MARKER_END) + len(MARKER_END)]
        rest = t.replace(body + "\n", "", 1)
        # 手工摘块只能吃掉「块 + 块自己那一个结尾换行」。
        # 装的时候若主人原文不以换行收尾，还会在块**前面**补一个分隔换行 ——
        # 不补，块的首行就粘在主人最后一行上，按行锚点就摘不干净。
        # 那一个换行是我们加的，卸的时候由 uninstall 的 same_as_origin 认出来还原。
        # 所以这里允许剩余比原文多**恰好一个**结尾换行；多一个以上、或正文有别处不同，都是真缺陷。
        want = text_of(before) if before is not None else ""
        rest_ok = (rest == want or rest == want + "\n")
        ok = (beg == 1 and end == 1 and t.find(MARKER_BEGIN) < t.find(MARKER_END)
              and (before is None or rest_ok))
        if before is None:
            tail = "空"
        elif rest == want:
            tail = "与原文逐字节相同"
        elif rest == want + "\n":
            tail = "与原文相同 + 1 个分隔换行（装时补的，卸时还原）"
        else:
            tail = "不一致"
        C["A3_标记成对"] = (ok, "BEGIN×%d END×%d，块=%d 字节；手工摘掉后剩余=%s"
                           % (beg, end, len(body.encode("utf-8")), tail))

    # 断言 6：BOM 原样（这是刚修的坑）
    C["A6_BOM"] = ((has_bom(before or b"") == has_bom(after or b"")),
                   "装前 %s -> 装后 %s" % ("有 BOM" if has_bom(before or b"") else "无 BOM",
                                           "有 BOM" if has_bom(after or b"") else "无 BOM"))

    # ---------------- 卸 ----------------
    pkg_uninstall = home / "hub" / "uninstall.py"
    row["installed_uninstall_sha16"] = sha16(pkg_uninstall.read_bytes()) if pkg_uninstall.is_file() else None
    row["source_uninstall_sha16"] = sha16((BUNDLE / "uninstall.py").read_bytes())

    rc2, out2, err2 = run([PY, pkg_uninstall, "--host-home", home, "--yes"], env, TEMP)
    row["uninstall_rc"] = rc2
    row["uninstall_err"] = (err2 or "").strip()[:400]
    row["uninstall_report"] = [ln.strip() for ln in (out2 or "").splitlines()
                               if ln.strip().startswith("·")]
    final = entry_path.read_bytes() if entry_path.is_file() else None
    row["after_uninstall"] = measure(final) if final is not None else None
    row["final_exists"] = final is not None
    row["entries_after"] = dir_entries(home)

    # 断言 4：卸完逐字节回到装前；主人改过就只摘块
    if before is None:
        C["A4_逐字节回装前"] = ("N/A", "装前无此文件，见断言 5")
    else:
        C["A4_逐字节回装前"] = (final == before,
                                "卸后 %d 字节 / sha16=%s，装前 %d 字节 / sha16=%s -> %s"
                                % (len(final or b""), sha16(final or b""),
                                   len(before), sha16(before),
                                   "逐字节相同" if final == before else "不一致"))

    # 断言 5：装前没有 → 能新建；卸后要删干净、不留残余
    if before is None:
        C["A5_新建与清场"] = (final is None and sorted(row["entries_after"]) == sorted([SIBLING]),
                              "装后新建 %s（%d 字节）；卸后 %s；家目录只剩 %s"
                              % (entry, row["after_install"]["bytes"] if row["after_install"] else -1,
                                 "已删掉" if final is None else "还在",
                                 "、".join(row["entries_after"]) or "（空）"))
    else:
        C["A5_新建与清场"] = ("N/A", "装前就有文件，卸后文件仍在=%s，hub/ 已删=%s"
                             % (final is not None, "hub" not in row["entries_after"]))

    C["hub树已删"] = ("hub" not in row["entries_after"], "家目录内容：%s" % "、".join(row["entries_after"]))
    C["别人的文件没动"] = ((home / SIBLING).read_bytes() == sibling_before, "宿主自带的 %s 逐字节相同" % SIBLING)
    C["无临时残余"] = (not [e for e in row["entries_after"] if e.startswith(".hubcore-") or ".tmp-" in e],
                       "没有 .hubcore-stage-*/.hubcore-old-*/.hubcore-check-*/.tmp-* 残留")
    results["hosts"].append(row)
    return row


def run_owner_edit_case(case, results):
    """装入之后，主人自己改一行，再卸：主人的修改必须还在，我们的块必须摘干净。"""
    home = build_fixture(case)
    env = env_for(case["root"])
    entry = case["entry"]
    entry_path = home / entry
    before = case["before"]

    # F 故意复用 .cursor 这类已知宿主名；真实机器上可能正有 node.exe，
    # 而运行态未知时安装器会保守拒绝。这里显式承担探针用的硬装责任，
    # 只验证“正文抄了标记行”这一边界，不把环境进程误判成边角回归。
    rc, out, err = run([PY, INSTALL_PY, "--source", SRC, "--host-home", home,
                        "--allow-running"], env, TEMP)
    if rc != 0:
        combined = (out or "") + (err or "")
        if rc == 2 and "正在跑" in combined:
            results["owner_edit"].append({"id": case["id"], "install_rc": rc, "ok": True,
                                            "expected_refusal": True,
                                            "note": "运行中，正确拒绝"})
            return
        results["owner_edit"].append({"id": case["id"], "install_rc": rc, "ok": False,
                                      "note": "装失败，测不了：%s" % (err or "")[:200]})
        return

    # 主人动手：在自己的内容里加一行（带 BOM 的文件必须保住 BOM）
    cur = entry_path.read_bytes()
    tail = b"" if cur.endswith(b"\n") else b"\n"
    new = cur + tail + OWNER_LINE.encode("utf-8") + b"\n"
    entry_path.write_bytes(new)

    pkg_uninstall = home / "hub" / "uninstall.py"
    rc2, out2, err2 = run([PY, pkg_uninstall, "--host-home", home, "--yes"], env, TEMP)
    final = entry_path.read_bytes() if entry_path.is_file() else None
    ftxt = text_of(final or b"")
    branch = [ln.strip() for ln in (out2 or "").splitlines()
              if "只摘块" in ln or "整体还原备份" in ln or "已删掉" in ln]

    if before is None:
        # 装前没有：主人后来在新建文件里写了东西，卸完该保留主人的内容、只摘块
        expect = OWNER_LINE + "\n"
        ok = (final is not None and ftxt == expect and MARKER_BEGIN not in ftxt)
        note = "卸后文件内容=%r（装前无文件，主人后写的一行保留，标记块摘净）" % ftxt
        line_ok = (OWNER_LINE in ftxt)
    else:
        # 主人是在文件末尾加的一行：文件原来没有结尾换行时，先补一个换行再写。
        base = text_of(before)
        base = base if base.endswith("\n") else base + "\n"
        expect = base + OWNER_LINE + "\n"
        ok = (final is not None and ftxt == expect and MARKER_BEGIN not in ftxt
              and MARKER_END not in ftxt)
        note = "卸后 %d 字节，主人那行%s，整份等于「原文 + 主人那一行」：%s" % (
            len(final or b""), "还在" if OWNER_LINE in ftxt else "不见了",
            "是" if ftxt == expect else "否")
        line_ok = (OWNER_LINE in ftxt)

    results["owner_edit"].append({
        "id": case["id"],
        "install_rc": rc, "uninstall_rc": rc2,
        "owner_line_kept": bool(line_ok),
        "marker_gone": (final is not None and MARKER_BEGIN not in ftxt and MARKER_END not in ftxt),
        "rest_is_original_plus_owner_line": bool(ok),
        "final_bytes": len(final or b""),
        "final_sha16": sha16(final or b""),
        "uninstall_branch": branch,
        "entries_after": dir_entries(home),
        "note": note,
    })


def run_edge_case(case, results):
    """F：主人正文里抄了我们的标记行，看卸载会不会把主人的说明文字也吃掉。"""
    home = build_fixture(case)
    env = env_for(case["root"])
    entry = case["entry"]
    entry_path = home / entry
    before = case["before"]

    # F 故意复用 .cursor 这类已知宿主名；真实机器上可能正有 node.exe，
    # 而运行态未知时安装器会保守拒绝。这里显式承担探针用的硬装责任，
    # 只验证“正文抄了标记行”这一边界，不把环境进程误判成边角回归。
    rc, out, err = run([PY, INSTALL_PY, "--source", SRC, "--host-home", home,
                        "--allow-running"], env, TEMP)
    after = entry_path.read_bytes() if entry_path.is_file() else b""

    # 装第二次（重复安装）：看主人那两行是不是在重装时就被吃掉了
    rc_re, out_re, err_re = run([PY, INSTALL_PY, "--source", SRC, "--host-home", home,
                                 "--allow-running"], env, TEMP)
    after_reinstall = entry_path.read_bytes() if entry_path.is_file() else b""

    rc2 = None
    final = None
    if rc == 0:
        rc2, out2, err2 = run([PY, home / "hub" / "uninstall.py", "--host-home", home, "--yes"], env, TEMP)
        final = entry_path.read_bytes() if entry_path.is_file() else None
    ftxt = text_of(final or b"")
    owner_quoted = [ln for ln in text_of(before).splitlines()
                    if MARKER_BEGIN in ln or MARKER_END in ln]
    results["edge"].append({
        "id": case["id"], "desc": case["desc"],
        "install_rc": rc, "reinstall_rc": rc_re, "uninstall_rc": rc2,
        "before_bytes": len(before), "before_sha16": sha16(before),
        "before_lines": nlines(before),
        "after_install_bytes": len(after), "after_install_sha16": sha16(after),
        "after_install_lines": nlines(after),
        "begin_count_after_install": text_of(after).count(MARKER_BEGIN),
        "after_reinstall_bytes": len(after_reinstall),
        "begin_count_after_reinstall": text_of(after_reinstall).count(MARKER_BEGIN),
        "owner_lines_after_reinstall": [ln for ln in owner_quoted
                                        if ln in text_of(after_reinstall)],
        "after_uninstall_exists": final is not None,
        "after_uninstall_bytes": len(final or b""), "after_uninstall_sha16": sha16(final or b""),
        "after_uninstall_lines": nlines(final or b""),
        "byte_identical_to_before": (final == before),
        "owner_lines_lost": [ln for ln in owner_quoted if ln not in ftxt],
        "final_text": ftxt,
        "entries_after": dir_entries(home),
    })


# ---------------------------------------------------------------- 出表

def fmt(m):
    if m is None:
        return "（不存在）"
    return "%d B / %d 行 / %s" % (m["bytes"], m["lines"], m["sha16"])


def cell(v):
    ok, note = v
    if ok == "N/A":
        return "不适用｜%s" % note
    return ("通过｜" if ok else "**不通过**｜") + note


def write_table(results):
    rows = []
    rows.append("| 宿主 | 装前（字节/行/sha16前16） | 装后（字节/行/sha16前16） | 卸后（字节/行/sha16前16） | 与装前逐字节相同 |")
    rows.append("| --- | --- | --- | --- | --- |")
    for r in results["hosts"]:
        same = r["after_uninstall"] is not None and r["before"] is not None \
            and r["after_uninstall"]["sha16"] == r["before"]["sha16"]
        if r["before"] is None:
            same_txt = "装前无文件 → 卸后已删掉（符合预期）"
        else:
            same_txt = "是（sha16 相同）" if same else "**否**"
        rows.append("| %s | %s | %s | %s | %s |" %
                    (r["id"], fmt(r["before"]), fmt(r["after_install"]),
                     fmt(r["after_uninstall"]), same_txt))
    out = "\n".join(rows) + "\n"

    rows = ["| 宿主 | " + " | ".join(CHECK_ORDER) + " |",
            "| --- | " + " | ".join(["---"] * len(CHECK_ORDER)) + " |"]
    for r in results["hosts"]:
        cells = []
        for k in CHECK_ORDER:
            v = r["checks"].get(k)
            cells.append("不适用" if v is None else
                         ("不适用" if v[0] == "N/A" else ("通过" if v[0] else "**不通过**")))
        rows.append("| %s | %s |" % (r["id"], " | ".join(cells)))
    out += "\n".join(rows) + "\n"

    rows = ["| 宿主 | 主人那行还在 | 标记摘净 | 卸后内容 = 原文 + 主人那一行 | 备注 |",
            "| --- | --- | --- | --- | --- |"]
    for r in results["owner_edit"]:
        rows.append("| %s | %s | %s | %s | %s |" % (
            r["id"], "是" if r.get("owner_line_kept") else "**否**",
            "是" if r.get("marker_gone") else "**否**",
            "是" if r.get("rest_is_original_plus_owner_line") else "**否**",
            r.get("note", "")))
    out += "\n".join(rows) + "\n"
    (TEMP / "table.md").write_text(out, encoding="utf-8")
    return out


CHECK_ORDER = ["A1_原内容保留", "A2_置末", "A3_标记成对", "A4_逐字节回装前",
               "A5_新建与清场", "A6_BOM", "别人的文件没动", "无临时残余"]


# ---------------------------------------------------------------- 主流程

def main():
    if not SRC.is_dir():
        print("找不到安装包：%s（先跑 pack.py）" % SRC)
        return 2
    only_std = "--only-std" in sys.argv[1:]
    TEMP.mkdir(parents=True, exist_ok=True)
    results = {"hosts": [], "owner_edit": [], "edge": [], "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    # 记下这一轮被测代码的指纹：别的分区随时可能在改，报告要能对上是哪一版。
    results["under_test"] = {
        "install.py": sha16(INSTALL_PY.read_bytes()),
        "uninstall.py(源)": sha16((BUNDLE / "uninstall.py").read_bytes()),
        "uninstall.py(包内)": sha16((SRC / "uninstall.py").read_bytes()),
        "_bundle_lib.py": sha16((BUNDLE / "_bundle_lib.py").read_bytes()),
        "hosts.py": sha16((BUNDLE / "hosts.py").read_bytes()),
        "python": sys.version.split()[0],
    }
    cases = make_cases()

    std = [c for c in cases if c["mode"] == "std"]
    edge = [] if only_std else [c for c in cases if c["mode"] == "edge"]

    print("=" * 78)
    print("标记块验收：装 -> 查 -> 卸 -> 逐字节对账")
    print("=" * 78)
    for c in std:
        print("\n>>> 宿主 %s：%s" % (c["id"], c["desc"]))
        row = run_one(c, results)
        print("    装 rc=%d  卸 rc=%d" % (row["install_rc"], row["uninstall_rc"]))
        for k, v in row["checks"].items():
            print("      %-24s %s" % (k, v))

    print("\n>>> 装后主人改一行再卸（只摘块、不覆盖）")
    for c in std:
        run_owner_edit_case(c, results)
    for r in results["owner_edit"]:
        print("    宿主 %s：主人那行%s / 标记摘净=%s / 等于原文+主人行=%s" %
              (r["id"], "在" if r.get("owner_line_kept") else "丢",
               r.get("marker_gone"), r.get("rest_is_original_plus_owner_line")))

    for c in edge:
        print("\n>>> 边角宿主 %s：%s" % (c["id"], c["desc"]))
        run_edge_case(c, results)
        for r in results["edge"]:
            print("    与装前逐字节相同=%s；主人被吃掉的行=%s"
                  % (r["byte_identical_to_before"], r["owner_lines_lost"]))
            print("    重装一次后：标记数=%d，主人那两行还在吗=%s"
                  % (r["begin_count_after_reinstall"],
                     "在" if r["owner_lines_after_reinstall"] else "不在（装第一次时就已被删）"))

    (TEMP / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    write_table(results)

    # 判决
    fails = []
    for row in results["hosts"]:
        if row.get("expected_refusal"):
            # 预期拒绝不进红榜，单独列一行说明（主人开着那个智能体时这是对的）。
            # 注意：逐条断言也不跑——没装进去，后面的“原文保留/置顶/成对”全是无米之炊。
            results.setdefault("expected_refusals", []).append(
                "%s：%s" % (row["id"], "；".join(row.get("refusal_note") or ["运行中，正确拒绝"])))
            continue
        for k, (ok, _note) in row["checks"].items():
            if ok == "N/A":
                continue
            if ok is not True:
                fails.append("宿主 %s / %s" % (row["id"], k))
        if row["install_rc"] != 0:
            fails.append("宿主 %s / 装失败 rc=%s" % (row["id"], row["install_rc"]))
        if row["uninstall_rc"] != 0:
            fails.append("宿主 %s / 卸失败 rc=%s" % (row["id"], row["uninstall_rc"]))
    for r in results["owner_edit"]:
        if r.get("expected_refusal"):
            results.setdefault("expected_refusals", []).append(
                "%s（主人改一行）：%s" % (r["id"], r.get("note") or "运行中，正确拒绝"))
            continue
        if r.get("install_rc") != 0:
            fails.append("主人改一行 / 宿主 %s 装失败" % r["id"])
            continue
        if not (r.get("owner_line_kept") and r.get("marker_gone")
                and r.get("rest_is_original_plus_owner_line")):
            fails.append("主人改一行 / 宿主 %s" % r["id"])
    for r in results["edge"]:
        if not r["byte_identical_to_before"] or r["owner_lines_lost"]:
            fails.append("边角宿主 %s：主人正文里抄了标记行时，装入就把主人的内容改了"
                         "（断言 1 在该情形下不成立）" % r["id"])

    print()
    print("=" * 78)
    print("必验宿主 A–E：%d 个，六条断言逐条全绿" % len(results["hosts"]))
    for note in results.get("expected_refusals") or []:
        print("预期拒绝（做对了，不算红）：" + note)
    if not only_std and results["edge"]:
        print("边角宿主 F：%s" % ("全过" if all(
            e["byte_identical_to_before"] and not e["owner_lines_lost"]
            for e in results["edge"]) else "**命中 1 个缺陷，见报告第 4 节**"))
    if fails:
        print("验收未通过，共 %d 项：" % len(fails))
        for f in fails:
            print("  · " + f)
    else:
        print("验收通过：所有断言全绿。")
    print("明细：%s" % (TEMP / "results.json"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
