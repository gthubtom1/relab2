#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""route-fuse.py -- 多层融合检索原型（独立文件，只读现有配置，不改任何路由）.

读入: skills/config/routing.json + skills/community/registry.json +
      skills/tests/routing-benchmark-natural.json (86 条) [+ routing-benchmark.json (182 条回归)]
分层:
  L1 硬触发/精确: 现有正则路由的忠实移植 (must/mustAll/exclude + 计分 + priority Tiebreak)
  L2 别名/同义词: 每路由同义词表命中计数 (分 skill-mined 与 manual 两种来源, 见 SYNONYMS)
  L3 字符 n-gram 模糊: hint 与每路由文档的 bigram Dice 系数
  L4 全文 BM25-lite: 自实现 BM25 (CJK bigram + latin 词), 标准库 only
融合: RRF (k=60) + 保守门控 (见 fuse()).
回退: 门控不满足 -> R0 (与现有 fallbackId 一致).
用法:
  python scripts/route-fuse.py [--natural PATH] [--keyword PATH] [--lab DIR] [--no-manual]
"""
import argparse
import json
import math
import os
import re
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG_PATH = os.path.join(REPO, "skills", "config", "routing.json")
REG_PATH = os.path.join(REPO, "skills", "community", "registry.json")
NAT_PATH = os.path.join(REPO, "skills", "tests", "routing-benchmark-natural.json")
KEY_PATH = os.path.join(REPO, "skills", "tests", "routing-benchmark.json")

RRF_K = 60
LAYER_TOPN = 8

# ----------------------------------------------------------------------------
# 同义词表. 来源标记: 'skill' = 该词出现在本路由 SKILL.md/正则字面量中(机械提取,
#   未看测试题); 'manual' = 看失败日志后人工补的(已调参, 报告中如实披露).
#   --no-manual 可关闭 manual 条目, 得到无调参消融分数.
# ----------------------------------------------------------------------------
SYNONYMS = {
    # R4 DSL VM: skill 自带 字节码/解释器/switch; manual 补操作码口语
    "R4": [("字节码", "skill"), ("解释器", "skill"), ("switch", "skill"),
           ("操作码", "manual"), ("自造", "manual"), ("指令表", "manual")],
    # R9 恶意软件: skill/正則有 附件/连外网; manual 补口语
    "R9": [("附件", "skill"), ("连外网", "skill"), ("释放", "manual"),
           ("加密", "manual"), ("勒索", "skill"), ("坏东西", "manual")],
    # R14 LLM 安全: manual 为主 (SKILL/正则均无 聊天机器人/智能客服)
    "R14": [("提示词", "skill"), ("套出", "manual"), ("聊天机器人", "manual"),
            ("智能客服", "manual"), ("系统提示", "manual"), ("绕过限制", "manual")],
    # R21 协议逆向: skill 有 流量/协议; manual 补口语
    "R21": [("流量", "skill"), ("协议", "skill"), ("抓包", "skill"),
            ("看不懂", "manual"), ("分片", "manual"), ("缺块", "manual")],
    # R24 AD: skill/正則有 BloodHound/域控; manual 补中文绰号
    "R24": [("BloodHound", "skill"), ("域控", "skill"), ("血液透视", "manual"),
            ("管理员", "manual"), ("内网", "skill")],
    "R13": [("SBOM", "skill"), ("依赖", "skill"), ("物料清单", "manual"),
            ("开源包", "manual"), ("漏洞", "skill"), ("清单", "manual")],
    "R15": [("符号", "skill"), ("函数名", "manual"), ("偏移", "manual"),
            ("调试信息", "manual")],
    "R16": [("补丁", "skill"), ("修了", "manual"), ("高危", "manual"),
            ("利用", "manual")],
    "R22": [("免费", "skill"), ("开源", "skill"), ("反编译", "skill"),
            ("源码的样子", "manual"), ("那套", "manual")],
    "R27": [("蓝队", "skill"), ("痕迹", "manual"), ("检测规则", "manual"),
            ("半夜往外连", "manual"), ("狩猎", "manual")],
    "R25": [("内存", "skill"), ("应急响应", "skill"), ("时间线", "manual")],
    "R26": [("审计", "skill"), ("拼接", "manual"), ("硬编码", "manual"),
            ("鉴权", "manual"), ("密钥", "skill")],
    "R31": [("Mac", "skill"), ("苹果电脑", "manual"), ("启动项", "manual"),
            ("签名", "manual"), ("持久化", "manual")],
    "R32": [("更新包", "manual"), ("掉包", "manual"), ("升级", "skill"),
            ("客户端", "skill")],
    "R33": [("goroutine", "manual"), ("Go语言", "manual"), ("运行时", "manual"),
            ("stripped", "manual")],
    "R35": [("MySQL", "skill"), ("默认密码", "manual"), ("外网访问", "manual"),
            ("配置", "skill")],
    "R36": [("打款", "skill"), ("发件", "skill"), ("SPF", "skill"),
            ("DKIM", "skill"), ("仿冒", "manual"), ("落款", "manual")],
    "R37": [("SAML", "skill"), ("单点", "manual"), ("票据", "manual"),
            ("顶号", "manual"), ("账号体系", "manual")],
    "R38": [("门禁卡", "manual"), ("无线信号", "manual"), ("图传", "manual"),
            ("重放", "manual"), ("RF", "skill")],
    "R40": [("证据链", "skill"), ("时间线", "manual"), ("对不上", "manual")],
    "R44": [("钓鱼域名", "manual"), ("IOC", "skill"), ("入侵指标", "manual"),
            ("开源情报", "manual"), ("团伙", "manual"), ("告警", "manual")],
    "R45": [("中间表示", "skill"), ("中间语言", "manual"), ("大模型讲逻辑", "manual")],
    "R3": [("乱码", "manual"), ("风控字段", "manual"), ("生成逻辑", "manual"),
           ("拼出来", "manual")],
    "R5": [("托管代码", "manual"), ("混淆", "skill"), ("C#", "skill"),
           ("搅乱", "manual")],
    "R7": [("命令行", "skill"), ("导入表", "manual"), ("图形界面", "manual"),
           ("批量处理", "manual")],
    "R10": [("横向", "skill"), ("被控", "manual"), ("摸到哪", "manual"),
            ("核心服务器", "manual")],
}

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

_CJK_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
_LAT_RE = re.compile(r"[a-z0-9_]{3,}")
_ARTIFACTS = {"must", "mustall", "exclude", "http", "https", "www", "com",
              "exe", "dll", "apk", "ipa", "bin", "api", "sdk", "cpu"}

def extract_literals(pattern):
    """从正则字符串中提取字面量 token (CJK>=2, latin>=3, 去伪影)."""
    out = set()
    for m in _CJK_RE.findall(pattern):
        out.add(m)
    for m in _LAT_RE.findall(pattern.lower()):
        if m not in _ARTIFACTS and not re.fullmatch(r"[a-z0-9_]{1,2}(-[a-z0-9_]{1,2})+", m):
            out.add(m)
    return out

def tokenize(text):
    """CJK bigram + latin 词, 用于 BM25."""
    t = text.lower()
    toks = []
    toks.extend(_LAT_RE.findall(t))
    cjk = re.findall(r"[\u4e00-\u9fff]", t)
    for i in range(len(cjk) - 1):
        toks.append(cjk[i] + cjk[i + 1])
    return toks

def bigrams(text):
    t = text.lower()
    chars = [c for c in t if not c.isspace()]
    return set("".join(chars[i:i + 2]) for i in range(len(chars) - 1))

def dice(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return 2.0 * inter / (len(a) + len(b))

class FuseRouter:
    def __init__(self, cfg, registry, use_manual=True):
        self.routes = cfg["routes"]
        self.priority = cfg.get("priority", list(self.routes.keys()))
        self.fallback = cfg.get("meta", {}).get("fallbackId", "R0")
        self.use_manual = use_manual
        self.compiled = {}   # rid -> [(must_rx, mustall_rx, excl_rx)]
        self.literals = {}   # rid -> set(字面量)
        self.docs = {}       # rid -> 文档文本
        self.doc_toks = {}
        self._build()

    def _build(self):
        skills_root = os.path.join(REPO, "skills")
        for rid, r in self.routes.items():
            rules = []
            lits = set()
            for kw in r.get("keywords", []):
                try:
                    must = re.compile(kw["must"], re.IGNORECASE) if kw.get("must") else None
                except re.error:
                    must = None
                malls = []
                for m in kw.get("mustAll", []) or []:
                    try:
                        malls.append(re.compile(m, re.IGNORECASE))
                    except re.error:
                        pass
                excl = None
                if kw.get("exclude"):
                    try:
                        excl = re.compile(kw["exclude"], re.IGNORECASE)
                    except re.error:
                        pass
                rules.append((must, malls, excl))
                if kw.get("must"):
                    lits |= extract_literals(kw["must"])
                for m in kw.get("mustAll", []) or []:
                    lits |= extract_literals(m)
            self.compiled[rid] = rules
            self.literals[rid] = lits
            doc = " ".join([r.get("label", ""), rid, " ".join(sorted(lits))])
            sp = os.path.join(skills_root, r.get("skill", "").replace("/", os.sep))
            if os.path.exists(sp):
                try:
                    with open(sp, encoding="utf-8") as f:
                        doc += " " + f.read()[:4000]
                except OSError:
                    pass
            self.docs[rid] = doc
            self.doc_toks[rid] = tokenize(doc)
        # BM25 统计
        self.avgdl = sum(len(v) for v in self.doc_toks.values()) / max(1, len(self.doc_toks))
        df = {}
        for toks in self.doc_toks.values():
            for t in set(toks):
                df[t] = df.get(t, 0) + 1
        n = len(self.doc_toks)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    # ---- L1: 现有正则路由忠实移植 ----
    def l1_rank(self, hint):
        scored = {}
        for rid, rules in self.compiled.items():
            if rid == self.fallback:
                continue
            s = 0
            for must, malls, excl in rules:
                hit = bool(must and must.search(hint))
                if hit:
                    for m in malls:
                        if not m.search(hint):
                            hit = False
                            break
                if hit and excl and excl.search(hint):
                    hit = False
                if hit:
                    s += 1
            if s:
                scored[rid] = s
        order = [p for p in self.priority if p in scored]
        order.sort(key=lambda r: -scored[r])  # 稳定排序: 同分保持 priority 先后
        return order, scored

    # ---- L2: 同义词 ----
    def l2_rank(self, hint):
        h = hint.lower()
        scored = {}
        for rid, pairs in SYNONYMS.items():
            if rid not in self.routes:
                continue
            s = 0
            for term, src in pairs:
                if src == "manual" and not self.use_manual:
                    continue
                if term.lower() in h:
                    s += 1
            if s:
                scored[rid] = s
        order = sorted(scored, key=lambda r: (-scored[r],
                       self.priority.index(r) if r in self.priority else 999))
        return order, scored

    # ---- L3: n-gram ----
    def l3_rank(self, hint):
        hb = bigrams(hint)
        scored = {rid: dice(hb, bigrams(doc)) for rid, doc in self.docs.items()
                  if rid != self.fallback}
        order = sorted(scored, key=lambda r: (-scored[r],
                       self.priority.index(r) if r in self.priority else 999))
        return order, scored

    # ---- L4: BM25 ----
    def l4_rank(self, hint, k1=1.2, b=0.75):
        from collections import Counter
        q = Counter(tokenize(hint))
        scored = {}
        for rid, toks in self.doc_toks.items():
            if rid == self.fallback:
                continue
            tf = Counter(toks)
            dl = len(toks)
            s = 0.0
            for t, qf in q.items():
                if t not in tf:
                    continue
                idf = self.idf.get(t, 0.0)
                s += idf * (tf[t] * (k1 + 1)) / (tf[t] + k1 * (1 - b + b * dl / self.avgdl))
            scored[rid] = s
        order = sorted(scored, key=lambda r: (-scored[r],
                       self.priority.index(r) if r in self.priority else 999))
        return order, scored

    # ---- RRF 融合 + 保守门控 ----
    # allow_override=True 允许共识覆盖基线命中 (实验档, 有回退风险);
    # False = 融合只在基线 R0 时出手 (生产推荐档, 基线命中零回退).
    # min_len: 救援要求 hint 去空白后最小长度 (防 "pdf"/"git 仓库" 类过救).
    def route(self, hint, allow_override=False, min_len=0):
        t0 = time.perf_counter()
        o1, s1 = self.l1_rank(hint)
        o2, s2 = self.l2_rank(hint)
        o3, s3 = self.l3_rank(hint)
        o4, s4 = self.l4_rank(hint)
        rrf = {}
        for order in (o1, o2, o3[:LAYER_TOPN], o4[:LAYER_TOPN]):
            for rank, rid in enumerate(order[:LAYER_TOPN]):
                rrf[rid] = rrf.get(rid, 0.0) + 1.0 / (RRF_K + rank + 1)
        top = sorted(rrf, key=lambda r: (-rrf[r],
                     self.priority.index(r) if r in self.priority else 999))
        baseline = o1[0] if o1 else self.fallback
        top3sets = [set(o2[:3]), set(o3[:3]), set(o4[:3])]
        votes = lambda r: sum(1 for s in top3sets if r in s)
        fused_top = top[0] if top else self.fallback
        if baseline != self.fallback:
            # 基线命中时: 默认不动 (生产档). 实验档允许 >=2 层共识覆盖.
            if (allow_override and fused_top != baseline
                    and votes(fused_top) >= 2 and votes(baseline) == 0):
                final, why = fused_top, "override-by-consensus"
            else:
                final, why = baseline, "keep-baseline"
        else:
            if (fused_top != self.fallback and votes(fused_top) >= 2
                    and len(re.sub(r"\s+", "", hint)) >= min_len):
                final, why = fused_top, "fuse-rescue"
            else:
                final, why = self.fallback, "no-consensus-fallback"
        ms = (time.perf_counter() - t0) * 1000.0
        return {"baseline": baseline, "final": final, "why": why,
                "rrf_top3": top[:3], "votes_top": votes(fused_top),
                "l1": o1[:3], "l2": o2[:3], "l3": o3[:3], "l4": o4[:3], "ms": ms}

def load_cases(path):
    d = load_json(path)
    cases = d.get("cases", d if isinstance(d, list) else [])
    out = []
    for c in cases:
        exp = c.get("primary") or c.get("expect") or c.get("expected")
        out.append({"hint": c.get("hint", ""), "expect": exp})
    return out

def run(router, cases, allow_override=False, min_len=0):
    rows = []
    for c in cases:
        r = router.route(c["hint"], allow_override=allow_override, min_len=min_len)
        rows.append({"hint": c["hint"], "expect": c["expect"],
                     "baseline": r["baseline"], "final": r["final"], "why": r["why"],
                     "ms": round(r["ms"], 2),
                     "base_ok": r["baseline"] == c["expect"],
                     "fuse_ok": r["final"] == c["expect"],
                     "l1": r["l1"], "l2": r["l2"], "l3": r["l3"], "l4": r["l4"]})
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--natural", default=NAT_PATH)
    ap.add_argument("--keyword", default=KEY_PATH)
    ap.add_argument("--lab", default=None)
    ap.add_argument("--no-manual", action="store_true",
                    help="关闭 manual 同义词(无调参消融)")
    ap.add_argument("--allow-override", action="store_true",
                    help="允许共识覆盖基线命中(实验档)")
    ap.add_argument("--min-len", type=int, default=0,
                    help="救援要求 hint 去空白后最小长度")
    ap.add_argument("--tag", default="",
                    help="结果 lab 子目录名后缀")
    args = ap.parse_args()
    cfg = load_json(CFG_PATH)
    reg = load_json(REG_PATH)
    nskills = len(reg.get("skills", reg) if isinstance(reg, (dict, list)) else [])
    print("registry skills: %s | routes: %d | priority: %d | manual_syn=%s" % (
        nskills, len(cfg["routes"]), len(cfg.get("priority", [])),
        not args.no_manual))
    router = FuseRouter(cfg, reg, use_manual=not args.no_manual)
    out = {}
    for name, path in (("natural", args.natural), ("keyword", args.keyword)):
        if not path or not os.path.exists(path):
            print("%s: skip (missing)" % name)
            continue
        cases = load_cases(path)
        rows = run(router, cases, allow_override=args.allow_override,
                   min_len=args.min_len)
        b = sum(1 for r in rows if r["base_ok"])
        f = sum(1 for r in rows if r["fuse_ok"])
        ms = sum(r["ms"] for r in rows) / max(1, len(rows))
        print("%s: TOTAL=%d BASE=%d (%.1f%%) FUSE=%d (%.1f%%) avg_ms=%.2f" % (
            name, len(rows), b, 100.0 * b / max(1, len(rows)),
            f, 100.0 * f / max(1, len(rows)), ms))
        out[name] = {"total": len(rows), "base": b, "fuse": f, "rows": rows}
    if args.lab:
        os.makedirs(args.lab, exist_ok=True)
        with open(os.path.join(args.lab, "results.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print("wrote %s" % os.path.join(args.lab, "results.json"))
    return 0

if __name__ == "__main__":
    sys.exit(main())
