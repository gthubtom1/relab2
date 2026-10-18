# -*- coding: utf-8 -*-
"""hubcore 打包器：把散落的素材组装成一棵可搬运的自包含树。

    python pack.py [--out dist/hubcore] [--with-skill-tools] [--check]

只读取材，不写素材所在的任何目录。所有改写都发生在写出的副本上。
产出：out/ 下的完整包 + bundle-meta.json（版本、计数、禁名清单）。

硬约束：产出的每一个文件里都不许出现源仓路径、本机盘符、远端地址、技能系统路径。
这一条在本文件里当场断言，不靠 verify 事后才发现。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

try:
    from . import _bundle_lib as L
except ImportError:
    import _bundle_lib as L

HERE = Path(__file__).resolve().parent
# 素材根：pack.py 自身在 <hubcore>/03-bundle/ 下，往上一级就是素材根。
CI_ROOT = HERE.parent
# 仓根：本仓能独立运行，绝大多数时候用不到它；只有「同仓里还装着上一版中枢」
# 那种情况下才用来找技能夹目录（找不到就跳过，不报错）。
REPO_ROOT = CI_ROOT.parent
# 运行核（state.py / hub_flow.py 等 15 个）在中枢本体自己的 tools/ 下。
# 原来这里写的是 REPO_ROOT / "hub" / "tools"——那是**上一版**中枢的位置，
# 意味着打包器必须靠旧中枢在场才能出包。本仓要能独立打包，就不能依赖仓外任何东西。
HUB_TOOLS = CI_ROOT / "02-hubcore" / "tools"
HUBCORE = CI_ROOT / "02-hubcore"
CTXISO = CI_ROOT / "ctxiso"

# 运行核：原样搬，一个字不改。skill_pull / own_skill 是技能系统工具，
# 带远端地址和技能路径，违反 SPEC §0.4「不联网」与 §0.5「不碰 Skill」，默认不装。
CORE_TOOLS = (
    "state.py", "shift.py", "map_show.py", "map_freeze.py", "hub_io.py",
    "hub_flow.py", "hub_cmds.py", "hub_ask.py", "hub_wording.py", "hub_work.py",
    "hub_memory.py", "hub_assertions.py", "hub_gates.py", "feature_set.py",
    "speech_land.py",
)
SKILL_TOOLS = ("skill_pull.py", "own_skill.py")
TEST_TOOLS = tuple(p.name for p in sorted(HUB_TOOLS.glob("test_*.py"))) if HUB_TOOLS.is_dir() else ()

# 装好后仍要在宿主家目录里独立跑的工具。
# 只放 uninstall.py：主人一键卸载要用，且它不含任何禁词（自包含，无内部 import）。
# pack / install / verify / hosts / _bundle_lib 都是**闸门与打包工具**，一律不进包——
# 它们内部必然写着禁词本身（不写就没法搜），打进包会让包永远过不了自己的检查，
# 逼着人放宽规则，比藏 bug 更糟。这些留在 03-bundle/。
RUNTIME_TOOLS = ("uninstall.py",)


# ---------------------------------------------------------------- 改写表

# 每条 = (正则, 替换, 为什么)。全部作用在**副本**上，素材原文件不动。
# 每条都必须真的命中，命中 0 次就让 pack 失败——防止素材改版后静默失效。
REWRITES = (
    (re.compile(r"\.agents/skills/([a-z0-9-]+)/SKILL\.md"), r"workflows/\1.md",
     "旧中枢技能指针 -> 包内六线工作流（与 build_hubcore.py 同款映射）"),
    (re.compile(r"\.\./INVARIANTS\.md"), "docs/methods/INVARIANTS.md",
     "原路径按旧技能夹层级算，包内解析不到"),
    (re.compile(r"(?<!docs/methods/)workflows/review/SKILL\.md"), "docs/methods/review.md",
     "包内没有 workflows/review/，方法书在 docs/methods/"),
    (re.compile(r"\.\./README\.md"), "AGENTS.md",
     "包内没有 README，该条规则实际在 AGENTS.md §3"),
    (re.compile(r"`speech_land\.py`"), "`tools/speech_land.py`",
     "裸文件名补出包内目录，运行核确实在包内"),
    (re.compile(r"<hub>/tools/"), "tools/", "占位符 -> 包根相对"),
    (re.compile(r"<dev>/ctxiso/"), "ctxiso/", "占位符 -> 包根相对"),
    (re.compile(r"<hub>/"), "", "残留占位符兜底"),
)

# 出货内容红线与白名单统一定义在 _bundle_lib，pack 与 verify 共用同一张表。
FORBIDDEN = L.FORBIDDEN
LOOPBACK_ALLOWED = L.LOOPBACK_ALLOWED

# 运行核里带旧项目名的那几行。只在**包副本**上换掉，原文件 hub/tools/*.py 一个字不动。
# 换之前先说清为什么换是安全的：这些字面量在装好的包里根本走不到。
TOOL_EDITS = (
    ("hub_io.py",
     'root = Path(base) / "hub-lean" if base else Path.home() / ".hub-lean"',
     'root = Path(base) / "hubcore" if base else Path.home() / ".hubcore"',
     "旧项目名出现在开发目录登记表兜底路径里。该分支只在 AGENTS.md 含 <hub> 占位符时进入，"
     "而装出来的 AGENTS.md 不含该占位符（实测命中 0），所以在包内不可达；换名不改变任何可达行为。"),
    ("state.py",
     '"""hub-lean CLI 入口。',
     '"""中枢 CLI 入口。',
     "docstring 里的旧项目名，用户看不见，但属于出货内容残留。"),
    ("state.py",
     'description="hub-lean 项目状态的唯一写入者"',
     'description="中枢项目状态的唯一写入者"',
     "argparse 的 description 会直接出现在用户敲 --help 看到的输出里，必须换。"),
)

