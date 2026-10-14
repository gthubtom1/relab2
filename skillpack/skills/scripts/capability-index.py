#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""capability-index.py —— 按**能力**发现本机工具，而不是按工具名背清单。

为什么存在（2026-10-15）：
  原设计靠 `Resolve-ReverseToolSpec -Name <id>` + 一张 36 条的**别名表**（`_map.json`）。
  换一台电脑、装的是另外五个工具、名字我们没见过 —— 那张表就废了，只能人肉打补丁。
  主人要的是：**任何机器、任何同类软件，只要装在机器上，就能被认出来、能被调用。**

  所以本脚本不看「工具叫什么」，只看「它能干什么」：

  1. **扫描**：PATH 上的目录 + 工具根 `<工具根>` 递归（限深度、排除依赖/缓存目录）。
  2. **归类**：先按**名字/路径规则**判（规则表，不是清单）；判不出的，跑一次
     `-h/--help/-?/--version`（限时 2s）抓关键词再判 —— 所以**没见过的新工具也能归位**。
  3. **产出**：能力索引 JSON（落在机器状态目录，**不入库**）。
  4. **查询**：`find(capability)` → 本机能干这件事的工具清单（按证据强度排序）。

用法：
  python capability-index.py --scan                 # 重建索引并打印摘要
  python capability-index.py --find firmware-unpack  # 问「谁能解固件」
  python capability-index.py --json                 # 整份索引
  python capability-index.py --list-capabilities    # 能力词表
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------- 能力词表
# id -> (中文名, 属于哪个战场)
CAPABILITIES: dict[str, tuple[str, str]] = {
    "triage":          ("查壳/文件类型/熵值", "逆向"),
    "strings":         ("字符串抽取（含混淆串）", "逆向"),
    "static-decompile":("静态反编译/反汇编", "逆向"),
    "disasm-cli":      ("命令行反汇编/二进制分析", "逆向"),
    "dynamic-debug":   ("用户态动态调试", "逆向"),
    "kernel-debug":    ("内核/驱动调试", "逆向"),
    "memory-dump":     ("内存转储与 IAT 修复", "逆向"),
    "hook":            ("运行时插桩 / Hook", "逆向"),
    "unpack":          ("脱壳 / 自解压展开", "逆向"),
    "dotnet":          ("托管程序集反编译 / 去混淆", "逆向"),
    "binary-diff":     ("二进制差分 / 符号迁移", "逆向"),
    "rop":             ("ROP gadget 检索", "逆向"),
    "emulate":         ("模拟执行 / 符号执行", "逆向"),
    "capability-map":  ("能力点自动识别（ATT&CK 映射）", "逆向"),
    "apk":             ("APK 解包 / smali / 重打包", "移动"),
    "mobile-runtime":  ("移动端运行时插桩 / 绕证书固定", "移动"),
    "device-bridge":   ("设备桥接 / 投屏 / 截图", "移动"),
    "firmware-unpack": ("固件解包 / 文件系统提取", "固件"),
    "firmware-emulate":("固件仿真运行", "固件"),
    "hardware":        ("硬件接口（UART/JTAG/SPI）", "固件"),
    "portscan":        ("端口 / 服务 / 资产扫描", "渗透"),
    "websqli":         ("SQL 注入检测与利用", "渗透"),
    "webscan":         ("Web 漏洞扫描 / PoC 模板", "渗透"),
    "fuzz-web":        ("目录 / 参数 / 虚拟主机爆破", "渗透"),
    "crack":           ("口令 / 哈希破解", "渗透"),
    "yara":            ("YARA 规则匹配", "样本"),
    "capture":         ("抓包 / PCAP 解析", "协议"),
    "proxy":           ("中间人代理 / 改包", "协议"),
    "http-client":     ("HTTP 客户端 / API 调试", "协议"),
    "js-runtime":      ("JS 运行时 / 补环境", "协议"),
    "sdr":             ("射频 / SDR 信号", "无线"),
    "cloud":           ("云 / 容器 / K8s 审计", "云"),
    "sandbox":         ("沙箱 / 隔离执行", "通用"),
}

