#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""看门狗：证明这套开发还在推进，并且在中断后能用一次点击接上。

说清它能做什么、不能做什么（重要）：
  能 —— 持续心跳、量出"这一轮到底推进了多少"、自动跑可脚本化的验证
        （索引 / 精简器校验 / 旧系统指纹）、中断后生成一条可直接粘贴的接续口令。
  不能 —— 它没法唤醒一个已经不存在的会话进程。它不是"AI 复活器"，
        它是"证据 + 恢复入口"：把恢复从"重讲一遍背景"压缩成"跑一条命令"。

用法：
    python watchdog.py start          # 后台起心跳（默认 300s）
    python watchdog.py stop
    python watchdog.py status         # 看最近一次心跳与推进量
    python watchdog.py check          # 只跑一次验证，不循环
    python watchdog.py resume         # 打印/写出一段接续提示词
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

DEV = Path(__file__).resolve().parent
REPO = DEV.parents[1]
STATE = DEV / "state"
STATE.mkdir(parents=True, exist_ok=True)
BEAT = STATE / "watchdog.json"
LOG = STATE / "watchdog-log.jsonl"
PID = STATE / "watchdog.pid"

# 推进量口径：只数"新内容"，不数心跳自己
TRACKED = ["ctxiso", "02-hubcore", "03-bundle", "04-console", "05-tests",
           "00-ANALYSIS", "01-design"]
SKIP_DIRS = {"__pycache__", "state", "dist", ".git"}

# 子代理的分区。它盯的不只是"代码好不好"，还有"人还在不在动"。
# 每个分区归一个代理；某个分区长时间没动，就是那个代理卡住了。
AGENTS = {
    "03-bundle": "T1 打包器/一键卸载",
    "04-console": "T2 极简控制台",
    "05-tests": "T4 九个必测场景",
    "00-ANALYSIS": "T5 分析文档",
    "01-design": "T5 分析文档",
    "ctxiso": "统筹本人（ctxiso 侧车）",
    "02-hubcore": "统筹本人（提示词/构建）",
}
# 多久没动算"卡住"（秒）
IDLE_ALERT = 900


def _walk() -> dict:
    out = {}
    for rel in TRACKED:
        base = DEV / rel
        if not base.exists():
            continue
        n_files = n_bytes = 0
        newest = 0.0
        for p in base.rglob("*"):
            if any(s in SKIP_DIRS for s in p.parts):
                continue
            if p.is_file():
                try:
                    st = p.stat()
                except OSError:
                    continue
                n_files += 1
                n_bytes += st.st_size
                newest = max(newest, st.st_mtime)
        if n_files:
            out[rel] = {"files": n_files, "bytes": n_bytes,
                        "newest_mtime": round(newest, 3)}
    return out


def _run(name: str, argv: list[str], cwd: Path) -> dict:
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(argv, cwd=str(cwd), capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=300)
        tail = (proc.stdout or "") + (proc.stderr or "")
        # 子代理正在改的文件可能是半成品（语法错误）。那不是产品回归，
        # 是"有人在写"。不区分的话，心跳会天天报红，噪音会盖掉真信号。
        torn = any(m in tail for m in (
            "IndentationError", "SyntaxError", "Traceback (most recent call last)",
            "unexpected indent"))
        return {"name": name, "ok": proc.returncode == 0,
                "rc": proc.returncode, "ms": int((time.perf_counter() - t0) * 1000),
                "torn": torn, "tail": tail.strip()[-600:]}
    except subprocess.TimeoutExpired:
        return {"name": name, "ok": False, "rc": -1, "ms": 300000,
                "torn": False, "tail": "超时（>300s）"}
    except OSError as exc:
        return {"name": name, "ok": False, "rc": -2, "ms": 0,
                "torn": False, "tail": str(exc)}


def verify() -> list[dict]:
    """只跑可脚本化、且绝对只读的验证。绝不写产品目录。"""
    checks = []
    py = sys.executable
    if (DEV / "ctxiso").is_dir() and (REPO / ".hub" / "ledger.jsonl").is_file():
        checks.append(_run("ctxiso-index", [py, "-m", "ctxiso", "index",
                                            "--product", str(REPO)], DEV))
        checks.append(_run("ctxiso-guard", [py, "-m", "ctxiso", "guard", "check",
                                            "--product", str(REPO)], DEV))
    builder = DEV / "02-hubcore" / "build_hubcore.py"
    if builder.is_file() and (DEV / "02-hubcore" / "MANIFEST.json").is_file():
        checks.append(_run("hubcore-check", [py, str(builder),
                                             "--product", str(REPO), "--check"],
                           DEV / "02-hubcore"))
    # 改源码 ≠ 改产物。产物是旧的，源码树的测试照样全绿——这条专门拦这个。
    sync = DEV / "02-hubcore" / "check_dist_sync.py"
    if sync.is_file() and (DEV / "03-bundle" / "dist" / "hubcore").is_dir():
        checks.append(_run("dist-sync", [py, str(sync)], DEV / "02-hubcore"))
    tests = DEV / "05-tests" / "run_all.py"
    if tests.is_file():
        checks.append(_run("scenarios", [py, str(tests)], DEV / "05-tests"))
    # 卡片 / 安装器 / 卸载器的**全部**验收（验收 1–9）住在 04-console/selftest.py。
    # 它以前不在这个列表里 —— 也就是说：改一张卡片，跑到的卡片断言数是零，
    # 唯一能防住宿主入口文件被损坏的那条不变量从没被自动跑过（2026-10-09 审计发现）。
    selftest = DEV / "04-console" / "selftest.py"
    if selftest.is_file():
        checks.append(_run("console-selftest", [py, "-B", str(selftest)],
                           DEV / "04-console"))
    return checks


