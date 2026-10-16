#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify-capability-help.py —— 把 capability-index 的 help 兜底路径接入门禁。

为什么需要这道门（2026-10-15 独立审查 P1）：
  `capability-index.py --selftest-help` 自测了「没见过名字的工具靠 --help 被认出」这条路，
  但**没有任何门禁调用它** —— 于是回到「自检绿、实际探测路径坏、CI 不变红」。
  本仓已经因此烂过一次：`HELP_HINTS` 的 `>= 2` 阈值配上「每能力 1 条正则」，
  让整条 help 兜底结构上永不命中（本机实测 23 次探测 0 成功），
  索引里 help-probe 条目为 0、没有任何门为此变红。

本门做两件事：
  1. 跑 `capability-index.py --selftest-help`（正例必须识别 / 三个历史误报必须落回 unknown）；
  2. 端到端：造一棵合成工具树，放**名字与目录名都没见过**的 wrapper，跑真实
     `build(probe_help=True)`，断言 help-probe 真的识别出它们 —— 这是唯一能证明
     「运行时探测路径」还活着的手段（内存级自检证明不了子进程那条路）。

退出码：0 全过 / 20 有问题（blocking）
自带控制组：--selftest 用一份必然退化的判据样本，必须被本门抓到。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS_ROOT = os.path.dirname(HERE)
CAPIDX = os.path.join(SKILLS_ROOT, "scripts", "capability-index.py")
FORBIDDEN_DIRNAME = "_归档-禁读-历史文档"

# 合成工具树：名字、目录名都不在任何规则里，只有 --help 描述能力。
# help 文本写成真实工具会写的长度（多行、带用法）：`>= 2` 判据要求同一能力命中
# 2 条关键词，一行过短的帮助凑不齐 —— 那是判据的真实局限，不是 bug。
SYNTH = [
    ("mynewfw", "firmware-unpack",
     "MyNewFw 1.0\nUsage: mynewfw <image>\nExtract firmware images and dump the "
     "filesystem (squashfs / jffs2) from a firmware image."),
    ("myownfuzz", "fuzz-web",
     "MyFuzz 1.0\nUsage: myfuzz -u <url>\nDirectory brute force and virtual host "
     "discovery with a wordlist."),
    ("myowndecomp", "static-decompile",
     "MyDecomp 1.0\nUsage: myowndecomp <binary>\nDecompile a binary function to "
     "pseudocode and print the control flow graph."),
    ("mydbg", "dynamic-debug",
     "MyDbg 1.0\nUsage: mydbg -p <pid>\nInteractive debugger: set a breakpoint, "
     "step into, attach to a running process."),
]


def _write_wrapper(cli_dir: str, name: str, helptext: str) -> str:
    """写一个我们自己的 cli wrapper（只落在合成目录，不触及真实工具根）。

    为什么不用 .cmd：help 文本里天然含 `(` `)` `<` `>` `|` `&` ——
    这些都是 cmd 的特殊字符，即使转义也容易把输出改面目（rc=255、零输出）。
    改用 Python 做 wrapper：只在合成目录里，不动工具根。
    """
    path = os.path.join(cli_dir, name + ".cmd")
    py = os.path.join(cli_dir, name + ".py")
    with open(py, "w", encoding="utf-8", newline="") as f:
        f.write("import sys\n")
        f.write("if '--help' in sys.argv or '-h' in sys.argv:\n")
        f.write("    sys.stdout.write(%r)\n" % helptext)
    # .cmd 只负责找到 Python 并转发（参数经 python 传，不经 cmd 解析）
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write('@echo off\r\npython "%~dp0' + name + '.py" %*\r\n')
    return path


def _make_tree() -> str:
    tmp = tempfile.mkdtemp(prefix="caphelp-")
    cli = os.path.join(tmp, "cli")
    os.makedirs(cli, exist_ok=True)
    for name, _cap, helptext in SYNTH:
        _write_wrapper(cli, name, helptext)
    return tmp


