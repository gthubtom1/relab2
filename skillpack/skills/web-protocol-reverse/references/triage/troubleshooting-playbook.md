# 故障排查手册（Troubleshooting Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `troubleshooting-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。
>
> **什么时候用**：重放逻辑**几乎能跑但就是还差一点**的时候 —— 不是「完全没头绪」（那是 `./startup-triage-playbook.md`），是「已经做了一堆但仍失败」。
>

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

---

## 适用信号（Recognition signals）

- 「脚本已经能跑了，但就是过不去」
- 「第一次能成，第二次就不行」
- 「浏览器里好好的，代码里就是不行」
- 「返回 200 但业务报错」
- 「改了 A 之后好了，但 B 又坏了」
- 「同一段代码，行为不确定」

## 前置（Entry conditions）

**你已经有了可重放的失败样本。** 没有失败样本就没有「排查」这一说 —— 先去 `./positive-sample-hygiene-playbook.md` 拿一条干净的成功样本 + 一条干净的失败样本。

要能重放，你至少需要：

```bash
# 干净基线落盘（失败样本 + 成功样本）
# mitmdump 实时录制
& (Resolve-ReverseToolSpec -Name 'mitmdump').Command --listen-port 8899 --save-stream-file flow.mitm
# 或 tshark 离线读已有 pcap
& (Resolve-ReverseToolSpec -Name 'tshark').Command -r flow.pcapng -Y "http.request" -T fields -e frame.number -e http.request.full_uri
```

---

## 步骤（Working method）

### 症状路由（Symptom routing）

#### `403` / `412` / `429`

- 比请求头
- 比 cookie
- 比请求节奏（pacing）
- 比签名新鲜度
- 比：被挑战的那个文档 URL，在**本地 bootstrap 之后**是否本身就能重放成功（而不是靠猜一个 API 跳转）
- 若失败**只在**装了 hook 或断点之后才出现 → 怀疑 observer effect（观察者效应），重抓一条干净基线
- 若同一实现在不同出口上时好时坏 → **在同一个出口上用浏览器验证同一路由**，再去改协议逻辑

#### `200` 但业务报错

- 比 query 与 body 的序列化
- 比时间戳精度
- 比传输 wrapper 的输出
- 比：是不是漏了一个 verifier 或 cookie 刷新步骤
- 若 subcode 每次尝试都在变 → **画一张阶梯**，不要把每次失败当成互不相关的噪声

#### `200` 但响应是乱码或一堆字符串

- 查解密路径
- 查字体（font）
- 查提示数组里有没有页面级的头线索
- 若原始字节能干净解出来、但存盘文件或终端输出仍乱 → **先把本地编码/渲染问题与目标端解码门分开**，再去改协议假设

#### 你选的登录或会话校验器「怎么验都过」

- **篡改一个决定性的 cookie / token / 会话字段，然后重跑校验器当负控（negative control）**
- 若篡改或清空之后仍返回 `200` 或页面外壳 → **那个端点是个假校验器**，不是登录证据
- 找一个「坏状态下会确定性失败」的强鉴权业务端点，在写 cookie 或会话产物之前先过它

#### 首次请求能成，重放失败

- 查轮转的 cookie
- 查内存里的刷新字段
- 查：是否每个请求前都必须跑一次 bootstrap
- **在怪 signer 之前先证明 cookie 溯源**
- 把首跳 HTML、链接的 bootstrap 资产、种子 cookie、生成状态**保持在同一条新会话链上**，然后才扩大环境补丁
- 若运行时外发（egress）暴露了完整出站 `Cookie` 头 → **拿它和 cookie jar 比**，再决定是不是某一个 cookie 名的刷新问题

#### 登录看着被接受了，但目标业务路由仍重定向或拒绝

- 把 grant ticket（授权票据）、redirect handle（重定向句柄）、异步后续 URL、auth ack 都当作**认证工件**，不是「会话已建立」的证明
- 抓 post-auth 回调、重定向交换、或**建立会话**的后续请求，然后才去改 signer
- **在每一跳 post-auth 前后 diff cookie 状态**，搞清楚到底是哪一步把可用会话变成了现实

#### 本地 helper 名字对上了，输出对不上

- 退回到固定输入比对
- **在证明它标准之前，一律假设它是打过补丁的**
- **活重放才是权威**；少抛异常、输出更像浏览器的样子，只是提示

#### 本地 helper 的失败看起来像「目标在拦我」

- **先查本地运行时完整性**：断链符号链接、从拷贝的 `node_modules` 带出来的占位链接文件、缺失的传递依赖、路径错误、编码导致的路径解析失败
- 在**冻结输入**上重跑 helper，把「helper 启动失败」和「协议失败」分开，再改 signer 假设
- 若 helper 连自己的依赖树都 load 不起来 → **先修本地运行时**，不要重开目标侧逆向

#### 干净抓包能成，插桩抓包失败

- 怀疑 observer effect
- 撤掉大范围全局 hook 和调试暂停
- 抓一对未被触碰的请求 / 响应
- 把插桩**向外**移到请求边界
- 优先用 initiator 栈和 diff，再考虑侵入式 monkey patch

