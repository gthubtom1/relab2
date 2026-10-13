# 验证器错误定位手册（Verifier Error Localization Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `verifier-error-localization-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。
>
> **什么时候用**：验证门（verifier-gated）流程**在报文结构看起来已经合理之后仍然失败**，或者目标返回**不断变化的拒绝码 / 子码（subcode）**时。
>

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

---

## 适用信号（Recognition signals）

- 「每次失败的错误码都不一样」
- 「报文看着该有的都有，但就是不收」
- 「sidecar 都 200 了，最终 verify 还是拒」
- 「完整基线和稀疏增量分别都能自己校验通过，整轮还是失败」
- 「普通浏览器能过，自动化/协议就是过不了」
- 「拿另一个站的错误码表套过来，完全不管用」← 源文档专门警告的反模式

## 前置（Entry conditions）

1. **冻结一轮的骨架（round skeleton）**。见下面 Step 0 —— 没冻结之前不要做任何消融。
2. **有一份已接受的干净成功样本**，用来判断「消融之后变差了没有」。见 `./positive-sample-hygiene-playbook.md`。
3. **消融矩阵能落盘**，每行一个变量。

---

## 步骤（Working method）

本文建立一份**任务局部**的语义映射（semantic map）。

> **不要把某个厂商的错误码表提升成普遍教条。**

### 目标（Goal）

按顺序回答四个问题：

1. 这个拒绝是**结构性**的吗？
2. 是**缺必需的 sidecar 或阶段**吗？
3. 是**共享状态或时序不一致**吗？
4. **只有到这一步**：才是答案 / 行为 / 环境风险吗？

### Step 0：冻结一轮骨架（Freeze one round skeleton）

保留**一个**有序 transcript id，**不要**跨轮混字段。

记录：

- init 或 load 的响应族
- 必需的 sidecar
- 最终 verify 请求与语义 body
- **第一个下游消费者**

### Step 1：结构消融（Structure ablations）

**一次只**制造一个受控的缺失或畸形字段：

- 删掉最终 token 或设备/证明字段
- 破坏校验和或信封封装
- 发一个过期的轮次 id，其余字段保持不变

**预期结果族：结构性拒绝。**

> **如果结构被破坏后线上代码从不变化，那么你正在读的那条代码路径不是权威路径。**

### Step 2：sidecar 消融（Sidecar ablations）

配合 `./verifier-replay-playbook.md`：

- 完整 transcript
- 去掉或屏蔽 telemetry/设备族
- **只**去掉一个预热或日志阶段
- 一次恢复一个阶段

**预期结果族：sidecar 必要性或风险门。**

### Step 3：一致性消融（Consistency ablations）

- **独立地**重新生成完整基线与稀疏增量
- 故意让计数器或采集耗时链接失步
- 把本应从 DeviceConfig 或 init **复制**的字段**重新随机**

**预期结果族：共享状态拒绝。**

### Step 4：时序消融（Timeline ablations）

- 保留载荷时间戳，但去掉真实等待
- 若干净 transcript 是「telemetry 在 verify 之前」，就把两者**顺序对调**

**预期结果族：时序或行为风险拒绝。**

### Step 5：答案或行为消融（Answer or behavior ablations）

**只有在 Step 1–4 都做完之后**：

- 改轨迹距离、点数、或答案封装
- 用干净人工轨迹 vs 合成轨迹互换

**预期结果族：答案/行为拒绝。**

### Step 6：环境面（Environment surface）

若**干净的普通浏览器成功存在**，但自动化或协议仍失败：

- 按 `./positive-sample-hygiene-playbook.md` 给样本分级
- **先换出口，或减少连续拒绝次数**，再谈算法改动
- **把环境风险当成一等公民**，不是轨迹噪声

### 任务局部映射模板（Task-local map template）

保存无秘密的笔记：

```markdown
错误映射表
- 目标家族：
- 轮次作用域：
- 码或子码 A：
  - 由谁产生：
  - 面：structure | sidecar | consistency | timeline | answer | environment
  - 恢复方式：
- 码或子码 B：
  - 由谁产生：
  - 面：
  - 恢复方式：
- 被接受的语义：
  - 必须保持一致的 body 字段：
- 下游消费者通过 oracle：
```

