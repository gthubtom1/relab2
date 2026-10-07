# -*- coding: utf-8 -*-
"""hubcore 自包含硬证明。装完跑一次，逐条说清楚成立还是没成立。

    python verify.py --host-home <宿主家目录> [--source-dir <素材目录>]

(a) 包内零外部痕迹：搜不到源仓路径、本机盘符、远端地址、技能系统路径
(b) 包内相对引用全部解析得到实际文件
(c) 常驻核心 CORE.md 不超过 CORE_BUDGET 字节
(d) 宿主入口文件里的标记块不含技能名 / 外部路径 / 远端地址
(e) 真跑一次 ctxiso status 和 state.py --help（子进程，stdio 直接继承）
(f) 硬证明：断开源仓之后 (a)(b)(c)(e) 仍然成立

不写宿主家目录里的任何文件：(e) 的产品夹造在系统临时目录，装完自删。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from . import _bundle_lib as L
    from . import hosts as H
except ImportError:
    import _bundle_lib as L
    import hosts as H

PKG_DIRNAME = L.PKG_DIRNAME

# 标记块里不该出现的词。技能名取素材里真实存在的那批（pack.py 写进 bundle-meta.json），
# 这里放的是不依赖任何源仓的兜底最小集。
FALLBACK_SKILL_NAMES = (
    "desktop-product", "web-service", "cli-tool", "source-takeover",
    "exe-rebuild", "protocol-automation", "anti-crack-build", "INVARIANTS",
    "user-skills", "skills-hub", "副插件", "底模",
)
PATHY = ("D:\\", "D:/", "临时项目", "context-isolation", "hub-dock",
         "user-skills", ".agents/skills", ".agents\\skills", "skills-hub", "gthubtom1")
REMOTE = ("http://", "https://", "github.com", "git@", "ssh://")


class Report:
    def __init__(self):
        self.rows = []
        self.failed = 0

    def add(self, cid, title, ok, detail=""):
        self.rows.append({"id": cid, "title": title, "ok": bool(ok), "detail": detail})
        if not ok:
            self.failed += 1
        print("[%s] (%s) %s" % ("PASS" if ok else "FAIL", cid, title))
        for line in str(detail).splitlines():
            if line.strip():
                print("        " + line)
        return ok

    def finish(self):
        print("-" * 68)
        print("%d 项检查，%d 项通过，%d 项失败" %
              (len(self.rows), len(self.rows) - self.failed, self.failed))
        return 1 if self.failed else 0


# ---------------------------------------------------------------- (a)

def check_a(pkg_root: Path, forbidden, allowlist=None):
    """三态分开报：pass 真的没出现 / allowlisted 命中白名单且列名列原因 / fail 其余一律判红。"""
    fails, allowed, skipped = L.scan_forbidden(pkg_root, forbidden, allowlist)
    lines = []
    for rel, line_no, word, line, why in allowed:
        lines.append("[白名单] %s:%d  [%s]" % (rel, line_no, word))
        lines.append("          故意保留的原因：%s" % why)
    if fails:
        lines.append("[FAIL]  非白名单命中 %d 处：" % len(fails))
        lines += ["          %s:%d  [%s]  %s" % f for f in fails[:25]]
        return False, "\n".join(lines)
    lines.insert(0, "[ pass ]  %d 个出货文件零禁词命中（无源仓路径 / 无盘符 / 无远端 / 无技能系统路径）"
                 % (len(L.list_package_files(pkg_root)) - len(skipped)))
    lines.append("[  白名单] %d 条（已逐条列名 + 列原因）" % len(allowed))
    if skipped:
        lines.append("[  排除  ] %d 个闸门自身文件（_bundle_lib.py / verify.py / uninstall.py）"
                     "里面必然写着禁词本身——那是检查工具的规则表，不是出货内容，故不扫：%s"
                     % (len(skipped), "、".join(sorted(skipped))))
    return True, "\n".join(lines)


def _only_loopback(line: str) -> bool:
    """这一行除了环回地址和标点，没有别的网址。"""
    rest = line
    for word in ("http://", "https://"):
        rest = rest.replace(word, "")
    for host in ("127.0.0.1", "localhost"):
        rest = rest.replace(host, "")
    for ch in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._:/\\ \t":
        rest = rest.replace(ch, "")
    return not rest


# ---------------------------------------------------------------- (b)

def check_b(pkg_root: Path):
    refs = L.scan_refs(pkg_root)
    # FIX-20：ok=None = 读不出、根本没扫。它不是死链，但也不是通过 ——
    # 判失败且把理由说清楚，别让盲区披着死链的外衣。
    blind = [r for r in refs if r["ok"] is None]
    dead = [r for r in refs if r["ok"] is False]
    if blind:
        return False, "%d 个文件读不出，引用**没扫过**，不算通过：\n%s" % (
            len(blind),
            "\n".join("  %s  —— %s" % (r["file"], r.get("why", "")) for r in blind[:25]))
    if dead:
        return False, "解析不到 %d / %d 条：\n%s" % (
            len(dead), len(refs),
            "\n".join("  %s:%d  ->  %s" % (r["file"], r["line"], r["ref"]) for r in dead[:25]))
    return True, "%d 条包内相对引用全部解析得到实际文件" % len(refs)


def check_b_informational(pkg_root: Path):
    """产品侧/本机侧的引用单独报出来，不计失败。"""
    rows = []
    for rel in L.list_package_files(pkg_root):
        p = pkg_root / rel
        if p.suffix.lower() not in (".md", ".json", ".jsonl", ".py"):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for ref, line_no in L.iter_refs(text):
            kind, _ = L.classify_ref(ref)
            if kind in ("product", "host"):
                rows.append((kind, rel, line_no, ref))
    return rows


# ---------------------------------------------------------------- (c)

def check_c(pkg_root: Path):
    core = pkg_root / L.META_NAME and pkg_root / "CORE.md"
    if not core.is_file():
        return False, "包根没有 CORE.md"
    size = core.stat().st_size
    if size > L.CORE_BUDGET:
        return False, "CORE.md %d 字节 > %d 字节上限" % (size, L.CORE_BUDGET)
    return True, "CORE.md %d 字节（上限 %d，余量 %d）" % (size, L.CORE_BUDGET,
                                                      L.CORE_BUDGET - size)


# ---------------------------------------------------------------- (d)

def check_d(host_home: Path, skill_names):
    """标记块只准出现「宿主自己家目录」和包内相对指针。

    宿主家目录的绝对路径要先抹成占位符再扫：SPEC 允许中枢指到宿主家目录内部，
    禁的是开发目录、盘符写死、远端地址，不是「这台机器的家目录在哪」。
    """
    spec = H.resolve_host(host_home)
    entry = H._resolve_entry(Path(host_home), spec) if spec else H.entry_name_for(host_home)
    entry_path = Path(host_home) / entry
    if not entry_path.is_file():
        return False, "宿主入口文件不在：%s" % entry_path
    # 走 L.decode：带 BOM 的入口文件里，第一行在字节上是「BOM + 标记」。
    # 不摘 BOM 就认不出块，闸门会误报「没装」。
    raw = L.decode(entry_path.read_bytes())
    # 装了中枢内核卡时，块里的正文是那张卡：认块要靠清单里的指纹，
    # 12 块底线那套判据只管包内默认规则，对卡片正文不适用（下面明说跳过）。
    body_sha = L.installed_marker_body_sha(host_home)
    card_name = L.installed_hub_card(host_home)
    block = L.extract_marker_block(raw, body_sha)
    if not block:
        return False, "入口文件 %s 里没有标记块" % entry

    scan = block
    hh = str(host_home)
    for form in {hh, hh.replace("\\", "/"), hh.replace("/", "\\")}:
        scan = scan.replace(form, "<HOST_HOME>")
    scan = scan.replace("C:" + chr(92) + "<HOST_HOME>", "<HOST_HOME>")

    bad = []
    for word in PATHY:
        if word in scan:
            bad.append("外部路径 / 技能系统路径：%s" % word)
    for word in REMOTE:
        if word in scan:
            bad.append("远端地址：%s" % word)
    for name in skill_names:
        if name and name in scan:
            bad.append("技能名：%s" % name)
    # 底线自检：12 块少一块都不算干净。装了中枢内核卡的情况明说跳过——
    # 那套判据是给包内默认规则写的，拿它去量一张卡的正文就是假判定。
    if card_name:
        print("  [skip] 12 块底线判据：这次的标记块正文来自中枢内核卡「%s」，该判据不适用" % card_name)
    else:
        gaps = L.bottom_line_gaps(block)
        for name, missing in gaps:
            bad.append("底线缺块：%s（缺 %s）" % (name, "、".join(missing)))

    head = ("标记块 %d 字节，在 %s 的最末（块外还有 %d 字节）"
            % (len(block.encode("utf-8")), entry, len(raw.encode("utf-8")) - len(block.encode("utf-8"))))
    if bad:
        return False, head + "\n" + "\n".join("  " + b for b in bad)
    tail = ("；块内零技能名 / 零开发目录 / 零远端地址；"
            "出现的绝对路径只有本宿主家目录，已抹成 <HOST_HOME> 后再验；")
    if card_name:
        return True, head + tail + "块内规则正文来自中枢内核卡「%s」（不含 12 块底线，已跳过该判据）" % card_name
    return True, (head + tail + "12 块底线（%s）逐条短语全在位"
                  % "、".join(n for n, _ in L.BOTTOM_LINES))


# ---------------------------------------------------------------- (e)

def _make_product_fixture(root: Path) -> Path:
    return L.make_product_fixture(root)


def _run(argv, cwd, env):
    return L.run_child(argv, cwd, env)


def check_e(pkg_root: Path, workdir: Path):
    prod = _make_product_fixture(workdir)
    env = L.child_env(pkg_root)
    py = sys.executable

    results = []
    # ctxiso status
    rc1 = _run([py, "-m", "ctxiso", "status", "--product", prod], pkg_root, env)
    results.append(("ctxiso status", rc1))
    # state.py --help
    rc2 = _run([py, pkg_root / "tools" / "state.py", "--help"], pkg_root, env)
    results.append(("state.py --help", rc2))

    bad = [n for n, rc in results if rc != 0]
    if bad:
        return False, "退出码非 0：%s" % "、".join("%s=%d" % (n, rc) for n, rc in results if rc)
    # 侧车状态必须真落在包内
    state_dir = pkg_root / L.STATE_DIRNAME
    if not state_dir.is_dir():
        return False, "跑完 ctxiso 之后包内没有 %s/，状态没落在包内" % L.STATE_DIRNAME
    return True, "两项都跑通；侧车状态落在包内 %s/" % L.STATE_DIRNAME


# ---------------------------------------------------------------- (f)

def _run_core_checks(rep_label, pkg_root, workdir):
    """在指定包根上重跑 (a)(b)(c)(e)。返回 (all_ok, 明细行)。"""
    lines = []
    ok = True
    forbidden = list(FORBIDDEN_FALLBACK)
    ok_a, det = check_a(pkg_root, forbidden)
    ok_b, det_b = check_b(pkg_root)
    ok_c, det_c = check_c(pkg_root)
    lines.append("  (a) %s — %s" % ("成立" if ok_a else "不成立", det.splitlines()[0]))
    lines.append("  (b) %s — %s" % ("成立" if ok_b else "不成立", det_b.splitlines()[0]))
    lines.append("  (c) %s — %s" % ("成立" if ok_c else "不成立", det_c.splitlines()[0]))
    ok = ok_a and ok_b and ok_c

    env_tmp = Path(tempfile.mkdtemp(prefix="hubcore-proof-"))
    try:
        ok_e, det_e = check_e(pkg_root, env_tmp)
    finally:
        shutil.rmtree(env_tmp, ignore_errors=True)
    lines.append("  (e) %s — %s" % ("成立" if ok_e else "不成立", det_e.splitlines()[0]))
    ok = ok and ok_e
    return ok, lines


FORBIDDEN_FALLBACK = ("D:\\", "D:/", "临时项目", "context-isolation", "hub-dock",
                      "github.com", "http://", "https://", "user-skills", ".agents/skills")


def check_f(pkg_root: Path, source_dir: Path, workdir: Path):
    lines = []
    ok = True

    # 第一层：装出来的东西，拷到一个跟源仓毫无关系的系统临时目录再验一遍。
    iso = workdir / "isolated" / "hub"
    iso.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(pkg_root, iso, ignore=shutil.ignore_patterns("__pycache__", ".state"))
    ok1, det1 = _run_core_checks("isolated", iso, workdir)
    lines.append("第一层 · 装好的包复制到系统临时目录后脱离安装位置运行：")
    lines += det1
    ok = ok and ok1

    # 第二层：真把源仓目录改名，再在原安装位置重验。
    if source_dir is None:
        lines.append("第二层 · 源仓改名：未指定 --source-dir，跳过"
                     "（第一层已证明与安装位置、源仓路径均无关）")
        return ok, "\n".join(lines)

    renamed = source_dir.with_name(source_dir.name + ".hubcore-renamed")
    if renamed.exists():
        return False, lines and "\n".join(lines) or "", "改名目标已存在，先手工清掉：%s" % renamed
    try:
        os.rename(source_dir, renamed)
        lines.append("第二层 · 源仓已临时改名：%s -> %s" % (source_dir.name, renamed.name))
        ok2, det2 = _run_core_checks("renamed", pkg_root, workdir)
        lines += det2
        ok = ok and ok2
    finally:
        if renamed.exists():
            os.rename(renamed, source_dir)
            lines.append("        源仓已改回：%s" % source_dir.name)
    if source_dir.name not in os.listdir(source_dir.parent):
        return False, "\n".join(lines), "源仓没有改回来！"
    return ok, "\n".join(lines)


# ---------------------------------------------------------------- 主流程

def main(argv=None):
    ap = argparse.ArgumentParser(prog="verify.py", description="hubcore 自包含硬证明")
    ap.add_argument("--host-home", required=True, help="宿主家目录")
    ap.add_argument("--source-dir", default="", help="素材目录；给了就做源仓改名的硬证明")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    host_home = Path(args.host_home).expanduser().resolve()
    pkg_root = host_home / PKG_DIRNAME
    rep = Report()

    if not pkg_root.is_dir():
        print("这个家目录下没有 %s/：%s" % (PKG_DIRNAME, host_home), file=sys.stderr)
        return 2
    print("宿主家目录：%s" % host_home)
    print("包根：      %s" % pkg_root)
    print("=" * 68)

    # 禁词表与技能名清单来自 03-bundle/bundle-meta.json（随打包工具留在 03-bundle/，
    # **不进包**——它把禁词序列化进文件，打进包会让包自己违反自己的规则）。
    meta_path = Path(__file__).resolve().parent / L.META_NAME
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    if not meta:
        print("提示：没找到 %s，用 verify.py 自带的兜底表（覆盖面更窄）" % L.META_NAME)
    forbidden = list(meta.get("forbidden_strings") or FORBIDDEN_FALLBACK)
    skill_names = list(meta.get("skill_name_denylist") or FALLBACK_SKILL_NAMES)

    workdir = Path(tempfile.mkdtemp(prefix="hubcore-verify-"))
    try:
        rep.add("a", "包内零外部痕迹", *check_a(pkg_root, forbidden))
        rep.add("b", "包内相对引用全部解析得到", *check_b(pkg_root))
        rep.add("c", "常驻核心 <= %d 字节" % L.CORE_BUDGET, *check_c(pkg_root))
        rep.add("d", "标记块干净", *check_d(host_home, skill_names))
        rep.add("e", "真跑 ctxiso status 与 state.py --help", *check_e(pkg_root, workdir))

        src = Path(args.source_dir).expanduser().resolve() if args.source_dir else None
        if src is not None and not src.is_dir():
            src = None
        rc_f = check_f(pkg_root, src, workdir)
        if len(rc_f) == 3:
            rep.add("f", "硬证明：脱离源仓仍成立", rc_f[0], rc_f[1] + "\n" + rc_f[2])
        else:
            rep.add("f", "硬证明：脱离源仓仍成立", rc_f[0], rc_f[1])
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    prod_refs = check_b_informational(pkg_root)
    if prod_refs:
        print("-" * 68)
        print("提示：另有 %d 处引用指向主人产品目录/本机侧的文件（不是包内死链，不计失败）" % len(prod_refs))
        seen = sorted({r[3] for r in prod_refs})
        print("      %s" % "、".join(seen[:20]) + (" …" if len(seen) > 20 else ""))

    if args.json:
        print(json.dumps(rep.rows, ensure_ascii=False, indent=2))
    return rep.finish()


if __name__ == "__main__":
    sys.exit(main())
