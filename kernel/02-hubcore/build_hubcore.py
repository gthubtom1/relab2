#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hubcore 精简器：把旧中枢的可用零件，程序化搬成一个独立的、不带旧包袱的新系统。

为什么不手抄：六套工作流正文约 15 万字，手抄必然引入错漏。这里做**确定性改写**，
每一处删改都记账写进 MANIFEST.json，主人可以逐条核对。

只读旧中枢，只写 work/context-isolation/02-hubcore/。

用法：
    python build_hubcore.py --product <产品根>            # 生成
    python build_hubcore.py --product <产品根> --check    # 只校验，不写
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
PRODUCT: Path = HERE            # 由 main 注入为产品根

# 六套工作流：一次只抱一条
WORKFLOWS = ("desktop-product", "web-service", "cli-tool",
             "source-takeover", "exe-rebuild", "protocol-automation")
# 六套工作流正文点名、且删掉就会真的断链的方法书（15 本）
# 审计依据：hub/.agents/skills/<线>/SKILL.md 的"会加载哪些书"表逐条点名。
REQUIRED_METHODS = ("security-audit", "review", "packaging", "data-storage",
                    "debugging-troubleshooting", "ui-design", "windows-environment",
                    "performance-optimization", "research-reuse", "project-init",
                    "software-integration", "release-readiness", "reverse-engineering",
                    "browser-testing", "project-integration")
# 六线正文 0 次点名，但确实是工程方法：留作文档，不被任何线路由
ON_DEMAND_METHODS = ("planning", "anti-crack-build", "browser-automation", "mobile-reverse")
# 明确不进新系统
PARKED_REASON = {
    "github": "云端发布工具；中枢只在「发 Release」一行点名，主人在场时手动做（查询类联网不受限）",
    "own-skill": "技能系统；本任务明确排除 Skill",
}
# 目录式技能：SKILL.md 之外还有必须一起搬的附录（review 强制读三份附录）
DIR_SKILLS = ("review", "browser-automation")

# 六套工作流要带的文档（门禁、记忆、交接、口径）
REQUIRED_DOCS = ("PHYSICAL-GATES.md", "RESPONSIBILITY-PROTOCOL.md",
                 "PROJECT-MEMORY.md", "ENGINEERING-CONTINUITY.md",
                 "VOCABULARY.md", "OPERATING-MODEL.md")
# 旧项目的元工作流，不属于新独立项目
META_WORKFLOW_DOCS = ("HUB-OWNER-NEED.md", "HUB-优化怎么走.md", "HUB-优化执行计划.md",
                      "HUB-真测漏洞.md", "HUB-综述-为什么总做不好.md",
                      "HUB-综述-穷举模拟为什么不够.md", "OPT-一次一项.md",
                      "OPT-历次总结目录.md", "怎样修好中枢.md", "HUB-需求验收.md")