#### 异步产物一直不出现，或无法对应到某一次尝试

- **先建立观察基线**：收件箱游标、webhook 接收器、队列偏移、或轮询窗口
- 基线在线之后**才**触发流程
- diff 触发前后的产物，让「尝试 → 产物」的对应关系显式化
- 把时序、游标状态、延迟投递当成**协议工作流的一部分**，不是运维噪声

#### 用户定义了延迟阈值或 honeypot（蜜罐）预算

- 若用户说某个请求或 helper 步骤超过 `N` 秒就该视为可疑 → **在采集器里编码成硬超时**
- 一旦越过阈值**立即中止**，不要静默重试掉
- 报告阈值在哪里强制生效，让交接反映真实的安全契约

#### 同一个请求在密集请求后降解成「密码错误」「字段错误」类提示

- 先让一个**已知能过**的请求充分冷却后重试，**不要**改那些已经匹配上的字段
- 比慢速与快速两种节奏下的失败文本 / subcode，而不只是比代码改动
- 当字段样错误**只在**重复尝试后出现时，怀疑惩罚性伪装或滥用冷却
- 目标对速率敏感时，优先 cookie 刷新或复用已有会话，而不是激进的重新登录循环

#### 访问间歇性被拒，或路由按出口重置

- **固定实现、会话形态和目标路由**，只改变网络出口或冷却时间
- **在同一个出口上用浏览器验证**该文档或业务路由，再去怪本地 signer / verifier / CSRF / 表单序列化
- 若浏览器和协议**都**在这个出口失败 → 把条件标为 `egress-gated`（出口受限），**换出口或等待**；**不要先重写算法**
- 若浏览器成功但协议失败 → 比传输身份一致性、sidecar 数量、cookie 迁移、以及精确的请求序列化
- **把最后一次成功输出单独保存**，不要让坏出口的诊断覆盖掉已验收的证据

#### 每打一个补丁，错误码 / subcode 就变一次

- **把变化序列当成证据** —— 说明一个门已经过了，下一个门暴露出来了
- 区分「同一个失败又来了」和「**进展之后**换了个失败」
- 在重写 signer / wrapper / bootstrap 之前，先更新「缺哪个门」的假设
- 用新代码决定下一步该查的是 cookie 溯源、会话准入、wrapper 槽位、verifier 状态、还是单纯的节奏退避

### 多上下文登录与激活（Multi-context login and activation）

#### 登录成功，但业务数据不对

- **租户、角色、数据范围三者分别确认**
- **重读最终身份**；不要停在切换接口的响应 envelope 上
- 见 `../state/multi-context-session-playbook.md`

#### 切换成功但作用域没变

- 把完整激活载荷与一份已知的 UI 抓取逐字节 diff
- 查是否有一个 type 字段必须与 value 字段**一起**发送
- **在身份重读与任务配置匹配之前，拒绝导出**

#### 密码正确但登录看着被拒

- 验证 RSA 或其他密码编码的**字母表与长度**
- 确认模数与指数是从**当前**登录页解析的
- 编码问题见 `../crypto/crypto-patterns.md`

#### 复用 cookie 抓到了别的店

- 采集前跑一次身份探针
- **不要让并发 worker 共用一个会话并来回切店铺/供应商**
- 重新激活 + 重新校验之后才开始采集

### 异步导出与报表下载（Async export and report download）

#### 创建返回 200，但没有新任务

- diff 方法、query vs body 位置、content-type、referer
- 确认 signer 的覆盖范围用的是**同一份序列化**
- 对创建前后的历史做快照
- 见 `../state/async-export-job-playbook.md`

#### 导出完成得太快，但日期或字段不对

- 查轮询是否复用了创建前的历史任务
- **必须**用「创建返回的 id」或「创建后新出现的 id + 条件匹配」

#### 下载回来的不是预期产物

- 查 body 是不是 JSON 报错、登录页、或挑战页
- 解析之前先验 magic bytes（魔数）或内容族
- 确认二次校验和旁路材料属于**本次**运行

#### 文件能解析但列不全

- 比对请求的字段数与下载文件的列数
- **失败即停（fail closed）**，不要落盘残缺结果
- 复查是不是创建时在序列化或签名阶段丢了字段数组

#### 旁路验证码一直失败

- 发送前先建立收件箱 / 消息游标基线
- **只接受基线之后**的消息
- 不要把登录场景的码和下载场景的码混用

### 验证器与样本卫生（Verifier and sample hygiene）

#### 验证器语义看着没问题，业务仍被拦

- 证明**同一轮内**第一个下游消费者的封装方式
- 查 grant 放在哪：query、cookie、header、body、还是成功别名
- **用内容指纹定义「业务通过」，不只看 HTTP 状态**
- 读 `./verifier-replay-playbook.md` 的「下游消费者契约」

#### sidecar 返回 200，但最终验证仍拒绝

