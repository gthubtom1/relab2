# 正样本卫生手册（Positive Sample Hygiene Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `positive-sample-hygiene-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。
>
> **什么时候用**：验证门恢复需要人工或浏览器的正向基准（oracle）时 —— 尤其是行为敏感的滑块、点击顺序、或被风险评分的 transcript。**一句话**：在你准备调轨迹之前，先看这一篇。
>
> **平台与本机状态**：Windows 10 x64。`playwright`、`frida`、`mitmdump`（`D:\EXE\python\Scripts\mitmdump.EXE`）、`tshark`（`D:\Tools\Wireshark\tshark.exe`）、`curl_cffi` 本机可用。**本文的核心纪律是「别用自动化去采正向基准」** —— 也就是说 `playwright` 在本文里的角色是**反面教材兼最后的退路**，不是推荐工具。

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

---

## 适用信号（Recognition signals）

- 你需要一条「人做过、且成功了」的 verifier 样本
- 「普通浏览器能过，但我的自动化一过就挂」
- 你正准备拿自动化采集的成功样本当调参基准
- 你在一条新出口 / 新 profile 上连续被拒
- 手上只有失败样本，且失败样本是插着 hook 采的

## 前置（Entry conditions）

- 你已经明确知道**缺的是哪一条样本**。本文明确反对「先要一堆再慢慢看」—— 只要缺的那一条。
- 有地方存任务局部产物：建议 `js_reverse_cache/tasks/<task-id>/`，见 `../contract/project-artifact-contract.md`。

---

## 步骤（Working method）

**浏览器工具只用于取证。最终交付仍然是无浏览器依赖的。**

### 为什么卫生很重要（Why hygiene matters）

**一个真实的人工动作，在自动化拥有的浏览器里，照样会失败。**

常见污染源（contaminants）：

- CDP 或远程调试的**所有权**（ownership）—— 只要开着调试端口就算
- 侵入式 hook —— 全局函数补丁、`toString` 拦截器
- 全新空 profile，没有任何普通浏览历史
- 同一个出口 IP 上的连续拒绝史
- 一次导出的抓包里混了多轮

> **被污染的失败，作为「环境证据」有用；作为「答案或轨迹算法错了」的证据，它很弱。**

### 样本等级（Sample grades）

给每一个 oracle（正向基准）打标签：

| 等级 | 含义 | 权威性 |
|---|---|---|
| `clean-success` | 普通浏览器或未插桩路径，verifier 被接受，下游消费者也过了 | **最高正向 oracle** |
| `clean-failure` | 普通路径、**无自动化所有权**，仍然失败 | 协议或风险策略的**强负控** |
| `contaminated-failure` | 涉及自动化、hook、调试端口、或被毒化的 profile | **先当环境证据** |
| `partial` | 缺 sidecar、缺 verify body、或缺下游消费者 | 不完整，不要过度解读 |

> **没有干净对照样本之前，绝不把 `contaminated-failure` 提升为「轨迹族被拒」。**

### 采样优先级（Capture preference order）

从最好到最差（作为正向 oracle 时）：

1. **用户或运维的日常浏览器**，无自动化附着，导出 HAR 或精确的 verify 与消费者请求
2. **未插桩的浏览器只听不注入**的抓包（listen-only capture，不注入页面 hook）
3. **只用来打开页面的自动化浏览器**，完全没 hook；**只有在干净普通抓包不可能时才接受**
4. **插了 hook 的自动化抓包** —— 只用于发现 initiator 和字段，**不是最终的正向真相**

> 若运维在普通浏览器里也失败：**在证明相反之前，按环境风险处理。**

### 协作采样规程（Collaborative capture protocol）

协议重放卡住、需要一条干净成功样本时：

1. **明确说出**运维应该操作哪些 URL、做哪些动作
2. **优先用运维的日常浏览器**，而不是任何 agent 拥有的 profile
3. 请对方导出**完整 verifier 轮次 + 第一条成功业务响应**的 Network 导出
4. 若用实时监听，**先关掉侵入式 hook**
5. 抓包存到任务缓存，**立刻分级**
6. 聊天里只报脱敏结论；**原始 token 留在任务本地**

> **只要缺的那一条样本。不要布置家庭作业。**

### 一条可用成功样本的最低字段

