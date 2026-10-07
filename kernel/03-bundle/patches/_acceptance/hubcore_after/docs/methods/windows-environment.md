---
name: windows-environment
description: 处理 Windows 特有的中文空格路径、权限/UAC、编码乱码、服务/注册表、进程坑。在 Windows 上遇到这些问题时用。
purpose: Windows 特有的路径/权限/编码/服务/注册表 坑的处理
use_when: 在 Windows 上遇到中文空格路径、权限/UAC、编码乱码、服务/注册表、进程相关问题
phase: exe-rebuild, desktop-product, web-service, cli-tool, source-takeover
needs: [PowerShell 或宿主提供的等价系统能力]
---

# Windows 环境方法

对主人先白话：做到什么、还缺什么、下一步看哪。一次只说一扇窗、一个键。机械项自己跑；主功能给人话清单等人测；做不到当场说。两句不能互相吞掉。乱码/路径只是中途一刀。做完按 WORK-HANDOFF 的方法调用链，回到直接调用方尚未做完的动作；主线的授权、打包与交付要求继续有效（见 `docs/ENGINEERING-CONTINUITY.md` 的当前工作包）。stdout 写了 `wrote` ≠ 屏上中文对。

## 路径

- 中文/空格路径对很多逆向/命令行工具不可靠 → 另开一整段都是 ASCII 的工作区（可以在产品根外面，不要挂在中文/空格产品根下）。跑完把**要留下的**拷回产品里的工作拷贝（不要放进 `TEMP/`），核哈希；ASCII 工作区当场删。
- 产品根是中文/空格时，产品根 `TEMP/` 也在这条路径上，**不能**拿它当 ASCII 工作区。`TEMP/` 只收绑回之后仍要丢掉的日志/草稿。
- 别写死盘符/用户名当产品路径；ASCII 工作区用短英文路径，用完就删。

## 编码

- 读文件按 `utf-8-sig`（吃掉 BOM）；PowerShell 传内嵌引号的 JSON 会被吞——用 `--data-file`。

## 权限 / 服务 / 注册表

- 需要管理员的操作先说明、要用户确认；改注册表/服务先备份、能还原。

## 找工具 / 文件

- 按 `<hub>/TOOLING.md`：tools.local.json 优先，其次源树 tools.json；再查宿主工具、PATH、已知安装位置，已有 Everything 时可用它。先做无副作用能力检查，不能因一个工具缺失就让主人接手机械调查。

## 别假装

- PATH 里有 ≠ 真能调用；装了 ≠ 当前会话/宿主能用。
