import sys, os, json, shutil

agent_dir = os.path.expandvars(r'%USERPROFILE%\.omp\agent')
active_mcp = os.path.join(agent_dir, 'mcp.json')
full_mcp = os.path.join(agent_dir, 'mcp.all.json')

profile = sys.argv[1] if len(sys.argv) > 1 else 'show'

if not os.path.exists(full_mcp) and os.path.exists(active_mcp):
    shutil.copy(active_mcp, full_mcp)

if profile == 'daily':
    with open(full_mcp, 'r', encoding='utf-8') as f:
        data = json.load(f)
    daily = {
        "$schema": data.get("$schema"),
        "mcpServers": {
            "pyghidra-mcp": data.get("mcpServers", {}).get("pyghidra-mcp")
        }
    }
    with open(active_mcp, 'w', encoding='utf-8') as f:
        json.dump(daily, f, indent=4, ensure_ascii=False)
    print(">>> 已切换为 [日常轻量模式 (daily)]")
    print("    - 活跃 MCP: pyghidra-mcp (20 个工具)")
    print("    - 卸载 MCP: ida-pro-mcp, idapro, x64dbg-automate-mcp, angr-mcp")
    print("    - 释放上下文空间: ~25,000 Tokens / 轮")
    print("    - 提示: 重新打开或新建 agent 会话后生效。")

elif profile == 'full':
    shutil.copy(full_mcp, active_mcp)
    print(">>> 已切换为 [全量逆向攻坚模式 (full)]")
    print("    - 活跃 MCP: 全部 5 个逆向服务器 (140+ 个工具)")
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
