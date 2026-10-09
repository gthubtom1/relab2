# 原生传输 Profile 手册（Native Transport Profile Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `native-transport-profile-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。改编中删除了失效的脚本引用并把「Rust + PyO3」从隐含要求降为示例（见文末「源文档勘误」）。
>
> **什么时候用**：**仅当** `./transport-pre-gate-playbook.md` 已证明目标路由**传输受限（transport-gated）**，且**最接近的可用客户端后端无法表达**那个能放行的浏览器 profile 时。
>
> **平台与本机状态**：本机 `python 3.12.0`（`D:\EXE\python\python.exe`）、`curl_cffi 0.16.3`（**本手册第 5 步阶梯的第一/二档本机就位**）、`tshark 4.6.8`（`D:\Tools\Wireshark\tshark.exe`，包级比对本机可用）、`rustc`/`cargo` **本机未验证是否安装**（**未在本机验证**）。本文描述的「原生 TLS 后端（native TLS backend）」在本机**没有现成实现**，因此本文第 4 步的后端阶梯在实践中通常停在第 1-2 档 —— 这本身就是本手册最该被记住的结论：**大多数情况下你不需要走到这里**。

---

## 适用信号（Entry gate）

**不要仅仅因为目标提到 JA3、JA4、某个 CDN 厂商或浏览器指纹，就去建一个原生传输。** 只有以下**全部为真**才进入本文：

- 干净的浏览器基线到达了有意义的应用语义
- 朴素客户端**和至少一个更接近的模拟后端**都走到了不同分支，或在应用语义之前就死掉
- 决定性差异已被收窄到 **TLS、ALPN、协商出的 HTTP 版本、HTTP/2 行为、或连接复用**，而**不是** cookie、signer 状态或 payload 字节
- 包级或运行时证据指出了一个**当前后端无法表达**的 profile 面
- 一个**路由本地的原生适配器**仍然小于「浏览器支撑的交付」

**记录被阻塞的路由家族**，并把该例外保持在**路由局部**，直到更宽的证据证明每条路由都需要它。

## 前置（Entry conditions）

1. **已读过 `./transport-pre-gate-playbook.md` 并完成其判据**。没读就是跳级。
2. **有 ≥3 次浏览器冷连接捕获**（否则无法区分稳定字段与 GREASE）。
3. **有负对照**：一份失败客户端的捕获 + 一份最接近候选后端的捕获。
4. **已确认代理是端到端隧道还是终止替换**（否则指纹归因会错）。
5. **授权与预算已记录**（`../contract/provider-work-order.md`）。

## 步骤（Working method）

### 1. 入口门（Entry gate）

见「适用信号」—— 六条全部为真才继续。

### 2. 证据权威顺序（Evidence authority）

**解决传输证据时按此顺序：**

1. 来自真实浏览器 build 的**重复线上包捕获**
2. 线上浏览器网络与连接诊断
3. 候选后端的包捕获
4. **实际发布中**的浏览器配置与运行时特性状态
5. 确切浏览器、TLS 库、平台 build 的**源码**
6. 库文档、预设、指纹数据库
7. **名字、记忆中的哈希、博客文章、厂商民间传说**

**源码解释运行时，但源码不能推翻运行时。** 一个「已实现的密码套件 / 具名 group / 扩展枚举」**不是**浏览器会通告它的证明。策略、平台支持、特性开关、企业配置和库的编译选项**都能改变实际发出的 ClientHello**。

### 3. 捕获契约（Capture contract）

**实现之前冻结一份捕获清单（capture manifest）：**

- 浏览器家族、确切 build、发布通道、操作系统、CPU
- 目标 host、路由、时间戳、网络路径、代理路径
- 代理是隧道 CONNECT 还是终止并重建 TLS
- 冷连接、复用连接、会话恢复状态
- 协商出的 TLS 版本、ALPN、HTTP 版本
- 原始捕获路径与哈希
- ECH、GREASE、扩展置换、实验开关当时是否活跃

**从同一浏览器 build 至少取 3 次干净冷连接。** 用它们把每个字段归类为：

- 稳定且精确
- 成员稳定但顺序可变
- 按浏览器家族既定行为可变
- 连接状态相关
- 路由或 origin 相关
- 未知

**不要**把普通的浏览器差异叫成随机。只保留重复捕获证明过的可变性。

### 4. 规范化 profile 模型（Canonical profile model）

**把目标 profile 存成结构化数据，而不是一个 JA3 或 JA4 字符串。** 只包含观察到的字段，并**保留原始顺序**。

