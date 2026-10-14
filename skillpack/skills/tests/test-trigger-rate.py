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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="store_true", help="实跑（需要模型调用）")
    ap.add_argument("--only", default="")
    ap.add_argument("--limit", type=int, default=0, help="最多实跑几个技能")
    ap.add_argument("--host", default="omp", help="宿主 CLI")
    ap.add_argument("--model", default="juhui/deepseek-v4.1-flash")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    evals, errs = load_evals()
    if not evals and not errs:
        print("test-trigger-rate: FAIL（tests/evals/ 里一个 eval 集都没有 —— "
              "没有触发率数据，就无法回答「这个技能在需要时会不会被选中」）")
        print("  提示：模板见 skills/tests/evals/README.md")
        return 1

    errs += structural_check(evals)

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
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
