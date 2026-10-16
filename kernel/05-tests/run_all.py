#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次跑完 6 个上下文隔离场景。

    python run_all.py                 # 跑全部，有红项退 3
    python run_all.py --only 3,7      # 只跑指定场景
    python run_all.py --keep-temp     # 保留 05-tests/TEMP/ 与侧车状态目录（默认跑完删）

退出码：0 = 全绿；3 = 有红项；2 = 环境没准备好（没找到被测对象/账本）。

写盘纪律：
  · 本文件只写 05-tests/RESULT.md 和 05-tests/TEMP/。
  · 假产品只在 05-tests/TEMP/ 里建。
  · 本仓 <hubcore>/ 的 02-hubcore/（中枢本体 + 运行核）、03-bundle/、04-console/、
    06-verify/、ctxiso/ 一律只读；跑前跑后逐文件比对指纹。
  · 被测产品是**本仓自己**（原来写死上一版中枢那套路径，那会让「删掉旧中枢就测不了」）。
  · 唯一会在 05-tests/ 之外留下东西的，是被测代码 ctxiso 自己的状态目录
    <hubcore>/state/<产品key>/ —— 那是它的设计位置，删不掉，
    所以本脚本跑完会把「本轮建的假产品」那几格删掉，并在 RESULT.md 里列明。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_scenarios as T  # noqa: E402

AUTO_BEGIN = "<!-- BEGIN AUTO-RUN -->"
AUTO_END = "<!-- END AUTO-RUN -->"


def rmtree_force(path, tries=4):
    """Windows 上偶发文件被占用；删不掉就重试，删不掉只告警不当红。"""
    import time as _t
    for i in range(tries):
        if not path.exists():
            return True
        try:
            shutil.rmtree(path, ignore_errors=False)
            return True
        except OSError:
            _t.sleep(0.7 * (i + 1))
    shutil.rmtree(path, ignore_errors=True)
    return not path.exists()


