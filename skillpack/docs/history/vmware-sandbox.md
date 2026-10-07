> **【已归档 · 2026-10-05】旧架构文档，不再适用。**
> 本文档描述的是「宿主 agent 通过 SSH / vmrun / MCP 遥控 VMware 客户机」的旧架构；2026-10-05 起 agent 与工具全部运行在同一隔离环境内，无跨设备控制。
> 文中 `vmrun` / `new-workvm.cmd` / `rework_key` / `192.168.232.*` / 共享文件夹 / `C:\RE-Lab` 等路径与通道均已作废，**不要照做**。
> 保留此文件仅为历史参考；现行运行环境见 `skills/SKILL.md` 的 EXECUTION ENVIRONMENT 段。

# VMware 靶机隔离与自动化执行手册 (VMware Sandbox Manual)

> 本文档记录本机专有 VMware 靶机自动化克隆、控制器路径及免密远程执行流水线。
> 当任务涉及未受控未知二进制运行、加壳对抗、内存挂钩、驱动加载、动态调试时按需查阅。

## 1. 母盘保护铁律 (Highest Priority)
- **母盘路径**: `E:\Vm-iso\muji\母鸡.vmx`（显示名: "母鸡-禁止使用"）
- **黄金快照**: `GoldenBase-20261003`
- **绝对红线**: 严禁开机跑业务、严禁删除快照、严禁合并磁盘、严禁移动或重命名 `muji` 目录内文件（所有工作机链条强依赖母盘）。

## 2. 自动化工作机流水线 (One-Click VM Creation)
- **创建新工作机**:
  - 宿主命令行执行: `D:\HACKER\_clone\new-workvm.cmd`（或 `powershell -File D:\HACKER\_clone\new-workvm.ps1 [-SkipShare]`）
  - 自动化流程: 自动关闭旧机 ➔ 从 GoldenBase-20261003 创建链接克隆 ➔ 规范重命名 ➔ 随机化 MAC 地址 ➔ 挂载共享盘。
  - 备查说明: `D:\HACKER\_clone\README.md`

## 3. 控制器工具 (vmrun CLI)
- **控制器路径**: `E:\Vmware\vmrun.exe`（**严禁**使用 `C:\Program Files` 下的错误路径）
- **常用命令模板**:
  - 列出运行中的虚拟机: `E:\Vmware\vmrun.exe -T ws list`
  - 启动虚拟机: `E:\Vmware\vmrun.exe -T ws start "<vmx路径>" gui|nogui`
  - 关闭虚拟机: `E:\Vmware\vmrun.exe -T ws stop "<vmx路径>" soft`
  - 恢复快照: `E:\Vmware\vmrun.exe -T ws revertToSnapshot "<vmx路径>" "<快照名>"`

## 4. SSH 免密远程执行通道 (首选交互方式)
- **用户名**: `toti`
- **专用私钥**: `$env:USERPROFILE\.ssh\rework_key`
- **动态 IP 发现**:
  - 宿主执行: `Get-NetNeighbor -AddressFamily IPv4 | ? IPAddress -like '192.168.232.*'`
- **远程执行命令**:
  ```powershell
  ssh -i "$env:USERPROFILE\.ssh\rework_key" -T toti@<IP> "<cmd>"
  # 执行 PowerShell 必须包裹:
  ssh -i "$env:USERPROFILE\.ssh\rework_key" -T toti@<IP> "powershell -NoProfile -Command \"<cmd>\""
  ```
- **文件传输 (SCP)**:
  ```powershell
  scp -i "$env:USERPROFILE\.ssh\rework_key" <本地文件> toti@<IP>:<远程路径>
  ```
