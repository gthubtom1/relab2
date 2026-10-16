# 纯 Python 重建手册（Pure Python Rebuild Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `pure-python-rebuild-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文，AI 检索时中英文均可命中。改编中修正了源文档的若干表述与失效引用（见文末「源文档勘误」）。
>
> **什么时候用**：浏览器或 wire（线上报文）输出**已经绑定到固定输入（fixed inputs）**，目标是把 JS 运行时依赖彻底拿掉。这不是站点专属档案 —— 像抖音 `a_bogus` 那样的移植，只是本方法的一个实例。
>

---

## 适用信号（Recognition signals）

- 已经定位到**决定性函数入口与调用契约**，且浏览器侧输出可以用一组固定输入复现
- 已经在浏览器/wire 上抓到了**成功样本 + 期望输出**，并且知道输入材料（时间戳、随机数、会话状态、服务端下发物）
- 用户明确要**纯 Python 的可维护实现、基元回归（primitive regression）、请求粘合（glue），或确定性移植**
- 剩余工作可以用**离线 fixture 验证**，不必反复打线上

反过来说，下面任何一条为真，**就不要用本文**，应退回主循环（`../principles/workflow-overview.md`）：

- 入口（entry）、脚本 URL、版本、调用链还没定
- session bootstrap（会话引导）、transport wrapper（传输包装）、response decoder（响应解码器）、pagination state（分页状态）还有未知项

## 前置（Entry conditions）

**以下 4 条全部为真，才允许跳过全新目标发现（fresh target discovery）。缺任何一条都退回主循环。**

1. **入口、调用契约、输入材料、期望输出已知。**
   即：你知道调哪个函数、传什么、期望拿到什么，不是「大概在那边」。
2. **相关版本、字段布局（field layout）或响应 schema 已由 trace（跟踪）证据证明。**
   不是「看源码像这样」，是有捕获/断点/离线执行证据。
3. **用户要的是纯 Python 维护、基元回归、请求胶水，或确定性移植。**
   如果用户要的其实是「先跑起来就行」，那是另一件事，别硬套本文的九步。
4. **剩余工作可以在打线上之前用固定 fixture 检查完。**
   这一条是安全性条款：先离线、后外联。

**入口 / 调用链未知时的分流**：交给专职逆向技能（本机可用的是 `pyghidra-mcp` / `ida-pro-mcp` 这类反编译族，或 `js-reverse` 若已挂载）；若没有可用专员，就用本机 `frida 17.17.0` + `playwright` 抓 initiator（发起方）栈，拿到证据后回到本文。**不要**直接开始移植。

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

**本机环境前提**：

- Python 3.12 解释器路径：`(Resolve-ReverseToolSpec -Name 'pyre').Command`（本文所有命令按此路径给）
- 若最终路径需要 TLS 层模拟，`curl_cffi` 本机可用，示例见「步骤」第 9 步
- 静态 AST 那套（`esprima` / `acorn` / `@babel/parser`）**本机未装**，需要时先装；未装不影响本文九步（九步全是运行时/数值比对，不依赖 AST 解析器）

## 步骤（Rebuild loop）

> 九步，一步都不能跳。第 2/3 步是**本手册的精髓**，也是最常被糊弄过去的地方。

### 第 1 步：冻结 fixture A

把下列全部内容固定下来，存成一份 fixture：

- URL / query / body
- **进入算法的那些 header**（不是所有 header —— 只有参与计算的）
- UA
- 时间戳
- 随机字节
- 服务端下发状态（server-issued state）
- **期望输出**

### 第 2 步：判断是否需要一份独立的 fixture B

规则很硬：**只要时间、随机性、会话状态、环境、字段顺序或请求序列化（request serialization）中任何一项会影响结果，就必须要有 fixture B。**

例外只有一个：**教科书级基元（textbook primitive）** —— 那可以用「一条公开的 known-answer vector（已知答案向量）+ 一条捕获的 fixture」代替。

### 第 3 步：从一次独立运行里捕获 fixture B，且至少改动一个决定性输入

**「只改了期望输出的复制品不算独立证据。」**

这句话是整篇的重心。一份 fixture B 如果是 fixture A 的拷贝、只把 expected output 手改成实际值，那它只能证明「你写的断言和实际输出吻合」，**证明不了生成逻辑是对的**。真正的 fixture B 必须是：另起一次运行 / 另一个页面 / 另一个时间戳 / 另一个会话，且**输入侧**发生了变化，然后拿它去卡你的实现。

### 第 4 步：把移动字段分门别类

把每个字段归到以下之一：

- **server-issued（服务端下发）**
- **request-derived（请求派生）**
- **session-bound（会话绑定）**
- **random（随机）**
- **time-derived（时间派生）**
- **locally computed（本地计算）**

分不清这一类，重建出来的代码就是把浏览器行为抄了一遍，改一个会话就炸。

### 第 5 步：先移植最小的基元