def env_check():
    problems = []
    if not (T.CTXISO_ROOT / "ctxiso" / "cli.py").is_file():
        problems.append("找不到被测对象 %s" % (T.CTXISO_ROOT / "ctxiso" / "cli.py"))
    if not (T.CTXISO_ROOT / "ctxiso" / "config.json").is_file():
        problems.append("找不到 ctxiso/config.json")
    if not (T.HUB_TOOLS / "state.py").is_file():
        problems.append("场景 3 需要真 state.py：%s" % (T.HUB_TOOLS / "state.py"))
    p = subprocess.run([sys.executable, "-m", "ctxiso", "--help"],
                       cwd=str(T.CTXISO_ROOT), env=T._env(),
                       capture_output=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        problems.append("python -m ctxiso 起不来：%s" % (p.stderr or "")[:200])
    return problems


def clean_state_for_fakes():
    """删掉本轮假产品在侧车状态目录里留下的格子（只按 TEMP 产品的 key 删）。"""
    removed = []
    if not T.STATE_DIR.is_dir():
        return removed
    for key in T.state_keys_used():
        d = T.STATE_DIR / key
        if d.is_dir():
            removed.append(key)
    return removed


def write_result_md(lines):
    path = T.TESTS / "RESULT.md"
    old = path.read_text(encoding="utf-8") if path.is_file() else ""
    if AUTO_BEGIN in old and AUTO_END in old:
        head = old.split(AUTO_BEGIN)[0]
        tail = old.split(AUTO_END, 1)[1]
    else:
        head = ""
        tail = ""
    body = AUTO_BEGIN + "\n" + "\n".join(lines) + "\n" + AUTO_END + "\n"
    path.write_text(head + body + tail, encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description="上下文隔离 6 场景")
    ap.add_argument("--only", default="", help="只跑这些场景号，逗号分隔，如 3,7")
    ap.add_argument("--keep-temp", action="store_true", help="跑完保留 TEMP/")
    ap.add_argument("--keep-state", action="store_true", help="跑完保留侧车里假产品的状态目录")
    ap.add_argument("--no-write-result", action="store_true", help="不刷新 RESULT.md")
    args = ap.parse_args(argv)

    only = {x.strip() for x in args.only.split(",") if x.strip()}

    print("=" * 78)
    print("上下文隔离场景测试")
    print("被测对象：%s" % (T.CTXISO_ROOT / "ctxiso"))
    print("被测产品：%s" % T.REPO)
    print("假产品根：%s" % T.TEMP)
    print("=" * 78)

    problems = env_check()
    if problems:
        for x in problems:
            print("[环境] %s" % x)
        return 2

    # 自愈：上一轮如果在改名 02-hubcore 的中途被掐断，先把它改回来再开跑
    hidden = T.CTXISO_ROOT / "02-hubcore.RENAMED-BY-05tests"
    src = T.CTXISO_ROOT / "02-hubcore"
    if hidden.is_dir() and not src.is_dir():
        import os as _os
        for _i in range(6):
            try:
                _os.rename(str(hidden), str(src))
                break
            except OSError:
                time.sleep(0.3)
        print("[自愈] 已把上一轮遗留的 02-hubcore.RENAMED-BY-05tests 改回原位：%s"
              % src.is_dir())

    if T.TEMP.exists() and not rmtree_force(T.TEMP):
        print("[警告] 上一次留下的 TEMP/ 删不掉（文件被占用），先跳过，跑完再清")
        T.TEMP.mkdir(parents=True, exist_ok=True)

    fp_before = T.fingerprint(T.HARD_ZONES + T.PROJ_ZONES + T.SOFT_ZONES)
    print("[保护区] 跑前取指纹：%d 个文件" % len(fp_before))

    # ★ 2026-10-16：场景 9.2 要验的是「**本轮测试自己**有没有把仓库弄脏」，
    #   而它原来拿的是「跑完后的绝对 git status」—— 于是**任何人的未提交改动**都会让它红
    #   （实测：统筹当时有 130+ 处未提交改动 → 9.2 必然假红）。这里跑前存一份基线，
    #   9.2 只对比「新增」，别人的改动不再误伤。
    try:
        import subprocess as _sp
        gb = _sp.run(["git", "status", "--porcelain"], cwd=str(T.REPO),
                     capture_output=True, encoding="utf-8", errors="replace", timeout=120)
        T.TEMP.mkdir(parents=True, exist_ok=True)
        (T.TEMP / ".git-status-before").write_text(gb.stdout or "", encoding="utf-8")
        print("[基线] 跑前 git status：%d 行（别人的未提交改动，9.2 不计入）"
              % len([x for x in (gb.stdout or "").splitlines() if x.strip()]))
    except Exception as exc:      # noqa: BLE001
        print("[警告] 存 git 基线失败（9.2 会降级为只报不判红）：%r" % (exc,))

    results = []
    t0 = time.perf_counter()
    for sid, title, fn in T.SCENARIOS:
        if only and sid not in only:
            continue
        print("\n" + "-" * 78)
        print("场景 %s  %s" % (sid, title))
        print("-" * 78)
        sc = T.Scenario(sid, title)
        try:
            fn_fill = fn()
            sc = fn_fill
        except Exception as exc:  # noqa: BLE001 —— 场景挂了要报出来，不能吞
            import traceback
            sc.fail(exc)
            sc.notes.append(traceback.format_exc(limit=6))
        for c in sc.checks:
            print(c.line())
        if sc.error:
            print("  [ERROR] %s" % sc.error)
        for n in sc.notes:
            print("  [注] %s" % n)
        n_ok = sum(1 for c in sc.checks if c.ok)
        print("  —— %d/%d 条断言通过，用时 %s ms" % (n_ok, len(sc.checks), sc.ms))
        results.append(sc)
    total_ms = round((time.perf_counter() - t0) * 1000, 1)

    # ---------------------------------------------------------- 保护区比对（三层）
    fp_after = T.fingerprint(T.HARD_ZONES + T.PROJ_ZONES + T.SOFT_ZONES)
    rels = lambda zs: {T.REPO.joinpath(z).relative_to(T.REPO).as_posix() for z in zs}
    hard_set, proj_set, soft_set = rels(T.HARD_ZONES), rels(T.PROJ_ZONES), rels(T.SOFT_ZONES)

    def zone_of(rel):
        for z in hard_set:
            if rel == z or rel.startswith(z + "/"):
                return "hard"
        for z in proj_set:
            if rel == z or rel.startswith(z + "/"):
                return "proj"
        for z in soft_set:
            if rel == z or rel.startswith(z + "/"):
                return "soft"
        return "hard" if "/" not in rel else "proj"      # 仓根文件算硬保护区

    changed = {"hard": [], "proj": [], "soft": []}
    added = {"hard": [], "proj": [], "soft": []}
    for rel, meta in fp_after.items():
        z = zone_of(rel)
        if rel not in fp_before:
            added[z].append(rel)
        elif fp_before[rel] != meta:
            changed[z].append(rel)
    # 消失的也要按层分——别把 T2 删掉的文件算到层 1 头上
    removed = {"hard": [], "proj": [], "soft": []}
    for rel in fp_before:
        if rel not in fp_after:
            removed[zone_of(rel)].append(rel)
    changed_hard, added_hard = changed["hard"], added["hard"]
    removed_hard = removed["hard"]

    print("\n" + "=" * 78)
    print("保护区指纹比对（跑前 %d 文件 → 跑后 %d 文件）" % (len(fp_before), len(fp_after)))
    print("  [层1 硬保护区·判红] hub/ .hub/ features/ work/v0.1.0/ + 仓根文件")
    print("    被改 %d · 新增 %d · 消失 %d"
          % (len(changed_hard), len(added_hard), len(removed_hard)))
    for x in (changed_hard + added_hard)[:20]:
        print("      !", x)
    for x in removed_hard[:20]:
        print("      -", x)
    print("  [层2 本项目内·只报不判红] 02-hubcore/ ctxiso/ 00-ANALYSIS/ 01-design/")
    print("    变化 %d / 消失 %d（E/F 分区，文档子代理与统筹本人随时在改）"
          % (len(changed["proj"]), len(removed["proj"])))
    for x in (changed["proj"] + removed["proj"])[:10]:
        print("      ~", x)
    print("  [层3 别人分区·只报不判红] 03-bundle/ 04-console/ 03-tests/")
    print("    变化 %d / 消失 %d（T1/T2 同时在开工）"
          % (len(changed["soft"]), len(removed["soft"])))
    for x in (changed["soft"] + removed["soft"])[:10]:
        print("      ~", x)
    print("=" * 78)

    hermetic = not changed_hard and not added_hard and not removed_hard
    print("[判定] 真仓库（层1）零改动：%s" % ("是" if hermetic else "否 ← 有问题，见上"))

    # ---------------------------------------------------------- 清理
    removed_state = []
    if not args.keep_state:
        for name in clean_state_for_fakes():
            d = T.STATE_DIR / name
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)
                removed_state.append(name)
    if not args.keep_temp and T.TEMP.exists():
        log = T.TEMP / "_cli-stderr.log"
        if log.is_file():
            shutil.copyfile(log, T.TESTS / "LAST-STDERR.log")
            print("[LOG] ctxiso 崩过的 stderr 已存 %s" % (T.TESTS / "LAST-STDERR.log"))
        shutil.rmtree(T.TEMP, ignore_errors=True)
        if T.TEMP.exists():
            print("[警告] TEMP/ 删不干净（文件被占用），下次跑会重试")

    red = [s for s in results if not s.ok] or ([] if hermetic else [None])
    verdict = 0 if not red else 3

    n_checks = sum(len(s.checks) for s in results)
    n_pass = sum(1 for s in results for c in s.checks if c.ok)
    n_red_assert = n_checks - n_pass
    n_red_scene = sum(1 for s in results if not s.ok)
    print("\n总结：%d 个场景，%d 条断言，%d 通过，%d 红；其中 %d 个场景有红；用时 %s ms"
          % (len(results), n_checks, n_pass, n_red_assert, n_red_scene, total_ms))
    print("退出码：%d（0=全绿，3=有红项）" % verdict)

    # ---------------------------------------------------------- 刷新 RESULT.md 自动段
    if not args.no_write_result:
        lines = []
        lines.append("")
        lines.append("> 本段由 `python run_all.py` 自动生成，数字全部来自实跑，不要手改。")
        lines.append("> 生成时间：%s　·　Python %s" % (
            time.strftime("%Y-%m-%d %H:%M:%S"), sys.version.split()[0]))
        lines.append("")
        lines.append("## 一句话总判定")
        lines.append("")
        lines.append("| 项 | 结果 |")
        lines.append("|---|---|")
        lines.append("| 场景数 | %d（全套 1–9） |" % len(results))
        lines.append("| 断言 | %d 条，%d 通过，%d 红 |" % (n_checks, n_pass, n_checks - n_pass))
        lines.append("| 有红的场景 | %s |" % (", ".join(
            "场景 %s" % s.sid for s in results if not s.ok) or "无"))
        lines.append("| 真仓库零改动（层 1） | %s |" % ("是" if hermetic else "否"))
        lines.append("| 退出码 | %d |" % verdict)
        lines.append("| 总用时 | %s ms |" % total_ms)
        lines.append("")
        for sc in results:
            lines.append("## 场景 %s　%s" % (sc.sid, sc.title))
            lines.append("")
            lines.append("用时 %s ms，%d/%d 条断言通过。%s"
                         % (sc.ms, sum(1 for c in sc.checks if c.ok), len(sc.checks),
                            ("**场景失败：%s**" % sc.error) if sc.error else ""))
            lines.append("")
            lines.append("| 判定 | 断言 | 实际数字 | 实际输出 |")
            lines.append("|---|---|---|---|")
            for c in sc.checks:
                nums = "；".join("%s=`%s`" % (k, v) for k, v in c.numbers.items()) or "—"
                det = c.detail.replace("|", "\\|").replace("\n", " ")
                lines.append("| %s | %s | %s | %s |"
                             % ("通过" if c.ok else "**红**", c.name, nums,
                                det or "—"))
            if sc.notes:
                lines.append("")
                for n in sc.notes:
                    lines.append("> %s" % n)
            lines.append("")
        lines.append("## 保护区指纹比对（三层）")
        lines.append("")
        lines.append("| 层 | 范围 | 被改 | 新增 | 消失 | 判红 |")
        lines.append("|---|---|---|---|---|---|")
        lines.append("| 1 硬保护区 | 中枢本体（`02-hubcore/` 的规则与运行核）、仓根文件 "
                     "| %d | %d | %d | **是** |"
                     % (len(changed["hard"]), len(added["hard"]), len(removed["hard"])))
        lines.append("| 2 本项目内 | `ctxiso/`、`00-ANALYSIS/`、`01-design/` "
                     "| %d | %d | %d | 否（E/F 分区，别人在改） |"
                     % (len(changed["proj"]), len(added["proj"]), len(removed["proj"])))
        lines.append("| 3 别人分区 | `03-bundle/`、`04-console/`、`03-tests/`、`06-verify/` "
                     "| %d | %d | %d | 否（T1/T2 同时开工） |"
                     % (len(changed["soft"]), len(added["soft"]), len(removed["soft"])))
        lines.append("")
        lines.append("跑前取指纹 %d 个文件，跑后 %d 个。"
                     % (len(fp_before), len(fp_after)))
        for label, bucket in (("层2 本项目内", "proj"), ("层3 别人分区", "soft")):
            touched = changed[bucket] + added[bucket] + removed[bucket]
            if touched:
                lines.append("")
                lines.append("%s 本轮观察到的变化（不是本测试夹具写的）：" % label)
                for x in touched[:20]:
                    lines.append("- `%s`" % x)
        lines.append("")
        lines.append("## 跑完删掉了什么")
        lines.append("")
        lines.append("- `05-tests/TEMP/` 整个目录：%s"
                     % ("保留（--keep-temp）" if args.keep_temp else "已删"))
        lines.append("- 侧车状态目录里本轮假产品的格子 `<hubcore>/state/<key>/`：%s"
                     % (", ".join(removed_state) if removed_state else
                        ("无" if not args.keep_state else "保留（--keep-state）")))
        lines.append("")
        try:
            lines.append("跑完 `<hubcore>/state/` 现有内容：`%s`"
                         % ", ".join(sorted(x.name for x in T.STATE_DIR.iterdir()
                                             if x.is_dir())))
        except OSError:
            pass
        lines.append("")
        write_result_md(lines)
        print("[RESULT] 已刷新 %s 的自动段" % (T.TESTS / "RESULT.md"))

    return verdict


if __name__ == "__main__":
    sys.exit(main())