# ---------------------------------------------------------------- 识别规则（规则，不是清单）
# (正则, 能力 id, 证据说明)；对「可执行文件名 + 所在路径」匹配。
RULES: list[tuple[str, str, str]] = [
    # 查壳 / 字符串 / 能力点
    (r"(^|[\\/])diec?\.(exe|cmd|bat)$", "triage", "Detect It Easy"),
    (r"^die\.exe$", "triage", "Detect It Easy (GUI)"),
    (r"peid|exeinfope|protection_id", "triage", "PE 查壳器"),
    (r"^floss", "strings", "FLOSS"),
    (r"strings\.exe$", "strings", "strings"),
    (r"^capa", "capability-map", "capa"),
    # 静态反编译
    (r"^ida(64)?\.exe$|^idat(64)?(\.exe|\.cmd)$", "static-decompile", "IDA Pro"),
    (r"ghidra|analyzeHeadless", "static-decompile", "Ghidra"),
    (r"hopper", "static-decompile", "Hopper"),
    (r"binaryninja|^binja", "static-decompile", "Binary Ninja"),
    (r"^jeb", "static-decompile", "JEB"),
    (r"(^|[\\/])r2(bat)?$|radare2|^rabin2|^rahash2|^rasm2", "disasm-cli", "radare2 家族"),
    (r"objdump|readelf|^nm\.exe|dumpbin", "disasm-cli", "binutils"),
    (r"^llvm-objdump|otool", "disasm-cli", "LLVM/otool"),
    # 动态调试
    (r"x64dbg|x32dbg|x96dbg|^headless\.exe$", "dynamic-debug", "x64dbg"),
    (r"ollydbg", "dynamic-debug", "OllyDbg"),
    (r"windbg|(^|[\\/])cdb(\.exe|\.cmd)?$|(^|[\\/])kd\.exe$", "kernel-debug", "WinDbg/cdb"),
    (r"^gdb(\.exe)?$|pwndbg|gef", "kernel-debug", "GDB/pwndbg"),
    (r"lldb", "dynamic-debug", "lldb"),
    # 内存转储 / 脱壳
    (r"pe-sieve|hollows_hunter|^scylla|scyllahide|^pd64|^pd32|mega dumper", "memory-dump", "PE-sieve/Scylla"),
    (r"(^|[\\/])upx|unpacker|(^|[\\/])aspack|unpackme|ripper", "unpack", "UPX/解包器"),
    (r"^7z|winrar|bandizip|^unzip|^tar\.exe|^xz|^zstd", "unpack", "归档解包"),
    # Hook / 插桩
    (r"(^|[\\/])frida", "hook", "Frida"),
    (r"^x64dbg|injector|^ncat.*pipe", "hook", "注入器/管道"),
    (r"^dbghelp|detours|mhook", "hook", "Hook 库"),
    # 托管
    (r"dnspy|ilspy|dotpeek|justdecompile|^de4dot|^ilspycmd|^dotnet", "dotnet", ".NET 工具链"),
    # 二进制差分
    (r"bindiff|diaphora|ghidriff|^radiff2", "binary-diff", "差分工具"),
    # ROP / 模拟
    (r"ropgadget|^ropper|^rp\+\+|one_gadget", "rop", "ROP 检索"),
    (r"(^|[\\\\/])angr|(^|[\\\\/])unicorn|(^|[\\\\/])qiling|(^|[\\\\/])triton|(^|[\\\\/])z3", "emulate", "模拟/符号执行"),
    # 移动
    (r"^jadx|dex2jar|^jd-gui|^baksmali|^smali|apktool|^aapt|dexdump|androidkiller|^gda", "apk", "APK 工具链"),
    (r"objection|(^|[\\\\/])frida-(ps|trace)|magisk|^frida$", "mobile-runtime", "移动运行时"),
    (r"(^|[\\\\/])adb(\\.exe)?$|scrcpy|(^|[\\\\/])fastboot|(^|[\\\\/])idevice", "device-bridge", "设备桥接"),
    # 固件
    (r"binwalk|unblob|(^|[\\\\/])ubireader|(^|[\\\\/])jefferson|firmware-mod-kit", "firmware-unpack", "固件解包"),
    (r"firmadyne|^fat\.py|qemu-system|^qemu\.exe|firmware-analysis", "firmware-emulate", "固件仿真"),
    (r"openocd|^jlink|^stlink|^urjtag|flashrom|^esptool", "hardware", "硬件接口"),
    # 渗透
    (r"(^|[\\/])nmap(\.exe)?$|(^|[\\/])masscan|(^|[\\/])zmap", "portscan", "端口扫描"),
    (r"(^|[\\\\/])sqlmap", "websqli", "sqlmap"),
    (r"(^|[\\\\/])nuclei|(^|[\\\\/])nikto|(^|[\\\\/])wpscan|(^|[\\\\/])xsstrike|(^|[\\\\/])dalfox", "webscan", "Web 扫描"),
    (r"(^|[\\\\/])ffuf|(^|[\\\\/])gobuster|(^|[\\\\/])dirb|(^|[\\\\/])wfuzz|(^|[\\\\/])feroxbuster|(^|[\\\\/])dirsearch", "fuzz-web", "目录爆破"),
    (r"(^|[\\\\/])hashcat|(^|[\\\\/])john|(^|[\\\\/])hydra|(^|[\\\\/])medusa|(^|[\\\\/])ncrack", "crack", "口令破解"),
    (r"(^|[\\\\/])yara(64)?", "yara", "YARA"),
    # 抓包 / 协议
    (r"^tshark|^dumpcap|^capinfos|wireshark|^pktmon", "capture", "抓包/解析"),
    (r"mitmdump|mitmproxy|burp|^fiddler|charles", "proxy", "中间人代理"),
    (r"^curl$|^curl\.exe|^httpx|^httpie|^wget", "http-client", "HTTP 客户端"),
    (r"^node\.exe$|^deno$|^bun(\.exe)?$|quickjs", "js-runtime", "JS 运行时"),
    # 无线 / 云 / 沙箱
    (r"gnuradio|^urh|inspectrum|^hackrf|^rtl_|^ubertooth|kismet", "sdr", "SDR 工具"),
    (r"kubectl|^k9s|trivy|kube-bench|^aws|^az\.cmd|gcloud", "cloud", "云/K8s"),
    (r"cuckoo|capev2|^cape\.cmd|firejail|sandboxie", "sandbox", "沙箱"),
]