顺序：**digest（摘要）→ alphabet（字母表）→ stream transform（流变换）→ packer（打包器）→ key schedule（密钥编排）→ field builder（字段构造器）→ response decoder（响应解码器）**。

不要一上来就把整个 SDK 抄成 Python。

### 第 6 步：每移植一个基元就对一次 fixture A

**先把第一个发生分歧的字节、字段或分支存下来，再去改下一个单元。**

这是本文与「跑通了再说」最大的区别：不存分歧点，你第二次运行时就不知道是哪一步开始错的。

### 第 7 步：在恢复线上动态字段之前，fixture B（或「公开向量 + 捕获样本」这一对）必须在**没有目标专属分支（target-specific branching）** 的情况下通过

「实现里写了 `if target == "xxx":`」是自欺欺人。判据就是这一条。

### 第 8 步：两个 parity check（一致性校验）都过之后，才恢复随机与时间路径

恢复后检查：shape（形状）、length（长度）、alphabet（字符集）、URL roundtrip（往返）、binary envelope invariants（二进制信封不变量）。

注意：这一步验的是**不变量**，不是**逐字节相等** —— 带时间戳的字段本来就不该逐字节相等。

### 第 9 步：最后才接请求胶水（request glue）

- 用**一个**连贯的 `requests.Session`（或本机的 `curl_cffi` session）
- **每一次调用都重建 request-derived 值** —— 不要预计算一次然后复用（见 `../state/public-bootstrap-envelope-playbook.md` 里「绑定到请求的产物属于请求循环内部」那条教训）

本机 `curl_cffi` 的接入形态（**未在本机对具体目标验证**，仅为路径示意）：

```python
# (Resolve-ReverseToolSpec -Name 'pyre').Command
from curl_cffi import requests as cf

# 传输层模拟浏览器 TLS/H2 指纹，替代 stdlib + 手搓 header
sess = cf.Session(impersonate="chrome", timeout=(5, 20))
r = sess.post(url, data=body, headers=headers, cookies=jar)
```

判据第 7 条说的「最终文件不得 import 浏览器自动化或 JS 运行时」，**不排斥 `curl_cffi`** —— 它是 TLS 层 HTTP 客户端，不是浏览器，也不是 JS 运行时。

## 判据（Verification gates）

**以下 8 条全部通过，才算「纯 Python 重建完成」。任一条不过，就不是这个形态。**

1. **fixture A 输出逐字节一致。**
2. **存在动态或上下文输入时，fixture B 也必须过**；否则「一条公开基元向量 + 一条捕获 fixture」两条都要过。
3. **基元向量独立于完整生成器通过** —— 单独跑 `digest()` / 编码器本身，而不是只在全链路里捎带跑过。
4. **序列化与 URL / 二进制 roundtrip 无损** —— 最终产物 roundtrip 回来必须一模一样。
5. **随机化冒烟检查保持形状（shape）**，但**不得替代固定向量 parity** —— 冒烟只是形状检查，不是正确性证明。
6. **线上 replay 在一个连贯会话上重复成功**（跑不了则该项记 `not-requested`，并显式声明 live acceptance 未证明）。
7. **最终文件不 import 任何浏览器自动化或 JS 运行时**，除非任务明确接受了一个极窄的本地 helper。禁用清单：**Node、jsdom、iv8、Playwright、Selenium、CDP、页面上下文执行（page-context execution）**。
8. **`main.py` 或声明的入口文件，在 IDE 默认配置下可直接右键运行，不带任何必填命令行参数。** 命令行 wrapper 是可选的验证工具，**不是交付接口**。

配套还要满足本包交付门（`./delivery-gate-playbook.md`）中对应形态的检查项；本文八条是**重建专属的加严项**，两者都要过。

## 规则（Rules）

1. **除非固定输出匹配，否则「加载成功」与本手册无关。** helper 能 import、能跑，只证明运行时活着。
2. **指纹与环境值是显式输入，不是隐藏的浏览器依赖。** 它们可以作为 collector 的配置项存在（`./delivery-gate-playbook.md` 明确允许），但不得因此让浏览器在每次运行时保持在线。
3. **未经证据，不得跨版本复用常量、字段顺序或字母表。**
4. **不得把「一个基元模板」宣称为「一个完整生成器」。**
5. **不得把 Node、jsdom、iv8、Playwright、Selenium、CDP 或页面上下文执行加入最终依赖路径。**
6. **最终请求胶水必须暴露一个 IDE 右键可运行的 Python 入口，无必填 CLI 参数。**
7. **目标专属向量放在任务工作区或 `../examples/` 下** —— 它们示范方法，不定义本技能包的归属。

## 常见坑（Failure modes）