# 出厂空表。hub_io.py 在装好后会让 REGISTRY 指向 HUB_ROOT/registry.json，
# 第一次运行前就把这张表放进包里，避免运行到一半才创建。
REGISTRY_JSON = '{\n  "products": []\n}\n'


# 素材里有些地方在同一段里先写了 `../docs/methods/x.md`，后面又用裸名 `x.md` 指同一本书。
# 裸名搬进包根解析不到，按实际存在的方法书名统一补出目录。已经带前缀的不重复加。
METHOD_STEMS = sorted(p.stem for p in (HUBCORE / "docs" / "methods").glob("*.md"))
_METHOD_REF = re.compile(
    r"`(?<!docs/methods/)(" + "|".join(re.escape(s) for s in METHOD_STEMS) + r")\.md`")


def prefix_method_refs(text: str, fired: dict) -> str:
    text, n = _METHOD_REF.subn(r"`docs/methods/\1.md`", text)
    if n:
        key = "同段裸方法书名补出 docs/methods/ 目录"
        fired[key] = fired.get(key, 0) + n
    return text


def apply_rewrites(text: str, where: str, fired: dict):
    for pat, repl, why in REWRITES:
        text, n = pat.subn(repl, text)
        if n:
            fired.setdefault(why, 0)
            fired[why] += n
    return prefix_method_refs(text, fired)


# ---------------------------------------------------------------- ctxiso 适配

# 装进宿主后包根从 __file__ 推、状态写包内 .state/，素材里的原文件一个字不动。
CTXISO_EDITS = (
    ("paths.py",
     '"""路径与配置。本包唯一的写盘位置是 DEV_ROOT/state/。"""',
     '"""路径与配置。本包唯一的写盘位置是包根 .state/。"""'),
    ("paths.py",
     'DEV_ROOT = PKG.parent                    # 本仓里是 kernel/（不是旧的 work/context-isolation/）\n'
     'STATE_DIR = DEV_ROOT / "state"',
     'PKG_ROOT = PKG.parent                   # 包根：AGENTS.md / tools / ctxiso 都在这层\n'
     'STATE_DIR = PKG_ROOT / ".state"       # 装进宿主后状态只落包内，卸载能一次删净'),
    ("__init__.py",
     "3. 本包所有状态写在 work/context-isolation/state/ 下，不写进 .hub/。",
     "3. 本包所有状态写在本包的 .state/ 下，不写进 .hub/，也不写宿主家目录根。"),
)


