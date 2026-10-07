#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""route-fuzzy.py -- 只读实验性模糊匹配打分层（不改现有路由）.

只读: 仅读取 registry.json / routing.json, 不写任何现有文件.
标准库: re / math / collections / json / argparse / unicodedata / pathlib.
不装第三方包.

语料 (corpus) 固定取自 routing.json 本身, 未针对 86 条自然基准调参:
  每个路由文档 = label + skill 路径分词 + 从 keywords 的 must/mustAll
  正则中机械抽出的字面词 (去正则元字符, 保留中文与拉丁词).
  不含 note 字段, 不含任何基准 hint 衍生的同义词表.

两种相似度 (可对比, 每次同时输出):
  1) 字符 n-gram Dice: bigram Dice + trigram Dice.
     中文"近失"(逃出去 vs 逃逸)靠字符重叠救.
  2) BM25 (手写, 标准库): latin 词 + 单汉字 token, k1=1.2, b=0.75,
     IDF = ln(1 + (N - df + 0.5) / (df + 0.5)).
     英文/混合 (ios/k8s/sql) 靠词项权重救.
  3) fused = alpha * bigramDice + (1 - alpha) * bm25_norm
     (bm25_norm = bm25 / 本 query 最大 bm25).

证据: 每条候选给出 ngram_bigram / ngram_trigram / bm25 / fused 四分,
命中 bigram 样例、命中 token(含 idf)、命中字面词样例.

用法:
  单条: python scripts/route-fuzzy.py --hint "<任务>" [--mode fused|ngram|bm25]
  榜单: python scripts/route-fuzzy.py --hint "<任务>" --top-k 5 --json
  评测: python scripts/route-fuzzy.py --eval-benchmark <bench.json> --out <res.json>
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import re
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROUTING = REPO_ROOT / "skills" / "config" / "routing.json"
DEFAULT_REGISTRY = REPO_ROOT / "skills" / "community" / "registry.json"

K1 = 1.2
B = 0.75
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
LATIN_RE = re.compile(r"[a-z0-9_]+")

# ---------------- 规范化与分词 ----------------

def norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").lower()
    return s

def bm25_tokens(s: str) -> list[str]:
    """latin 词 + 逐个汉字. 中文无分词, 用单字保证召回, 权重由 IDF 承担."""
    s = norm_text(s)
    toks: list[str] = []
    toks.extend(LATIN_RE.findall(s))
    toks.extend(CJK_RE.findall(s))
    return toks

def ngram_string(s: str) -> str:
    """n-gram 用连续串: 去掉空白与标点, 保留拉丁小写+数字+汉字."""
    s = norm_text(s)
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", s)

def ngrams(s: str, n: int) -> set[str]:
    if len(s) < n:
        return set()
    return {s[i:i + n] for i in range(len(s) - n + 1)}

