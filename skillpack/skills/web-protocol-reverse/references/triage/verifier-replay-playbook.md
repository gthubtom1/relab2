# 验证器重放手册（Verifier Replay Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `verifier-replay-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。本文是本组最长的一篇，源文档的 Common traps（19 条）与 Delivery rule（交付规则）已分别改写为「常见坑」与「判据」两段。
>
> **什么时候用**：
>
> - 数据请求被验证码（captcha）、一次性验证、或点击顺序挑战挡在后面
> - 没有有意义的业务 signer，但请求在 verifier 通过前一律失败
> - 浏览器里点一下之后，下一个请求才解锁
>

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

---

## 适用信号（Recognition signals）

- 「接口返回成功，但下一个业务接口还是 403」
- 「验证码接口明明过了，业务接口还是被拦」
- 「浏览器里手动点一下就过了，脚本怎么试都不行」
- 「点完验证码要等一会儿才生效」
- 「每次失败的错误码都不一样」
- 「本地复现出来的轨迹明显比浏览器的短」

## 前置（Entry conditions）

1. **一条完整的成功 transcript（会话记录）**。没有它，下面所有「对照」都无从谈起。
2. **一条失败 transcript**。两者必须在**同一套会话假设**下取得。
3. **样本已分级**。先读 `./positive-sample-hygiene-playbook.md` —— 被污染的失败样本会把结论带偏。
4. **wire 可见性**。本机两条路都可用：

```powershell
# 实时录制 verifier 整轮
& (Resolve-ReverseToolSpec -Name 'mitmdump').Command --listen-port 8899 --save-stream-file flow.mitm

# 离线读已抓的 pcap，列出有序请求
& (Resolve-ReverseToolSpec -Name 'tshark').Command -r flow.pcapng -Y "http.request" -T fields -e frame.number -e http.request.method -e http.request.full_uri
```

5. **若走本地引导执行器**：本机用 `node`（`(Resolve-ReverseToolSpec -Name 'node').Command`）或 `playwright`。**`iv8` 本机没有**；`../crypto/iv8-runtime-cheatsheet.md` 的 API 形态**未在本机验证**。

---

## 步骤（Working method）

### 挑战 HTML 直接出现在业务路由上（Challenge-HTML business route）

当业务路由返回的**不是 JSON 而是挑战 HTML**：

1. 在**同一条会话链**上冻结一组 失败 → 解题 → 成功 三联样本
2. 把链接出来的挑战脚本当作**同会话 bootstrap 资产**
3. 收获最近的**可重放工件**，通常是一个被改写的 URL 或 cookie 头
4. **之后**才去建模分页或并发

若短 token 与长 token 共用一个字段名，先用 `../observe/dual-writer-param-playbook.md`，再锁定产品生成器。

### 核心规则（Core rule）

**验证器契约可能是整条有序 transcript，而不只是最后的答案、token 或轨迹请求。**

验证器端点返回成功，本身可能**只是一个中间里程碑**。

必需的预热（warm-up）、设备（device）、日志（log）、遥测（telemetry）或行为（behavior）sidecar（旁路请求），**以及第一个下游业务被接受**，都属于同一份证明。

### 多阶段沉降（Multi-stage settle）

某些 verifier 与风控流程需要**好几个** sidecar 或采集器式请求，下游业务路由才会信任这个会话。

**干净浏览器 trace 显示有多个阶段时，不要在本地运行时/定时器循环/transcript 重放拿到第一个非空输出就停。**

改算法之前，先比这些面：

- sidecar 请求的**数量与顺序**
- body 大小或帧大小的序列
- 内容类型与 wrapper 形态
- 响应状态与**应用层确认**
- 从一个请求到下一个的状态迁移
- **第一个文档或业务页之后，是否还有路由局部 sidecar 触发**

浏览器 trace 是多阶段、本地是单阶段时，**先**查：生命周期、定时器、输入沉降（settle）、响应 cookie 镜像、缺失的 sidecar 分支。

> token 形态、cookie 长度、或单个 sidecar 的 HTTP 200，**在没有下游消费者的情况下都不是验收**。

### 工作法（Working method）

