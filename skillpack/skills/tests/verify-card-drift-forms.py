#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify-card-drift-forms.py —— check-card-drift.py 的五种形态判据回归。

为什么要这一门（2026-10-15 审计）：
  check-card-drift.py 的 console / bundle 两条分支在本机**没有已装宿主会用**，
  所以只靠 `relab2.ps1 doctor` 永远只能证明「原样直写卡」那一种形态。
  一旦某台机器用 console 装机（`# ==== 底模：X ====`）或 bundle 装机
  （`# >>> hubcore base >>>` + 指纹），这两条分支此前是：`_segments` 未定义会崩、
  console 拿整份文件当单卡比、marker 把 pool 当卡名。
  本门用**合成负控**把五种形态和它们的坏例钉死，不依赖本机装了什么宿主。

判据（与安装器源码一一对应）：
  console  kernel/04-console/server.py:_direct_text  → `# ==== 底模|指引|中枢：<name> ====` + body
  bundle   kernel/03-bundle/_bundle_lib.py:412-427,485-494 → 定界行 / 头 / `指纹：<sha>` / body
  direct   原样直写卡 → 文件头就是卡自己的 `# base:` + `# kind:`

退出码：0 全过 / 3 有形状判错（阻塞）。
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "scripts", "check-card-drift.py")

spec = importlib.util.spec_from_file_location("ccd", SCRIPT)
ccd = importlib.util.module_from_spec(spec)
sys.modules["ccd"] = ccd
try:
    spec.loader.exec_module(ccd)
except SystemExit:                                       # 脚本自身 import 期不退出
    pass

fails: list[str] = []


def _load_cache():
    cards = ccd._all_cards()
    ccd._card_cache.clear()
    ccd._card_cache.update(ccd._build_cache(cards))
    return cards


def _body_of(name, pool):
    got_pool, cl = ccd._card_by_name(name, pool)
    if cl is None:
        fails.append("测试前置失败：仓库里没有 %s/%s" % (pool, name))
        return ""
    return "\n".join(cl)


def _one(host, ef, text):
    rows = ccd._check_one(host, ef, text.split("\n"), text)
    return rows


def _expect(cond, what):
    if not cond:
        fails.append(what)


def main() -> int:
    cards = _load_cache()
    _expect(bool(cards), "仓库卡一张都读不到（%s）" % ccd.REPO)

    base = _body_of("space-bunny-2", "base")
    guest = _body_of("全能专精指引", "guest")
    if not base or not guest:
        return 3

    # 1 console 正控
    t = "# ==================== 底模：space-bunny-2 ====================\n" + base + "\n"
    r = _one("H", "AGENTS.md", t)
    _expect(r and r[0]["status"] == "OK" and r[0]["diff_lines"] == 0,
            "console 正控应 OK，实得 %r" % (r[0] if r else None))

    # 2 console 负控：正文插一行 → DRIFT 且行数精确
    t2 = t.replace("\n\n", "\nDRIFTX\n\n", 1)
    r = _one("H", "AGENTS.md", t2)
    _expect(r and r[0]["status"] == "DRIFT" and r[0]["diff_lines"] == 1,
            "console 负控应 DRIFT/1 行，实得 %r" % (r[0] if r else None))

    # 3 bundle base 正控：指纹对
    fp = hashlib.sha256(base.encode("utf-8")).hexdigest()
    tb = "\n".join([ccd.BASE_BEGIN, "底模：space-bunny-2", "指纹：" + fp, base, ccd.BASE_END]) + "\n"
    r = _one("H", "AGENTS.md", tb)
    _expect(r and r[0]["status"] == "OK" and r[0]["fingerprint_ok"] is True,
            "bundle base 正控应 OK/指纹对，实得 %r" % (r[0] if r else None))

    # 4 bundle base 负控：指纹被改坏（正文仍对）→ DRIFT
    tb2 = tb.replace(fp, "0" * 64)
    r = _one("H", "AGENTS.md", tb2)
    _expect(r and r[0]["status"] == "DRIFT" and r[0]["fingerprint_ok"] is False,
            "bundle base 指纹负控应 DRIFT，实得 %r" % (r[0] if r else None))

    # 5 bundle guest 正控
    gfp = hashlib.sha256(guest.encode("utf-8")).hexdigest()
    tg = "\n".join([ccd.GUEST_BEGIN, "技能指引：全能专精指引", "指纹：" + gfp, guest, ccd.GUEST_END]) + "\n"
    r = _one("H", "RULES.md", tg)
    _expect(r and r[0]["status"] == "OK", "bundle guest 正控应 OK，实得 %r" % (r[0] if r else None))

    # 6 声明了仓库里没有的卡 → DRIFT(not in repo)，绝不静默通过
    t6 = "# ==================== 底模：不存在的卡 ====================\nbody\n"
    r = _one("H", "AGENTS.md", t6)
    _expect(r and r[0]["status"] == "DRIFT" and "not in repo" in (r[0].get("note") or ""),
            "未知名卡应 DRIFT(not in repo)，实得 %r" % (r[0] if r else None))

    # 7 未认识形态 → UNVERIFIED（不猜、不误红）
    r = _one("H", "AGENTS.md", "user's own config\nhello\n")
    _expect(r and r[0]["status"].startswith("UNVERIFIED"),
            "外来文件应 UNVERIFIED，实得 %r" % (r[0] if r else None))

    # 8 逐行的 direct 负控：整份卡（含自己的 # base:/# kind: 头）+ 插一行
    #    direct 形态的契约是「文件 == 卡，逐字节」，所以插一行应恰好报 1 行。
    t8 = base.replace("\n\n", "\nEXTRA\n\n", 1)
    r = _one("H", "PERSONALITY.md", t8)
    _expect(r and r[0]["status"] == "DRIFT" and r[0]["diff_lines"] == 1,
            "direct 负控应 DRIFT/1 行，实得 %r" % (r[0] if r else None))

    # 9 bundle 负控：有 BASE_BEGIN、无 BASE_END → 未闭合 → DRIFT（不许静默零行）
    t9 = "\n".join([ccd.BASE_BEGIN, "底模：space-bunny-2", "指纹：" + fp, base]) + "\n"
    r = _one("H", "AGENTS.md", t9)
    _expect(r and len(r) == 1 and r[0]["status"] == "DRIFT"
            and "unclosed" in (r[0].get("note") or ""),
            "未闭合 bundle 块应 DRIFT(unclosed)，实得 %r" % (r if r else None))

    # 10 零段兜底：只出现 HUB_BEGIN 而无任何闭合的 base/guest/hub 块
    t10 = ccd.HUB_BEGIN + "\nx\n"
    r = _one("H", "AGENTS.md", t10)
    _expect(bool(r) and all(x["status"].startswith(("DRIFT", "UNVERIFIED")) for x in r),
            "只识别到形态却解不出段时应 DRIFT/UNVERIFIED（不得零行），实得 %r" % (r if r else None))

    if fails:
        print("verify-card-drift-forms: FAIL (%d)" % len(fails))
        for f in fails:
            print("   " + f)
        return 3
    print("verify-card-drift-forms: PASS")
    print("   10 条判据：console 正/负、bundle base 正/指纹负、bundle guest 正、")
    print("              未知名卡 DRIFT、外来文件 UNVERIFIED、direct 负控、")
    print("              未闭合 bundle 块 DRIFT、零段兜底 DRIFT/UNVERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
