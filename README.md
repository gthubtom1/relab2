# RELAB2 · 逆向工程工作台

**给 AI 智能体用的一套东西：怎么做事（kernel）+ 会做什么（skillpack）+ 工具怎么找（TOOLS.md）。**

本机当前部署在 **`C:\relab2`**（工具根 **`D:\Tools`**）—— 但这**不是约定**：入口脚本全部按 `$PSScriptRoot` 上溯定位，换机可以 clone 到任何位置，别把绝对路径写进命令。
命令里直接写，不用占位符。探测层内置这两个默认值；万一某台机器还没按约定建好，
它会自推导并给出警告（`REVERSE_SKILL_ROOT` 指向 skills 根 / 包根 / 仓库根三种写法都认）。
新机第一步见 [`环境初始化.md`](环境初始化.md) 开头。

---

## ★ 工具从哪来

商业付费 / 官方下架 / 中文小众的便携工具（IDA Pro、JEB、脱壳机全集等）放在**私有仓库**：

**`https://github.com/gthubtom1/relab-tools.git`**（9 卷 7z，共 770 MB，附每卷 SHA256）

新机上 `git clone` + 7z 解压即可，不需要装。取用思路见 [`环境初始化.md`](环境初始化.md)。
GitHub / winget 上一键能装的免费工具不在那里 —— 那些由 `TOOLS.md` 的装法现场安装。

---

## ★ 新电脑从哪开始

```powershell
# ★ 一条命令：先看它要干什么（一个字都不改），再真跑，再看就绪度
powershell -NoProfile -ExecutionPolicy Bypass -File .\relab2.ps1 setup -DryRun
powershell -NoProfile -ExecutionPolicy Bypass -File .\relab2.ps1 setup
powershell -NoProfile -ExecutionPolicy Bypass -File .\relab2.ps1 doctor   # 退出码 0 = 就绪
```

`doctor` 逐项报：仓根 / 环境变量 / 自检 / **MCP 通道**（注册几条、哪条是懒启、后端在不在）/ 技能挂载 /
技能卡数 / 门禁清单 / 破甲卡 / 要求门 R1–R13 / **行为门实跑**（上次什么时候跑的、过没过；从未跑或超 30 天报 WARN）/
**GitHub CLI 登录**。**它就是「换机 = 一条命令」的那条命令。**
它只证明「本机配置就绪」，不证明「能力就绪」—— 能力只由真实验收证明。

| 情况 | 先读 |
|---|---|
| **新开的电脑，环境是空的** | 先跑上面的 `relab2.ps1 setup` → `doctor`；再读 **[`环境初始化.md`](环境初始化.md)** §11（完整适配清单） |
| 环境已就绪，要开始干活 | [`START-HERE.md`](START-HERE.md) |

---

## 目录结构

```
C:\relab2\
├─ 环境初始化.md              ★ 新机施工单（AI 第一份读）
├─ START-HERE.md              ★ 正式干活的主入口
├─ relab2.ps1                 ★ 唯一门面：doctor / setup / update（换机一条命令）
├─ README.md                     本文件
│
├─ kernel\                  ① 行为层 —— agent 怎么做事
│  ├─ 04-console\cards\        常驻卡 10 张（base 5 + guest 1 + hub 4）+ 停车位若干
│  │  └─ guest\全能专精指引.md  ★ 安全逆向总控路由（常驻卡片）
│  ├─ 02-hubcore\               中枢本体
│  ├─ 03-bundle\                卡片打包/装卸/校验
│  └─ 07-kernel-sweep\          提示词实测与调优工具链
│
├─ skillpack\              ② 能力层 —— agent 会做什么
│  ├─ skills\                   ★ 57 个技能模块，主入口 SKILL.md
│  │  ├─ TOOLS.md               ★ 工具清单与装法（机器无关）+ 按能力找工具
│  │  ├─ references\tool-registry.md   MCP 通道登记模板（含 stdio·懒启代理）
│  │  ├─ scripts\capability-index.py     能力发现（不按名字，按「能干什么」扫本机）
│  │  ├─ scripts\relab2-tools-mcp.py     工具箱 MCP（把本机工具链递给模型）
│  │  ├─ scripts\mcp-lazy-http.py        HTTP 型 MCP 通道的 stdio 懒启动代理
│  │  └─ scripts\lib\Bootstrap.ps1      探测层（纯测量）
│  ├─ CTF-Sandbox-Orchestrator\  CTF 场景编排
│  ├─ community-raw\             第三方技能源（vendored，有 README 声明）
│  └─ scripts\                   仓库级路由/校验脚本
│
├─ extensions\              ③ 物理兜底层（可选）—— 仅 pi 宿主：cmd-guard 补 timeout / 拦 GUI 二进制
│
└─ _archive\               退出使用的文件（死工具链、历史备份），可回退
```

