#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check-card-drift.py —— 装机卡 vs 仓库卡的漂移检查（P7）。

事实基线（2026-10-15 实测，不是推测）：
  · ~/.omp/agent/RULES.md 与 kernel/04-console/cards/guest/全能专精指引.md
    sha256 完全一致（8f3b47b92ae1…）—— 装机形态是**卡片直写副本**，
    没有 `# >>> hubcore base >>>` 标记块，也没有 console 的 `# ==== 底模 ====` 分隔行。
  · ~/.omp/agent/PERSONALITY.md 与 base 池五张卡 sha 全不相等 —— 它就是漂移实例。
  · ~/.dsh/AGENTS.md 是 0 字节 —— 不是本包装的，算 SKIP。

判据（经五种形态实测）：
  · 入口文件存在且非空 → 与全部仓库卡逐行比，取 diff 最小的一张；
    diff == 0 → OK；diff > 0 → DRIFT（附卡名与行数）
  · 入口文件不存在 / 0 字节 → SKIP（不计入，也不误报）
  · 一个可比对象都没有（没装任何宿主）→ 11 UNVERIFIED，绝不等于 OK

退出码：0 全部一致 / 10 有漂移 / 11 无对象可比 / 12 脚本错误
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from difflib import SequenceMatcher

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
HOSTS_DIR = os.path.join(REPO, "kernel", "03-bundle")
sys.path.insert(0, HOSTS_DIR)

try:
    import hosts as hosts_mod
except Exception as exc:                                # noqa: BLE001
    print("check-card-drift: cannot import kernel/03-bundle/hosts.py: %r" % exc)
    raise SystemExit(12)

HOME = os.path.expanduser("~")


def _read_lines(p):
    try:
        with io.open(p, encoding="utf-8-sig", errors="replace") as f:
            t = f.read()
    except OSError:
        return None
    return t.replace("\r\n", "\n").split("\n")


_card_cache = {}


def _strip(ls):
    ls = list(ls)
    while ls and not ls[-1].strip():
        ls.pop()
    while ls and not ls[0].strip():
        ls.pop(0)
    return ls


def _ordered_diff(a, b):
    """顺序敏感的行差（SequenceMatcher 的 opcode 是 tuple，不能取 .size）。"""
    sm = SequenceMatcher(a=a, b=b, autojunk=False)
    return sum(j - i for tag, i, j, _i2, _j2 in sm.get_opcodes() if tag != "equal")


# ---------------- 真实形态常量（从安装器源码取，2026-10-15）----------------
# bundle: kernel/03-bundle/_bundle_lib.py
BASE_BEGIN, BASE_END = "# >>> hubcore base >>>", "# <<< hubcore base <<<"
GUEST_BEGIN, GUEST_END = "# >>> hubcore guest >>>", "# <<< hubcore guest <<<"
HUB_BEGIN, HUB_END = "# >>> hubcore hub >>>", "# <<< hubcore hub <<<"
# console 直写: kernel/04-console/server.py:_direct_text
CONSOLE_SEG = re.compile(r"(?m)^#\s*=+\s*(底模|指引|中枢)：\s*(.+?)\s*=+\s*$")
# 原样直写卡（omp 实测）: 文件头就是卡自己的头
CARD_HEADER = re.compile(r"(?m)^#\s*base:\s*(\S+)\s*$")
KIND_HEADER = re.compile(r"(?m)^#\s*kind:\s*(\S+)\s*$")

POOLS = ('base', 'guest', 'hub')
KIND_TO_POOL = {'底模': 'base', '指引': 'guest', '中枢': 'hub'}


def _card_by_name(name, prefer_pool=None):
    """按卡名（无扩展名）取仓库卡。prefer_pool 给定时只在该池找——
    绝不跨池回退（跨池回退会把合法其他宿主的卡当成别的池）。
    """
    key = (name or '').strip()
    if not key:
        return None, None
    for pool in ([prefer_pool] if prefer_pool else list(POOLS)):
        hit = _card_cache.get((pool, key))
        if hit is not None:
            return pool, hit
    return None, None


def _build_cache(cards):
    """[('base/xxx.md', lines)] → {('base','xxx'): lines}"""
    idx = {}
    for full, lines in cards:
        pool, fn = full.split('/', 1)
        idx[(pool, fn[:-3] if fn.endswith('.md') else fn)] = lines
    return idx


def _all_cards():
    out = []
    for pool in POOLS:
        d = os.path.join(REPO, "kernel", "04-console", "cards", pool)
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d)):
            if n.endswith(".md"):
                ls = _read_lines(os.path.join(d, n))
                if ls:
                    out.append(("%s/%s" % (pool, n), _strip(ls)))
    return out


