# 升级阶梯手册（Escalation Ladder Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `escalation-ladder-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。**改编要点：Rung 4 / Rung 5 的「本地宿主」在源文档里默认由 `iv8` 提供，本机没有 `iv8`；本文按本机实际能力重写了这两级，并明确给出「本机的升级终点是什么」。**
>
> **什么时候用**：手里有一个部分证明，正想直接跳到更重的运行时、更宽的补丁面，或者某个路由专用的传输例外时 —— 也就是**手痒想跳级**的时候。
>

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

---

## 适用信号（Recognition signals）

- 「Python 算出来和浏览器不一样，要不我直接上个浏览器跑吧」← 最典型
- 「helper 能 load，但输出明显偏短/偏简单」
- 「只知道某个字段有问题，但不知道它在哪被改的」
- 「想直接改 UA / 改头 / 改 TLS 一把梭」
- 「本地跑不起来，怀疑需要真浏览器」

## 前置（Entry conditions）

1. **手里有一条已知能跑通的证据**（哪怕只是一条 wire 抓包），否则你没有基准。
2. **已经确认本机的运行时能力边界**，否则你会在「升级」时误以为有 `iv8`。直接查：

```powershell
# Node 在位 —— 本机 Rung 4 的首选宿主（实测 v24.20.0）
& (Resolve-ReverseToolSpec -Name 'node').Command -v

# iv8 检查：本机预期为「未安装」，因为它是社区运行时，PyPI 上不存在该发行版
& (Resolve-ReverseToolSpec -Name 'pyre').Command -c "import importlib.util as u; print('iv8:', bool(u.find_spec('iv8')))"
```

---

## 步骤（Working method）

### 核心规则（Core rule）

**禁止跳级（Do not jump multiple rungs）。**

在往上挪一级之前，必须先写全这四行：

1. 当前级最新、仍然成立的证明是什么
2. 当前级**确切的**失败或盲区是什么
3. 为什么下一级是能回答该失败的**最小**层
4. 为什么挪上去之后交付门仍然是**无浏览器**的

**写不出这四行，就不要升级。**

### 通用阶梯（Universal ladder）

#### Rung 0：重述基线（Re-state the baseline）

**证明**：

- 启动门仍然有效（见 `./startup-triage-playbook.md`）
- 真正的请求路径仍然是真正的请求路径
- 会变的部分已被**分类**过，不是猜的

**停留**：家族可能变了；路由可能是诱饵；失败的那个请求从没在真正的业务路径上被证明过。

**升级条件**：基线是真的、当前的、而且**确实不够**。

#### Rung 1：固定输入与 wire diff（Fixed-input and wire diff）

**证明**：

- 固定输入下 helper 的平价（parity）
- 精确的 query / body 序列化
- 精确的字段槽位（slot）位置
- cookie 溯源
- 在**一个冻结载荷**上的解码顺序

**停留**：helper 名字可能骗人；输出不同但宿主依赖还没被证明；blob 的**值**可能对，但**槽位或封装**不对。

**升级条件**：固定输入或 wire diff 已证明剩下的差距**不是**简单的平价、槽位或解码问题。

> 本机做法：用 `(Resolve-ReverseToolSpec -Name 'pyre').Command` 跑固定向量；wire 侧用 `mitmdump` 落盘后逐字节 diff。

#### Rung 2：窄边界观察（Narrow boundary observation）

**证明**：

- canonical mutation point（规范化变更点）
- 最窄的稳定入口/出口边界
- 运行时**是否已经**直接吐出决定性产物

**典型动作**：initiator 栈、wrapper 追踪、窄的请求边界 hook、出站头或 body 捕获。

本机手段：`frida` 的 `Interceptor.attach`、或 `playwright` 的 CDP `Debugger.setBreakpointByUrl`。

**停留**：业务代码仍是诱饵；变更点未知；如果存在**一个**稳定的收获边界，本地运行时可能根本不需要。

**升级条件**：边界已知，且缺失的逻辑仍依赖本地执行。

#### Rung 3：纯本地复现（Pure local reproduction）

**证明**：Python 改写平价，**或**一个极小的本地 JS/WASM helper 带固定输入检查点。

**停留**：剩下的逻辑是标准 crypto、紧凑 JSON、报文封装（framing）、解码，或一个小 helper。

**升级条件**：helper 仍依赖宿主可见语义 —— `document.cookie`、解析器顺序、定时器、描述符、或「看起来像原生」的面。

#### Rung 4：窄本地宿主引导（Narrow local host bootstrap）

> ⚠️ **本机在这一级的实际形态与源文档不同。**
>
> 源文档 Rung 4 依赖本地嵌入式运行时（`iv8`）来恢复一个决定性产物。**本机没有 `iv8`。** 本机在这一级的手段是：

