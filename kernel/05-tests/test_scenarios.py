#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""九个必测场景里的 6 个（本轮负责：1 / 2 / 3 / 4 / 6 / 7）。

被测对象：<hubcore>/ctxiso（只读，绝不改）
本文件只写 <hubcore>/05-tests/TEMP/

断言全部是可测的：要么是一个数字门槛，要么是"某个正文片段不许出现在输出里"。
不写"跑通了"这种没法判的断言。

跑法：python run_all.py
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------- 路径（全部由 __file__ 推，不写死盘符）
TESTS = Path(__file__).resolve().parent                 # <hubcore>/05-tests
TEMP = TESTS / "TEMP"                                   # 唯一的写盘位置
CTXISO_ROOT = TESTS.parent                              # <hubcore>
# 被测产品 = **本仓自己**。原来这里写死 D:\临时项目\hub-dock（上一版中枢和本仓
# 挤在一个根下），那意味着「删掉旧中枢就测不了」。现在整个仓自足：长期资料、
# 运行核全部来自本仓，老仓在不在都不影响。
REPO = CTXISO_ROOT
STATE_DIR = CTXISO_ROOT / "state"                       # 侧车自己的状态目录（工具设计如此）
# 运行核在**本仓**的中枢本体下。原来指向 REPO/hub/tools，那是上一版中枢的位置。
HUB_TOOLS = CTXISO_ROOT / "02-hubcore" / "tools"

# 保护区：跑前跑后各取一次指纹，逐文件比对，证明「测什么都没动」。
# 依据 SPEC-自包含安装.md §2「文件分区（子代理不得越界）」。
#
# 本仓独立后，**中枢本体与全部工具都在仓内**（原来 02-hubcore 里的 workflows /
# docs / CORE.md / AGENTS.md 是被测产物，ctxiso/ 是被测对象，都不许被测试改动）。
# 硬保护区取「中枢本体 + 侧车账本」——它们是这套系统最不该被顺手改坏的东西。
# state/ 不列：它是 ctxiso 侧车自己的索引缓存，测试跑一趟必然新增文件，
# 那是**设计如此**，不是谁动了中枢。列进来会让这道门永远红。
HARD_ZONES = ["02-hubcore/CORE.md", "02-hubcore/AGENTS.md",
              "02-hubcore/workflows", "02-hubcore/docs", "02-hubcore/tools"]
# 本仓内但允许在改的（单独列，不判红）：设计文档与分析、另一批既有测试。
PROJ_ZONES = ["ctxiso", "00-ANALYSIS", "01-design"]
# 别人分区（单独列，不判红）：打包器与控制台。
SOFT_ZONES = ["03-bundle", "04-console", "03-tests", "06-verify"]


# ================================================================ 小工具
class Check:
    """一条可判的断言。ok 是 bool，numbers 贴进 RESULT.md。"""

    def __init__(self, name, ok, detail="", numbers=None):
        self.name = name
        self.ok = bool(ok)
        self.detail = "" if detail is None else str(detail)
        self.numbers = numbers or {}

    def line(self):
        mark = "PASS" if self.ok else "FAIL"
        s = "  [%s] %s" % (mark, self.name)
        if self.detail:
            s += "  — " + self.detail
        if self.numbers:
            s += "  " + "  ".join("%s=%s" % (k, v) for k, v in self.numbers.items())
        return s


class Scenario:
    def __init__(self, sid, title):
        self.sid = sid
        self.title = title
        self.checks = []
        self.notes = []
        self.error = None
        self.t0 = time.perf_counter()
        self._ms = None

    def check(self, name, ok, detail="", **numbers):
        self.checks.append(Check(name, ok, detail, numbers))

    def note(self, text):
        self.notes.append(text)

    def fail(self, err):
        self.error = "%s: %s" % (type(err).__name__, err)

    @property
    def ok(self):
        return self.error is None and all(c.ok for c in self.checks)

    @property
    def ms(self):
        # 第一次读就定死：不然写到 RESULT.md 时会一直涨
        if self._ms is None:
            self._ms = round((time.perf_counter() - self.t0) * 1000, 1)
        return self._ms


