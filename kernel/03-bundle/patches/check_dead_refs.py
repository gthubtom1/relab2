#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_dead_refs.py —— 02-hubcore 死链 / 死引用 / 能力缺口校验器。

用法：
    python check_dead_refs.py                       # 人看的表，退出码 0 = 零死链
    python check_dead_refs.py --json                # 机器读
    python check_dead_refs.py --root <02-hubcore>   # 指定被检树（默认自动定位）

被检范围（只读，不改任何东西）：
    workflows/*.md          六条线
    docs/**/*.md            含 docs/methods/** 与两本目录式方法书的附录
    AGENTS.md               常驻提示词（额外加检，单独一行）

判定规则（DEAD-REFS.md 里有同一份说明；改规则必须同步改那份文档）：

R1  收集面：行内反引号里的记号（`` `xxx` ``）。围栏代码块另走 R7b。
R2  注释屏蔽：落在 <!-- --> 里的行不收（apply_*_fix.py 归档的旧原文不是活引用）。
R3  路径的形状：记号至少有一个「段」形如 `名字.ext`（名字非空、点前不含斜杠），
    或以 `/` 结尾，才算「看起来像路径」。像 `5/6`、`2-impl/3-build: business_flow`、
    `intent/constraints/rationale/sources`、`.bat/.cmd`、`/`、`/review` 这种
    「有斜杠但不是路径」的记号直接不判。
R4  占位符：含 < > { } * …  → PLACEHOLDER（不是死链）。
R5  运行期路径：TEMP/ .hub/ work/vX freeze/ artifacts/ 等运行期前缀，
    以及不带斜杠的裸文件名（main.py、MAP.md、resume.json…）→ RUNTIME。
    依据：hubcore 从不引用自己树里的裸文件名，裸文件名一律是产品侧/运行期的东西。
R6  安装根 / 系统外路径：
    R6a `tools/` `ctxiso/` `hub/` 开头 → EXTERNAL（安装根或运行期脚本）。
    R6b 首段不属于本系统（docs/ workflows/ templates/）的路径 → OFFSITE
        （下游资料、本机工具、别人的仓库）。
R7  本系统内的路径：首段是 docs/ workflows/ templates/，或以 ../ ./ 开头
    → 真去解析。基准两个，任一命中即 OK_LINK（文件或目录都算）：
        B1 = 该记号所在文件的目录
        B2 = 02-hubcore 根
    B2 的依据：02-hubcore/AGENTS.md §9.2 写明「命令里的路径一律写相对中枢根的」。
    B1/B2 都不命中 → DEAD_LINK（真死链，必须修）。
R7b 围栏代码块里的 `python tools/xxx.py` 之类，只计数不判死链（EXTERNAL）。
R8  裸书名：形如 [a-z][a-z0-9]*(-[a-z0-9]+)+ 的记号：
    - docs/methods/<名字>.md 存在 → OK_METHOD（算「这条线指向了方法书」）
    - 属于旧技能库里**没搬进来**的名字 → REMOVED_BOOK
      （本系统故意不带的能力，单独列，不算真死链）
    - 否则不是书名，不判
R9  松散方法书名：裸 `xxx.md` 且 xxx 是本系统真实存在的方法书
    → LOOSE_METHOD。写得不对（照字面在 workflows/ 下解析不到），
    按「写法要修」算进真死链桶，但单列一类，方便人工看。
R10 能力缺口：某条线指向的方法书数为 0（既没有 docs/methods/*.md 路径，
    也没有 OK_METHOD）→ 报「无书可开」。

退出码：0 = 零 DEAD_LINK / LOOSE_METHOD / DEAD_TOOL；1 = 有真死链；2 = 环境错。
REMOVED_BOOK、无书可开、UNCLASSIFIED_BOOK、EXTERNAL/OFFSITE 都会打印，但**不**单独导致退出码非 0
（它们要人拍板，不是脚本能判定的错）。

闸门自身的诚实性（FIX-15/FIX-16，改了必须同步改本段）：
R0a 收集面非空：被扫文件数 = 0，或扫到文件但引用数 = 0 → 退出码 2（环境错）。
    「什么都没查到」和「查了、零死链」是两回事，前者绝不能出绿灯。
R0b 旧技能库可达：--old-skills 解析不到真实技能目录时，结果里带 old_skills_missing=true，
    报告顶部打醒目告警行。此时 REMOVED_BOOK 桶不可信，靠 R0c 兜底。
R0c 裸书名不静默丢弃：形如 xxx-yyy 的记号，既不在 methods 里、也不在旧技能库里
    → 计入 UNCLASSIFIED_BOOK 单列一节。以前这些直接被「不是书名，不判」吞掉。
R0d 只有带 SKILL.md 的目录才算「一个技能」：scripts/ tests/ references/ ops/ 这类
    辅助目录不会被误报成「故意不带的能力」。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

INLINE_CODE = re.compile(r"`([^`\n]+)`")
# R1b：markdown 链接 [文字](目标)。http/mailto/# 开头的不判。
MD_LINK = re.compile(r"\]\(([^)\s]+)\)")
FENCE = re.compile(r"^\s*(python|py|pwsh|powershell|bash|sh)\s+((?:tools|ctxiso)/[\w./\\-]+)")
BOOKNAME = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$")
# R3：一个段形如 名字.ext，且 ext 必须是已知文件类型（否则 `mission.success`
#    `implementation.summary` 这种字段名会被误当路径）
SEG_FILE = re.compile(
    r"[^/\\.]+\.(md|py|jsonl|json|bat|cmd|sh|ps1|yaml|yml|txt|log|har|toml|ini|cfg|exe)$",
    re.I)

RUNTIME_SEGMENTS = {"TEMP", ".hub", "work", "freeze", "artifacts", "logs",
                    "dist", "node_modules", ".git"}
RUNTIME_BASENAMES = {
    "CHANGES.md", "FEATURES.md", "OWNER-SPEECH.md", "OWNER-STOPS.md",
    "WORK-HANDOFF.md", "SHIFT.md", "EXPERIMENTS.jsonl", "requirements.jsonl",
    "SURVIVOR.md", "dropped.json", "resume.json", "MAP.md", "STATUS.md",
    "TOOLING.md", "SOURCE.md", ".env", "physical-gates.json",
    "PROJECT-MEMORY.jsonl", "speech_land.py",
}
EXTERNAL_PREFIXES = ("tools/", "ctxiso/", "hub/")
SYSTEM_PREFIXES = ("docs/", "workflows/", "templates/")
SYSTEM_FILES = {"AGENTS.md", "MANIFEST.json", "build_hubcore.py"}

WORKFLOWS = ("desktop-product", "web-service", "cli-tool",
             "source-takeover", "exe-rebuild", "protocol-automation")
PARKED_EXPLICIT = ("github", "own-skill")

HERE = Path(__file__).resolve().parent
CTX = HERE.parent.parent
DEFAULT_ROOT = CTX / "02-hubcore"
REPO = CTX.parent                      # 本项目根
# FIX-16：旧技能库候选。第一个候选是历史布局（C:\relab\hub\.agents\skills），
# 在本机根本不存在 —— 旧代码拿它当默认值，removed_books() 里的 is_dir() 判断
# 于是恒假，REMOVED_BOOK 桶永远只剩 PARKED_EXPLICIT 两个名字，真实被移出的书
# 全部掉进「不是书名，不判」被静默吞掉。改成按序探测 + 缺失即告警。
OLD_SKILLS_CANDIDATES = (
    CTX.parent / "hub" / ".agents" / "skills",          # 历史布局
    REPO / "skillpack" / "skills",# 本机实际技能库
    REPO / "backups" / "skillpack-portable-20261007-061647" / "skills",
)

def resolve_old_skills(explicit: str | None = None) -> tuple[Path, bool]:
    """返回 (旧技能库路径, 是否真的存在)。显式 --old-skills 优先。"""
    if explicit:
        p = Path(explicit)
        return p, p.is_dir()
    for cand in OLD_SKILLS_CANDIDATES:
        if cand.is_dir():
            return cand, True
    return OLD_SKILLS_CANDIDATES[0], False

def comment_mask(lines: list[str]) -> list[bool]:
    mask = [False] * len(lines)
    inside = False
    for i, line in enumerate(lines):
        opens, closes = line.count("<!--"), line.count("-->")
        if inside:
            mask[i] = True
        if inside:
            if closes:
                inside = False
        elif opens and opens > closes:
            inside = True
            mask[i] = True
    return mask

def scan_files(root: Path) -> list[Path]:
    out: list[Path] = []
    if (root / "workflows").is_dir():
        out += sorted((root / "workflows").glob("*.md"))
    if (root / "docs").is_dir():
        out += sorted(p for p in (root / "docs").rglob("*.md") if p.is_file())
    if (root / "AGENTS.md").is_file():
        out.append(root / "AGENTS.md")
    return out

def segments(tok: str) -> list[str]:
    return [s for s in tok.replace("\\", "/").split("/")]

def has_file_segment(tok: str) -> bool:
    return any(SEG_FILE.search(s) for s in segments(tok))

def is_dir_ref(tok: str) -> bool:
    """以 / 结尾、且最后一段非空（`docs/methods/` 是，`/` 不是）。"""
    norm = tok.replace("\\", "/")
    if not norm.endswith("/"):
        return False
    return bool([s for s in norm.split("/") if s])

def is_placeholder(tok: str) -> bool:
    return any(c in tok for c in "<>{}*…") or "…" in tok

def runtime_reason(tok: str) -> str | None:
    segs = segments(tok)
    stripped = [s for s in segs if s]
    if any(s in RUNTIME_SEGMENTS for s in stripped[:1]):
        return "运行期路径"
    if not segs[0].find("/") == -1 or len(segs) == 1:
        base = segs[-1]
        if base in RUNTIME_BASENAMES:
            return "产品根/运行期"
    return None

def external_reason(tok: str) -> str | None:
    norm = tok.replace("\\", "/").lstrip("/")
    for p in EXTERNAL_PREFIXES:
        if norm.startswith(p):
            return "安装根/运行期脚本（build_hubcore.py 从不搬 tools/）"
    return None

def system_owned(tok: str) -> bool:
    norm = tok.replace("\\", "/")
    if norm.startswith("../") or norm.startswith("./"):
        return True
    if norm in SYSTEM_FILES:
        return True
    head = segments(norm)[0]
    return any(head == p.rstrip("/") or norm.startswith(p) for p in SYSTEM_PREFIXES)

def resolve(tok: str, b1: Path, b2: Path) -> tuple[str, str | None]:
    norm = tok.replace("\\", "/")
    b2 = b2.resolve()
    for tag, base in (("B1-文件同级", b1), ("B2-中枢根", b2)):
        try:
            cand = (base / norm).resolve()
        except (OSError, ValueError):
            continue
        if cand.is_file():
            return tag, cand.relative_to(b2).as_posix() if b2 in cand.parents or cand == b2 else str(cand)
        if cand.is_dir() and is_dir_ref(norm):
            return tag, (cand.relative_to(b2).as_posix() + "/") if b2 in cand.parents or cand == b2 else str(cand)
    return "未命中", None

def carried_methods(root: Path) -> set[str]:
    d = root / "docs" / "methods"
    if not d.is_dir():
        return set()
    return {p.stem for p in d.glob("*.md") if p.is_file()}

def removed_books(root: Path, old_skills: Path) -> tuple[set[str], dict[str, str]]:
    carried = carried_methods(root)
    out: set[str] = set()
    reason: dict[str, str] = {}
    if old_skills.is_dir():
        for d in sorted(old_skills.iterdir()):
            # R0d：只有带 SKILL.md 的目录才算「一个技能」。否则 scripts/ tests/
            # references/ ops/ _archive/ 这类辅助目录会被当成「本系统故意不带的能力」。
            if not d.is_dir() or not (d / "SKILL.md").is_file():
                continue
            if d.name in carried or d.name in WORKFLOWS or d.name == "INVARIANTS":
                continue
            out.add(d.name)
            reason[d.name] = ("build_hubcore.py PARKED_REASON 明写不带"
                              if d.name in PARKED_EXPLICIT
                              else "旧技能目录里有，但没进本系统")
    for n in PARKED_EXPLICIT:
        out.add(n)
        reason.setdefault(n, "build_hubcore.py PARKED_REASON 明写不带")
    return out, reason

def check(root: Path, old_skills: Path) -> dict:
    methods = carried_methods(root)
    removed, removed_reason = removed_books(root, old_skills)
    findings: list[dict] = []
    per_file: list[dict] = []
    fenced_cmds: list[dict] = []

    for path in scan_files(root):
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        mask = comment_mask(lines)
        rel = path.relative_to(root).as_posix()
        c = {"total": 0, "ok": 0, "runtime": 0, "placeholder": 0, "external": 0,
             "offsite": 0, "method": 0, "dead_link": 0, "loose_method": 0,
             "removed_book": 0, "unclassified": 0}
        methods_here: set[str] = set()

        def note(kind, i, tok, why, text_=None):
            f = {"kind": kind, "file": rel, "line": i, "token": tok, "why": why}
            if text_:
                f["text"] = text_
            findings.append(f)

        for idx, line in enumerate(lines):
            i = idx + 1
            m = FENCE.match(line)
            if m:
                fenced_cmds.append({"file": rel, "line": i, "token": m.group(2)})
            if mask[idx]:
                continue
            toks = [("code", t.strip()) for t in INLINE_CODE.findall(line)]
            for tgt in MD_LINK.findall(line):
                if tgt.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                toks.append(("link", tgt.strip()))
            for src, tok in toks:
                if not tok:
                    continue
                c["total"] += 1
                if is_placeholder(tok):
                    c["placeholder"] += 1
                    note("PLACEHOLDER", i, tok, f"含占位符（{src}）")
                    continue
                ext = external_reason(tok)
                if ext:
                    c["external"] += 1
                    note("EXTERNAL", i, tok, ext)
                    continue
                # R1b：markdown 链接的目标一律按解析判（标准语义：相对本文件），
                # 不给「系统外路径」「裸文件名」留逃生口——链接就是链接。
                if src == "link":
                    tag, hit = resolve(tok, path.parent, root)
                    if hit is None:
                        c["dead_link"] += 1
                        note("DEAD_LINK", i, tok, "markdown 链接：B1/B2 都解析不到",
                             line.strip()[:160])
                    else:
                        c["ok"] += 1
                        if hit.startswith("docs/methods/") and hit.endswith(".md"):
                            methods_here.add(Path(hit).stem)
                            c["method"] += 1
                        note("OK_LINK", i, tok, f"{tag} -> {hit}")
                    continue
                # R5/R9：单段裸文件名先判，别混进「系统外路径」
                if "/" not in tok.replace("\\", "/") and SEG_FILE.search(tok):
                    stem = tok.rsplit(".", 1)[0]
                    if stem in methods:
                        c["loose_method"] += 1
                        note("LOOSE_METHOD", i, tok,
                             "本系统确有这本书，但写成了裸文件名，照字面解析不到",
                             line.strip()[:160])
                    else:
                        c["runtime"] += 1
                        note("RUNTIME", i, tok, "产品侧裸文件名")
                    continue
                looks_path = has_file_segment(tok) or is_dir_ref(tok) or \
                    (("/" in tok.replace("\\", "/")) and
                     any(s in RUNTIME_SEGMENTS for s in segments(tok)[:1]))
                if looks_path:
                    rt = runtime_reason(tok)
                    if rt:
                        c["runtime"] += 1
                        note("RUNTIME", i, tok, rt)
                        continue
                    if not system_owned(tok):
                        c["offsite"] += 1
                        note("OFFSITE", i, tok,
                             "首段不属于本系统（下游资料/本机工具/别人的仓库）")
                        continue
                    tag, hit = resolve(tok, path.parent, root)
                    if hit is None:
                        c["dead_link"] += 1
                        note("DEAD_LINK", i, tok, "B1/B2 都解析不到", line.strip()[:160])
                    else:
                        c["ok"] += 1
                        if hit.startswith("docs/methods/") and hit.endswith(".md"):
                            methods_here.add(Path(hit).stem)
                            c["method"] += 1
                        note("OK_LINK", i, tok, f"{tag} -> {hit}")
                    continue
                if "/" in tok.replace("\\", "/") or is_dir_ref(tok):
                    c["total"] -= 1      # 有斜杠但不是路径，不计总数
                    continue
                if BOOKNAME.match(tok):
                    if tok in methods:
                        c["method"] += 1
                        c["ok"] += 1
                        methods_here.add(tok)
                        note("OK_METHOD", i, tok, "docs/methods 下真实存在")
                    elif tok in removed:
                        c["removed_book"] += 1
                        note("REMOVED_BOOK", i, tok, removed_reason.get(tok, ""),
                             line.strip()[:160])
                    else:
                        # R0c：既不是本系统方法书、旧技能库里也查无此名。
                        # 旧代码在这里直接落空（既不 note 也不计数），于是
                        # 「旧技能库路径写错」这件事在报告里完全不可见。
                        c["unclassified"] += 1
                        note("UNCLASSIFIED_BOOK", i, tok,
                             "形似书名，但既不在 docs/methods 也不在旧技能库（旧技能库不可达？）",
                             line.strip()[:160])
        per_file.append({"file": rel, **c, "methods": sorted(methods_here)})

    gaps = []
    for wf in WORKFLOWS:
        p = root / "workflows" / f"{wf}.md"
        rec = next((r for r in per_file if r["file"] == f"workflows/{wf}.md"), None)
        n = len(rec["methods"]) if rec else 0
        if rec is None:
            gaps.append({"line": wf, "methods": 0, "why": "工作流文件不存在"})
        elif n == 0:
            gaps.append({"line": wf, "methods": 0, "why": "一个方法书都没指向"})

    def pick(k):
        return [f for f in findings if f["kind"] == k]

    return {
        "root": str(root),
        # FIX-15/FIX-16：闸门把自己的分母也报出来，让「什么都没查」可判定。
        "files_scanned": len(per_file),
        "old_skills": str(old_skills),
        "old_skills_missing": not old_skills.is_dir(),
        "methods": sorted(methods),
        "removed_books": sorted(removed),
        "dead_link": pick("DEAD_LINK"),
        "loose_method": pick("LOOSE_METHOD"),
        "removed_refs": pick("REMOVED_BOOK"),
        "unclassified_refs": pick("UNCLASSIFIED_BOOK"),
        "external": pick("EXTERNAL"),
        "offsite": pick("OFFSITE"),
        "fenced_cmds": fenced_cmds,
        "gaps": gaps,
        "per_file": per_file,
        "totals": {
            "refs": sum(r["total"] for r in per_file),
            "ok": sum(r["ok"] for r in per_file),
            "method": sum(r["method"] for r in per_file),
            "runtime": sum(r["runtime"] for r in per_file),
            "placeholder": sum(r["placeholder"] for r in per_file),
            "external": sum(r["external"] for r in per_file),
            "offsite": sum(r["offsite"] for r in per_file),
            "dead_link": len(pick("DEAD_LINK")),
            "loose_method": len(pick("LOOSE_METHOD")),
            "removed_book": len(pick("REMOVED_BOOK")),
            "unclassified_book": len(pick("UNCLASSIFIED_BOOK")),
        },
    }

def report(res: dict) -> None:
    t = res["totals"]
    print(f"被检树 = {res['root']}")
    print(f"扫描面 = {res['files_scanned']} 个文件，收集到 {t['refs']} 条引用"
          f"（分母为空 = 闸门没跑起来，退出码会是 2）")
    print(f"旧技能库 = {res['old_skills']}")
    if res["old_skills_missing"]:
        print("[告警] 旧技能库不可达 —— REMOVED_BOOK 桶不完整，"
              "被移出的书会全掉进下面的「未分类」一节。请用 --old-skills 指到真实技能目录。")
    print(f"docs/methods 现有方法书 {len(res['methods'])} 本：{', '.join(res['methods'])}")
    print(f"旧技能目录里没搬进来的名字 {len(res['removed_books'])} 个 = 本系统故意不带的能力：{', '.join(res['removed_books'])}")
    print("=" * 120)
    print(f"{'文件':<44}{'引用':>5}{'通过':>5}{'指向书':>7}{'占位':>5}{'运行期':>7}"
          f"{'安装根':>7}{'系统外':>7}{'死链':>5}{'写法错':>7}{'移出书':>7}")
    print("-" * 120)
    for r in res["per_file"]:
        print(f"{r['file']:<44}{r['total']:>5}{r['ok']:>5}{r['method']:>7}{r['placeholder']:>5}"
              f"{r['runtime']:>7}{r['external']:>7}{r['offsite']:>7}{r['dead_link']:>5}"
              f"{r['loose_method']:>7}{r['removed_book']:>7}")
    print("-" * 120)
    print(f"{'合计':<44}{t['refs']:>5}{t['ok']:>5}{t['method']:>7}{t['placeholder']:>5}"
          f"{t['runtime']:>5}{t['external']:>5}{t['offsite']:>5}{t['dead_link']:>5}"
          f"{t['loose_method']:>7}{t['removed_book']:>7}")
    print()
    print("== 真死链 A：本系统内路径解析不到（必须修）==")
    if not res["dead_link"]:
        print("  无。")
    for f in res["dead_link"]:
        print(f"  DEAD_LINK    {f['file']}:{f['line']}  `{f['token']}`")
        print(f"               ← {f.get('text','')}")
    print()
    print("== 真死链 B：方法书写成了裸文件名，写法要修 ==")
    if not res["loose_method"]:
        print("  无。")
    for f in res["loose_method"]:
        print(f"  LOOSE_METHOD {f['file']}:{f['line']}  `{f['token']}`")
    print()
    print("== 本系统故意不带的能力（不是死链，单独列）==")
    if not res["removed_refs"]:
        print("  正文里没有再点名任何被移出的书。")
    for f in res["removed_refs"]:
        print(f"  REMOVED      {f['file']}:{f['line']}  `{f['token']}`  {f['why']}")
    print()
    print("== 未分类的裸书名（既不在方法书、也不在旧技能库；要人看一眼）==")
    if not res["unclassified_refs"]:
        print("  无。")
    uc: dict[str, int] = {}
    for f in res["unclassified_refs"]:
        uc[f["token"]] = uc.get(f["token"], 0) + 1
    for k, n in sorted(uc.items(), key=lambda kv: (-kv[1], kv[0])):
        where = [f"{f['file']}:{f['line']}" for f in res["unclassified_refs"]
                 if f["token"] == k][:4]
        print(f"  UNCLASSIFIED `{k}`  ×{n}  首次出现在 {'、'.join(where)}")
    print("== 无书可开（最严重）==")
    if not res["gaps"]:
        print("  无。六条线都至少指向一本本系统真实存在的方法书。")
    for g in res["gaps"]:
        print(f"  GAP          {g['line']}  指向方法书 0 本 —— {g['why']}")
    print()
    print("== 安装根 / 运行期脚本引用（不是本树死链，待主人拍板）==")
    seen: dict[str, int] = {}
    for e in res["external"]:
        seen[e["token"]] = seen.get(e["token"], 0) + 1
    fseen: dict[str, int] = {}
    for e in res["fenced_cmds"]:
        fseen[e["token"]] = fseen.get(e["token"], 0) + 1
    if not seen and not fseen:
        print("  无。")
    for k, n in sorted(seen.items()):
        print(f"  EXTERNAL(行内) `{k}`  ×{n}")
    for k, n in sorted(fseen.items()):
        print(f"  EXTERNAL(围栏) `{k}`  ×{n}")
    print()
    print("== 系统外路径（下游资料/本机工具/别人的仓库，不是本树死链）==")
    oseen: dict[str, int] = {}
    for e in res["offsite"]:
        oseen[e["token"]] = oseen.get(e["token"], 0) + 1
    if not oseen:
        print("  无。")
    for k, n in sorted(oseen.items()):
        print(f"  OFFSITE      `{k}`  ×{n}")
    print()
    print(f"判定：真死链 {t['dead_link'] + t['loose_method']} 处"
          f"（路径解析不到 {t['dead_link']} + 写法错 {t['loose_method']}），"
          f"故意不带的能力被点名 {t['removed_book']} 处，"
          f"未分类裸书名 {t['unclassified_book']} 处，"
          f"无书可开的线 {len(res['gaps'])} 条。")

def main(argv: list[str] | None = None) -> int:
    # Windows 控制台默认不是 UTF-8，输出重定向到文件时会变乱码
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="02-hubcore 死链/死引用/能力缺口校验")
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--old-skills", default=None,
                    help="旧技能库目录（缺省按 OLD_SKILLS_CANDIDATES 探测）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"[错误] 被检树不存在：{root}", file=sys.stderr)
        return 2
    old_skills, old_ok = resolve_old_skills(a.old_skills)
    res = check(root, old_skills)
    # FIX-15 R0a：闸门自己的分母不许是空。「扫了 0 个文件」和「扫了、零死链」
    # 都会让下面那行 return 0 —— 旧代码把前者也判成了绿灯。
    if res["files_scanned"] == 0:
        print(f"[错误] 收集面为空：{root} 下既没有 workflows/*.md，也没有 docs/**/*.md，"
              "也没有 AGENTS.md。这次什么都没查，不能判通过。", file=sys.stderr)
        return 2
    if res["totals"]["refs"] == 0:
        print(f"[错误] 扫了 {res['files_scanned']} 个文件、收到 0 条引用 —— "
              "收集正则失效，闸门没真正跑起来。", file=sys.stderr)
        return 2
    # FIX-16 R0b：旧技能库不可达时 REMOVED_BOOK 桶不完整，必须让人看见。
    if not old_ok:
        print(f"[告警] 旧技能库不可达：{old_skills}\n"
              "       REMOVED_BOOK 桶不完整；被移出的技能书会落进「未分类」一节。\n"
              "       用 --old-skills 指到真实技能目录可消除此告警。", file=sys.stderr)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        report(res)
    return 0 if not res["dead_link"] and not res["loose_method"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
