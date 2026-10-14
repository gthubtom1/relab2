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

# 四条验收标准 → 判据（启发式；可用 --judge 让模型判）
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


def run_session(case: dict, model: str, timeout_s: int, probe: bool = False) -> str:
    prompt = str(case.get("task_verbatim", "")) + "\n\n【硬约束】" + str(case.get("constraint", ""))
    if probe:
        prompt += PROBE_SUFFIX
    try:
        r = subprocess.run(["omp", "-p", "--no-session", "--model=" + model, prompt],
                           capture_output=True, text=True, timeout=timeout_s, cwd=find_repo_root())
        return (r.stdout or "") + "\n" + (r.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return f"<运行失败: {exc}>"


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
        return trust

    answer = run_session(case, args.model, args.timeout, probe=args.probe)
    results = score(answer)
    n_pass = sum(1 for r in results if r["pass"])

    if args.json:
        print(json.dumps({"case": args.case, "pass": n_pass, "total": len(results),
                          "results": results, "answer_len": len(answer)}, ensure_ascii=False, indent=2))
    else:
        print(f"test-assault-behavior: {n_pass}/{len(results)} 条通过（case={args.case}）")
        for r in results:
            print(f"  {'PASS' if r['pass'] else 'FAIL'} {r['id']} :: {r['why']}")
        if n_pass < len(results):
            print("  未过的标准：把上面 FAIL 的那几条写进对应 SKILL.md 的判据段，再复跑。")

    return 0 if n_pass == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