def dice(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return 2.0 * inter / (len(a) + len(b))

# ---------------- 从正则中机械抽字面词 ----------------

LOOK_RE = re.compile(r"\(\?<[=!][^)]*\)|\(\?[=:!][^)]*\)")
BRACE_RE = re.compile(r"\{[^}]*\}")
PAREN_RE = re.compile(r"[()]")
CLASS_RE = re.compile(r"\[[^\]]*\]")

def literals_from_pattern(pat: str) -> list[str]:
    """把一条正则拆成候选字面词: 按 | 切分, 去正则元字符, 保留中文/拉丁片段."""
    if not pat:
        return []
    out: list[str] = []
    try:
        parts = pat.split("|")
    except Exception:
        parts = [pat]
    for part in parts:
        p = LOOK_RE.sub(" ", part)
        p = BRACE_RE.sub(" ", p)
        p = CLASS_RE.sub(" ", p)
        p = PAREN_RE.sub(" ", p)
        p = p.replace("(?", " ")
        p = re.sub(r"\.\*|\.\+|\.\?|\\\b|\\b", " ", p)
        p = re.sub(r"[\\^$*+?.]", " ", p)
        for tok in re.findall(r"[\u4e00-\u9fff]{1,8}|[a-z0-9]{2,}", norm_text(p)):
            t = tok.strip("_")
            if len(t) >= 1 and t not in ("http", "https"):
                out.append(t)
    return out

def build_route_docs(routing: dict) -> dict[str, dict]:
    """route_id -> {label, skill, literals, doc_text}."""
    docs: dict[str, dict] = {}
    routes = routing.get("routes", {})
    for rid, r in routes.items():
        if rid == routing.get("meta", {}).get("fallbackId", "R0"):
            continue  # R0 为回退, 不参与模糊排名
        label = r.get("label", "")
        skill = r.get("skill", "")
        lits: list[str] = []
        for kw in r.get("keywords", []):
            lits.extend(literals_from_pattern(kw.get("must", "")))
            for m in kw.get("mustAll", []) or []:
                lits.extend(literals_from_pattern(m))
        seen: set[str] = set()
        uniq: list[str] = []
        for t in lits:
            if t not in seen:
                seen.add(t)
                uniq.append(t)
        doc_text = " ".join([label, skill.replace("/", " ")] + uniq)
        docs[rid] = {
            "label": label,
            "skill": skill,
            "literals": uniq,
            "doc_text": doc_text,
        }
    return docs

# ---------------- BM25 ----------------

class BM25:
    def __init__(self, docs: dict[str, list[str]]):
        self.docs = docs
        self.N = len(docs)
        self.doc_len: dict[str, int] = {k: len(v) for k, v in docs.items()}
        self.avgdl = sum(self.doc_len.values()) / max(1, self.N)
        df: collections.Counter[str] = collections.Counter()
        for toks in docs.values():
            for t in set(toks):
                df[t] += 1
        self.df = df
        self.idf: dict[str, float] = {}
        for t, d in df.items():
            self.idf[t] = math.log(1.0 + (self.N - d + 0.5) / (d + 0.5))

    def score(self, qtoks: list[str], doc_id: str) -> tuple[float, list[tuple[str, float]]]:
        tf: collections.Counter[str] = collections.Counter(self.docs[doc_id])
        dl = self.doc_len[doc_id] or 1
        total = 0.0
        hits: list[tuple[str, float]] = []
        for t in qtoks:
            if t not in tf:
                continue
            idf = self.idf.get(t)
            if idf is None:
                continue
            f = tf[t]
            denom = f + K1 * (1.0 - B + B * dl / (self.avgdl or 1.0))
            s = idf * (f * (K1 + 1.0)) / denom
            total += s
            hits.append((t, round(s, 4)))
        hits.sort(key=lambda x: -x[1])
        return total, hits

# ---------------- 打分层 ----------------

class FuzzyRouter:
    def __init__(self, routing: dict):
        self.routing = routing
        self.route_docs = build_route_docs(routing)
        tok_docs = {rid: bm25_tokens(d["doc_text"]) for rid, d in self.route_docs.items()}
        self.bm25 = BM25(tok_docs)
        self.ngram_cache: dict[str, tuple[set[str], set[str]]] = {}
        for rid, d in self.route_docs.items():
            s = ngram_string(d["doc_text"])
            self.ngram_cache[rid] = (ngrams(s, 2), ngrams(s, 3))

    def rank(self, hint: str) -> list[dict]:
        hs = ngram_string(hint)
        h2, h3 = ngrams(hs, 2), ngrams(hs, 3)
        qtoks = bm25_tokens(hint)
        rows: list[dict] = []
        bm: dict[str, float] = {}
        bmh: dict[str, list] = {}
        for rid in self.route_docs:
            sc, hits = self.bm25.score(qtoks, rid)
            bm[rid] = sc
            bmh[rid] = hits
        bmax = max(bm.values()) if bm else 0.0
        for rid, d in self.route_docs.items():
            d2, d3 = self.ngram_cache[rid]
            b2 = dice(h2, d2)
            b3 = dice(h3, d3)
            bscore = bm[rid]
            bnorm = (bscore / bmax) if bmax > 0 else 0.0
            fused = 0.5 * b2 + 0.5 * bnorm
            inter2 = sorted((h2 & d2))[:8]
            hl = norm_text(hint)
            hit_lits = [t for t in d["literals"] if t and t in hl][:8]
            rows.append({
                "route": rid,
                "label": d["label"],
                "skill": d["skill"],
                "ngram_bigram": round(b2, 4),
                "ngram_trigram": round(b3, 4),
                "bm25": round(bscore, 4),
                "bm25_norm": round(bnorm, 4),
                "fused": round(fused, 4),
                "ev_bigrams": inter2,
                "ev_tokens": bmh[rid][:8],
                "ev_literals": hit_lits,
            })
        return rows

    def ranked(self, hint: str, mode: str = "fused", top_k: int = 5) -> list[dict]:
        key = {"fused": "fused", "ngram": "ngram_bigram", "bm25": "bm25"}.get(mode, "fused")
        rows = self.rank(hint)
        rows.sort(key=lambda r: (-r[key], r["route"]))
        return rows[:top_k]

def load_json(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))

