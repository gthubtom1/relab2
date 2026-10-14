import sys, os, json, shutil

agent_dir = os.path.expandvars(r'%USERPROFILE%\.omp\agent')
active_mcp = os.path.join(agent_dir, 'mcp.json')
full_mcp = os.path.join(agent_dir, 'mcp.all.json')

profile = sys.argv[1] if len(sys.argv) > 1 else 'show'

if not os.path.exists(full_mcp) and os.path.exists(active_mcp):
    shutil.copy(active_mcp, full_mcp)

if profile == 'daily':
    # ★ 2026-10-15 改：daily 原来只留 pyghidra-mcp，会把 idapro / x64dbg-mcp / angr-mcp
    #   从活跃配置里**删掉** —— 于是模型手上又只剩一条通道，回到"拿着枪不会用"。
    #   现在 idapro / x64dbg-mcp 走 stdio 懒启动代理（mcp-lazy-http.py）：
    #   工具常驻可见，后端只在**真被调用**时才拉起，不再有"冷启失败 / 弹窗"的代价，
    #   所以 daily 与 full 合并，两者都表示"全部登记"。
    shutil.copy(full_mcp, active_mcp)
    with open(active_mcp, 'r', encoding='utf-8') as f:
        n = len(json.load(f).get("mcpServers", {}))
    print(">>> [全部登记] daily 与 full 已合并（懒启动代理上线后不再需要切来切去）")
    print(f"    - 活跃 MCP: {n} 个（工具常驻可见；IDA/x64dbg 后端只在被调用时自动拉起）")
    print("    - 提示: 重新打开或新建 agent 会话后生效。")

elif profile == 'full':
    shutil.copy(full_mcp, active_mcp)
    with open(active_mcp, 'r', encoding='utf-8') as f:
        n = len(json.load(f).get("mcpServers", {}))
    print(">>> 已切换为 [全量逆向攻坚模式 (full)]")
    print(f"    - 活跃 MCP: {n} 个")
    print("    - 提示: 重新打开或新建 agent 会话后生效。")

else:
    if os.path.exists(active_mcp):
        with open(active_mcp, 'r', encoding='utf-8') as f:
            data = json.load(f)
        servers = list(data.get("mcpServers", {}).keys())
        print(f"当前 MCP 状态 ({active_mcp}):")
        print(f"  活跃服务数: {len(servers)} ({', '.join(servers)})")
    else:
        print("mcp.json 不存在")
