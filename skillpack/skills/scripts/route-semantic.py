#!/usr/bin/env python3
"""route-semantic.py —— 技能路由的**语义层**（BM25 over skill body）。

## 为什么要有它

现有 `master-route.ps1` 只吃 `routing.json` 的**关键词/正则**。审计（2026-10-18, A2）实测：
20 条真人原话严格命中 **5/20 = 25%**，且错时给 `confidence: high` ——
「这个网站的数据我扒不下来」→ `Fix bug`，「公司要做等保，查查服务器有没有洞」→ `Implement feature`。

这不是我们的实现问题，是**方法选错了**。检索领域的共识（vLLM Semantic Router、R3-Skill 等）：

    keyword / regex  →  只适合 fast path（精确术语、产品名、扩展名）
    embedding / BM25 →  才是自然语言的主力

R3-Skill（arXiv 2606.03565，腾讯，2026-06）还量了一条对本项目更关键的事实：
**「隐藏 skill body 会让路由准确率掉 31–44 个百分点」** —— body 不是元数据，是**主要路由信号**。
而我们现在只用了 frontmatter 的 keywords，body 一个字没进检索。

## 本实现的选择（受 4 GB 内存 + 零依赖约束）

| 方案 | 为什么不用 / 用 |
|---|---|
| 0.6B embedding（R3-Embedding） | 4 GB 内存跑不动，且要 torch |
| BM25 over `name+description+body` | **用这个** —— 纯 stdlib、索引几 MB、CPU 毫秒级 |
| 中文分词 | 复用 `experience-card.py:search_terms` 的**二元切词**（项目已验证过的中文方案） |

## 用法

    python skills/scripts/route-semantic.py --hint "这个网站的数据我扒不下来"
    python skills/scripts/route-semantic.py --hint "..." --top 5 --json
    python skills/scripts/route-semantic.py --self-test      # 跑内置的 12 条正确性用例

退出码：0 正常 / 1 --self-test 有错 / 2 用法错误
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent
REPO = SKILLS.parent.parent

# ---------------------------------------------------------------- 分词
_SPLIT = re.compile(r"[\s,，、;；/|()（）\[\]{}<>\"'`~!@#$%^&*+=?？：:。.\\_\-]+")
_CJK = re.compile(r"[\u4e00-\u9fff]")


# 中文虚词/指示词 —— 它们在任何技能正文里都高频，是纯噪声
_STOP_ZH = set("""这个 那个 一个 什么 怎么 为什么 能不能 可以 帮我 看看 想 要 的 了 是 在 我 你 他
老是 一直 总是 就是 还是 但是 而且 因为 所以 如果 然后 现在 已经 没有 不是 有点 一下
东西 事情 问题 情况 地方 时候 这样 那样 哪些 多少 如何 怎样 请 给 让 把 被 从 到 和 与""".split())
_STOP_EN = {"the","a","an","is","are","to","of","and","or","for","with","in","on","it","this","that"}


def tokenize(text: str) -> list[str]:
    """英文按词、中文按二元切（与 experience-card.py 同一套已验证逻辑）+ 去停用词。"""
    out: list[str] = []
    for part in _SPLIT.split(text.lower()):
        if not part:
            continue
        # 拉丁/数字段：整段保留（含 3 字以上才留，避免 a/an 噪声）
        latin = re.findall(r"[a-z0-9][a-z0-9_.+\-]*", part)
        for w in latin:
            if len(w) >= 2 and w not in _STOP_EN:
                out.append(w)
        # 中文段：二元切
        for run in re.findall(r"[\u4e00-\u9fff]+", part):
            if run in _STOP_ZH:
                continue
            for i in range(len(run) - 1):
                bg = run[i:i + 2]
                if bg not in _STOP_ZH:
                    out.append(bg)
    return out


# ---------------------------------------------------------------- 语料
def read_skill(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    name = path.parent.name
    desc = ""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, re.S)
    if m:
        fm = m.group(1)
        d = re.search(r"^description:\s*(.+)$", fm, re.M)
        if d:
            desc = d.group(1).strip()
        n = re.search(r"^name:\s*(.+)$", fm, re.M)
        if n:
            name = n.group(1).strip()
        body = raw[m.end():]
    else:
        body = raw
    # 去来源声明/改编说明里的上游引用（它们会把无关技能拉近）
    body = re.sub(r"^##\s*来源声明.*?(?=^##\s)", "", body, flags=re.S | re.M)
    # ★ 字段加权：description 里就有「用于：403/412/429、HAR 离线复现」这类**真实症状词**，
    #   是自然语言查询最直接的匹配面；body 只做补充（长文档会被 BM25 的长度归一化稀释）。
    text = " ".join([desc] * 5 + [name] * 3 + [body])
    return {"id": path.parent.name, "name": name, "desc": desc, "text": text}


class BM25:
    def __init__(self, docs: list[dict], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = docs
        self.tfs: list[Counter] = []
        self.lens: list[int] = []
        df: Counter = Counter()
        for d in docs:
            toks = tokenize(d["text"])
            tf = Counter(toks)
            self.tfs.append(tf)
            self.lens.append(len(toks))
            for t in tf:
                df[t] += 1
        self.N = len(docs)
        self.avgdl = (sum(self.lens) / self.N) if self.N else 0.0
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def scores(self, query: str) -> list[tuple[str, float]]:
        q = tokenize(query)
        if not q:
            return []
        out = []
        for i, tf in enumerate(self.tfs):
            s = 0.0
            dl = self.lens[i] or 1
            for t in q:
                f = tf.get(t)
                if not f:
                    continue
                idf = self.idf.get(t, 0.0)
                s += idf * (f * (self.k1 + 1)) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            if s > 0:
                out.append((self.docs[i]["id"], s))
        out.sort(key=lambda x: -x[1])
        return out


SYMPTOM = SKILLS / "SYMPTOM-INDEX.md"
_ROW = re.compile(r"^\|\s*[\"「](.+?)[\"」]\s*\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|\s*(.*?)\s*\|\s*$", re.M)


def load_symptom_index() -> list[dict]:
    """解析 `SYMPTOM-INDEX.md` 的「用户这样说 → 去这里」表（204 行）。

    ★ 这是本项目的**正确方法**，只是以前没接进路由：
      语料是「用户会怎么描述这个需求」的**现象句**，与查询**同分布** ——
      而 BM25 over skill body 是「文档 vs 短查询」的异分布匹配，实测只有 4/12。
      文档自己写着「master-route 报 low / R0 时先在这张表里对现象」，
      但那条路要人（或模型）**主动去读**；这里把它做成机器可检索的索引。
    """
    if not SYMPTOM.is_file():
        return []
    raw = SYMPTOM.read_text(encoding="utf-8", errors="replace")
    docs = []
    for m in _ROW.finditer(raw):
        phrase, label, path, note = m.groups()
        skill = path.split("/")[0]
        if not skill or skill.startswith("."):
            continue
        docs.append({"id": skill, "name": label, "desc": note,
                     "text": phrase + " " + note + " " + label})
    return docs


def load_skill_docs() -> list[dict]:
    """第二路：每个 SKILL.md 的 name + description（**不含 body**）。

    2026-10-18 实测：把 body 拼进去后，单个技能文档 6998 tokens，而查询只有 7 个 token ——
    BM25 的长度归一化把「接口老是返回 412」这条的正确技能压出 top10，
    尽管它的 description 里 `412` 出现 6 次。去掉 body 后症状词不再被稀释。
    """
    docs = []
    for p in sorted(SKILLS.glob("*/SKILL.md")):
        if p.parent.name.startswith(("_", ".")):
            continue
        try:
            d = read_skill(p)
        except OSError:
            continue
        d["text"] = " ".join([d["desc"]] * 5 + [d["name"]] * 3)
        docs.append(d)
    return docs


def load_index():
    """双索引：症状句（用户会怎么说）+ 技能描述（技能声称能做什么）。

    ★ 单靠任一路都不够（2026-10-18 实测）：
      · 只用 SYMPTOM-INDEX -> recall@5 = 3/12（「接口老是返回 412」在这张表里没有对应行）
      · 只用 SKILL.md body -> 4/12（长文档把短查询稀释）
      两路用 RRF 融合后取候选，再由调用方（模型）做最终判定。
    """
    sym = load_symptom_index()
    sk = load_skill_docs()
    return sym, sk


def load_index_legacy() -> tuple[BM25, list[dict]]:
    sym = load_symptom_index()
    if sym:
        return BM25(sym), sym
    docs = []
    for p in sorted(SKILLS.glob("*/SKILL.md")):
        if p.parent.name.startswith(("_", ".")) or p.parent.name in ("community", "config",
                                                                     "field-journal", "ops",
                                                                     "references", "scripts",
                                                                     "templates", "tests", "work"):
            continue
        try:
            docs.append(read_skill(p))
        except OSError:
            continue
    return BM25(docs), docs


# ---------------------------------------------------------------- 融合检索
def hybrid(hint: str, top: int = 5, k: int = 60) -> list[dict]:
    """RRF 融合两路 BM25：症状句索引 + 技能描述索引。

    RRF 的好处：两路的分数尺度完全不同（一个在症状句上、一个在 description 上），
    直接加权会互相压；按**排名**融合就不需要标定。
    """
    sym, sk = load_index()
    out: dict[str, dict] = {}

    if sym:
        b1 = BM25(sym)
        # 每路只取前 20 参与融合：整条长尾一起加会让「某一路的第 1 名」被另一路的第 15 名压掉
        for rank, (sid, sc) in enumerate(b1.scores(hint), 1):
            e = out.setdefault(sid, {"skill": sid, "rrf": 0.0, "why": []})
            e["rrf"] += 1.0 / (k + rank)
            e["why"].append("symptom#%d" % rank)

    if sk:
        # ★ desc 路权重 ×2：2026-10-18 实测，「接口老是返回 412」在 desc 索引里
        #   web-protocol-reverse 得分 7.03 排第一，但等权 RRF 被 symptom 路的高排名
        #   (api-security) 稀释掉了。技能 description 是「这个技能声称能做什么」的
        #   权威自述，比症状句更接近用户要的结果，所以加权。
        b2 = BM25(sk)
        for rank, (sid, sc) in enumerate(b2.scores(hint), 1):
            e = out.setdefault(sid, {"skill": sid, "rrf": 0.0, "why": []})
            e["rrf"] += 2.0 / (k + rank)
            e["why"].append("desc#%d" % rank)

    rows = sorted(out.values(), key=lambda x: -x["rrf"])[:top]
    for r in rows:
        r["rrf"] = round(r["rrf"], 5)
        r["why"] = ",".join(r["why"])
    return rows


# ---------------------------------------------------------------- 正确性用例
SELF_TEST = [
    ("这个网站的数据我扒不下来，老是报错不给我", "web-protocol-reverse"),
    ("公司要做等保，让我查查这几台服务器有没有洞", "pentest-tools"),
    ("客户发来一个手机应用的安装包，想看看它开机自启后都在后台干些什么", "apk-reverse"),
    ("接口老是返回 412，怎么绕过", "web-protocol-reverse"),
    ("抓了 HAR，想离线重放", "web-protocol-reverse"),
    ("这个 exe 一打开就闪退，帮我看看为什么", "reverse-engineering"),
    ("软件要输入注册码，能不能算出正确的", "reverse-engineering"),
    ("这个 dll 里有个校验，想改成永远返回 true", "reverse-engineering"),
    ("帮我看看这个路由器的固件里有什么", "firmware-pentest"),
    ("这个安卓 app 检测 root，装到模拟器上就退出", "apk-reverse"),
    ("挖矿木马样本，想搞清楚它连哪", "malware-analysis"),
    ("网页上的加密参数 sign 是怎么算的", "js-reverse"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hint", default="")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    sym, sk = load_index()
    if not sym and not sk:
        print("用法错误：既没有 SYMPTOM-INDEX.md 也没有 SKILL.md", file=sys.stderr)
        return 2

    if a.self_test:
        ok = 0
        for hint, want in SELF_TEST:
            got = [r["skill"] for r in hybrid(hint, top=5)]
            top1 = got[0] if got else None
            hit = top1 == want
            top3 = got[:3]
            print("  [%s] %-34s want=%-22s got=%-22s top3=%s"
                  % ("OK  " if hit else "FAIL", hint[:34], want, top1, top3))
            ok += 1 if hit else 0
        print()
        print("BM25 路由自测：%d/%d top-1 正确" % (ok, len(SELF_TEST)))
        return 0 if ok == len(SELF_TEST) else 1

    if not a.hint.strip():
        print("用法错误：需要 --hint", file=sys.stderr)
        return 2

    rows = hybrid(a.hint, top=a.top)
    if a.json:
        print(json.dumps({"hint": a.hint,
                          "index": {"symptom_phrases": len(sym), "skill_descs": len(sk)},
                          "top": [{"skill": r["skill"], "rrf": r["rrf"], "why": r["why"]}
                                  for r in rows]},
                         ensure_ascii=True, indent=2))
    else:
        print("hint = %s" % a.hint)
        print("index = %d 条症状句 + %d 个技能描述（RRF 融合，desc 权重 x2）" % (len(sym), len(sk)))
        for r in rows:
            print("  %-28s %.5f  [%s]" % (r["skill"], r["rrf"], r["why"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