# ---------------------------------------------------------------- 改写规则
# 每条规则 = (正则, 动作, 说明)。动作：drop_line 整行删 / sub 替换。
# 删除必须是"整行无内容"或"只删引导句"，正文里的方法内容一律保留。
LINE_RULES: list[tuple[re.Pattern, str]] = [
    # 技能引导 —— 主人明确不要
    (re.compile(r"掌舵书读配套|技能书在同夹|读配套技能|配套中枢技能夹"), "drop"),
    (re.compile(r"\buser-skills\b|全域专业技能库|技能全量融合|三层极简架构"), "drop"),
    (re.compile(r"副插件|底模|客人卡带|大路挂上|挂上卡"), "drop"),
    (re.compile(r"按\s*`use_when`\s*匹配|一次只加载当前最需要的那一个"), "drop"),
    (re.compile(r"产品任务去用户技能目录读中枢技能|中枢技能"), "drop"),
    # 云端路径
    (re.compile(r"https?://"), "drop"),
    (re.compile(r"gthubtom1|skills-hub|hub-lean"), "drop"),
    (re.compile(r"^\s*\|\s*(发 Release|打 tag|上传 Release)[^|]*\|"), "drop"),
    # 旧项目的元工作流
    (re.compile(r"完善中枢|优化中枢|一次一项|OPT-"), "drop"),
    (re.compile(r"配套夹|外置中枢这个产品|这份配套夹"), "drop"),
    # 死链：hub/vendor/reverse-skill/ 实测不存在；「深度按 ../README.md」指向那张全死的表
    (re.compile(r"vendor/reverse-skill|vendored 库|深度按\s*`\.\./README\.md`|"
                r"能力→深库|去 vendored"), "drop"),
    (re.compile(r"^\s*[-|].*\.\./README\.md.*$"), "drop"),
]
# 路径改写：把旧占位符指向新系统的相对路径
SUB_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"<hub>/\.agents/skills/([a-z0-9-]+)/SKILL\.md"), r"workflows/\1.md"),
    (re.compile(r"<hub>/docs/([A-Za-z0-9_.\-]+\.md)"), r"docs/\1"),
    (re.compile(r"<hub>/templates/([A-Za-z0-9_.\-]+)"), r"templates/\1"),
    (re.compile(r"<hub>/tools/([A-Za-z0-9_.\-]+)"), r"tools/\1"),
    (re.compile(r"`\.\./exe-rebuild/SKILL\.md`"), "`workflows/exe-rebuild.md`"),
    (re.compile(r"\.agents/skills/"), "workflows/"),
]
# 保留但改写措辞的固定行
# 保留但改写措辞的固定行。顺序敏感：先改长的、再改短的。
LINE_FIXUPS = {
    # 整行替换：把「发 Release 换 github 书」改成「中枢不代发，主人自己做」
    "| 发 Release / 打 tag | `github`（真要发、主人点名了才换；一次只开一本；发前须有答句） |":
        "| 对外发布 | 中枢不代发。主人当场点名，主人自己执行（搜索查文档装依赖随便用）|",
    "（不要换成 `github`；后半段走完才换）": "（后半段走完才读）",
    "（不要换成 `github`）": "",
    "不要换成 `github`": "",
    "不要自动换成 `github`": "不要自动对外发布",
    "不要从本书跳到 `github`。": "",
    "不要从本书跳到 `github`": "",
    # 六线共用的派发句：不再指向 user-skills
    "专业细技能听当场挂上的副插件和主人自加的书": "细活方法书见 `docs/methods/`，点名才读",
    "细活交给当场挂上的副插件": "细活走本线工作流 + `docs/methods/`",
}

# 任何输出文件里都不许再出现的词（--check 用）
FORBIDDEN = ("副插件", "底模", "user-skills", "skills-hub", "gthubtom1",
             "github.com", "hub-lean", "完善中枢", "优化中枢", "一次一项",
             "cha-", "冷咖啡", "寒霜", "FUSION")

# CORE.md 是**首读件**（不是物理常驻件）：物理每轮注入的是标记块，它内联整份 AGENTS.md，
# 由 03-bundle/_bundle_lib.py 的 MARKER_BUDGET（32,000 B）管。这个数是 CORE.md 自己的硬闸门。
# 旧系统常驻 = hub/AGENTS.md 26,342 + hub/FUSION.md 4,591 + 引擎运行时生成的
# 约 100 个技能名清单（engine.py:1002-1028）约 3,750 ≈ 34,683 B。
# 权威值在 03-bundle/_bundle_lib.py 的 CORE_BUDGET（四道闸共用同一个数），
# 这里只做兜底：那份模块不在本脚本的搜索路径上时用这个同值常量。
CORE_BUDGET = 4000


def slim_text(text: str, ledger: list) -> str:
    out_lines = []
    for i, line in enumerate(text.splitlines(), 1):
        for a, b in LINE_FIXUPS.items():
            if a in line:
                line = line.replace(a, b)
                ledger.append({"line": i, "action": "fixup", "detail": a})
        if any(rx.search(line) for rx, _ in LINE_RULES):
            dropped = line.strip()[:90]
            ledger.append({"line": i, "action": "drop_line", "detail": dropped})
            continue
        for rx, rep in SUB_RULES:
            line = rx.sub(rep, line)
        out_lines.append(line)
    # 改写留下的空洞要收干净：空括号、悬空标点、空表格行
    polished: list[str] = []
    for line in out_lines:
        line = re.sub(r"（\s*）", "", line)
        line = re.sub(r"[，、；]\s*[。；]", "。", line)
        line = re.sub(r"\s+([|。；])", r"\1", line)
        if re.fullmatch(r"[\s|]*\|[\s|]*", line) and "|" in line:
            continue          # 表格行被清空了
        polished.append(line)
    out_lines = polished
    # 折叠连续空行（删行留下的空洞）
    cleaned: list[str] = []
    blanks = 0
    for line in out_lines:
        if line.strip():
            blanks = 0
            cleaned.append(line)
            continue
        blanks += 1
        if blanks <= 1:
            cleaned.append(line)
    return "\n".join(cleaned).strip() + "\n"