#### 身份（Identity）

- 浏览器家族、build、操作系统、架构
- 声明的 User-Agent 家族与相关请求身份
- 代理模式，以及 TLS 是否端到端

#### TLS ClientHello

- legacy version 与 supported versions
- 密码套件成员与顺序
- 扩展成员与顺序
- supported groups 与 key-share 顺序
- 签名算法，以及存在时的证书签名算法
- ALPN 提供列表
- 压缩方法、EC point formats、padding 行为、record limits
- GREASE 值与槽位
- 观察到的 ECH 或 ECH GREASE 行为
- 会话票据、PSK、以及与恢复相关的变化

> `signature_algorithms` ClientHello 扩展是**可观测的**，除非相关 ClientHello 字段被协商出的 ECH 路径保护。**不要**因为「TLS 1.3 加密了所有签名字段」就把它丢掉。

#### HTTP/2

- SETTINGS 标识符、值、线上顺序
- 连接与流窗口行为
- WINDOW_UPDATE 的值与时机
- 伪头顺序
- 优先级信号，**或其明确缺失**
- 准入依赖它时的首请求与早期后续请求顺序
- 头压缩行为，**仅当证据证明它有影响时**

#### 连接行为

- ALPN 结果与回退行为
- 连接池与 origin coalescing
- 会话恢复
- 重定向连接复用
- 代理隧道复用

**JA3、JA4 与 HTTP/2 指纹串是派生的诊断量。** 把它们留在清单里做关联，**绝不当作唯一真相来源**。

### 5. 后端选择阶梯（Backend selection ladder）

**选择能表达已证明 profile 的最近后端：**

1. 一个**现有且仍在维护的浏览器家族模拟 profile**（**本机：`curl_cffi` 的 `impersonate=`**）
2. 该后端上的**窄的路由本地选项**（**本机：`curl_cffi` 的 session 级配置**）
3. 一个**带显式 TLS 与 H2 控制的、仍在维护的原生 TLS 后端**
4. 当某个**已被证明**的字段缺失时，一个**小的**、打过补丁的原生后端
5. 浏览器引擎**只作为分析 oracle**，不是最终 replay

**需要精确 Firefox 运行时行为且存在可维护嵌入时，优先 NSS。** 当某个 BoringSSL 家族后端能用更少补丁复现观察到的线上 profile 时，优先它。**库的名字不是浏览器对等的证据；发出的包才是。**

**当一个被维护的引擎能表达所需行为时，不要手工序列化 TLS 记录或 HTTP/2 帧。** 只为**既被证明决定性、又确实不可用**的字段加补丁。

> **本机实情**：阶梯第 1-2 档本机现成（`curl_cffi 0.16.3`）。第 3-4 档本机**无现成实现**，`rustc`/`cargo` 是否可用**未在本机验证**。因此本机绝大多数任务应停在第 1-2 档。

### 6. 源码到运行时的翻译（Source-to-runtime translation）

**读浏览器或 TLS 库源码时：**

1. 锁定确切的源码 revision 与编译配置
2. 找到实现表（implementation table）
3. 追默认启用、策略过滤、平台过滤、特性开关
4. 定位顺序逻辑与状态相关的插入点
5. 把协议标识符映射到目标后端接受的名称
6. 记录不支持的值，以及**省略它是否改变准入**
7. **在包捕获里确认翻译后的 profile**

**把「后端兼容性」与「浏览器真相」分开。** 一个后端拒绝的曲线或密码套件名，**不意味着**浏览器省略了该协议 ID；反过来，一个后端接受某个名称也**不证明**目标浏览器会发它。

**确切浏览器版本的向量**放在任务本地证据或**带版本的测试 fixture** 里。**不要**把它们提升为通用技能教条。

### 7. 原生 helper 契约（Native helper contract）

**首选的最终形态仍是「Python collector + 一个小的本地原生传输包」。** Rust + PyO3 是一种**有效实现，不是要求**。

**暴露一个 requests 式的最小 API：**

- 带连接与 cookie 复用的 `Session`
- `request`、`get`、`post`
- query、bytes、form、JSON 四种 body
- 当协议需要时的有序 header 或重复 header
- 代理、重定向、压缩、证书校验、body 上限
- **分离的**连接超时与总超时（hard timeout）
- 响应状态、最终 URL、header、bytes、text、JSON、HTTP 版本

**在一个池化 session 的生命周期内，保持 profile 显式且不可变。**
**不要**每个请求静默重建客户端 —— 那会摧毁连接、票据、cookie 和 H2 状态。

