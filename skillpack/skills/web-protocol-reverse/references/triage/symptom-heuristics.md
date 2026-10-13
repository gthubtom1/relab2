# 症状启发式对照表（Symptom Heuristics）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `symptom-heuristics.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。**改编要点：源文档的 80 条信号全部写成技术术语，AI 检索时人话描述对不上。本文把每一组改写成「用户/运维会怎么说」的话，再给出可能原因与下一步。**
>
> **什么时候用**：目标还新鲜、症状还很宽、或者在挑更具体的手册之前需要一个快速家族匹配时。这张表是**路由用**的，不是判定用的 —— 命中不等于确诊。
>

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 

---

## 适用信号（Recognition signals）

- 用户描述了一个现象，你不知道该开哪本手册
- 症状模糊（「就是不行」「就是过不去」），需要先缩小范围
- 同一段代码在 A 站能跑、B 站不行
- 手工浏览器能跑，脚本不行（或反过来）

## 前置（Entry conditions）

- **没有前置**。这张表就是用来在什么都不知道的时候起手的。
- 但用它做粗筛之后，**必须**接着走 `./startup-triage-playbook.md` 固化家族判定 —— 命中两三条不等于确诊家族。

---

## 步骤（Working method）

**读法**：先在「用户会这么说」列找到用户原话或近似表述，再读「可能原因」和「下一步」。跳着查，不要从上往下通读。

### 一、页面看着正常但数据不出来

| 用户会这么说 | 可能原因 | 下一步 |
|---|---|---|
| 「页面一直转圈，最后什么都不显示」 | 页面是 SSR 外壳或加载壳，真正数据走另一个 API，且 hydration 包是空的 | 抓 wire，看有没有二次 XHR；别只看 HTML |
| 「HTML 返回 200，页面是空的」 | 同上，业务数据在后续 API 上 | 同上 |
| 「接口返回 `ok`/`success`，但 `data` 是空的」 | 应用层成功 ≠ 业务成功；可能有 subcode（子码）在说拒绝 | 读 subcode，别看 HTTP 状态 |
| 「列表接口能匿名调，详情/提交接口不行」 | 权限边界不只在列表层 | 找一个能确定性失败的强鉴权端点做负控 |
| 「首页能开，但导出的数据是别家店的」 | 登录态通了，但租户/店铺/组织上下文没切 | 读最终身份重读（identity reread），别停在切换接口的响应 |
| 「切了店铺还是老数据，接口返回 200」 | 上下文切换只是回执，最终身份需要重读 | 同上；见 `../state/multi-context-session-playbook.md` |
| 「创建/导出接口返回 200，但历史里没多出新任务」 | 请求成功但没落库，或方法/参数位置错了 | diff 方法、query vs body、content-type、referer；见 `../state/async-export-job-playbook.md` |
| 「轮询一下就看到一个成功任务，但时间范围不对」 | 轮询捡到了旧的历史任务 | 必须用创建返回的 id，或要求「新建 id + 条件匹配」 |
| 「文件下载下来了，列数比要的少」 | 字段数组在序列化或签名阶段被丢了 | 先核对请求的字段数，再解析文件 |
| 「筛选条件留空，回显的却不是那个 tab」 | 页面在发请求前注入了分类/模式状态 | 抓真实的出站 query，别照抄 UI |

### 二、参数、token、签名相关

| 用户会这么说 | 可能原因 | 下一步 |
|---|---|---|
| 「同一个字段名，有时特别短，有时特别长」 | 同一个字段有**两个写入方**（dual writer） | 比成功样本的 wire 形态，别急着写生成器；见 `../observe/dual-writer-param-playbook.md` |
| 「辅助函数叫 `sm3`，但跟标准库算出来的不一样」 | 固定样本没过，可能是魔改常量或环境分支选常量 | 用固定向量（fixed vectors）比对；见 `../crypto/crypto-patterns.md` |
| 「只有部分页面的 Python 结果和服务端不一致」 | uint32 边界 bug，例如 `ROTL(x, 0)` 写错 | 拿单页固定向量单独验证 |
| 「`md5`/`btoa`/`atob`/`sha1` 算出来的东西不像标准值」 | 魔改算法或编码变体 | 比对固定输入输出，别信函数名 |
| 「GET 重放总失败，但参数看着是对的」 | query 顺序、空字段保留、URL 编码与前端签名前的输入不一致 | 逐字节比对签名前字符串 |
| 「body 用库自带的 dict/JSON 发就失败，照抄前端的字节就能过」 | 序列化字节必须完全一致 | 抓原始字节，别自己构造 |
| 「方法、content-type 或 body 位置一改，签名错误就消失」 | signer 的输入集合和实际发送的不一致 | 让 signer 覆盖同一份序列化 |
| 「RSA 登录一直提示密码错误，其实密码是对的」 | 密文编码长度或字母表不对；模数/指数可能取自旧页面 | 查编码字母表与长度，确认公钥来自当前登录页 |
| 「重新生成/重试能过，但第一次创建就是不行」 | 首次请求缺一次性状态 | 查首请求必须的前置 |
| 「同一个请求第一次成功，之后就死，除非刷新某个隐藏状态」 | 轮转状态未刷新 | 找刷新路径，别硬重试 |