# help 文本关键词 → 能力（给「规则认不出的新工具」兜底）
HELP_HINTS: list[tuple[str, str]] = [
    (r"firmware|filesystem|squashfs|jffs2|ubifs|extract.*(image|firmware)", "firmware-unpack"),
    (r"disassembl|decompil|pseudocode|control flow", "static-decompile"),
    (r"debugger|breakpoint|step into|attach to process", "dynamic-debug"),
    (r"packer|entropy|detect .*(packer|compiler)", "triage"),
    (r"sql injection|sqli|injectable", "websqli"),
    (r"port scan|service detection|syn scan", "portscan"),
    (r"directory|brute ?forc|fuzz|wordlist", "fuzz-web"),
    (r"vulnerabilit|template|scanner|cve-", "webscan"),
    (r"hashcat|hash|wordlist|crack", "crack"),
    (r"yara|rule match|pattern match", "yara"),
    (r"pcap|packet capture|dissect", "capture"),
    (r"proxy|intercept|man.in.the.middle", "proxy"),
    (r"apk|dalvik|smali|android", "apk"),
    (r"hook|inject|instrument|frida", "hook"),
    (r"dump.*memory|memory dump|iat", "memory-dump"),
    (r"rop|gadget", "rop"),
    (r"emulat|symbolic|concolic", "emulate"),
]

