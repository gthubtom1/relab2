# JSVMP 分析手册（JSVMP Analysis Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `jsvmp-analysis-playbook.md`。原文为英文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文，AI 检索时中英文均可命中。源文档技术内容经核对**未发现错误**，未作技术性修改。
>
> **什么时候用**：目标把逻辑包在**自定义 VM 或字节码解释器**里面。
>

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

---

## 适用信号（Recognition signals）

- opcode（操作码）数组
- 对字节值做 switch 的派发循环（dispatch loop）
- **很小的 VM 运行时 + 很大的编码后程序**
- helper 被藏在解释器调用之后，而不是直接的 JavaScript

## 前置（Entry conditions）

1. **一条完整的成功运行转录**。没有它就无法判断「哪一段在变」。
2. **能确定 VM 的公开边界**，即：什么输入进 VM、什么输出（wrapper 返回、状态写入、或请求出网）出来。
   源文档第 2 步把这条列为「先映射公开边界」，**这是本手册最重要的前置**。
3. **一个能执行 JS 的宿主**。本机两条路：
   - `node`（本机可用）：轻量，`vm` 模块 + 自建 stub 足以跑大部分自研 VM
     ```powershell
     & (Resolve-ReverseToolSpec -Name 'node').Command -v
     ```
   - `playwright`（本机可用）：需要真实 DOM / 定时器 / canvas 语义时才升级，代价高
4. **如果是自研 VMP 风控（尤其是瑞数 Riverbed 系）**：先查 `../../../js-reverse/references/rs-vmp-env-stub.md`。
   ⚠ 那里面的 `rs-reverse` / `sdenv` 是 Node 工具，**本机未安装**；未安装前先按该文的「路线一」判断是否真的需要装。

## 步骤（Working method）

源文档 9 步方法论**全部保留**，此处按执行顺序重排并展开。

### 1. 定位 VM 入口点

先找到谁在构造 VM 实例、谁在喂字节码。入口点通常是一个显式的 `new VM(...)` 或等价的工厂调用。

### 2. **先映射公开边界（最关键）**

识别清楚：

- **输入**：什么进了 VM（参数、字节码、配置）
- **输出**：什么出来了（wrapper 返回值、状态写入、请求出网）

> **这一步是整份手册的分水岭。** 源文档第 5 步和第 7 步都明确说了：
> 「**在证明公开边界不够之前**，不要碰 opcode handler 或解释器内部」。

### 3. **先试最小本地执行路径，而不是全量反虚拟化**

一个真实的嵌入式引擎或宿主运行时，**执行**这个 VM 所需的工作量，通常**远小于**把它反虚拟化（devirtualize）。

> 源文档原文强调：a real embedded engine or host runtime may execute the VM
> with far less work than devirtualization。

本机对应手段：
- `node` + `vm` 模块 + 手写 stub（最轻，本机实测可用，见 `iv8-runtime-cheatsheet.md` 的替代路径）
- `playwright`（最重，本机实测可启动 Chromium）

### 4. 若输出漂移仍像「宿主语义问题」，先补宿主，不要碰 opcode

如果本地输出和线上输出**结构上就不一样**（明显更短、更简单、字段缺失），那大概率是**宿主表面（host surface）缺口**，不是 VM 逻辑错了。

先按 `environment-patch-playbook.md` 补宿主，**再**回来考虑 opcode。

### 5. 只有在公开边界被证明不够时，才去抓 stage（阶段）

若存在稳定的 mode（模式）、transform（变换）、serializer（序列化器）或 packer（打包器）派发器：

- **先捕获有序的 stage 输入与输出**，**再**去逐条追 opcode

⚠ 源文档的核心警告：**不要**在 stage 级证据证明「决定性变换无法隔离」之前，就铺开做 opcode 级日志。

### 6. **把一次完整运行当作一个原子捕获**

`opaque-runtime-profile-playbook.md` 专门讲这件事：当本地移植依赖捕获到的环境块或不透明输入块时，用那一份。

### 7. 除非协议真的依赖，否则**不要**做全量 VM 还原

### 8. 优先**隔离出**当前请求需要的**那一个** helper 输出

### 9. 在尝试全量反虚拟化**之前**，先转向本地执行或 helper 包装

## 判据（Verification checklist）

只有满足以下**全部 4 条**，才可以说「JSVMP 这块搞懂了」：

1. **公开边界已被证明**（而非假设）—— 有具体的证据说明：给什么输入、拿到什么输出、这个输出足以驱动请求
2. **决定性产物已能在本地复现** —— 用固定输入验证，与线上样本一致
3. **真实请求 replay 至少成功两次**，且用的是**本地复现**的产物，不是从浏览器收割的现成值
4. **明确写下了交付形态**：
   - 若最终方案是「一个包住 VM 输出的薄 helper」→ 说清这一点，这是**被接受**的交付
   - 若本地移植仍消费**捕获的运行时 profile** → **必须**报为 snapshot-driven（快照驱动），**不得**称为「完全算法化」

> ⚠ **不构成完成**的典型情形：
> - 「opcode 表已经 dump 出来了」—— 那只是中间产物，不等于协议可回放
> - 「helper 能跑不报错」—— 见 `environment-patch-playbook.md` 的「加载成功只是里程碑」
> - 拿到了一个 final artifact 池 → 那是 pool-backed（池回放），**不是**生成能力被还原

## 常见坑（Common traps）

- **只有一个结果重要，却试图还原整个 VM**
- **漏掉**传入 VM 入口点的**旁路输入**（side inputs）
- **在证明公开边界不够之前**，就去插桩 opcode handler、派发分支、或解释器内部
- **在证明它们相互独立之前**，就把不同成功运行的 stage 片段混在一起
- 把「捕获到的 final artifact 池」当作「VM 变换已被移植」的证明
- **把 Node / jsdom / 薄 shim 下的失败，当作「VM 根本不能本地运行」的证明**
  —— 这恰恰是最容易误判的一条：本机 `node` 就是一个比 jsdom 更进一步的真实引擎

---

## 相关（Related）

- `../../../js-reverse/references/rs-vmp-env-stub.md` —— **强相关**：自研 VMP 风控（尤其瑞数系）的现成工具链 `rs-reverse` / `sdenv`，以及它们与本手册的分工
- `opaque-runtime-profile-playbook.md` —— 第 6 步「原子捕获」的展开，含 stage trace schema
- `environment-patch-playbook.md` —— 第 4 步「先补宿主，不要碰 opcode」的展开
- `iv8-runtime-cheatsheet.md` —— 第 3 步的**本机可执行替代路径**（`node` + `vm` + 自建 stub）
- `embedded-browser-runtime-playbook.md` —— 「要不要用嵌入式宿主」的进入 / 退出判据
- `local-challenge-executor-playbook.md` —— 挑战型 VM 的**契约化**执行（JSON 输入输出）
- `../observe/anti-debug-playbook.md` —— 第 3 步中「为什么执行路径比静态更稳」