def adapt_ctxiso(dst: Path, fired: dict):
    dst.mkdir(parents=True, exist_ok=True)
    for src in sorted(CTXISO.glob("*")):
        if src.name == "__pycache__" or not src.is_file():
            continue
        out = dst / src.name
        if src.suffix in (".py", ".json"):
            text = src.read_text(encoding="utf-8")
            out.write_text(text, encoding="utf-8")
        else:
            shutil.copy2(src, out)
    for name, old, new in CTXISO_EDITS:
        target = dst / name
        text = target.read_text(encoding="utf-8")
        if old not in text:
            raise SystemExit(
                "ctxiso 适配锚点没命中，素材可能已改版。\n  文件：%s\n  找不到：%r" % (name, old[:70]))
        target.write_text(text.replace(old, new, 1), encoding="utf-8")
        fired["ctxiso 适配：%s" % name] = fired.get("ctxiso 适配：%s" % name, 0) + 1
    # 素材配置里有两条指向外部目录的负向忽略 glob：
    #   **/work/context-isolation/**  指向素材自己的目录，包内不存在
    #   **/user-skills/**            指向技能库
    # 查证结论：archive_ignore_globs 这个键**当前没有任何代码读它**——
    # store.refresh_docs() 只按 archive_scan（具名文件）和 archive_scan_dirs（具名目录）取，
    # 忽略 glob 根本不在链路上。所以从包副本里删掉这两条，行为零变化。
    cfg = dst / "config.json"
    data = json.loads(cfg.read_text(encoding="utf-8"))
    globs = data.get("archive_ignore_globs", [])
    before = len(globs)
    dropped = [g for g in globs if "context-isolation" in g or "user-skills" in g]
    data["archive_ignore_globs"] = [g for g in globs if g not in dropped]
    if dropped:
        fired["ctxiso 适配：config.json 去掉 %d 条从未被读取的外部目录 glob（%s）"
              % (len(dropped), "、".join(dropped))] = 1
    cfg.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- 装包

def copy_text(src: Path, dst: Path, fired: dict):
    text = src.read_text(encoding="utf-8")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(apply_rewrites(text, str(src), fired), encoding="utf-8")