def _delta(prev: dict | None, cur: dict) -> dict:
    # 两条返回路径的键必须一致，否则 status() 读 'since' 会 KeyError。
    if not prev:
        return {"new_files": sum(v["files"] for v in cur.values()),
                "new_bytes": sum(v["bytes"] for v in cur.values()),
                "since": "首次", "since_seconds": None}
    nf = nb = 0
    for rel, v in cur.items():
        o = prev.get(rel) or {"files": 0, "bytes": 0}
        nf += max(0, v["files"] - o["files"])
        nb += max(0, v["bytes"] - o["bytes"])
    secs = int(time.time() - prev.get("at_epoch", time.time()))
    return {"new_files": nf, "new_bytes": nb,
            "since": f"{secs // 60} 分钟内", "since_seconds": secs}


def _agent_liveness() -> list[dict]:
    """每个分区最后一次动是什么时候。用来回答"子代理还在不在干活"。"""
    now = time.time()
    out = []
    for rel, who in AGENTS.items():
        base = DEV / rel
        if not base.exists():
            out.append({"zone": rel, "who": who, "state": "还没开工"})
            continue
        newest, nfiles = 0.0, 0
        for p in base.rglob("*"):
            if any(s in SKIP_DIRS for s in p.parts):
                continue
            if p.is_file():
                try:
                    nfiles += 1
                    newest = max(newest, p.stat().st_mtime)
                except OSError:
                    pass
        if not nfiles:
            out.append({"zone": rel, "who": who, "state": "空目录"})
            continue
        idle = int(now - newest)
        out.append({
            "zone": rel, "who": who, "files": nfiles,
            "idle_seconds": idle, "idle_minutes": round(idle / 60, 1),
            "state": ("正在动" if idle < 300 else
                      ("久没动，可能卡住" if idle >= IDLE_ALERT else "静置中")),
            "alert": idle >= IDLE_ALERT,
        })
    return out


def beat() -> dict:
    prior = None
    if BEAT.is_file():
        try:
            prior = json.loads(BEAT.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            prior = None
    cur = _walk()
    d = _delta(prior, cur)
    checks = verify()
    # 单次红项多半是并发撞锁或文件正在被重建，不该立刻当成警报。
    # 连续两轮红才算真问题——这样心跳不会因为一次偶发就喊狼来了。
    torn = [c["name"] for c in checks if not c["ok"] and c.get("torn")]
    reds = [c["name"] for c in checks if not c["ok"] and not c.get("torn")]
    live = _agent_liveness()
    stuck = [x for x in live if x.get("alert")]
    streak = 0
    if prior and prior.get("failing"):
        streak = int(prior.get("red_streak", 0)) + 1 if reds else 0
    elif reds:
        streak = 1
    if not reds:
        streak = 0
    rec = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "at_epoch": time.time(),
        "progress": d,
        "totals": {k: v for k, v in cur.items()},
        "checks": [{"name": c["name"], "ok": c["ok"], "rc": c["rc"],
                    "ms": c["ms"], "torn": bool(c.get("torn"))} for c in checks],
        "all_checks_ok": all(c["ok"] for c in checks) if checks else None,
        "failing": reds,
        "torn": torn,
        "red_streak": streak,
        "verdict": ("全绿" if not reds else
                    (f"偶发红项（{', '.join(reds)}），先看是否与人工操作撞在一起"
                     if streak < 2 else
                     f"连续 {streak} 轮红项：{', '.join(reds)}。这是真问题，去看下面的输出。")),
        "idle_hint": ("没有新文件，看起来停住了" if d["new_files"] == 0
                      and prior is not None else "有推进"),
        "agents": live,
        "agents_stuck": stuck,
        "agent_verdict": (
            "全部分区都在动" if not stuck else
            "疑似卡住：" + "、".join(f"{x['zone']}（{x['who']}，{x['idle_minutes']} 分钟没动）"
                                  for x in stuck)
            + "。去看它是不是交了卷没接住，或卡在等一个回答。"),
    }
    BEAT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": rec["at"], "progress": d,
                             "ok": rec["all_checks_ok"]}, ensure_ascii=False) + "\n")
    return rec