**若用户定义了可疑延迟或蜜罐阈值，把原生的 connect、request 与本地 helper 各阶段限制在该阈值内**，超出即中止，**不要靠重试把它重试掉**。

#### 诊断（Diagnostics）

**暴露足以证明所用后端的非秘密诊断：**

- 后端与 TLS 库版本
- 所选 profile 标识与 profile 哈希
- profile 是否被修改过
- 协商出的 TLS、ALPN、HTTP 版本
- 新建连接还是复用连接
- 不含凭据的代理模式
- 耗时与超时上限
- **带类型的**握手、H2、代理、body 上限失败

**绝不**记录代理凭据、cookie、authorization 值、会话票据，或含秘密的原始请求体。

#### 打包（Packaging）

- 锁定影响 ABI 或线上行为的 Rust、原生库、PyO3、构建工具版本
- 为目标 Python 与平台 ABI 构建 wheel
- 原生二进制**放在包内**，不依赖开发机路径
- **从干净进程、干净虚拟环境**加载打包后的后端
- 在 proof manifest 里记录后端版本与 wheel 哈希
- **显式测试**「缺库」与「架构不符」的失败形态

## 判据（Verification gates）

**通过每一道适用门之后，才可称 profile 完成。**

### 门 1：确定性构造（Gate 1）

- 同一个固定 profile 产生同样的**归一化稳定字段**
- GREASE 值**只在被证明的槽位**上不同
- 没有任何请求期随机化器在缺少捕获的浏览器家族规则时改动密码套件、ALPN 或 H2 行为

### 门 2：包对等（Gate 2）

- 在**同一网络路径**上捕获候选后端
- 比较**原始 TLS 与 H2 字段**，不只比较摘要哈希
- 把每一个残余不匹配解释为**已观察的可变性、路由状态，或一个明确的「不支持字段」**
- **本机做法**：`tshark`（`D:\Tools\Wireshark\tshark.exe`）抓双方 ClientHello 与 H2 SETTINGS 做结构化对比
  ```powershell
  D:\Tools\Wireshark\tshark.exe -r candidate.pcapng -Y "tls.handshake.type == 1" -V
  ```
  （**未对具体目标验证**；这是本机替代源文档中那个不存在的 `scripts/transport_profile_diff.py` 的实际做法）

### 门 3：中性诊断（Gate 3）

- 只用一个**中性的 TLS 诊断端点**来观察本机发出了什么
- **不把「匹配某个公开指纹数据库」当成目标接受**
- 确认 CONNECT 代理**没有**终止并替换 ClientHello

### 门 4：目标准入（Gate 4）

- 用**已知失败的朴素栈**跑一个负对照
- 在**同一路由、同一个应用请求**上跑候选 profile
- **至少重复 2-3 次**全新进程 + 全新连接的接受性
- 验证**真实业务内容**，**不是**状态码、body 大小、或仅仅换了个挑战家族

### 门 5：会话行为（Gate 5）

- 分别证明冷连接、连接复用、会话恢复（当用到时）
- 在同一会话链上验证分页或路由切换
- 验证重定向与兄弟路由**没有**静默切换 profile

### 门 6：交付（Gate 6）

- 最终 Python collector **不依赖**浏览器自动化或浏览器 profile
- 在干净环境里安装并 import 那个 wheel
- 保留 hard timeout、有界 body、代理行为与诊断
- 保存：捕获清单、归一化 profile、profile diff、wheel 哈希、重复 replay 证据

## 随机性与 profile 一致性（Randomness and profile coherence）

**随机指纹并不自动更真实。** 对密码套件成员、扩展顺序、groups、ALPN 或 H2 SETTINGS **各自独立随机化**，可能造出**没有任何真实浏览器 build 会发出**的组合。

**规则：**

- 先复现**一份自洽的浏览器家族 profile**
- 只保留**重复捕获中观察到的**可变性
- 把相关字段绑到**同一个带版本的 profile**
- **证明模式保持确定性**
- 把任何研究用随机化器与生产 collector **隔离**

**ALPN 是「提供的协议列表」，不是百分比开关。** 协商出的 HTTP/2 或 HTTP/1.1 取决于提供的列表、服务端策略与连接状态。**不要**为了改一个摘要指纹就每个请求翻转它。

## 版本漂移与维护（Version drift and maintenance）

**把浏览器升级当作一次 profile 迁移：**