SKIP_DIR_PARTS = {"node_modules", "__pycache__", ".git", "_dl", "docs", "db", "dist-info",
                  "site-packages", "include", "lib", "share", "templates", "examples",
                  "tests", "test-data", "man", "locale", "cmake", "pkgconfig"}
EXEC_EXT = {".exe", ".cmd", ".bat", ".ps1"}

PROBE_TIMEOUT = 2.0
MAX_CANDIDATES = 6000
MAX_HELP_PROBES = 220


def state_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = Path(base) / "reverse-skill" / "capabilities"
    d.mkdir(parents=True, exist_ok=True)
    return d


def search_roots() -> list[Path]:
    """工具根优先 —— help 探测预算有限，要先花在「我们自己的工具」上，再轮到系统目录。"""
    roots: list[Path] = []
    tr = os.environ.get("REVERSE_TOOL_ROOT")
    if tr and Path(tr).is_dir():
        roots.append(Path(tr))
    elif Path(r"D:\Tools").is_dir():
        roots.append(Path(r"D:\Tools"))
    for p in (os.environ.get("PATH") or "").split(os.pathsep):
        if p and Path(p).is_dir():
            try:
                pp = Path(p)
                if any(pp.samefile(r) for r in roots):
                    continue
            except OSError:
                pass
            roots.append(Path(p))
    return roots


def load_toolmap_exclusions() -> tuple[list[str], list[str]]:
    """复用工具根 `_map.json` 的既有判断：deny（明确不要的副本）+ notHere（确认没有的）。
    别人已经踩过的坑，这里不再重踩一遍。"""
    cands = []
    tr = os.environ.get("REVERSE_TOOL_ROOT") or r"D:\Tools"
    for p in (Path(tr) / "_map.json", Path(tr) / "_map.json.default"):
        if p.exists():
            cands.append(p)
    deny_re: list[str] = []
    nothere: list[str] = []
    for p in cands:
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for d in (m.get("deny") or []):
            deny_re += [x for x in (d.get("pathPatterns") or [])]
        nh = (m.get("notHere") or {})
        for key in ("free", "pip", "runtime"):
            nothere += [x for x in (nh.get(key) or []) if isinstance(x, str)]
        break
    return deny_re, nothere


def _deny_hit(path: str, deny_re: list[str]) -> bool:
    for pat in deny_re:
        rx = re.escape(pat).replace(r"\*", ".*")
        if re.search(rx, path, re.IGNORECASE):
            return True
    return False


def scan_candidates(roots: list[Path], max_depth: int = 5) -> list[Path]:
    deny_re, nothere = load_toolmap_exclusions()
    deny_roots = {n.lower() for n in nothere if "\\" not in n and "/" not in n}
    out: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            base_depth = len(root.parts)
            for p in root.rglob("*"):
                if len(out) >= MAX_CANDIDATES:
                    return out
                try:
                    if len(p.parts) - base_depth > max_depth:
                        continue
                    if p.is_dir() or p.suffix.lower() not in EXEC_EXT:
                        continue
                    if SKIP_DIR_PARTS & {x.lower() for x in p.parts}:
                        continue
                    if _deny_hit(str(p), deny_re):
                        continue
                    if p.stem.lower() in deny_roots and p.suffix.lower() in (".cmd", ".bat", ".ps1"):
                        continue
                    k = str(p).lower()
                    if k in seen:
                        continue
                    seen.add(k)
                    out.append(p)
                except OSError:
                    continue
        except OSError:
            continue
    return out


def classify_by_rules(p: Path) -> tuple[str, str] | None:
    """先拿**文件名**匹配（规则里的 ^ 才是有意义的），再退到**完整路径**匹配
    （有些能力只体现在目录名上，例如 `\\wireshark\\` 下的 exe）。"""
    for pat, cap, why in RULES:
        try:
            if re.search(pat, p.name, re.IGNORECASE) or re.search(pat, str(p), re.IGNORECASE):
                return cap, why
        except re.error:
            continue
    return None