def _blocks(text, begin, end):
    """按定界行（begin/end 各自独占一行）切出整块。

    返回 (closed, unclosed)；unclosed 是“有 begin 没有 end”的定界行行号（从 1 数）。
    ★ 2026-10-15 外部审计：旧写法把未闭合的块**直接丢弃**，于是“有 BASE_BEGIN、无 BASE_END”
    的入口产出零行 —— 在 omp 两张 OK 下仍返 0，完全不得知。
    """
    closed, unclosed = [], []
    cur, start, inside = [], 0, False
    for i, ln in enumerate(text.split("\n"), start=1):
        s = ln.strip()
        if s == begin:
            inside, cur, start = True, [], i
            continue
        if inside:
            if s == end:
                closed.append(cur)
                inside = False
            else:
                cur.append(ln)
    if inside:
        unclosed.append(start)
    return closed, unclosed


def _console_segments(ls):
    """返回 [(label, name, body_lines)]；body 到下一个 header 或 EOF。"""
    idx = []
    for k, ln in enumerate(ls):
        m = CONSOLE_SEG.match(ln)
        if m:
            idx.append((k, m.group(1), m.group(2).strip()))
    segs = []
    for i, (k, label, name) in enumerate(idx):
        stop = idx[i + 1][0] if i + 1 < len(idx) else len(ls)
        segs.append((label, name, ls[k + 1:stop]))
    return segs


def _bundle_parts(block, label_prefix):
    """block: 定界行之间的行。返回 (name, fingerprint, body_lines)。"""
    inner = [l for l in block]
    head = inner[0].strip() if inner else ""
    rest = inner[1:]
    fp = ""
    if rest and rest[0].strip().startswith("指纹："):
        fp = rest[0].strip()[len("指纹："):]
        rest = rest[1:]
    nm = head
    if label_prefix and nm.startswith(label_prefix):
        nm = nm[len(label_prefix):]
    # 底模：<名>（<hosts>）
    nm = re.sub(r"（.*?）\s*$", "", nm).strip()
    return nm, fp, rest


def _sha(s):
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _check_one(host, ef, ls, text):
    rows = []
    # 形态 3：bundle 标记块
    if any(m in text for m in (BASE_BEGIN, GUEST_BEGIN, HUB_BEGIN)):
        for begin, end, prefix, pool in ((BASE_BEGIN, BASE_END, "底模：", "base"),
                                         (GUEST_BEGIN, GUEST_END, "技能指引：", "guest")):
            closed, unclosed = _blocks(text, begin, end)
            for ln_no in unclosed:
                rows.append({'host': host, 'file': ef, 'pool': pool,
                             'status': 'DRIFT', 'diff_lines': None,
                             'note': 'unclosed block (line %d): %s present but %s absent'
                                     % (ln_no, begin, end)})
            for blk in closed:
                nm, fp, body = _bundle_parts(blk, prefix)
                _, cl = _card_by_name(nm, pool)
                if cl is None:
                    rows.append({'host': host, 'file': ef, 'pool': pool, 'card': nm,
                                 'status': 'DRIFT', 'diff_lines': None,
                                 'note': 'declared card not in repo'})
                    continue
                body_s = "\n".join(body)
                d = _ordered_diff(_strip(body_s.split("\n")), cl)
                fp_ok = (not fp) or (_sha(body_s) == fp)
                rows.append({'host': host, 'file': ef, 'pool': pool, 'card': nm,
                             'diff_lines': d, 'fingerprint_ok': fp_ok,
                             'status': 'OK' if (d == 0 and fp_ok) else 'DRIFT'})
        hclosed, hunclosed = _blocks(text, HUB_BEGIN, HUB_END)
        for ln_no in hunclosed:
            rows.append({'host': host, 'file': ef, 'pool': 'hub',
                         'status': 'DRIFT', 'diff_lines': None,
                         'note': 'unclosed block (line %d): %s present but %s absent'
                                 % (ln_no, HUB_BEGIN, HUB_END)})
        for blk in hclosed:
            rows.append({'host': host, 'file': ef, 'pool': 'hub',
                         'status': 'UNVERIFIED(no card mapping for hub block)'})
        if not rows:
            # 识别为 bundle 形态，但一个完整块/未闭行都没解出 → 不能算通过
            rows.append({'host': host, 'file': ef,
                         'status': 'UNVERIFIED(识别为 bundle 形态，但一个完整块都没解出)'})
        return rows
    # 形态 2：console 直写分隔行 —— 只比各段正文
    segs = _console_segments(ls)
    if segs:
        for label, nm, body in segs:
            pool = KIND_TO_POOL.get(label, '')
            _, cl = _card_by_name(nm, pool or None)
            if cl is None:
                rows.append({'host': host, 'file': ef, 'card': nm,
                             'status': 'DRIFT', 'diff_lines': None,
                             'note': 'declared card not in repo'})
                continue
            d = _ordered_diff(_strip(body), cl)
            rows.append({'host': host, 'file': ef, 'pool': pool, 'card': nm,
                         'diff_lines': d, 'status': 'OK' if d == 0 else 'DRIFT'})
        return rows
    # 形态 1：原样直写卡（文件头 = 卡自己的 # base: / # kind:）
    hb = CARD_HEADER.search(text)
    kb = KIND_HEADER.search(text)
    if hb and kb:
        nm = hb.group(1)
        pool = kb.group(1).strip()
        _, cl = _card_by_name(nm, pool if pool in POOLS else None)
        if cl is None:
            rows.append({'host': host, 'file': ef, 'card': nm,
                         'status': 'DRIFT', 'diff_lines': None,
                         'note': 'declared card not in repo'})
            return rows
        d = _ordered_diff(_strip(ls), cl)
        rows.append({'host': host, 'file': ef, 'pool': pool, 'card': nm,
                     'diff_lines': d, 'status': 'OK' if d == 0 else 'DRIFT'})
        return rows
    # 不认识 → 不猜（用户自己的入口文件）
    rows.append({'host': host, 'file': ef,
                 'status': 'UNVERIFIED(unrecognized form)'})
    return rows


