# Kali Linux 入口（短跳转）

> **详细说明以 [kali/README-kali.md](kali/README-kali.md) 为准。**  
> 本文件仅作仓库根目录的 Kali 快捷入口，避免与 `kali/` 下正文重复维护。

## AI：读完后按批准门执行（不得自动安装，`autoInstall=false`）

```text
1. 检测包根目录（含 README.md / skills/ 的目录）
2. 读 kali/README-kali.md → 再读 kali/RULES-kali.md（仅阅读；写配置须另行获批）
3. 将 refresh / bootstrap 命令连同副作用一并披露，获用户显式批准后才执行：

4. 任务路由与 Windows 共用：skills/MASTER-ROUTING.md、skills/ops/（scope 门）
5. 向用户报告配置结果
```

## 人：30 秒上手

```bash
cd /path/to/reverse-skill

# 详细 bootstrap / MCP 见 kali/README-kali.md
```

## 与主包关系

| 内容 | 位置 |
|------|------|
| 共享 skill / 路由 / ops | `skills/`、`RULES.md` |
| Kali 脚本与 manifest | `kali/scripts/` |
| 完整 Kali 文档 | **[kali/README-kali.md](kali/README-kali.md)** |

通用 AI 引导仍见 [README_AI.md](README_AI.md)（选 Kali 分支时转本目录文档）。