def copy_slim(src: Path, dst: Path, ledger: list, tag: str) -> dict:
    ledger.clear()
    raw = src.read_text(encoding="utf-8")
    new = slim_text(raw, ledger)
    before, after = len(raw.encode("utf-8")), len(new.encode("utf-8"))
    # 精简器只许变小。变大就是改写逻辑出了 bug（曾把非空行 append 两次，全文翻倍）。
    if after > before:
        raise AssertionError(
            f"精简后反而变大：{src} {before}B -> {after}B。拒绝落盘。")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(new, encoding="utf-8")
    return {"src": src.relative_to(PRODUCT).as_posix(),
            "dst": dst.relative_to(HERE).as_posix(),
            "before_bytes": before, "after_bytes": after,
            "dropped_lines": len(ledger),
            "ledger": ledger[:80],
            "tag": tag}


def build() -> dict:
    hub = PRODUCT / "hub"
    skills = hub / ".agents" / "skills"
    out = HERE
    for sub in ("workflows", "docs", "docs/methods", "templates", "parked"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    report = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "product": str(PRODUCT), "files": [], "workflows": [], "methods": [],
              "docs": [], "parked": [], "templates": []}

    # 1) 六套工作流
    for name in WORKFLOWS:
        src = skills / name / "SKILL.md"
        if not src.is_file():
            report["workflows"].append({"name": name, "ok": False, "why": "源文件不存在"})
            continue
        r = copy_slim(src, out / "workflows" / f"{name}.md", [], "workflow")
        r["name"] = name
        report["workflows"].append(r)
        report["files"].append(r)

    # 2) 必需方法书 + 按需方法书（都只是 md，不再是 skill）
    for name in REQUIRED_METHODS:
        src = skills / name / "SKILL.md"
        if not src.is_file():
            continue
        r = copy_slim(src, out / "docs" / "methods" / f"{name}.md", [], "method-required")
        r["name"] = name
        report["methods"].append(r)
        report["files"].append(r)
    for name in ON_DEMAND_METHODS:
        src = skills / name / "SKILL.md"
        if not src.is_file():
            continue
        r = copy_slim(src, out / "docs" / "methods" / f"{name}.md", [], "method-on-demand")
        r["name"] = name
        report["methods"].append(r)
        report["files"].append(r)

    # 2b) 目录式技能的附录必须一起搬：review 明确要求"加载本书必须读这三份附录"
    for name in DIR_SKILLS:
        src_dir = skills / name
        if not src_dir.is_dir():
            continue
        for extra in sorted(src_dir.glob("*.md")):
            if extra.name == "SKILL.md":
                continue
            r = copy_slim(extra, out / "docs" / "methods" / name / extra.name,
                          [], "method-appendix")
            r["name"] = f"{name}/{extra.name}"
            report["methods"].append(r)

    # 2c) INVARIANTS：六线与必留方法书都按约定引用它，是公共铁律的真源
    inv = skills / "INVARIANTS.md"
    if inv.is_file():
        r = copy_slim(inv, out / "docs" / "methods" / "INVARIANTS.md", [], "invariants")
        r["name"] = "INVARIANTS"
        report["methods"].append(r)
        report["files"].append(r)

    # 3) 其余技能：不进新系统，记原因，不删除原件
    keep = set(WORKFLOWS) | set(REQUIRED_METHODS) | set(ON_DEMAND_METHODS)
    for d in sorted(skills.iterdir()):
        if not d.is_dir() or d.name in keep:
            continue
        report["parked"].append({"name": d.name,
                                 "reason": PARKED_REASON.get(d.name, "与六套工作流无依赖关系")})

    # 4) 六套工作流要带的文档
    for name in REQUIRED_DOCS:
        src = hub / "docs" / name
        if not src.is_file():
            report["docs"].append({"name": name, "ok": False, "why": "源文件不存在"})
            continue
        r = copy_slim(src, out / "docs" / name, [], "doc-required")
        r["name"] = name
        report["docs"].append(r)
        report["files"].append(r)
    for name in META_WORKFLOW_DOCS:
        report["docs"].append({"name": name, "ok": False,
                               "why": "旧项目的元工作流，不属于本独立系统"})

    # 5) 模板：六套工作流的阶段表与门禁样例
    for p in sorted((hub / "templates").glob("*")):
        if p.is_file():
            shutil.copy2(p, out / "templates" / p.name)
            report["templates"].append({"name": p.name, "bytes": p.stat().st_size})

    # 6) 后置修补：protocol-automation 的能力矩阵。
    #    这一步必须在生成之后跑，而且要挂在构建流程里 —— 否则下次重建
    #    workflows/ 就会把矩阵退回成指向已删技能库的死链。
    report["post_patches"] = _post_patch(out)
    return report


