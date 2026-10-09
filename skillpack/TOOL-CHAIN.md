# 工具链协议

> **这份文档是「怎么接一个新工具」的标准动作，不是工具清单。**
>
> 清单会永远过时 —— 今天的机器、今天装的软件，明天就不一样。
> 所以这里只写**规则**：遇到没见过的工具，怎么判断、怎么装、怎么登记、登记到哪。
> 具体的工具列表散落在下面四个文件里，**它们都可以由使用者自己增补**。

---

## 0. 一句话原则

**遇到不认识的工具时：自己查 → 自己装 → 自己登记 → 继续干活。不要因为「文档里没有」就停下来问人。**

只有三种情况才停下来问：
- 需要商业许可或账号（不知道去哪买）
- 需要管理员权限且你没有
- 装了两条路都不通

---

## 1. 四份文件的分工（记这个就够）

| 文件 | 回答什么 | 谁维护 |
|---|---|---|
| `TOOLS.md` | 这个工具**干什么用、怎么装** | 装的时候顺手加一行 |
| `bootstrap-manifest.json` | 有哪些工具可以**自动安装** | 加了新工具、且想让它能被脚本装时 |
| `D:\Tools\_map.json` | 目录名 → 工具名的**映射**，以及要排除的陷阱 | 工具换了目录、或新增便携工具时 |
| `D:\Tools\MANIFEST.json` | 工具根里**实际有什么** | 加工具后跑生成脚本 |

**关键：没有一份是「必须完整」的。** 缺条目 = 探测层少一条线索，不影响其它工具工作。

---

## 2. 工具定位：四级递进（固定规则，不用改）

```powershell
# ★ 载入探测层必须用这一行（写成 `. <路径>` 会被执行策略直接拒 —— 全新 Windows 默认 Restricted）
powershell -NoProfile -ExecutionPolicy Bypass -Command ". '<包根>\skillpack\skills\scripts\lib\Bootstrap.ps1'; Resolve-ReverseToolSpec -Name '<工具id>'"

# 返回值：
$r.Available   # 有没有
$r.Command     # 在哪（用完整路径调用，不要依赖当前目录）
$r.Via         # 从哪找到的：env / PATH / map / scan
```

> **若你在同一条命令里已经 dot-source 过了，就直接调 `Resolve-ReverseToolSpec` 即可，
> 不用再套一层 `-Command`。** 首次载入必须带 `-ExecutionPolicy Bypass`。

| 级 | 手段 | Via | 可信度 |
|---|---|---|---|
| 1 | 环境变量（同名大写变量指向全路径） | `env` | 最高 |
| 2 | `Get-Command` 查 PATH | `PATH` | 高 |
| 3 | `D:\Tools\_map.json` 的别名 | `map` | 高 |
| 4 | 工具根递归找同名文件 | `scan` | **最低，务必实跑一次确认身份** |

**为什么需要第 3、4 级**：便携工具躺在 `D:\Tools\<分类>\<工具名>\` 里，目录名不等于工具名
（`IDA Pro 9.3\` 里才是 `idat`），而且不在 PATH 上。只查 PATH 一个都找不到。

**没有 `_map.json` 别名也能工作**（退到第 4 级），只是可信度低。所以加工具时别名是「推荐」不是「必须」。

---

## 3. ★ 发现缺工具时的标准动作（**最常用的一段**）

这是给**任何**接手的智能体看的。不需要认识这个工具，照做即可：

```powershell
# 1) 确认真的没有（换个名字再试，有时别名不同）
#    ★ 用「不带扩展名」的工具 id（idat / die / jadx），不要写成 'idat.exe' ——
#    带扩展名时探测层会当精确键去找，返回 Available=False，属**假缺失**。
#    实测：'idat' → True/map，'idat.exe' → False。
#    换名字的正确做法是试同义词/别名（die↔diec、ida↔idat↔ida64），不是加 .exe。
#    想知道它认哪些名字、登记在哪：直接读 D:\Tools\_map.json 的 aliases 段（-Encoding UTF8）。
Resolve-ReverseToolSpec -Name '<工具id>'

# 1b) ★ 别被「PATH 命中」骗了
#    探测层第 2 级是 Get-Command，它会返回 PATH 里任何东西 ——
#    包括别的项目留下的、主人已声明废弃的目录。看到 Via=PATH 却指向一个
#    陌生或废弃的路径时，当它不存在，继续走第 3、4 级（_map.json 别名 → 工具根递归）。
Resolve-ReverseToolSpec -Name '<工具id>' | Select-Object Available,Via,Command

# 2) 找它的官方来源
#    GitHub releases > 官网 > winget > choco > pip
#    优先级：官方 release（版本明确） > 包管理器（省事但版本可能旧）

# 3) 装
#    - 包管理器：winget install --source winget <id>
#      注意 --source winget，否则首次会弹 msstore 协议提示卡住
#    - pip 类：装进独立 venv，别污染系统 Python
#    - 绿色版：解压到 D:\Tools\<分类>\<工具名>\
#    - 商业许可：停下来问主人

# 4) 装完必须实跑一次（不是看文件在不在，是看能不能真跑）
& <完整路径> --version

# 5) 找到它了 —— 那就用，不需要登记也能干活
#    只有「放在 D:\Tools 里、且目录名和工具名不一致」时才需要登记（见下）