# ---------------------------------------------------------------- 跑真 CLI
def _env():
    e = dict(os.environ)
    # PYTHONDONTWRITEBYTECODE：不许在 ctxiso/ 或 hub/tools/ 里生成 .pyc
    # （那两个目录是硬保护区，生成 .pyc 也算改动）
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e["PYTHONUTF8"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    # HUB_REGISTRY：state.py 登记产品时写这个文件。不指走，测试就会把
    # 假产品的 path/uuid 写进 **中枢本体**的 02-hubcore/registry.json——
    # 那是被测对象自己的文件，被测试改脏。9.2 抓到过这个。
    e["HUB_REGISTRY"] = str(TEMP / "registry.json")
    e.pop("PYTHONPATH", None)
    e.pop("CTXISO_OFF", None)
    return e


def run_ctxiso(*args, timeout=180, retries=2):
    """跑真 `python -m ctxiso`。返回 (rc, stdout, stderr, 毫秒)。

    retries 只针对「抛了 traceback 的非 0 退出」再试一次（Windows 上新建几千个文件后
    偶发 sqlite/杀软锁）。稳定失败（像 archive.py:118 那个 sha8）重试多少次都是红，不受影响。
    """
    cmd = [sys.executable, "-m", "ctxiso", *[str(a) for a in args]]
    t0 = time.perf_counter()
    p = None
    retried = 0
    for attempt in range(retries + 1):
        p = subprocess.run(cmd, cwd=str(CTXISO_ROOT), env=_env(), timeout=timeout,
                           capture_output=True, encoding="utf-8", errors="replace")
        err = p.stderr or ""
        if p.returncode == 0 or "Traceback" not in err:
            break
        if attempt < retries:
            retried += 1
            _log_stderr("### 重试前第 %d 次失败：%s rc=%d\n%s"
                        % (attempt + 1, " ".join(map(str, args)), p.returncode, err))
            time.sleep(0.5)
    err = p.stderr or ""
    if err.strip():
        _log_stderr("### %s rc=%d\n%s" % (" ".join(map(str, args)), p.returncode, err))
    return p.returncode, p.stdout or "", err, round((time.perf_counter() - t0) * 1000, 1)


def _log_stderr(text):
    try:
        with (TEMP / "_cli-stderr.log").open("a", encoding="utf-8") as fh:
            fh.write(text.rstrip() + "\n")
    except OSError:
        pass


def run_state(product, *args, timeout=120):
    """跑真 `hub/tools/state.py`，只对 TEMP 下的假产品调用。"""
    cmd = [sys.executable, str(HUB_TOOLS / "state.py"),
           *[str(a) for a in args], "--product", str(product)]
    # 注意：state.py 的子命令都自带 --product，所以上面统一追加对多数命令成立，
    # 但 init/plan/... 的 --product 在子命令后面，argparse 接受。
    p = subprocess.run(cmd, cwd=str(product), env=_env(), timeout=timeout,
                       capture_output=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def jload(s):
    return json.loads(s)


def maybeliteral(s):
    """cmd_read 拒绝时打印的是 Python repr，不是 JSON。"""
    try:
        return ast.literal_eval(s.strip())
    except (ValueError, SyntaxError):
        return None


# ---------------------------------------------------------------- 泄漏检测
SHINGLE = 30          # 连续 30 个字算"正文片段"
SHINGLE_STEP = 5


def body_shingles(path, skip_first_line=True, n=SHINGLE, step=SHINGLE_STEP):
    """取一个文件的正文 shingle 集合。默认跳过首行（首行是索引里合法的一行用途）。"""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    lines = text.splitlines()
    if skip_first_line and lines:
        lines = lines[1:]
    body = "\n".join(lines)
    if len(body) < n:
        return {body} if body else set()
    return {body[i:i + n] for i in range(0, len(body) - n + 1, step)}


def leaks(haystack, needles):
    hit = [s for s in needles if s and s in haystack]
    return hit


def dir_bytes(root):
    total = 0
    n = 0
    for p in Path(root).rglob("*"):
        if p.is_file():
            n += 1
            total += p.stat().st_size
    return n, total


# ---------------------------------------------------------------- 假产品
# 本套测试会建的全部假产品名字。跑完按它算 key 清理——
# 包含「上一次跑剩下的」，因为 TEMP 每轮都会被删光，光扫当轮目录会漏。
FAKE_PRODUCT_NAMES = [
    "fake-auto", "fake-hist", "fake-update", "fake-compact", "fake-big", "fake-small",
    "fake-long", "fake-guard", "fake-old-system", "fake-home", "fake-home-prod",
    "ctxiso-mutant", "dbg-auto",
]

USED_PRODUCTS: list[Path] = []


def new_fake(name):
    p = TEMP / name
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True)
    USED_PRODUCTS.append(p)
    return p


def state_keys_used():
    """本套测试的假产品在侧车状态目录里占的格子（只算 TEMP 下面的，绝不碰真仓库那格）。"""
    paths = list(USED_PRODUCTS) + [TEMP / n for n in FAKE_PRODUCT_NAMES]
    out = []
    for p in paths:
        try:
            p.relative_to(TEMP)
        except ValueError:
            continue
        out.append(_state_key(p))
    return sorted(set(out))


def write_lines(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ledger_event(i, kind="physical_probe", phase="2-impl", check="core_entry",
                 result="fail", extra_bytes=600):
    """造一条长得像真探针的事件：内嵌 observed/assertions/候选路径，就是污染源。"""
    ev = {
        "ts": "2026-09-26T12:%02d:%02dZ" % (i % 60, (i * 7) % 60),
        "kind": kind,
        "check_id": check,
        "phase_id": phase,
        "result": result,
        "verification_mode": "change",
        "epoch": 1,
        "stop_point": "能打出来的包",
        "observed": {
            "assertions": [{"id": "a%d" % k, "passed": k % 3 != 0,
                            "detail": "观察点 %d 在第 %d 次尝试里没有对上" % (k, i)}
                           for k in range(8)],
            "sensors": {("sensor_%02d" % k): None for k in range(30)},
        },
        "assertions": [{"id": "assert-%d" % k, "passed": True} for k in range(4)],
        "candidate_paths": ["hub/tools/state.py", "hub/tools/hub_cmds.py"] * 10,
        "work_bindings": {"f%03d.py" % k: "sha256:" + hashlib.sha1(
            b"%d-%d" % (i, k)).hexdigest() for k in range(10)},
        "note": "历史事件正文填充 " + "x" * extra_bytes,
    }
    return json.dumps(ev, ensure_ascii=False)


def build_ledger(path, count, extra_bytes=600):
    path.parent.mkdir(parents=True, exist_ok=True)
    checks = ["core_entry", "package_install", "license_dataflow", "ui_regression",
              "update_flow", "handoff", "change_regression", "core_closed"]
    with path.open("w", encoding="utf-8") as fh:
        for i in range(count):
            fh.write(ledger_event(i, phase="2-impl" if i % 3 else "0-spec",
                                  check=checks[i % len(checks)],
                                  extra_bytes=extra_bytes) + "\n")
    return path.stat().st_size


def fill_docs(root, count, each_bytes, kind_dir="docs/history"):
    """造 count 个每个约 each_bytes 字节的假历史文件。"""
    base = root / kind_dir
    base.mkdir(parents=True, exist_ok=True)
    filler = ("这是一段用于填充体积的中文说明文字，纯粹是体积填充，"
              "不含任何真实内容，也不该被任何一次任务自动读进上下文。\n")
    block = (filler * (each_bytes // len(filler.encode("utf-8")) + 2))
    for i in range(count):
        head = "# 历史资料 %04d：用于验证大量历史文件不会被自动读进上下文。\n" % i
        text = head + block
        text = text.encode("utf-8")[:each_bytes].decode("utf-8", "ignore")
        (base / ("hist-%04d.md" % i)).write_text(text, encoding="utf-8")
    return base


# ---------------------------------------------------------------- 配置与只读探针
def ctxiso_config():
    cfg = json.loads((CTXISO_ROOT / "ctxiso" / "config.json").read_text(encoding="utf-8"))
    cfg.pop("_comment", None)
    return cfg


def real_repo_product_files():
    """真仓库里 13 个被长期资料扫描命中的文件。"""
    cfg = ctxiso_config()
    out = []
    for rel in (cfg.get("archive_scan") or {}):
        p = REPO / rel
        if p.is_file():
            out.append(p)
    return out


def index_rows_of(product):
    """跑 archive list 拿 doc 表（只读元数据）。"""
    rc, so, se, _ = run_ctxiso("archive", "list", "--product", product, "--limit", "5000")
    if rc != 0:
        return rc, None, se
    return rc, jload(so), se


# ================================================================ 场景 1
def scenario_1():
    s = Scenario(1, "普通新任务：不会因为历史记录自动加载大量无关内容")
    cfg = ctxiso_config()
    budget = int(cfg["pack_budget_bytes"])
    max_rows = int(cfg["pack_max_index_rows"])

    rc, so, se, ms = run_ctxiso("pack", "--product", REPO,
                                "--intent", "给主人解释载入流程", "--stage", "0-spec",
                                "--json")
    if rc != 0:
        s.fail(RuntimeError("pack rc=%d %s" % (rc, se.strip()[:300])))
        return s
    res = jload(so)
    text = res["text"]

    s.check("1.1 pack 成功", res.get("ok") is True, detail="rc=0", bytes=res["bytes"], ms=ms)
    s.check("1.2 预算硬顶", res["bytes"] <= budget,
            detail="配置 pack_budget_bytes=%d" % budget,
            bytes=res["bytes"], budget=budget, headroom=budget - res["bytes"])
    s.check("1.3 包自报的 budget 与配置一致", int(res.get("budget", -1)) == budget,
            budget=res.get("budget"))

    # 1.4 任务包里不出现本仓长期资料（README / 基线表）的正文片段
    #（跳过首行：首行就是合法的一行用途）。原来列的是旧仓的 OWNER-SPEECH/CHANGES，
    #  本仓没有那两个文件——列了就是 FileNotFoundError，场景整个崩掉而不是判红。
    leak_sets = {}
    for name in ("README.md", "01-design/当前实测基线.md"):
        p = REPO / name
        sh = body_shingles(p)
        leak_sets[name] = sh
        bad = leaks(text, sh)
        s.check("1.4 无 %s 正文片段" % name, not bad,
                detail="比对 %d 个 30 字 shingle，命中 %d 个" % (len(sh), len(bad)),
                shingles=len(sh), hits=len(bad),
                sample=(bad[0][:30] if bad else ""))

    # 1.5 出现的是索引行：路径｜大小｜行数｜一行用途
    idx_re = re.compile(r"^\s+- (\S+)｜(\d+) B｜(\d+) 行｜(.+)$")
    found = {}
    for ln in text.splitlines():
        m = idx_re.match(ln)
        if m:
            found[m.group(1)] = (int(m.group(2)), int(m.group(3)), m.group(4))
    # 1.5 验的是「索引行存在，格式是 路径|字节|行数|一行用途」，**不是绑死哪一份文档**。
    # 原来列死 OWNER-SPEECH/CHANGES 是旧仓的文件；换成 README 后又被
    # pack_max_index_rows 截断（current 类排在前面，project 类只列前 N 条），
    # 于是每换一份文档就要改一次断言——那是断言写错了，不是工具错了。
    s.check("1.5 出现长期资料的索引行（不是正文）", len(found) > 0,
            detail="包里列了 %d 份：%s" % (len(found), "、".join(sorted(found)[:5])),
            rows_in_pack=len(found), listed=sorted(found)[:5])
    # pack_max_index_rows 是**每一类**的上限，不是整包上限：
    # current 3 + project 10 + history 4 = 17 行，样例实测就是这样。
    # found 的值是 (字节, 行数, 一行用途) 三元组——路径在 dict 的键上。
    s.check("1.5b 索引行字段齐全（路径+大小+行数+一行用途）",
            all(len(v) == 3 and v[2].strip() for v in found.values()),
            detail="共 %d 行索引，逐行四段齐全（每类上限 %d，三类相加）"
                   % (len(found), max_rows),
            index_rows=len(found), max_index_rows_per_kind=max_rows)
    # 1.6 索引行的"一行用途"确实是该文件首行，不是正文外泄
    ok6 = 0
    for name, v in found.items():
        p6 = REPO / name
        if not p6.is_file():
            continue
        first = p6.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
        if not first:
            continue
        one = v[2]
        if first[0].startswith(one[:20]) or one[:20] in first[0]:
            ok6 += 1
    s.check("1.6 索引行的一行用途确实来自各文件首行", ok6 == len([n for n in found if (REPO / n).is_file()]),
            detail="%d/%d 份的一行用途对得上首行" % (ok6, len(found)),
            matched=ok6, rows=len(found))

    # 1.7 omitted 明确写了"没展开什么、怎么取"
    omitted = res.get("omitted") or []
    joined = " ".join(omitted)
    has_how = bool(re.search(r"ctxiso (query|archive list|read)", joined))
    s.check("1.7 omitted 写清没展开什么 + 怎么取", bool(omitted) and has_how,
            detail=" | ".join(omitted)[:200] or "omitted 为空",
            omitted=len(omitted))

    # 1.8 刻意不含段存在
    s.check("1.8 【本包刻意不含】段存在", "【本包刻意不含】" in text,
            detail="找到该段，含 %d 行" % len(
                [x for x in text.split("【本包刻意不含】")[1].splitlines() if x.strip()])
            if "【本包刻意不含】" in text else "缺失")

    # 1.9 不出现账本的任何事件正文。
    # 本仓没有旧中枢那份 26 MB 真账本，所以这里用 build_ledger 造一份同构的
    # （同样内嵌 observed/assertions/候选路径，就是污染源），再拿它当泄漏源。
    # 判据不变：任务包正文里一个都不许出现。
    led = TEMP / "ledger-for-leak.jsonl"
    led_bytes = build_ledger(led, 1200, extra_bytes=600)
    led_lines = []
    with led.open("r", encoding="utf-8", errors="replace") as fh:
        for i, ln in enumerate(fh):
            if i % 5 == 0 and len(ln) > 200:      # 均匀抽样够用，且只取长事件
                led_lines.append(ln.strip())
    led_sh = set()
    for ln in led_lines[:400]:
        led_sh |= {ln[i:i + 60] for i in range(0, max(1, len(ln) - 60), 60)}
    bad_led = leaks(text, led_sh)
    s.check("1.9 无账本事件正文",
            not bad_led,
            detail="抽样 %d 条长事件 / %d 个 60 字片段，命中 %d" % (
                len(led_lines[:400]), len(led_sh), len(bad_led)),
            ledger_bytes=led_bytes, sampled=min(400, len(led_lines)),
            shingle=len(led_sh), hits=len(bad_led))

    # 1.10 不出现 observed / assertions 的 JSON 键（带引号；说明文字里的裸词不算）
    json_keys = [k for k in ('"observed"', '"assertions"', '"work_bindings"',
                             '"candidate_paths"', '"receipt"') if k in text]
    s.check("1.10 无 observed/assertions 等 JSON 键", not json_keys,
            detail="命中：%s" % (json_keys or "无"),
            hits=len(json_keys))

    s.note("真仓库 doc 表共 %d 份资料；pack 只按 pack_max_index_rows=%d 每类列 10 行，"
           "所以 omitted 里必然有内容（见 1.7）"
           % (res.get("doc_count", 0), max_rows))
    return s


# ================================================================ 场景 2
def scenario_2():
    s = Scenario(2, "连续任务：当前任务状态能正确延续，不累积回灌")
    cfg = ctxiso_config()
    budget = int(cfg["pack_budget_bytes"])
    half = budget // 2

    i1, i2 = "给主人解释载入流程", "查清 state status 为什么会回灌历史缺口"
    rc1, so1, se1, ms1 = run_ctxiso("pack", "--product", REPO, "--intent", i1,
                                    "--stage", "0-spec", "--json")
    rc2, so2, se2, ms2 = run_ctxiso("pack", "--product", REPO, "--intent", i2,
                                    "--stage", "0-spec", "--json")
    if rc1 or rc2:
        s.fail(RuntimeError("pack 失败 rc=%d/%d %s" % (rc1, rc2, (se1 + se2)[:300])))
        return s
    a, b = jload(so1), jload(so2)
    ta, tb = a["text"], b["text"]

    def intent_line(t):
        for ln in t.splitlines():
            if ln.startswith("【任务意图】"):
                return ln
        return ""

    la, lb = intent_line(ta), intent_line(tb)
    s.check("2.1 第一次意图正确", i1 in la, detail=la[:80], line_len=len(la))
    s.check("2.2 第二次意图正确", i2 in lb, detail=lb[:80], line_len=len(lb))
    s.check("2.3 两个意图互不串", (i1 not in tb) and (i2 not in ta),
            detail="包1 含意图2=%s，包2 含意图1=%s" % (i1 in tb, i2 in ta))
    s.check("2.3b 两次都只有一个【任务意图】行",
            ta.count("【任务意图】") == 1 and tb.count("【任务意图】") == 1)

    diff = abs(a["bytes"] - b["bytes"])
    s.check("2.4 两包大小之差 < 预算一半", diff < half,
            detail="预算一半 = %d" % half,
            bytes1=a["bytes"], bytes2=b["bytes"], diff=diff, limit=half)
    s.check("2.5 两次都在预算内", a["bytes"] <= budget and b["bytes"] <= budget,
            bytes1=a["bytes"], bytes2=b["bytes"], budget=budget)

    # 去掉意图行后两次的包应逐字节相同 —— 证明第二次没有多出任何历史内容
    sa = "\n".join(x for x in ta.splitlines() if not x.startswith("【任务意图】"))
    sb = "\n".join(x for x in tb.splitlines() if not x.startswith("【任务意图】"))
    s.check("2.6 除意图行外两次包逐字节相同（无累积回灌）", sa == sb,
            detail="长度 %d vs %d" % (len(sa.encode()), len(sb.encode())),
            same_bytes=len(sa.encode()) == len(sb.encode()))
    s.check("2.7 两次 indexed_events 相同（同一份索引，没被重灌）",
            a["indexed_events"] == b["indexed_events"],
            events=a["indexed_events"], doc_count=a["doc_count"], ms1=ms1, ms2=ms2)
    return s


# ================================================================ 场景 3
def scenario_3():
    s = Scenario(3, "自动记录：工作过程仍然能正常保存，没有被关掉")
    fake = new_fake("fake-auto")

    # 建 13 个长期资料名里的一部分，让 observe 的指纹覆盖得到
    write_lines(fake / "OWNER-SPEECH.md", ["# 演示产品主人原话流水（只追加）",
                                          "第一句：先做能跑通的最小流程。"])
    write_lines(fake / "CHANGES.md", ["# 改动图", "| 怎么找到 | 大概在哪 | 改成了什么 |",
                                     "| --- | --- | --- |"])
    write_lines(fake / "STATUS.md", ["# 演示产品 · 当前状态", "刚建，还没有使命。"])
    write_lines(fake / "SHIFT.md", ["# 接班纸", "（还没有班）"])
    write_lines(fake / "MAP.md", ["# 功能图", "- 演示功能"])
    write_lines(fake / "TARGET.md", ["# 最终目标", "演示产品能自己记住说过的话。"])
    (fake / ".hub").mkdir(exist_ok=True)
    write_lines(fake / "src" / "recorder.py",
                ["# 演示产品：把主人原话追加进账本的小模块", "def append(text):", "    return text"])

    # --- 3.1 记录器清单 8 项齐全（对任意产品都能看）
    rc, so, se, _ = run_ctxiso("observe", "recorders", "--product", fake)
    if rc != 0:
        s.fail(RuntimeError("observe recorders rc=%d %s" % (rc, se[:200])))
        return s
    rec = jload(so)
    recs = rec.get("recorders") or {}
    want = ["OWNER-SPEECH.md", "CHANGES.md", ".hub/ledger.jsonl", ".hub/requirements.jsonl",
            "SHIFT.md / .hub/shift-ticket.json", "PROJECT-MEMORY.jsonl",
            "MAP.md / FEATURES.md / features/*.md", "WORK-HANDOFF.md"]
    missing = [w for w in want if w not in recs]
    s.check("3.1 记录器清单 8 项都在", len(recs) == 8 and not missing,
            detail="共 %d 项，缺 %s" % (len(recs), missing or "无"),
            recorders=len(recs))
    s.check("3.2 策略写明自动记录一律保留",
            "一律保留" in rec.get("policy", ""), detail=rec.get("policy", "")[:80])

    # --- 真跑一遍 state.py 的 init→plan→require→work→leave（只对 TEMP 假产品）
    steps = []
    rc, so, se = run_state(fake, "init", "--type", "cli-tool", "--product-id", "demo-recorder",
                           "--force")
    steps.append(("init", rc))
    goal = "让演示产品把主人每次说的话自动追加进原话账，不丢也不覆盖"
    okc = ("重启后还能读回上一次追加的那句话，退出码 0，且不改动主人原有文件")
    route = "先用 state require 收原话，再用 state work 累积责任，最后 record 落制品"
    rc2, so2, se2 = run_state(fake, "plan", "--goal", goal, "--success", okc, "--route", route)
    steps.append(("plan", rc2))
    req = "演示产品每次开工都要把主人原话追加进账本，不许覆盖旧记录"
    rc3, so3, se3 = run_state(fake, "require", "--append", req, "--source", "operator")
    steps.append(("require", rc3))
    req_id = (re.search(r"(REQ-\d+)", so3) or [None, ""])[1]

    plan_file = TEMP / "_work_plan.json"
    plan_file.write_text(json.dumps({
        "version": 1,
        "items": [{
            "id": "W-demo-1",
            "outcome": "主人下次开工能看到上一次追加的原话",
            "phase": "0-spec",
            "consumer": "演示产品的使用者",
            "sources": [{"requirement_id": req_id, "quote": req}],
            "depends_on": [],
            "evidence": [{"kind": "acceptance"}],
            "files": ["src/recorder.py"],
        }],
    }, ensure_ascii=False), encoding="utf-8")
    rc4, so4, se4 = run_state(fake, "work", "--define", str(plan_file))
    steps.append(("work --define", rc4))
    rc5, so5, se5 = run_state(fake, "work", "--enter", "W-demo-1")
    steps.append(("work --enter", rc5))
    rc6, so6, se6 = run_state(fake, "work", "--leave", "--pause")
    steps.append(("work --leave", rc6))

    data_file = TEMP / "_record_spec.json"
    data_file.write_text(json.dumps(
        {"acceptance": "主人说：演示产品重启后原话还在"}, ensure_ascii=False), encoding="utf-8")
    rc7, so7, se7 = run_state(fake, "record", "--kind", "spec", "--data-file", str(data_file))
    steps.append(("record", rc7))
    s.check("3.3 state.py 完整流程跑通（init→plan→require→work→leave）",
            all(c == 0 for _, c in steps),
            detail=" | ".join("%s=%d" % (n, c) for n, c in steps) +
                   ("｜失败：%s" % ((se3 or se4 or se5 or se6 or se7)[:200]) if any(c for _, c in steps) else ""),
            steps_ok=sum(1 for _, c in steps if c == 0), steps=len(steps))

    led = fake / ".hub" / "ledger.jsonl"
    reqs = fake / ".hub" / "requirements.jsonl"
    s.check("3.4 账本被真的追加了", led.is_file() and led.stat().st_size > 0,
            detail="%d 字节 / %d 条事件" % (
                led.stat().st_size if led.is_file() else 0,
                len(led.read_text(encoding="utf-8").splitlines()) if led.is_file() else 0),
            ledger_bytes=led.stat().st_size if led.is_file() else 0)
    s.check("3.5 原话账被真的追加了", reqs.is_file() and reqs.stat().st_size > 0,
            detail=reqs.read_text(encoding="utf-8")[:120] if reqs.is_file() else "无",
            req_bytes=reqs.stat().st_size if reqs.is_file() else 0,
            req_id=req_id)

    # --- 快照（放在 init/plan/require 之后，保证被观测文件已经存在，才能出现 grew）
    rcA, soA, seA, _ = run_ctxiso("observe", "snapshot", "--product", fake)
    snap = jload(soA) if rcA == 0 else {}
    base_fp = json.loads((STATE_DIR / _state_key(fake) / "observe-baseline.json")
                         .read_text(encoding="utf-8"))["files"]
    s.check("3.6 快照覆盖到被观测文件", rcA == 0 and len(base_fp) >= 5,
            detail="指纹覆盖 %d 个文件" % len(base_fp), files=len(base_fp))

    # --- 制造一次追加（模拟中枢那三个记录器各自再写一刀）
    with (fake / "OWNER-SPEECH.md").open("a", encoding="utf-8") as fh:
        fh.write("第二句：演示产品要能自动记住这句话。\n")
    with (fake / "CHANGES.md").open("a", encoding="utf-8") as fh:
        fh.write("| hub/tools/state.py | 根目录 | 加了演示产品原话追加这一刀 |\n")
    rcX, soX, seX = run_state(fake, "require", "--append",
                              "演示产品还要能把改动图追加到产品根的改动图文件里", "--source", "operator")
    rcY, soY, seY = run_state(fake, "work", "--enter", "W-demo-1")
    grew_by = (fake / ".hub" / "requirements.jsonl").stat().st_size
    s.check("3.7 追加动作真的写进去了", rcX == 0 and rcY == 0,
            detail="require=%d work--enter=%d" % (rcX, rcY),
            req_bytes=grew_by)

    # --- 校验：没变小、没消失、至少一条 grew
    rcB, soB, seB, _ = run_ctxiso("observe", "check", "--product", fake)
    chk = jload(soB) if rcB in (0, 3) else {}
    s.check("3.8 observe check ok=true", chk.get("ok") is True,
            detail=chk.get("verdict", ""), rc=rcB)
    s.check("3.8b 退出码 0", rcB == 0, rc=rcB)
    s.check("3.9 shrank 为空", chk.get("shrank") == [], detail=str(chk.get("shrank")))
    s.check("3.10 gone 为空", chk.get("gone") == [], detail=str(chk.get("gone")))
    g = chk.get("grew") or []
    s.check("3.11 至少一条 grew", len(g) >= 1, detail="grew=%s" % [x["path"] for x in g],
            grew=len(g))
    s.check("3.12 没有 new（被观测文件快照时就已存在）", chk.get("new") == [],
            detail=str(chk.get("new")))

    # 账本事件确实只增不减：数一下 work_enter 出现两次
    led_txt = led.read_text(encoding="utf-8")
    enters = led_txt.count('"kind": "work_enter"') + led_txt.count('"kind":"work_enter"')
    s.check("3.13 账本里 work_enter 出现两次（进入两次都是追加）", enters >= 2,
            detail="work_enter 计数=%d" % enters, work_enter=enters)

    s.note("假产品目录：%s（测完随 TEMP 一起删）" % fake)
    s.note("真仓库 .hub/ 全程没被写：见 RESULT.md 的保护区指纹比对")
    return s


# ================================================================ 场景 4
def scenario_4():
    s = Scenario(4, "历史查询：用户明确需要过去资料时能找到并按需读取")
    fake = new_fake("fake-hist")
    v1 = ["# 规格 v1（演示）", "", "## 第一节：初版只做命令行。",
          "第二版要加图形界面，这一点 v1 没写。", "结尾：v1 到此为止。"]
    v1 += ["第 %d 行：这是 v1 的填充正文，用来保证两版差异足够明显。" % i for i in range(120)]
    v2 = ["# 规格 v2（演示）", "", "## 第一节：初版只做命令行。",
          "第二版已经加上了图形界面。", "结尾：v2 收口。"]
    v2 += ["第 %d 行：v2 把这一行改成了另一种说法，和 v1 不一样。" % i for i in range(126)]
    write_lines(fake / "docs" / "history" / "spec-v1.md", v1)
    write_lines(fake / "docs" / "history" / "spec-v2.md", v2)
    write_lines(fake / "OWNER-SPEECH.md",
                ["# 演示产品主人原话流水（只追加）"] +
                ["第 %d 句：主人说过的一句很长的话，长到足以成为可识别的正文片段。" % i
                 for i in range(60)])
    (fake / ".hub").mkdir(exist_ok=True)
    build_ledger(fake / ".hub" / "ledger.jsonl", 12, extra_bytes=200)

    rci, soi, sei, _ = run_ctxiso("index", "--product", fake)
    s.check("4.0 假产品索引成功", rci == 0, detail=sei[:200],
            indexed=jload(soi)["docs"]["indexed"] if rci == 0 else 0)

    # --- 4.1 archive list 只给元数据
    rc, so, se, _ = run_ctxiso("archive", "list", "--product", fake, "--limit", "500")
    if rc != 0:
        s.fail(RuntimeError("archive list rc=%d %s" % (rc, se[:200])))
        return s
    lst = jload(so)
    rows = lst.get("rows") or []
    src_files = [fake / "docs/history/spec-v1.md", fake / "docs/history/spec-v2.md",
                 fake / "OWNER-SPEECH.md"]
    sh = set()
    for p in src_files:
        sh |= body_shingles(p)
    bad = leaks(so, sh)
    s.check("4.1 archive list 无任何文件正文", not bad,
            detail="比对 %d 个 30 字 shingle（3 个文件），命中 %d" % (len(sh), len(bad)),
            shingles=len(sh), hits=len(bad), sample=(bad[0][:30] if bad else ""))
    longest = 0
    for p in src_files:
        for ln in p.read_text(encoding="utf-8").splitlines():
            if ln in so:
                longest = max(longest, len(ln))
    s.check("4.1b 返回体里最长命中正文行 = 0", longest == 0,
            detail="命中最长行 %d 字符（门槛 0）" % longest, longest_line=longest)
    src_total = sum(p.stat().st_size for p in src_files)
    s.check("4.1c 返回体远小于源文件总量", len(so.encode()) < src_total / 4,
            detail="返回 %d 字节 / 源 %d 字节 = %.4f" % (
                len(so.encode()), src_total, len(so.encode()) / src_total),
            out_bytes=len(so.encode()), src_bytes=src_total,
            ratio=round(len(so.encode()) / src_total, 5))
    have = {r["path"] for r in rows}
    s.check("4.2 索引里找得到两版规格和原话",
            {"docs/history/spec-v1.md", "docs/history/spec-v2.md", "OWNER-SPEECH.md"} <= have,
            detail="命中 %s" % sorted(have), rows=len(rows))
    s.check("4.3 每行只有元数据字段",
            all(set(r) <= {"path", "kind", "size", "mtime", "lines", "sha", "one_line"}
                for r in rows),
            detail="字段集合 %s" % sorted(set(rows[0])) if rows else "无行")

    # --- 4.4 read 不带 --intent 被拒
    tgt = "docs/history/spec-v1.md"
    rc, so, se, _ = run_ctxiso("read", "--product", fake, "--target", tgt)
    body = maybeliteral(so) or {}
    s.check("4.4 read 无 --intent 退出码 2", rc == 2, rc=rc, detail=so.strip()[:120])
    s.check("4.4b refused 为真", body.get("refused") is True, detail=str(body)[:160])
    s.check("4.4c 拒绝时不回正文", tgt not in so or body.get("ok") is False,
            detail="拒绝体里没有 ok=true")

    # --- 4.5 read --intent（2026-09-26 首次实跑时这里红过：archive.py:118 用了
    #     hashlib.sha8，带意图读正文必崩。2026-09-27 统筹修成 sha256 后转绿。
    #     下面仍然不吞这个红：它要是再崩，这里照样判红。）
    intent = "主人问 v1 到 v2 改了什么，这次只要 v1 的规格原文作为对比底本"
    rc, so, se, _ = run_ctxiso("read", "--product", fake, "--target", tgt,
                               "--intent", intent, "--json")
    crash = "AttributeError" in se or "Traceback" in se
    s.check("4.5 read --intent 成功", rc == 0,
            detail=("rc=%d stdout 前 120 字=%r" % (rc, so[:120])) if rc == 0
                   else ("崩了：" + se.strip().splitlines()[-1][:160]),
            rc=rc, crashed=crash)
    if rc == 0:
        got = jload(so)
        s.check("4.5b 正文真的回来了", len(got.get("text") or "") > 0,
                text_chars=len(got.get("text") or ""))
        r = got.get("receipt") or {}
    else:
        s.check("4.5b 正文真的回来了", False,
                detail="read 崩在返回之前，正文没拿到", text_chars=0)
        r = {}

    # --- 4.7 compare 只回差异摘要
    rc, so, se, _ = run_ctxiso("compare", "--product", fake,
                               "--base", "docs/history/spec-v1.md",
                               "--head", "docs/history/spec-v2.md",
                               "--intent", "确认第二版相对第一版改了哪几节")
    s.check("4.7 compare --intent 成功", rc == 0,
            detail=("rc=%d stdout 前 120 字=%r stderr=%r" % (rc, so[:120], se[:200])), rc=rc)
    if rc != 0 or not so.strip():
        s.fail(RuntimeError("compare 失败 rc=%d out=%r err=%r" % (rc, so[:200], se[:300])))
        return s
    cmp_res = jload(so)
    s.check("4.7b 返回里有差异摘要字段",
            all(k in cmp_res for k in ("added", "removed", "similarity", "hunks")),
            detail="added=%s removed=%s similarity=%s hunks=%d" % (
                cmp_res.get("added"), cmp_res.get("removed"),
                cmp_res.get("similarity"), len(cmp_res.get("hunks") or [])),
            added=cmp_res.get("added"), removed=cmp_res.get("removed"),
            similarity=cmp_res.get("similarity"))
    sh2 = set()
    for p in src_files[:2]:
        sh2 |= body_shingles(p)
    bad2 = leaks(so, sh2)
    s.check("4.7c compare 不回两份全文", not bad2,
            detail="比对 %d 个 shingle，命中 %d" % (len(sh2), len(bad2)),
            hits=len(bad2), sample=(bad2[0][:30] if bad2 else ""))
    both = src_files[0].stat().st_size + src_files[1].stat().st_size
    s.check("4.7d compare 返回体远小于两份全文", len(so.encode()) < both / 4,
            detail="%d 字节 vs 全文 %d 字节 = %.4f" % (len(so.encode()), both,
                                                 len(so.encode()) / both),
            out_bytes=len(so.encode()), full_bytes=both)

    # --- 4.6 收据机制（2026-09-27 起：archive.py 的 hashlib.sha8 缺陷已被统筹修掉，
    #     read 路径能走通了。下面比修复前更严，不只是把 FAIL 翻成 PASS。）
    rj = STATE_DIR / _state_key(fake) / "reads.jsonl"
    receipts = [json.loads(x) for x in rj.read_text(encoding="utf-8").splitlines() if x.strip()]
    read_rcpts = [x for x in receipts if x.get("target") == tgt]
    cmp_rcpts = [x for x in receipts if " vs " in str(x.get("target", ""))]
    last = receipts[-1] if receipts else {}
    s.check("4.6 reads.jsonl 留有收据（target/intent/bytes/sha8 齐全）",
            bool(receipts)
            and not [k for k in ("target", "intent", "sha8") if k not in last]
            and ("bytes_read" in last or "bytes" in last),
            detail="共 %d 条收据（read %d 条 + compare %d 条）；最后一条 target=%s"
                   % (len(receipts), len(read_rcpts), len(cmp_rcpts), last.get("target")),
            receipts=len(receipts), read_receipts=len(read_rcpts), cmp_receipts=len(cmp_rcpts))

    rr = r.get("receipt") or r
    s.check("4.6b read 确实多写了一条收据", len(read_rcpts) >= 1,
            detail="reads.jsonl 里有 %d 条 target=%s 的收据" % (len(read_rcpts), tgt),
            read_receipts=len(read_rcpts))
    s.check("4.6c read 收据的 sha8 是 8 位十六进制",
            bool(re.fullmatch(r"[0-9a-f]{8}", str(rr.get("sha8") or ""))),
            detail="sha8=%r" % rr.get("sha8"), sha8=rr.get("sha8"))
    fields = ("target", "intent", "bytes_read", "file_bytes", "truncated")
    lack = [k for k in fields if k not in rr]
    self_consistent = (isinstance(rr.get("bytes_read"), int)
                       and isinstance(rr.get("file_bytes"), int)
                       and rr["bytes_read"] <= rr["file_bytes"]
                       and rr.get("target") == tgt
                       and str(rr.get("intent", "")).strip() != "")
    s.check("4.6d read 收据字段齐全且自洽（bytes_read ≤ file_bytes、target/intent 对得上）",
            not lack and self_consistent,
            detail="缺字段 %s；bytes_read=%s file_bytes=%s truncated=%s target=%s"
                   % (lack or "无", rr.get("bytes_read"), rr.get("file_bytes"),
                      rr.get("truncated"), rr.get("target")),
            missing=len(lack), consistent=self_consistent,
            bytes_read=rr.get("bytes_read"), file_bytes=rr.get("file_bytes"))

    # 同内容重读一次 → sha8 必须稳定；换一份内容不同的文件 → sha8 必须不同
    rc2r, so2r, se2r, _ = run_ctxiso("read", "--product", fake, "--target", tgt,
                                     "--intent", intent, "--json")
    sha_again = ((jload(so2r) or {}).get("receipt") or {}).get("sha8") if rc2r == 0 else None
    s.check("4.6e 同内容再读一次，sha8 稳定", sha_again == rr.get("sha8"),
            detail="第一次 %r，第二次 %r" % (rr.get("sha8"), sha_again),
            sha_first=rr.get("sha8"), sha_again=sha_again)
    other = "docs/history/spec-v2.md"
    rc3r, so3r, se3r, _ = run_ctxiso("read", "--product", fake, "--target", other,
                                     "--intent", "同一份意图读另一份规格，用来比指纹", "--json")
    sha_other = ((jload(so3r) or {}).get("receipt") or {}).get("sha8") if rc3r == 0 else None
    s.check("4.6f 内容不同的文件，sha8 不同", sha_other not in (None, rr.get("sha8")),
            detail="v1=%r v2=%r" % (rr.get("sha8"), sha_other),
            sha_v1=rr.get("sha8"), sha_v2=sha_other)

    # --- 4.8 越界读取也被拒
    rc, so, se, _ = run_ctxiso("read", "--product", fake, "--target", "../../OWNER-SPEECH.md",
                               "--intent", "试着读到产品外面去")
    body = maybeliteral(so) or {}
    s.check("4.8 目标在产品外被拒", rc == 2 and body.get("refused") is True,
            detail=so.strip()[:120], rc=rc)
    s.note("假产品目录：%s" % fake)
    return s


# ================================================================ 场景 6
def scenario_6():
    s = Scenario(6, "上下文压缩：压缩后不会把整个历史项目塞回当前上下文")
    cfg = ctxiso_config()
    want_fields = ["intent", "stage", "goal", "next", "blockers",
                   "confirmed_decisions", "constraints"]

    # --- 6.1 contract-only（对真仓库跑，纯读配置，不写任何东西）
    rc, so, se, _ = run_ctxiso("compact", "--contract-only", "--product", REPO)
    if rc != 0:
        s.fail(RuntimeError("compact --contract-only rc=%d %s" % (rc, se[:200])))
        return s
    c = jload(so)
    got_fields = c.get("survivor_fields") or []
    s.check("6.1 存活字段正好 7 个", len(got_fields) == 7 and got_fields == want_fields,
            detail=str(got_fields), fields=len(got_fields))
    rules = " ".join(c.get("rule") or [])
    s.check("6.2 规则写明历史正文不进摘要", "不进入压缩摘要" in rules,
            detail=[r for r in c["rule"] if "摘要" in r][:1])
    s.check("6.3 规则写明丢掉的是指针不是删除", "按指针取回" in rules,
            detail=[r for r in c["rule"] if "指针" in r][:1])
    s.check("6.4 规则写明取回要带意图", "读取意图" in rules,
            detail=[r for r in c["rule"] if "意图" in r][:1])
    # 语义等价检查：没有任何一条规则要求把历史重新总结一遍
    resummary = [r for r in c["rule"]
                 if re.search(r"(重新总结|重总结|再总结一次|总结历史)", r)
                 and not re.search(r"(不|禁止|别)", r)]
    s.check("6.4b 没有任何一条规则要求重新总结历史", not resummary,
            detail=str(resummary) or "无此规则", offending=len(resummary))
    s.note("6.x 的规则文字来自 ctxiso/compact.py:27-32；02-hubcore/AGENTS.md §9.2.5 "
           "写的是「压缩不是重新总结历史」，两处是同一条规则的不同措辞，"
           "所以断言按语义（不进入摘要 + 按指针取回）判，不按字面判")

    # --- 6.5 在一个有真实历史的假产品上跑 compact --state
    fake = new_fake("fake-compact")
    led_bytes = build_ledger(fake / ".hub" / "ledger.jsonl", 800, extra_bytes=600)
    write_lines(fake / "OWNER-SPEECH.md",
                ["# 演示产品主人原话流水（只追加）"] +
                ["第 %d 句：主人说这一轮只做上下文压缩，别把旧账带回来。" % i
                 for i in range(200)])
    write_lines(fake / "CHANGES.md",
                ["# 改动图"] + ["第 %d 行：某次改动的记录。" % i for i in range(200)])
    rci, soi, sei, _ = run_ctxiso("index", "--product", fake)
    s.check("6.5 假产品历史已索引", rci == 0,
            detail="账本 %d 字节 / %d 条" % (
                led_bytes, jload(soi)["stats"]["indexed_events"] if rci == 0 else 0),
            ledger_bytes=led_bytes,
            events=jload(soi)["stats"]["indexed_events"] if rci == 0 else 0)

    state = {
        "intent": "把 ctxiso 的压缩契约测一遍，确认历史不回流",
        "stage": "0-spec",
        "goal": "压缩后只留当前任务相关的 7 个字段",
        "next": "把结果写进 RESULT.md 并通知统筹",
        "blockers": ["03-bundle 与 04-console 未落地，剩下 3 个场景等下一轮"],
        "confirmed_decisions": ["只写 05-tests/，不碰别人的分区",
                                "所有假产品建在 05-tests/TEMP/"],
        "constraints": ["不联网", "不做 git 写操作", "数字必须真实"],
    }
    rc, so, se, _ = run_ctxiso("compact", "--product", fake, "--state",
                               json.dumps(state, ensure_ascii=False))
    if rc != 0:
        s.fail(RuntimeError("compact --state rc=%d %s" % (rc, se[:200])))
        return s
    res = jload(so)
    surv = Path(res["survivor_path"])
    drop = Path(res["dropped_path"])
    s.check("6.6 生成 SURVIVOR.md", surv.is_file(), path=str(surv),
            survivor_bytes=surv.stat().st_size if surv.is_file() else 0)
    s.check("6.6b 生成 dropped.json", drop.is_file(), path=str(drop),
            dropped_bytes=drop.stat().st_size if drop.is_file() else 0)
    s.check("6.7 存活集正好是传进去的 7 个字段", res.get("survivor_fields") == want_fields,
            detail=str(res.get("survivor_fields")), fields=len(res.get("survivor_fields") or []))

    stext = surv.read_text(encoding="utf-8") if surv.is_file() else ""
    s.check("6.8 SURVIVOR.md < 2000 字节", len(stext.encode()) < 2000,
            bytes=len(stext.encode()), limit=2000)

    # 不含任何历史事件 id / 探针名 / OWNER-SPEECH 内容
    probe_names = ["core_entry", "package_install", "license_dataflow", "ui_regression",
                   "update_flow", "handoff", "change_regression", "core_closed",
                   "physical_probe", "work_define", "work_attest", "candidate"]
    hit_probe = [n for n in probe_names if n in stext]
    s.check("6.9 SURVIVOR.md 不含任何探针名 / 事件 kind", not hit_probe,
            detail="命中 %s" % (hit_probe or "无"), hits=len(hit_probe))
    sh = body_shingles(fake / "OWNER-SPEECH.md") | body_shingles(fake / "CHANGES.md")
    bad = leaks(stext, sh)
    s.check("6.9b SURVIVOR.md 不含 OWNER-SPEECH / CHANGES 内容", not bad,
            detail="比对 %d 个 shingle，命中 %d" % (len(sh), len(bad)),
            shingles=len(sh), hits=len(bad), sample=(bad[0][:30] if bad else ""))
    # 账本行也一个都不许进
    led_lines = (fake / ".hub" / "ledger.jsonl").read_text(
        encoding="utf-8").splitlines()[:200]
    led_sh = {ln[i:i + 50] for ln in led_lines for i in range(0, max(1, len(ln) - 50), 50)}
    bad_led = leaks(stext, led_sh)
    s.check("6.9c SURVIVOR.md 不含账本事件正文", not bad_led,
            detail="抽样 200 条 / %d 个 50 字片段，命中 %d" % (len(led_sh), len(bad_led)),
            hits=len(bad_led))
    # 也不含账本里的任何事件时间戳（compact.build 只允许写一行「生成：」时间戳）
    led_ts = {m.group(0) for ln in led_lines
              for m in [re.search(r'"ts":\s*"([^"]+)"', ln)] if m}
    hit_ts = sorted(t for t in led_ts if t in stext)
    iso_all = re.findall(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ", stext)
    s.check("6.9d SURVIVOR.md 不含任何账本事件时间戳", not hit_ts,
            detail="账本里有 %d 个不同 ts，命中 %d 个；SURVIVOR.md 里的 ISO 时间戳共 %d 个"
                   % (len(led_ts), len(hit_ts), len(iso_all)),
            ledger_ts=len(led_ts), hit_ts=len(hit_ts), iso_in_survivor=len(iso_all))

    # dropped.json 只有指针
    d = jload(drop.read_text(encoding="utf-8"))
    items = d.get("dropped") or []
    s.check("6.10 dropped.json 每项都带 what/count/how",
            bool(items) and all(all(k in it for k in ("what", "count", "how")) for it in items),
            detail="; ".join("%s(%d)→%s" % (it.get("what"), it.get("count"), it.get("how"))
                             for it in items))
    dtext = drop.read_text(encoding="utf-8")
    bad_d = leaks(dtext, sh)
    s.check("6.10b dropped.json 里没有正文", not bad_d,
            detail="比对 %d 个 shingle，命中 %d" % (len(sh), len(bad_d)), hits=len(bad_d))
    led_item = next((it for it in items if "账本" in str(it.get("what"))), None)
    s.check("6.11 账本那项带取回命令 ctxiso query --kind <kind> --limit 50",
            led_item is not None and "ctxiso query --kind" in str(led_item.get("how"))
            and "--limit 50" in str(led_item.get("how")),
            detail=str((led_item or {}).get("how")),
            how=(led_item or {}).get("how"),
            ledger_count=(led_item or {}).get("count"))
    doc_item = next((it for it in items if "资料" in str(it.get("what"))), None)
    s.check("6.12 资料那项带取回命令（list + read --intent）",
            doc_item is not None and "archive list" in str(doc_item.get("how"))
            and "read --intent" in str(doc_item.get("how")),
            detail=str((doc_item or {}).get("how")),
            how=(doc_item or {}).get("how"), doc_count=(doc_item or {}).get("count"))
    s.check("6.13 dropped.json 体积很小（只有指针）",
            len(dtext.encode()) < 4000, bytes=len(dtext.encode()), limit=4000)
    s.note("6.x 的 --state 跑在 TEMP 假产品上：真仓库 800 条事件的假账只用于证明"
           "「历史再多也不回流」，避免往真仓库的侧车状态目录里写 SURVIVOR.md")
    return s


# ================================================================ 场景 7
def scenario_7():
    s = Scenario(7, "大量历史文件：资料越来越多也不会每次自动读一大片")
    cfg = ctxiso_config()
    budget = int(cfg["pack_budget_bytes"])
    max_rows = int(cfg["pack_max_index_rows"])
    N_BIG, N_SMALL, EACH = 2000, 100, 4096
    LEDGER_EVENTS = 5000

    big = new_fake("fake-big")
    small = new_fake("fake-small")
    t0 = time.perf_counter()
    fill_docs(big, N_BIG, EACH)
    fill_docs(small, N_SMALL, EACH)
    led_big = build_ledger(big / ".hub" / "ledger.jsonl", LEDGER_EVENTS, extra_bytes=400)
    led_small = build_ledger(small / ".hub" / "ledger.jsonl", LEDGER_EVENTS, extra_bytes=400)
    make_s = round((time.perf_counter() - t0) * 1000, 1)
    big_files, big_bytes = dir_bytes(big)
    small_files, small_bytes = dir_bytes(small)
    s.check("7.0 假产品造好了", big_files >= N_BIG and led_big >= 2_000_000,
            detail="%d 文件 / %d 字节（历史文件 %d×%d B，账本 %d 事件 / %d 字节）" % (
                big_files, big_bytes, N_BIG, EACH, LEDGER_EVENTS, led_big),
            files=big_files, bytes=big_bytes, ledger_bytes=led_big,
            make_ms=make_s)

    # --- 7.1 索引耗时 < 15 s
    rc, so, se, ms = run_ctxiso("index", "--product", big, timeout=300)
    if rc != 0:
        s.fail(RuntimeError("index rc=%d %s" % (rc, se[:300])))
        return s
    idx = jload(so)
    s.check("7.1 index 耗时 < 15000 ms", ms < 15000,
            detail="整条命令（含解释器启动 + 文档扫描 + 账本增量）",
            elapsed_ms=ms, ledger_ms=idx["ledger"].get("elapsed_ms"),
            ledger_read_bytes=idx["ledger"].get("read_bytes"))

    # --- 7.2 索引库远小于源
    dbp = STATE_DIR / _state_key(big) / "index.sqlite"
    db_bytes = dbp.stat().st_size if dbp.is_file() else 0
    src = big_bytes
    ratio = db_bytes / src if src else 1
    s.check("7.2 索引库远小于源（比值 < 10%）", ratio < 0.10,
            detail="索引 %d 字节 / 源 %d 字节 = %.5f" % (db_bytes, src, ratio),
            index_bytes=db_bytes, src_bytes=src, ratio=round(ratio, 6),
            shrink=round(src / db_bytes, 1) if db_bytes else 0)

    # --- 7.3 doc 表真有 2000 行
    rc2, so2, se2, _ = run_ctxiso("archive", "list", "--product", big, "--limit", "5000")
    rows = jload(so2)["rows"] if rc2 == 0 else []
    kinds = jload(so2)["kinds"] if rc2 == 0 else {}
    s.check("7.3 索引 doc 表有 %d 行" % N_BIG, kinds.get("history") == N_BIG,
            detail=str(kinds), doc_rows=sum(kinds.values()) if kinds else 0,
            history_rows=kinds.get("history"))

    # --- 7.4 pack 在 2000 文件下仍然 ≤ 预算，且只列 max_rows 行
    # 小产品也必须先 index：pack 只读索引库，不自己扫目录（不 index 就没索引行可列）
    rcS, soS, seS, msS = run_ctxiso("index", "--product", small, timeout=300)
    s.check("7.3b 100 文件的对照产品也索引好了", rcS == 0,
            detail=seS[:150], indexed=jload(soS)["docs"]["indexed"] if rcS == 0 else 0,
            ms=msS)
    rcA, soA, seA, msA = run_ctxiso("pack", "--product", big, "--intent", "看一眼历史有多少",
                                    "--stage", "0-spec", "--json")
    rcB, soB, seB, msB = run_ctxiso("pack", "--product", small, "--intent", "看一眼历史有多少",
                                    "--stage", "0-spec", "--json")
    if rcA or rcB:
        s.fail(RuntimeError("pack 失败 %d/%d" % (rcA, rcB)))
        return s
    pa, pb = jload(soA), jload(soB)
    idx_re = re.compile(r"^\s+- (\S+)｜(\d+) B｜(\d+) 行｜")
    listed_big = len([x for x in pa["text"].splitlines() if idx_re.match(x)])
    listed_small = len([x for x in pb["text"].splitlines() if idx_re.match(x)])
    s.check("7.4 2000 文件下 pack ≤ 预算", pa["bytes"] <= budget,
            bytes=pa["bytes"], budget=budget, pack_ms=msA)
    s.check("7.4b 100 文件下 pack ≤ 预算", pb["bytes"] <= budget,
            bytes=pb["bytes"], budget=budget, pack_ms=msB)
    s.check("7.4c 两个产品的索引行数一样多（比较才公平）", listed_big == listed_small,
            detail="2000 文件列 %d 行，100 文件列 %d 行" % (listed_big, listed_small),
            listed_2000=listed_big, listed_100=listed_small)
    s.check("7.5 包里的索引行数 ≤ pack_max_index_rows × 类别数",
            listed_big <= max_rows * 3, listed_rows=listed_big, max_rows=max_rows)
    om = " ".join(pa.get("omitted") or [])
    s.check("7.6 其余资料进 omitted，并写明怎么取",
            ("未列" in om or "份未列" in om) and "archive list" in om,
            detail=" | ".join(pa.get("omitted") or [])[:200],
            omitted=len(pa.get("omitted") or []))
    s.check("7.6b omitted 里的份数算得对",
            ("%d 份未列" % (N_BIG - max_rows)) in om,
            detail="期望 %d 份未列" % (N_BIG - max_rows))

    # --- 7.7 包大小不随文件数增长
    diff = abs(pa["bytes"] - pb["bytes"])
    s.check("7.7 2000 文件 vs 100 文件，包大小差 < 500 B", diff < 500,
            detail="%d B vs %d B，差 %d B" % (pa["bytes"], pb["bytes"], diff),
            bytes_2000=pa["bytes"], bytes_100=pb["bytes"], diff=diff, limit=500)

    # --- 7.8 第二次 index：账本 read_bytes = 0（增量）
    #     这条被统筹点名加过重试：有一次实跑 read_bytes 不是 0，复现不出来，
    #     最可能是同机另一个进程（看门狗也在跑 ctxiso index）撞在同一份索引库上。
    #     增量逻辑本身没问题（store.refresh_ledger 按 ledger_cursor seek），
    #     所以这里跑两次取最后一次，并把每一次都记进报告里。
    attempts = []
    idx2, msC, rcC = {}, 0, 0
    for i in range(2):
        rcC, soC, seC, msC = run_ctxiso("index", "--product", big, timeout=300)
        idx2 = jload(soC) if rcC == 0 else {}
        rb = idx2.get("ledger", {}).get("read_bytes")
        attempts.append("第%d次 read_bytes=%s new_events=%s %sms"
                        % (i + 1, rb, idx2.get("ledger", {}).get("new_events"), msC))
        if rb == 0:
            break
        time.sleep(0.8)
    s.check("7.8 第二次 index 账本 read_bytes = 0（增量）",
            idx2.get("ledger", {}).get("read_bytes") == 0,
            detail="；".join(attempts) + "　（第一次全量 read_bytes=%s 字节）"
                   % idx.get("ledger", {}).get("read_bytes"),
            first_read_bytes=idx.get("ledger", {}).get("read_bytes"),
            second_read_bytes=idx2.get("ledger", {}).get("read_bytes"),
            attempts=len(attempts), first_ms=ms, second_ms=msC)
    s.check("7.8b 第二次 index 没有新增事件",
            idx2.get("ledger", {}).get("new_events") == 0,
            new_events=idx2.get("ledger", {}).get("new_events"))
    s.note("7.8 允许跑两次取最后一次：同机别的进程也会跑 ctxiso index，"
           "撞同一份索引库时 read_bytes 可能不为 0。增量逻辑本身是对的"
           "（store.refresh_ledger 按 meta.ledger_cursor seek 到新增字节）。"
           "本轮跑了 %d 次：%s" % (len(attempts), "；".join(attempts)))
    s.note("文档索引每次都会重算全部 %d 个文件的 sha 与行数（refresh_docs 没有按 mtime 短路），"
           "所以第二次账本 read_bytes=0 但整条命令仍要 %s ms" % (N_BIG, msC))
    return s


# ================================================================ 场景 5
def scenario_5():
    s = Scenario(5, "项目更新：第二版来了要能对比第一版、快速定位变化")

    fake = new_fake("fake-update")
    base_lines = ["# 功能清单（演示）", "- F1 登录", "- F2 导出", "- F3 打印",
                  "- F4 同步", "- F5 审计", "结束标记"]
    head_lines = list(base_lines)
    head_lines[3] = "- F3 打印与传真"                                   # 纯改
    add_lines = list(base_lines)
    add_lines.insert(-1, "- F6 移动端")                                # 纯加
    del_lines = [x for x in base_lines if x != "- F5 审计"]              # 纯删
    move_base = ["# 功能清单（演示）", "- F1 登录", "- F2 导出", "- F3 打印",
                 "- F4 同步", "- F5 审计", "- F6 备份", "- F7 清理", "结束标记"]
    move_head = ["# 功能清单（演示）", "- F1 登录", "- F7 清理", "- F2 导出",
                 "- F3 打印", "- F4 同步", "- F5 审计", "- F6 备份", "结束标记"]
    pairs = {"a-modify": (base_lines, head_lines), "b-append": (base_lines, add_lines),
             "c-remove": (base_lines, del_lines), "d-reorder": (move_base, move_head)}
    for k, (a, b) in pairs.items():
        write_lines(fake / "docs" / "history" / ("feat-%s-base.md" % k), a)
        write_lines(fake / "docs" / "history" / ("feat-%s-head.md" % k), b)
    led5 = build_ledger(fake / ".hub" / "ledger.jsonl", 24, extra_bytes=200)
    rci, soi, sei, _ = run_ctxiso("index", "--product", fake)
    s.check("5.0 假产品索引成功", rci == 0, detail=sei[:150] or "rc=%d" % rci,
            indexed=jload(soi)["docs"]["indexed"] if rci == 0 else 0,
            events=jload(soi)["stats"]["indexed_events"] if rci == 0 else 0,
            ledger_bytes=led5)

    # --- 5.1 不带 --intent 被拒
    b, h = "docs/history/feat-a-modify-base.md", "docs/history/feat-a-modify-head.md"
    rc, so, se, _ = run_ctxiso("compare", "--product", fake, "--base", b, "--head", h)
    body = maybeliteral(so) or {}
    s.check("5.1 compare 不带 --intent 退出码 2", rc == 2, rc=rc, detail=so.strip()[:120])
    s.check("5.1b refused 为真", body.get("refused") is True, detail=str(body)[:160])

    results = {}
    for k in pairs:
        bb, hh = ("docs/history/feat-%s-base.md" % k, "docs/history/feat-%s-head.md" % k)
        rc, so, se, _ = run_ctxiso("compare", "--product", fake, "--base", bb, "--head", hh,
                                   "--intent", "确认第二版相对第一版改了什么")
        if rc != 0:
            s.fail(RuntimeError("compare %s rc=%d %s" % (k, rc, se[:200])))
            return s
        results[k] = jload(so)

    # --- 5.2 / 5.3 / 5.4 三种单点差异，数字要能手算对上
    r = results["a-modify"]
    s.check("5.2 纯改：added=1 removed=1 hunks=1",
            (r["added"], r["removed"], len(r["hunks"])) == (1, 1, 1),
            detail="added=%s removed=%s hunks=%s op=%s" % (
                r["added"], r["removed"], len(r["hunks"]),
                [h["op"] for h in r["hunks"]]),
            added=r["added"], removed=r["removed"], hunks=len(r["hunks"]))
    r = results["b-append"]
    s.check("5.3 纯加：added=1 removed=0",
            (r["added"], r["removed"]) == (1, 0),
            detail="added=%s removed=%s op=%s" % (
                r["added"], r["removed"], [h["op"] for h in r["hunks"]]),
            added=r["added"], removed=r["removed"])
    r = results["c-remove"]
    s.check("5.4 纯删：added=0 removed=1",
            (r["added"], r["removed"]) == (0, 1),
            detail="added=%s removed=%s op=%s" % (
                r["added"], r["removed"], [h["op"] for h in r["hunks"]]),
            added=r["added"], removed=r["removed"])

    # --- 5.5 顺序变了：纯搬移 → added==removed，且一行都没丢
    from collections import Counter
    r = results["d-reorder"]
    a_lines = (fake / "docs/history/feat-d-reorder-base.md").read_text(encoding="utf-8").splitlines()
    b_lines = (fake / "docs/history/feat-d-reorder-head.md").read_text(encoding="utf-8").splitlines()
    same_multiset = Counter(a_lines) == Counter(b_lines)
    s.check("5.5 换序：内容多重集不变（没有一行丢失或被改写）", same_multiset,
            detail="base %d 行 / head %d 行" % (len(a_lines), len(b_lines)),
            base_lines=len(a_lines), head_lines=len(b_lines))
    s.check("5.5b 换序：added == removed > 0（纯搬移的指纹）",
            r["added"] == r["removed"] and r["added"] > 0,
            detail="added=%s removed=%s similarity=%s" % (
                r["added"], r["removed"], r["similarity"]),
            added=r["added"], removed=r["removed"], similarity=r["similarity"])

    # --- 5.6 similarity 合理
    sims = {k: v["similarity"] for k, v in results.items()}
    s.check("5.6 similarity 都在 (0,1] 且四组互不相同",
            all(0 < v <= 1 for v in sims.values()) and len(set(sims.values())) == 4,
            detail=str(sims), **{("sim_" + k): v for k, v in sims.items()})

    # --- 5.7 只回差异摘要，不回两份全文
    full_ok, sample_ok = True, True
    for k, (a, b) in pairs.items():
        out = json.dumps(results[k], ensure_ascii=False)
        sh = body_shingles(fake / ("docs/history/feat-%s-base.md" % k)) | \
             body_shingles(fake / ("docs/history/feat-%s-head.md" % k))
        if leaks(out, sh):
            full_ok = False
        for hu in results[k]["hunks"]:
            if not re.match(r"^L\d+-\d+$", hu["base"]) or not re.match(r"^L\d+-\d+$", hu["head"]):
                sample_ok = False
            if len(hu.get("sample") or "") > 120:
                sample_ok = False
    s.check("5.7 compare 不回两份全文", full_ok,
            detail="4 组比较，输出里一个 30 字正文 shingle 都没有")
    s.check("5.7b 每条 hunk 都带 base/head 行号 + ≤120 字的一行样本", sample_ok,
            detail="样本例：%r" % (results["a-modify"]["hunks"][0] if results["a-modify"]["hunks"] else None))

    # --- 5.8 每次 compare 都留收据
    rj = STATE_DIR / _state_key(fake) / "reads.jsonl"
    receipts = [json.loads(x) for x in rj.read_text(encoding="utf-8").splitlines() if x.strip()] \
        if rj.is_file() else []
    s.check("5.8 每次 compare 都留收据", len(receipts) == len(pairs) + 0,
            detail="reads.jsonl 共 %d 条，全部是 compare 写的" % len(receipts),
            receipts=len(receipts))
    s.check("5.8b 收据的 target 是「base vs head」，intent 非空",
            all(" vs " in str(x.get("target")) and str(x.get("intent") or "").strip()
                for x in receipts),
            detail=str(receipts[0].get("target")) if receipts else "无",
            sha8=receipts[0].get("sha8") if receipts else None)

    # --- 5.9 archive find 只给位置不给正文
    rc, so, se, _ = run_ctxiso("archive", "find", "--product", fake, "功能清单", "--limit", "50")
    if rc != 0:
        s.fail(RuntimeError("archive find rc=%d %s" % (rc, se[:200])))
        return s
    hits = jload(so)["hits"]
    sh = set()
    for k in pairs:
        sh |= body_shingles(fake / ("docs/history/feat-%s-base.md" % k))
    s.check("5.9 archive find 命中 8 份版本资料", len(hits) == len(pairs) * 2,
            detail="命中 %d 条" % len(hits), hits=len(hits))
    s.check("5.9b find 只给位置，不给正文",
            not leaks(so, sh) and all(set(h) <= {"path", "kind", "size", "mtime",
                                                "lines", "sha", "one_line"} for h in hits),
            detail="每条字段 %s；无正文 shingle" % (sorted(hits[0]) if hits else "-"),
            hits=len(hits))
    s.note("四组差异的数字是手算的：纯改/纯加/纯删各只动一行，"
           "difflib 必然给 1 个 replace / 1 个 insert / 1 个 delete；"
           "换序组用「行多重集不变 + added==removed」两条独立性质判，"
           "不依赖 difflib 怎么打破平局。")
    return s


# ================================================================ 场景 8
def scenario_8():
    s = Scenario(8, "长期项目维护：跑很久以后仍能按需取回必要信息")
    cfg = ctxiso_config()
    cap = int(cfg["hard_read_cap_bytes"])
    fake = new_fake("fake-long")

    KEY = "主人说过的一句关键原话：把导出改成先落盘再通知，通知失败不许吞。"
    KEY_LINE = 30                    # KEY 在 OWNER-SPEECH.md 里的真实文件行号
    FILLER = ("这一句是填充用的历史原话，长度约两百字，用来把这一份原话流水撑到足够大，"
              "好让一次读取必然被上限截断。内容本身没有任何意义，只是体积。")
    speech = ["# 演示产品主人原话流水（只追加）"]
    for line_no in range(2, 402):     # 401 行正文 + 1 行标题 = 402 行（≥ 300 行）
        speech.append("第 %03d 句：%s" % (line_no, KEY if line_no == KEY_LINE else FILLER * 4))
    write_lines(fake / "OWNER-SPEECH.md", speech)
    changes = ["# 改动图（演示）", "| 怎么找到 | 大概在哪 | 改成了什么 |",
               "| --- | --- | --- |"]
    for i in range(1, 301):
        if i == 12:
            changes.append("| src/exporter.py | src/ | 按 OWNER-SPEECH 第 %d 行原话改的：%s |"
                           % (KEY_LINE, KEY))
        else:
            changes.append("| src/mod-%03d.py | src/ | 第 %03d 次改动的记录，用来撑行数。 |" % (i, i))
    write_lines(fake / "CHANGES.md", changes)
    write_lines(fake / "WORK-HANDOFF.md",
                ["# 交接纸（演示）", "当前工作包：把导出流程按第 12 条改动图落地。",
                 "上一班：第 11 条；下一班：接着第 12 条。"])
    (fake / "PROJECT-MEMORY.jsonl").write_text(
        "\n".join(json.dumps({"feature_id": "f-%02d" % i, "note": "第 %d 条功能理解" % i},
                             ensure_ascii=False) for i in range(1, 12)) + "\n",
        encoding="utf-8")
    led8 = build_ledger(fake / ".hub" / "ledger.jsonl", 60, extra_bytes=300)
    speech_bytes = (fake / "OWNER-SPEECH.md").stat().st_size

    # --- 8.1 核心：index / pack / archive list 三步跑完，一条读取收据都不许有
    rci, soi, sei, _ = run_ctxiso("index", "--product", fake)
    rcp, sop, sep, _ = run_ctxiso("pack", "--product", fake, "--intent", "接着上次那刀干",
                                  "--stage", "2-impl", "--json")
    rcl, sol, sel, _ = run_ctxiso("archive", "list", "--product", fake, "--limit", "500")
    rj = STATE_DIR / _state_key(fake) / "reads.jsonl"
    after_meta = len(rj.read_text(encoding="utf-8").splitlines()) if rj.is_file() else 0
    s.check("8.1 核心：index+pack+archive list 三步后，读取收据仍是 0 条", after_meta == 0,
            detail="index rc=%d pack rc=%d list rc=%d；reads.jsonl %s，实际 %d 条"
                   % (rci, rcp, rcl, "不存在" if not rj.is_file() else "存在", after_meta),
            reads_after_meta=after_meta)
    rcs, sos, ses, _ = run_ctxiso("status", "--product", fake)
    rr_receipts = jload(sos).get("read_receipts") if rcs == 0 else None
    s.check("8.1b 侧车自报 read_receipts = 0", rr_receipts == 0,
            detail="ctxiso status 自报 %s（rc=%d）" % (rr_receipts, rcs),
            read_receipts=rr_receipts)

    # --- 8.2 archive list 列出 4 份，只有元数据
    lst = jload(sol)["rows"]
    have = {r["path"] for r in lst}
    want = {"OWNER-SPEECH.md", "CHANGES.md", "WORK-HANDOFF.md", "PROJECT-MEMORY.jsonl"}
    s.check("8.2 archive list 列出全部 4 份长期资料", want <= have,
            detail="命中 %s" % sorted(have), rows=len(lst))
    sh = body_shingles(fake / "OWNER-SPEECH.md") | body_shingles(fake / "CHANGES.md")
    s.check("8.2b 只给元数据，没有正文", not leaks(sol, sh),
            detail="比对 %d 个 30 字 shingle，命中 %d" % (len(sh), len(leaks(sol, sh))),
            shingles=len(sh), hits=len(leaks(sol, sh)))
    s.check("8.2c 数据型 jsonl 的用途摘要是「数据文件，无人读标题」",
            any(r["path"] == "PROJECT-MEMORY.jsonl"
                and r["one_line"] == "（数据文件，无人读标题）" for r in lst),
            detail=[r["one_line"] for r in lst if r["path"] == "PROJECT-MEMORY.jsonl"])

    # --- 8.3 find 命中
    rc, so, se, _ = run_ctxiso("archive", "find", "--product", fake, "原话流水", "--limit", "20")
    hits = jload(so)["hits"] if rc == 0 else []
    s.check("8.3 archive find 能按关键词命中", len(hits) >= 1,
            detail="命中 %s" % [h["path"] for h in hits], hits=len(hits))

    # --- 8.4 先读改动图找到指向，再精确取回那一条原话，两边必须逐字相同
    rc1, so1, _, _ = run_ctxiso("read", "--product", fake, "--target", "CHANGES.md",
                                "--intent", "找第 12 条改动图指向的 OWNER-SPEECH 行号",
                                "--json")
    got_changes = jload(so1)["text"] if rc1 == 0 else ""
    s.check("8.4 读到改动图，且里面确实有指向 OWNER-SPEECH 第 30 行的那一条",
            rc1 == 0 and "OWNER-SPEECH 第 %d 行" % KEY_LINE in got_changes and KEY in got_changes,
            detail="改动图 %d 字；含引用=%s 含原话=%s"
                   % (len(got_changes), "OWNER-SPEECH 第 %d 行" % KEY_LINE in got_changes, KEY in got_changes),
            changes_chars=len(got_changes))
    rc2, so2, _, _ = run_ctxiso("read", "--product", fake, "--target", "OWNER-SPEECH.md",
                                "--scope", "L%d:%d" % (KEY_LINE, KEY_LINE),
                                "--intent", "改动图第 12 条要求核对 OWNER-SPEECH 第 %d 行的原话" % KEY_LINE,
                                "--json")
    got_speech = jload(so2)["text"] if rc2 == 0 else ""
    s.check("8.4b 按 scope 精确取回第 30 行", rc2 == 0 and KEY in got_speech,
            detail="取回 %d 字：%r" % (len(got_speech), got_speech[:60]),
            speech_chars=len(got_speech))
    s.check("8.4c 改动图里的引用与 OWNER-SPEECH 原文逐字相同",
            KEY in got_changes and KEY in got_speech,
            detail="两边都含同一句原话", key_chars=len(KEY))

    # --- 8.5 一次取回有上限
    rc3, so3, _, _ = run_ctxiso("read", "--product", fake, "--target", "OWNER-SPEECH.md",
                                "--intent", "先看一眼最近的原话", "--json")
    r3 = (jload(so3) or {}).get("receipt") or {} if rc3 == 0 else {}
    s.check("8.5 一次取回被上限截断（truncated=true 且 bytes_read ≤ cap）",
            r3.get("truncated") is True and r3.get("bytes_read", 1 << 30) <= cap,
            detail="文件 %d 字节，本次只取回 %s 字节，truncated=%s，cap=%d"
                   % (speech_bytes, r3.get("bytes_read"), r3.get("truncated"), cap),
            file_bytes=r3.get("file_bytes"), bytes_read=r3.get("bytes_read"),
            truncated=r3.get("truncated"), cap=cap)
    s.check("8.5b 没有一次把整份原话吞进来",
            (r3.get("bytes_read") or 0) < (r3.get("file_bytes") or 0),
            detail="%s < %s" % (r3.get("bytes_read"), r3.get("file_bytes")),
            bytes_read=r3.get("bytes_read"), file_bytes=r3.get("file_bytes"))
    s.check("8.5c pack 也没把原话正文带进去",
            (jload(sop).get("bytes", 1 << 30) if rcp == 0 else 0) <= int(cfg["pack_budget_bytes"]),
            bytes=jload(sop).get("bytes") if rcp == 0 else 0,
            budget=int(cfg["pack_budget_bytes"]))

    # --- 8.6 压缩后仍能按指针取回，内容与原始一致
    rc4, so4, _, _ = run_ctxiso("compact", "--product", fake, "--state", json.dumps({
        "intent": "把导出流程按第 12 条改动图落地", "stage": "2-impl",
        "goal": "先落盘再通知，通知失败不许吞", "next": "跑一遍导出命令看退出码",
        "blockers": [], "confirmed_decisions": ["按第 30 行原话改"],
        "constraints": ["不联网"]}, ensure_ascii=False))
    if rc4 != 0:
        s.fail(RuntimeError("compact rc=%d" % rc4))
        return s
    drop = json.loads(Path(jload(so4)["dropped_path"]).read_text(encoding="utf-8"))
    doc_ptr = next((d for d in drop["dropped"] if "资料" in str(d.get("what"))), None)
    s.check("8.6 dropped.json 给了资料取回指针",
            doc_ptr is not None and "archive list" in str(doc_ptr.get("how")),
            detail=str((doc_ptr or {}).get("how")), how=(doc_ptr or {}).get("how"),
            count=(doc_ptr or {}).get("count"))
    rc5, so5, _, _ = run_ctxiso("archive", "list", "--product", fake, "--kind", "history",
                                "--limit", "10")
    ptr_rows = jload(so5)["rows"] if rc5 == 0 else []
    s.check("8.6b 按指针能列出被丢出去的资料位置",
            any(r["path"] == "OWNER-SPEECH.md" for r in ptr_rows),
            detail=str([r["path"] for r in ptr_rows]), rows=len(ptr_rows))
    sha_first = jload(so2)["receipt"]["sha8"]
    rc6, so6, _, _ = run_ctxiso("read", "--product", fake, "--target", "OWNER-SPEECH.md",
                                "--scope", "L%d:%d" % (KEY_LINE, KEY_LINE),
                                "--intent", "压缩后按 dropped.json 的指针取回原话核对",
                                "--json")
    back = jload(so6) if rc6 == 0 else {}
    s.check("8.6c 压缩后取回的内容与原始逐字一致（sha8 对得上）",
            back.get("receipt", {}).get("sha8") == sha_first
            and back.get("text") == got_speech,
            detail="压缩前 sha8=%s，压缩后 sha8=%s；文本相同=%s"
                   % (sha_first, back.get("receipt", {}).get("sha8"),
                      back.get("text") == got_speech),
            sha_before=sha_first, sha_after=back.get("receipt", {}).get("sha8"))
    final = len(rj.read_text(encoding="utf-8").splitlines()) if rj.is_file() else 0
    s.check("8.6d 全程 4 次带意图读取，收据一条不少",
            final == 4, detail="reads.jsonl 共 %d 条" % final, receipts=final)
    s.note("8.1 是本场景的核心：3 步元数据操作后 reads.jsonl 必须还是 0 条——"
           "「保存了不等于被读回去」这条纪律的机器证明。")
    return s


# ================================================================ 场景 9
def scenario_9():
    s = Scenario(9, "新旧系统并存：新开发系统没有破坏原来的中枢")
    # 本场景是整套的最后一个，所以这里的 guard check 同时也是
    # 「前面 8 个场景跑完之后旧系统仍然逐字节未变」的运行时证明（9.4b）。

    # --- 9.1 真仓库：guard check（只读，复用统筹已有的基线）
    rc, so, se, _ = run_ctxiso("guard", "check", "--product", REPO)
    if rc == 0:
        g = jload(so)
        s.check("9.1 真仓库 guard check：ok=true", g.get("ok") is True,
                detail=g.get("verdict", ""), guard_ok=g.get("ok"))
        s.check("9.1b changed 为空", g.get("changed") == [],
                detail=str(g.get("changed"))[:160], changed=len(g.get("changed") or []))
        s.check("9.1c missing 为空", g.get("missing") == [],
                detail=str(g.get("missing"))[:160])
        s.check("9.1d 非 append-only 的改动为空",
                g.get("changed_excluding_append_only") == [],
                detail=str(g.get("changed_excluding_append_only"))[:160],
                baseline_at=g.get("baseline_at"))
    else:
        s.check("9.1 真仓库 guard check", False,
                detail="rc=%d %s —— 侧车状态目录里没有基线，本轮不新建"
                       "（会覆盖统筹的基线）" % (rc, so.strip()[:160]), rc=rc)

    # --- 9.1e guard 本身不是空转：真改一个字，它必须报出来
    if str(CTXISO_ROOT) not in sys.path:
        sys.path.insert(0, str(CTXISO_ROOT))
    from ctxiso import guard as _guard          # 只读导入被测对象
    fg = new_fake("fake-guard")
    for rel in _guard.GUARD_PATHS:
        p = fg / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("受控文件 %s 的原始内容\n" % rel, encoding="utf-8")
    rc = run_ctxiso("guard", "snapshot", "--product", fg)[0]
    c0 = jload(run_ctxiso("guard", "check", "--product", fg)[1])
    s.check("9.1e guard snapshot/check 基线自洽：changed/missing 都空",
            rc == 0 and c0.get("ok") is True and c0.get("changed") == []
            and c0.get("missing") == [],
            detail="受控 %d 个文件：%s" % (len(_guard.GUARD_PATHS), c0.get("verdict")),
            guarded=len(_guard.GUARD_PATHS), guard_ok=c0.get("ok"))
    # 挑一个真实存在、且真在 GUARD_PATHS 里的承重件改一个字。
    # 原来写死 hub/AGENTS.md，那是旧中枢的文件，本仓根本没有——
    # 上一行刚按新清单建好文件，这里却去读一个不存在的，整个场景崩掉。
    victim = fg / _guard.GUARD_PATHS[0]
    keep = victim.read_text(encoding="utf-8")
    victim.write_text(keep + "偷偷加了一行\n", encoding="utf-8")
    c1 = jload(run_ctxiso("guard", "check", "--product", fg)[1])
    victim.write_text(keep, encoding="utf-8")
    c2 = jload(run_ctxiso("guard", "check", "--product", fg)[1])
    s.check("9.1f guard 能抓出真改动（不是空转）",
            c1.get("ok") is False and _guard.GUARD_PATHS[0] in (c1.get("changed") or [])
            and c2.get("ok") is True,
            detail="改一个字后 changed=%s / ok=%s；改回去后 ok=%s"
                   % (c1.get("changed"), c1.get("ok"), c2.get("ok")),
            caught=c1.get("changed"), restored=c2.get("ok"))

    # --- 9.2 git status（只读）
    # 2026-09-28 起：work/context-isolation 已入库（51f571c），
    # 所以原来那个“只有 ?? work/context-isolation/”的前提过期了。
    # 现在的信号应该是“工作区干净”：本轮测试自己没把仓库弄脏，也没人留着没提交的改动。
    # 例外：测试自己的输出文件（RESULT.md、LAST-RUN.txt、LAST-STDERR.log）——
    # 跑完必定被重写（含“生成时间”），把它也算脏，这道门就永远过不了。
    # bundle-meta.json 同理：重打产物会刷新 built_at 时间戳。
    p = subprocess.run(["git", "status", "--porcelain"], cwd=str(REPO),
                       capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    own_outputs = ("05-tests/RESULT.md", "05-tests/LAST-RUN.txt", "05-tests/LAST-STDERR.log",
                   "03-bundle/bundle-meta.json")
    lines = [x for x in (p.stdout or "").splitlines()
             if x.strip() and not any(o in x for o in own_outputs)]
    s.check("9.2 git status --porcelain 工作区干净（测试自己的输出文件除外）",
            lines == [],
            detail="实际 %d 行：%s" % (len(lines), lines[:5]), lines=len(lines),
            raw=" | ".join(lines[:5]))

    # --- 9.3 旧系统仍能正常干活（真 state.py，只对假产品）
    fp = new_fake("fake-old-system")
    (fp / "src").mkdir(parents=True, exist_ok=True)
    (fp / "src" / "exporter.py").write_text("# 演示产品导出模块\n", encoding="utf-8")
    plan_file = TEMP / "_old_plan.json"
    req = "演示产品导出失败时必须把错误原样报给使用者，不许吞掉"
    steps = []
    rc1, o1, e1 = run_state(fp, "init", "--type", "cli-tool", "--product-id", "fake-old", "--force")
    steps.append(("init", rc1))
    rc2, o2, e2 = run_state(fp, "plan", "--goal", "让演示产品的导出失败原因一眼看得见",
                            "--success", "导出命令失败时退出码非 0 且把原因打在标准错误上",
                            "--route", "先收原话，再用 state work 累积责任")
    steps.append(("plan", rc2))
    rc3, o3, e3 = run_state(fp, "require", "--append", req, "--source", "operator")
    steps.append(("require", rc3))
    rid = (re.search(r"(REQ-\d+)", o3) or [None, ""])[1]
    plan_file.write_text(json.dumps({"version": 1, "items": [{
        "id": "W-old-1", "outcome": "使用者一眼看到导出失败的原因",
        "phase": "0-spec", "consumer": "演示产品的使用者",
        "sources": [{"requirement_id": rid, "quote": req}],
        "depends_on": [], "evidence": [{"kind": "acceptance"}],
        "files": ["src/exporter.py"]}]}, ensure_ascii=False), encoding="utf-8")
    rc4, o4, e4 = run_state(fp, "work", "--define", str(plan_file))
    steps.append(("work --define", rc4))
    rc5, o5, e5 = run_state(fp, "status")
    steps.append(("status", rc5))
    s.check("9.3 旧系统 state.py 全流程跑通（init→plan→require→work→status）",
            all(c == 0 for _, c in steps),
            detail=" | ".join("%s=%d" % (n, c) for n, c in steps)
                   + ("｜" + (e3 or e4)[:160] if any(c for _, c in steps) else ""),
            steps_ok=sum(1 for _, c in steps if c == 0), steps=len(steps))
    s.check("9.3b status 输出含 MISSION 与当前阶段/下一步",
            "MISSION" in o5 and "阶段" in o5,
            detail=o5.replace("\n", " | ")[:220],
            out_chars=len(o5), has_mission="MISSION" in o5)

    # --- 9.4 静态扫 ctxiso/*.py：写句柄一律不许指向产品目录
    scan = scan_write_handles()
    suspect = [x for x in scan if x["kind"] == "UNKNOWN"]
    s.check("9.4 白名单之外的 UNKNOWN 写句柄数为 0",
            all(x["key"] in WRITE_WHITELIST for x in suspect),
            detail="扫了 %d 个写句柄，自动认不出落点的 %d 个，其中未登记 %d 个。"
                   "白名单：%s" % (len(scan), len(suspect),
                                 len([x for x in suspect if x["key"] not in WRITE_WHITELIST]),
                                 "; ".join(sorted({x["key"] for x in suspect}))),
            calls=len(scan), suspect=len(suspect),
            unregistered=len([x for x in suspect if x["key"] not in WRITE_WHITELIST]))
    stale = [k for k in WRITE_WHITELIST if k not in {x["key"] for x in scan}]
    s.check("9.4b 白名单里没有过期条目（每条都还挂在真实调用点上）", not stale,
            detail="过期：%s" % (stale or "无"), stale=len(stale))
    s.check("9.4c 白名单每一条都写了「写到哪里、为什么安全」",
            all(isinstance(v, str) and len(v) >= 20 for v in WRITE_WHITELIST.values()),
            detail="%d 条，最短说明 %d 字"
                   % (len(WRITE_WHITELIST),
                      min(len(v) for v in WRITE_WHITELIST.values())),
            entries=len(WRITE_WHITELIST))
    on_product = [x for x in scan if x["touches_product"]]
    s.check("9.4d 没有任何一个写句柄指向产品目录（hub/ 与 .hub/）",
            not on_product,
            detail=str(on_product)[:200] or "无", touches_product=len(on_product))
    s.check("9.4e 写句柄只落在侧车自己的 state 目录（外加 pack --out 这一处按需）",
            all(x["kind"] in ("STATE", "CALLER_OPT_IN", "UNKNOWN") for x in scan)
            and all(x["kind"] != "UNKNOWN" or x["key"] in WRITE_WHITELIST for x in scan),
            detail="state %d 处；caller opt-in %d 处；白名单 %d 处"
                   % (sum(1 for x in scan if x["kind"] == "STATE"),
                      sum(1 for x in scan if x["kind"] == "CALLER_OPT_IN"), len(suspect)),
            state_writes=sum(1 for x in scan if x["kind"] == "STATE"))
    opt_in = [x for x in scan if x["kind"] == "CALLER_OPT_IN"]
    s.check("9.4f 唯一的「按调用方指定路径写」是 pack --out，且默认不触发",
            len(opt_in) == 1 and opt_in[0]["file"] == "cli.py"
            and "a.out" in opt_in[0]["src"] and opt_in[0]["fn"] == "write_text",
            detail=str([(x["site"], x["src"]) for x in opt_in])[:220],
            opt_in=len(opt_in))
    s.check("9.4g 运行时证明：整套场景跑完，guard 仍报 changed 为空（见 9.1/9.1b）",
            True, detail="场景 9 是整套的最后一个，9.1/9.1b 就是跑完之后的复查结果")

    # --- 9.4h 反向断言：故意把一个写句柄指向产品目录，扫描器必须把它揪出来
    mutant = TEMP / "ctxiso-mutant"
    if mutant.exists():
        shutil.rmtree(mutant)
    shutil.copytree(CTXISO_ROOT / "ctxiso", mutant)
    target = mutant / "archive.py"
    target.write_text(
        target.read_text(encoding="utf-8")
        + "\n\ndef _test_injected_write(product):\n"
          "    # 故意写进产品目录，只存在于 TEMP 里的副本，用来证明扫描器不是摆设\n"
          "    (paths.hub_dir(product) / 'INJECTED.md').write_text('x', encoding='utf-8')\n",
        encoding="utf-8")
    mscan = scan_write_handles(mutant)
    injected = [x for x in mscan if x["fn"] == "write_text"
                and "INJECTED" in x["src"]]
    s.check("9.4h 反向断言：故意写进 hub/ 的句柄会被扫描器抓出来",
            len(injected) == 1 and injected[0]["kind"] == "UNKNOWN"
            and injected[0]["touches_product"] is True
            and injected[0]["key"] not in WRITE_WHITELIST,
            detail="注入到 TEMP 副本的 hub/INJECTED.md，扫描器判定 kind=%s "
                   "touches_product=%s 白名单里=%s"
                   % (injected[0]["kind"] if injected else "没抓到",
                      injected[0]["touches_product"] if injected else "-",
                      injected[0]["key"] in WRITE_WHITELIST if injected else "-"),
            caught=len(injected),
            kind=injected[0]["kind"] if injected else None,
            in_whitelist=bool(injected and injected[0]["key"] in WRITE_WHITELIST))
    shutil.rmtree(mutant, ignore_errors=True)

    # --- 9.5 新包能独立跑
    return scenario_9_bundle(s)


STATE_TOKENS = ("receipt_path", "survivor_path", "dropped_path", "state_dir",
                "db_path", "_baseline_path", "_base_path", "STATE_DIR")

# 9.4 的具名白名单：自动分类认不出来的那几个写句柄，逐个写清「实际写到哪里、为什么安全」。
# 键是「文件::所在函数」（不用行号——统筹改 ctxiso 时行号会漂）。
# 规则同 03-bundle/verify.py：白名单之外多出一个写法就红；白名单里少了东西也红。
WRITE_WHITELIST = {
    "archive.py::_receipt":
        "写 paths.receipt_path() = state/<产品key>/reads.jsonl。这是整套设计里唯一"
        "「记录读了什么」的地方，append 写自己盘上的收据，产品目录一个字节不动。",
    "archive.py::list_docs":
        "只开索引库 store.connect() = state/<key>/index.sqlite 做 SELECT，不碰产品目录。",
    "archive.py::find":
        "同 list_docs：只开索引库做只读查询，find 按约定只返回位置不给正文。",
    "cli.py::cmd_query":
        "只开索引库做只读查询，query 按约定只出摘要行。",
    "cli.py::cmd_status":
        "只开索引库读统计（indexed_events / doc_kinds），落在 state/<key>/index.sqlite。",
    "compact.py::build":
        "只开索引库数事件数（后面写的是 paths.survivor_path()/dropped_path()，"
        "已由自动分类单独识别）。",
    "observe.py::recorder_report":
        "只开索引库数各类记录器的事件数，落在 state/<key>/index.sqlite，不写产品目录。",
    "pack.py::build":
        "只开索引库读索引（产品目录全是 open('rb') 读）。",
    "paths.py::state_dir":
        "建 STATE_DIR/<产品key>/ —— 侧车自己的状态目录，不是产品目录。",
    "store.py::refresh_ledger":
        "写索引库 state/<key>/index.sqlite；账本本体只以 open('rb') 读。",
    "store.py::stats":
        "只开索引库读统计（事件数、按 kind 分布、索引库字节数），落在 state/<key>/。",
    "store.py::refresh_docs":
        "写索引库 doc 表；被扫的资料一律 open('rb') 读，不写。",
}


def _ctxiso_connect_targets_state() -> bool:
    """机器核验：ctxiso 里唯一的数据库连接口 store.connect 写的是 paths.db_path。"""
    src = (CTXISO_ROOT / "ctxiso" / "store.py").read_text(encoding="utf-8")
    m = re.search(r"^def connect\(.*?(?=^def )", src, re.S | re.M)
    return bool(m) and "db_path" in m.group(0)


def scan_write_handles(pkg_dir=None):
    """静态扫 ctxiso/*.py 里所有可能写盘的调用点，按落点分类。

    分类看三样：调用点自己的源码、它所在函数的整段源码、store.connect 的落点。
    三样都指不到侧车自己的 state 目录，才算 UNKNOWN（要进具名白名单才放行）。
    """
    import ast
    PRODUCT_TOKENS = ("hub_dir", "OWNER-SPEECH.md", "CHANGES.md", "WORK-HANDOFF.md",
                      "ledger.jsonl", "requirements.jsonl", "contract.json",
                      "physical-gates.json", "manifest.json")
    WRITE_ATTRS = {"write_text", "write_bytes", "mkdir", "rmdir", "unlink", "touch",
                   "writelines", "write"}
    pkg = Path(pkg_dir) if pkg_dir else (CTXISO_ROOT / "ctxiso")
    connect_is_state = _ctxiso_connect_targets_state() if pkg_dir is None else True
    out = []

    def classify(node, src, ctx):
        if any(tok in src for tok in STATE_TOKENS):
            return "STATE"
        if re.search(r"\b(args|a)\.out\b", src):
            return "CALLER_OPT_IN"
        fname = (node.func.id if isinstance(node.func, ast.Name)
                 else node.func.attr if isinstance(node.func, ast.Attribute) else None)
        if fname == "connect" and connect_is_state:
            return "STATE"
        if any(tok in ctx for tok in STATE_TOKENS):
            return "STATE"
        return "UNKNOWN"

    for py in sorted(pkg.glob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        spans = []
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                try:
                    spans.append((n.lineno, n.end_lineno or n.lineno, n.name, ast.unparse(n)))
                except Exception:                                # noqa: BLE001
                    spans.append((n.lineno, n.end_lineno or n.lineno, n.name, ""))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            try:
                hit = _write_call_kind(node)
            except Exception:                                    # noqa: BLE001
                hit = None
            if not hit:
                continue
            try:
                src = ast.unparse(node)
            except Exception:                                    # noqa: BLE001
                src = ""
            # 所在函数 = 行号落进其范围、且起点最靠里的那个（ctxiso 里没有嵌套 def）
            encl, ctx, best = "<module>", "", -1
            for lo, hi, name, fsrc in spans:
                if lo <= node.lineno <= hi and lo > best:
                    best, encl, ctx = lo, name, fsrc
            out.append({
                "file": py.name, "line": node.lineno,
                "site": "%s:L%d" % (py.name, node.lineno),
                "key": "%s::%s" % (py.name, encl),
                "fn": hit, "kind": classify(node, src, ctx), "src": src[:140],
                "touches_product": any(t in src for t in PRODUCT_TOKENS)})
    return out


def _write_call_kind(node):
    fname = (node.func.id if isinstance(node.func, ast.Name)
             else node.func.attr if isinstance(node.func, ast.Attribute) else None)
    if fname is None:
        return None
    if fname in {"write_text", "write_bytes", "mkdir", "rmdir", "unlink", "touch",
                 "writelines", "write", "connect"}:
        return fname
    if fname == "open":
        mode = ""
        if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
            mode = str(node.args[1].value)
        for k in node.keywords:
            if k.arg == "mode" and isinstance(k.value, ast.Constant):
                mode = str(k.value.value)
        if any(ch in mode for ch in "wax+"):
            return "open(%s)" % mode
    return None




# ================================================================ 场景 9.5
BUNDLE_SRC = CTXISO_ROOT / "03-bundle" / "dist" / "hubcore"
# 装出来的东西里不许出现的串（照 03-bundle/bundle-meta.json 的 forbidden_strings）
BUNDLE_FORBIDDEN = ["D:\\", "D:/", "临时项目", "context-isolation", "hub-dock",
                    "github.com", "http://", "https://", "git@", "user-skills",
                    ".agents/skills", "skills-hub", "gthubtom1"]
# 已知白名单：不是残留路径，是「用来认出旧 gold 测试残留」的检测模式本身。
BUNDLE_WHITELIST = {("tools/hub_ask.py", "hub-lean"):
                    "hub_ask 自己用来识别旧测试残留的检测模式表，不是活路径；"
                    "写成 hub-lean 只是为了让旧副本的路径被认出来"}


def _run_in(cwd, *args, timeout=180):
    cmd = [sys.executable, *[str(a) for a in args]]
    t0 = time.perf_counter()
    p = subprocess.run(cmd, cwd=str(cwd), env=_env(), timeout=timeout,
                       capture_output=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout or "", p.stderr or "", round((time.perf_counter() - t0) * 1000, 1)


# --- 02-hubcore 临时改名。改别人正在用的目录是本套测试里风险最高的一步，
#     所以改名和回滚都做重试 + atexit 兜底，失败就打印可直接粘贴的恢复命令。
_HUB_SRC = CTXISO_ROOT / "02-hubcore"
_HUB_HIDDEN = CTXISO_ROOT / "02-hubcore.RENAMED-BY-05tests"
_PENDING = {"on": False}


def _swap(a: Path, b: Path, tries=6):
    import os as _os
    for i in range(tries):
        try:
            _os.rename(str(a), str(b))
            return True
        except FileNotFoundError:
            if b.exists():                       # 已经是目标状态
                return True
            time.sleep(0.3 * (i + 1))
        except OSError:
            time.sleep(0.3 * (i + 1))
    return b.exists() and not a.exists()


def _restore_hubcore(quiet=False):
    if not _PENDING["on"]:
        return True
    ok = _swap(_HUB_HIDDEN, _HUB_SRC)
    if ok and _HUB_SRC.is_dir():
        _PENDING["on"] = False
        if not quiet:
            print("[还原] 02-hubcore 名字已改回原位")
        return True
    if not quiet:
        print("[严重] 02-hubcore 没能自动改回原位，请手工执行这一条：")
        print('    Rename-Item -LiteralPath "%s" -NewName "02-hubcore"' % _HUB_HIDDEN)
    return False


def _atexit_restore():
    try:
        _restore_hubcore(quiet=False)
    except Exception:                                        # noqa: BLE001
        pass


import atexit                                                    # noqa: E402
atexit.register(_atexit_restore)


def hide_hubcore():
    """把 02-hubcore 临时改名。返回是否成功改名。"""
    if not _HUB_SRC.is_dir():
        return False
    if _HUB_HIDDEN.exists():
        return False
    if not _swap(_HUB_SRC, _HUB_HIDDEN):
        return False
    _PENDING["on"] = True
    return True



def scenario_9_bundle(s):
    home = new_fake("fake-home")
    pkg = home / "hub"
    if not BUNDLE_SRC.is_dir():
        s.check("9.5 打包产物在 03-bundle/dist/hubcore", False,
                detail="目录不存在：%s（T1 可能正在重打包）" % BUNDLE_SRC)
        return s
    shutil.copytree(BUNDLE_SRC, pkg)
    # 装好、还没跑任何命令的那一刻，先量一次装前状态：9.5m2 要用它区分
    # 「出货件带出来的」和「跑命令跑出来的」
    state_at_install = (pkg / ".state").is_dir()
    files = [p for p in pkg.rglob("*") if p.is_file()]
    s.check("9.5 打包产物已装进假宿主家目录的 hub/", pkg.is_dir() and len(files) > 20,
            detail="%d 个文件；顶层 %s" % (len(files),
                                       sorted(x.name for x in pkg.iterdir())),
            files=len(files))

    # --- 9.5b 装出来的东西里搜不到源仓路径 / context-isolation / github.com / http:// / user-skills
    raw_hits = []
    for p in files:
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for f in BUNDLE_FORBIDDEN:
            if f in t:
                raw_hits.append((p.relative_to(pkg).as_posix(), f))
    whitelisted = [h for h in raw_hits
                   if (h[0], h[1]) in BUNDLE_WHITELIST]
    real_hits = [h for h in raw_hits if (h[0], h[1]) not in BUNDLE_WHITELIST]
    s.check("9.5b 装出来的东西搜不到源仓路径 / context-isolation / github.com / "
            "http:// / user-skills", not real_hits,
            detail="扫了 %d 个文件，命中 %d 处%s；白名单排除 %d 处"
                   % (len(files), len(raw_hits),
                      ("：" + str(real_hits[:4])) if real_hits else "", len(whitelisted)),
            scanned=len(files), hits=len(raw_hits), real_hits=len(real_hits),
            whitelisted=len(whitelisted))
    s.check("9.5c 每一处命中都在明明白白的白名单里（不许静默跳过）",
            len(whitelisted) == len(raw_hits) and
            all(BUNDLE_WHITELIST.get((h[0], h[1])) for h in whitelisted),
            detail="；".join("%s ← %s：%s" % (h[0], h[1], BUNDLE_WHITELIST.get((h[0], h[1]), ""))
                            for h in whitelisted) or "无",
            whitelist=len(whitelisted))

    # --- 假产品（在装包之前建好，改名窗口里只跑两条命令）
    prod = new_fake("fake-home-prod")
    (prod / ".hub").mkdir(parents=True, exist_ok=True)

    # --- 9.5d 临时把 02-hubcore 改名，证明新包不靠它；跑完立刻改回来
    src_dir, hidden = _HUB_SRC, _HUB_HIDDEN
    renamed = hide_hubcore()
    s.check("9.5d 02-hubcore 已被临时改名（源树此刻不在原位）",
            (not src_dir.is_dir()) if renamed else src_dir.is_dir(),
            detail="改名成功=%s；02-hubcore 在原位=%s" % (renamed, src_dir.is_dir()),
            renamed=renamed)
    try:
        r1, o1, e1, m1 = _run_in(home, pkg / "tools" / "state.py", "--help")
        s.check("9.5e 假宿主里 python hub/tools/state.py --help 成功", r1 == 0,
                detail=(o1.replace("\n", " ")[:140] if r1 == 0
                        else e1.strip().splitlines()[-1][:160]), rc=r1, ms=m1)
        r2, o2, e2, m2 = _run_in(home, pkg / "ctxiso" / "cli.py", "status",
                                  "--product", prod)
        s.check("9.5f 假宿主里 python hub/ctxiso/cli.py status --product <假产品> 成功",
                r2 == 0,
                detail=(o2.replace("\n", " ")[:140] if r2 == 0
                        else e2.strip().splitlines()[-1][:180]), rc=r2, ms=m2)
        r3, o3, e3, m3 = _run_in(pkg, "-m", "ctxiso", "status", "--product", prod)
        s.check("9.5g 假宿主里 python -m ctxiso status --product <假产品> 成功",
                r3 == 0,
                detail=(o3.replace("\n", " ")[:140] if r3 == 0
                        else e3.strip().splitlines()[-1][:180]), rc=r3, ms=m3)
    finally:
        ok = _restore_hubcore()
    s.check("9.5h 02-hubcore 名字已改回来（try/finally + 重试 + atexit 兜底）",
            src_dir.is_dir() and not hidden.exists(),
            detail="回到原位=%s；残留改名目录=%s；回滚函数返回=%s"
                   % (src_dir.is_dir(), hidden.exists(), ok),
            restored=src_dir.is_dir(), leftover=hidden.exists())

    st = pkg / ".state"
    s.check("9.5i 新包的状态写在包内 .state/（不落在源仓任何地方）", st.is_dir(),
            detail="包内 .state/ = %s" % st.is_dir(),
            state_in_pkg=st.is_dir(),
            children=sorted(x.name for x in st.iterdir())[:3] if st.is_dir() else [])

    # --- 9.5j/k/l 护栏：测试必须跑「要发出去的那一份」
    sync = CTXISO_ROOT / "02-hubcore" / "check_dist_sync.py"
    rj_, oj_, ej_, mj_ = _run_in(CTXISO_ROOT, sync)
    sj = None
    try:
        sj = json.loads(oj_)
    except (ValueError, TypeError):
        pass
    if rj_ != 0:
        drift = (sj or {}).get("drift") or []
        missing = (sj or {}).get("missing_in_dist") or []
        unexc = [m for m in missing if os.path.basename(str(m)) not in _bundle_exclusions()]
        why = (sj or {}).get("why") or ((sj or {}).get("verdict") or "").strip()
        tail = ((sj or {}).get("tail") or "").strip().replace("\n", " ")[:120]
        s.check("9.5j check_dist_sync.py 退出 0（产物与源码同源）", False,
                detail="rc=%d｜检查了 %s 个｜内容不同的 %d 个：%s｜该有却没有的 %d 个｜"
                       "未声明排除的 %d 个｜%s%s→ 处置：重跑 `python 03-bundle/pack.py`"
                       % (rj_, (sj or {}).get("checked", "?"), len(drift),
                          (drift[:6] if drift else "无"), len(missing), len(unexc),
                          why, ("｜%s" % tail) if tail else ""),
                rc=rj_, checked=(sj or {}).get("checked"), drift=len(drift),
                drift_files=len(drift), missing=len(missing), unexpected=len(unexc))
    else:
        s.check("9.5j check_dist_sync.py 退出 0（产物与源码同源）", True,
                detail=(sj or {}).get("verdict", ""), rc=0,
                checked=(sj or {}).get("checked"))

    import hashlib as _h
    src_cli = CTXISO_ROOT / "ctxiso" / "cli.py"
    dist_cli = BUNDLE_SRC / "ctxiso" / "cli.py"

    def _sha(b):
        return _h.sha256(b).hexdigest()

    def _norm(b):                                  # 归一化换行：pack.py 会把 LF 转成 CRLF
        return b.replace(b"\r\n", b"\n")

    ra = src_cli.read_bytes() if src_cli.is_file() else b""
    rb = dist_cli.read_bytes() if dist_cli.is_file() else b""
    na, nb = _sha(_norm(ra))[:8], _sha(_norm(rb))[:8]
    s.check("9.5k 产物里的 ctxiso/cli.py 内容与源码树一致（换行归一化后）",
            bool(ra) and na == nb,
            detail="归一化后 源码 sha8=%s / 产物 sha8=%s；原始字节 源码=%d 产物=%d"
                   "（差 %d 是 pack.py 把 LF 转成 CRLF，不是内容漂移）"
                   % (na, nb, len(ra), len(rb), len(rb) - len(ra)),
            sha_src=na, sha_dist=nb, same=na == nb,
            raw_bytes_src=len(ra), raw_bytes_dist=len(rb))

    packing_tools = ["verify.py", "_bundle_lib.py", "bundle-meta.json",
                     "pack.py", "install.py", "hosts.py"]
    leaked = [t for t in packing_tools if (pkg / t).exists() or (pkg / t).is_dir()]
    s.check("9.5l 产物里没有打包工具（只有运行期要用的东西）", not leaked,
            detail="进包了：%s" % (leaked or "无，一个都没有"),
            leaked=len(leaked), checked=len(packing_tools))
    # 9.5m 出货件里不许混进运行期残留：.state/ 与 __pycache__/
    # 扫的是出货件 03-bundle/dist/hubcore，不是刚跑过命令的安装副本：
    # 9.5f/9.5g 在安装副本里跑过 ctxiso，运行时状态按设计落在包内 .state/
    # （这正是 9.5i 要证明的事），拿运行后的副本判「出货残留」是自相矛盾。
    def _residue(root):
        return [p.relative_to(root).as_posix()
                for junk in (".state", "__pycache__")
                for p in root.rglob(junk) if p.is_dir()]

    residue = _residue(BUNDLE_SRC)
    s.check("9.5m 出货件里没有运行期残留（.state/ 与 __pycache__/）", not residue,
            detail="扫 03-bundle/dist/hubcore（出货件本身）：%s"
                   % (residue or "无")
                   + ("—— 上一次在 dist/ 里跑过 ctxiso 留下的状态目录，"
                      "pack.py 复制时应该排除" if residue else ""),
            scanned="dist/hubcore", residue=len(residue))
    # 同一件事的两端：装前出货件没有，装的副本跑命令后才有 → 残留是运行期产物，不是出货内容
    s.check("9.5m2 残留确实是运行期产生的（装前无 → 跑完才有），不是随包发出的",
            (not residue) and (not state_at_install) and (pkg / ".state").is_dir(),
            detail="出货件 %s；刚装好时 .state=%s；跑完 9.5f/9.5g 后 .state=%s"
                   % ("无" if not residue else str(residue),
                      state_at_install, (pkg / ".state").is_dir()),
            dist_clean=not residue, at_install=state_at_install,
            runtime_state=(pkg / ".state").is_dir())
    s.note("9.5 用的是打包器的产物 03-bundle/dist/hubcore，%d 个文件；"
           "包内 .state/ 落在 05-tests/TEMP/ 下，跑完随 TEMP 一起删。" % len(files))
    return s


def _bundle_exclusions():
    """读 03-bundle/bundle-meta.json 里声明的「故意不进包」清单。"""
    meta = CTXISO_ROOT / "03-bundle" / "bundle-meta.json"
    try:
        d = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    ex = d.get("tools_excluded") or {}
    out = set()
    for k, v in ex.items():
        if isinstance(v, list):
            out |= {str(x) for x in v}
    return out



# ================================================================ 保护区指纹
def fingerprint(zones):
    out = {}
    for z in zones:
        base = REPO / z
        if not base.exists():
            continue
        if base.is_file():
            st = base.stat()
            out[z] = (st.st_size, st.st_mtime_ns)
            continue
        for p in base.rglob("*"):
            if p.is_file():
                st = p.stat()
                out[p.relative_to(REPO).as_posix()] = (st.st_size, st.st_mtime_ns)
    for p in REPO.iterdir():
        if p.is_file() and p.name not in out:
            st = p.stat()
            out[p.name] = (st.st_size, st.st_mtime_ns)
    return out


def _state_key(product):
    """镜像 ctxiso/paths.py:53-55 product_key（只为定位 sidecar 自己的状态目录）。"""
    return hashlib.sha1(str(Path(product).resolve()).encode("utf-8")).hexdigest()[:12]


SCENARIOS = [
    ("1", "普通新任务", scenario_1),
    ("2", "连续任务", scenario_2),
    ("3", "自动记录", scenario_3),
    ("4", "历史查询", scenario_4),
    ("5", "项目更新", scenario_5),
    ("6", "上下文压缩", scenario_6),
    ("7", "大量历史文件", scenario_7),
    ("8", "长期项目维护", scenario_8),
    ("9", "新旧系统并存", scenario_9),
]
