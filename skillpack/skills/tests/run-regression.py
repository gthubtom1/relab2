#!/usr/bin/env python3
"""run-regression.py —— 失败→技能回归表（L2.1）的门

背景：
    本包此前 26 个门全是格式/一致性门，**0 个行为门**。结果是「每次说改好了、
    下次真实做又出问题」—— 因为「改好了」只能验形状，不能验行为。
    这张表是打破循环的机械核心：每个真实项目留一条 case，记录
    「期望链路」与「这次实际卡在哪」。

本门做四件事（都不需要模型调用，所以能进 CI）：
    1. 每条 case 的必填字段是否齐全
    2. `expect_chain` 里引用的技能/文档是否真实存在（防悬空承诺）
    3. `known_failures` 是否为空 —— 空的必须显式写"正控/无"的说明（防假填）
    4. 统计 open / resolved，报出未收敛的失败数

模型驱动的行为门（`test-routing-e2e` / `test-trigger-rate` / `test-assault-behavior`）
在 L2.2，它们要花模型调用，挂 non-blocking 先跑数。

用法：
    python skills/tests/run-regression.py [--json] [--strict]
退出码：0 通过 / 1 有违规（--strict 时 open case 也算违规）
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

CASES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cases")
REQUIRED = ("id", "date", "domain", "task_verbatim", "expect_chain",
            "expect_deliverable", "known_failures", "status")
VALID_STATUS = ("open", "resolved")
# 允许 known_failures 为空的显式声明（防假填）
EMPTY_OK_RE = re.compile(r"无（|无\s*$|正控|示例案例|positive control")


def find_repo_root() -> str:
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "skillpack", "skills")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return os.getcwd()


_TRACKED_CACHE: set[str] | None = None
_TRACKED_DIRS: set[str] | None = None


def _tracked_sets(repo_root: str):
    """(跟踪文件集合, 跟踪目录集合)，仓库相对、正斜杠。

    ★ 2026-10-17：引用解析改为**优先按 git 跟踪的文件**判存在，而不是工作树。
    起因：`case-002-prng-upx.yaml` 的 lesson_refs 指向
    `work/assault-prng-upx/assault.md` —— 那是 `.gitignore` 掉的运行时工作区，
    **开发机上存在、全新 clone 里不存在**。于是这道门在开发机绿、在 CI 红
    （`FAIL（1 条）`，且日志只印了那句汇总，看不到是哪一条）。
    按跟踪集合判，两边一致。git 不可用（tarball 解包等）时返回空集合，
    调用方回退到 os.path.exists —— 保持旧行为而不是让整门炸掉。
    """
    global _TRACKED_CACHE, _TRACKED_DIRS
    if _TRACKED_CACHE is not None:
        return _TRACKED_CACHE, _TRACKED_DIRS
    files: set[str] = set()
    try:
        out = subprocess.run(["git", "-C", repo_root, "ls-files", "-z"],
                             capture_output=True, check=False, timeout=120).stdout
        files = {x.decode("utf-8").replace("\\", "/")
                 for x in out.split(b"\0") if x}
    except (OSError, subprocess.SubprocessError):
        files = set()
    dirs: set[str] = set()
    for t in files:
        parts = t.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))
    _TRACKED_CACHE, _TRACKED_DIRS = files, dirs
    return files, dirs


def _tracked_candidates(e: str) -> list[str]:
    """一个引用可能对应的仓库相对路径（按解析顺序）。"""
    cands = []
    for base in ("skillpack/skills/", "", "skillpack/"):
        cands.append((base + e.replace("\\", "/")).lstrip("/"))
    if "/" not in e:
        cands.append("skillpack/skills/%s/SKILL.md" % e)
    return cands


def chain_entry_exists(entry: str, repo_root: str, skills_root: str) -> bool:
    """expect_chain 的一条是否指向真实存在的技能目录或文档。"""
    e = entry.strip()
    if not e:
        return False
    files, dirs = _tracked_sets(repo_root)
    if files:
        for c in _tracked_candidates(e):
            if c in files or c in dirs:
                return True
        return False
    if e in ("ctf-sandbox", "pwn-chain", "docs-generator", "case-review",
             "reverse-engineering", "x64dbg-reverse", "ida-reverse",
             "ghidra-reverse", "radare2", "apk-reverse", "malware-analysis"):
        if os.path.isfile(os.path.join(skills_root, e, "SKILL.md")):
            return True
    for base in (skills_root, repo_root, os.path.join(repo_root, "skillpack")):
        if os.path.exists(os.path.join(base, e.replace("/", os.sep))):
            return True
    # 纯技能名（无斜杠）也接受
    if "/" not in e and os.path.isfile(os.path.join(skills_root, e, "SKILL.md")):
        return True
    return False


def load_cases() -> tuple[list[dict], list[str]]:
    cases, errs = [], []
    if not os.path.isdir(CASES_DIR):
        return cases, [f"cases 目录不存在: {CASES_DIR}"]
    for fn in sorted(os.listdir(CASES_DIR)):
        if not fn.endswith((".yaml", ".yml")):
            continue
        p = os.path.join(CASES_DIR, fn)
        if yaml is None:
            errs.append(f"{fn} :: 需要 PyYAML（pip install pyyaml）")
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
        cases.append(doc)
    return cases, errs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="open case 也判为违规（用于「彻底完成」验收时刻）")
    args = ap.parse_args()

    repo_root = find_repo_root()
    skills_root = os.path.join(repo_root, "skillpack", "skills")

    cases, errs = load_cases()
    if not cases and not errs:
        print("run-regression: FAIL（cases/ 里一条 case 都没有 —— 回归表是空的，等于没有）")
        return 1

    for c in cases:
        fn = c.get("_file", "?")
        for k in REQUIRED:
            if k not in c or c[k] in (None, "", []):
                if k == "known_failures" and k in c:
                    pass  # 单独判
                else:
                    errs.append(f"{fn} :: 缺必填字段 `{k}`")

        st = str(c.get("status", "")).strip()
        if st and st not in VALID_STATUS:
            errs.append(f"{fn} :: status={st!r} 不在 {VALID_STATUS}")

        chain = c.get("expect_chain") or []
        if not isinstance(chain, list):
            errs.append(f"{fn} :: expect_chain 必须是列表")
        else:
            for e in chain:
                if not chain_entry_exists(str(e), repo_root, skills_root):
                    errs.append(f"{fn} :: expect_chain 引用了不存在的目标：{e!r}（悬空承诺）")

        kf = c.get("known_failures") or []
        if not isinstance(kf, list):
            errs.append(f"{fn} :: known_failures 必须是列表")
            kf = []
        if not kf:
            blob = json.dumps(c, ensure_ascii=False)
            if not EMPTY_OK_RE.search(str(c.get("note", "")) + str(c.get("expect_deliverable", ""))):
                errs.append(f"{fn} :: known_failures 为空且未显式声明「无/正控」—— "
                            f"防假填（真实项目几乎不可能零失败）")

        for f in kf:
            if not isinstance(f, str) or len(str(f).strip()) < 8:
                errs.append(f"{fn} :: known_failures 有一条过短（<8 字符），像占位符：{f!r}")

    # ★ 2026-10-16 新增：id 唯一 + 文件名与 id 一致。
    #   起因：两个代理并行写 case，各自都用了 `case-004` / `case-005` —— **两条 case 同 id，
    #   本门却静默 PASS**（旧实现从不看 id，只把它当必填字段）。回归表是"每条 case 一个身份"，
    #   重号等于两条真实经历挤进一个身份，检索/对照/统计全部失真。文件名与 id 也要一致，
    #   否则按文件名找 case 和按 id 找 case 会指向不同东西。
    seen_ids: dict[str, str] = {}
    for c in cases:
        fn = c.get("_file", "?")
        cid = str(c.get("id", "")).strip()
        if not cid:
            continue
        if cid in seen_ids:
            errs.append(f"{fn} :: id={cid!r} 与 {seen_ids[cid]} 重复（每条 case 必须有唯一身份）")
        else:
            seen_ids[cid] = fn
        if os.path.splitext(fn)[0] != cid:
            errs.append(f"{fn} :: 文件名与 id 不一致（id={cid!r}）—— 按文件名找与按 id 找会指向不同东西")

    # ★ 2026-10-16 新增：lesson_refs 不许悬空。
    #   起因：本门一直只校验 `expect_chain`（"下次该走到哪"），**从不校验 `lesson_refs`** ——
    #   而后者同样是承诺（"这条经验是从哪来的"）。实测抓到 case-002 写着
    #   `field-journal/seed-005 等 seed 系列（正控语料）`，而 `seed-005` 真名是
    #   `seed-005_ad-certipy-esc1.md`（ADCS ESC1，与本 case 的 PRNG/UPX 无关），
    #   全 17 篇 seed 里 grep `upx|prng|加壳` 零命中 —— 一条**没有对应文件的"经验来源"**。
    #   判据比 expect_chain 宽：允许"路径（说明）"、`:行号`、`；` 分隔多条、泛指词跳过。
    #   ★ 外部引用（另一台机器/另一个仓库的绝对路径）**必须显式标 `[外部]`** 才跳过：
    #     本仓确实有几条 case 的经验来自已归档的外部项目报告，那些路径在本仓永远不存在。
    #     但**不静默跳过** —— 不标就 FAIL，否则打错字的外部位路径会混进来当"已核验"。
    GENERIC_REF_RE = re.compile(r"(等\s*\S*\s*系列|示例|同上|见上|待补)")
    EXT_RE = re.compile(r"^\s*(\[外部\]|【外部】)")
    # ★ 2026-10-17：与 `[外部]` 同构的第二类显式标记 —— **本机运行时产物（不入库）**。
    #   起因：case-002 的一条经验来自 `work/assault-prng-upx/assault.md`（该 case 自己的
    #   攻坚工作区）。`work/` 被 .gitignore 挡住、永不进仓 —— 引它是**有意的**，
    #   但它在新 clone 里必然不存在。原来只认 `[外部]`，于是这条引用在 CI 上判悬空
    #   （开发机上因为有那个目录反而是绿的）。不静默跳过：不标就 FAIL。
    WS_RE = re.compile(r"^\s*(\[未入库\]|【未入库】)")
    ABS_RE = re.compile(r"^([A-Za-z]:[\\/]|\\\\)")

    def _ref_resolvable(part: str) -> bool:
        """把一条引用里可能夹着的说明/小节/范围后缀剥掉，再判是否存在。"""
        cands = [part]
        for sep in (" §", "（", "(", " ~", " ／", " / ", "：", ":"):
            cands.append(part.split(sep)[0])
        # "ops/x.md R2 / R4* / R43（说明）" → 取第一个空格前的路径
        if " " in part:
            cands.append(part.split(" ")[0])
        for c in cands:
            c = c.strip().strip("\"'")
            c = re.sub(r":\d+$", "", c)
            if c and chain_entry_exists(c, repo_root, skills_root):
                return True
        return False

    for c in cases:
        fn = c.get("_file", "?")
        refs = c.get("lesson_refs") or []
        if isinstance(refs, str):
            refs = [refs]
        if not isinstance(refs, list):
            errs.append(f"{fn} :: lesson_refs 必须是列表")
            continue
        for r in refs:
            for part in re.split(r"[；;]", str(r)):
                raw = str(part).strip()
                if not raw or GENERIC_REF_RE.search(raw):
                    continue
                if EXT_RE.match(raw):
                    continue          # 显式标记的外部引用：接受（换机不可解析）
                if WS_RE.match(raw):
                    continue          # 显式标记的本机运行时产物：接受（永不入库，见上）
                part2 = re.split(r"[（(]", raw)[0].strip().strip("\"'")
                if not part2:
                    continue
                if ABS_RE.match(part2):
                    errs.append(f"{fn} :: lesson_refs 是绝对路径且未标 `[外部]`：{part2!r}"
                                f"（本仓无法解析；确认是外部项目就加 `[外部]` 前缀）")
                    continue
                if not _ref_resolvable(part2):
                    errs.append(f"{fn} :: lesson_refs 指向不存在的目标：{part2!r}（悬空引用）")

    open_cases = [c for c in cases if str(c.get("status", "")).strip() == "open"]
    n_open_fail = sum(len(c.get("known_failures") or []) for c in open_cases)
    if args.strict:
        for c in open_cases:
            errs.append(f"{c.get('_file')} :: status=open（--strict 下视为未收敛）")

    summary = {
        "cases_total": len(cases),
        "open": len(open_cases),
        "resolved": len(cases) - len(open_cases),
        "open_failures": n_open_fail,
        "errors": errs,
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"run-regression: cases={len(cases)} open={len(open_cases)} "
              f"resolved={summary['resolved']} open_failures={n_open_fail}")
        if errs:
            print(f"  FAIL（{len(errs)} 条）")
            for e in errs:
                print("    " + e)
        else:
            print("  PASS（字段齐全 / 无悬空引用 / 无假填）")
        if open_cases and not args.strict:
            print("  未收敛的 case（不算失败，但必须在解决后改 status）：")
            for c in open_cases:
                print(f"    - {c.get('_file')}  failures={len(c.get('known_failures') or [])}")

    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
