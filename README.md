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

| 情况 | 先读 |
|---|---|
| **新开的电脑，环境是空的** | **[`环境初始化.md`](环境初始化.md)** —— 只给判断依据，步骤由智能体按本机实际情况自己定 |
| 环境已就绪，要开始干活 | [`START-HERE.md`](START-HERE.md) |

---

## 目录结构

```
C:\relab2\
├─ 环境初始化.md              ★ 新机施工单（AI 第一份读）
├─ START-HERE.md              ★ 正式干活的主入口
├─ README.md                     本文件
│
├─ kernel\                  ① 行为层 —— agent 怎么做事
│  ├─ 04-console\cards\        44 张卡片（3 个可读池 hub/base/guest + 各停车位）
│  │  └─ guest\全能专精指引.md  ★ 安全逆向总控路由（常驻卡片）
│  ├─ 02-hubcore\               中枢本体
│  ├─ 03-bundle\                卡片打包/装卸/校验
│  └─ 07-kernel-sweep\          提示词实测与调优工具链
│
├─ skillpack\              ② 能力层 —— agent 会做什么
│  ├─ skills\                   ★ 50 个技能模块（46 顶层 + 4 community wrapper），主入口 SKILL.md
│  │  ├─ TOOLS.md               ★ 工具清单与装法（机器无关）
│  │  ├─ references\tool-registry.md   MCP 通道登记模板
│  │  └─ scripts\lib\Bootstrap.ps1    探测层（纯测量）
│  ├─ CTF-Sandbox-Orchestrator\  CTF 场景编排
│  ├─ community-raw\             第三方技能源（vendored，有 README 声明）
│  └─ scripts\                   仓库级路由/校验脚本
│
└─ _archive\               退出使用的文件（死工具链、历史备份），可回退
```

---

## 两层各解决什么

| 层 | 回答的问题 | 入口 |
|---|---|---|
| **① 行为卡片** | agent **怎么做事** —— 身份、纪律、输出契约、卡死判据 | `kernel/04-console/cards/guest/全能专精指引.md` |
| **② 能力路由** | agent **会做什么** —— 逆向/协议/APK/自动化的方法论与工具用法 | `skillpack/skills/SKILL.md` |

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

| 项 | 数量 |
|---|---|
| 技能模块 | 50 |
| 行为卡片 | 42 |
| 本仓库 | ~2500 文件 / ~25 MB |
| 工具根 `D:\Tools` | ~1.3 GB（商业工具，便携版，**不随本仓库分发**） |

---

## 边界（如实列出）

- **纯 GUI 工具需要人工** —— PE-bear / Scylla / 010 Editor / JEB GUI 无 CLI 孪生，agent 不得经 bash 启动
- **不跨设备** —— 不 SSH、不连远程 MCP 端点、不碰共享文件夹
- **不管理虚拟机** —— 建工作机 / 打快照 / 恢复快照是人的活
- **不维护工具状态文件** —— 探测是运行时的，没有「索引过期」问题，也不需要刷新步骤
- **不含工具二进制** —— 本仓库 25 MB，工具在 `D:\Tools`，换机时拉取或现场装
- **卡片历史目录** `_archive/` `_park/` `_pending/` 是停用卡片，保留但不使用
- 报告里的 `x/x` 必须带分母定义，未通过项逐条列出，不许用「已完成」覆盖