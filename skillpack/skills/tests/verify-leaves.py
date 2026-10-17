#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify-leaves.py —— 逐**叶子**核验：树干只是骨架，要保证的是**每一片叶子都是通的**。

主人 2026-10-16 的原话（这就是本脚本存在的全部理由）
--------------------------------------------------
「你要把树状图做好，那些层是**树干**，然后各个树干上还有很多**树杈**，非常多。
  你要的就是保证**每一个树杈都是通的**。…然后**不停地去核验各个树杈是不是通的**。」

什么叫「树杈通」
--------------
一片叶子（一个 md、一个脚本、一个模板）**通** = 它从入口**真的能被走到**：
  · 知识库的 473 篇 `references/*.md`：至少被 KB-INDEX（现象索引）或所属 SKILL.md 引用
  · 技能/契约的脚本与模板：至少被某个 SKILL.md / 脚本 / 门禁引用
  · KB-INDEX 里的每一行「现象 → 文档」：目标文件真实存在
  · 技能卡引用的相对路径（反引号里的 `scripts/x.py`、`references/y.md`）：真实存在
反过来，**存在但没有任何入口指向它 = 断掉的树杈**（模型永远走不到）。
这就是 `verify-doc-links.py` 看不到的那一半：它只查「链接指向的东西在不在」，
不查「在的东西有没有入口」。

用法
----
    python skills/tests/verify-leaves.py                    # 全量
    python skills/tests/verify-leaves.py --trunk references # 只看某个树干
    python skills/tests/verify-leaves.py --json
退出码：0 没有断链（或只有已登记的）；1 有断链。
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent
REPO = SKILLS.parent.parent

SKIP_PARTS = {"_归档-禁读-历史文档", "work", "community-raw", "node_modules",
              "__pycache__", ".git", "_history", "_archive", "_snapshots"}

# ★ 已判定为「按需、不接入口」的叶子。**登记在案、每次运行都报出来**（不静默放行）
#   —— 项目自己的规矩：偏离必须登记 + 每次大声报出，否则就是个"偷偷放行"。
ALLOWED_NO_ENTRY = {
    "skillpack/skills/browser-automation/scripts/setup.ps1":
        "内核禁令拦下（kernel/02-hubcore/docs/methods/reverse-engineering.md:43「不跑 vendor 安装脚本」；"
        "kernel/03-bundle/patches/DEAD-REFS.md:183 归为「禁令里的名字，不是活指针」）→ 按需，不接入口",
}

_REPO_RESOLVED = REPO.resolve()

# ★ 2026-10-17：**约定根**。`docs/KNOWN-BOUNDARIES.md` 第 10 条明写：`C:\relab2` 与 `D:\Tools`
#   是主人定死的约定路径，文档/技能卡里写它们**不是缺陷**（`scan-defect-classes.py` 的 D3
#   已把它们加进白名单）。这里做同一件事：把以约定根开头的引用**归一成仓内相对路径**再判存在 ——
#   否则在「换机 / 发布包 / CI runner」这些**仓根不在 `C:\relab2`** 的地方，这些引用会被
#   整片误判成断叶（实测在无 `.git` 的发布副本里 50 片）。
_CONVENTION_ROOTS = ("c:\\relab2", "c:/relab2")


def _skip(p) -> bool:
    """按**仓库相对**的路径段判断是否跳过。

    ★ 2026-10-17：以前按**绝对路径**的段比 —— 而 GitHub runner 的检出目录是
      `/home/runner/work/relab2/relab2`，里面**有一个叫 `work` 的目录段**。
      `work` 在 SKIP_PARTS 里（指的是仓内那个运行时目录），于是 CI 上**每个文件都被跳过**：
      `_files()` 全返回空 → 0 片叶子 / 0 片断 → 门报 PASS。
      也就是说这道门在 CI 上从来没真扫过（假绿），而路径里没有 `work` 段的地方
      （例如无 .git 的副本）才真的扫 —— 同一个提交两处结论不同。
      修法：只比**相对仓根**的段（与 verify-powershell-syntax.py 2026-10-17 的修法同源）。
    """
    try:
        rel = Path(p).resolve().relative_to(_REPO_RESOLVED)
    except (ValueError, OSError):
        rel = Path(p)
    return bool(set(rel.parts) & SKIP_PARTS)