### 诊断顺序（Diagnostic order）

新拒绝出现时的默认顺序：

```text
结构
  -> sidecar 的发出与确认
  -> 共享基线 / 稀疏增量一致性
  -> 真实时序
  -> helper / 数据封装
  -> 答案或轨迹
  -> 环境风险
```

**在第一个能受控复现该拒绝族的面处停下。**

### 反 cargo-cult 规则（Anti-cargo-cult rules）

- 不要把另一个任务的拒绝码硬编码成普遍真理
- 不要把 HTTP 200 或通用成功信封当接受
- **在结构或 sidecar 必要性尚未确定时，不要继续轨迹搜索**
- 不要把「helper 加载成功」当 oracle

---

## 判据（Completion criteria）

1. **Step 0 已完成**：轮次骨架已冻结，含第一个下游消费者。
2. **代码/子码已被映射到六个面之一**（structure / sidecar / consistency / timeline / answer / environment），且有**受控消融**作为证据 —— 不是靠猜。
3. **顺序被遵守**：如果还在 Step 1 或 Step 2，就**没有**去调答案或轨迹。
4. **诊断在第一个能受控复现该拒绝族的面停下**，没有继续往下爬。
5. **若结论是环境风险**：已经给出「干净普通浏览器成功存在」的对照，否则不得下环境结论。
6. **任务局部映射表已落盘**，且**没有**把别家的码表当作本家的权威。

判据的反例（**以下情况算没做完**）：

- 「错误码 A 好像表示签名错」—— 没有消融证据
- 结构消融显示线上代码不变，却还在读那条代码路径
- Step 2 还没跑完就去调滑块轨迹
- 用 contaminated-failure 当成答案/轨迹的证据
- 声称「是环境问题」但手上根本没有干净浏览器成功样本

## 常见坑（Common traps）

- **在结构或 sidecar 必要性未知时死磕轨迹**。这是最耗时的一条。
- **把别家的码表当本家的字典**。厂商代际之间会变。
- **把 HTTP 200 当接受**。
- **把 helper 加载成功当 oracle**。
- **跨轮混字段**。消融必须在一轮内做。
- **多个变量同时改**。那样哪个面生效就说不清了。
- **把「线上代码不变」当成「结构不重要」** —— 恰恰相反，说明你读的路径不权威。

## 相关（Related）

- `./verifier-replay-playbook.md` —— 消融矩阵、共享基线、时序、验收阶梯的完整方法
- `./positive-sample-hygiene-playbook.md` —— Step 6 环境结论的前提
- `./troubleshooting-playbook.md` —— 「每打一个补丁码就变」的对应条目
- `./escalation-ladder-playbook.md` —— 六面都排除后该升到哪一级
- `./startup-triage-playbook.md` —— `verifier-gated` 家族判定
- `./symptom-heuristics.md` —— 「每次失败错误码都不一样」的口语症状
- `../state/challenge-artifact-harvest-playbook.md` —— 收获 verifier 产物的具体手法

---

## 源文档勘误与本机化改动

1. **源文档缺判据**。原文只有「怎么做」，没有「做到哪算完」。本文新增判据段（6 条 + 反例），其中第 2、3、5 条是把源文档正文里隐含的约束显式化。
2. **交叉引用路径失效**：源文档用 `verifier-replay-playbook.md`，而该文件实际就在 `references/triage/` 同级。原写法从 `references/triage/` 出发会指向不存在的 `verifier-replay-playbook.md`。已改为 `./verifier-replay-playbook.md`。
3. **`Step 5` 的编号不一致**：源文档 Step 5 标题为「Answer or behavior ablations」，而目录与正文其余部分均按「step N」引用。原文无实质错误，但「only after steps 1-4」这种写法在小节化后容易漏读，已加粗前置。
4. **「反 cargo-cult」的原词保留**。`cargo cult`（搬教条）是有信息量的表达，译为「反 cargo-cult 规则」并在首句补「不要把某厂商的码表提升成普遍教条」的原意。
5. **本机化**：本文方法论本身不绑定工具，无需替换。判据第 5 条「干净普通浏览器成功存在」在本机由 `playwright`（普通配置、无 hook）提供，已在「适用信号」与判据中点明。