1. **先分类 verifier 家族与失败面**，再搬运字段：
   - 滑块（slider）、点选（point-click）、顺序点选（ordered-click）、旋转（rotate），或其它分支
   - **同一厂商的新旧代际可能有互不兼容的字段与证明构造器**
   - 协议、计算、感知、行为、遥测、会话、传输 —— 七个面分开看
2. **把一个 verifier 轮次端到端冻结为一条有序 transcript**：
   - prehandle 或 load 响应
   - 回调 id 或随机密钥
   - 资产 URL 与已下载图片
   - config、device、warm-up、log、telemetry、status 路由
   - 验证 token、工作因子（work factor）或轮次 id
   - 完整 profile 基线，以及后续 delta 形态的载荷
   - 最终 verify 请求与响应
   - **第一个消费 verifier 输出的下游业务请求与响应**
3. 按 序号 / initiator / 会话 / 角色 / 状态写入 / 语义响应 逐条清点每个观察到的请求
4. 确定**是什么输出授权了下一个业务请求，以及它从哪进入那个请求**：
   - 直接 header / cookie / query / body 字段
   - **或者**是稍后被另一个 signer 包装的「签名前明文 / 加密前明文」
5. 在复用任何东西之前，确定新鲜度模型：
   - 一次性 vs 可复用
   - 绑本轮 vs 跨轮有效
   - 耦合于页面 / body / 时间戳 / signer 上下文，还是独立
6. 主证明看着对但仍不被接受时，用**单变量 sidecar 对照**
7. 映射 baseline、sidecar、delta 载荷、最终 verify 之间**每一个共享字段或派生关系**
8. 按 verifier 类型拆分答案路径：
   - 点选 / 顺序点选：提示提取、命中定位、证明封装
   - 滑块 / 图像派生：还原图坐标、显示坐标、提交坐标、行为轨迹
9. **把声明的时间戳与事件增量，从真实墙钟经过时间中分离出来**
10. 在本地解出或重建所需输出
11. 在每一个稳定的编码、签名、封装、信封边界上验证固定输入
12. 用协议形式重放**整条** verifier transcript
13. 用得到的 token / cookie / 坐标 / grant，在**同一轮顺序**里发出下游业务请求

### Transcript 清单（Transcript manifest）

记录一轮完整的「已接受」或「已知最好」的结果：

```markdown
验证器 Transcript
- 轮次 id 或本地抓取 id：
- 会话作用域：
- 生效资产与 helper 哈希：
- 步骤 1：路由、角色、请求哈希、响应族、状态写入、耗时偏移
- 步骤 2：路由、角色、请求哈希、响应族、状态写入、耗时偏移
- 最终验证器语义结果：
- 第一个下游消费者结果：
```

**每一步都要区分**：

- 请求传输成功
- 应用信封成功
- sidecar / 遥测被接受
- 最终验证器被接受
- 下游业务被接受

**不要**把这五个合并成一个 `success` 布尔值。

### sidecar 发现与对照（Sidecar discovery and controls）

答案或轨迹**看着对**但仍失败时，**在再次调行为之前**先清点相邻的请求族：

- 设备或指纹采集
- 日志、状态、遥测、风险事件上报
- 预热、前置（preflight）、config 或时间同步调用
- 资源驱动的状态初始化
- 答完之后、verify 之前的 sidecar

用浏览器 initiator 与 wire 顺序识别候选，然后跑一个**窄的对照矩阵**：

1. 保住一条已接受或人工确认过的答案路径
2. **一次只**屏蔽或去掉一个 sidecar 路由族
3. 固定会话、答案、轨迹、时序策略、以及所有其它路由
4. 在**新一轮**上恢复该路由并重复
5. 比对**最终验证器语义**，而不只是 sidecar 的 HTTP 响应

> **一个 sidecar 只有在「受控去掉会改变最终验收族，且恢复后能救回来」时，才成为协议相关内容。** 只有一次相关性、没有负控与恢复对照，**不够**。

**保持 header 或传输例外为路由局部。** 一个落地路由需要不同头集合，**不证明** telemetry 与 verify 路由也需要同样的例外。

### Sidecar 消融矩阵（Sidecar ablation matrix）

在调答案或轨迹之前，为同一套会话假设**冻结**一张消融矩阵，存到任务缓存，作为无秘密的表：