def _read(p) -> str:
    try:
        return io.open(p, encoding="utf-8-sig", errors="replace").read()
    except OSError:
        return ""


def _files(patterns, root=REPO):
    out = []
    for pat in patterns:
        # ★ 2026-10-16：`glob` **默认不匹配以 `.` 开头的目录** —— 于是 `.github/workflows/*.yml`
        #   一直返回空列表（实测 0 个），被 CI 直接 run 的脚本因此全成了"假断叶"。
        #   Python 3.11+ 用 include_hidden=True。
        for f in glob.glob(str(Path(root) / pat), recursive=True, include_hidden=True):
            if _skip(f):
                continue
            out.append(Path(f))
    return sorted(set(out))


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(p)


# ---------------------------------------------------------------- 引用抽取
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
# 正斜杠与**反斜杠**都要认（`C:\relab2\...\scripts\x.py`、`..\scripts\lib\Bootstrap.ps1`）
BACKTICK_PATH_RE = re.compile(
    r"`([^`\n]*?(?:references|scripts|templates|schemas|ops)[\\/][^`\n]*?\.(?:md|py|ps1|json|yaml|yml))`")
# 脚本里指路径的几种写法（子代理实测漏抽的那些）
CODE_PATH_RE = re.compile(
    r"(?:Join-Path\s+\$PSScriptRoot\s+['\"]([^'\"]+)['\"])"          # PowerShell 拼路径
    r"|(?:importlib[^\n]*?['\"]([a-z0-9_./-]+\.py)['\"])"              # importlib 字符串
    r"|(?:^\s*run:\s*.*?((?:skills|skillpack)[\\/][^\s|>]*\.(?:py|ps1)))", re.M)
# ★ 2026-10-16：workflow 的 `run: |` 是**多行块**，路径不带 `run:` 前缀；脚本里也常把路径
#   拼在命令行里。所以补一条通用规则：文本里出现的任何 `skillpack/skills/.../x.py|ps1` 都算引用。
BARE_PATH_RE = re.compile(r"((?:skillpack[/\\])?skills[/\\][^\s'\"|>)\]]*?\.(?:py|ps1))")


_CMD_PREFIX_RE = re.compile(
    r"^(?:python3?|powershell|pwsh|node|cmd|\. |& |>\s*|-File\s+|--file\s+|call\s+|start\s+)+", re.I)


def _clean_path(t: str) -> str:
    """把「命令行里的一段」剥成纯路径。

    ★ 2026-10-16：第一版直接拿反引号里的整串当路径，于是
      `python skillpack/skills/scripts/x.py` 与 PowerShell 的 `. ../scripts/lib/Bootstrap.ps1`
      全被当成"目标不存在"——那是**抽取器的误报**，不是项目断链。判据要认命令形态。
    """
    t = _CMD_PREFIX_RE.sub("", t.strip())
    if " " in t:
        t = t.split()[0]
    t = t.strip().strip("\"'")
    if t.startswith("-"):        # `-NoProfile` 这类命令行开关不是路径
        return ""
    return t


def referenced_targets(src: Path) -> list[tuple[str, int]]:
    """从一份文档里抽出它引用的仓内**相对路径** -> [(目标原文, 行号)]。"""
    out = []
    txt = _read(src)
    for i, line in enumerate(txt.splitlines(), 1):
        for m in LINK_RE.finditer(line):
            t = m.group(1).strip()
            if re.match(r"^(https?:|mailto:|tel:|ftp:|data:|#)", t):
                continue
            t = t.split("#")[0]
            if t:
                out.append((t, i))
        for m in BACKTICK_PATH_RE.finditer(line):
            t = _clean_path(m.group(1))
            if t:
                out.append((t, i))
        for m in CODE_PATH_RE.finditer(line):
            g = next((x for x in m.groups() if x), "")
            if g:
                out.append((g.strip(), i))
        for m in BARE_PATH_RE.finditer(line):
            out.append((m.group(1), i))
    return out