def main() -> int:
    ap = argparse.ArgumentParser(description="只读模糊路由打分层 (n-gram + BM25)")
    ap.add_argument("--hint", default="", help="单条 hint")
    ap.add_argument("--routing", default=str(DEFAULT_ROUTING))
    ap.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    ap.add_argument("--mode", default="fused", choices=["fused", "ngram", "bm25"])
    ap.add_argument("--alpha", type=float, default=0.5)
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--min-score", type=float, default=0.0)
    ap.add_argument("--json", action="store_true", help="只输出 JSON")
    ap.add_argument("--eval-benchmark", default="", help="跑通基准, 输出每条 top1")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    routing = load_json(Path(args.routing))
    try:
        reg = load_json(Path(args.registry))
        reg_n = len(reg.get("skills", [])) if isinstance(reg, dict) else 0
    except Exception as e:
        reg_n = -1
        print("WARN: registry unreadable: %s" % e)

    router = FuzzyRouter(routing)

    if args.eval_benchmark:
        bench = load_json(Path(args.eval_benchmark))
        cases = bench.get("cases", [])
        out_rows = []
        for i, c in enumerate(cases):
            hint = c.get("hint", "")
            exp = c.get("primary") or c.get("expect")
            ranked = router.ranked(hint, mode=args.mode, top_k=3)
            top = ranked[0] if ranked else None
            out_rows.append({
                "idx": i,
                "hint": hint,
                "expect": exp,
                "fuzzy_top1": top["route"] if top else None,
                "fused": top["fused"] if top else 0.0,
                "ngram_bigram": top["ngram_bigram"] if top else 0.0,
                "ngram_trigram": top["ngram_trigram"] if top else 0.0,
                "bm25": top["bm25"] if top else 0.0,
                "top3": [(r["route"], r["fused"], r["ngram_bigram"], r["bm25"]) for r in ranked],
            })
        payload = {"mode": args.mode, "total": len(out_rows), "rows": out_rows,
                   "registry_skills": reg_n, "corpus": "routing.json routes (R0 excluded)"}
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
        else:
            print(text)
        return 0

    if not args.hint:
        ap.error("--hint 或 --eval-benchmark 二选一必填")
    rows = router.rank(args.hint)
    if args.alpha != 0.5:
        for r in rows:
            r["fused"] = round(args.alpha * r["ngram_bigram"] + (1.0 - args.alpha) * r["bm25_norm"], 4)
    key = {"fused": "fused", "ngram": "ngram_bigram", "bm25": "bm25"}[args.mode]
    rows.sort(key=lambda r: (-r[key], r["route"]))
    rows = [r for r in rows if r[key] >= args.min_score][:args.top_k]
    if args.json:
        print(json.dumps({"hint": args.hint, "mode": args.mode, "candidates": rows},
                         ensure_ascii=False, indent=2))
    else:
        print("hint: %s" % args.hint)
        print("mode: %s | corpus: routing.json routes (R0 excluded, registry %s 条仅校验存在)" % (args.mode, reg_n))
        for r in rows:
            print("- %s %s | fused=%.4f ngram2=%.4f ngram3=%.4f bm25=%.4f | lit=%s | tok=%s | bi=%s" % (
                r["route"], r["label"], r["fused"], r["ngram_bigram"], r["ngram_trigram"],
                r["bm25"], "/".join(r["ev_literals"][:5]) or "-",
                "/".join("%s:%.2f" % (t, s) for t, s in r["ev_tokens"][:5]) or "-",
                "/".join(r["ev_bigrams"][:5]) or "-"))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