| 条件 | 动作 | 最终验证器语义 | 第一个下游消费者 | 结论 |
|---|---|---|---|---|
| 完整 transcript | 所有必需 sidecar 都在 | | | 基线 |
| 去掉 telemetry/设备域 | 屏蔽或去掉该 host 族 | | | sidecar 必要性 |
| 去掉一个预热或日志阶段 | **只**删掉那一步 | | | 阶段必要性 |
| 保留 sidecar，删掉最终 token 字段 | 去掉一个决定性 verify 字段 | | | 结构族 |
| 保留结构，断掉共享基线链接 | 基线与增量**独立**重新生成 | | | 一致性族 |
| 保留所有包，去掉真实等待 | 立刻发送声明了好几秒的轨迹 | | | 时序族 |

规则：

- **一次只改一个变量**
- 每一行都记录请求顺序、耗时偏移、状态写入
- **sidecar 的 HTTP 200 不够**；要记录应用层确认，以及最终语义是否变化
- 去掉某个 sidecar 把干净成功翻成拒绝 → **那个 sidecar 就是契约的一部分**
- **矩阵里还有未解决的必要性或一致性问题时，不要开始轨迹搜索**

### 共享基线与稀疏增量（Shared baseline and sparse delta）

有些 verifier 家族先上传一份完整的设备/环境基线，之后再发一个从该基线派生的**稀疏增量**、紧凑状态 token 或行为更新。

生成请求**之前**，先建立共享状态契约：

| 字段类 | 写入方 | 基线用法 | 增量用法 | 关系 | 作用域 |
|---|---|---|---|---|---|
| 身份 | bootstrap 或 profile 构造器 | 全量 | 复制或保留 | 相等 | 轮次/会话 |
| 时间 | 时钟或服务端种子 | 初始 | 单调更新 | 派生 | 轮次 |
| 计数器 | 采集阶段 | 来源 | 复制或变换 | 派生 | 轮次 |
| 环境 | profile 构造器 | 全量 | 子集 | 子集 | profile/轮次 |
| 校验和 | 包构造器 | 包内局部 | 包内局部 | 重算 | 请求 |

> **只使用观察到的类别与关系。不要把这张表当固定 schema 抄走。**

要证明基线是 profile 级、会话级还是轮次级。为那个作用域建**一个**基线实例，让该轮内每个依赖请求都从**同一个**实例派生。

**不要独立随机化那些必须相等、必须取子集、必须单调、必须校验和链接、或必须计数器链接的字段。**

> 每一个包都能自己解密、自己解析、自己签名、自己过校验和，而整轮**仍然失败** —— 因为这些包描述的是**不同的设备状态**。**包有效不等于 transcript 一致。**

#### 共享状态一致性检查表

在怪答案或轨迹质量之前，先证明这些：

- 有一个会话或轮次 id 把 init、sidecar、verify、第一个消费者绑在一起
- 为那个作用域**只创建一次**完整基线实例
- 稀疏/增量包派生自**同一个**实例，而不是第二个随机 profile
- 计数器、采集耗时、校验和种子、或单调字段在包之间保持链接
- 必须匹配的动态字段（ip、服务端时间、本地采集起点、certify 或轮次 id 槽位）是**复制**而非**重掷**
- **每个包单独都过、但整轮失败 → 先修一致性，不是轨迹噪声**

若基线仍是一份被抓下来的不透明 profile，其出处与交付分类见 `../crypto/opaque-runtime-profile-playbook.md`。

### 真实时序（Real timeline）

把时间当作**三个独立的面**：

- 写进载荷的**绝对时间戳**
- 轨迹或遥测内部的**事件增量**
- 请求之间的**真实墙钟延迟**

> 一条声称有好几秒交互、却把每个阶段立刻连发的 transcript，即使每个时间戳格式都正确，**内部也是自相矛盾的**。

要证明：

- 每个时钟域内的**单调顺序**
- 服务端时间、本地时间、事件偏移之间的**关系**
- 行为完成、遥测上传、最终 verify 之前的**真实等待**
- 重试是否需要新一轮，还是能复用当前状态

**只按已证明的契约需要**使用真实等待，并保留任何用户定义的硬超时或蜜罐上限。

#### 时序操作检查表