def _build_over(tmp: str):
    """在合成工具树上跑真实 build(probe_help=True)。"""
    os.environ["REVERSE_TOOL_ROOT"] = tmp
    try:
        spec = importlib.util.spec_from_file_location("capidx_under_test", CAPIDX)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        m.search_roots = lambda: [Path(tmp)]
        return m.build(probe_help=True)
    finally:
        os.environ.pop("REVERSE_TOOL_ROOT", None)


def _found_by_help(idx: dict) -> dict:
    return {x["tool"]: c for c, v in idx["capabilities"].items()
            for x in v if x.get("how") == "help-probe"}


def synth_tree_check() -> tuple[list[str], dict]:
    errs: list[str] = []
    tmp = _make_tree()
    idx = _build_over(tmp)
    found = _found_by_help(idx)
    meta = {"probes": idx.get("help_probes"), "unknown": idx.get("unknown_count"),
            "found": found}
    for name, cap, _h in SYNTH:
        got = found.get(name)
        if got != cap:
            errs.append(f"合成工具 {name}: 期望经 help 兜底识别为 {cap}，实得 {got}")
    if (idx.get("help_probes") or 0) < len(SYNTH):
        errs.append(f"help 探测 {idx.get('help_probes')} 次 < 合成工具数 {len(SYNTH)}"
                    f"—— 探测没跑起来（例如 _safe_to_probe 全挡了）")
    if (idx.get("unknown_count") or 0) != 0:
        errs.append(f"unknown={idx.get('unknown_count')}（合成树上本该 0）—— 有工具没被归类")
    return errs, meta


def selftest() -> list[str]:
    """控制组：把 HELP_HINTS 清空（必然退化），本门必须转红。"""
    fails: list[str] = []
    tmp = _make_tree()
    os.environ["REVERSE_TOOL_ROOT"] = tmp
    try:
        spec = importlib.util.spec_from_file_location("capidx_ctl", CAPIDX)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        m.HELP_HINTS = []                      # 判据退化
        m.search_roots = lambda: [Path(tmp)]
        idx = m.build(probe_help=True)
    finally:
        os.environ.pop("REVERSE_TOOL_ROOT", None)
    found = _found_by_help(idx)
    if found:
        fails.append(f"控制组未转红：判据退化（HELP_HINTS=[]）后仍识别出 {sorted(found)}")
    return fails


def run_selftest_help() -> tuple[bool, str]:
    p = subprocess.run([sys.executable, CAPIDX, "--selftest-help"],
                       capture_output=True, text=True, timeout=300)
    return p.returncode == 0, (p.stdout or "") + (p.stderr or "")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true", help="只跑控制组")
    a = ap.parse_args(argv)

    st = selftest()
    if st:
        print("verify-capability-help: FAIL（控制组失效：%d 项）—— 本门自身不可信" % len(st))
        for s in st:
            print("  " + s)
        return 20
    if a.selftest:
        print("verify-capability-help: 控制组 PASS（判据退化即转红）")
        return 0

    errs: list[str] = []
    ok, out = run_selftest_help()
    if not ok:
        errs.append("capability-index --selftest-help 未通过：")
        errs.extend("    " + l for l in out.strip().splitlines()[:12])

    serrs, meta = synth_tree_check()
    errs += serrs

    if a.json:
        print(json.dumps({"errors": errs, "synth": meta}, ensure_ascii=False, indent=2))
    elif errs:
        print("verify-capability-help: FAIL（%d 项）" % len(errs))
        for e in errs:
            print("  " + e)
    else:
        print("verify-capability-help: PASS（help 兜底存活：合成工具树上 "
              f"{len(SYNTH)}/{len(SYNTH)} 个未见名工具被识别，"
              f"探测 {meta.get('probes')} 次 / unknown {meta.get('unknown')}）")
    return 20 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
