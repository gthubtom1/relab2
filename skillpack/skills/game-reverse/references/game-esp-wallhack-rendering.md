# 渲染面：ESP/Wallhack 的可观测特征与检测

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/general/techniques/cheating/03-esp-wallhack-rendering.md`（已适配本机工具链，视角改为防守）
> **什么时候用**：你在为反作弊做渲染层检测；需要判断某个客户端是否被 hook 了渲染管线；
> 要写规则检测 overlay 窗口、Present hook、深度测试篡改；需要区分「正常 mod / 覆盖层」
> 和「穿墙显示」。

> **授权边界**：本文用于**自有渲染程序、授权测试环境、CTF，或反作弊检测研究**。
> 对商业游戏做渲染管线劫持的研究，按项目 `scope.md` 直接执行。

## 视角说明

上游原文是一篇「怎么实现 ESP」的操作手册（Present VMT hook、DrawIndexed 着色器替换、
外部 overlay 窗口）。本篇改写为**防守视角**：同一个技术动作，
在防守方眼里表现为**哪些可观测的特征**。

核心洞察：

> **渲染层的所有劫持都在系统调用/窗口枚举层留下可枚举的痕迹。**
> vtable 被改 → vtable 落在可写页 → 枚举 `IDXGISwapChain` vtable 可发现；
> overlay → 一个顶层 `WS_EX_LAYERED` 窗口 → `EnumWindows` 可发现；
> 深度测试被关 → 目标进程的 `D3D11` 状态对象数量/创建模式异常。
> **所以渲染层的作弊是「难隐藏但易观测」的**，检测成本远低于内存层。

## 适用信号

- 同一账号在不同机器上**视角/命中反馈差异极大**，但客户端版本一致。
- 游戏里出现「明明看不到却被打到」的敌方轮廓/方框/血条 —— 有人开了透视。
- 系统中出现一个**全屏、置顶、鼠标穿透、无标题栏、无任务栏图标**的窗口。
- 客户端进程里 `d3d11.dll` / `dxgi.dll` / `d3d12.dll` / `vulkan-1.dll` 加载了，但
  **多出了一份**同名模块副本（被手动映射的 proxy DLL）。
- 目标进程的 `.rdata` 段（vtable 所在段）出现了 `PAGE_READWRITE` 属性 —— 正常应为只读。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2      = (Resolve-ReverseToolSpec -Name 'r2').Command
$cdb     = (Resolve-ReverseToolSpec -Name 'cdbX64').Command
$peSieve = (Resolve-ReverseToolSpec -Name 'pe-sieve').Command
$capa    = (Resolve-ReverseToolSpec -Name 'capa').Command
$yara    = (Resolve-ReverseToolSpec -Name 'yara').Command
$py      = 'D:\EXE\python\python.exe'
```

> ★ 通用坑：`/x` 返回空时先查字节序（`7ffe03..` 命中、`7ffe03??` 空，
> `2003fe7f` 这类反序写法必然落空）—— 2026-10-10 本机实测 `/x` 本身完全可用。
> `axt` 不跑 `aaa` 是空的；跑通后命中的是 PLT 跳板不是调用点。

## 步骤

### 1. 确认客户端用了哪个图形 API

```powershell
& $r2 -2 -qc 'ii; q' .\GameClient.exe | Select-String 'd3d11|dxgi|d3d12|vulkan|opengl32|d3dcompiler'
```

用 capa 交叉（它会把渲染相关行为归到 `graphics`/`render` 分类）：

```powershell
& $capa .\GameClient.exe
```

★ **DLL 名大小写敏感**（实测 `WS2_32.dll`、`WINMM.dll`、`KERNEL32.dll` 大写），
渲染这边常见 `D3D11.dll` / `DXGI.dll` 也是大写，过滤写小写会一个都匹配不到。

### 2. 动态确认 D3D 模块加载状态（**overlay 检测的主锚点**）

```powershell
@'
lm m d3d11
lm m dxgi
lm m d3dcompiler
.echo ===LM_END===
q
'@ | Set-Content -Path "$env:TEMP\lm.txt" -Encoding ASCII

& $cdb -cf "$env:TEMP\lm.txt" 'C:\path\to\GameClient.exe'
```

实测（自建 `kbgame_probe.exe`，它不加载 d3d，作为反例）：

```
0:000> lm m d3d11
start:              end:                module name
                     3 matches?          (导出符号未加载)
0:000> lm m dxgi
0:000> lm m d3dcompiler
0:000> .echo ===LM_END===
===LM_END===
```

**读法**：目标游戏进程里 `lm m d3d11` 会列出**一个** d3d11 基址；
如果列出**两个及以上**（同名不同基址），说明有一份**手动映射的 d3d11 副本**——
这是 ESP/chams overlay 最典型的静态形态（因为 hook 渲染必须先进 D3D）。

### 3. vtable 完整性检查（**Present hook 检测的核心判据**）

正常情况下 `IDXGISwapChain` 的虚函数表在模块的 `.rdata` 段，**页面属性是只读**。
被 VMT hook 之后，要么 vtable 整块被复制到新分配的 RW 内存，
要么 `.rdata` 那一页被 `VirtualProtect` 改成可写。