- 把抓下来的轨迹**重新定时到当前墙钟**，而不是重放陈旧的绝对时间戳
- 让「声明的交互时长」与「verify 前的实际 sleep」**保持在同一数量级**
- 干净 transcript 里遥测在 verify 之前，就保持这个顺序
- 轨迹声称约一秒的运动，就**不要**在几十毫秒内发完整条链
- 重试时，先决定这一轮能否复用，还是必须完整重新初始化

### 动态资产与 helper 版本（Dynamic assets and helper versions）

脚本 URL、资产后缀、缓存击穿路径变了，**本身并不证明**验证器算法变了。

重逆之前：

1. 给当前生效的资产做哈希
2. 比对公开 helper 或 VM 边界
3. 重跑确定性的固定向量
4. 输出变了时，比对阶段 trace
5. **只有**当行为、封装或向量确实分叉时，才建新的 helper 版本

> 保留一个极小的、宿主无关的本地 JS 或 WASM helper，只要它是最窄的忠实实现。**Python 仍必须拥有 HTTP、会话顺序、状态、超时和验收检查。**

### 验收阶梯（Acceptance ladder）

从窄到宽逐层验证：

1. 挑战或初始化响应在**语义上**有效
2. 必需的 sidecar 返回了它们**预期的应用层确认**
3. 基线与增量的状态关系成立
4. 答案、行为、helper 的固定向量匹配
5. 最终验证器响应里含该平台特有的「被接受」语义
6. **第一个下游业务请求消费了 verifier 结果**

> HTTP 200、通用成功信封、token 形态的值、或 sidecar 上传确认，**都不能替代**最终适用门。

**把错误码或 subcode 的变化当成定位证据。** 用受控的状态变化证明它们的含义；**不要**把某个目标的码提升成通用 verifier 教条。建一份任务局部的语义图，见 `./verifier-error-localization-playbook.md`。

#### 下游消费者契约（Downstream consumer contract）

**在第一个业务请求消费它之前，验证器被接受都只是中间状态。**

记录：

- 哪些 grant 字段离开 verifier：token、cookie、query、header、body、还是成功别名
- 这些字段从哪进入原始业务 URL 或后续 API
- 是否存在别名，活浏览器实际发的是哪些
- **业务通过的 oracle**：内容指纹、magic bytes、非挑战 HTML 标记、还是 JSON schema
- **同轮封装**：不要把 A 轮的 grant 和 B 轮的消费者混起来

> 若验证器语义已过、消费者仍返回挑战 HTML 或空外壳，**先查封装与会话绑定**，再重开答案生成。

---

## 判据（Completion criteria）

（源文档的 Delivery rule 已并入本节）

**不要在最终方案里模拟 UI 交互。把 verifier 复现为一条有序的协议 transcript。**

只有以下**全部**成立，才算交付完成：

1. **已按顺序重放完整 verifier transcript**，包含全部必需 sidecar
2. **Python 拥有真实 HTTP 重放**，不含浏览器自动化、CDP 页面驱动、手动点击
3. **共享状态规则**已显式记录（哪些字段相等 / 子集 / 单调 / 链接）
4. **真实时序**已被使用，且顺序与干净 transcript 一致
5. **helper 边界**已说明；若仍有本地 JS/WASM helper，已标注「双运行时 helper 封装」
6. **最终语义验收**已确认（不只是 HTTP 200）
7. **第一个下游消费者**在**同一轮**成功消费了 verifier 结果

**并且必须同时报告**：

- 消融矩阵的路径
- 任务局部的错误语义图（见 `./verifier-error-localization-playbook.md`）
- 任何人工/浏览器 oracle 的 positive-sample hygiene 等级（见 `./positive-sample-hygiene-playbook.md`）
- 环境风险是否被牵涉
- 是否仍存在本地 JS/WASM helper（双运行时封装）
- **若交付是「快照驱动」而非完全算法化，必须如此标注**

判据的反例（**以下情况算没做完**）：

- 只到「验证器语义成功」就宣布交付 —— **缺下游消费者证明**
- sidecar 只发了 HTTP 200 就当被接受
- 轨迹在毫秒级内发完，却声称了好几秒交互
- 拿被抓下来的不透明 profile 当「已算法化交付」
- 最终方案里还有模拟点击 / 模拟拖动