---

## 分层（★ 两条轴，别混）

| 轴 | 是什么 | 权威 |
|---|---|---|
| **必读层**（agent 要读几份） | ① 行为卡片（怎么做事）+ ② 能力路由（会做什么）**必读**；③ 物理兜底（`extensions/pi/cmd-guard`）**仅 pi 宿主可选** | [`START-HERE.md`](START-HERE.md) §0 |
| **功能线路**（项目由哪些层组成） | **15 层**：入口 / 技能 / 路由 / 工具 / MCP / 门禁 / 工作流 / 换机 / 知识库 / kernel 行为 / 经验卡 / 社区 / 扩展 / 契约 / 依赖 | [`docs/PROJECT-MAP.md`](docs/PROJECT-MAP.md) |

> 本节只做**指路**：每一层里面是什么、用什么命令核验，一律以右边那份权威文档为准。

---

## 核心设计：工具靠探测，不靠声明

**工具定位是运行时行为，不是数据。** 没有需要维护、会过期的工具清单文件。

```powershell
. .\skillpack\skills\scripts\lib\Bootstrap.ps1
$r = Resolve-ReverseToolSpec -Name 'idat'
$r.Available   # 有没有
$r.Command     # 在哪
$r.Via         # 从哪找到的：env / PATH / map / scan
```

四级递进，命中即停：

| 级 | 手段 | Via | 为什么需要 |
|---|---|---|---|
| 1 | 环境变量 | `env` | 主人显式指定的，最高优先 |
| 2 | `Get-Command` 查 PATH | `PATH` | 系统安装优先于便携副本 |
| 3 | `D:\Tools\_map.json` 别名 | `map` | 目录名 ≠ 工具名，只能声明 |
| 4 | 工具根递归 | `scan` | 兜底，可信度最低 |

**为什么第 3、4 级不能省**：商业工具（IDA / JEB）在 `D:\Tools\disasm\IDA Pro 9.3\`
里，目录名不等于工具名，也不在 PATH 上。只跑 `Get-Command` 一个都找不到。

**第 4 级有陷阱**，所以有 `deny` 规则：IDA 自带的裸 Python 没有 pip 包，误命中它，
脚本就跑在没有依赖的解释器上 —— 不报错，只是「装不上包」，最难查。

> **本表的正本是 [`skillpack/TOOL-CHAIN.md`](skillpack/TOOL-CHAIN.md) §2「工具定位：四级递进（固定规则，不用改）」。**
> 这里与 [`环境初始化.md`](环境初始化.md) §4.1 都是它的摘要；**三处冲突时以 `TOOL-CHAIN.md` §2 为准**（它多写了 `deny` 语义与「第 4 级务必实跑确认身份」）。

详见 `skillpack/skills/TOOLS.md` §0。

---

## 工具从哪来、到哪去、怎么被找到

```
装法说明书（机器无关）    skillpack/skills/TOOLS.md
        ↓ agent 照着装
工具根 D:\Tools\<分类>\<工具名>\
        ↓ 探测层四级递进