def loop(interval: int) -> None:
    PID.write_text(str(os.getpid()), encoding="utf-8")
    while True:
        try:
            r = beat()
            print(f"[{r['at']}] 新增 {r['progress']['new_files']} 文件 / "
                  f"{r['progress']['new_bytes']} B；验证 "
                  f"{'全绿' if r['all_checks_ok'] else '有红项'}", flush=True)
            for x in r.get("agents", []):
                if x.get("alert"):
                    print(f"    !! {x['zone']}（{x['who']}）{x['idle_minutes']} 分钟没动，"
                          f"去看是不是卡住了", flush=True)
        except Exception as exc:                      # 看门狗自己不能成为故障点
            print(f"心跳异常：{exc}", flush=True)
        time.sleep(interval)


def stop() -> int:
    if not PID.is_file():
        print("没有在跑的心跳。")
        return 0
    pid = int(PID.read_text(encoding="ascii").strip())
    # Windows 上 os.kill(pid, 15) 会抛 [WinError 87] 参数错误。
    # 老实按平台来：Windows 用 taskkill，别的地方才用信号。
    try:
        if os.name == "nt":
            r = subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=20)
            if r.returncode != 0:
                print(f"taskkill 停不掉 {pid}：{(r.stdout or r.stderr or '').strip()}")
                return 2
        else:
            os.kill(pid, 15)
        print(f"已停掉心跳 {pid}。")
    except OSError as exc:
        print(f"停不掉 {pid}：{exc}")
        return 2
    PID.unlink(missing_ok=True)
    return 0


def status() -> int:
    if not BEAT.is_file():
        print("还没有心跳记录。先跑：python watchdog.py check")
        return 2
    r = json.loads(BEAT.read_text(encoding="utf-8"))
    # 读端要对旧格式的记录容错：心跳文件可能是改动前写的，不该一读就崩。
    prog = r.get("progress") or {}
    since = prog.get("since")
    if since is None:
        secs = prog.get("since_seconds")
        since = "首次" if secs is None else f"{int(secs) // 60} 分钟内"
    print(f"最近心跳：{r.get('at', '(无)')}")
    print(f"推进量：新增 {prog.get('new_files', 0)} 文件 / "
          f"{prog.get('new_bytes', 0)} B（{since}）")
    print(f"判断：{r.get('idle_hint', '(无)')}")
    print(f"结论：{r.get('verdict', '（旧记录，无结论字段）')}")
    print("\n—— 子代理状态 ——")
    for x in r.get("agents", []):
        mark = "!!" if x.get("alert") else (" >" if x.get("idle_seconds", 0) >= 300 else "  ")
        print(f" {mark} {x['zone']:<14} {x['who']:<22} {x.get('state','')}"
              + (f"  {x.get('idle_minutes')} 分钟没动" if "idle_minutes" in x else ""))
    if r.get("agent_verdict"):
        print(f" {r['agent_verdict']}")
    print("\n—— 闸门 ——")
    for c in r.get("checks", []):
        mark = "写" if c.get("torn") else ("绿" if c.get("ok") else "红")
        print(f"  [{mark}] {c.get('name')}  rc={c.get('rc')} {c.get('ms')}ms")
    if r.get("torn"):
        print(f"  （{'、'.join(r['torn'])} 正在被改，语法错不算回归）")
    if int(r.get("red_streak", 0) or 0) >= 2:
        print("\n连续红项详情（最近一次输出尾部）：")
        for c in verify():
            if not c["ok"] and not c.get("torn"):
                print(f"--- {c['name']} ---\n{c['tail']}")
    return 0


RESUME = """\
中枢上下文隔离重构 · 接续口令
================================
接着 `D:\\临时项目\\hub-dock\\work\\context-isolation\\TASKBOARD.md` 往下做。

1. 先跑 `python watchdog.py status` 看这一轮推进到哪、哪项验证是红的。
2. 读 `TASKBOARD.md` 的状态表和推进日志；已完成的不重做。
3. 规格真源是 `01-design/SPEC-自包含安装.md`。硬约束：
   不改旧中枢任何文件、装出来的东西零外部路径、可一键卸载、不联网、不碰 Skill。
4. 文件分区照 TASKBOARD 第 2 节，别越界写别人的目录。
5. 子代理没交卷的，重新派；交了卷的，自己复核到能签字再收。
"""


def resume() -> int:
    (STATE / "RESUME.txt").write_text(RESUME, encoding="utf-8")
    print(RESUME)
    print(f"（已存到 {STATE / 'RESUME.txt'}）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="中枢重构看门狗")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start"); s.add_argument("--interval", type=int, default=300)
    sub.add_parser("stop"); sub.add_parser("status")
    sub.add_parser("check"); sub.add_parser("resume")
    a = ap.parse_args()
    if a.cmd == "start":
        loop(a.interval)
    elif a.cmd == "stop":
        return stop()
    elif a.cmd == "status":
        return status()
    elif a.cmd == "check":
        r = beat()
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["all_checks_ok"] in (True, None) else 3
    else:
        return resume()
    return 0


if __name__ == "__main__":
    sys.exit(main())