- **共享文件夹在非交互 SSH 会话内完全不可用**（本机实测：`VMTools` / `vmhgfs` 驱动均 RUNNING，
  但 `Test-Path \\vmware-host\` 返回 False，`dir Z:\` 报路径不存在）。
  **文件传输唯一通道是 `scp` / `sftp`。** 共享盘只用于交互式桌面会话下的人工便利，
  禁止作为 agent 自动化流程的文件通道。

> §4 为速查；带超时与 `-n` 的完整 SSH 用法见 **§6**（本包纪律要求 ssh 必带 `ConnectTimeout` 与 `</dev/null`/`-n`）。快照操作见 **§7**（§3 未含 snapshot，且必须异步）。

## 5. 启动与 IP 发现 (Start & IP Discovery)
- **启动工作机（异步，勿同步等待）**:
  ```powershell
  E:\Vmware\vmrun.exe -T ws start "<vmx路径>" nogui   # 启动后另用 getGuestIPAddress -wait 取 IP
  ```
  `start gui` 会拉起图形窗口并可能不返回；控制台/自动化场景一律 `nogui`，需要图形时由人在 VM 侧或经 vmrun 连通后处理。
- **取客户机 IP（带等待上限，优于自己扫邻居表）**:
  ```powershell
  E:\Vmware\vmrun.exe -T ws getGuestIPAddress "<vmx路径>" -wait
  ```
- **动态 IP 发现（备选，宿主邻居表）**:
  ```powershell
  Get-NetNeighbor -AddressFamily IPv4 | ? IPAddress -like '192.168.232.*'
  ```
- **先验连通再跑业务**（避免 ssh 静默挂起/打错 IP）:
  ```bash
  ssh -n -o ConnectTimeout=5 -i "$USERPROFILE/.ssh/rework_key" toti@<IP> "echo ok"
  ```

## 6. SSH 免密远程执行通道（完整版，必带超时与 -n）
- **必带项**: `-i <key>` + `-o ConnectTimeout=15` + `-n`（或 `</dev/null`）。缺任一项都可能在 banner 警告或密码提示上无限期挂住。
- **用户名**: `toti`；**私钥**: `$env:USERPROFILE\.ssh\rework_key`
- **远程执行**:
  ```bash
  ssh -n -o ConnectTimeout=15 -i "$USERPROFILE/.ssh/rework_key" toti@<IP> "<cmd>"
  # PowerShell 必须显式包裹（远程默认 Shell 是 CMD）:
  ssh -n -o ConnectTimeout=15 -i "$USERPROFILE/.ssh/rework_key" toti@<IP> "powershell -NoProfile -Command \"<cmd>\""
  ```
- **文件传输 (SCP)**:
  ```bash
  scp -o ConnectTimeout=15 -i "$USERPROFILE/.ssh/rework_key" <本地文件> toti@<IP>:<远程路径>
  ```
- **会话 0 铁律**: 严禁用 `Z:` 盘符判断共享盘；唯一判据 `Test-Path '\\vmware-host\Shared Folders'`。

## 7. 快照：异步快照（本次事故现场）
> 事故：2026-10-04 会话 `01a107ea` 中 `vmrun snapshot` 对运行中的客户机同步写快照，客户机带 GUI + Defender 实时扫描 + 快照锁争用，命令无限期挂起，模型全程不运行且不自愈（终端计时器涨、token 静止）。**§3 原本根本没有 snapshot 命令**，这不是用错，是漏写。

**禁止 `vmrun snapshot` 同步阻塞调用。唯一正确写法 = 后台执行 + 轮询 `*.vmsn` 是否落地。**

```bat
:: 后台起快照，日志落盘，立即返回
start /b "E:\Vmware\vmrun.exe" -T ws snapshot "<vmx>" > "%TEMP%\snap.log" 2>&1 &

:: 轮询：*.vmsn 出现即完成（最多约 5 分钟）
for /l %%i in (1,1,60) do ( dir /b "<vmx目录>\*.vmsn" >nul && (echo SNAP-READY & break) || (timeout /t 5 & ping -n 2 127.0.0.1 >nul) )
```

- **校验**: 快照完成后必须确认 `*.vmsd` 已记录该快照名，`*.vmsn` 落地才算成功。
- **失败处理**: 超时未落地判失败，重试一次；仍失败则放弃并报告，**不得**转而同步阻塞等待。
- **母盘红线（§1 复述）**: 严禁对 `muji` 母盘做 `snapshot` / `stop` / `delete`——它只提供黄金快照 `GoldenBase-20261003` 给工作机克隆，任何写操作会破坏所有工作机的启动链。

## 8. 产物回收（销毁 VM 前 MUST 执行）
工作 VM 是可重建环境，**不是数据仓库**。以下内容 MUST 回收并落宿主项目目录：

| 类别 | 内容 |
|---|---|
| `metadata/` | `project.json`（项目ID、Base 版本、VM UUID、工具版本、最后一次同步时间） |
| `samples/` | 原始样本 + SHA256 |
| `dumps/` | 内存 dump |
| `patches/` | patched 样本 |
| `scripts/` | 分析脚本（可复用） |
| `captures/` | `*.pcap` / `*.pcapng` |
| `reports/` | `REVERSE-MAP.md`、分析结论 |
| `logs/` | x64dbg / 工具日志 |

回收后逐文件校验哈希，全部一致才允许 revert 快照或删除 VM。
**缺失任意一类 = 项目未完成，禁止销毁。**
回收目录结构（宿主）：`<项目根>/{metadata,samples,dumps,patches,scripts,captures,reports,logs}`

## 9. 项目工作区与工具层基线
客户机工作区：`C:\RE-Lab\Projects\<项目ID>\`（项目ID = 样本 SHA256 前 12 位）。
**禁止**把样本或产物直接丢在 `C:\work` 根目录。

工具层基线：

1. 工具安装与验证在【母机】完成，不在项目工作机上反复安装。
2. 母机装齐后 MUST 逐项做**功能性验证**（见 `TOOLS.md` 的「验证命令」列）。
3. 全绿后关机 → 打快照（命名 `完整工具版-YYYY-MM-DD`）→ **另做一次完整 VM 复制当 Backup**。
   **Snapshot 不是 Backup**，不可作为唯一恢复来源。
4. 之后每个项目 MUST 从该基线快照克隆，**不得从更早的快照克隆**。
5. **母鸡快照名 MUST 唯一**：出现同名快照会导致 `vmrun -snapshot=<name>` 报
   `Invalid snapshot name`（已实测：母鸡现存两个 `GoldenBase-20261003`，uid 4 / uid 6）。
   克隆前用 `vmrun listSnapshots` 核对。**当前唯一有效克隆源是快照 `最新`。**
6. linked clone 不受其他 VM 运行影响（本机已实测：01 号运行中成功克隆 02 号，两台并存）。