def resolve_rel(src: Path, target: str) -> Path | None:
    """把引用解析成绝对路径。

    ★ 2026-10-16 子代理实测补齐：候选基里**必须有 `SKILLS.parent`（= skillpack/）**。
      仓库的内容根是 `skillpack/`：`ci-gates.json` 的 `script` 字段、以及文档里大量的
      `skills/scripts/x.py` 都相对它；少了这个基，40 条门禁路径全被解析成
      `skillpack/skills/skills/scripts/x.py`（exists=False）→ 假断一大片。
    """
    t = target.replace("\\", "/").strip()
    # ★ 约定根归一化（见 _CONVENTION_ROOTS 注释）：`C:\relab2\skillpack\...` → `skillpack/...`
    low = t.lower()
    for root in _CONVENTION_ROOTS:
        root_fwd = root.replace("\\", "/")
        if low.startswith(root_fwd):
            t = t[len(root_fwd):].lstrip("/")
            break
    for cand in (src.parent / t, REPO / t, SKILLS / t, SKILLS.parent / t):
        try:
            if cand.exists():
                return cand.resolve()
        except OSError:
            continue
    return None


# ---------------------------------------------------------------- 各树干
def trunk_references():
    """树干：references 技术正文（知识库正文）。断 = 没有任何入口指向它。"""
    files = _files(["skillpack/skills/**/references/**/*.md"])
    inbound: dict[str, list[str]] = {_rel(f): [] for f in files}
    # 收集所有引用的目标
    sources = _files(["skillpack/skills/**/*.md", "docs/**/*.md", "kernel/**/*.md", "*.md",
                      ".github/workflows/*.yml", "skillpack/skills/**/*.py", "skillpack/skills/**/*.ps1",
                      "skillpack/docs/**/*.md", "skillpack/tests/**/*.py", "skillpack/scripts/**/*.py"])
    for s in sources:
        for t, ln in referenced_targets(s):
            rp = resolve_rel(s, t)
            if rp is None:
                continue
            k = _rel(rp)
            if k in inbound and _rel(s) != k:
                inbound[k].append(f"{_rel(s)}:{ln}")
    broken = [(k, v) for k, v in inbound.items() if not v]
    return {"trunk": "references", "leaves": len(files),
            "linked": len(files) - len(broken), "broken": len(broken),
            "detail": [(k, "没有任何入口引用它（模型按现象查不到）") for k, _ in broken]}


def trunk_scripts():
    """树干：技能包脚本。断 = 没有任何文档/门禁/脚本引用它（可能已被淘汰却还挂着）。"""
    files = _files(["skillpack/skills/**/scripts/*.py", "skillpack/skills/**/scripts/*.ps1"])
    refs = set()
    # 引用源要**包括脚本自己**：`. ..\scripts\lib\Bootstrap.ps1`（dot-source）与
    # `from x import` / `importlib` 都算"有入口"；只扫 md 会把这些误判成孤儿。
    for s in _files(["skillpack/skills/**/*.md", "skillpack/skills/**/*.ps1",
                     "skillpack/skills/**/*.py", "skillpack/skills/tests/ci-gates.json",
                     "*.md", "relab2.ps1", "docs/**/*.md", "skillpack/docs/**/*.md",
                     "skillpack/tests/**/*.py", "skillpack/scripts/**/*.py",
                     ".github/workflows/*.yml"]):
        for t, _ in referenced_targets(s):
            rp = resolve_rel(s, t)
            if rp:
                refs.add(_rel(rp))
        # 门禁清单里的 script 字段
        # 门禁清单里的 script 字段（**相对 skillpack/**，不是相对 skills/ —— 同一个坑）
        if s.name == "ci-gates.json":
            try:
                d = json.loads(_read(s))
                for g in d.get("gates", []):
                    p = SKILLS.parent / str(g.get("script", ""))
                    if p.is_file():
                        refs.add(_rel(p))
            except ValueError as e:
                # ★ 2026-10-16（D5）：解析失败原来静默 —— 门禁脚本会被当成"没人引用"，
                #   于是 verify-leaves 可能报出一批假 broken（或者反过来漏掉真 broken）。
                print(f"[warn] {s.name} 解析失败，门禁 script 引用未收录：{e}", file=sys.stderr)
    broken = [_rel(f) for f in files if _rel(f) not in refs and _rel(f) not in ALLOWED_NO_ENTRY]
    allowed = [_rel(f) for f in files if _rel(f) not in refs and _rel(f) in ALLOWED_NO_ENTRY]
    return {"trunk": "scripts", "leaves": len(files), "allowed": allowed,
            "linked": len(files) - len(broken) - len(allowed),
            "broken": len(broken),
            "detail": [(b, "没有任何文档/门禁引用它") for b in broken]}


