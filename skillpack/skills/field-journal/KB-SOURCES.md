# 知识库来源与改编约定（KB-SOURCES）

> **这份文件回答三个问题**：这些技术文档从哪来、改编时改了哪些规矩、哪些源文档的说法被本机实测推翻了。
> **什么时候读**：你在 `KB-INDEX.md` 里挑到一篇文档、准备照着跑之前；如果文档里的命令和本机表现不一致，先来这儿核对。
> **配套**：[`KB-INDEX.md`](KB-INDEX.md)（按症状检索）

---

## 1. 来源

| 项 | 值 |
|---|---|
| 上游仓库 | `LING71671/open-reverselab` |
| 取用范围 | 仓库内 `kb/` 知识库目录 |
| 上游 License | **GPL-3.0** |
| 原始副本（本机留存） | `<工具根>\kb-open-reverselab\` |
| 副本规模 | **221 篇 markdown**，约 3.0 MB |
| 副本板块 | `pe-reverse/`（35）· `apk-reverse/`（27）· `general/`（20）· `ctf-website/`（133）· `windows/`（3）· `ai-findings/`（1）· 根目录（2）= **221 篇**（2026-10-16 现算；旧表写的 33/27/17/~150/2 合计 229，与 221 自相矛盾，已改） |
| 已改编落盘 | **209 篇技术正文**（2026-10-16 复测；口径 = `skills/*/references/**` 里带**标准来源声明行**的文件，与 `skillpack/NOTICE` 同判据、可现算；历史值 206/218/221 都是旧快照，勿引用） |

**原副本保留不动**。所有对照、diff、回溯都指向 `<工具根>\kb-open-reverselab\`，
不要去改它 —— 它是 GPL 原始来源，改了就失去溯源意义。

---

## 2. License 说明（**引用改编，不是复制**）

GPL-3.0 允许复制与衍生，前提是**保留许可与声明**。本技能包采取的做法：

1. **每篇文档头部都带来源声明**，格式固定：

   ```markdown
   > **来源**：改编自 `LING71671/open-reverselab` 的 `kb/<原路径>`（已适配本机工具链）
   ```

   「原路径」精确到源库内的文件，便于第三方核对与回溯。

2. **不是整段搬运**。源文档的正文被重写为本机命令、路径、判据，
   保留的是**技术结构与攻击链逻辑**（这部分是知识本身，不是版权表达）。
   上游的 `MCP 工具映射` 章节一律剔除 —— 本技能包没有 `run_ctf_tool` / `http_probe` 这类挂载。

3. **不逐字复制大段散文**。源库的例子、脚本、表格被改写或替换为本机实测版本。

4. **本文件即改编声明**。第三方若要复用改编结果，同样受 GPL-3.0 约束。

---

## 3. 改编规则（**硬规矩，不是建议**）

### 3.1 工具命令一律换成本机实测版本

源文档里的命令是**别人的机器**上的，不改就是误导。每篇必须：

- 用**探测层**取路径，不写死猜测路径：

  ```powershell
  . 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
  $r = Resolve-ReverseToolSpec -Name '<工具id>'
  & $r.Command <参数>          # 永远用完整路径，不依赖 cwd
  ```

- Python 脚本指定**带全部逆向库的那个解释器**，即探测层别名 `pyre`（`(Resolve-ReverseToolSpec -Name 'pyre').Command`）。
  **不要写 `(Resolve-ReverseToolSpec -Name 'pyre').Command`** —— 那是空壳，见 §4。
- 未在本机验证过的命令，**显式标注「未在本机验证」**，不许写成既定事实。
- 工具在本机不存在时，写清**替代方案**，不要照抄上游裸命令。

### 3.2 判据必须外部可观测

**合格**：HTTP 状态码变化、响应体字段变化、两次运行差分、`Breakpoint 0 hit`、
落盘文件的 SHA256、日志里出现的具体字符串、寄存器/栈参数的实际值。

**不合格**：「有输出」「看起来加密了」「工具报告说检测到」「执行成功」。

判据要写成**别人能独立复现的一步**，而不是「确认一下就好了」。

### 3.3 统一文档骨架

每篇固定六节：`适用信号` / `前置` / `步骤` / `判据` / `坑` / `相关`。
`KB-INDEX.md` 的症状列直接从「适用信号」抽取，所以这一节不能省、不能写成套话。

### 3.4 不编造

常量、偏移、工具版本、CVE 编号 —— 没查到就不写。
宁可写「本机未验证/未复现」，也不要写一个看起来很专业的错值。

### 3.5 落盘跟着技能走

文档**不集中堆一处**，按任务类型分发到对应 skill 的 `references/`，
这样 agent 命中 skill 后自然读到相关技法，路由不失焦。
症状级检索统一走 `KB-INDEX.md`（本目录），不另立第二套。

---

## 4. ★ 源文档被本机实测推翻的清单

以下是**上游文档里写了、但在本机跑出来是错的**的说法。
改编时一律以「实测」为准；遇到源文档与本节冲突，**信本节**。

| # | 上游说法 | 本机实测 | 处置 |
|---|---|---|---|
| 1 | **API hash 常量**（如 `0xEC0E4E8E` 之类）直接可用 | 各家编译器的 ROR13 变体、hash 种子、字符大小写处理各不相同，照抄常量必然对不上 | 常量**不写死**，改为「从 `../reverse-engineering/references/dynamic-api-resolution.md` 的方法现场拟合」 |
| 2 | `cdb` 写内存用 `eb 0xADDR <bytes>` | `eb` 是**下软件断点**（INT3），不是写内存。写内存是 `e 0xADDR b8 0f 27 00 00`（字节空格分隔） | 命令已更正；写完必须 `d 0xADDR` 回读校验 |
| 3 | `rabin2` 可用来扒导入表 / 节区 | 探测层能命中 `(Resolve-ReverseToolSpec -Name 'rabin2').Command`（153600 字节），但 `rabin2 -I <PE>` **实跑直接挂起不返回、零输出** —— 看着像能用，实际不可用 | 全文改用 `r2 -qc`；`_map.json` 的 `rabin2` 别名已加 `note` 记录此坑 |
| 4 | YARA 里 `pe.entry_point` 是 RVA | 实际是**文件偏移**，不是 RVA | 规则里必须自己换算 |
| 5 | `bp kernel32!X` 能拦住 API | kernel32 公开 PDB 里只有 `*Stub` 别名，`bl` 显示绑定成功但**永远不命中** | 断点下在 `ntdll!NtXxx`（真正的实现所在） |
| 6 | 「断点列表里能看到该 API」就算下好了 | 自己敲的 `.echo` 也会出现在 `bl` 里，那是**命令回显**不是命中 | 唯一判据是日志里的 `Breakpoint 0 hit` |
| 7 | cdb 日志可直接 `Select-String` 过滤 | cdb 日志是 **UTF-16LE**，`Select-String` 报「非 UTF-8」 | `[IO.File]::ReadAllText($log, [Text.Encoding]::Unicode)` |
| 8 | 内联带引号的 cdb 命令串可直接传 | 经 `cmd` / `CreateProcess` **引号被转义坏**，报 `Win32 error 0n2` | 一律写 `-cf <命令文件>`；命令文件每行一条、扁平，**结尾必须有 `q`** |
| 9 | `cdb` 可从包目录直接调用 | MSIX ACL 会让 `WindowsApps\cdb.exe` 直跑报「拒绝访问」 | 只能走 app execution alias `%LOCALAPPDATA%\Microsoft\WindowsApps\cdbX64.exe`；**不要把它加进 PATH** |
| 10 | `cdbX86` 能调 64 位目标（或反之） | 架构严格对应，混用报 `Win32 error 0n50` | x86 目标找 `%SystemRoot%\SysWOW64\*`（PE machine `0x14C`） |
| 11 | `cdb` 退出码 0 = 调试成功 | 实测退出码不可信（见过 `-2147024866`） | 判成功只看日志里的 `Breakpoint 0 hit` |
| 12 | PyPI 版 `flare-capa` 可用 | 该 wheel **不含内置规则集**，实跑 `default embedded rules not found!` 后 exit 10 | 用工具根里自带规则的官方二进制；`capa` 已进 `_map.json` 的 deny 段 |
| 13 | 官方 `capa.exe` 是可信二进制 | PyInstaller+UPX 打包，**被 Defender 误报隔离** | 加排除项，**不要退回 PyPI 版** |
| 14 | radare2 的 `/x` 通配符是 `?` | r2 用 `.`（`/x 488b05..`） | 命令按 r2 语法写 |
| 15 | `search.in=from..to` 能限定搜索范围 | 本机 r2 的 `search.from/to` 语法无效 | 用 `s <addr>` 定位后再搜 |
| 16 | 反调试看 `PEB.NtGlobalFlag` 一个偏移 | **x64 是 +0xBC，x86 是 +0x68** | 按架构取偏移，写死一个值必错一半 |
| 17 | 满屏 `????` 说明内存没读到 | 通常是**读了结构体指针而不是裸字符串** | 先 `dt` / `dq` 逐级解引用 |
| 18 | IDA headless 用 `idat.exe` 跑 64 位 | `idat.exe` 是 **32 位**，64 位必须 `idat64.exe` | 脚本结尾必须 `idc.qexit(0)`，开头 `idaapi.auto_wait()` |
| 19 | `pip install` 装完 venv 就齐了 | `python -m venv` **只建骨架不装包**。本机 `(Resolve-ReverseToolSpec -Name 'pyre').Command\` 就是空壳：能报 3.12.0，但 `pefile`/`capstone`/`lief`/`angr`/`unicorn`/`qiling`/`z3`/`yara`/`dnfile` **全部 NO** | 逆向库实际全在 `(Resolve-ReverseToolSpec -Name 'pyre').Command`。用探测层别名 `pyre`；装完**逐个** `find_spec` 验证（见 `../../../环境建设.md` §4.3） |
| 20 | YARA 递归扫目录即可 | 会**命中规则文件自身** | 排除规则目录，或只传单文件/索引 |
| 21 | `pe.imports` 匹配 DLL 名不分大小写 | **大小写敏感** | 规则里写对大小写 |
| 22 | `Get-FileHash` 总能用 | 某些执行上下文不可用 | 备 `.NET` 的 `SHA256` 或 `certutil` |
| 23 | GUI 工具可以同步调用看输出 | GUI 前端**零 stdout、进程永不退出**，同步拉起会卡死整轮且模型察觉不到 | `_map.json` 的 deny 段挡住；一律走 CLI 孪生（`die.exe`→`diec`、`ida.exe`→`idat`、`Wireshark.exe`→`tshark`、`x64dbg.exe`→headless） |
| 24 | stdio MCP server 用 `ReadToEnd()` 探测 | **永不退出**，`ReadToEnd()` 永远不返回，表现为「超时、零输出、像没装」 | 必须 `StreamReader.ReadLine()` 逐行读 |
| 25 | IDA MCP 用 stdio 形态 | `idalib-mcp --help` 写明默认 **HTTP 8745**，`--stdio` 才走 stdio；技能包给的是 13337 HTTP 通道 | 配 13337 HTTP，形态配错表现为「握手一直 TIMEOUT」 |
| 26 | 读中文 `.md` 直接 `read` 就行 | Windows 默认 936 码页，不加编码会读出乱码并**误判成文件不存在** | `[IO.File]::ReadAllText($p, [Text.Encoding]::UTF8)` / PS 的 `-Encoding UTF8` |
| 27 | 读结构体失败就当数据无效 | 指令里嵌 `\\E` 之类路径时，docstring 未用 `r"""` 会触发 `SyntaxWarning: invalid escape sequence` | 文档字符串一律用 `r"""` |

**这张表会继续长。** 每次在改编或实战中实测推翻了源文档，就加一行 —— 它的价值就是「不重复踩同一个坑」。

---

## 5. 已落地脚本

| 脚本 | 位置 | 依赖 | 判据 |
|---|---|---|---|
| `algo_identify.py` | `../reverse-engineering/scripts/algo_identify.py` | **仅标准库** | 退出码 0 = 至少命中一个算法；1 = 未识别；2 = 用法错误/文件不存在 |
| `prng_detect.py` | `../reverse-engineering/scripts/prng_detect.py` | **仅标准库** | 退出码 0 = 识别出类型；1 = 未识别；2 = 用法错误/输入不足 |

两者都用 `r"""` + UTF-8 头，**任意 Python 3 解释器都能跑**（本机两个解释器均已实跑验证）。
但要 `import pefile` 之类的**必须**走 `pyre`：

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
& (Resolve-ReverseToolSpec -Name 'pyre').Command -c "import pefile, capstone, lief, angr, unicorn, qiling, z3, yara, dnfile; print('ok')"
```

---

## 6. 相关

- [`KB-INDEX.md`](KB-INDEX.md) —— 按症状检索全部已落盘文档
- `../../../环境建设.md` §4.3 —— venv 别当「装全了」，含逐个 import 验证法
- `../scripts/lib/Bootstrap.ps1` —— 探测层，四级递进取工具路径
- `D:\Tools\_map.json` —— 工具根别名表，`pyre` / `deny` 段与 `note` 字段记录了同类坑
- `D:\Tools\_tools\backup\` —— `_map.json` 的历次改动备份，改前必备份