技能脚本 Resolve-ReverseToolSpec → 拿到真实路径
        ↓
技能执行
```

**新增工具时改两处**（都改，缺一不可）：

| 改哪 | 写什么 | 不改会怎样 |
|---|---|---|
| `skillpack/skills/TOOLS.md` | 干什么 / 哪个 skill 要 / 装法 / 许可标记 | agent 不知道有这个工具，也不会去装 |
| `D:\Tools\_map.json` | 位置别名（`prefer`）/ 排除规则（`deny`） | 装上了但探测层认不出来 |

`_map.json` **跟着工具根走**（会打进工具根的压缩包一起上传），所以换机后**通常不需要重建**。

但**要核对一遍**，因为它是上一台机器的目录结构写的：

1. 有没有 `..` 逃出工具根的条目（工具根一换盘就死）
2. 有没有指向不存在目录的 `prefer`
3. `deny` 的模式还匹配得上吗

核对方式：跑 `selfcheck.ps1`（退出码 0 且无 MISSING）＋ 对新工具根下每个目录跑一次 `Resolve-ReverseToolSpec`。
**只有「换了工具根的子目录结构」或「条目指歪」时才需要手改** —— 改法见 `skillpack/TOOL-CHAIN.md` §4。
口径与 `环境初始化.md` §11 保持一致；两处冲突时以 `环境初始化.md` 为准。

---

## 怎么用

```powershell
# 1. 读入口
notepad .\START-HERE.md

# 2. 跑路由，选 PRIMARY 技能
powershell -ExecutionPolicy Bypass -File .\skillpack\skills\scripts\master-route.ps1 -Hint "<任务描述>"

# 3. 打开 PRIMARY 技能照做
notepad .\skillpack\skills\<技能名>\SKILL.md
```

换 agent 行为底模：卡片在 `kernel/04-console/cards/`，用
`kernel/03-bundle/install.py` 载入、`uninstall.py` 卸载。

---

## 规模

<!-- scale: generated by skills/tests/check-readme-scale.py; do not hand-edit. skills_top=57 skills_nested=6 cards_active=10 tracked_files=3131 tracked_mb=43.6 -->

| 项 | 口径（数字统一见上方 scale 行，本表不重复） |
|---|---|
| 技能模块 | 顶层技能 + 嵌套技能（skills_top + skills_nested） |
| 行为卡片 | base + guest + hub 三个池子（cards_active） |
| 本仓库 | 跟踪文件数 + 体积（tracked_files / tracked_mb） |
| 工具根 `D:\Tools` | 商业工具，便携版，**不随本仓库分发**（体积固然随机，不归入 scale 行） |

> 上方那行是**机器生成**的：`python skillpack/skills/tests/check-readme-scale.py` 每次现算，
> 与 README 里手写的数字不一致就报错。
> 2026-10-15 审计实测：本节以前手写的
> `50 / 42 / ~2500 文件 / ~25 MB` **四个数全错**（实际 57 / 10 / 3083 / 43.0 MB）
> —— 手写规模数字必然腐烂，所以改成可核对的形态。

---

## 边界（如实）

**两条都不在本文件复述 —— 直接读权威：**

- **行为 / 范围边界**（不跨设备 / 不管理虚拟机 / 装工具前先报告再直接装 / 报告 `x/x` 必须带分母）
  → [`START-HERE.md`](START-HERE.md) §4
- **能力 / 环境边界**（这个项目**做不到**哪些事、为什么做不到）
  → [`docs/KNOWN-BOUNDARIES.md`](docs/KNOWN-BOUNDARIES.md)；一条命令列全：`.\relab2.ps1 known`（`-Json` 出结构化；**条数以实际输出为准**）

本仓库特有的两条：**不含工具二进制**（工具在 `D:\Tools`，本仓库体积见上方 scale 行）；
**卡片历史目录** `_archive/` `_park/` `_pending/` 是停用卡片，保留但不使用。