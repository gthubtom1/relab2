# 实弹攻坚记录：从属模块目标（宿主进程依赖）· 2026-10-13

> 脱敏：目标为「伪装成 X 客户端、实际疑似依附 X 游戏的从属模块」。
> ★ **2026-10-13 06:5x 重验修正**：初版把 cdb 的 `0n998` 噪声当成「命中 payload 入口」，
> 已撤销。见「三、重验」与「四、教训」。

## 目标画像

- PE32+ x64 GUI，26 MB，8 节（`.text` / `.rdata` / `.data` / `.pdata` / `.fptable` / `.ace0` / `.reloc` / `.rsrc`）
- 导入表极薄（96 条），功能走 `LoadLibraryExW`/`GetProcAddress` 动态解析（FNV-1a 哈希）
- `.rsrc` 内 21 MB 自定义 blob；`.ace0` 4.6 MB 可执行节
- 启动即自毁：原名 → `0xC0000409`（`__fastfail(7)`）

## 攻克过的层

### 门栓层（外门，一击即破，成本低）

- **名字门**：`GetModuleFileNameW` 取自身名，与硬编码 `RiotClientServices.exe` 做**大小写不敏感**比较。
  原名 → 崩；改名 → 干净退出（16 名对照实验实证）。
- **游戏进程门**（`sub_1400175A0`）：枚举进程找名为 `RiotClientServices.exe` 的在跑进程，返回其 PID。
- **路径门**（`sub_140017B60`）：对 PID 调 `QueryFullProcessImageNameW` 拿镜像路径。
  → **哈希逆推技巧（可复用）**：门里的 FNV-1a 目标立即数 `889188100` 是**导出函数名的哈希**；
  暴力遍历本机 `System32\*.dll` 导出表（8.2 万条）即可反查 → 一次命中
  `QueryFullProcessImageNameW`。**见到 FNV-1a 立即数就暴力匹配导出表。**
- **字符串**：栈上 word 级 XOR，密钥 `k_i = i - 55*(i/55) + 50`。
  解出 `RiotClientServices.exe` 与 `C:\Windows\explorer.exe`。

### 补丁（成功）

- 两处分支 `je` 在 `0x14000211f` / `0x140002132`（各 6 字节 `0f 84 …`）→ NOP。
- **补丁后 GATE(0x2138)/DISPATCH(0x2175)/PAYLOAD-ENTRY(0x4da848) 依次原子命中（5/5 稳定）**
  → 门栓绕过 + **payload 入口确被进入**（`@rip=0x7ff77321a848`，base+RVA 吻合）。

### payload 层（进入后即崩 —— 反篡改专项查明是自解密）

- payload 是**自包含的自解密段**：`ReadProcessMemory` 全是 `handle=-1`（自身进程），
  target 全在自身模块/堆 → **无宿主依赖**（旧「需真实游戏内存」彻底作废）。
- 真实 API 足迹（已剔除命令回显）：`LoadLibraryExW`×17（API-set）+ `GetProcAddress`×80
  （CRT/API-set 动态解析）+ `CreateFileW`×1（ntdll）+ `ReadProcessMemory`×114（自身）。
- 运行时**自翻页** 174 页（`PAGE_NOACCESS`）。强制 RW 后 AV 从 32→2 → **AV 是 fault-driven 解密触发器**。
- 解密未完成即 fail-fast `0xC0000409`（.text 故障点，与既有 A-001 同族）。

## 三个可复用的卡点/心得

1. **FNV-1a 立即数 → 暴力匹配导出表**：立刻把「这函数是谁」从黑盒变白盒。
2. **门栓层别恋战**：外层名字检查往往是一击即破的低成本比较；真工作量在 payload 语义（五条①）。
3. **★ 动态调试判据必须原子 + 多轮 + 剔回显**（本会话连栽四次）：
   ① 自翻页页内下断点，cdb 报 `0n998`（移除失败）**不是命中**；
   ② **单轮**断点结果不能当否证（bp 可能恰好被页翻吞掉）；
   ③ 手算运行时 VA 必须复核 `base+offset`；
   ④ **bp 命令回显不是命中**——WinHttpOpen/CreateWindowExW 我一度当成命中，实为回显，
      真实命中是 0（必须只统计 `g` 之后的输出）。
   正解：判据用断点命令内原子 `@rip`，跑 ≥3 轮，且**严格区分回显与命中**。

## 结论

- 外层门栓**已绕过**，payload 入口**确被进入**（5/5 实证）；payload 是**自包含自解密段**，
  **无宿主依赖**；解密未完成即崩（真卡点 U-003）。
- **成品未出**——如实记卡点。
- **纠正**：本会话同一事实翻转多次（0n998 噪声 / 过度修正 / VA 算错 / 回显当命中），教训已记经验卡。