### 三、传输层被挡（还没到业务）

| 用户会这么说 | 可能原因 | 下一步 |
|---|---|---|
| 「`requests` 一发就断，浏览器能开」 | H2 reset / TLS EOF / 握手超时 / 早期断连 —— **传输准入**问题 | 先跑准入矩阵，别去改签名算法；用 `curl_cffi` 试 impersonation |
| 「换个 UA 或换 HTTP/1.1 就能过」 | 传输准入 | 同上；见 `../observe/transport-pre-gate-playbook.md` |
| 「落地页打不开，但同族的登录接口能直接调」 | 路由局部准入；被挑战的只是落地路由 | 别把落地路由的头改法推广到全链路 |
| 「同一个请求，出口 IP 一换就失败」 | 出口（egress）风险 | 浏览器和协议都试同一出口；都失败就是 `egress-gated`，换出口或等 |
| 「请求很快，但偶尔能成」 | 一次性 token、会话刷新、并发耦合 | 逐项排查 |

### 四、验证门 / 验证码

| 用户会这么说 | 可能原因 | 下一步 |
|---|---|---|
| 「点完验证码接口说成功，但业务请求还是被拦」 | verifier 成功只是中间里程碑；缺 sidecar（旁路请求）或缺时序 | 见 `./verifier-replay-playbook.md` |
| 「接口直接返回一大坨 HTML 挑战页，不是 JSON」 | challenge 状态在业务路由上做 bootstrap | 按 HTML 挑战处理，摘 cookie / 重定向；见 `../state/challenge-artifact-harvest-playbook.md` |
| 「验证码 challenge 返回的 token/图片链接/回调 id 换一轮就失效」 | 一次性、绑轮次 | 禁止跨轮复用 |
| 「本地 helper 跑出来的结果比浏览器的短很多、也重复很多」 | 宿主语义不足，helper 只覆盖了部分路径 | 逐项补宿主面；见 `./escalation-ladder-playbook.md` |
| 「加了滑块验证后，页面偶尔开始失败」 | 风险评分：出口、连续拒绝、注入式 hook | 先分级样本；见 `./positive-sample-hygiene-playbook.md` |
| 「普通浏览器能过，自动化一过就挂」 | 自动化环境被识别 | 同上；先量环境，别调轨迹 |
| 「每次失败返回的错误码都不一样」 | 错误码变化是**定位证据**，不是随机噪声 | 做单变量消融；见 `./verifier-error-localization-playbook.md` |
| 「第一次请求能过，重放同样的不行」 | challenge 状态或 cookie 未在同一会话链上续上 | 保持整条会话链 |
| 「OCR 找到点了，提交还是错」 | 坐标空间搞混了（还原图坐标 / 显示坐标 / 提交坐标） | 见 `./verifier-replay-playbook.md` 的答案路径拆分 |

### 五、验证码 / 风控请求的形态

| 用户会这么说 | 可能原因 | 下一步 |
|---|---|---|
| 「prehandle 返回一堆 challenge 配置，看着像是直接转发过来的」 | 客户端只是中继，不自己推导 | 先照抄透传，把 challenge 当协议的一部分建模；见 `../state/challenge-state-envelope-playbook.md` |
| 「先下几张图，再报答案，才能过」 | 图像派生的验证分支 | 按分支处理；见 `./verifier-replay-playbook.md` |
| 「提示图和背景图是分开的两张」 | 点击顺序由提示图定义，命中几何由背景图定义 | 分别处理，不要混成一张图 |
| 「查设备指纹那条是 200，但最终验证还是拒」 | sidecar 传输成功 ≠ 应用层接受 | 跑 sidecar 消融矩阵 |
| 「我在页面里看到 `Object.keys(window)` / `document.all` 这类检查」 | 环境探针链，判的是「像不像真浏览器」 | 别大面积打补丁，按 Rung 5 逐项补 |
| 「脚本里用了 `canvas` / WebGL / `getComputedStyle`」 | 同上 | 同上 |
| 「改 UA 大版本号或定时器模式，引导顺序就变了」 | 环境差异影响 bootstrap 顺序 | 先固定环境，别让它乱动 |
| 「初始化后有一个同步的 getter 能拿到值，但定时器回调一调就报错」 | 有可利用的同步边界 | 见 `../state/challenge-artifact-harvest-playbook.md`，不要继续暴力补 DOM |