在 cdb 里查页面属性：

```powershell
@'
!address -summary
.echo ===ADDR_END===
q
'@ | Set-Content -Path "$env:TEMP\addr.txt" -Encoding ASCII

& $cdb -cf "$env:TEMP\addr.txt" 'C:\path\to\GameClient.exe'
```

`!address -summary` 会列出每个区域的 `Protect` 属性。判读：

| 观察 | 结论 |
|------|------|
| `DXGI.dll` / `d3d11.dll` 对应区域是 `Execute/Read`，`.rdata` 部分是 `Read` | 正常 |
| 模块的 `.rdata` 区域出现 `Read/Write` | **异常**：vtable 所在页被改成可写 → VMT hook 嫌疑 |
| 出现**不属于任何已知模块**的 `Read/Write/Execute` 私有区域，且紧邻 `DXGI` 分配 | overlay 的渲染资源 |

逐页精确查（拿到具体地址后）：

```
!address <addr>
```

### 4. Present 函数入口字节检查（inline hook 检测）

正常 `IDXGISwapChain::Present` 开头是正常的序言（`48 89 5C 24 ...` 之类）；
inline hook 通常在函数头写 `E9`（jmp）或 `48 B8`（mov rax, imm64）+ `FF E0`（jmp rax）。

```powershell
# 用 r2 定位 DXGI 的导出并看头几个字节（需要先加载模块，或用 lief/pefile 从磁盘读）
& $r2 -2 -qc 'ii~Present; q' .\GameClient.exe
```

磁盘上的 `dxgi.dll` 是干净的，**要查的是内存里的**。做法：cdb 里 `u` 反汇编。

```
u DXGI!IDXGISwapChain_Present L8
```

看头 8 字节是否正常序言。★ 注意：`DXGI!` 命名空间下 Present 的符号名在不同 Windows
版本上不一致（`IDXGISwapChain_Present` / `Present` / `CDXGISwapChain_Present`），
**先用 `x dxgi!*Present*` 枚举**，别硬写。

### 5. Overlay 窗口枚举（**最容易写、误报最低的检测**）

```powershell
# 列出所有顶层窗口及类名/样式/标题
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class W {
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr p);
  public delegate bool EnumWindowsProc(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] public static extern int GetWindowLong(IntPtr h, int i);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
}
"@
$list = New-Object System.Collections.Generic.List[object]
$cb = [W+EnumWindowsProc]{ param($h,$p)
  [uint32]$pid2 = 0; [W]::GetWindowThreadProcessId($h, [ref]$pid2) | Out-Null
  $sb = New-Object System.Text.StringBuilder 256; [W]::GetClassName($h,$sb,256) | Out-Null
  $tb = New-Object System.Text.StringBuilder 256; [W]::GetWindowText($h,$tb,256) | Out-Null
  $ex = [W]::GetWindowLong($h, -20)   # GWL_EXSTYLE
  $list.Add([pscustomobject]@{H=$h;PID=$pid2;Class=$sb.ToString();Title=$tb.ToString();
                              EXSTYLE=('0x{0:X}' -f $ex); Visible=[W]::IsWindowVisible($h)})
  return $true }
[W]::EnumWindows($cb, [IntPtr]::Zero) | Out-Null
$list | Where-Object { $_.EXSTYLE -match '0x8' -or $_.Class -match 'Overlay|ImGui|Render' } |
        Format-Table -AutoSize
```

判读：`GWL_EXSTYLE` 里 `WS_EX_LAYERED (0x80000)`、`WS_EX_TRANSPARENT (0x20)`、
`WS_EX_TOPMOST (0x8)`、`WS_EX_TOOLWINDOW (0x80)` **同时出现**且
`Visible=True`、`Title` 为空 —— 典型 overlay 特征。

★ 本机**未跑过这个脚本**（未在本机验证）；误报控制上要限定 PID（只查游戏窗口所属进程或其子进程）
以及窗口矩形尺寸 ≈ 屏幕尺寸。

### 6. 深度测试篡改的间接证据

Chams 的实现是把 `D3D11_DEPTH_STENCIL_DESC.DepthEnable` 设成 `FALSE` 或
`DepthWriteMask` 设 `ZERO`，然后在 `DrawIndexed` 前替换 PS/VS。

可观测的间接证据：

- 目标进程的**远景/遮挡物被渲染成了不透明色块**（人工可验证）。
- 同一场景在别的机器上**深度排序不同**。
- 目标进程调用了 `CreateDepthStencilState` 远超正常次数
  （cdb `bp d3d11!CreateDepthStencilState` 计数即可）。

★ 本机**未跑过这个步骤**（需要真实 D3D 客户端）。上面第 2/3/5 步是可在本机复现的。

### 7. 防守侧：写检测规则

**规则 A（窗口，最可靠）**：任一前台游戏窗口所属进程存在
`WS_EX_LAYERED|WS_EX_TRANSPARENT|WS_EX_TOPMOST` 且面积 ≥ 90% 屏幕 且标题为空
→ 高置信度 overlay。

