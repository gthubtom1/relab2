# -*- coding: utf-8 -*-
"""hubcore 装进一个宿主家目录。

    python install.py --source dist/hubcore --host-home <宿主家目录> [--dry-run] [--base <底模卡片>] [--guest <指引卡片>]

流程照 SPEC 第 3 节，一步都不省：
  1. 宿主必须在空闲状态；正在跑的一律不写
  2. 宿主入口文件整份备份到 hub/.backups/AGENTS.md.<时间戳>
  3. 写 hub/ 整棵树（先写临时目录，再原子改名，不留半装）
  4. 入口文件按顺序写：宿主原文 / 底模块（给了 --base 才有）/ 指引块（给了 --guest 才有）/ 标记块；原文一个字不动
     --replace-origin 走覆盖模式：宿主原文整段丢弃（原字节在 hub/.backups/ 里存着，卸回时合并还原）
     （标记块刻意写最后：它是最后一段定论，主人换任何底模、任何指引卡都不影响它生效）
  5. 写 install-manifest.json（含卡片名与 sha，对不上就报）
  6. 立刻自检：抽 3 个文件对 sha；跑一次 ctxiso status；跑一次 state.py --help
     任一失败 -> 整体回滚

宿主原文件只在标记块与底模块内被改。重复安装幂等（先摘旧块再插新块）。
底模卡片是控制台侧的东西（04-console/cards/），永不进包。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

try:
    from . import _bundle_lib as L
    from . import hosts as H
except ImportError:
    import _bundle_lib as L
    import hosts as H

PKG_DIRNAME = L.PKG_DIRNAME
HERE = Path(__file__).resolve().parent
REQUIRED = ("CORE.md", "AGENTS.md", "registry.json", "workflows", "docs", "templates",
            "tools", "ctxiso", "uninstall.py")


class InstallError(RuntimeError):
    pass


# ---------------------------------------------------------------- 卡片（底模 / 技能指引）

def delimiter_in_text(text: str) -> str:
    """正文里有没有整行等于中枢的定界行。有就返回那一行，没有就返回空串。

    定界行是中枢标记块的护栏。别人的成品提示词里出现它，卸回就会把那一段
    当成“我们的块”只截一半，卡片的后半截留在主人的原文里当指令被读。
    """
    marks = (L.MARKER_BEGIN, L.MARKER_END, L.BASE_BEGIN, L.BASE_END, L.GUEST_BEGIN, L.GUEST_END)
    for line in str(text or "").splitlines():
        if line.strip() in marks:
            return line.strip()
    return ""


def is_valid_card_name(name: str) -> bool:
    if not name or not isinstance(name, str) or len(name) > 80:
        return False
    invalid_chars = set('\\/:*?"<>|\0\r\n')
    if any(c in invalid_chars or ord(c) < 32 for c in name):
        return False
    if ".." in name:
        return False
    stem = name.split(".")[0].upper()
    reserved = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4",
                "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2",
                "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
    return stem not in reserved


def read_card(path: Path, want_kind: str):
    """读一张卡片：整个文件原样返回，一个字不改、不剥头、不校验格式。

    卡片没有格式要求。底模 / 指引 / 中枢三层一视同仁：文件里是什么，装进去
    就是什么。手写的成品提示词、没有任何结构的纯文本 —— 一律原样用。
    kind 由调用方给的槽位(want_kind)决定，不由卡片自称。
    卡片是控制台侧的东西（04-console/cards/），永不进包。
    返回 (kind, name, hosts_note, content)。
    """
    p = Path(path).expanduser()
    content = p.read_text(encoding="utf-8").strip("\n")
    if "\x00" in content:
        raise InstallError("卡片正文含 NUL 字节，拒绝装：%s" % path)
    if not content:
        raise InstallError("卡片正文是空的，拒绝装：%s" % path)
    size = len(content.encode("utf-8"))
    if size > L.BASE_BUDGET:
        raise InstallError("卡片 %d 字节 > 上限 %d 字节（每轮都注入，太大拖上下文），拆小再装。"
                           % (size, L.BASE_BUDGET))
    # name 取文件名（卡片的名字本来就是文件名），hosts_note 走 _meta.json，混不到这儿。
    return want_kind, p.stem, "", content


def read_base_card(path: Path):
    kind, name, hosts_note, content = read_card(path, "base")
    return name, hosts_note, content


def read_hub_card(path: Path):
    kind, name, hosts_note, content = read_card(path, "hub")
    return name, hosts_note, content


# ---------------------------------------------------------------- 前置检查

def check_source(source: Path):
    source = Path(source).expanduser().resolve()
    if not source.is_dir():
        raise InstallError("安装包不存在：%s" % source)
    missing = [n for n in REQUIRED if not (source / n).exists()]
    if missing:
        raise InstallError("安装包不完整，缺：%s\n  先跑 pack.py 生成。" % "、".join(missing))
    if not (source / "CORE.md").is_file():
        raise InstallError("安装包没有 CORE.md")
    core_bytes = (source / "CORE.md").stat().st_size
    if core_bytes > L.CORE_BUDGET:
        raise InstallError("安装包 CORE.md %d 字节 > %d 字节上限，拒绝装"
                           % (core_bytes, L.CORE_BUDGET))
    return source


def check_idle(host_home: Path, allow_running: bool) -> str:
    spec = H.resolve_host(host_home)
    if spec is None:
        return "自定义家目录（不在已知宿主名单里，活进程检测按不到，只做文件级检查）"
    info = H.detect(host_home, spec)
    if not getattr(info, "running_known", True) and not allow_running:
        raise InstallError(
            "读不出这家是否正在跑，拒绝写入。先关掉宿主后再试；"
            "确实要硬装，加 --allow-running 自己担责。")
    if info.running and not allow_running:
        raise InstallError(
            "这家 %s 正在跑（%s）。先把软件关掉再装。\n"
            "  正在跑的时候盖它的入口文件，会让它这一场读到半份规则。\n"
            "  确实要硬装，加 --allow-running 自己担责。" % (info.display, info.running_detail))
    if allow_running and not getattr(info, "running_known", True):
        # 调用方自己的探针比这一份强：控制台按进程命令行认宿主，这份只认同名 exe，
        # 认不出 node 承载的家就报「读不出」。调用方敢传 --allow-running，就是它已经确认过空闲。
        return ("调用方已确认空闲（本包这份探针只认同名 exe，认不出 node 承载的宿主：%s）"
                % info.running_detail)
    return info.running_detail


def check_target(host_home: Path, replace: bool):
    """宿主家目录里已经有 hub/ 时怎么办。先看清楚，绝不默默盖掉别人的东西。"""
    pkg = host_home / PKG_DIRNAME
    if not pkg.exists():
        return {"backed_up": False, "backup": ""}
    if (pkg / L.MANIFEST_NAME).is_file():
        return {"backed_up": False, "backup": "", "supersede": True}
    if not replace:
        raise InstallError(
            "宿主家目录里已经有 %s/，但里面没有本系统的安装清单 —— 这不是本系统装的东西。\n"
            "  为避免误删主人家里的东西，这里拒绝直接盖。\n"
            "  确认那目录可以整体搬走，加 --replace（装前会备份到 hub/.backups/）。" % PKG_DIRNAME)
    return {"backed_up": True, "backup": None, "supersede": False}   # backup 稍后填


# ---------------------------------------------------------------- 写盘

def _previous_origin_backup(host_home: Path, entry_name: str):
    """上一次也是覆盖模式时，真正的「宿主原文」在上一棵树记着的备份里。返回 (路径, 相对路径) 或 None。

    覆盖模式会把入口文件里的原文整段丢掉。这意味着**第二次**覆盖安装时，「装前文件」
    已经不是原文了——照旧备份它，真原文就永远找不回来，卸回还原出来的还是一份中枢文本。
    所以这里把上一棵树里那份原文原样接下来。
    """
    live = host_home / PKG_DIRNAME
    manifest = live / L.MANIFEST_NAME
    if not manifest.is_file():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    entry = data.get("entry_file") or {}
    if not entry.get("origin_dropped"):
        return None
    if str(entry.get("path") or "") != entry_name:
        return None
    rel = str(entry.get("backup") or "")
    path = (live / rel) if rel else None
    if path is None or not path.is_file():
        return None
    return path, rel


def stage_tree(source: Path, host_home: Path, ts: str, entry_name: str,
               entry_bytes, pre_existing):
    """把包写进临时目录，顺手把入口文件备份也放进去。返回 (stage_root, backup_rel)。

    entry_bytes 是「要存进备份的那一份」：非覆盖模式就是装前原字节；覆盖模式是**摘掉我们
    自己旧块之后的原文**——照旧备份整份，卸回会把上一轮的中枢文本一起还回来。
    """
    stage = host_home / (".hubcore-stage-" + ts)
    L.rmtree_quiet(stage)
    stage_pkg = stage / PKG_DIRNAME
    shutil.copytree(source, stage_pkg,
                    ignore=shutil.ignore_patterns("__pycache__", ".state"))

    backups = stage_pkg / L.BACKUP_DIRNAME
    backups.mkdir(parents=True, exist_ok=True)
    backup_rel = "%s/%s.%s" % (L.BACKUP_DIRNAME, entry_name, ts)
    L.atomic_write_bytes(stage_pkg / backup_rel, entry_bytes)

    if pre_existing.get("backed_up"):
        pre_rel = "%s/%s-preexisting.%s" % (L.BACKUP_DIRNAME, PKG_DIRNAME, ts)
        shutil.copytree(host_home / PKG_DIRNAME, stage_pkg / pre_rel)
        pre_existing["backup"] = pre_rel
    return stage, backup_rel


def swap_into_place(stage_pkg: Path, host_home: Path):
    """原子改名就位。旧树挪到一边，成功后再删，失败就搬回来。"""
    live = host_home / PKG_DIRNAME
    old = None
    if live.exists():
        old = host_home / (".hubcore-old-" + L.stamp())
        L.rmtree_quiet(old)
        os.rename(live, old)
    os.replace(stage_pkg, live)
    return old


# ---------------------------------------------------------------- 自检

def self_check(pkg_root: Path, manifest: dict, workdir: Path) -> list:
    """抽 3 个文件对 sha + 真跑 ctxiso status + state.py --help。任一不过就抛。"""
    problems = []
    # 产物里不该有任何字节码：.pyc 头里的 co_filename 记着编译时的绝对源码路径，
    # 打进包发出去就是把构建机信息带出去，且无法事后剔除。
    bad = L.find_bytecode(pkg_root)
    if bad:
        problems.append("产物里有 %d 个字节码/缓存目录：%s" % (
            len(bad), "、".join(str(p.relative_to(pkg_root)) for p in bad[:5])))
    else:
        print("  [ ok ] 无 .pyc / __pycache__")

    rows = manifest["files"]
    picks = []
    if rows:
        for i in (0, len(rows) // 2, len(rows) - 1):
            if i < len(rows) and rows[i] not in picks:
                picks.append(rows[i])
    for row in picks:
        p = pkg_root / row["path"]
        if not p.is_file():
            problems.append("缺文件：%s" % row["path"])
            continue
        got = L.sha256_file(p)
        if got != row["sha256"]:
            problems.append("sha 不符：%s 期望 %s 实得 %s" % (row["path"], row["sha256"][:12], got[:12]))
        else:
            print("  [ ok ] sha 相符：%s" % row["path"])
    if not picks:
        problems.append("清单里一个文件都没有")

    env = L.child_env(pkg_root)
    prod = L.make_product_fixture(workdir)
    py = sys.executable

    rc = L.run_child([py, "-m", "ctxiso", "status", "--product", prod], pkg_root, env)
    if rc != 0:
        problems.append("ctxiso status 退出码 %d" % rc)
    else:
        print("  [ ok ] ctxiso status 跑通")

    rc = L.run_child([py, pkg_root / "tools" / "state.py", "--help"], pkg_root, env)
    if rc != 0:
        problems.append("state.py --help 退出码 %d" % rc)
    else:
        print("  [ ok ] state.py --help 跑通")
    return problems


# ---------------------------------------------------------------- 回滚

def rollback(pkg_root_live: Path, host_home: Path, entry_path: Path,
             entry_before: bytes, entry_existed: bool, old_tree, stage: Path, why: str):
    print()
    print("自检没过 -> 整体回滚：%s" % why)
    # 1. 包树删净
    L.rmtree_quiet(pkg_root_live)
    # 2. 装前的旧树搬回来（如果有）
    if old_tree is not None and old_tree.exists():
        os.rename(old_tree, host_home / PKG_DIRNAME)
        print("  · 已把装前的 %s/ 搬回来" % PKG_DIRNAME)
    else:
        print("  · 已删掉 %s/，没有半装残留" % PKG_DIRNAME)
    # 3. 入口文件还原
    if entry_existed:
        L.atomic_write_bytes(entry_path, entry_before)
        print("  · 入口文件已按装前字节还原：%s" % entry_path)
    elif entry_path.exists():
        entry_path.unlink()
        print("  · 装前不存在入口文件，已删掉新建的：%s" % entry_path)
    L.rmtree_quiet(stage)
    print("  · 临时目录已清：%s" % stage.name)
    now = L.sha256_bytes(entry_path.read_bytes()) if entry_path.is_file() else ""
    want = L.sha256_bytes(entry_before) if entry_existed else ""
    print("  · 入口文件当前 sha256=%s 装前 sha256=%s -> %s"
          % (now[:16] or "(不存在)", want[:16] or "(不存在)", "一致" if now == want else "不一致！"))
    return 1


# ---------------------------------------------------------------- 主流程

def _install_unlocked(source: Path, host_home: Path, dry_run: bool = False,
            replace: bool = False, allow_running: bool = False,
            base_path: str = "", guest_path: str = "", hub_path: str = "",
            entry: str = "", with_marker: bool = True,
            keep_origin: bool = True) -> int:
    source = check_source(source)
    host_home = Path(host_home).expanduser().resolve()
    if not host_home.is_dir():
        raise InstallError("宿主家目录不存在：%s" % host_home)

    host_id = H.host_id_for(host_home)
    spec = H.resolve_host(host_home)
    entry_name = entry or (H._resolve_entry(host_home, spec) if spec else H.entry_name_for(host_home))
    entry_path = host_home / entry_name

    # 底线自检：标记块每轮都注入，12 块底线少一块都不许装。
    # 这是机器证明「底线真的在每轮里」，不是靠嘴说。
    if hub_path and not with_marker:
        raise InstallError("中枢卡是靠标记块写进去的：--hub 不能和 --no-marker 一起用。")
    hub_name, hub_hosts, hub_content = "", "", ""
    if hub_path:
        hub_name, hub_hosts, hub_content = read_hub_card(Path(hub_path))
        block = L.marker_block(str(host_home), rule_text=hub_content)
    else:
        block = L.marker_block(str(host_home))
        gaps = L.bottom_line_gaps(block)
        if gaps:
            raise InstallError(
                "标记块底线自检没过，缺 %d 块，拒绝装（一个字节都还没写）：\n%s"
                % (len(gaps),
                   "\n".join("  · %s：缺 %s" % (n, "、".join(m)) for n, m in gaps)))
    marker_bytes = len(block.encode("utf-8")) if with_marker else 0
    if marker_bytes > L.MARKER_BUDGET:
        raise InstallError("标记块全文 %d 字节 > 上限 %d 字节，拒绝装。"
                           % (marker_bytes, L.MARKER_BUDGET))

    # 底模：有就读 + 验，没有就空着。顺序固定：原文 / 底模块 / 指引块 / 标记块。
    base_name, base_hosts, base_content = "", "", ""
    base_block = ""
    if base_path:
        base_name, base_hosts, base_content = read_base_card(Path(base_path))
        base_block = L.render_base_block(base_name, base_hosts, base_content)
    guest_name, guest_content = "", ""
    guest_block = ""
    if guest_path:
        _, guest_name, _, guest_content = read_card(Path(guest_path), "guest")
        guest_block = L.render_guest_block(guest_name, guest_content)

    if not (with_marker or base_block or guest_block):
        raise InstallError("三段都没选，没什么可写的。")

    running_detail = check_idle(host_home, allow_running)
    pre_existing = check_target(host_home, replace)

    entry_existed = entry_path.is_file()
    entry_before = entry_path.read_bytes() if entry_existed else b""
    # 宿主原文件有没有 UTF-8 BOM，必须原样带回去——改编码就是改了主人的文件。
    entry_bom = L.has_bom(entry_before)
    sha_before = L.sha256_bytes(entry_before) if entry_existed else ""
    if entry_existed:
        try:
            original_text = (entry_before[len(L.BOM):] if entry_bom else entry_before).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InstallError("入口文件不是有效的 UTF-8，拒绝改写以保护原字节：%s" % entry_path) from exc
    else:
        original_text = ""
    # 上一次装进去的块长什么样，清单里有指纹：装了中枢内核卡时正文是那张卡，
    # 不拿这份指纹就认不出旧块（重装会叠块、卸回会摘不掉）。
    prev_body_sha = L.installed_marker_body_sha(host_home)
    had_marker = L.has_marker(original_text, prev_body_sha) if entry_existed else False

    # 备份里到底存什么、这次算不算「覆盖」，在动手之前一次算清：
    #   · 上一轮就是覆盖模式 -> 真原文只在上一棵树的备份里，原样接过来，一直管到卸回；
    #   · 这次才开覆盖       -> 存的是**摘掉我们自己旧块之后的原文**（不然卸回把旧块也还回来）；
    #   · 非覆盖             -> 装前原字节，逐字节。
    prev_origin = _previous_origin_backup(host_home, entry_name) if entry_existed else None
    if prev_origin is not None:
        backup_bytes = prev_origin[0].read_bytes()
        origin_dropped = True
    elif not keep_origin:
        fallback, _ = L.strip_marker(original_text, prev_body_sha)
        fallback, _ = L.strip_base_block(fallback)
        fallback, _ = L.strip_guest_block(fallback)
        backup_bytes = L.encode(fallback, entry_bom)
        origin_dropped = True
    else:
        backup_bytes = entry_before
        origin_dropped = False

    print("=" * 68)
    print("装 hubcore 进 %s" % host_home)
    print("=" * 68)
    print("  安装包：%s" % source)
    print("  宿主：  %s（%s）" % (host_id, entry_name))
    print("  入口文件：%s%s" % (entry_path, "" if entry_existed else "（装前不存在，将新建）"))
    print("  标记块：%d 字节（底线正文 %d / 上限 %d），%d 块底线逐条短语自检全在"
          % (len(block.encode("utf-8")), marker_bytes, L.MARKER_BUDGET, len(L.BOTTOM_LINES)))
    if base_block:
        print("  底模：%s（%d 字节 / 上限 %d）%s"
              % (base_name, len(base_block.encode("utf-8")), L.BASE_BUDGET,
                 ("，适用：" + base_hosts) if base_hosts else ""))
    if guest_block:
        print("  指引：%s（%d 字节成品，原样粘）"
              % (guest_name, len(guest_block.encode("utf-8"))))
    print("  活进程：%s" % running_detail)
    print("  已有标记块：%s -> 重复安装会先摘旧块再插新块" % ("是" if had_marker else "否"))
    if origin_dropped and not keep_origin:
        print("  宿主原文：覆盖模式 —— 原有文本整段丢弃，原字节存进 %s/，卸回时合并还原"
              % L.BACKUP_DIRNAME)
    elif origin_dropped:
        print("  宿主原文：上一轮就是覆盖模式，原文已经不在文件里（只在 %s/ 备份里）；"
              "这次仍按备份管到底，卸回时还原原文" % L.BACKUP_DIRNAME)
    else:
        print("  宿主原文：保留，跟在我们的几段前面")
    print("  本次写：%s" % "、".join(
        [x for x in [("中枢标记块" if with_marker else None),
                     ("底模 " + base_name) if base_block else None,
                     ("指引 " + guest_name) if guest_block else None] if x]) or "（三段都没选，什么都不会写）")
    if pre_existing.get("supersede"):
        print("  已装过：将覆盖旧安装（旧树成功后才删）")
    elif pre_existing.get("backed_up"):
        print("  已存在非本系统的 %s/：将备份后替换" % PKG_DIRNAME)
    print()

    if dry_run:
        rows = L.file_rows(source)
        total = sum(r["bytes"] for r in rows)
        print("[试运行] 不会写任何文件。将要做：")
        print("  1. 备份 %s -> %s/%s/.<时间戳>" % (entry_path, PKG_DIRNAME, entry_name))
        print("  2. 写 %s/：%d 个文件，%d 字节" % (PKG_DIRNAME, len(rows) + 1, total))
        print("  3. 在 %s 按顺序写标记块（%d 字节）%s%s，%s"
              % (entry_path, len(L.marker_block(host_home).encode()),
                 (" + 底模块 %s" % base_name) if base_block else "",
                 (" + 指引 %s" % guest_name) if guest_block else "",
                 ("原文整段丢弃（覆盖模式，原字节已进备份）" if origin_dropped else "原文不动")))
        print("  4. 写 %s/%s" % (PKG_DIRNAME, L.MANIFEST_NAME))
        print("  5. 自检：抽 3 个文件对 sha + 跑 ctxiso status + 跑 state.py --help")
        print("  6. 任一失败 -> 整体回滚")
        return 0

    ts = L.stamp()
    stage = None
    old_tree = None
    try:
        stage, backup_rel = stage_tree(source, host_home, ts, entry_name,
                                       backup_bytes, pre_existing)
        if origin_dropped:
            # 清单里的「装前 sha」要对着真正被丢掉的那份原文，卸回时的比对才有意义。
            _bp = stage / PKG_DIRNAME / backup_rel
            if _bp.is_file():
                sha_before = L.sha256_bytes(_bp.read_bytes())
        old_tree = swap_into_place(stage / PKG_DIRNAME, host_home)
    except BaseException as exc:
        if stage:
            L.rmtree_quiet(stage)
        if old_tree is not None and old_tree.exists():
            os.rename(old_tree, host_home / PKG_DIRNAME)
        raise InstallError("写包树失败：%s\n  已还原，没有半装。" % exc)

    live = host_home / PKG_DIRNAME
    try:
        # 4. 入口文件最前面插标记块
        # 必须走 L.decode：它会把 BOM 摘成「没有 BOM 的文本」，
        # 写回时再由 L.encode(text, entry_bom) 补回一个 BOM。
        # 直接 original.decode() 会把 BOM 变成正文里的 U+FEFF 字符，
        # 写回时又补上 BOM 字节 -> 双 BOM，卸完和原文差 3 个字节。
        new_text = L.insert_marker(original_text, str(host_home), base_block, guest_block,
                                   with_marker, marker_block_text=block,
                                   keep_origin=keep_origin, strip_body_sha=prev_body_sha)
        L.atomic_write_bytes(entry_path, L.encode(new_text, entry_bom))
        sha_after = L.sha256_bytes(entry_path.read_bytes())

        # 5. 写清单
        manifest = {
            "format": 1,
            "installed_at": L.now_iso(),
            "host": host_id,
            "host_home": str(host_home),
            "package": {
                "name": L.PACKAGE_NAME,
                "version": L.PACKAGE_VERSION,
                "file_count": len(L.list_package_files(live)),
                "total_bytes": sum((live / r).stat().st_size
                                   for r in L.list_package_files(live)),
            },
            "entry_file": {
                "path": entry_name,
                "existed_before": entry_existed,
                "marker_written": bool(with_marker),
                "marker_body_sha256": L.marker_body_fingerprint(block) if with_marker else "",
                "origin_dropped": bool(origin_dropped),
                "marker_begin": L.MARKER_BEGIN,
                "marker_end": L.MARKER_END,
                "backup": backup_rel,
                "sha_before": sha_before,
                "sha_after": sha_after,
                "base": {
                    "name": base_name,
                    "hosts": base_hosts,
                    "sha256": L.sha256_bytes(base_block.encode("utf-8")) if base_block else "",
                    "card_sha256": L.sha256_bytes(base_content.encode("utf-8")) if base_block else "",
                    "begin": L.BASE_BEGIN,
                    "end": L.BASE_END,
                } if base_block else None,
                "guest": {
                    "name": guest_name,
                    "sha256": L.sha256_bytes(guest_block.encode("utf-8")) if guest_block else "",
                    "card_sha256": L.sha256_bytes(guest_content.encode("utf-8")) if guest_block else "",
                    "begin": L.GUEST_BEGIN,
                    "end": L.GUEST_END,
                } if guest_block else None,
                "hub": {
                    "name": hub_name,
                    "hosts": hub_hosts,
                    "sha256": L.sha256_bytes(block.encode("utf-8")),
                    "card_sha256": L.sha256_bytes(hub_content.encode("utf-8")) if hub_content else "",
                } if hub_name else None,
            },
            "pre_existing_hub": pre_existing,
            "files": L.file_rows(live),
            "uninstall": {
                "command": "python %s/uninstall.py --host-home %s" % (live, host_home),
                "removes": ["%s/" % PKG_DIRNAME,
                            "入口文件 %s 里的标记块（%s … %s）" % (entry_name, L.MARKER_BEGIN, L.MARKER_END)]
                           + (["入口文件里的底模块（%s … %s）" % (L.BASE_BEGIN, L.BASE_END)]
                              if base_block else [])
                           + (["入口文件里的指引块（%s … %s）" % (L.GUEST_BEGIN, L.GUEST_END)]
                              if guest_block else []),
                "keeps": ["宿主家目录下除 %s/ 以外的一切" % PKG_DIRNAME,
                          "入口文件主人的原文"],
                "restores_entry_file": True,
            },
        }
        L.write_manifest(live, manifest)
        print("  [ ok ] 包树就位：%s" % live)
        print("  [ ok ] 标记块已插入%s%s（装前入口文件 %d 字节；这一轮摘掉的只有我们自己上一轮写的块）"
              % ((" + 底模 %s" % base_name) if base_block else "",
                 (" + 指引 %s" % guest_name) if guest_block else "", len(entry_before)))
        print("  [ ok ] 清单已写：%s/%s" % (PKG_DIRNAME, L.MANIFEST_NAME))

        # 6. 自检
        print("  自检中…")
        workdir = host_home / (".hubcore-check-" + ts)
        try:
            problems = self_check(live, manifest, workdir)
        finally:
            L.rmtree_quiet(workdir)
        if problems:
            return rollback(live, host_home, entry_path, entry_before,
                            entry_existed, old_tree, stage, "；".join(problems))
    except BaseException as exc:
        return rollback(live, host_home, entry_path, entry_before,
                        entry_existed, old_tree, stage, "写盘被拒：%s" % exc)

    if old_tree is not None and old_tree.exists():
        L.rmtree_quiet(old_tree)
        print("  [ ok ] 旧的安装树已删")
    L.rmtree_quiet(stage)

    print()
    print("装好了。自证跑一遍（verify 是打包工具，不随包走）：")
    print("  python %s --host-home %s" % (HERE / "verify.py", host_home))
    print("一键卸（这份随包走，装好后就在中枢根里）：")
    print("  python %s/uninstall.py --host-home %s" % (live, host_home))
    return 0


def install(source: Path, host_home: Path, dry_run: bool = False,
            replace: bool = False, allow_running: bool = False,
            base_path: str = "", guest_path: str = "", hub_path: str = "",
            entry: str = "", with_marker: bool = True,
            keep_origin: bool = True) -> int:
    """在检查和写盘全程持有宿主锁，挡住并发装/卸互相覆盖。"""
    host_home = Path(host_home).expanduser().resolve()
    try:
        with L.operation_lock(host_home):
            return _install_unlocked(source, host_home, dry_run, replace,
                                     allow_running, base_path, guest_path, hub_path,
                                     entry, with_marker, keep_origin)
    except RuntimeError as exc:
        raise InstallError(str(exc)) from exc


def main(argv=None):
    ap = argparse.ArgumentParser(prog="install.py", description="把 hubcore 装进一个宿主家目录")
    ap.add_argument("--source", required=True, help="安装包目录（pack.py 的产物）")
    ap.add_argument("--host-home", required=True, help="宿主家目录")
    ap.add_argument("--dry-run", action="store_true", help="只报计划，不写任何文件")
    ap.add_argument("--replace", action="store_true", help="宿主已有非本系统的 hub/ 时也装（先备份）")
    ap.add_argument("--allow-running", action="store_true", help="宿主正在跑也硬装，自己担责")
    ap.add_argument("--base", default="", help="底模卡片文件（04-console/cards/ 下的卡），装完顺序：标记块/底模块/原文/指引块")
    ap.add_argument("--guest", default="", help="技能指引卡片文件（成品文本原样粘，拼在最后）")
    ap.add_argument("--hub", default="", help="中枢内核卡片文件（04-console/cards/ 下的 hub 卡）")
    ap.add_argument("--entry", default="", help="入口文件名（如 CLAUDE.md / AGENTS.md）")
    ap.add_argument("--replace-origin", action="store_true",
                    help="覆盖模式：丢弃宿主入口文件原有文本，只写我们的三段。原文本在 .backups/ 里逐字节存着，卸回时合并还原。")
    ap.add_argument("--no-marker", action="store_true", help="不写中枢标记块，只写底模与指引两段")
    args = ap.parse_args(argv)
    try:
        return install(args.source, args.host_home, args.dry_run,
                       args.replace, args.allow_running, args.base, args.guest, args.hub,
                       args.entry, not args.no_marker,
                       keep_origin=not args.replace_origin)
    except InstallError as exc:
        print("装不了：\n  %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
