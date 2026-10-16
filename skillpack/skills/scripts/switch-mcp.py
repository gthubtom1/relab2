"""switch-mcp.py —— 切换宿主 agent 的 MCP 通道profile（daily / full / show）。

★★ 2026-10-16 修一个"会静默删通道"的缺陷（DocConverge2 实测发现，父代理核实）：
    本脚本原来把 `mcp.all.json` **整份拷贝**覆盖到 `mcp.json`。
    而事实上 `mcp.json` 里可能比 `mcp.all.json` **多**若干条（本机实测：多一个 `rea`——
    那是后来手工/独立加进活跃配置的）。于是跑一次 `daily` 或 `full`，`rea` 就被**拷没**，
    而且不给任何提示。这不是"切模式"，是**静默删配置**。

    修法：改成**合并**语义 —— `mcp.all.json` 为准，但 **`mcp.json` 里 all 没有的通道一律保留**，
    并在输出里明确列出"保留了哪几条"。同时把保留下来的通道**回写进 `mcp.all.json`**，
    让两个文件不再漂移（下次切换也是同一份事实）。

用法（不变）：
    python switch-mcp.py            # 看当前状态
    python switch-mcp.py daily      # 全部登记
    python switch-mcp.py full       # 全部登记（与 daily 合并后等价）
"""
import json
import os
import shutil
import sys

agent_dir = os.path.expandvars(r'%USERPROFILE%\.omp\agent')
active_mcp = os.path.join(agent_dir, 'mcp.json')
full_mcp = os.path.join(agent_dir, 'mcp.all.json')


def _load(path: str) -> dict | None:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _servers(d: dict | None) -> dict:
    return dict((d or {}).get("mcpServers") or {})


def merge_and_apply(label: str) -> int:
    """把 all 合并进 active，保留 active 独有的通道；并把结果回写 all。"""
    full = _load(full_mcp)
    active = _load(active_mcp)
    if full is None and active is None:
        print("两个配置文件都读不到（或者不存在）：")
        print(f"  {active_mcp}\n  {full_mcp}")
        return 2

    fs, as_ = _servers(full), _servers(active)
    if not fs:                       # all 还没有内容 → 用 active 播种
        fs, as_ = as_, {}

    # ★ 合并：all 为准；active 独有的**保留**
    out = dict(fs)
    kept = []
    for k, v in as_.items():
        if k not in out:
            out[k] = v
            kept.append(k)

    doc = dict(full) if isinstance(full, dict) else {}
    doc["mcpServers"] = out
    try:
        os.makedirs(agent_dir, exist_ok=True)
        # 回写 all（保证下次切换是同一份事实）
        with open(full_mcp, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        # 写 active（原子些：先写临时文件再替换）
        tmp = active_mcp + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        shutil.move(tmp, active_mcp)
    except OSError as e:
        print(f"写配置失败：{e}")
        return 2

    print(f">>> [{label}] 已登记 {len(out)} 个 MCP 通道")
    if kept:
        print(f"    ★ 保留了 {len(kept)} 条只存在于活跃配置里的通道（原来会被整份拷贝抹掉）："
              f"{', '.join(kept)}")
    print("    - 工具常驻可见；IDA/x64dbg 后端只在被调用时自动拉起。")
    print("    - 提示: 重新打开或新建 agent 会话后生效。")
    return 0


profile = sys.argv[1] if len(sys.argv) > 1 else 'show'

if profile == 'daily':
    # 2026-10-15：daily 与 full 已合并（懒启动代理上线后不再需要切来切去）。
    sys.exit(merge_and_apply("全部登记"))

if profile == 'full':
    sys.exit(merge_and_apply("全量逆向攻坚模式 (full)"))

# show
data = _load(active_mcp)
if data is None:
    print("mcp.json 不存在或解析失败")
    sys.exit(0)
servers = list(_servers(data).keys())
print(f"当前 MCP 状态 ({active_mcp}):")
print(f"  活跃服务数: {len(servers)} ({', '.join(servers)})")
full_servers = list(_servers(_load(full_mcp)).keys())
missing = [s for s in servers if s not in full_servers]
if missing:
    print(f"  ★ 只在活跃、不在 mcp.all.json 的通道（跑 daily/full 时会被保留，但仍建议补进 all）："
          f"{', '.join(missing)}")