| 触发条件（Trigger） | 立即动作（Action） | 回退边界（Fallback） |
|---|---|---|
| 版本或字段布局未确认 | 停止复用常量 | 回到核心证据采集（主循环） |
| 入口或调用链未知 | **不要开始移植** | 用调用链逆向技能；无则用 `frida` / `playwright` 抓 initiator 栈 |
| 基元过了但完整输出不过 | 比对**第一个分歧字段** | 不要上线 replay |
| 形状对但服务端拒绝 | 查会话、cookie、UA、时序、传输层准入 | **不要加浏览器兜底** |
| 证明 JS 生命周期确实必需 | 把失败的 Python 证明**记录下来** | 只升一级到窄 helper，不升到浏览器自动化 |
| fixture B 是 fixture A 的复制品 | 作废该 B，重新独立捕获 | 输入侧不变 = 不算独立证据 |
| 实现里出现 `if target == ...` 分支 | 拆开，把站点特性参数化 | 目标专属分支违反判据第 7 条 |

**本机常见坑补充**：

- 把本机可用的 `node v24.20.0` 当成「反正有 Node，用 Node 跑更省事」—— 它是**迁移期的对照宿主**，不是交付形态；判据第 5 条照样卡住。
- 静态 AST 那套（`esprima` / `acorn` / `@babel/parser`）本机没装时，误以为「必须先装 AST 解析器才能开始」—— 九步全都不需要它，只有结构还原需要。
- 抓包时去找 `reqable` —— 本机没有，**用 `tshark` / `mitmdump`**（命令见 `../observe/local-mcp-environment.md`）。

## 示例 fixture（Example fixtures）

`../examples/douyin-bdms-pure/` 里有一个「固定 trace 式纯 Python 签名维护」案例的基元向量与笔记（[algorithm-notes.md](../examples/douyin-bdms-pure/algorithm-notes.md)）。**把它当作 fixture 纪律与负面边界的示例**，不是路线选择器，也不是从零开始的完整说明书。

## 相关（Related）

- `./delivery-gate-playbook.md` —— 交付门；本文八条判据必须与对应形态的 gate 同时满足
- `./response-decode-playbook.md` —— 第 5 步里「response decoder」这一格的专门手册
- `./case-reuse-playbook.md` —— 从历史 case 复用 helper 时的验证回路
- `../crypto/iv8-runtime-cheatsheet.md` —— **`iv8` 本机无**；该文档的 API 形态供你手头已有该运行时时参考，**未在本机验证**
- `../crypto/offline-inline-deob-playbook.md` —— 先离线还原，再谈移植
- `../observe/transport-pre-gate-playbook.md` —— 判据第 6 条「线上被拒」时先排除传输层准入
- `../triage/verifier-replay-playbook.md` —— 「重复成功」的验证规程
- `../principles/doctrine-index.md` —— 教条 5（自动化不是可接受的拐杖）、教条 7（交付门高于便利）
- `../../../field-journal/_template.md` —— 完成后按本包证据规范落一条脱敏 case 记录

---

## 源文档勘误（改编时修正）

1. **源文档「Rules 第 5 条」与本包 `delivery-gate-playbook.md` 的「Acceptable runnable delivery shapes」在字面上冲突。** 交付门把「Python + 隔离的本地 JS helper」列为**可接受的**可运行交付形态，而本文规则第 5 条禁止 Node 进入最终依赖路径。改编后的裁决：**两者按形态分层** —— 判据第 7 条是「纯 Python 重建」这一形态的**终局**要求；若任务在 `delivery-gate-playbook.md` 下**明确接受**了一个极窄 helper（且该 helper 不读 `window`/`document`/浏览器存储），则按交付门走并如实标注 `runtimeFree: false`。源文档没点明这层关系，读者容易自相矛盾。
2. **源文档多处引用 `scripts/` 下的脚本（`check_reverse_env.py`、`evidence_normalizer.py`、`forward_test_report.py`、`transport_profile_diff.py`、`grpc_frame_inspector.py` 等），但本次落地的 `web-protocol-reverse/` 目录中 `scripts/` 目录根本不存在**（`C:\relab2\skillpack\skills\web-protocol-reverse\scripts` 无此目录，仓库内也搜不到这些文件）。改编时已把所有脚本引用删除或改写为可执行的实际做法，**不再引用不存在的路径**。这是落地时的**真实缺口**，不是改编引入的问题。
3. **源文档入口条件引用的专员技能名 `camoufox-js-reverse` 以及 `chrome-devtools` / `js-reverse` 这两个 MCP 家族，在本机 agent 工具注册表中未挂载**（本机挂载的是 `pyghidra-mcp` / `idapro`(13337 HTTP) / `ida-pro-mcp` / `angr-mcp` / `x64dbg-automate-mcp`，均为逆向侧，无 web 侧）。改编时按本机实际改写分流路径。
4. **源文档规则第 6 条把入口形态特指为 PyCharm 右键运行。** 改编保留「IDE 右键可运行、无必填 CLI 参数」这一实质要求（这才是它想表达的），去掉对特定 IDE 的绑定。
5. **源文档没有给出任何本机路径或运行前提。** 改编补入本机 Python / Node / curl_cffi 的实际路径与版本，并显式写出「Node 可用但禁入最终依赖」这一本机特有的张力，避免读者以为 `node` 不可用而绕路。