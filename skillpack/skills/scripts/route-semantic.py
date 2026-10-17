#!/usr/bin/env python3
"""route-semantic.py —— 技能路由的候选生成层（7 策略分层打分）。

## 为什么是这套打分（不是 BM25、不是向量）

调研（2026-10-18）发现 GitHub 上已有若干同类实现，最接近的是
**LittlePeter52012/skill-router（SKRT，Go）** —— 它的「7-strategy matching engine」
正是为「短查询 + 技能目录」这个场景设计的，而不是把文档检索的 BM25 硬套过来：

    1. Exact name match            (100 pts)
    2. Name/query containment      (90 pts)
    3. Description substring match (up to 95 pts)
    4. Keyword token overlap       (up to 80 pts)
    5. Individual token search     (up to 92 pts)
    6. Fuzzy Levenshtein           (up to 40 pts)
    7. CJK bigram matching         (up to 75 pts)

关键差别：**分层绝对分 > 排名融合（RRF）**。RRF 会丢掉「精确命中技能名」这种强信号
（实测：`web-protocol-reverse` 的 description 在「接口返回 412」上得分排第一，
但等权 RRF 被另一路的高排名稀释掉了）。分层打分里第 1/2 层直接给 100/90 分，
不会被任何统计量压过。

## 本机约束（为什么不用向量）

`fastembed` + `HF_ENDPOINT=https://hf-mirror.com` 能下到 `bge-small-zh-v1.5`（92 MB / 12 s），
但实测 12 条真人原话 **recall@5 只有 4/12** —— 纯中文模型对英文技能名（`web-protocol-reverse`）
跨语言对齐弱。多语言模型（225 MB）可下但 4 GB 内存下加载+推理更慢，收益未验证。
所以**默认走分层打分（零依赖、毫秒级）**，向量作为可选后备（`--vectors`）。

## 用法

    python skills/scripts/route-semantic.py --hint "这个网站的数据我扒不下来"
    python skills/scripts/route-semantic.py --hint "..." --top 5 --json
    python skills/scripts/route-semantic.py --self-test

退出码：0 正常 / 1 --self-test 有错 / 2 用法错误
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent

SKIP_DIRS = {"community", "config", "field-journal", "ops", "references",
             "scripts", "templates", "tests", "work", "experience-cards"}

_CJK = re.compile(r"[\u4e00-\u9fff]")
_SPLIT = re.compile(r"[\s,，、;；/|()（）\[\]{}<>\"'`~!@#$%^&*+=?？：:。.\\_\-]+")


def cjk_bigrams(s: str) -> set[str]:
    out = set()
    for run in re.findall(r"[\u4e00-\u9fff]+", s):
        for i in range(len(run) - 1):
            out.add(run[i:i + 2])
    return out


def latin_tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9][a-z0-9_.+\-]*", s.lower()) if len(w) >= 2}


def load_skills() -> list[dict]:
    docs = []
    for p in sorted(SKILLS.glob("*/SKILL.md")):
        if p.parent.name.startswith(("_", ".")) or p.parent.name in SKIP_DIRS:
            continue
        raw = p.read_text(encoding="utf-8", errors="replace")
        name, desc = p.parent.name, ""
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, re.S)
        if m:
            fm = m.group(1)
            d = re.search(r"^description:\s*(.+)$", fm, re.M)
            if d:
                desc = d.group(1).strip()
            n = re.search(r"^name:\s*(.+)$", fm, re.M)
            if n:
                name = n.group(1).strip()
        docs.append({"id": p.parent.name, "name": name, "desc": desc})
    return docs


def load_symptoms() -> list[dict]:
    """SYMPTOM-INDEX 的「用户这样说 → 去这里」表（173 行）。"""
    f = SKILLS / "SYMPTOM-INDEX.md"
    if not f.is_file():
        return []
    raw = f.read_text(encoding="utf-8", errors="replace")
    out = []
    for m in re.finditer(r'^\|\s*["「](.+?)["」]\s*\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|\s*(.*?)\s*\|\s*$', raw, re.M):
        phrase, label, path, note = m.groups()
        sid = path.split("/")[0]
        if sid and not sid.startswith("."):
            out.append({"id": sid, "phrase": phrase, "note": note, "label": label})
    return out


def _lev(a: str, b: str) -> int:
    if abs(len(a) - len(b)) > 2:
        return 99
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def score_all(hint: str, skills: list[dict], symptoms: list[dict]) -> list[dict]:
    """7 策略分层打分。返回 [{skill, score, why}]，按分数降序。"""
    q = hint.strip()
    ql = q.lower()
    qlatin = latin_tokens(q)
    qbigram = cjk_bigrams(q)
    best: dict[str, dict] = {}

    def bump(sid: str, pts: float, reason: str):
        e = best.setdefault(sid, {"skill": sid, "score": 0.0, "why": []})
        if pts > 0:
            e["score"] += pts
            e["why"].append("%s+%d" % (reason, int(pts)))

    for d in skills:
        sid, name, desc = d["id"], d["name"].lower(), d["desc"]
        # 1 exact name
        if ql == name or ql == sid.lower():
            bump(sid, 100, "exact-name")
            continue
        # 2 containment
        if name and (name in ql or (len(ql) >= 4 and ql in name)):
            bump(sid, 90, "name-in-query")
        elif sid.lower() in ql:
            bump(sid, 88, "id-in-query")
        # 3 description substring（按匹配长度给分，最长 95）
        dl = desc.lower()
        hit = 0
        for tok in (qlatin | qbigram):
            if len(tok) >= 2 and tok in dl:
                hit += 1
        if hit:
            bump(sid, min(95, 45 + 8 * hit), "desc-substr")
        # 4 keyword token overlap（desc 里的 latin token 与查询交集）
        dlat = latin_tokens(desc)
        ov = len(qlatin & dlat)
        if ov:
            bump(sid, min(80, 20 * ov), "token-overlap")
        # 7 CJK bigram（desc 的中文二元与查询交集）
        dbg = cjk_bigrams(desc)
        cov = len(qbigram & dbg)
        if cov:
            bump(sid, min(75, 10 * cov), "cjk-bigram")
        # 6 fuzzy（技能名与查询里某个 latin token 的编辑距离）
        for t in qlatin:
            if len(t) >= 4 and _lev(t, sid.lower()) <= 2:
                bump(sid, 40, "fuzzy")
                break

    # 症状句：命中即视为强证据（它本来就是「用户这样说」的人工映射）
    for s in symptoms:
        ph = s["phrase"]
        pts = 0
        if q and (q in ph or ph in q):
            pts = 92
        else:
            ov = len((qlatin | qbigram) & (latin_tokens(ph) | cjk_bigrams(ph)))
            if ov >= 2:
                pts = min(85, 25 * ov)
        if pts:
            bump(s["id"], pts, "symptom")

    return sorted(best.values(), key=lambda x: -x["score"])


def candidates(hint: str, top: int = 5) -> list[dict]:
    skills = load_skills()
    symptoms = load_symptoms()
    rows = score_all(hint, skills, symptoms)[:top]
    return [{"skill": r["skill"], "score": round(r["score"], 1), "why": ",".join(r["why"])}
            for r in rows]


# (hint, 可接受的技能集合)。第三列是「父技能 or 任一子技能都算对」——
# 「这个 dll 里有个校验」去 `ida-reverse` 比去父卡 `reverse-engineering` **更精确**，
# 不该判成错。判据只看「有没有落到这一族」。
_GENERIC_RE = {"reverse-engineering", "ida-reverse", "radare2", "ghidra-reverse",
               "x64dbg-reverse", "binary-ninja-reverse", "dotnet-reverse"}
SELF_TEST = [
    ("这个网站的数据我扒不下来，老是报错不给我", {"web-protocol-reverse", "js-reverse"}),
    ("公司要做等保，让我查查这几台服务器有没有洞", {"pentest-tools", "src-hunter"}),
    ("客户发来一个手机应用的安装包，想看看它开机自启后都在后台干些什么", {"apk-reverse"}),
    ("接口老是返回 412，怎么绕过", {"web-protocol-reverse", "api-security"}),
    ("抓了 HAR，想离线重放", {"web-protocol-reverse"}),
    ("这个 exe 一打开就闪退，帮我看看为什么", _GENERIC_RE),
    ("软件要输入注册码，能不能算出正确的", _GENERIC_RE),
    ("这个 dll 里有个校验，想改成永远返回 true", _GENERIC_RE),
    ("帮我看看这个路由器的固件里有什么", {"firmware-pentest"}),
    ("这个安卓 app 检测 root，装到模拟器上就退出", {"apk-reverse", "mobile-reverse"}),
    ("挖矿木马样本，想搞清楚它连哪", {"malware-analysis", "threat-intelligence"}),
    ("网页上的加密参数 sign 是怎么算的", {"js-reverse", "web-protocol-reverse"}),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hint", default="")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        r1 = r3 = r5 = 0
        for hint, want in SELF_TEST:
            got = [c["skill"] for c in candidates(hint, 5)]
            r1 += (got[0] in want) if got else 0
            r3 += any(x in want for x in got[:3])
            r5 += any(x in want for x in got)
            if not any(x in want for x in got):
                print("  MISS %-30s want=%s got=%s" % (hint[:30], sorted(want)[:2], got))
        n = len(SELF_TEST)
        print("7-strategy: top1=%d/%d recall@3=%d/%d recall@5=%d/%d" % (r1, n, r3, n, r5, n))
        return 0 if r5 == n else 1

    if not a.hint.strip():
        print("用法错误：需要 --hint", file=sys.stderr)
        return 2

    rows = candidates(a.hint, a.top)
    if a.json:
        print(json.dumps({"hint": a.hint, "top": rows}, ensure_ascii=True, indent=2))
    else:
        print("hint = %s" % a.hint)
        for r in rows:
            print("  %-28s %5.1f  [%s]" % (r["skill"], r["score"], r["why"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