def classify_by_help(p: Path) -> tuple[str, str] | None:
    for flag in ("--help", "-h", "-?"):
        try:
            r = subprocess.run([str(p), flag], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=PROBE_TIMEOUT)
        except (OSError, subprocess.TimeoutExpired, ValueError):
            return None
        txt = ((r.stdout or "") + (r.stderr or ""))[:8000]
        if len(txt) < 20:
            continue
        for pat, cap in HELP_HINTS:
            if re.search(pat, txt, re.IGNORECASE):
                return cap, f"help 关键词命中 /{pat}/"
    return None


def build(probe_help: bool = True) -> dict:
    roots = search_roots()
    cands = scan_candidates(roots)
    index: dict[str, list[dict]] = {c: [] for c in CAPABILITIES}
    unknown: list[str] = []
    probes = 0
    for p in cands:
        hit = classify_by_rules(p)
        if not hit:
            if probe_help and probes < MAX_HELP_PROBES:
                probes += 1
                hit = classify_by_help(p)
            if not hit:
                unknown.append(str(p))
                continue
        cap, why = hit
        index.setdefault(cap, []).append({"tool": p.stem, "path": str(p), "why": why,
                                          "how": "rule" if "help" not in why else "help-probe"})
    # 去重 + 排序：clawer/wrapper 优先（cli 下的）→ 路径短优先 → 名字字典序；每个能力最多留 12 个
    cli = (Path(os.environ.get("REVERSE_TOOL_ROOT") or r"D:\Tools") / "cli")
    for cap, lst in index.items():
        best: dict[str, dict] = {}
        for it in lst:
            k = it["tool"].lower()
            if k not in best or len(it["path"]) < len(best[k]["path"]):
                best[k] = it

        def rank(x: dict) -> tuple:
            try:
                in_cli = 0 if Path(x["path"]).parent == cli else 1
            except OSError:
                in_cli = 1
            return (in_cli, len(x["path"]), x["tool"].lower())

        index[cap] = sorted(best.values(), key=rank)[:12]
    return {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "roots": [str(r) for r in roots],
        "candidates": len(cands),
        "help_probes": probes,
        "capabilities": {c: v for c, v in index.items() if v},
        "unknown_count": len(unknown),
        "unknown_sample": unknown[:40],
    }


def load() -> dict | None:
    f = state_dir() / "capabilities.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            return None
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true", help="重建索引")
    ap.add_argument("--no-help-probe", action="store_true", help="不跑 --help 探测（快，但认不出没见过的新工具）")
    ap.add_argument("--find", metavar="CAP", help="按能力查工具")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list-capabilities", action="store_true")
    a = ap.parse_args()

    if a.list_capabilities:
        for cid, (name, domain) in CAPABILITIES.items():
            print(f"  {cid:18s} {domain:4s} {name}")
        return 0

    if a.scan:
        t0 = time.time()
        idx = build(probe_help=not a.no_help_probe)
        (state_dir() / "capabilities.json").write_text(
            json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"扫描 {idx['candidates']} 个候选，help 探测 {idx['help_probes']} 个，"
              f"未知 {idx['unknown_count']} 个，用时 {time.time()-t0:.1f}s")
        for c, lst in idx["capabilities"].items():
            print(f"  {c:18s} {len(lst):3d} 个  e.g. {', '.join(x['tool'] for x in lst[:4])}")
        return 0

    idx = load()
    if not idx:
        print("还没有索引，先跑 --scan", file=sys.stderr)
        return 2

    if a.find:
        lst = idx["capabilities"].get(a.find) or []
        if a.json:
            print(json.dumps(lst, ensure_ascii=False, indent=1)); return 0
        if not lst:
            print(f"本机没有能做「{a.find}」的工具。")
            return 1
        for x in lst:
            print(f"  {x['tool']:24s} {x['why']:28s} {x['path']}")
        return 0

    print(json.dumps(idx, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