def trunk_contracts():
    """树干：templates / schemas / ops。断 = 存在但没有任何入口。"""
    files = _files(["skillpack/skills/templates/**/*", "skillpack/schemas/**/*",
                    "skillpack/skills/ops/**/*.md"])
    files = [f for f in files if f.is_file()]
    refs = set()
    for s in _files(["skillpack/skills/**/*.md", "skillpack/skills/**/*.py", "*.md"]):
        for t, _ in referenced_targets(s):
            rp = resolve_rel(s, t)
            if rp:
                refs.add(_rel(rp))
    broken = [_rel(f) for f in files if _rel(f) not in refs]
    return {"trunk": "contracts(templates/schemas/ops)", "leaves": len(files),
            "linked": len(files) - len(broken), "broken": len(broken),
            "detail": [(b, "没有任何入口引用它") for b in broken]}


def trunk_kb_index():
    """树干：KB-INDEX 的「现象 → 文档」每一行。断 = 目标文件不存在。"""
    idx = SKILLS / "field-journal" / "KB-INDEX.md"
    txt = _read(idx)
    bad = []
    total = 0
    for i, line in enumerate(txt.splitlines(), 1):
        for m in LINK_RE.finditer(line):
            t = m.group(1).split("#")[0].strip()
            if not t or re.match(r"^(https?:|#)", t):
                continue
            total += 1
            if resolve_rel(idx, t) is None:
                bad.append((f"skillpack/skills/field-journal/KB-INDEX.md:{i}", f"→ {t} 不存在"))
    return {"trunk": "kb-index 现象行", "leaves": total, "linked": total - len(bad),
            "broken": len(bad), "detail": bad}


def trunk_card_refs():
    """树干：每张 SKILL.md 里引用的相对路径。断 = 目标真不存在。

    ★ 2026-10-16 三轮降噪（每一条都是我自己抽错，不是项目断链）：
      ① 命令前缀（`python <path>`、PowerShell 的 `. <path>`）要剥掉；
      ② **跨卡引用**：卡里常写「`../js-reverse/` 的 `references/x.md`」——
         目标在本卡下不存在，但在**兄弟技能卡**里唯一存在 → 可达；
      ③ **已声明的缺件**：文档写了「上游 `scripts/x.py` … 本次未随包落地」，
         那是在**如实说明**，不是断链。
    """
    bad = []
    total = 0
    for card in _files(["skillpack/skills/**/SKILL.md"]):
        for ln, line in enumerate(_read(card).splitlines(), 1):
            for t, _ in [(t, ln) for t, l2 in referenced_targets(card) if l2 == ln]:
                t2 = t.split("#")[0]
                if not t2 or re.match(r"^(https?:|#)", t2):
                    continue
                total += 1
                if resolve_rel(card, t2) is not None:
                    continue
                # ② 跨卡：兄弟技能卡里存在同名目标即可达（多个同名则算有歧义但不判断）
                # ★ 2026-10-18：**反斜杠必须先归一成 `/`**。
                #   卡里写的路径有 Windows 风格（`skillpack\skills\x64dbg-reverse\...`），
                #   在 POSIX 上 `\` 不是分隔符 —— `Path(t2).name` 会返回整串，
                #   `SKILLS.glob(f"*/{t2}")` 也匹配不到任何东西，于是同一份文档
                #   在 Windows 上「有入口」、在 ubuntu CI 上「断了」。
                #   实测：同一 commit，本机 1911 叶 0 断；CI `verify-leaves` exit 1（blocked）。
                t2_posix = t2.replace("\\", "/")
                name = t2_posix.rsplit("/", 1)[-1]
                # ★ 2026-10-17：**单条怪引用不许把整道门弄崩**。
                #   实测：文档里写了 `references/**.md`（本意是"references 下的 .md"），
                #   抽取器把它当路径 → `glob("*/references/**.md")` ——
                #   而 Python 3.12 的 pathlib 对「`**` 不单独成段」的模式抛
                #   `ValueError: Invalid pattern: '**' can only be an entire path component`。
                #   后果：整道门在 CI（py3.12）上 traceback 崩掉、exit 1，
                #   而本机（py3.14，pathlib 已支持 `**` 任意位置）完全看不出来。
                #   glob 失败就当"没有兄弟"处理（该引用照旧按断叶判），而不是崩门。
                try:
                    sib = [p for p in SKILLS.glob(f"*/{t2_posix}") if p.is_file()]
                    sib += [p for p in SKILLS.glob(f"*/**/{name}") if p.is_file()]
                except (ValueError, OSError):
                    sib = []
                if sib:
                    continue
                # ③ 已声明未落地
                if re.search(r"未随包|未随包落地|上游|不提供其调用方式|自行实现|不在本包", line):
                    continue
                bad.append((f"{_rel(card)}:{ln}", f"→ {t2} 不存在（也不是跨卡引用 / 未标注未落地）"))
    # 去重（同一行多次命中同一目标）
    seen, uniq = set(), []
    for b in bad:
        if b[0] in seen:
            continue
        seen.add(b[0])
        uniq.append(b)
    return {"trunk": "技能卡内引用", "leaves": total, "linked": total - len(uniq),
            "broken": len(uniq), "detail": uniq}