### 六、会话 / 状态 / 上下文

| 用户会这么说 | 可能原因 | 下一步 |
|---|---|---|
| 「登录接口返回 200，但业务接口还重定向到登录」 | grant ticket、redirect handle 只是**交接件**，不是完成的会话 | 抓 post-auth 回调与后续交换；每跳 diff cookie；见 `../state/cookie-provenance-playbook.md` |
| 「登录能拿到 grant，但后面的业务路由还是拒」 | 缺后置会话交换 | 同上 |
| 「复用了旧 cookie，过一阵就失效」 | 短命交接票据被当成持久 cookie 存了 | 只存长期凭据 |
| 「心跳/重连一乱，后续帧就全错」 | 会话有序性（order）是协议的一部分 | 冻结完整成功 transcript，先理清握手/保活/业务帧 |
| 「媒体元数据能拿到，文件下载要另一个密钥」 | 解密密钥是前序流量派生的 | 先复现派生链 |
| 「只有最后一个页面/最后一页过不去」 | 翻页到某个点切了分页端点或路由族 | 见 `../observe/pagination-route-pivot-playbook.md` |
| 「相对路径的接口只有解析到入口 origin 才对，硬编码同级 host 就 CSRF」 | origin 解析错 | 用有效入口 origin 解析 |
| 「页面说已经登录，但 wire 上没带 cookie 也照样返回全量数据」 | 文案与实际鉴权脱节 | 别按文案判断信任 |
| 「保存的登录 cookie 用久了就失效」 | 过期或交接票据被误持久化 | 见 `../state/session-contract-playbook.md` |

### 七、响应读不懂

| 用户会这么说 | 可能原因 | 下一步 |
|---|---|---|
| 「接口返回的是乱码/一串没意义的字符」 | 多层编码、压缩、protobuf、msgpack、自定义字体 | 先冻结原始字节，再找第一个消费者；见 `../deliver/response-decode-playbook.md` |
| 「返回的是字形/字体/提示表，不是数字」 | glyph mapping（字形映射）解码 | 同上 |
| 「URL 参数、body、响应、cookie 长得像同一套包」 | 同一 packet family（报文族）不同字段变体 | 逐字段对齐；见 `../observe/structured-transport-playbook.md` |
| 「原始字节解出来是对的，但保存的文件还是乱的」 | 本地编码/渲染问题，不是目标端问题 | 先分开排查，别改协议假设 |
| 「body 用固定 XOR 或 hex 或 base64 就能解，但外层还有个签名过不去」 | 解码便宜，签名贵 —— 痛点在签名 | 先攻签名，别在解码上耗 |

### 八、异步、副作用与外部通道

| 用户会这么说 | 可能原因 | 下一步 |
|---|---|---|
| 「点了之后什么也没发生，过一会儿才有结果」 | 异步副作用，结果走邮件/短信/webhook/队列/延迟回调 | 先建观察基线（收件箱游标、轮询窗口），再触发；见 `../state/challenge-artifact-harvest-playbook.md` |
| 「验证码短信码一直输错」 | 场景不同码长不同，或用错了场景的码 | 基线后只收基线之后的码，别混场景 |
| 「快速连打之后开始返回一堆像密码错误的提示」 | 惩罚性伪装 / 冷却 | 冷却后重试同一个已知能过的请求，先对比错误文本，别改字段 |
| 「导出接口限速很凶」 | 站点限敏感 | 优先复用 cookie 或已有会话，别做反复重新登录循环 |
| 「有一个监控脚本或 `.wasm`，看着跟业务无关，但去掉就签名不对」 | 旁路小资产在播种签名状态 | 见 `../state/side-asset-bootstrap-playbook.md` |
| 「页面里有个内联 `onclick` 或模板字符串里藏着接口地址」 | DOM 解析出来的值和原始源码不一致（实体转义 / 老式标记） | 直接读原始源码，别信 DOM 解析结果 |

### 九、环境/探针类散点

这些单独列，因为它们本身不是症状而是「读代码时的可疑标记」：