## 常见坑（Common traps）

（源文档 Common traps 19 条，译并归类）

**在验证器之外乱找业务签名器**；**用自动化点击代替理解验证器载荷**；**把 verifier 当成纯 UI 行为**；**把 verifier 响应成功当业务流已解决**；**在没检查被省略的预热或遥测 sidecar 之前反复调轨迹**；**把 sidecar HTTP 成功当它的状态与最终 verify 请求匹配**；**从独立随机状态生成完整基线和稀疏增量**；**伪造看似合理的时间戳，却用不可能的墙钟时序发 transcript**；**在检查边界与固定向量平价之前就重逆每个动态资产路径**；**跨相邻验证轮次混用 token、图片、回调或证明字段**；**把提示图 OCR 或图像匹配单独当 verifier 成功的证明**；**混用还原图像素、渲染 UI 坐标与提交证明坐标**；**在没证明新鲜度、一次性或绑轮次之前复用验证器工件**；**在实时流程把工件喂给签名前明文时，却在签名/加密之后才注入**；**因为页面角色看起来相似，就把某一验证器家族或代际的字段搬到另一个**；**把被自动化污染的手动滑动失败当轨迹真相**；**在结构与 sidecar 都已经验证通过、只剩风险类语义时仍继续轨迹搜索**；**在验证器语义成功时就宣布交付完成，没有同轮下游消费者证明**；**在某出口或自动化 profile 上连续被拒之后仍无视环境风险**。

## 相关（Related）

- `./startup-triage-playbook.md` —— `verifier-gated` 家族判定从这里开始
- `./verifier-error-localization-playbook.md` —— 错误码漂移时的定位方法与消融顺序
- `./positive-sample-hygiene-playbook.md` —— 拿到样本先分级，避免污染结论
- `./troubleshooting-playbook.md` —— 通用症状路由（含 sidecar 与身份场景）
- `./escalation-ladder-playbook.md` —— 本地引导执行器该用哪一级；`iv8` 本机无
- `./symptom-heuristics.md` —— 「接口返回成功但业务还是被拦」等口语症状
- `../state/challenge-artifact-harvest-playbook.md` —— 收获 verifier 产物的具体手法
- `../observe/dual-writer-param-playbook.md` —— 同字段名同时有长短两种取值
- `../crypto/opaque-runtime-profile-playbook.md` —— 不透明 profile 的出处与交付分类
- `../deliver/delivery-gate-playbook.md` —— 交付门

---

## 源文档勘误与本机化改动

1. **源文档的 `## Contents` 目录与正文小节对不上**。目录列了 13 项，但正文里 `Transcript manifest` 之后缺 `Common traps` 的目录锚点一致性问题已通过重排解决；同时目录中的「Sidecar discovery and controls」与正文标题措辞有出入。改编时按正文实际小节重建了对应关系。
2. **源文档空行残留**：`## Shared baseline and sparse delta` 标题后有两个连续空行、`## Acceptance ladder` 与 `### Downstream consumer contract` 之间有空行 —— 排版残留，已清理。
3. **共享状态契约表有自我警告但易被误抄**：源文档表格列了 identity/time/counter/environment/checksum 五类，但明确写了 `Do not copy this example as a fixed schema`。本文保留表格**并把警告加粗前置**，防止被当成固定 schema 搬运。
4. **交叉引用路径失效**：源文档用 `references/xxx.md`，实际文件分散在 `references/{triage,observe,crypto,state,deliver}/`。已全部改为实际相对路径。
5. **Delivery rule 已并入判据段**。源文档把「不要模拟 UI 交互」放在 `## Delivery rule`（位于文末），不在目录里，且与 `## Common traps` 的最后一条重复。改编时并入判据段作为第 2、7 条。
6. **本机化**：`mitmdump` / `tshark` 完整路径命令在「前置」给出；「本地引导执行器」在本机走 `node` / `playwright`，并标注 `iv8` 本机无。
7. **保留未本地化的部分**：工作法 13 步、transcript 清单、消融矩阵、共享状态一致性检查表、时序操作检查表、验收阶梯 6 级 —— 这是本文的核心方法论，原样保留（译为中文）。