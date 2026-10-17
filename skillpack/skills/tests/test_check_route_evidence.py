#!/usr/bin/env python3
"""test_check_route_evidence.py —— `check-route-evidence.py` 的行为测试（R58）。

只测**行为**（给定输入 → 退出码 + 关键输出），不测实现（不 assert 内部函数名/正则）。

覆盖的判据：
  E1 缺 key / 非法 JSON            -> rc=20
  E2 status 非法                    -> rc=20
  E3 route 与目录名不一致           -> rc=20
  E4 pass 但 observed 太短          -> rc=20
  E5 pass 但 evidence_files 为空    -> rc=20
  E5 pass 但列出的文件不存在        -> rc=20
  E6 partial 但 blocked_by 太短     -> rc=20
  E7 evidence_files 越出路由目录    -> rc=20
  E8 占位 observed：默认 warn，--strict 下 rc=20
  --only 指定不存在的路由            -> rc=2（**回归测试**：修前这里是 rc=0 假绿）
  --only 指定存在的路由              -> rc=0
  合规 pass                         -> rc=0

用法：python skills/tests/test_check_route_evidence.py
退出码：0 全通过 / 1 有失败
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "scripts", "check-route-evidence.py")
PY = sys.executable

GOOD = {
    "route": "R01", "label": "x", "status": "pass",
    "sample": "s", "criterion": "c", "method": ["m"],
    "observed": ("真跑 jadx 1.5.3 反编译 6 个 .java，命中 1 处 AES key="
                 "8d127684cbc37c17616d806cf50473cc，解密明文 'I want to believe'"),
    "blocked_by": "", "evidence_files": ["evidence.txt"],
}


def make_route(root, name, payload, extra_files=("evidence.txt",)):
    d = os.path.join(root, name)
    os.makedirs(d, exist_ok=True)
    with io.open(os.path.join(d, "result.json"), "w", encoding="utf-8") as f:
        f.write(payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False))
    for ef in extra_files:
        full = os.path.join(d, ef)
        os.makedirs(os.path.dirname(full), exist_ok=True) if os.path.dirname(full) else None
        if not os.path.exists(full):
            with io.open(full, "w", encoding="utf-8") as f:
                f.write("raw command + raw output\n")
    return d


def run(args):
    p = subprocess.run([PY, SCRIPT] + args, capture_output=True, text=True,
                       errors="replace", timeout=120)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


results = []


def case(name, args, want_rc, must_contain=None, must_not=None):
    rc, out = run(args)
    ok = rc == want_rc
    detail = ""
    if not ok:
        detail = "rc=%d want=%d" % (rc, want_rc)
    if must_contain:
        for s in must_contain:
            if s not in out:
                ok = False
                detail += " | 缺 %r" % s
    if must_not:
        for s in must_not:
            if s in out:
                ok = False
                detail += " | 不该出现 %r" % s
    results.append((name, ok, detail, rc, out.strip().splitlines()[:2]))


tmp = tempfile.mkdtemp(prefix="r58-")
try:
    # ---- 正例 ----
    root_ok = os.path.join(tmp, "ok")
    make_route(root_ok, "R01", GOOD)
    case("合规 pass -> rc=0", ["--routes", root_ok], 0, must_contain=["violations=0"])

    # ---- E1 缺 key ----
    root = os.path.join(tmp, "e1")
    bad = dict(GOOD); bad.pop("criterion")
    make_route(root, "R01", bad)
    case("E1 缺必需 key -> rc=20", ["--routes", root], 20, must_contain=["E1"])

    # ---- E1 非法 JSON ----
    root = os.path.join(tmp, "e1b")
    make_route(root, "R01", "{not json")
    case("E1 非法 JSON -> rc=20", ["--routes", root], 20, must_contain=["E1"])

    # ---- E2 status 非法 ----
    root = os.path.join(tmp, "e2")
    make_route(root, "R01", dict(GOOD, status="done"))
    case("E2 status 非法 -> rc=20", ["--routes", root], 20, must_contain=["E2"])

    # ---- E3 route 串号 ----
    root = os.path.join(tmp, "e3")
    make_route(root, "R01", dict(GOOD, route="R99"))
    case("E3 route 与目录名不一致 -> rc=20", ["--routes", root], 20, must_contain=["E3"])

    # ---- E4 observed 太短 ----
    root = os.path.join(tmp, "e4")
    make_route(root, "R01", dict(GOOD, observed="ok"))
    case("E4 pass 但 observed 太短 -> rc=20", ["--routes", root], 20, must_contain=["E4"])

    # ---- E5 evidence_files 为空 ----
    root = os.path.join(tmp, "e5a")
    make_route(root, "R01", dict(GOOD, evidence_files=[]))
    case("E5 pass 但 evidence_files 为空 -> rc=20", ["--routes", root], 20, must_contain=["E5"])

    # ---- E5 列出的文件不存在 ----
    root = os.path.join(tmp, "e5b")
    make_route(root, "R01", dict(GOOD, evidence_files=["nope.txt"]), extra_files=())
    case("E5 evidence 文件不存在 -> rc=20", ["--routes", root], 20, must_contain=["E5"])

    # ---- E6 blocked_by 太短 ----
    root = os.path.join(tmp, "e6")
    make_route(root, "R01", dict(GOOD, status="partial", blocked_by="没有工具"))
    case("E6 partial 但 blocked_by 太短 -> rc=20", ["--routes", root], 20, must_contain=["E6"])

    # ---- E7 路径逃逸 ----
    root = os.path.join(tmp, "e7")
    make_route(root, "R01", dict(GOOD, evidence_files=["../../etc/passwd"]), extra_files=())
    case("E7 evidence 越出路由目录 -> rc=20", ["--routes", root], 20, must_contain=["E7"])

    # ---- E8 占位 observed ----
    root = os.path.join(tmp, "e8")
    make_route(root, "R01", dict(GOOD, observed=(
        "见 evidence.md（该文件里有完整的 jadx 1.5.3 反编译输出、openssl enc -d -aes-128-ecb "
        "解密命令与 xxd 明文十六进制，共 83 行原始输出；此处不再重复粘贴，只做指针）")))
    case("E8 占位 observed 默认只 warn -> rc=0", ["--routes", root], 0, must_contain=["warn"])
    case("E8 --strict 下 -> rc=20", ["--routes", root, "--strict"], 20, must_contain=["E8"])

    # ---- --only 回归：修前这里是假绿 ----
    root = os.path.join(tmp, "only")
    make_route(root, "R01", GOOD)
    make_route(root, "R02", dict(GOOD, route="R02"))
    case("--only 存在的路由 -> rc=0", ["--routes", root, "--only", "R01"], 0,
         must_contain=["checked=1"])
    case("--only 不存在的路由 -> rc=2（修前 rc=0 假绿）",
         ["--routes", root, "--only", "R999"], 2, must_contain=["不存在的路由", "R999"])
    case("--only 一半存在 -> rc=2 并列出缺的那个",
         ["--routes", root, "--only", "R01,R999"], 2, must_contain=["R999"])

    # ---- E0 路由集合核对（A1/A2）----
    root = os.path.join(tmp, "e0")
    make_route(root, "R1", dict(GOOD, route="R1"))
    make_route(root, "R2", dict(GOOD, route="R2"))
    cfg = os.path.join(tmp, "routing.json")
    with io.open(cfg, "w", encoding="utf-8") as f:
        json.dump({"routes": {"R1": {"label": "a"}, "R2": {"label": "b"}}}, f)
    case("E0 集合全对上 -> rc=0", ["--routes", root, "--expect-routes", cfg], 0,
         must_contain=["checked=2"])
    cfg2 = os.path.join(tmp, "routing2.json")
    with io.open(cfg2, "w", encoding="utf-8") as f:
        json.dump({"routes": {"R1": {}, "R2": {}, "R3": {}}}, f)
    case("E0 routing.json 多一条但没目录 -> rc=20 且点名 R3",
         ["--routes", root, "--expect-routes", cfg2], 20,
         must_contain=["E0", "R3"])
    cfg3 = os.path.join(tmp, "routing3.json")
    with io.open(cfg3, "w", encoding="utf-8") as f:
        json.dump({"routes": {"R1": {}}}, f)
    case("E0 有目录但 routing.json 没声明 -> rc=20 且点名 R2",
         ["--routes", root, "--expect-routes", cfg3], 20,
         must_contain=["E0", "R2"])

    # ---- 用法错误 ----
    case("--routes 不是目录 -> rc=2", ["--routes", os.path.join(tmp, "no-such-dir")], 2)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

fails = [r for r in results if not r[1]]
print("test_check_route_evidence: %d cases, %d passed, %d failed"
      % (len(results), len(results) - len(fails), len(fails)))
for name, ok, detail, rc, head in results:
    print("  [%s] %-48s rc=%d %s" % ("PASS" if ok else "FAIL", name, rc, detail))
    if not ok and head:
        for h in head:
            print("        | %s" % h)
sys.exit(1 if fails else 0)