# 生成后必须重跑的定点修补。key=被修补的文件，value=补丁脚本。
# 由 T3 的死链全量核查产出：改前 56 处（路径解析不到 45 + 方法书写法错 11），改后 0 处。
# 注意 protocol-automation 那个键只能有一个：apply_protocol_automation_fix.py 内部第一步就调
# apply_matrix_fix.py，矩阵修补和写法修补都得对同一个文件跑。
POST_PATCHES = {
    "workflows/protocol-automation.md":
        "03-bundle/patches/apply_protocol_automation_fix.py",
    "workflows/exe-rebuild.md":
        "03-bundle/patches/apply_exe_rebuild_fix.py",
    "docs/methods/INVARIANTS.md":
        "03-bundle/patches/apply_invariants_fix.py",
    "docs/methods/reverse-engineering.md":
        "03-bundle/patches/apply_reverse_engineering_fix.py",
    "docs/methods/review.md":
        "03-bundle/patches/apply_review_fix.py",
    "docs/methods/browser-automation.md":
        "03-bundle/patches/apply_browser_automation_fix.py",
    "docs/methods/browser-automation/proof.md":
        "03-bundle/patches/apply_browser_automation_proof_fix.py",
    "docs/PROJECT-MEMORY.md":
        "03-bundle/patches/apply_project_memory_fix.py",
    "docs/OPERATING-MODEL.md":
        "03-bundle/patches/apply_docs_audits_fix.py",
    "docs/ENGINEERING-CONTINUITY.md":
        "03-bundle/patches/apply_docs_audits_fix.py",
    "docs/RESPONSIBILITY-PROTOCOL.md":
        "03-bundle/patches/apply_docs_audits_fix.py",
}