| 手段 | 本机可用 | 适用 |
|---|---|---|
| `node` + `node:vm` 手工构造最小宿主桩 | ✅ | 只需要 `document.cookie` 赋值、`navigator`/`screen`/`location` 这类可桩化语义 |
| `../../profiles/env-patch/` 的环境补丁架构 | ✅ | 已知入口 + Node/VM 宿主面 |
| `playwright` 跑离线页（`page.set_content()` / 本地 HTML） | ✅ | 需要真实 DOM 生命周期、定时器顺序、XHR wrapper 语义。**这是本机的兜底，属于重活** |
| `iv8` 本地嵌入式运行时 | ❌ **本机没有** | —— |

**证明**：某个本地宿主/引导执行器能恢复**一个**决定性产物，且 Python 仍拥有真实 HTTP 重放。

**可接受的产物**：签名 URL、封装后的 body、token、cookie 串、出站 `Cookie` 头、解码后的载荷。

**停留**：一个本地的类宿主阶段就够恢复产物了。

**升级条件**：运行时能 load，但产物形态**结构性错误**，因为缺了一个具体的宿主面。

#### Rung 5：窄宿主面补丁（Narrow host-surface patching）

**证明**：缺口是**一个具体的宿主面**，不是含糊的「浏览器味」。

典型面：`canvas`、WebGL、布局度量、`getComputedStyle`、`Function.prototype.toString`、描述符（descriptor）、枚举顺序、解析器顺序、定时器调度。

**停留**：每补一个面产物就更接近一次。

**本机的边界 —— 这一级的终点是什么：**

即使把上面这些面全部补齐，本机也**不会**出现一台「无浏览器、无渲染、可完整替代真实浏览器」的离线运行时。原因很直接：

- **`iv8` 不存在** —— 本机没有那个「离线嵌入浏览器」的运行时品类。
- **`playwright` 需要真实 Chromium** —— 它能给出真实的 DOM 与定时器语义，但它**就是一个浏览器**。用在取证阶段没问题；一旦让它进入交付路径，就等于交付了一个浏览器自动化采集器，违反交付门。

所以本机的升级阶梯终点是：

```text
Rung 4（node 桩 / env-patch）—— 能恢复产物就停
Rung 5（逐项补宿主面，用 playwright 验证）—— 补到「产物正确」就停
若补完仍差：停下来，报阻塞，不要继续爬
```

**停止爬升的条件**（与源文档一致）：

- 流程仍需要活的渲染、手势、或每次请求都依赖完整浏览器状态
- 唯一剩下的路是浏览器驱动的 replay

> **那不是自动化许可。那是阻塞报告。**

> ⚠️ 本机特别提醒：`playwright` 在 Rung 5 里是**验证工具**，不是交付工具。用它验证「补了这个面产物就对了」是可以的；用它跑整个采集流程是不可以的。

### 升级线索（Promotion cues）

| 当前症状 | 最小诚实的下一级 |
|---|---|
| 标准 helper 在冻结输入上输出不同 | Rung 1 |
| query / body 值看着对，但重放仍失败 | Rung 1 |
| 还不知道 wire 载荷在哪被改的 | Rung 2 |
| 变更点已知且看起来自包含 | Rung 3 |
| 代码读宿主对象，或依赖定时器 / 解析器顺序 | Rung 4 |
| 本地产物明显偏短、偏简单、或结构性错误 | Rung 5 |
| 只有真页面才能端到端维持流程 | **停，报阻塞** |
| **补完 Rung 5 全部宿主面，本机也没有 `iv8` 可退** | **停，报阻塞**（本机终点） |

### 坏跳（Bad jumps）

别做这些：

- Python 不匹配 → 不做固定输入平价，直接跳嵌入式运行时
- 本地 helper 能 load → 不做一次活重放，直接跳分页规模化
- 一次坏请求 → 不做准入矩阵，直接上路由专用传输例外
- 不知道 cookie 写入方 → 硬编码 cookie，然后去怪 signer
- 本地运行时还是空 → 随机扩大补丁面，而不是先确定缺哪个面
- 「`playwright` 能跑通」 → 直接把它当交付路径（**本机特别容易犯**）

### 阶梯日志（Ladder log）

下一次动作有争议时，用这块：

```markdown
升级阶梯
- 当前级：
- 上一级证明出的产物：
- 当前级的确切失败：
- 为什么下一级是最小诚实动作：
- 无浏览器交付仍如何保持：
```

---

## 判据（Completion criteria）

### 升级的判据

只有写全了下面四条，才允许往上挪一级（否则停在原地）：

