"""极简控制台：只做扫描、选智能体、载入、卸载。

只读本机 %USERPROFILE% 下的各家智能体家目录，判断它有没有装中枢、有没有正在跑。
不写任何文件，不联网，不碰旧系统。

被 03-bundle 的打包器复用也可以，但本模块不 import 03-bundle 的任何代码。
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
import uuid
from pathlib import Path

# 每家只描述三件事：家目录在哪、它会读哪份入口文件、怎么认出它的活进程。
# home 是相对 %USERPROFILE% 的相对路径；不写死盘符。
#
# ## 这些路径的依据（2026-09-28 逐家核实，别再凭印象改）
#
# 每条都来自该家的**官方文档或本机安装的源码**，核实记录见每条的 source 字段。
# 2026-09-28 出过一次真事故：pi 原来认 ~/.pi，装进去、打包器退出码 0、
# 所有自检全过，但 PI 源码 `getAgentDir()` 返回 `~/.pi/agent`，
# **它从头到尾没看见过那 12 块底线**——问它底线，它报的是自己那套 6 条。
# 「装成功」和「生效」是两件事，只有真机问一句才能分辨。
#
# 各家加载全局规则的方式也不同，这决定标记块的位置有没有意义：
#   · codex   全局 ~/.codex/AGENTS.md；另有 AGENTS.override.md **会盖掉它**
#   · dsh     $DSH_HOME/AGENTS.md，且有 **65536 字节硬预算**（装得下，但要知道）
#   · opencode 全局 + 项目各级「**合并**」而非覆盖，位置不决定谁赢
#   · pi      ~/.pi/agent/，候选顺序 override → AGENTS.md → CLAUDE.md，每目录只取第一个
#   · hermes  ~/.hermes/SOUL.md（身份文件，**系统提示词最靠前**）
SOURCE_NOTES = {
    "codex": "官方 learn.chatgpt.com/docs/agent-configuration/agents-md：~/.codex/AGENTS.md",
    "claude": "Claude Code 读 ~/.claude/CLAUDE.md（唯一一家不是 AGENTS.md 的）",
    "cursor": "官方 cursor.com/docs/rules 支持 AGENTS.md；.cursorrules 是旧机制",
    "grok": "未见官方文档，按 AGENTS.md 惯例；装上后应复核",
    "gemini": "官方 geminicli.com/docs/cli/gemini-md：~/.gemini/GEMINI.md",
    "deepseek": "官方 deepseek-harness 仓库 dsh-agent-instructions：$DSH_HOME/AGENTS.md",
    "hermes": "官方 hermes-agent 文档：~/.hermes/SOUL.md（身份文件，在系统提示词最前）",
    "pi": "本机安装源码 getAgentDir()= ~/.pi/agent（**不是 ~/.pi**）",
    "omp": "本机实测：~/.omp/agent/ 下是 PERSONALITY.md（人设）+ RULES.md（规则）两文件形态；"
           "无 AGENTS.md，不融合三段",
    "pidesktop": "社区 dsh-desktop，沿用 pi 的 agent/ 约定；未验证",
    "dsh": "官方 deepseek-harness：$DSH_HOME/AGENTS.md，预算 65536 B",
    "zcode": "官方 zcode.z.ai 有 memory 机制，AGENTS.md 位置未见明文；未验证",
    "opencode": "官方 opencode.ai/docs/rules：~/.config/opencode/AGENTS.md",
    "windsurf": "官方 Cascade memories 机制；全局规则路径未验证",
    "aider": "官方 aider.chat/docs/usage/conventions：约定文件，未验证 AGENTS.md 自动读",
}
HOST_SPECS: tuple[dict, ...] = (
    {
        "id": "codex",
        "name": "Codex",
        "home": ".codex",
        "entry": "AGENTS.md",
        "images": ("codex.exe",),
        "markers": (".codex",),
    },
    {
        "id": "claude",
        "name": "Claude Code",
        "home": ".claude",
        "entry": "CLAUDE.md",
        "images": ("claude.exe",),
        "markers": (".claude",),
    },
    {
        "id": "cursor",
        "name": "Cursor",
        "home": ".cursor",
        "entry": "AGENTS.md",
        "entry_alternates": ("rules/hubcore.mdc",),
        "images": ("cursor.exe",),
        "markers": (".cursor",),
    },
    {
        "id": "grok",
        "name": "Grok",
        "home": ".grok",
        "entry": "AGENTS.md",
        "images": ("grok.exe",),
        "markers": (".grok",),
    },
    {
        "id": "gemini",
        "name": "Gemini",
        "home": ".gemini",
        "entry": "GEMINI.md",
        "images": ("gemini.exe",),
        "markers": (".gemini",),
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "home": ".deepseek",
        "entry": "DEEPSEEK.md",
        "images": ("deepseek.exe",),
        "markers": (".deepseek",),
    },
    {
        "id": "hermes",
        "name": "Hermes",
        "home": ".hermes",
        "entry": "SOUL.md",
        "images": ("hermes.exe",),
        "markers": (".hermes",),
    },
    {
        "id": "pi",
        "name": "Pi",
        # 家是 ~/.pi/agent，**不是 ~/.pi**。本机安装的源码里写死：
        #   getAgentDir(){ return join(homedir(), CONFIG_DIR_NAME, "agent") }
        #   CONFIG_DIR_NAME = ".pi"
        # 原来这里写 .pi，装是装成功了，但 PI 读的是 agent/AGENTS.md，
        # 那 12 块底线它一条也没看见。entry_alternates 里早就有 agent/AGENTS.md，
        # 可解析逻辑从来没用它——**表里有备选 ≠ 代码会用备选**。
        "home": ".pi/agent",
        "entry": "AGENTS.md",
        "entry_alternates": (),
        "images": ("pi.exe",),
        "markers": (".pi",),
    },
    {
        "id": "omp",
        "name": "omp",
        # ★ 2026-10-14：omp 是**全项目唯一一家把底模和规则分开放的**。
        #   本机实测：~/.omp/agent/ 下只有 PERSONALITY.md（人设/破甲，kind: base）
        #   和 RULES.md（规则/指引，kind: guest），**没有 AGENTS.md**，
        #   也不需要把三段融成一份。所以：
        #     base 卡 → entry_base（PERSONALITY.md）
        #     中枢段 + guest 卡 → entry（RULES.md）
        "home": ".omp/agent",
        "entry": "RULES.md",
        "entry_base": "PERSONALITY.md",
        "entry_alternates": ("AGENTS.md",),
        "images": ("omp.exe", "oh-my-pi.exe"),
        "markers": (".omp",),
    },
    {
        "id": "pidesktop",
        "name": "PI-Desktop",
        "home": ".pi-desktop",
        "entry": "AGENTS.md",
        "images": ("pi-desktop.exe", "PI-Desktop.exe"),
        "markers": ("plugins", "scratch"),
    },
    {
        "id": "dsh",
        "name": "DeepSeek Harness",
        "home": ".dsh",
        "entry": "AGENTS.md",
        "images": ("dsh.exe",),
        "markers": ("AGENTS.md",),
    },
    {
        "id": "zcode",
        "name": "ZCode",
        "home": ".zcode",
        "entry": "AGENTS.md",
        "images": ("zcode.exe",),
        "markers": (".zcode",),
    },
    {
        "id": "opencode",
        "name": "OpenCode",
        "home": ".config/opencode",
        "entry": "AGENTS.md",
        "images": ("opencode.exe",),
        "markers": (".config",),
    },
    {
        "id": "windsurf",
        "name": "Windsurf",
        "home": ".windsurf",
        "entry": "AGENTS.md",
        "entry_alternates": ("memories/global_rules.md",),
        "images": ("windsurf.exe",),
        "markers": (".windsurf",),
    },
    {
        "id": "aider",
        "name": "Aider",
        "home": ".aider",
        "entry": "AGENTS.md",
        "images": ("aider.exe", "aider-chat.exe"),
        "markers": (".aider",),
    },
)

# 这些是各家的命令行特征。只有在 tasklist 认出镜像名之后才去看命令行，
# 用来区分「同一个 node.exe 跑的是哪一家」。
CMD_MARKERS: dict[str, tuple[str, ...]] = {
    "codex": ("@openai/codex", "codex-cli", "\\.codex\\", "/.codex/"),
    "claude": ("@anthropic-ai/claude-code", "claude-code", "\\.claude\\", "/.claude/"),
    "cursor": ("\\.cursor\\", "/.cursor/", "cursor-agent"),
    "grok": ("grok-cli", "\\.grok\\", "/.grok/"),
    "gemini": ("@google/gemini-cli", "gemini-cli", "\\.gemini\\", "/.gemini/"),
    "deepseek": ("deepseek-chat", "\\.deepseek\\", "/.deepseek/"),
    "hermes": ("\\.hermes\\", "/.hermes/", "hermes-cli"),
    "pi": ("\\.pi\\agent", "/.pi/agent", "pi-desktop"),
    "pidesktop": ("pi-desktop", "\\.pi-desktop\\", "/.pi-desktop/"),
    "dsh": ("@deepseek-ai/dsh", "\\.dsh\\", "/.dsh/", " dsh", "dsh-prompt"),
    "zcode": ("\\.zcode\\", "/.zcode/"),
    "opencode": ("opencode-ai", "opencode", "\\.config\\opencode"),
    "windsurf": ("\\.windsurf\\", "/.windsurf/", "\\.codeium\\windsurf", "windsurf"),
    "aider": ("aider", "\\.aider\\", "/.aider/"),
}

# 只有这些镜像会去查命令行。系统进程、系统服务一律不看。
RUNTIME_IMAGES = frozenset(
    {
        "node.exe",
        "bun.exe",
        "deno.exe",
        "dsh.exe",
        "codex.exe",
        "claude.exe",
        "cursor.exe",
        "grok.exe",
        "gemini.exe",
        "deepseek.exe",
        "hermes.exe",
        "pi.exe",
        "pi-desktop.exe",
        "PI-Desktop.exe",
        "zcode.exe",
        "opencode.exe",
        "windsurf.exe",
        "aider.exe",
        "aider-chat.exe",
    }
)

# 中枢装在宿主家目录下的样子。改这一段等于改整棵树的形状，只动这一处。
HUB_DIRNAME = "hub"
CORE_RELPATH = f"{HUB_DIRNAME}/CORE.md"
MANIFEST_RELPATH = f"{HUB_DIRNAME}/install-manifest.json"

# ---------------------------------------------------------------- 扫外来家目录
# 名单是死的，机器是活的。老中枢的教训：名单之外还有一个真家目录时，页面上就
# 「扫不到」，主人以为坏了。所以名单之外再扫，而且比老站扫得更宽：
#   1) 四个位置：家目录、.config、%APPDATA%、%APPDATA%\opencode
#   2) 入口文件认家，认不到再看 <家>\agent\入口（Pi 这一家的入口就在 agent 底下）
#   3) 没有入口文件时，看表面特征（.cursor / .pi-desktop）
#   4) 盘上装了 Everything（es.exe）就还能全盘按入口文件名兜一遍，主人点「深扫」才跑
#   5) 主人手填的家目录写进 hostlist/custom-hosts.json —— 扫不到也能自己加
ENTRY_CANDIDATES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "DEEPSEEK.md",
                    "GLM.md", "SOUL.md")

# 明确不是宿主的目录：缓存、工具链、共用夹、各家自己的数据库。
# 放进这个集合 = 页面不列它（列了只会让人以为能装）。
EXTRA_SKIP = frozenset({
    ".agents", ".agents-anywhere", ".agentsanywhere", ".ssh", ".cache", ".cargo",
    ".rustup", ".local", ".tmp", ".android", ".mitmproxy", ".modsearch",
    ".playwright-mcp", ".computer-use-mcp", ".cua-driver", ".pchat-token-inject",
    ".uuyc-mux", ".leigod", ".bsk", ".grokbot", ".cursor-agents", ".cc-switch",
    ".claude_backup_20260927", ".pi_backup_20260927", ".antigravity-ide",
    ".antigravity_cockpit", "node_modules", "__pycache__", "AppData", "Desktop",
    "Documents", "Downloads", "Music", "Pictures", "Videos", "Contacts",
    "Favorites", "Links", "Searches", "Saved Games", "OneDrive", "3D Objects",
})

# 备份副本一律不当家。名字里带这些词的目录，是上一轮留下来的，不是智能体。
_BAD_TAGS = ("backup", "bak", ".old", "-old", "_old", "-copy", "副本", "备份")

# 一级子目录不要求带点时，只额外放行这几个（沿用老站口径）。
_PLAIN_ALLOWED = frozenset({"opencode"})

# 没有入口文件、但一看就知道是谁家的目录。
SURFACE_HINTS: dict[str, tuple[str, ...]] = {
    ".cursor": ("User", "rules", "argv.json"),
    ".pi-desktop": ("pi.sqlite", "sessions", "plugins"),
}

# 主人手填的名单。落在本模块目录里，跟打包器无关，也不进任何智能体夹。
HOSTLIST_DIR = Path(__file__).resolve().parent / "hostlist"
CUSTOM_PATH = HOSTLIST_DIR / "custom-hosts.json"
IGNORE_PATH = HOSTLIST_DIR / "ignore.json"

_EXTRA_TTL = 15.0
_extra_cache: dict = {"at": 0.0, "rows": []}
# 深扫一次滤掉了多少个不像家的目录。页面上要报出来，不然主人以为漏了。
_deep_cache: dict = {"filtered": 0}


def _slug(name: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not text:
        # 纯中文名（"探针假家"） slug 出来是空的，退回短哈希，保证 id 唯一可用。
        text = "x" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]
    return "x-" + text


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp-%s" % uuid.uuid4().hex)
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def _key_of(path: Path) -> str:
    try:
        return str(path.resolve()).casefold()
    except OSError:
        return str(path).casefold()


def load_ignored() -> set[str]:
    rows = _read_json(IGNORE_PATH, [])
    return {_key_of(Path(str(r))) for r in rows if str(r or "").strip()}


def ignore_host(home: str) -> list[str]:
    """主人点了「别列这家」：记下来，下次扫描跳过。"""
    target = Path(str(home)).expanduser()
    rows = sorted(load_ignored() | {_key_of(target)})
    _write_json(IGNORE_PATH, rows)
    _extra_cache.update({"at": 0.0, "rows": []})
    return rows


def unignore_host(home: str) -> dict:
    """把「别列这家」撤回来。

    「别列」是单向门的话，主人点错一次就再也看不到这家了。每一项都得有退路。
    """
    target = _key_of(Path(str(home)).expanduser())
    before = load_ignored()
    if target not in before:
        return {"ok": False, "error": "这家本来就没被点名不列。"}
    _write_json(IGNORE_PATH, sorted(before - {target}))
    _extra_cache.update({"at": 0.0, "rows": []})
    return {"ok": True, "home": str(home), "left": len(before) - 1}


def ignored_homes() -> list[str]:
    """被点名不列的那几家（按原样路径给回去，页面要能一键恢复）。"""
    return [str(r) for r in _read_json(IGNORE_PATH, []) if str(r or "").strip()]


def add_custom(name: str, home: str) -> dict:
    title = str(name or "").strip()
    raw = str(home or "").strip().strip('"')
    if not title:
        return {"ok": False, "error": "先给这家起个名。"}
    if not raw:
        return {"ok": False, "error": "家目录要写完整路径。"}
    target = Path(raw).expanduser()
    if not target.is_absolute():
        return {"ok": False, "error": "家目录要写完整路径。"}
    if not target.is_dir():
        return {"ok": False, "error": "这个家目录在盘上找不到，先确认路径。"}
    if target == target.parent:
        return {"ok": False, "error": "不能把盘符根当智能体家目录。"}
    rows = load_custom()
    base = user_home()
    known = {_key_of(base / s["home"]) for s in HOST_SPECS}
    known |= {_key_of(Path(r["home"])) for r in rows}
    if _key_of(target) in known:
        return {"ok": False, "error": "这家已经在名单里了，不用再加。"}
    new_id = _slug(title)
    used_ids = {str(s["id"]) for s in HOST_SPECS} | {str(r.get("id")) for r in rows}
    if new_id in used_ids:
        return {"ok": False, "error": "这家名字会和已有宿主冲突，换一个名字再加。"}
    entry = _entry_in(target)
    # ★ 手加的家也要继承名单里同款宿主的槽位（omp：RULES.md + PERSONALITY.md）。
    #   不然手加一个 ~/.omp/agent 会拿到 AGENTS.md，底模也塞错地方。
    inh_entry, inh_base = _inherit_slots({"home": str(target), "custom": True}, target)
    row = {
        "id": new_id,
        "name": title,
        "home": str(target),
        "entry": entry or inh_entry or ENTRY_CANDIDATES[0],
        "entry_alternates": (),
        "images": (),
        "markers": (),
        "custom": True,
    }
    if inh_base:
        row["entry_base"] = inh_base
    rows.append(row)
    save_custom(rows)
    return {"ok": True, "id": row["id"], "home": str(target), "entry": row["entry"]}


def remove_custom(host_id: str) -> dict:
    rows = load_custom()
    kept = [r for r in rows if r.get("id") != str(host_id or "").strip()]
    if len(kept) == len(rows):
        return {"ok": False, "error": "名单上没有这家。"}
    save_custom(kept)
    return {"ok": True, "id": str(host_id or "").strip()}


def load_custom() -> list[dict]:
    rows = _read_json(CUSTOM_PATH, [])
    if not isinstance(rows, list):
        return []
    out: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("name") or "").strip()
        raw = str(row.get("home") or "").strip()
        if not title or not raw:
            continue
        out.append({
            "id": str(row.get("id") or _slug(title)),
            "name": title,
            "home": raw,
            "entry": str(row.get("entry") or ENTRY_CANDIDATES[0]),
            "entry_base": str(row.get("entry_base") or ""),
            "entry_alternates": (),
            "images": (),
            "markers": (),
            "custom": True,
        })
    return out


def save_custom(rows: list[dict]) -> list[dict]:
    _write_json(CUSTOM_PATH, [
        {"id": r["id"], "name": r["name"], "home": r["home"], "entry": r["entry"]}
        for r in rows
    ])
    _extra_cache.update({"at": 0.0, "rows": []})
    return rows


def _entry_in(home: Path) -> str:
    """入口文件在哪。认不到就退到 <家>\\agent\\下面（Pi 就是这个形状）。"""
    for name in ENTRY_CANDIDATES:
        if (home / name).is_file():
            return name
    agent = home / "agent"
    if agent.is_dir():
        for name in ENTRY_CANDIDATES:
            if (agent / name).is_file():
                return "agent/" + name
    return ""


def _surface_of(home: Path) -> bool:
    names = SURFACE_HINTS.get(home.name)
    if not names:
        return False
    return any((home / n).exists() for n in names)


def _banned(home: Path) -> bool:
    low = home.name.casefold()
    if any(tag in low for tag in _BAD_TAGS):
        return True
    if (home / ".git").exists():
        return True
    return False


def scan_roots() -> list[tuple[Path, bool]]:
    """(根目录, 子目录是否必须带点)。口径沿用老外置中枢。"""
    base = user_home()
    rows: list[tuple[Path, bool]] = [(base, True)]
    for rel in (".config", "config"):
        cand = base / rel
        if cand.is_dir():
            rows.append((cand, False))
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        roaming = Path(appdata)
        if roaming.is_dir():
            rows.append((roaming, True))
            opc = roaming / "opencode"
            if opc.is_dir():
                rows.append((opc, False))
    return rows


def _es_bin() -> str | None:
    # 只认 PATH 上的 es.exe，并且不许它在临时目录里。
    # shutil.which 会先命中 PATH 上任何同名的东西——在临时目录里放一个叫 es.exe 的文件，
    # 点一次「深扫全盘」就等于以当前用户权限执行了那个文件。
    # 注意：Everything 装在哪都行（主人这台在 <工具根>\Everything\），不能只认 Program Files。
    for name in ("es", "es.exe"):
        found = shutil.which(name)
        if not found:
            continue
        try:
            resolved = Path(found).resolve()
        except OSError:
            continue
        low = str(resolved).lower()
        temp_markers = ("\\temp\\", "\\tmp\\", "\\downloads\\", "\\appdata\\local\\temp\\")
        if any(marker in low for marker in temp_markers):
            continue
        return str(resolved)
    return None


def _everything_hits(base: Path, name: str) -> list[Path]:
    """Everything 在不在就在全盘按入口文件名兜一遍；不在就安静跳过。"""
    exe = _es_bin()
    if not exe:
        return []
    try:
        proc = subprocess.run(
            [exe, "-n", "80", "-path", str(base), name],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=12, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    hits: list[Path] = []
    for line in (proc.stdout or "").splitlines():
        text = line.strip().strip('"')
        if not text:
            continue
        path = Path(text)
        if path.is_file() and path.name.casefold() == name.casefold():
            hits.append(path)
    return hits


def _plausible(home: Path, root: Path, must_dot: bool) -> bool:
    try:
        rel = home.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    parts = rel.parts
    if len(parts) != 1:
        return False
    name = parts[0]
    if must_dot:
        return name.startswith(".") or name.casefold() in _PLAIN_ALLOWED
    return True


# 深扫会命中整台盘上每一个 AGENTS.md，绝大多数是测试夹、仓库里的子目录、临时目录。
# 这两张表就是深扫的准入门槛：过了才认作家，没过的算成「滤掉 N 个」。
_DEEP_NO_PARENT = frozenset({
    "skills", "vendor", "plugins", "docs", "doc", "hub", "hub-lean", "backups",
    "worktrees", "sessions", "scratch", "node_modules", "npm", "templates",
    "references", "examples", "bench", "tests", "test", "src", "lib", "dist",
    "build", "target", "out", "fixtures", "fixture", "sandboxes", "seeds",
})
_DEEP_NO_LEAF = frozenset({
    "home", "homes", "host", "hosts", "hub", "hub-lean", "seats", "docs",
    "secrets", "credential", "credentials", "keys", "auth",
})
_DEEP_HOME_SHAPE = ("skills", "rules", "sessions", "agents", "prompts",
                    "config.json", "config.toml", "settings.json")


def _deep_plausible(home: Path) -> bool:
    """深扫结果的准入门槛。宁可漏，也不把测试夹当智能体列给主人。"""
    try:
        parts = [p.casefold() for p in home.resolve().parts]
    except OSError:
        return False
    if any(p in _DEEP_NO_PARENT for p in parts[:-1]):
        return False
    if parts[-1] in _DEEP_NO_LEAF:
        return False
    # 备份/残副本：名字带 backup/bak/old 的整条路径都不认。
    # （`.claude_backup_20260927\.claude` 就是这么混进来的——上一轮留下的家目录。）
    if any(tag in part for part in parts for tag in _BAD_TAGS):
        return False
    if _banned(home):
        return False
    # 临时目录、缓存目录一律不当家：那里全是历次测试的残骸。
    if "temp" in parts or "tmp" in parts or ".cache" in parts:
        return False
    # 像个家目录：有技能夹、有配置、有会话，或者名字本身带点。
    if any((home / shape).exists() for shape in _DEEP_HOME_SHAPE):
        return True
    return home.name.startswith(".")


def discover_extra(*, deep: bool = False, ttl: float = _EXTRA_TTL) -> list[dict]:
    """名单之外，扫出来的家目录。只读、只列，不改。

    deep=True 时再借 Everything 全盘兜一遍（默认关，主人点「深扫」才跑）。
    """
    now = time.time()
    if not deep and now - _extra_cache["at"] < ttl:
        return _extra_cache["rows"]
    base = user_home()
    known = {_key_of(base / s["home"]) for s in HOST_SPECS}
    for s in HOST_SPECS:
        p = (base / s["home"]).parent
        if p != base:
            known.add(_key_of(p))
    known |= {_key_of(Path(r["home"])) for r in load_custom()}
    ignored = load_ignored()

    found: dict[str, Path] = {}
    deep_filtered = 0

    def _keep(home: Path, root: Path, must_dot: bool) -> None:
        if not _plausible(home, root, must_dot) or _banned(home):
            return
        key = _key_of(home)
        if key in known or key in ignored:
            return
        found.setdefault(key, home)

    for root, must_dot in scan_roots():
        if not root.is_dir():
            continue
        try:
            children = list(root.iterdir())
        except OSError:
            continue
        for child in children:
            if not child.is_dir():
                continue
            if child.name in EXTRA_SKIP or child.name.casefold() in ("node_modules", ".git"):
                continue
            if must_dot and not (child.name.startswith(".") or
                                 child.name.casefold() in _PLAIN_ALLOWED):
                continue
            if _entry_in(child) or _surface_of(child):
                _keep(child, root, must_dot)

    if deep:
        filtered = 0
        for name in ENTRY_CANDIDATES:
            for hit in _everything_hits(base, name):
                home = hit.parent
                if home.name.casefold() == "agent":
                    home = home.parent
                if not _deep_plausible(home):
                    filtered += 1
                    continue
                key = _key_of(home)
                if key in known or key in ignored:
                    continue
                found.setdefault(key, home)
        deep_filtered = filtered

    rows: list[dict] = []
    used_ids = {s["id"] for s in HOST_SPECS} | {str(r.get("id")) for r in load_custom()}
    for home in found.values():
        ident = _slug(home.name.lstrip(".") or home.name)
        if ident in used_ids:
            ident += "-" + hashlib.sha256(str(home.resolve()).encode("utf-8")).hexdigest()[:8]
        used_ids.add(ident)
        rows.append({
            "id": ident,
            "name": home.name.lstrip(".") + "（扫到）",
            "home": str(home),
            "entry": _entry_in(home) or ENTRY_CANDIDATES[0],
            "entry_alternates": (),
            "images": (),
            "markers": (),
            "extra": True,
        })
    rows.sort(key=lambda r: r["name"])
    # 深浅都进同一份缓存：深扫慢 1 秒多，轮询不该每 5 秒重付一次。
    _extra_cache.update({"at": now, "rows": rows})
    if deep:
        _deep_cache["filtered"] = deep_filtered
    return rows


def host_specs(deep: bool = False) -> list[dict]:
    """名单 + 主人手填的 + 扫到的。id 不重复。"""
    seen = {s["id"] for s in HOST_SPECS}
    rows = list(HOST_SPECS)
    for spec in load_custom() + discover_extra(deep=deep):
        if spec["id"] in seen:
            continue
        seen.add(spec["id"])
        rows.append(spec)
    return rows

_SCAN_TTL_SECONDS = 3.0
_lock = threading.Lock()
_cache: dict = {"at": 0.0, "value": None}


# ---------------------------------------------------------------- 家目录定位

def user_home() -> Path:
    raw = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
    return Path(raw) if raw else Path.home()


def _inherit_slots(spec: dict, home: Path):
    """扫到/手加的家，把名单里同款宿主的**槽位定义**继承过来。

    名单里的 omp 自带 `entry=RULES.md` + `entry_base=PERSONALITY.md`；
    但**扫到/手加**的家是从盘上推出来的 spec，两个字段都会退到默认值 ——
    不继承的话，主人手加一个 `~/.omp/agent` 会拿到 `AGENTS.md`（错的文件名），
    而且丢掉「底模单独一个文件」这个行为，底模会被塞进那份错文件里。

    返回 `(entry, entry_base)`；没匹配上就返回空串。
    """
    named = (spec.get("entry"), spec.get("entry_base") or "")
    if named[1] and not (spec.get("custom") or spec.get("extra")):
        return "", str(named[1])
    rel = str(spec.get("home") or "").replace("/", "\\").strip("\\").lower()
    try:
        tail = "\\".join(Path(home).parts[-2:]).lower()
    except (TypeError, ValueError):
        tail = ""

    def _match(s: dict) -> bool:
        key = str(s["home"]).replace("/", "\\").strip("\\").lower()
        return bool(key) and (key == rel or (tail and (key == tail or key.endswith("\\" + tail))))

    for s in HOST_SPECS:
        if _match(s):
            return str(s["entry"]), str(s.get("entry_base") or "")
    return "", ""


def _resolve_home(spec: dict, base: Path) -> Path:
    rel = spec.get("home") or "."
    candidate = base / rel
    if not candidate.is_dir():
        fallback = spec.get("home_fallback")
        if fallback and (base / fallback).is_dir():
            return base / fallback
    return candidate


def _host_by_id(host_id: str) -> dict | None:
    for spec in HOST_SPECS:
        if spec["id"] == str(host_id or ""):
            return spec
    return None


# ---------------------------------------------------------------- 进程扫描

def _run_tasklist() -> dict[str, list[int]]:
    """tasklist /FO CSV /NH -> {镜像名(小写): [pid, ...]}。"""
    out: dict[str, list[int]] = {}
    try:
        proc = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=25,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return out
    if proc.returncode != 0:
        return out
    for row in csv.reader(io.StringIO(proc.stdout or "")):
        if len(row) < 2:
            continue
        image = str(row[0]).strip().lower()
        try:
            pid = int(str(row[1]).strip())
        except ValueError:
            continue
        out.setdefault(image, []).append(pid)
    return out


def _run_cmdline_probe(images: list[str]) -> dict[int, str]:
    """一次 CIM 查询，取这些镜像的完整命令行。取不到就返回空，不猜。"""
    names = [name for name in images if re.fullmatch(r"[A-Za-z0-9_.-]{1,40}", name)]
    if not names:
        return {}
    where = " or ".join(f"Name='{name}'" for name in sorted(set(names)))
    # 先把 PowerShell 的输出管道切到 UTF-8，否则中文命令行会解码炸。
    script = (
        "$OutputEncoding=[Text.Encoding]::UTF8; "
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
        "Get-CimInstance Win32_Process -Filter \"{where}\" "
        "| Select-Object ProcessId,CommandLine "
        "| ConvertTo-Json -Compress"
    ).format(where=where)
    for shell in ("powershell", "pwsh"):
        exe = _which(shell)
        if not exe:
            continue
        try:
            proc = subprocess.run(
                [exe, "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if proc.returncode != 0:
            continue
        payload = (proc.stdout or "").strip()
        if not payload:
            continue
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue
        rows = data if isinstance(data, list) else [data]
        out: dict[int, str] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                out[int(row["ProcessId"])] = str(row.get("CommandLine") or "")
            except (KeyError, TypeError, ValueError):
                continue
        return out
    return {}


def _which(name: str) -> str | None:
    for folder in (os.environ.get("SystemRoot", r"C:\Windows") + r"\System32",
                   os.environ.get("SystemRoot", r"C:\Windows") + r"\System32\WindowsPowerShell\v1.0"):
        exe = Path(folder) / (name + ".exe")
        if exe.is_file():
            return str(exe)
    return None


def _scan_running() -> dict:
    """一次扫描，得出每家的运行态。返回 {host_id: {...}}。"""
    table = _run_tasklist()
    images_found = {image for image in table if image in RUNTIME_IMAGES}
    commandlines: dict[int, str] = {}
    if images_found:
        commandlines = _run_cmdline_probe(sorted(images_found))
    # 看到了运行类进程、却一条命令行都没读回来，就不能算「知道谁在跑」。
    probe_ok = bool(commandlines) or not images_found

    result: dict[str, dict] = {}
    for spec in HOST_SPECS:
        hid = spec["id"]
        pids: list[int] = []
        for image in spec["images"]:
            pids.extend(table.get(image, []))
        # 同一家里可能被不同入口拉起，node.exe 也要算进去。
        if not pids and images_found:
            markers = CMD_MARKERS.get(hid, ())
            for pid in sorted(commandlines):
                line = commandlines.get(pid, "").lower().replace("/", "\\")
                if not line:
                    continue
                if any(marker.replace("/", "\\") in line for marker in markers):
                    pids.append(pid)
        pids = sorted(set(pids))
        result[hid] = {
            "running": bool(pids),
            "known": probe_ok or not images_found,
            "pids": pids,
        }
    return {
        "hosts": result,
        "known": probe_ok or not images_found,
        "source": "tasklist+cim" if probe_ok else "tasklist",
        "at": time.time(),
    }


def process_state(host_id: str, *, ttl: float = _SCAN_TTL_SECONDS, now: float | None = None) -> dict:
    """带 3 秒缓存的运行态查询，避免每 5 秒轮询都去拉一遍进程表。"""
    stamp = time.monotonic() if now is None else now
    with _lock:
        cached = _cache["value"]
        if cached is not None and (stamp - _cache["at"]) < ttl:
            row = (cached.get("hosts") or {}).get(host_id)
            if row is not None:
                return dict(row)
        value = _scan_running()
        _cache["value"] = value
        _cache["at"] = stamp
    row = (value.get("hosts") or {}).get(host_id) or {"running": False, "known": False, "pids": []}
    return dict(row)


def _custom_process_state(home: Path) -> dict:
    """对自定义/扫到的家目录做保守的命令行路径匹配。"""
    table = _run_tasklist()
    if not table:
        return {"running": False, "known": False, "pids": []}
    images = sorted({name for name in table if name in RUNTIME_IMAGES})
    if not images:
        return {"running": False, "known": True, "pids": []}
    commandlines = _run_cmdline_probe(images)
    if not commandlines:
        return {"running": False, "known": False, "pids": []}
    needle = str(Path(home).resolve()).replace("/", "\\").rstrip("\\").lower()
    hits = sorted(pid for pid, line in commandlines.items()
                  if needle and needle in str(line).replace("/", "\\").lower())
    return {"running": bool(hits), "known": True, "pids": hits}


def probe_known() -> bool:
    """整体上能不能判断谁在跑。缓存冷了就先扫一遍。"""
    with _lock:
        cached = _cache["value"]
        if cached is not None and (time.monotonic() - _cache["at"]) < _SCAN_TTL_SECONDS:
            return bool(cached.get("known"))
    _scan_running()
    with _lock:
        return bool((_cache["value"] or {}).get("known"))


def invalidate_cache() -> None:
    with _lock:
        _cache["value"] = None
        _cache["at"] = 0.0


# ---------------------------------------------------------------- 装没装

def _hub_dir(home: Path) -> Path:
    return home / HUB_DIRNAME


def _count_files(root: Path) -> int:
    total = 0
    try:
        for item in root.rglob("*"):
            if item.is_file():
                total += 1
    except OSError:
        return total
    return total


def _entry_state(home: Path, entry: str, entry_base: str = "") -> dict:
    """入口文件实测：中枢写的那几段现在真在不在。

    页面说「装好了 / 正在用」，必须由这里支撑。只看 hub/ 目录在不在是不作数的——
    有人手删了入口文件里的块，hub/ 还照样躺在那儿。

    ★ 2026-10-14：omp 这类**两文件形态**的宿主，底模块不在 entry 里，在 entry_base 里。
    传了 entry_base 就分开判：`has_marker` / `has_guest` 看 entry，`has_base` 看 entry_base。
    """
    blank = {"entry_blocks": 0, "entry_ok": False, "entry_note": "",
             "has_marker": False, "has_base": False, "has_guest": False,
             "base_file": entry_base, "base_file_note": ""}
    if not entry:
        d = dict(blank); d["entry_note"] = "没定入口文件"; return d
    p = home / entry
    if not p.is_file():
        d = dict(blank); d["entry_note"] = "入口文件不在"; return d
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        d = dict(blank); d["entry_note"] = "入口文件读不出来"; return d
    lines = [ln.strip() for ln in text.splitlines()]
    has_marker = "# >>> hubcore hub >>>" in lines
    has_guest = "# >>> hubcore guest >>>" in lines

    # 两文件形态：底模块单独一个文件
    base_note = ""
    if entry_base:
        bp = home / entry_base
        if not bp.is_file():
            has_base = False
            base_note = "%s 不在（底模卡还没写进去）" % entry_base
        else:
            try:
                blines = [ln.strip() for ln in bp.read_text(encoding="utf-8", errors="replace").splitlines()]
                has_base = "# >>> hubcore base >>>" in blines
                base_note = "%s %s" % (entry_base, "有底模块" if has_base else "里没有底模块")
            except OSError:
                has_base = False
                base_note = "%s 读不出来" % entry_base
        # 两文件形态下，底模块**不参与**入口文件的配对计数
        begins = sum(1 for ln in lines if ln in ("# >>> hubcore hub >>>", "# >>> hubcore guest >>>"))
        ends = sum(1 for ln in lines if ln in ("# <<< hubcore hub <<<", "# <<< hubcore guest <<<"))
        has_base_in_entry = "# >>> hubcore base >>>" in lines
    else:
        has_base = "# >>> hubcore base >>>" in lines
        has_base_in_entry = has_base
        begins = sum(1 for ln in lines if ln in ("# >>> hubcore hub >>>", "# >>> hubcore base >>>",
                                                 "# >>> hubcore guest >>>"))
        ends = sum(1 for ln in lines if ln in ("# <<< hubcore hub <<<", "# <<< hubcore base <<<",
                                               "# <<< hubcore guest <<<"))
    if begins == 0:
        return {"entry_blocks": 0, "entry_ok": False, "entry_note": "入口文件里没有中枢的段",
                "has_marker": has_marker, "has_base": has_base, "has_guest": has_guest,
                "base_file": entry_base, "base_file_note": base_note}
    if begins != ends:
        return {"entry_blocks": begins, "entry_ok": False,
                "entry_note": "定界行不成对（%d 开 / %d 闭），装卸可能没摘干净" % (begins, ends),
                "has_marker": has_marker, "has_base": has_base, "has_guest": has_guest,
                "base_file": entry_base, "base_file_note": base_note}
    note = "入口文件里有 %d 段中枢" % begins
    if entry_base and not has_base_in_entry:
        note += "；底模另存 %s" % (entry_base if has_base else "（还没写）")
    return {"entry_blocks": begins, "entry_ok": True, "entry_note": note,
            "has_marker": has_marker, "has_base": has_base, "has_guest": has_guest,
            "base_file": entry_base, "base_file_note": base_note}


def _install_state(home: Path, entry: str = "", entry_base: str = "") -> dict:
    hub = _hub_dir(home)
    core = home / CORE_RELPATH
    manifest = home / MANIFEST_RELPATH
    installed = manifest.is_file() or core.is_file()
    # 旧外置中枢写的是 hub-lean/，这一版写 hub/。两棵树不是一回事，
    # 不能把旧的当「已装」，但也不许装作没看见 —— 主人问「我装过的呢」时要答得出来。
    legacy = home / "hub-lean"
    state = {
        "installed": installed,
        "manifest": manifest.is_file(),
        "core_kb": 0.0,
        "file_count": 0,
        "version": "",
        "installed_at": "",
        "base_name": "",
        "guest_name": "",
        "hub_name": "",
        "base_card_sha": "",
        "guest_card_sha": "",
        "hub_card_sha": "",
        "entry_blocks": 0,
        "entry_ok": False,
        "entry_note": "",
        "legacy": legacy.is_dir(),
        "legacy_files": _count_files(legacy) if legacy.is_dir() else 0,
    }
    state.update(_entry_state(home, entry, entry_base))
    if installed:
        try:
            state["core_kb"] = round(core.stat().st_size / 1024.0, 1) if core.is_file() else 0.0
        except OSError:
            state["core_kb"] = 0.0
        state["file_count"] = _count_files(hub) if hub.is_dir() else 0
        if manifest.is_file():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            entry = data.get("entry_file") or {}
            state["version"] = str((data.get("package") or {}).get("version") or "")
            state["installed_at"] = str(data.get("installed_at") or "")
            state["base_name"] = str((entry.get("base") or {}).get("name") or "")
            state["guest_name"] = str((entry.get("guest") or {}).get("name") or "")
            state["hub_name"] = str((entry.get("hub") or {}).get("name") or "")
            state["base_card_sha"] = str((entry.get("base") or {}).get("card_sha256") or "")
            state["guest_card_sha"] = str((entry.get("guest") or {}).get("card_sha256") or "")
            state["hub_card_sha"] = str((entry.get("hub") or {}).get("card_sha256") or "")
    return state


# ---------------------------------------------------------------- 对外接口

def _resolve_entry(home: Path, spec: dict) -> str:
    """和 03-bundle 的 hosts.py 一样：主入口没有就退到备用入口，报实际存在的那份。"""
    candidates = (spec.get("entry") or "AGENTS.md",) + tuple(spec.get("entry_alternates") or ())
    for rel in candidates:
        if (home / rel).is_file():
            return rel
    return candidates[0]


def describe_host(spec: dict, base: Path | None = None) -> dict:
    root = base if base is not None else user_home()
    home = _resolve_home(spec, root)
    entry = _resolve_entry(home, spec)
    entry_base = str(spec.get("entry_base") or "")
    # 扫到/手加的家：把名单里同款宿主的槽位继承过来（omp 的 RULES.md + PERSONALITY.md）
    if spec.get("custom") or spec.get("extra"):
        inh_entry, inh_base = _inherit_slots(spec, home)
        if inh_base:
            entry_base = inh_base
            if inh_entry and not (home / entry).is_file():
                entry = inh_entry
    entry_path = home / entry
    exists = home.is_dir()
    row = {
        "id": spec["id"],
        "name": spec["name"],
        "home": str(home),
        "entry": entry,
        "entry_base": entry_base,
        "entry_base_exists": bool(entry_base) and (home / entry_base).is_file(),
        "entry_exists": entry_path.is_file(),
        "exists": exists,
        "custom": bool(spec.get("custom")),
        "scanned": bool(spec.get("extra")),
    }
    row.update(_install_state(home, entry, entry_base))
    if spec.get("extra") or spec.get("custom"):
        run = _custom_process_state(home)
        row.update({"running": bool(run["running"]), "running_known": bool(run["known"]),
                    "pids": list(run["pids"]),
                    "auto": True, "why": "你手填的家目录" if spec.get("custom") else "扫到的家目录"})
        return row
    run = process_state(spec["id"])
    row["running"] = bool(run["running"])
    row["running_known"] = bool(run["known"])
    row["pids"] = list(run["pids"])
    row["why"] = "名单里的"
    return row


def list_hosts(include_missing: bool = False, deep: bool = False) -> list[dict]:
    """include_missing=False 时把「没有这家」的藏起来——老中枢就是这么干的，
    列表干净，扫不到才不会看花眼。扫到和手加的那几家本来就在盘上，一律列。

    「被你点名不列」的那几家也不列。以前它只挡扫出来的那几家，点在 Codex 这类
    内置名单上等于点了没反应——一个骗人的按钮。现在对所有家都真生效，
    恢复的入口在页面右边的扫描报告里。
    """
    base = user_home()
    rows = [describe_host(spec, base) for spec in host_specs(deep=deep)]
    rows.extend(_test_rows())
    if not include_missing:
        rows = [r for r in rows if r["exists"]]
    ignored = load_ignored()
    if ignored:
        rows = [r for r in rows if _key_of(Path(r["home"])) not in ignored]
    return rows


def kill_host_processes(host_id: str) -> dict:
    """终止指定智能体运行中的进程。
    只杀根据指纹探测到的这家的进程，不碰其他无关进程。
    """
    invalidate_cache()
    host = get_host(host_id)
    if host is None:
        return {"ok": False, "error": "没有这家智能体。"}
    pids = [int(p) for p in host.get("pids", []) if isinstance(p, int) or (isinstance(p, str) and str(p).isdigit())]
    if not pids:
        return {"ok": True, "killed": [], "remaining": [], "message": "没有正在运行的进程。"}

    if os.name == "nt":
        cmd = ["taskkill", "/F", "/T"]
        for pid in pids:
            cmd.extend(["/PID", str(pid)])
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            pass
        for pid in pids:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    timeout=5,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception:
                pass
    else:
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except (OSError, AttributeError):
                pass

    time.sleep(0.3)
    invalidate_cache()
    new_host = get_host(host_id)
    new_pids = set(new_host.get("pids", []) if new_host else [])
    killed = sorted(set(pids) - new_pids)
    remaining = sorted(new_pids)
    if remaining:
        return {
            "ok": False,
            "killed": killed,
            "remaining": remaining,
            "error": f"已关闭 {len(killed)} 个进程，但仍有 {len(remaining)} 个进程未能退出。",
        }
    return {
        "ok": True,
        "killed": killed,
        "remaining": [],
    }


def get_host(host_id: str) -> dict | None:
    base = user_home()
    for spec in host_specs():
        if spec["id"] == str(host_id or ""):
            return describe_host(spec, base)
    for row in _test_rows():
        if row["id"] == str(host_id or ""):
            return row
    return None


def _test_home_env() -> Path | None:
    """只给自测用的临时宿主家目录，必须落在本模块 TEMP 里，默认不开。"""
    raw = os.environ.get("HUBCONSOLE_TEST_HOME", "").strip()
    if not raw:
        return None
    here = Path(__file__).resolve().parent
    temp_root = (here / "TEMP").resolve()
    try:
        target = Path(raw).resolve()
    except OSError:
        return None
    if target != temp_root and temp_root not in target.parents:
        return None
    return target


def _test_rows() -> list[dict]:
    target = _test_home_env()
    if target is None:
        return []
    row = {
        "id": "fixture",
        "name": "自测用假宿主",
        "home": str(target),
        "entry": _resolve_entry(target, {"entry": "AGENTS.md"}),
        "entry_exists": (target / "AGENTS.md").is_file(),
        "exists": target.is_dir(),
        "fixture": True,
    }
    row.update(_install_state(target, row.get("entry") or ""))
    row.update({"running": False, "running_known": True, "pids": []})
    return [row]


def totals() -> dict:
    rows = list_hosts()
    installed = [row for row in rows if row["installed"]]
    return {
        "hosts_total": len(rows),
        "hosts_installed": len(installed),
        "hosts_present": sum(1 for row in rows if row["exists"]),
        "hosts_scanned": sum(1 for row in rows if row.get("scanned")),
        "hosts_custom": sum(1 for row in rows if row.get("custom")),
        "core_kb": round(sum(row["core_kb"] for row in installed), 1),
        "file_count": sum(row["file_count"] for row in installed),
        "running": sum(1 for row in rows if row["running"]),
        "installed_ids": [row["id"] for row in installed],
    }


def scan_report(deep: bool = False) -> dict:
    """扫了一遍的账：扫到几家、跳过了几家、为什么。页面上要说得出来。"""
    base = user_home()
    found = discover_extra(deep=deep)
    ignored = load_ignored()
    skipped = sorted(
        str(p) for p in (extra for extra in _skipped_candidates() if extra)
    )
    return {
        "roots": [str(root) for root, _ in scan_roots()],
        "found": [row["name"] for row in found],
        "found_homes": [row["home"] for row in found],
        "custom": len(load_custom()),
        "ignored": len(ignored),
        "ignored_homes": ignored_homes(),
        "filtered": int(_deep_cache.get("filtered") or 0),
        "skipped": skipped[:40],
        "deep": bool(deep),
        "everything": bool(_es_bin()),
        "user_home": str(base),
    }


def _skipped_candidates() -> list[Path]:
    """被跳过的点目录：页面要点名，不然主人看到没列又不知道去哪找。

    扫描根本身（.config）不算 —— 它是「看了的位置」，不是「没列出来的家」。
    """
    base = user_home()
    rows: list[Path] = []
    roots = {_key_of(root) for root, _ in scan_roots()}
    try:
        children = list(base.iterdir())
    except OSError:
        return rows
    known = {_key_of(base / s["home"]) for s in HOST_SPECS}
    known |= {_key_of(Path(r["home"])) for r in load_custom()}
    for child in children:
        if not child.is_dir() or not child.name.startswith("."):
            continue
        if child.name in EXTRA_SKIP or _key_of(child) in roots:
            continue
        if _key_of(child) in known or _entry_in(child) or _surface_of(child):
            continue
        rows.append(child)
    return rows
