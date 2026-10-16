#!/usr/bin/env python3
"""test-trigger-rate.py —— 技能触发率评估（L2.2 行为门之一）

背景：
    包里的门此前全是格式/一致性门。**没有任何门回答「这个技能在被需要时会不会被选中」**。
    Anthropic 官方要求：每个技能准备约 20 条 query（8–10 正 + 8–10 **近邻负例**），
    每条跑 3 次算触发率，正例 ≥0.5 通过、负例 <0.5 通过。
    负例必须**近邻**（共享关键词但需求不同）—— 弱负例（"今天天气怎么样"）测不出任何东西。

本脚本负责：
  1. **结构部分（默认，不需要模型调用）**：
     - 每个技能是否有 eval 集（`tests/evals/<skill>.yaml`）
     - 正例 ≥8、近邻负例 ≥8
     - 负例是否"近邻"（与目标技能或同域技能共享关键词 / 同域）
     - eval 集是否引用了真实存在的技能
  2. **实跑部分（`--run`，需要模型调用）**：
     - 对每条 query 调宿主让模型盲选技能，比对期望，算触发率
     - 输出每技能的正/负触发率；阈值可配

用法：
    python skills/tests/test-trigger-rate.py                 # 只做结构检查（可进 CI）
    python skills/tests/test-trigger-rate.py --run --limit 20  # 实跑（花钱，默认 non-blocking）
    python skills/tests/test-trigger-rate.py --run --only ida-reverse
退出码：0 通过 / 1 结构有问题（或实跑低于阈值）
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
EVALS_DIR = os.path.join(HERE, "evals")

MIN_POS = 8
MIN_NEG = 8
POS_THRESHOLD = 0.5   # 正例触发率下限
NEG_THRESHOLD = 0.5   # 负例触发率上限


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


def load_evals() -> tuple[dict[str, dict], list[str]]:
    out, errs = {}, []
    if not os.path.isdir(EVALS_DIR):
        return out, [f"evals 目录不存在: {EVALS_DIR}"]
    for fn in sorted(os.listdir(EVALS_DIR)):
        if not fn.endswith((".yaml", ".yml")):
            continue
        name = os.path.splitext(fn)[0]
        p = os.path.join(EVALS_DIR, fn)
        if yaml is None:
            errs.append(f"{fn} :: 需要 PyYAML")
            continue
        try:
            with open(p, encoding="utf-8-sig") as f:
                doc = yaml.safe_load(f)
        except Exception as exc:  # noqa: BLE001
            errs.append(f"{fn} :: YAML 解析失败: {exc}")
            continue
        if not isinstance(doc, dict):
            errs.append(f"{fn} :: 顶层不是映射")
            continue
        doc["_file"] = fn
        out[name] = doc
    return out, errs


def skill_exists(name: str) -> bool:
    return os.path.isfile(os.path.join(SKILLS_ROOT, name, "SKILL.md"))


def keywords_of(name: str) -> set[str]:
    """从 routing.json 里取该技能的关键词字面量（用于「近邻」判定）。"""
    p = os.path.join(SKILLS_ROOT, "config", "routing.json")
    try:
        with open(p, encoding="utf-8-sig") as f:
            d = json.load(f)
    except Exception:  # noqa: BLE001
        return set()
    out: set[str] = set()
    target = f"{name}/SKILL.md"
    for v in (d.get("routes") or {}).values():
        if v.get("skill") == target:
            for kw in v.get("keywords", []):
                raw = str(kw.get("must", ""))
                out |= {t for t in re.split(r"[|()\[\]\\?.{}+*?^$]+", raw) if len(t) >= 2}
    return out


def is_near_neighbor(neg_hint: str, target: str, all_skills: list[str]) -> bool:
    """近邻负例判定：与目标技能共享关键词，或命中同域任一技能的关键词。

    弱负例（"今天天气怎么样"）两者都不满足 → 判为无效负例。
    """
    low = neg_hint.lower()
    own = keywords_of(target)
    if any(k.lower() in low for k in own if len(k) >= 2):
        return True
    for other in all_skills:
        if other == target:
            continue
        for k in keywords_of(other):
            if len(k) >= 3 and k.lower() in low:
                return True
    return False


def structural_check(evals: dict[str, dict]) -> list[str]:
    errs: list[str] = []
    all_skills = [d for d in os.listdir(SKILLS_ROOT)
                  if os.path.isfile(os.path.join(SKILLS_ROOT, d, "SKILL.md"))]
    for name, doc in evals.items():
        fn = doc.get("_file", name)
        if not skill_exists(name):
            errs.append(f"{fn} :: 目标技能不存在: {name}")
        target = doc.get("skill", name)
        # ★ 2026-10-14 控制组补洞：原先只查文件名 stem，声明的 `skill:` 字段没人查 ——
        #   一个写着不存在技能的 eval 集会静默留在库里。两边都查。
        if not skill_exists(target):
            errs.append(f"{fn} :: 声明的 skill 不存在: {target}")
        pos = doc.get("positive") or []
        neg = doc.get("negative") or []
        if not isinstance(pos, list) or len(pos) < MIN_POS:
            errs.append(f"{fn} :: 正例 {len(pos) if isinstance(pos,list) else '?'} 条 < {MIN_POS}")
        if not isinstance(neg, list) or len(neg) < MIN_NEG:
            errs.append(f"{fn} :: 负例 {len(neg) if isinstance(neg,list) else '?'} 条 < {MIN_NEG}（规范要求近邻负例 8–10 条）")
        for h in neg:
            if not isinstance(h, str):
                errs.append(f"{fn} :: 负例不是字符串: {h!r}")
                continue
            if len(h.strip()) < 6:
                errs.append(f"{fn} :: 负例过短像占位: {h!r}")
            elif not is_near_neighbor(h, target, all_skills):
                errs.append(f"{fn} :: 负例不是「近邻」（与任何技能的关键词都不共享，测不出东西）: {h!r}")
    return errs


def run_eval(name: str, doc: dict, host_cmd: str, model: str) -> dict:
    """实跑：把全部技能清单 + 一条 hint 给宿主，让模型盲选，返回选中的技能名。"""
    prompt = (
        "下面是你可用的技能清单（每行一个）。请只回答最该用的那一个技能名，不要解释。\\n"
        "{list}\\n\\n请求：{hint}\\n只回答技能名："
    )
    skills = [d for d in sorted(os.listdir(SKILLS_ROOT))
              if os.path.isfile(os.path.join(SKILLS_ROOT, d, "SKILL.md"))]
    listing = chr(10).join(skills)
    res = {"skill": name, "pos_hits": 0, "pos_n": 0, "neg_hits": 0, "neg_n": 0, "errors": []}
    for kind, key in (("pos", "positive"), ("neg", "negative")):
        for hint in (doc.get(key) or []):
            try:
                out = subprocess.run(
                    [host_cmd, "-p", "--no-session", "--model=" + model,
                     prompt.replace("{list}", listing).replace("{hint}", hint)],
                    capture_output=True, text=True, timeout=180)
                picked = (out.stdout or "").strip().splitlines()
                picked = picked[-1].strip() if picked else ""
            except Exception as exc:  # noqa: BLE001
                res["errors"].append(f"{hint!r}: {exc}")
                continue
            hit = (name in picked) or (picked == name)
            if kind == "pos":
                res["pos_n"] += 1
                res["pos_hits"] += int(hit)
            else:
                res["neg_n"] += 1
                res["neg_hits"] += int(hit)
    res["pos_rate"] = round(res["pos_hits"] / res["pos_n"], 3) if res["pos_n"] else None
    res["neg_rate"] = round(res["neg_hits"] / res["neg_n"], 3) if res["neg_n"] else None
    return res


def selftest() -> int:
    """控制组：结构判据必须能判红坏样本、放行好样本。

    ★ 没有控制组的门 = 没有门。本门此前只有「结构检查通过」这一句话，
      没人验证过它真能判红 —— 这里补上：
        坏样本 4 类（技能不存在 / 正例不足 / 弱负例 / 负例过短）→ 必须报错；
        好样本 1 类（8 正 + 8 近邻负）→ 必须零报错。
      近邻负例用 routing.json 的全局关键词池拼（与真 eval 集同一套判据）。
    """
    all_skills = [d for d in sorted(os.listdir(SKILLS_ROOT))
                  if os.path.isfile(os.path.join(SKILLS_ROOT, d, "SKILL.md"))]
    if not all_skills:
        print("test-trigger-rate: 控制组 FAIL（技能目录为空，无法构造样本）")
        return 1
    target = "ida-reverse" if "ida-reverse" in all_skills else all_skills[0]

    pool: list[str] = []
    for s in all_skills:
        pool.extend(k for k in keywords_of(s) if len(k) >= 3)
    if not pool:
        print("test-trigger-rate: 控制组 FAIL（routing.json 没给出任何 ≥3 字符关键词，近邻判据无法验证）")
        return 1
    kw = max(pool, key=len)  # 用最长的关键词拼负例，确保命中近邻判据

    pos8 = [f"请处理样例任务 {i}" for i in range(8)]
    neg8 = [f"这条请求里带了 {kw} 关键词但需要的是另一件事 {i}" for i in range(8)]

    cases = [
        ("坏：技能不存在",
         {"skill": "__no_such_skill__", "positive": pos8, "negative": neg8}, True),
        ("坏：正例只有 7 条",
         {"skill": target, "positive": pos8[:7], "negative": neg8}, True),
        ("坏：弱负例（跟技能域无关的日常语）",
         {"skill": target, "positive": pos8,
          "negative": ["帮我订一张明天去上海的机票"] * 8}, True),
        ("坏：负例过短像占位",
         {"skill": target, "positive": pos8, "negative": ["短"] * 8}, True),
        ("好：8 正 + 8 近邻负",
         {"skill": target, "positive": pos8, "negative": neg8}, False),
    ]
    ok = True
    for label, doc, should_fail in cases:
        doc["_file"] = f"<control:{label}>"
        errs = structural_check({target: doc})
        fired = bool(errs)
        verdict = "PASS" if fired == should_fail else "FAIL"
        if fired != should_fail:
            ok = False
        print(f"  [{verdict}] {label} :: 判红={fired}（期望 {should_fail}）")
        if fired != should_fail and errs:
            print("        " + errs[0][:140])
    print("test-trigger-rate: 控制组 " + ("PASS（本门可信）" if ok else "FAIL（本门判据失效）"))
    return 0 if ok else 1


def record_run(scope: str, n_errs: int, n_skills: int) -> None:
    """实跑台账 —— 与 test-assault-behavior 共用一份 jsonl，供 `relab2.ps1 doctor` 报"上次实跑"。"""
    import time
    from pathlib import Path
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = Path(base) / "reverse-skill" / "behavior-runs.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "gate": "test-trigger-rate",
               "mode": "run", "scope": scope, "skills": n_skills, "failed": n_errs}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"  实跑台账已记：{path}")
    except OSError:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="store_true", help="实跑（需要模型调用）")
    ap.add_argument("--only", default="")
    ap.add_argument("--limit", type=int, default=0, help="最多实跑几个技能")
    ap.add_argument("--host", default="omp", help="宿主 CLI")
    ap.add_argument("--model", default="juhui/deepseek-v4.1-flash")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true", help="只跑控制组（验证本门判据仍有效）")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    evals, errs = load_evals()
    if not evals and not errs:
        print("test-trigger-rate: FAIL（tests/evals/ 里一个 eval 集都没有 —— "
              "没有触发率数据，就无法回答「这个技能在需要时会不会被选中」）")
        print("  提示：模板见 skills/tests/evals/README.md")
        return 1

    errs += structural_check(evals)

    # ★ 控制组随默认模式一起跑：门自己失效的话，后面的绿都是假的。
    if selftest() != 0:
        errs.append("控制组未通过 —— 本门的结构判据已失效（见上面的控制组输出）")

    results = []
    if args.run and not errs:
        names = [args.only] if args.only else sorted(evals)
        if args.limit:
            names = names[: args.limit]
        for n in names:
            r = run_eval(n, evals[n], args.host, args.model)
            results.append(r)
            bad = []
            if r["pos_rate"] is not None and r["pos_rate"] < POS_THRESHOLD:
                bad.append(f"正例触发率 {r['pos_rate']} < {POS_THRESHOLD}")
            if r["neg_rate"] is not None and r["neg_rate"] >= NEG_THRESHOLD:
                bad.append(f"负例触发率 {r['neg_rate']} >= {NEG_THRESHOLD}（抢触发）")
            if bad:
                errs.append(f"{n} :: " + "; ".join(bad))

    if args.json:
        print(json.dumps({"evals": len(evals), "errors": errs, "results": results},
                         ensure_ascii=False, indent=2))
    else:
        print(f"test-trigger-rate: eval sets={len(evals)} ran={len(results)}")
        if not results:
            print("")
            print("  " + "!" * 66)
            print("  ⚠️  本次只做了**结构检查**（eval 集存在、字段齐全）—— 模型行为一次都没验。")
            print("     这道门在 CI 里从不带 --run，所以「技能能不能被正确触发」这件事，CI 给不出任何证据。")
            print("     要真数字：python skills/tests/test-trigger-rate.py --run --limit 20（会调模型，慢且花钱）。")
            print("  " + "!" * 66)
        if results:
            print("  ┌ 实测触发率（正例应 ≥0.5 / 负例应 <0.5）")
            for r in results:
                flag = ""
                if r["pos_rate"] is not None and r["pos_rate"] < POS_THRESHOLD:
                    flag += " ← 正例未达线"
                if r["neg_rate"] is not None and r["neg_rate"] >= NEG_THRESHOLD:
                    flag += " ← 负例抢触发"
                print(f"  │ {r['skill']:<24} 正 {r['pos_hits']}/{r['pos_n']} = {r['pos_rate']}"
                      f"   负 {r['neg_hits']}/{r['neg_n']} = {r['neg_rate']}{flag}")
                if r["errors"]:
                    print(f"  │   运行错误 {len(r['errors'])} 条（例：{r['errors'][0][:60]}）")
            print("  └ 注：样本小则只是抽样，不是全量结论。全量去掉 --limit。")
        if errs:
            print(f"  FAIL（{len(errs)} 条）")
            for e in errs:
                print("    " + e)
        else:
            print(f"  PASS（结构检查通过；正例 ≥{MIN_POS} / 近邻负例 ≥{MIN_NEG}）")
    if args.run:
        record_run(args.only or "(all)", len(errs), len(results))
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