1. 上一级最新且仍然成立的证明
2. 上一级确切的失败/盲区
3. 下一级是最小层的理由
4. 挪上去之后仍然无浏览器交付的理由

### 交付完成的判据

一份交付可以说「逆向做完了」的条件（**本机口径**）：

1. **停在 Rung 3 或 Rung 4**，并且在阶梯日志里写清了停在哪一级、为什么上一级不够
2. Python 拥有全部真实 HTTP 重放、编解码、会话顺序与验收检查
3. 最终重放路径**不含** `playwright` / `frida` / CDP / 浏览器 profile / 手动点击
4. 若使用了本地 JS helper，它是**窄的、宿主无关的**，且有固定输入检查点
5. **本机约束已显式记录**：是否使用了 `iv8`（本机无）、是否依赖 managed host（本机无）、静态 AST 的 npm 依赖是否已装（本机未装）
6. 如果结论是「补完所有层也做不到」：报阻塞，并写清「本机没有 `iv8`，升级到 Rung 5 之后已无更高可用层」—— **这是合法终态，不是失败**

判据的反例（**以下情况算没做完**）：

- 「用 `playwright` 能跑通」就宣布完成 —— 那是取证，不是交付
- 跳到 Rung 4/5 却没写过阶梯日志
- 在 Rung 5 反复补面而不确定缺哪个具体面
- 把「本机有 `iv8`」写成结论（本机无）

## 常见坑（Common traps）

- **因为重的那层「看起来更强」就升级**。升级的唯一理由是轻的那层**被证据推翻了**。
- **把 `playwright` 当成「比浏览器轻的替代品」**。它是浏览器，只是被自动化驱动的浏览器。
- **以为本机有 `iv8` 而一路规划到 Rung 5 之上**。本机到 Rung 5 就没有更高的可用层了。
- **Rung 4 一上来就上 `playwright`**，跳过 `node` 桩这一级便宜的证明。
- **在 Rung 5 盲目补面**。每一项补丁都要能说出「补了它，产物变化了什么」。
- **把「helper 能 load」当成「helper 正确」**。固定向量过一遍。
- **一次改五个东西**。单变量。

## 相关（Related）

- `./startup-triage-playbook.md` —— Rung 0 的启动门与家族分诊
- `./tool-playbook.md` —— 每一级对应的本机实际工具；`iv8` / managed host 缺口在这里
- `./escalation-ladder-playbook.md` 的表格式速查版已在「升级线索」节内
- `./troubleshooting-playbook.md` —— 已经做完了但仍失败时的症状路由
- `../crypto/embedded-browser-runtime-playbook.md` —— Rung 4/5 的方法论（源文档假定 `iv8`，本机按 `node`/`playwright` 执行）
- `../crypto/iv8-runtime-cheatsheet.md` —— **`iv8` 本机无，API 形态未在本机验证**
- `../crypto/environment-patch-playbook.md` —— Rung 5 宿主面补丁清单
- `../../profiles/env-patch/index.md` —— 本机 Rung 4 的现成路线（Node/VM 宿主）
- `../deliver/pure-python-rebuild-playbook.md` —— Rung 3 的具体做法
- `../deliver/delivery-gate-playbook.md` —— 交付门的正式判据

---

## 源文档勘误与本机化改动

1. **Rung 4 的执行前提在本机不成立**。源文档 Rung 4「窄本地宿主引导」默认有本地嵌入式运行时（`iv8`）。**本机没有 `iv8`**，已改为三级降级表述：`node` 桩 → `env-patch` → `playwright` 兜底，并明确「完全离线、无浏览器的产物」在本机**不存在**这条路。
2. **补充了「本机约束」这条硬判据**（任务特别要求）：新增「本机的升级终点是什么」小节 + `iv8` 缺失写入判据第 5、6 条 + 升级线索表末行。源文档没有这一层。
3. **`playwright` 被显式钉在「验证工具」而非「交付工具」**。本机没有 `iv8` 意味着很多人会拿 `playwright` 当「轻量替代」，本文在 Rung 5、坏跳、判据反例三处点名禁止。
4. **交叉引用路径失效**：源文档的 `../deliver/pure-python-rebuild-playbook.md` 等用 `references/` 风格路径，实际分散在 `references/{triage,deliver,crypto,observe}/`。已全部改为实际相对路径。
5. **保留未本地化的部分**：Rung 0–3 的证明项与升级条件、升级线索表、坏跳清单、阶梯日志模板 —— 这些与工具无关，是阶梯的核心逻辑，原样保留（译为中文）。
6. **自指错误已避免**：源文档「相关」段若按 `escalation-ladder-playbook.md` 指回自己是无效引用；本文「相关」段不含自指。