TRUNKS = {"references": trunk_references, "scripts": trunk_scripts,
          "contracts": trunk_contracts, "kb-index": trunk_kb_index, "card-refs": trunk_card_refs}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trunk", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-show", type=int, default=15)
    # ★ 2026-10-16 加 `--write-doc`（照 feature-graph.py:369）：PS 5.1 的裸 `>` 写 UTF-16LE，
    #   会把 `docs/_snapshots/*.md`（UTF-8/LF）毁掉 —— 让脚本自己写字节是唯一干净修法。
    ap.add_argument("--write-doc", default="", metavar="PATH",
                    help="把正文写入该文件（UTF-8/LF），而不是打印到 stdout")
    a = ap.parse_args()

    names = [a.trunk] if a.trunk else list(TRUNKS)
    res = []
    for n in names:
        fn = TRUNKS.get(n)
        if not fn:
            print(f"未知树干 {n}；可选：{', '.join(TRUNKS)}")
            return 2
        res.append(fn())

    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 1 if any(r["broken"] for r in res) else 0

    tot_l = tot_b = 0
    _old_stdout, _fh = None, None
    if a.write_doc:
        _out = Path(a.write_doc)
        _out.parent.mkdir(parents=True, exist_ok=True)
        _fh = io.open(_out, "w", encoding="utf-8", newline="\n")
        _old_stdout, sys.stdout = sys.stdout, _fh
    print("逐树杈核验（叶子 = 能被真的走到）")
    print("=" * 72)
    for r in res:
        tot_l += r["leaves"]
        tot_b += r["broken"]
        flag = "通" if r["broken"] == 0 else f"断 {r['broken']}"
        print(f"[{r['trunk']:<28}] 叶子 {r['leaves']:>4} · 有入口 {r['linked']:>4} · {flag}")
        for f, why in r["detail"][:a.max_show]:
            print(f"      {f}")
            print(f"        {why}")
        if len(r["detail"]) > a.max_show:
            print(f"      … 另有 {len(r['detail']) - a.max_show} 片（--max-show N 看全）")
    print()
    print(f"合计叶子 {tot_l} 片，其中 {tot_b} 片断了入口。")
    # ★ 2026-10-17：**扫到 0 片叶子必须判红**。原实现只在「有断叶」时返回 1，
    #   于是「一片都没扫到」（路径算错 / 排除规则误伤整个仓 / 布局变了）会静默报绿 ——
    #   本仓反复出现的一类假绿（门早就不检查了，但汇总数字一样好看）。
    #   实测踩过：CI 检出目录 `/home/runner/work/relab2/relab2` 里有 `work` 段，
    #   被 SKIP_PARTS 命中 → 全仓被跳过 → 0 片叶子 → PASS。
    #   只在**全量**运行时判（`--trunk` 单选某个树干时它本来就可能是 0）。
    if not a.trunk and tot_l == 0:
        print("FAIL：一片叶子都没扫到 —— 本仓不可能没有叶子，说明扫描根或排除规则算错了", file=sys.stderr)
        if _fh is not None:
            _fh.close()
            sys.stdout = _old_stdout
        return 1
    if _fh is not None:
        _fh.close()
        sys.stdout = _old_stdout
        print(f"已落档：{a.write_doc}（UTF-8/LF）")
    return 1 if tot_b else 0


if __name__ == "__main__":
    sys.exit(main())