- 代码里分支依赖 `Object.keys(window)`、`Reflect.ownKeys`、`getOwnPropertyDescriptor`、`Function.prototype.toString`、`JSON.stringify`、`document.all`
- 运行时在决定性字段出现前摸过 `canvas`、WebGL、`getComputedStyle`、布局度量
- 混淆器的字符串表重写本身没效果，得先展开成员映射对象、规范化十六进制 key
- 顶层 SDK 初始化在 axios / fetch / adapter 里挂了，但更小的内部导出或序列化器仍能返回你要的那类 blob

---

## 判据（Completion criteria）

这张表用完时，「用完」的标准是：

1. **你已经把用户的原话映射到了一条症状行**，并抄下了对应的家族候选
2. **你至少跑了 2 个证据面去互证**候选家族，不是只凭一条症状就下结论
3. **如果症状不匹配表中任何一行**：按「通用兜底」走 —— 先抓一条干净基线，再走 `./startup-triage-playbook.md` 的四问，不要硬套某个家族
4. **如果症状落在「传输层」组**：你在改签名算法**之前**已经有了一张准入矩阵，或者明确记录了「尚未做准入矩阵」
5. **如果症状落在「验证门」组**：你在动 hook 之前已经有了一条未插桩的干净基线

判据的反例（**以下情况算没做完**）：

- 只凭「接口返回 200」就认为没问题
- 只凭「浏览器能过」就认为协议也能过（或者反过来）
- 拿 `contaminated-failure`（被污染的失败）当算法错误的证据
- 命中「请求很快但偶尔能成」就反复重试，不去查一次性 token

## 常见坑（Common traps）

- **把「命中症状」当成「确诊家族」**。这张表是路由器，不是判决书。
- **症状描述全是技术术语**，用户说的是「页面卡在转圈」「一直报签名错误」。用本文的话去匹配，别用源文档的术语去匹配。
- **跳过传输准入直接改签名算法**。最难缠的一类问题往往在 TLS 层。
- **把应用层 `success` 当业务通过**。要看内容指纹、看下游消费者。
- **拿自动化失败当轨迹算法错的证据**。先分级样本。
- **同一段症状反复出现但家族判定从未升级**。连续两次「按家族走完仍失败」就应该换层，见 `./escalation-ladder-playbook.md`。

## 相关（Related）

- `./startup-triage-playbook.md` —— 家族分诊与交付形态的正式判定
- `./tool-playbook.md` —— 症状落到本机具体工具
- `./troubleshooting-playbook.md` —— 已经做完但仍失败时的症状路由（含 403/412/429、导出、登录等）
- `./escalation-ladder-playbook.md` —— 什么时候该升级到重运行时
- `./verifier-replay-playbook.md` / `./verifier-error-localization-playbook.md` —— 验证门家族
- `./positive-sample-hygiene-playbook.md` —— 拿到样本先分级
- `../observe/dual-writer-param-playbook.md` —— 「同一参数有时短有时长」
- `../observe/transport-pre-gate-playbook.md` —— 「浏览器能开 requests 不行」
- `../observe/pagination-route-pivot-playbook.md` —— 「只有最后一页过不去」

---

## 源文档勘误与本机化改动

1. **最大的问题：症状全用技术术语写成**。源文档 80 条 bullet 大量使用 `payload`、`envelope`、`sidecar`、`verifier`、`hydration blob`、`glyph mapping`、`prehandle`、`seed`、`delta` 等词，用户和运维不会这样说，AI 用自然语言提问时检索不到。**本文全部改写为「用户会这么说」的口语化描述**，技术术语保留在「可能原因」列以保证中英文双向命中。
2. **结构缺失**：源文档把 ~80 条症状堆在一个无序列表里，中途还有一个孤立的空行（第 65 行）把列表切成两段（前半段与后半段主题不同但无任何说明）。已按主题归为九组，每组有明确标题。
3. **交叉引用路径失效**：源文档用 `references/xxx.md`，实际文件分散在 `references/{triage,observe,crypto,state,deliver}/`。已改为实际相对路径。
4. **遗漏了一条自己的目录锚点**：源文档末尾引用 `../observe/dual-writer-param-playbook.md`，而该文件实际在 `references/observe/`。已修正。
5. **没有家族映射**：源文档只列症状，不说命中后该归哪个家族、更没给下一步动作。本文每一组都给了「下一步」列，指向本包内对应手册或本机工具。
6. **未本地化风险已规避**：源文档症状表本身不含工具调用，因此无需替换工具；但若按症状行动时会落到 `iv8` / `reqable`，本文的「下一步」列一律指向本机路线（`playwright` / `frida` / `mitmdump` / `tshark` / `node` / `curl_cffi`）。
7. **保留了源文档的通用性**：症状按**模式**而非按站点写，站点/参数名不同时方法论仍然适用 —— 这是源文档的核心价值，未削减。