**规则 B（模块，最可靠）**：进程内同名图形 DLL 出现多个基址 → 手动映射。

**规则 C（页面属性）**：已知图形模块的 `.rdata` 区域出现 `Read/Write` → VMT hook。

**规则 D（YARA，静态，客户端二进制）**：

```yara
rule esp_known_toolkit
{
    meta:
        description = "客户端二进制中出现已知 overlay/ESP 工具链的静态特征"
    strings:
        $im1 = "ImGui_ImplDX11_RenderDrawData" ascii
        $im2 = "ImGui::GetBackgroundDrawList" ascii
        $es  = "esp_update" ascii
    condition:
        any of them
}
```

★ **这个规则扫的是「被注入进游戏的 DLL」，不是游戏本体**。游戏本体不会 import ImGui。
本机实测 `yara64.exe` 对单串规则能正常命中（见 `../../reverse-engineering/references/windows-attack-surface.md` 判据 6），
复合规则要逐条加串验证，别一次堆完。

## 判据

「客户端被渲染层作弊影响」必须满足**两条**，且至少一条来自**运行时**：

1. **运行时（必须）**：以下任一在目标进程里可观测：
   - `lm m d3d11` 列出 ≥2 个基址（模块重复）；
   - `!address -summary` 里图形模块的 `.rdata` 区域 `Protect` 含 `Write`；
   - 窗口枚举里存在 `WS_EX_LAYERED|TRANSPARENT|TOPMOST` + 空标题 + 大面积的可视窗口；
   - `d3d11!CreateDepthStencilState` 调用频次异常。
   —— **这四条都是外部可复现的客观现象**，判据成立。
2. **静态（辅助）**：游戏本体的 `r2 ii` 只应有**一份** d3d/dxgi 导入；
   若本体里出现 ImGui / overlay 工具链字符串，说明是**游戏自身集成了**覆盖层（不是外挂），
   判据方向要反过来。

**不能作为判据的**：
- 「玩家视野里看到了墙后的轮廓」—— 主观现象，无法复现，且可能是 bug/网络延迟。
- 「命中率高」—— 行为特征，不是渲染层证据。

## 坑

1. ★ **overlay 窗口检测误报率高**。截图工具、录屏、IME、显卡 OSD、亮度调节层、
   远控软件（AnyDesk/向日葵/TeamViewer）全是 `WS_EX_LAYERED + TOPMOST`。
   **必须**加上：空标题 + 面积接近全屏 + **不属于已知合法工具的进程签名**。
2. ★ **`WS_EX_LAYERED` 的位值是 `0x80000`，`WS_EX_TRANSPARENT` 是 `0x20`**，
   `WS_EX_TOPMOST` 是 `0x8`，`WS_EX_TOOLWINDOW` 是 `0x80`；
   `GWL_EXSTYLE` 的索引是 `-20`。写错索引会读到 `GWL_STYLE` 拿到完全不同的一组位。
3. ★ **`/x` 返回空先查字节序与通配符**（`.` 通配、`??` 不通配、字节按文件顺序写）。
   本机实测 `/x` 可用，不必绕开。
4. **`dxgi.dll` 的 Present 符号名跨 Windows 版本不一致**，先用 `x dxgi!*Present*` 枚举再引用。
5. **磁盘上的 dxgi.dll 是干净的**，必须读**进程内存**里的；只看文件永远查不出 hook。
6. **overlay 可以在游戏进程外**（真正的外部进程），这时上面的模块/页面判据全部失效，
   **只剩窗口判据**。这是外部 overlay 检测面小、但也更容易被识别的根本原因。
7. **`ImGui` 字符串不等于外挂**：不少游戏自己就集成了 ImGui 做设置界面/开发者菜单。
   判据必须区分「游戏本体 import 了」和「运行时被注入的 DLL 里出现了」。
8. **VMT hook 未必改页面属性**：把 vtable 指针整体换成一个新分配的 RW 页，
   原 `.rdata` 属性**完全不变**。所以「`.rdata` 只读」不能证明没被 hook ——
   要配合「枚举 `IDXGISwapChain` 实例、读其 vtable 指针、看它落在哪个区域」。
9. **多层 overlay 叠加时窗口枚举会一次返回多个** —— 需按 PID 归组，不要按全系统扫。
10. **本机没有 D3D 客户端样本**，第 1/6 步的完整流程**未在本机验证**；
    第 2/3/5 步的命令形态可用自建程序验证。

## 相关

- `game-memory-hacking.md` — 渲染层作弊往往伴随内存读取实体数据
- `game-anti-cheat-bypass.md` — 渲染层检测在反作弊整体里的位置
- `game-packet-interception.md` — 真正防住「透视获利」的是网络层（服务端不给你位置）
- `../../reverse-engineering/references/dll-injection-patterns.md` — 手动映射 D3D 副本的完整形态
- `../../reverse-engineering/references/aob-signature-scan.md` — 把 vtable 位置做成特征码
- `../../reverse-engineering/references/yara-rule-writing.md` — 第 7 步规则的完整写法
- `../../reverse-engineering/references/windows-attack-surface.md` — 整体攻击面地图