# 6) 如果这个工具未来还会用到 → 按第 4 节登记，让下次更快
```

### 第 1 步的补充：两个常见的假象

- **Windows 商店占位程序**：某些机器上 `python`/`node` 能被查到，点开是弹商店。
  判断依据是**能不能实跑**，不是「文件在不在」。
- **工具自带的环境**：`D:\Tools` 里某些工具捆绑了自己的 Python / 7z / JDK，
  那是给它内部用的，版本旧、缺依赖。**不要当系统工具用**（这类陷阱已写进 `_map.json` 的 `deny`）。

---

## 4. ★ 怎么登记（加工具 / 换版本时）

### 4.1 什么时候需要登记

| 情况 | 要改哪 |
|---|---|
| 工具装在 PATH 里（如 winget 装的 Python） | 不用登记 |
| 工具装在 `D:\Tools`，**目录名 = 工具名** | 不用登记（第 4 级能扫到） |
| 工具装在 `D:\Tools`，**目录名 ≠ 工具名** | 加 `_map.json` 别名 |
| 同名有多个副本，要指定用哪个 | 加 `_map.json` 别名（`prefer` 按优先级排） |
| 这个工具容易误命中（比如捆绑的旧 Python） | 加 `_map.json` 的 `deny` |
| 某个技能需要它，但没人知道它存在 | 加 `TOOLS.md` 一行 |
| 想让脚本能自动装它 | 加 `bootstrap-manifest.json` 一条 |

**判断不了就都加上** —— 多一条别名的代价只是多一行 JSON，不会坏事。

### 4.2 `D:\Tools\_map.json` 的模板

```jsonc
{
  "aliases": {
    "工具id": {
      "exec": "实际可执行文件名.exe",       // 可省略，省略则按 工具id.exe 找
      "prefer": [                              // 相对工具根的路径，按优先级
        "分类\\目录名\\入口.exe",
        "分类\\另一个目录\\入口.exe"
      ],
      "note": "为什么这么映射。有坑一定写下来。"
    }
  },

  "deny": [
    {
      "toolIds": ["工具id"],
      "pathPatterns": ["*要排除的目录*"],       // ★ 前后都要带 *
      "reason": "为什么必须排除"
    }
  ]
}
```

> **`pathPatterns` 必须前后都带 `*`。** PowerShell 的 `-like` 要求**整串匹配** ——
> 写成 `*\python3*\` 匹配不到 `...\python311\python.exe`（后面还有内容），正确写法 `*\python3*`。

### 4.3 `TOOLS.md` 的模板

在对应的分节里加一行：

```markdown
| **工具名** | 干什么用 | 怎么装 | 许可 |
```

四个字段就够：**干什么用**（最重要 —— 这决定了别人会不会想起它）、**怎么装**、许可。

许可三档：🟢 免费自动 / 🟡 需要已有环境或管理员 / 🔴 商业许可不自动下载。

### 4.4 加工具后刷新机器清单

```powershell
python <工具根>\_tools\gen-manifest.py    # 重生成 MANIFEST.json
python <工具根>\_tools\gen-sha256.py     # 重算 SHA256SUMS.txt
```

改了 `SHA256SUMS.txt` 之后，工具仓库的压缩包也要重打并推送 —— 否则新机拉下来的会对不上。

---

## 5. MCP：能用就用，不能也不影响干活

优先级：**MCP → 无头/CLI → GUI**。

- **MCP 装完必须让宿主的智能体知道** —— 多数情况要写进它的配置文件。
  **不同智能体的配置位置和格式完全不同，问主人或查它自己的文档**，别照抄别人的。
- **注册 ≠ 在监听**：HTTP 型 MCP 是按需启动的，要探一下端口（`Test-ReverseTcpPort`，1 秒超时）。
- **冷启动不是故障**：首次拉起十几秒属正常，不要因此退回裸开 exe。
- **GUI 是最后手段**：弹窗等输入、零输出、进程永不退 —— 同步拉起会把你自己卡死。
  用之前先找它的命令行版本（`die.exe`→`diec`、`Wireshark.exe`→`tshark`、`ida.exe`→`idat`、
  `dnSpy.exe`→`dnSpy.Console`）。GUI 能不能用取决于你的宿主有没有界面控制能力，没有就别试。

---

## 6. 出问题了怎么排查

| 症状 | 先查 |
|---|---|
| 探测不到明明装了的工具 | `Via` 是什么？`scan` 就是目录名不匹配 → 加别名 |
| 装完还是说没有 | PATH 变了要刷新；pip 装进 venv 的话 venv 的 Scripts 不在 PATH |
| 工具跑起来报奇怪的错 | 可能命中了捆绑副本 → 看 `_map.json` 的 `deny` |
| 文件明明在，`Test-Path` 说没有 | **编码问题** —— 先加 `-Encoding UTF8` 读，再怀疑文件真没了 |
| 多个副本，选错了 | `prefer` 里把要的排前面 |

---

## 7. 核心纪律（任何时候都成立）

1. **不许猜路径。** 没查到就是没装，不是「可能在某个地方」。
2. **不许把探测到的路径写回文档。** 路径只在当次会话里有效。
3. **装完必须实跑一次**，有输出才算好。
4. **命令挂死（计时器还在走但你没输出）就立刻中断换路子** —— 这类中断不会自愈。
5. **如实报告**：装不上就说装不上，附上试过的命令和报错原文。

---

## 8. 相关文件

- 装法清单：`skillpack\skills\TOOLS.md`
- MCP 通道登记模板：`skillpack\skills\references\tool-registry.md`
- 探测层：`skillpack\skills\scripts\lib\Bootstrap.ps1`（只测量，不判定）
- 工具根结构：`D:\Tools\README.md`