- 带耗时偏移的**有序请求列表**
- init/load 的响应族
- 必需的 sidecar 请求**及其应用层确认**
- 最终 verify 请求与语义成功 body
- 答案或轨迹载荷（若行为敏感）
- **第一个下游消费者**请求与业务通过 body
- 涉及动态脚本时的，生效 helper / 资产哈希
- 环境备注：普通还是自动化、hook 开还是关、出口有没有换

### 怎么用这些样本

- **先**把 `clean-success` 与协议重放做 diff
- 用 `contaminated-failure` **避免**得出错误算法结论
- 尽量**只**从干净成功的边界重建固定向量
- **若只有被污染的样本**：明说，并限制结论范围

---

## 判据（Completion criteria）

1. **每一条 oracle 都打了等级**（`clean-success` / `clean-failure` / `contaminated-failure` / `partial`），且报告里写明了等级
2. **至少有一条 `clean-success`**；若没有，报告里明确写「没有干净正向样本，结论受限」
3. **从 `clean-success` 重建的固定向量**已落盘并可复跑
4. **「环境风险」结论只在有 `clean-failure` 或干净浏览器对照的前提下才下**
5. **最终采集器仍然是无浏览器自动化重放** —— 本篇没有引入任何浏览器依赖
6. **原始 token 与敏感值留在任务本地**，聊天/报告只出现脱敏结论

判据的反例（**以下情况算没做完**）：

- 拿 `contaminated-failure` 当成「轨迹算法错了」的证据
- 把一次 hook 采集当成最终正向真相
- 把 A 轮的 grant 混进 B 轮的失败样本
- 只报告「有样本」，没报告样本等级
- 因为「采样本方便」就在**唯一一条正向路径**上注入了广泛 hook

## 常见坑（Common traps）

- **拿自动化手动滑动的失败当轨迹真相**。自动化环境本身就是变量。
- **为了「让抓包更容易」在唯一正向路径上打 hook**。污染的就是唯一的基准。
- **把成功轮的 grant 混进后面的失败轮**。
- **样本没有下游消费者也叫它完整**。
- **一口气要一堆样本**。只要缺的那一条。
- **报告里写「有干净样本」却不写等级**。
- **把卫生纪律和「要多试几种浏览器」混为一谈**。本文讲的是样本可信度，不是工具多样性。

## 相关（Related）

- `./verifier-replay-playbook.md` —— 把 verifier 复现为有序协议 transcript
- `./verifier-error-localization-playbook.md` —— Step 6 的环境面结论依赖本篇的分级
- `./troubleshooting-playbook.md` —— 「普通浏览器能过，自动化/协议过不了」条目
- `./symptom-heuristics.md` —— 「普通浏览器能过，自动化一过就挂」的口语症状
- `./reproducible-evidence-playbook.md` —— 把样本规范化成可审计、无秘密的证据包
- `./escalation-ladder-playbook.md` —— 本篇不改变升级阶梯；`playwright` 永远只在取证阶段
- `../contract/project-artifact-contract.md` —— 产物落在哪、命名约定

---

## 源文档勘误与本机化改动

1. **源文档缺判据**。原文有「Sample grades」和「How to use samples」，但没有明确的「做到哪算完成」。本文新增判据段（6 条 + 反例），其中第 1、2 条是把源文档隐含要求显式化。
2. **`## Delivery notes` 原文只有四项，措辞松散**（`Report:` 后跟 4 条 bullet）。已整合进判据段与「相关」段。
3. **交叉引用失效**：源文档引用 `positive-sample-hygiene-playbook.md`（自指，无意义）。已改为指向本篇真正的邻接手册。
4. **「协作采样规程」的第 6 条原文措辞断裂**（`redacted chat reports; raw tokens stay task-local` 缺主语动词）。已补全为「聊天里只报脱敏结论；原始 token 留在任务本地」。
5. **本机化说明**：本文**刻意没有**给出任何本机命令。原因：本文的核心纪律是「别用自动化采正向基准」，而本机可用的浏览器工具（`playwright`）恰恰属于要受限使用的那一类；给命令会误导读者把它当常规手段。「相关」段中已注明 `playwright` 只在取证阶段出现。
6. **保留未本地化的部分**：污染源清单、四级样本表、采样优先级四档、协作采样六步、最低字段清单 —— 这些是本文全部价值所在，原样保留（译为中文）。