def check():
    cards = _all_cards()
    _card_cache.clear()
    _card_cache.update(_build_cache(cards))
    if not cards:
        return 12, ['no repo cards found'], []
    rows = []
    for spec in hosts_mod.HOSTS:
        home = os.path.join(HOME, spec.rel.replace('/', os.sep))
        if not os.path.isdir(home):
            continue
        for ef in [f for f in (spec.entry, getattr(spec, 'entry_base', '')) if f]:
            p = os.path.join(home, ef)
            if not os.path.isfile(p):
                continue
            ls = _read_lines(p)
            if ls is None or not [x for x in ls if x.strip()]:
                rows.append({'host': spec.id, 'file': ef, 'status': 'SKIP(empty)'})
                continue
            sub = _check_one(spec.id, ef, ls, "\n".join(ls))
            if not sub:
                # 不允许“非空且已识别的入口 → 零行”的静默路径
                sub = [{'host': spec.id, 'file': ef,
                        'status': 'UNVERIFIED(已识别形态但解析出零段)'}]
            rows.extend(sub)

    drift = [r for r in rows if r['status'] == 'DRIFT']
    ok = [r for r in rows if r['status'] == 'OK']
    unv = [r for r in rows if r['status'].startswith('UNVERIFIED')]

    if drift:
        def _msg(r):
            if r.get('note'):
                return '%s %s: %s' % (r['host'], r['file'], r['note'])
            return '%s %s %s: %s line(s) differ' % (r['host'], r['file'],
                                                    r.get('card'), r.get('diff_lines'))
        msgs = [_msg(r) for r in drift]
        return 10, msgs, rows
    if not ok:
        hosts = sorted({r['host'] for r in unv})
        return 11, ['没有任何可核对的装机卡（未核对：%s）' % (', '.join(hosts) or '无')], rows
    if unv:
        # 混合：有核对通过的，但也有未核对的宿主 → 不能声称全宿主覆盖
        hosts = sorted({('%s/%s' % (r['host'], r['file'])) for r in unv})
        return 11, ['已核对 %d 段一致；但 %d 处宿主入口未核对（%s）——不宣称全宿主覆盖'
                   % (len(ok), len(unv), ', '.join(hosts))], rows
    return 0, ['all %d installed segment(s) match repo cards line-for-line' % len(ok)], rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", "--Json", "-json", "-Json", action="store_true",
                    dest="json", help="machine readable")
    a = ap.parse_args(argv)

    res = check()
    if len(res) == 3:
        rc, msgs, rows = res
    else:
        rc, msgs, rows = res, [], []

    if a.json:
        print(json.dumps({"rc": rc, "messages": msgs, "hosts": rows},
                         ensure_ascii=False, indent=2))
    else:
        tag = {0: "PASS", 10: "DRIFT", 11: "UNVERIFIED", 12: "ERROR"}[rc]
        print("check-card-drift: %s" % tag)
        for m in msgs:
            print("   " + m)
        for r in rows:
            if r["status"] in ("OK", "SKIP(empty)"):
                print("   · %s %s: %s%s" % (r["host"], r["file"], r["status"],
                      "" if r["status"] != "OK" else " (%s)" % r.get("card")))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