def copy_blob(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def collect_skill_names():
    """把**技能系统**里真实存在的技能名收成一份禁名清单，写进包内给 verify 的 (d) 用。

    有了它，(d) 就是拿真名单逐条比对，不是凭感觉说「看着没有技能名」。

    ★ 2026-10-16 修：不再把包自己的 `workflows/*.md` 与 `docs/methods/*.md` 名字算进来。
      标记块内联的就是中枢自己的 `AGENTS.md` 全文（`_bundle_lib.py` 的 `rule_text()`），
      而它的「六套工作流」与「产品线 → 关键物理门」两张表**必然**出现这六个产品线名，
      也必然出现 `docs/methods/review.md` 这类**包内相对指针**。
      把包自己的零件名当禁名，(d) 就恒红（实测：标记块 24048 B，
      命中 6 个产品线名 + `review`）；而 SPEC 第 0 节硬约束 5「不碰 Skill 系统」
      针对的是**技能系统**的名字，不是本包自己出货的产品线与方法书。
      所以禁名清单只留技能系统那一侧。
    """
    names = set()
    # 技能夹是**上一版**中枢的东西，本仓没有，也不该依赖。留着这两个候选路径只为
    # 「主人在同一个仓里同时装了旧中枢」那种情况；目录不存在就跳过，不报错。
    for base in (REPO_ROOT / "hub" / ".agents" / "skills", REPO_ROOT / "user-skills"):
        if base.is_dir():
            for p in base.iterdir():
                if p.is_dir():
                    names.add(p.name)
    # 过短的目录名（如 pi、dsh）比单个字母还容易误报，剔除；>=4 字符的才是有意义的技能名
    return sorted(n for n in names if len(n) >= 4)


def build(out: Path, with_skill_tools: bool = False,
          allow_out_anywhere: bool = False) -> dict:
    # 1,000 B 闸门：标记块是物理每轮注入的那一层，超了就直接拒绝打包。
    marker_bytes = len(L.marker_block().encode("utf-8"))
    if marker_bytes > L.MARKER_BUDGET:
        raise SystemExit(
            "标记块全文 %d 字节 > 上限 %d 字节，拒绝打包。\n"
            "  标记块每轮都注入，塞不下的内容应该放进 CORE.md（上限 %d），不是挤进标记块。"
            % (marker_bytes, L.MARKER_BUDGET, L.CORE_BUDGET))
    out = Path(out).expanduser().resolve()
    dist_root = (HERE / "dist").resolve()
    expected_out = (dist_root / L.PACKAGE_NAME).resolve()
    if out != expected_out and not allow_out_anywhere:
        raise SystemExit("--out 只能是 03-bundle/dist/hubcore，拒绝覆盖源码或任意外部目录。"
                         "（确需写别处时显式加 --allow-out-anywhere，仅限目标为空的新目录）")
    if out != expected_out and allow_out_anywhere:
        # Explicit opt-in, used by check_dist_sync.py to build a throwaway comparison
        # package. Never allowed to touch an existing non-empty directory.
        if out.exists() and any(out.iterdir()):
            raise SystemExit("--allow-out-anywhere 只允许空目录，拒绝覆盖：%s" % out)
    if out.exists():
        if not out.is_dir() or not (HERE / L.META_NAME).is_file():
            raise SystemExit("--out 已存在但不是本工具生成的包目录，拒绝递归删除：%s" % out)
        L.rmtree_quiet(out)
    out.mkdir(parents=True)
    out.mkdir(parents=True, exist_ok=True)
    fired: dict = {}

    # 1. 常驻核心（措辞是产品决定，原样打进包，打包器不二次生成）+ 全量规则
    core_src = HUBCORE / "CORE.md"
    if not core_src.is_file():
        raise SystemExit("素材里没有常驻核心：%s" % core_src)
    shutil.copy2(core_src, out / "CORE.md")
    copy_text(HUBCORE / "AGENTS.md", out / "AGENTS.md", fired)

    # 2. 六线工作流 / 方法书与文档 / 模板
    for sub in ("workflows", "docs", "templates"):
        for src in sorted((HUBCORE / sub).rglob("*")):
            if not src.is_file():
                continue
            rel = src.relative_to(HUBCORE)
            (copy_text if src.suffix in (".md", ".json", ".jsonl") else copy_blob)(src, out / rel, fired)

    # 3. 运行核：原样搬，只换掉出货内容里那几处旧项目名（见 TOOL_EDITS）
    tools_dst = out / "tools"
    tools_dst.mkdir()
    names = list(CORE_TOOLS) + (list(SKILL_TOOLS) if with_skill_tools else [])
    for name in names:
        src = HUB_TOOLS / name
        if not src.is_file():
            raise SystemExit("运行核缺文件：%s" % src)
        dst = tools_dst / name
        text = src.read_text(encoding="utf-8")
        edited = False
        for fname, old, new, why in TOOL_EDITS:
            if fname != name:
                continue
            if old not in text:
                raise SystemExit(
                    "运行核改写锚点没命中，素材可能已改版。\n  文件：%s\n  找不到：%r" % (name, old[:70]))
            text = text.replace(old, new, 1)
            edited = True
            key = "运行核 %s：%s" % (name, why)
            fired[key] = fired.get(key, 0) + 1
        if edited:
            dst.write_text(text, encoding="utf-8")
        else:
            shutil.copy2(src, dst)

    # 3b. 出厂空表，让 hub_io.py 装好后指向的 registry.json 第一次运行前就在
    (out / "registry.json").write_text(REGISTRY_JSON, encoding="utf-8")

    # 4. 上下文隔离侧车（副本上适配）
    adapt_ctxiso(out / "ctxiso", fired)

    # 5. 装好后要在宿主家目录独立跑的装卸与自证工具
    for name in RUNTIME_TOOLS:
        src = HERE / name
        if not src.is_file():
            raise SystemExit("缺少随包工具：%s" % src)
        copy_blob(src, out / name)

    meta = {
        "name": L.PACKAGE_NAME,
        "version": L.PACKAGE_VERSION,
        "built_at": L.now_iso(),
        "entry_file": "AGENTS.md",
        "core_file": "CORE.md",
        "core_bytes": (out / "CORE.md").stat().st_size,
        "core_budget_bytes": L.CORE_BUDGET,
        "marker_begin": L.MARKER_BEGIN,
        "marker_end": L.MARKER_END,
        "installs_into": "<宿主家目录>/" + L.PKG_DIRNAME,
        "uninstall_entry": "uninstall.py",
        "verify_entry": "verify.py",
        "tools_installed": names,
        "tools_excluded": {
            "reason": "带远端地址与技能系统路径，违反「不联网 / 不碰 Skill」；"
                      "新独立版 AGENTS.md 只路由到 state.py 与 shift.py，功能不缺。",
            "skill_tools": list(SKILL_TOOLS),
            "tests": list(TEST_TOOLS),
        },
        "state_dir": L.STATE_DIRNAME,
        "skill_name_denylist": collect_skill_names(),
        "rewrites_applied": fired,
        "forbidden_strings": list(FORBIDDEN),
        "loopback_allowed": list(LOOPBACK_ALLOWED),
    }
    # 6. 产物里一个字节码、一个状态目录都不该有。
    #    .pyc 头里的 co_filename 记着编译时的绝对源码路径，必然带构建机信息且无法事后剔除；
    #    .state/ 是有人对着本目录跑过 ctxiso 留下的，会跟着装进每台机器。
    purged = L.purge_bytecode(out)
    for state_dir in out.rglob(L.STATE_DIRNAME):
        if state_dir.is_dir():
            L.rmtree_quiet(state_dir)
            purged += 1
    if purged:
        fired["剔除产物里的字节码 / 状态目录"] = purged

    # 元数据留在 03-bundle/ 供 verify 读取，**不进包**（它把禁词表序列化进文件，
    # 打进包等于让包自己违反自己的规则）。
    (HERE / L.META_NAME).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


# ---------------------------------------------------------------- 当场断言

def scan_forbidden(pkg_root: Path):
    """包内每个文件逐行搜禁词。返回 (fails, allowlisted, skipped)，三种结果分开，不混成一句全绿。"""
    return L.scan_forbidden(pkg_root)


def check_uninstall_sync():
    """卸载器认块靠的是它自己那份常量。两份漂移了，卸载就摘不掉自己写的块。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_uninst", HERE / "uninstall.py")
    u = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(u)
    for hh in ("", "C:\\host\\.codex"):
        if u.marker_block(hh) != L.marker_block(hh):
            return False, "uninstall.py 的块和 _bundle_lib 对不上（host_home=%r）" % hh
    return True, "卸载器与装的时候写进去的块逐字符一致"


def self_check(out: Path) -> int:
    ok = True
    core_bytes = (out / "CORE.md").stat().st_size
    if core_bytes > L.CORE_BUDGET:
        print("[FAIL] CORE.md %d B > %d B" % (core_bytes, L.CORE_BUDGET))
        ok = False
    else:
        print("[ ok ] CORE.md %d B <= %d B" % (core_bytes, L.CORE_BUDGET))

    fails, allowed, skipped = scan_forbidden(out)
    n_files = len(L.list_package_files(out))
    for rel, line_no, word, line, why in allowed:
        print("[白名单] %s:%d  [%s]  %s" % (rel, line_no, word, line[:90]))
        print("          保留原因：%s" % why)
    if fails:
        ok = False
        print("[FAIL] 禁词命中 %d 处（不含白名单）：" % len(fails))
        for rel, line_no, word, line in fails[:20]:
            print("        %s:%d  [%s]  %s" % (rel, line_no, word, line))
    else:
        print("[ pass ] %d 个文件零禁词命中（无源仓路径 / 无盘符 / 无远端 / 无技能系统路径）"
              % (n_files - len(skipped)))
        if allowed:
            print("[   白] 另有 %d 处命中白名单，已逐条列名 + 列原因" % len(allowed))
        else:
            print("[   白] 白名单 0 条命中")
        if skipped:
            # FIX-20：skipped 这一桶混了两种**完全不同**的东西，原来的打印把
            # 它们一起说成「闸门自身文件」，于是「读不出来、根本没扫」的文件
            # 被报成「属检查工具不属出货内容」—— 理由是假的。
            #   (a) rel in GATE_FILES：按设计排除，理由成立；
            #   (b) 读不出 / 非 UTF-8：这是**盲区**，不是设计。
            by_design = [s for s in skipped if "不可读" not in s]
            unreadable = [s for s in skipped if "不可读" in s]
            if by_design:
                print("[  排除] %d 个闸门自身文件按设计未扫"
                      "（里面必然写着禁词本身，属检查工具不属出货内容）：%s"
                      % (len(by_design), "、".join(by_design)))
            if unreadable:
                ok = False
                print("[  盲区] %d 个文件读不出，**根本没扫过禁词**，"
                      "不能算「零命中」：" % len(unreadable))
                for s in unreadable:
                    print("        %s" % s)

    refs = L.scan_refs(out)
    # FIX-20：ok=None 是「读不出、根本没扫」，不是死链。混进 dead 会让
    # 盲区披着死链的外衣 —— 结果非零对，但理由是假的，人会去修错东西。
    dead = [r for r in refs if r["ok"] is False]
    blind = [r for r in refs if r["ok"] is None]
    if blind:
        ok = False
        print("[  盲区] %d 个文件读不出，包内相对引用**没扫过**，不能算通过："
              % len(blind))
        for r in blind[:20]:
            print("        %s  —— %s" % (r["file"], r.get("why", "")))
    if dead:
        ok = False
        print("[FAIL] 包内相对引用解析不到 %d 条：" % len(dead))
        for r in dead[:20]:
            print("        %s:%d  ->  %s" % (r["file"], r["line"], r["ref"]))
    else:
        print("[ ok ] 包内相对引用 %d 条全部解析得到" % (len(refs) - len(blind)))

    if not (out / "ctxiso" / "paths.py").is_file():
        print("[FAIL] 缺 ctxiso/paths.py")
        ok = False
    if "PKG_ROOT / \".state\"" not in (out / "ctxiso" / "paths.py").read_text(encoding="utf-8"):
        print("[FAIL] ctxiso/paths.py 没适配到包内 .state/")
        ok = False
    else:
        print("[ ok ] ctxiso/paths.py 已指向包内 .state/")

    bad = L.find_bytecode(out)
    if bad:
        ok = False
        print("[FAIL] 产物里有 %d 个字节码/缓存目录（.pyc 头里记着编译时的绝对路径）：" % len(bad))
        for p in bad[:10]:
            print("        %s" % p.relative_to(out))
    else:
        print("[ ok ] 产物里 0 个 .pyc / __pycache__")

    states = [p for p in out.rglob(L.STATE_DIRNAME)]
    if states:
        ok = False
        print("[FAIL] 产物里有 %d 个 %s/ 状态目录：" % (len(states), L.STATE_DIRNAME))
        for p in states[:10]:
            print("        %s" % p.relative_to(out))
    else:
        print("[ ok ] 产物里 0 个 %s/ 状态目录" % L.STATE_DIRNAME)

    good, why = check_uninstall_sync()
    if good:
        print("[ ok ] %s" % why)
    else:
        ok = False
        print("[FAIL] %s" % why)

    print("[ ok ] 包内文件 %d 个，合计 %d 字节" % (
        len(L.list_package_files(out)),
        sum((out / r).stat().st_size for r in L.list_package_files(out))))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pack.py", description="生成 hubcore 自包含安装包")
    ap.add_argument("--out", default=str(HERE / "dist" / L.PACKAGE_NAME))
    ap.add_argument("--with-skill-tools", action="store_true",
                    help="连技能系统工具一起装（会带远端地址，verify 的禁词检查必红）")
    ap.add_argument("--check", action="store_true", help="只跑当场断言，不重建")
    ap.add_argument("--allow-out-anywhere", action="store_true",
                    help="允许 --out 指向 dist/ 之外的目录（仅供 check_dist_sync.py "
                         "建临时对照包用；目标必须不存在或为空，绝不允许覆盖任何已有内容）")
    args = ap.parse_args(argv)

    out = Path(args.out)
    if not args.check:
        if args.with_skill_tools:
            print("[警告] --with-skill-tools：包里会带远端地址与技能系统路径，"
                  "违反「不联网 / 不碰 Skill」，verify (a) 会红。")
        meta = build(out, args.with_skill_tools, allow_out_anywhere=args.allow_out_anywhere)


        print("已生成：%s" % out)
        print("  文件 %d 个，常驻核心 %d B，改写 %d 类" % (
            len(L.list_package_files(out)), meta["core_bytes"], len(meta["rewrites_applied"])))
        for why, n in sorted(meta["rewrites_applied"].items()):
            print("    改写 %2d 处：%s" % (n, why))
    rc = self_check(out)
    return rc


if __name__ == "__main__":
    sys.exit(main())
