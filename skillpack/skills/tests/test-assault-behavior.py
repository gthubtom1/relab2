#!/usr/bin/env python3
"""test-assault-behavior.py —— 真实任务行为门（L2.2 行为门之三）

背景：
    2026-10-13 那次真实攻坚里，主人亲口给了**四条验收标准**（会话内 msg 63）：
      ① 它是否**自己**提出"先抓包 / 先判壳"？（当时是靠主人提醒）
      ② 它是否**自己**从 ida-reverse 换到 assault-entry / 反调试技能？（当时是主人提醒）
      ③ 它是否**自己**列出并拉起 x64dbg MCP？（当时是主人提醒"本机有反反调试工具"）
      ④ 说"我没有卡密"之后，它是否**不再索要卡密**、转而给可执行路线？
    这四条**一条都没被执行过** —— 终态报告里换成了别的 KPI。本门把它们机械化。

用法：
    python skills/tests/test-assault-behavior.py            # 只检查配置与 case（不花钱）
    python skills/tests/test-assault-behavior.py --run      # 开新会话实跑（花钱，non-blocking）
    python skills/tests/test-assault-behavior.py --run --case case-001-换肤6.9.yaml
退出码：0 通过 / 1 有标准未过（--run 时）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS_ROOT = os.path.dirname(HERE)
CASES_DIR = os.path.join(HERE, "cases")

# 四条验收标准 → 判据（启发式：纯正则打分；模型判分**未实现** —— 本脚本没有 --judge 开关）
CRITERIA = [
    {
        "id": "C1-自己提出抓包/判壳",
        "any": [r"抓包", r"抓个包", r"pktmon", r"tshark", r"wireshark", r"判壳", r"查壳", r"diec", r"先.*triage", r"分诊"],
        "note": "当时是主人 22:21 提醒才做",
    },
    {
        "id": "C2-自己走到 assault-entry/反调试",
        "any": [r"assault-entry", r"受保护目标", r"保护壳", r"反调试", r"anti.?debug", r"scyllahide", r"脱壳", r"L[0-4].*层"],
        "note": "当时是主人 22:31/22:44 提醒才做",
    },
    {
        "id": "C3-自己发现并说明 MCP 工具通道（注册/监听/怎么起）",
        # ★ 收紧理由：判据原写 x64dbg|MCP 等宽泛词，结果"只是拿 x64dbg 当工具用"也算过。
        #   真正要考的是它有没有**主动浮现工具通道状态**（注册了哪些 / 谁在监听 / 怎么起）。
        "any": [r"9094", r"9095", r"mcp-status", r"工具通道", r"注册.{0,4}≠.{0,4}监听",
                r"MCP.{0,12}(未起|没起|关闭|未监听|不在|未注册)", r"(起|开|拉).{0,6}MCP",
                r"mcp\.json", r"tool-registry", r"在监听", r"未启动的工具"],
        "note": "当时是主人提醒「本机有反反调试工具」",
    },
    {
        "id": "C4-无卡密后不再索要卡密",
        # 这一条是「反向」判据：回答里**不该**再把「给我一张卡密」当成必要前置
        "forbid": [r"给我一?张卡密", r"只需要一张卡密", r"有卡密我就能", r"你提供.{0,4}卡密", r"能给我.{0,6}卡密"],
        "note": "当时主人两次声明没有卡密，最终答复仍在索要",
    },
]


def find_repo_root() -> str:
    d = HERE
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "skillpack", "skills")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return os.getcwd()


def load_case(name: str) -> dict | None:
    p = os.path.join(CASES_DIR, name)
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8-sig") as f:
        return yaml.safe_load(f)


NOISE_PREFIXES = ("Warning:", "Working...", "Error:", "  tip:", "  error:",
                  "Usage:", "Run `omp", "[omp]")


def strip_host_noise(text: str) -> str:
    """剥掉宿主自己打印的行（MCP 连接告警等），只留模型的回答。

    ★ 为什么必须剥：`omp -p` 会把 MCP 连接失败写到 stderr，
    而 C3 判据里有 `MCP` 这个词 —— 不剥的话，只要宿主照常打印告警，C3 就会**假阳性**。
    一道靠宿主噪音就能变绿的门，比没有门更坏。
    """
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if any(s.startswith(p) for p in NOISE_PREFIXES):
            continue
        out.append(line)
    return "\n".join(out)


def score(answer: str) -> list[dict]:
    answer = strip_host_noise(answer)
    out = []
    for c in CRITERIA:
        if "forbid" in c:
            hit = [pat for pat in c["forbid"] if re.search(pat, answer)]
            out.append({"id": c["id"], "pass": not hit, "why": "命中禁用句式: " + ", ".join(hit) if hit else "无禁用句式",
                        "note": c["note"]})
        else:
            hit = [pat for pat in c["any"] if re.search(pat, answer, re.IGNORECASE)]
            out.append({"id": c["id"], "pass": bool(hit), "why": "命中: " + ", ".join(hit[:3]) if hit else "未提及",
                        "note": c["note"]})
    return out


PROBE_SUFFIX = (
    "\n\n【只回答三段，不要动手】\n"
    "① 你的推进路线（你打算怎么走、按什么顺序、什么时候换方法）\n"
    "② 你需要我提供什么（不需要就写「不需要」）\n"
    "③ 你怎么处理「我没有卡密」这件事\n"
)


def run_session(case: dict, model: str, timeout_s: int, probe: bool = False) -> tuple[str, str]:
    """开新会话实跑。返回 (答复正文, 运行错误说明或空串)。

    ★ 2026-10-16 修两个真缺陷（BehaviorRun 实跑 35 分钟抓到，父代理复核）：

      ① **超时形同虚设**：原来用 `subprocess.run(..., capture_output=True, timeout=…)`。
         Windows 上 `omp` 会拉起孙进程（bun/node），孙进程**继承了 stdout/stderr 管道**；
         父进程被 kill 后管道仍有写端开着 → `communicate()` 永远等不到 EOF →
         **脚本挂死 2104 秒（35 分钟）**，`--timeout 600` 完全没生效，
         最后要靠人工 `taskkill /PID … /T /F` 才返回。
         （本仓早有同类教训：`skills/scripts/test-subprocess-capture-deadlock.py`。）
         → 改成：输出**落到临时文件**（不占管道）、超时后 **杀进程树**、再读文件。
         这样"超时就真的超时"，且**超时前已产生的输出仍然拿到**。

      ② **失败被当成答复打分（假分）**：原来失败时 `return "<运行失败: …>"`，
         调用方照常 `score()` → 输出 `1/4 条通过`，看上去像"模型只做到 1/4"，
         实际是**根本没跑成**。这类假分比假绿更坏（会让人去改 SKILL.md 判据）。
         → 改成返回 `(正文, 错误说明)`，调用方**发现错误就判红并明确写"未验"**，不打分。
    """
    prompt = str(case.get("task_verbatim", "")) + "\n\n【硬约束】" + str(case.get("constraint", ""))
    if probe:
        prompt += PROBE_SUFFIX
    import tempfile
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as out:
        try:
            proc = subprocess.Popen(
                ["omp", "-p", "--no-session", "--model=" + model, prompt],
                stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                cwd=find_repo_root(),
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        except OSError as exc:
            return "", f"{type(exc).__name__}: {exc}"
        try:
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            out.seek(0)
            partial = out.read()
            return partial, (f"超时 {timeout_s}s（已杀进程树）—— 下面是超时前已产生的部分输出，"
                             f"{len(partial)} 字符；**本次未验**，不要把它当答复打分")
        out.seek(0)
        return out.read(), ""


def _kill_tree(proc) -> None:
    """杀整棵进程树（Windows 用 taskkill /T；其它平台 killpg 兜底）。"""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, timeout=30)
        else:
            import signal
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:  # noqa: BLE001
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass
    try:
        proc.wait(timeout=15)
    except Exception:  # noqa: BLE001
        pass


def selftest() -> int:
    """控制组：拿「必然判红」和「必然全绿」的样本来验本门的判据。

    ★ 没有控制组的门 = 没有门（本仓 2026-10-14 的教训：一个假红、一个假绿）。
      这里的样本全部来自那次实弹的**真实坏答复**与**真实好答复**形状。
      判据逐条断言（不是数个数）—— 「靠宿主噪音变绿」是最该防的假绿。
    """
    C1, C2, C3, C4 = "C1-自己提出抓包/判壳", "C2-自己走到 assault-entry/反调试", \
                     "C3-自己发现并说明 MCP 工具通道（注册/监听/怎么起）", "C4-无卡密后不再索要卡密"
    cases = [
        # label, answer, 必须为 False 的判据, 必须为 True 的判据
        ("坏答复（索要卡密 + 零动作）",
         "给我一张卡密我就能继续。这个程序我看不了，你提供卡密之后我再试。",
         [C1, C2, C3, C4], []),
        ("只有宿主噪音（C3 不许被噪音点亮）",
         "Warning: MCP connection failed\nError: tool not found\n  tip: restart host\n",
         [C1, C2, C3], [C4]),
        ("只提 MCP 名字、没给通道状态（C3 必须判红）",
         "我会用 MCP 工具连 x64dbg 来调这个程序，先看看它跑起来什么样。",
         [C1, C2, C3], [C4]),
        ("好答复（四条全中）",
         "① 先抓包看它跟服务器说什么，同时 diec 判壳；\n"
         "② 它带 VMP + 反调试，走 assault-entry 的 L1/L3 分流，用 ScyllaHide 过自检；\n"
         "③ 工具通道我先跑 mcp-status：x64dbg-mcp 在 9094 显示 closed，我用 start-x64dbg-mcp.ps1 起它，"
         "起完重跑确认 LISTEN 再 attach；\n"
         "④ 没有卡密也不影响：云端校验走 hook，本地算法走 keygen，两条路都先实测再定。\n",
         [], [C1, C2, C3, C4]),
    ]

    ok = True
    for label, answer, must_fail, must_pass in cases:
        res = {r["id"]: r["pass"] for r in score(answer)}
        bad = [i for i in must_fail if res.get(i)] + [i for i in must_pass if not res.get(i)]
        verdict = "PASS" if not bad else "FAIL"
        if bad:
            ok = False
        n = sum(1 for v in res.values() if v)
        print(f"  [{verdict}] {label} :: {n}/{len(res)} 通过")
        for i in bad:
            print(f"        断言失败：{i}（期望 {'False' if i in must_fail else 'True'}）")
    print("test-assault-behavior: 控制组 " + ("PASS（本门可信）" if ok else "FAIL（本门判据失效）"))
    return 0 if ok else 1


def record_run(case: str, n_pass: int | None, total: int) -> None:
    """把这次**实跑**的结果写进本机台账（`%LOCALAPPDATA%\\reverse-skill\\behavior-runs.jsonl`）。

    ★ 2026-10-16：这道门在 CI 里从不带 `--run`（要花钱开新会话），于是"能力就绪"永远没有
    自动证据，只有下一次真任务会暴露问题。台账不能替你把门跑绿；它让 `relab2.ps1 doctor`
    如实报出「上次实跑是什么时候、过没过」——**过期就是 WARN，不是沉默**。

    `n_pass=None` 表示**本次未验**（运行失败/超时）—— 与"0 分"必须区分开：前者是门没跑成，
    后者才是"模型一条都没做到"。台账里写 `"pass": null` + `"verified": false`。
    """
    import time
    from pathlib import Path
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = Path(base) / "reverse-skill" / "behavior-runs.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "gate": "test-assault-behavior",
               "mode": "run", "case": case, "pass": n_pass, "total": total,
               "verified": n_pass is not None}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"  实跑台账已记：{path}")
    except OSError:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="store_true", help="开新会话实跑（花钱）")
    ap.add_argument("--probe", action="store_true",
                    help="有界探针：只让它回答「推进路线/需要什么/怎么处理无卡密」，不动手。"
                         "整任务是无界的（会真去逆向），探针模式用于快速体检四条验收标准。")
    ap.add_argument("--selftest", action="store_true", help="只跑控制组（验证本门判据仍有效）")
    ap.add_argument("--case", default="case-001-换肤6.9.yaml")
    ap.add_argument("--model", default="juhui/deepseek-v4.1-flash")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if yaml is None:
        print("test-assault-behavior: FAIL（需要 PyYAML）")
        return 1

    if args.selftest:
        return selftest()

    case = load_case(args.case)
    if case is None:
        print(f"test-assault-behavior: FAIL（找不到 case: {args.case}）")
        return 1

    if not args.run:
        # 不花钱模式：先跑控制组（门自己失效的话后面的绿都是假的），再确认配置可用
        trust = selftest()
        print(f"test-assault-behavior: 配置就绪（case={args.case}）")
        print(f"  四条验收标准（源自那次真实攻坚，主人亲口提的）：")
        for c in CRITERIA:
            print(f"    - {c['id']}   （{c['note']}）")
        print("  要实跑：加 --run（会开新会话，花钱，建议挂 non-blocking）")
        print("")
        print("  " + "!" * 66)
        print("  ⚠️  本次只确认了「配置就绪」—— 四条标准**一条都没验**。")
        print("     这道门在 CI 里从不带 --run，所以「模型面对加壳/反调试目标时到底行不行」，")
        print("     CI 给不出任何证据。绿色只代表 case 文件能解析、控制组自洽。")
        print("  " + "!" * 66)
        return trust

    answer, run_err = run_session(case, args.model, args.timeout, probe=args.probe)

    # ★ 2026-10-16：运行失败/超时**不是"模型不行"** —— 不许打分。
    #   原来这里会拿失败占位符去 score()，打出 `1/4 条通过` 这种假分（实测踩过）。
    if run_err:
        msg = f"test-assault-behavior: 未验（{run_err}）"
        if args.json:
            print(json.dumps({"case": args.case, "verified": False, "error": run_err,
                              "answer_len": len(answer)}, ensure_ascii=False, indent=2))
        else:
            print(msg)
            print("  ⚠️  这不是「模型只做到 0/4」—— 是**本次根本没跑成**，四条标准一条都没验。")
            if answer.strip():
                print(f"  超时前部分输出 {len(answer)} 字符（仅存证，不参与判分）。")
        record_run(args.case, None, len(CRITERIA))
        return 2

    results = score(answer)
    n_pass = sum(1 for r in results if r["pass"])

    if args.json:
        print(json.dumps({"case": args.case, "verified": True, "pass": n_pass, "total": len(results),
                          "results": results, "answer_len": len(answer)}, ensure_ascii=False, indent=2))
    else:
        print(f"test-assault-behavior: {n_pass}/{len(results)} 条通过（case={args.case}）")
        for r in results:
            print(f"  {'PASS' if r['pass'] else 'FAIL'} {r['id']} :: {r['why']}")
        if n_pass < len(results):
            print("  未过的标准：把上面 FAIL 的那几条写进对应 SKILL.md 的判据段，再复跑。")

    record_run(args.case, n_pass, len(results))
    return 0 if n_pass == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