- **区分传输成功与应用层确认**
- 在找轨迹之前，先跑 sidecar 消融矩阵
- 查共享基线与稀疏增量的一致性
- 读 `./verifier-error-localization-playbook.md`

#### 普通浏览器能过，自动化或协议过不了

- 给样本分级：clean-success（干净成功）对 contaminated-failure（被污染的失败）
- **在采集下一个正向 oracle（成功基准）之前，先撤掉 hook 与调试所有权**
- 把出口信誉与连续拒绝史当作环境风险
- 读 `./positive-sample-hygiene-playbook.md`

#### 每打一个本地补丁，拒绝码就变

- **把码的变化当成定位证据**，不是随机噪声
- 用单变量消融，把每个码映射到 结构 / sidecar / 一致性 / 时序 / 答案 / 环境 之一
- **不要把另一个任务的码表当成普遍真理**

#### 动态 helper 路径变了，输出坏了

- 先给资产做哈希并比对 helper 边界，再考虑完整重逆
- 重跑固定向量
- 之后才重建本地 helper 版本

---

## 判据（Completion criteria）

「排查完了」的标准（**全满足**才算）：

1. **症状归到了一节**，而不是「我瞎试了几招」
2. **每次改动只有一个变量**，且每一步都有可复核的证据
3. 若涉及 observer effect：已经**撤掉插桩重抓**，并证明干净基线能过
4. 若涉及「登录看着成功」：已经用**篡改后的负控**证明那个校验点是真校验点
5. 若涉及 `egress-gated`：已经**在同一出口上用浏览器验证过**，才下「出口受限」的结论
6. 若涉及错误码漂移：已经画出**单变量消融矩阵**，而不是靠感觉猜
7. **最后一跳成功被稳定复现了至少两次**（不是一次偶然成功）

判据的反例（**以下情况算没排查完**）：

- 「多试几次就成了」—— 不可复现等于没解决
- 「我同时改了 UA、headers、cookie 和签名」—— 无法归因
- 「浏览器里能跑」就认为问题在对方 —— 同一出口没验证过
- 拿一次偶发成功当结论
- 把已被坏出口污染的诊断，覆盖掉了已验收的成功证据

## 常见坑（Common traps）

- **同时改五样东西**。改一样，跑一次，记一次。
- **把 hook 造成的失败当成目标变难了**。
- **把 `200` 当成通过**。应用层成功 ≠ 业务成功。
- **把「篡改后仍通过」的端点当登录证据**。
- **在没做固定输入比对之前就改 signer**。
- **把短命交接票据存成长期 cookie**。
- **只重试不冷却**，在限速目标上把问题越搞越糟。
- **把错误码漂移当噪声**，于是永远在调 signer，而门其实在别处。
- **把本地 helper 的启动失败当成协议失败**。

## 相关（Related）

- `./startup-triage-playbook.md` —— 完全没头绪时先走这里，而不是这里
- `./symptom-heuristics.md` —— 症状到家族的快速匹配
- `./escalation-ladder-playbook.md` —— 排查多轮无果时该升级到哪一级
- `./verifier-replay-playbook.md` —— 验证门家族的完整重放方法
- `./verifier-error-localization-playbook.md` —— 错误码漂移的定位
- `./positive-sample-hygiene-playbook.md` —— 样本分级
- `./reproducible-evidence-playbook.md` —— 把成功/失败 transcript diff 成可审计证据
- `../state/multi-context-session-playbook.md` / `../state/async-export-job-playbook.md` / `../state/cookie-provenance-playbook.md`
- `../crypto/crypto-patterns.md` —— 密码编码与摘要平价

---

## 源文档勘误与本机化改动

1. **交叉引用路径失效**：源文档用 `references/xxx.md`，实际文件分散在 `references/{triage,state,crypto,deliver}/`。已全部改为实际相对路径。
2. **源文档空行造成的结构断裂**：源文档在 `## Multi-context login and activation`、`## Async export and report download`、`## Verifier and sample hygiene`、`## Final rule` 四节之间各有连续空行（最多 3 行），是上游文件的排版残留。已清理。
3. **`## Final rule` 原文只有一句**（`When stuck, route by symptom. Do not randomly mutate five things at once.`），且内容与「常见坑」重复。已把这句话提炼进判据段作为核心约束，删除空的 Final rule 节。
4. **补齐了源文档缺失的判据**。源文档**完全没有**验收标准 —— 全是「怎么做」，没有「做到哪算完」。本文新增判据段（7 条 + 反例）。
5. **「同出口浏览器验证」这条纪律在本机是可执行的**（`playwright` + `curl_cffi` 都能指定出口），已在判据中固化；源文档只提了一句，没进判据。
6. **本机化**：`tshark` / `mitmdump` 的落盘命令在「前置」给出完整路径；`curl_cffi` 作为「同出口浏览器验证」的手段点名。源文档正文不含具体工具调用，故无需替换工具名。
7. **保留未本地化的部分**：所有症状路由的具体排查项、负控方法、消融原则 —— 这是本文最有价值的部分，原样保留（译为中文）。