def _post_patch(out: Path) -> list:
    done = []
    for rel, script_rel in POST_PATCHES.items():
        script = HERE.parent / script_rel
        target = out / rel
        if not script.is_file() or not target.is_file():
            done.append({"target": rel, "script": script_rel, "status": "缺脚本或缺目标"})
            continue
        proc = subprocess.run(
            [sys.executable, str(script), "--target", str(target)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120)
        done.append({"target": rel, "script": script_rel, "rc": proc.returncode,
                     "status": "ok" if proc.returncode == 0 else "failed",
                     "out": (proc.stdout or proc.stderr or "").strip()[-400:]})
    return done


def check() -> int:
    """校验生成结果：禁词、瘦身比、必需件是否齐全。"""
    bad, total_before, total_after = [], 0, 0
    for p in sorted(HERE.rglob("*.md")):
        if "parked" in p.parts or "MANIFEST" in p.name:
            continue
        text = p.read_text(encoding="utf-8")
        for w in FORBIDDEN:
            if w in text:
                for i, line in enumerate(text.splitlines(), 1):
                    if w in line:
                        bad.append(f"{p.relative_to(HERE).as_posix()}:{i} 含禁词「{w}」")
    manifest = json.loads((HERE / "MANIFEST.json").read_text(encoding="utf-8"))
    for r in manifest["files"]:
        total_before += r["before_bytes"]
        total_after += r["after_bytes"]
    grew = [f"{r['dst']} {r['before_bytes']}->{r['after_bytes']}"
            for r in manifest["files"] if r["after_bytes"] > r["before_bytes"]]
    missing = [w for w in WORKFLOWS if not (HERE / "workflows" / f"{w}.md").is_file()]
    for d in REQUIRED_DOCS:
        if not (HERE / "docs" / d).is_file():
            missing.append("docs/" + d)
    always = HERE / "AGENTS.md"
    core_path = HERE / "CORE.md"
    # 常驻进上下文的只有 CORE.md，硬上限 CORE_BUDGET B。超了就是设计错了，不是排版问题。
    core_bytes = core_path.stat().st_size if core_path.is_file() else -1
    core_over = core_bytes > CORE_BUDGET
    core_missing = core_path.is_file() and core_bytes <= 0
    # 被移出系统的技能，不许以书名形式还留在交付件里（否则等于留了个死链）
    parked_leak = []
    for item in manifest["parked"]:
        token = "`" + item["name"] + "`"
        for p in sorted(HERE.rglob("*.md")):
            if "parked" in p.parts:
                continue
            if token in p.read_text(encoding="utf-8"):
                parked_leak.append(f"{item['name']} -> {p.relative_to(HERE).as_posix()}")
    # 降幅报告要量「旧系统」的两个文件，那是**上一版中枢**的东西，本仓没有。
    # 查不到就跳过这一段：它是给人看的报告，不是校验判据——
    # 校验判据（禁词 / 瘦身比 / 必需件齐全）全部在上面，与旧中枢无关。
    old_hub = PRODUCT / "hub"
    old_always = 0
    if (old_hub / "AGENTS.md").is_file() and (old_hub / "FUSION.md").is_file():
        old_always = (old_hub / "AGENTS.md").stat().st_size + \
                     (old_hub / "FUSION.md").stat().st_size
    new_always = always.stat().st_size
    patch_fail = [p for p in manifest.get("post_patches", [])
                  if p.get("status") == "failed"]
    patch_missing = [p["target"] for p in manifest.get("post_patches", [])
                     if str(p.get("status", "")).startswith("缺")]
    # 实测，不是估算：在本机 ~/.dsh/AGENTS.md 里量 "# >>> hub-dock hub >>>" 到
    # "# <<< hub-dock hub <<<" 的整块 = 36,685 B / 292 行。
    # 静态盘 = hub/AGENTS.md 26,342 + hub/FUSION.md 4,591 = 30,933，
    # 差额 5,752 是引擎运行时生成的部分（八大领域硬编 92 个技能名，按本机技能夹过滤渲染）。
    # 早先这里用的是估算值 3,750（合计 34,683），被复核推翻，已改为实测。
    old_gen = 5752
    old_real = old_always + old_gen
    result = {
        "ok": not bad and not missing and not grew and not parked_leak
               and not patch_fail and not core_over and not core_missing,
        "forbidden_hits": bad,
        "grew_after_slim": grew,
        "parked_leak": parked_leak,
        "post_patch_failed": patch_fail,
        "post_patch_missing": patch_missing,
        "missing": missing,
        "core": {"bytes": core_bytes, "budget": CORE_BUDGET,
                 "over": core_over, "path": "02-hubcore/CORE.md"},
        "always_on_real": {
            # 没有上一版中枢时（old_always == 0），「旧账」只剩一个凭空的 old_gen，
            # 算出来的 cut_pct 和 old_parts（hub/AGENTS.md 会是负数）都没有意义。
            # 那种情况只报 new_bytes，不给降幅——宁可缺一项，也不给一个会被引用的假数字。
            "old_bytes": old_real if old_always else None,
            "old_source": ("实测：本机 ~/.dsh/AGENTS.md 标记块整块 36,685 B / 292 行"
                           if old_always else None),
            "old_parts": ({"hub/AGENTS.md": old_always - 4591,
                           "hub/FUSION.md": 4591,
                           "引擎运行时生成部分（实测差额）": old_gen}
                          if old_always else None),
            "new_bytes": core_bytes,
            "new_parts": {"CORE.md（第一份按需首读）": core_bytes,
                          "标记块（物理每轮注入）":
                              "见 03-bundle/_bundle_lib.py BOTTOM_LINES（12 块底线自检）+ MARKER_BUDGET=32000 闸门"},
            "cut_pct": round(100 * (1 - core_bytes / old_real), 1) if old_always else None,
            "note": ("本机没有上一版中枢的 hub/，只报 CORE.md 的大小，不算降幅。"
                     "物理常驻是标记块（24 KB 级，见 MARKER_BUDGET），CORE.md 是首读件。"
                     if not old_always else
                     "本项以 CORE.md 作分母口径，只说明首读件的大小。"
                     "物理常驻是标记块（24 KB 级，见 MARKER_BUDGET），CORE.md 是首读件。"),
        },
        "always_on": {"old_bytes": old_always, "new_bytes": new_always,
                      "cut_pct": round(100 * (1 - new_always / old_always), 1)
                      if old_always else None,
                      "old_files": ["hub/AGENTS.md", "hub/FUSION.md"],
                      "note": None if old_always else
                              "本机没有上一版中枢的 hub/AGENTS.md，跳过降幅对比。"
                              "基准数字见 01-design/当前实测基线.md。",
                      "new_files": ["02-hubcore/AGENTS.md"]},
        "on_demand": {"before_bytes": total_before, "after_bytes": total_after,
                      "cut_pct": round(100 * (1 - total_after / total_before), 1)
                      if total_before else None},
        "workflows": len(manifest["workflows"]),
        "methods": len(manifest["methods"]),
        "parked": len(manifest["parked"]),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 3


def main():
    global PRODUCT
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", required=True)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    PRODUCT = Path(a.product).resolve()
    if a.check:
        return check()
    rep = build()
    (HERE / "MANIFEST.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True,
                      "workflows": len(rep["workflows"]),
                      "methods": len(rep["methods"]),
                      "docs": len(rep["docs"]),
                      "parked": len(rep["parked"]),
                      "manifest": str(HERE / "MANIFEST.json")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