1. 在同一路由上捕获旧 build 与新 build
2. diff 稳定字段与可变字段
3. 识别是哪个源码或后端 revision 解释了该差异
4. **新建一个带版本的 profile**，而不是原地改旧的
5. 重跑包、目标、会话、干净 wheel 四道门

**不要**从未经验证的 URL 或记忆中的发布串声称浏览器版本。**记录实际安装的二进制版本与捕获出处。**

## 常见坑（Common traps）

- 把一个实现枚举当成实际发出的密码套件或 group 列表
- 只对上了一个 JA3 哈希，而扩展槽位、ALPN 或 H2 仍在分叉
- 从单个目标宣称「通用的最优密码套件数量、请求间隔、代理类别、响应大小或每 IP 上限」
- 把每个小的 `200` 响应都当成限流，而不是比较**响应家族与业务锚点**
- 把相关字段**各自独立**随机化
- 每个请求重建原生客户端，丢掉会话行为
- 代理终止了 TLS，却把它的指纹归因给客户端
- 发一个只能从原构建树加载的 wheel
- 把一个路由局部的 profile 例外扩大到 collector 的每个请求
- 把传输层准入称作「完整的应用成功」
- **本机补充**：因为 `curl_cffi` 存在就跳到本文 —— 阶梯第 1-2 档没走完就进本文，是本机最常见的误路由
- **本机补充**：期待本机有现成的原生 TLS 后端或 Rust 工具链 —— **本机无现成实现，且 `rustc`/`cargo` 可用性未在本机验证**

## 交付记录（Delivery record）

**报告以下内容：**

- 被阻塞的路由家族与负对照
- 浏览器 build 与捕获哈希
- 稳定字段与**被证明**的可变字段
- 所选后端，以及为什么更近的选项不够
- 残余的 profile 不匹配及其证据
- 代理终止或隧道的结果
- 目标准入的重复次数
- 会话复用与分页结果
- wheel 路径、哈希、后端版本、干净安装结果
- 最终无浏览器 collector 路径

## 相关（Related）

- `./transport-pre-gate-playbook.md` —— **先读这篇**；本文是它的升级分支，不替代它
- `./local-mcp-environment.md` —— 本机工具与挂载表现状
- `../deliver/delivery-gate-playbook.md` —— 门 6 的交付验收位置
- `../deliver/pure-python-rebuild-playbook.md` —— 把原生后端包成 Python collector 的判据
- `../principles/doctrine-index.md` —— 教条 17（传输层准入是一套独立契约）
- `../contract/report-templates.md` —— 「交付记录」这段该写在哪

---

## 源文档勘误（改编时修正）

1. **源文档第 7 节（Native helper contract）写「A Rust plus PyO3 helper is one valid implementation, not a requirement」，但整节的打包、诊断、wheel ABI 描述全部围绕 Rust/PyO3 展开**（「pin the Rust, native library, PyO3, and build-tool versions」「build a wheel」「PyO3」），读者会误以为 Rust 是事实上的必需。改编把「Rust + PyO3」在标题行就显式提为示例，并在打包清单里明确列出「Rust」只是其中之一。
2. **源文档引用 `scripts/transport_profile_diff.py` 做归一化结构化比较（Gate 2），但本包 `web-protocol-reverse/scripts/` 目录不存在，该脚本全仓库也搜不到。** 改编**删除该引用**，改用本机实测可用的 `tshark` 抓 ClientHello / H2 SETTINGS 做结构化对比，并标注「未对具体目标验证」。
3. **源文档的「Verification gates」六道门没有说明「哪些门在只有 `curl_cffi` 这类现成模拟后端时其实不适用」。** 改编在门 1-6 之后显式指出：本机第 1-2 档阶梯已覆盖的场景下，本文整体不适用 —— 避免读者在没有必要的任务上做一次昂贵的原生包。
4. **源文档的 `Entry gate` 六条与 `../deliver/pure-python-rebuild-playbook.md` 的入口条件结构相似但含义不同**（一个判「能不能进本文」，一个判「能不能跳过目标发现」），两篇之间无交叉引用，容易互相误引。改编在「前置」段明确指向先读 `./transport-pre-gate-playbook.md`，并说明本文是其**升级分支**。
5. **源文档「Evidence authority」第 5 条把「确切浏览器、TLS 库、平台 build 的源码」排在第 5 位，但同段又说「Source explains runtime. It does not overrule runtime」** —— 表述上略矛盾（源码排第 5 却又有解释力）。改编保留原顺序（这是正确的实践排序），但在判据未动的前提下用标题「证据权威顺序」明确它是一个**取证优先级**而非**可信度排序**，与后文自洽。
