# 挑战产物摘取手册（Challenge Artifact Harvest Playbook）

> **来源声明**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `challenge-artifact-harvest-playbook.md`。英文原文译为中文，术语保留英文原词并附中文，按本包六段式规范重排。
>
> **什么时候用**：敌意运行时（hostile runtime）**已经在本地产出了决定性产物**，而任务是在不把方案退化成浏览器自动化的前提下把它摘出来。
>
> **平台与本机状态**：`playwright`、`node v24`、`python 3.12`、`mitmdump`、`curl_cffi`、`tshark 4.6.8` 本机可用。`iv8` 本机无；`reqable` 本机无（改用 mitmproxy / tshark）。

> ★★ **本机 playwright 必须显式指定浏览器**（2026-10-10 实测）：
> `launch()` 默认启动会报 `Executable doesn't exist at %LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1234\...`
> —— python 包期望 1234，本机装的是 **1243**，版本号对不上。
> **可用写法**：`p.chromium.launch(channel="msedge")`（实测能起、能渲染、能读 DOM），
> 或 `launch(executable_path=<显式路径>)`。照抄裸 `launch()` 一定失败。
> 
>
> **立场声明**：本文是**协议逆向与风控机制研究**方法论。目标是理解「服务端挑战如何产生状态、状态如何门控业务请求」，并把该状态**在授权前提下**建模成可复现的协议契约。本文**不涉及**绕过验证码、绕过风控或规避厂商检测手段；那属于未授权规避，不在本文范围。

---

## 适用信号（Route here when）

- bootstrap 或 challenge 脚本在初始化后暴露一个稳定的 getter（取值器）或对象方法
- 本地运行时自己发出了 XHR/fetch，带着真实的包装体、二进制载荷或决定性 header
- 浏览器或本地运行时**已经吐出**最终加密体或决定性 header 集，只是完整的离线重建还没做完
- 某个安全 SDK 全局 hook 了 `fetch` / XHR / 其他请求原语，**一次极小的合成请求**就能暴露它自动注入了哪些签名参数、cookie 或 header
- 后面开始冒出定时器错误或 DOM 错误，但**需要的产物可能早就已经存在**了
- 阻塞式 `vm` 执行会死锁，而 DOM 或脚本插入式执行保住了定时器、微任务或请求钩子
- 改代码生成（codegen）边界，比补齐几十个缺失 DOM API 更省事
- 顶层 SDK init 死在 axios / fetch / adapter 胶水 / 遥测上传 / 框架编排里，但**更低层的序列化器或 packer 仍可直接调用**

## 前置（Entry conditions）

1. **先做过上游判定**：已经确认 `../triage/startup-triage-playbook.md` 判定需要动态证据，而不是静态读码就能解决。
2. **本地执行宿主已就位**。本机现状：
   - `playwright`（本机可用）—— **保留定时器/微任务/请求钩子语义的执行路径**是本文首选。DOM 或脚本插入式执行优于阻塞式 `vm` 求值。
   - `node v24`（本机可用）—— 够跑只做纯计算的序列化器 / packer / signer。
   - `iv8` **本机无、未在本机验证**。若你已有该运行时，`../crypto/iv8-runtime-cheatsheet.md` 的形态可参考。
3. **一条成功样本 + 一次失败样本**，用于确认「摘到的产物确实是被业务请求接受的」。
4. **网络隔离意识**：本机 `mitmdump` 会接管出向流量。判据第 4、5 条要求证明「本地产物采集」时**不触碰线上站点**，需提前把本地宿主的出向请求 mock 掉。**绝不能让本地运行时代替采集器打真实业务 HTTP**。
5. **授权边界**：仅在有权访问的目标上做。

## 步骤（Steps）

### 核心思想

**在最近的那个稳定边界上恢复产物。**

当运行时已经比你想象的更便宜地产出决定性产物时，**优先「拦截转发」（intercept-and-forward）而不是完整重建**。这是本文全篇的取舍判断。

典型的稳定边界：

- 同步 init 之后暴露的一个 getter
- 发出的那个 XHR 或 fetch 调用
- 页面完整跑完之前就吐出的导航目标或重定向 URL
- 经由全局 hook 的传输原语发出的一次合成请求
- 失败外层门面之下的底层序列化器、签名器、packer 或导出函数
- 让完整挑战执行变得不必要的一条更干净的替代路径

### 默认产物优先级

多个边界同时可用时，按此顺序摘：

1. **导航目标或重定向 URL** —— 如果它已经带上了决定性的 query 或 path 状态
2. **拼装好的出站 `Cookie` 头或 cookie 字符串** —— 足以让 Python 重放的程度即可
3. 单个派生 cookie 值
4. 存储（storage）里的模块 —— 仅当后续重新生成仍依赖它时
5. 完整加密链重建

> **运行时已经吐出可重放的重定向 URL 时，停止补 DOM 平价（parity），把控制权交给 Python。**

### 业务 API 返回挑战 HTML 时

把「一个业务 JSON 路由回了挑战 HTML」当作**一等挑战路径**，而不是死端点：

1. 把 HTML 主体、外链 challenge 脚本、seed cookie **冻结在同一条会话链上**
2. 必要时用最小宿主本地执行
3. 摘取重定向 URL 和/或 cookie
4. 从 Python 重放，包括证据所要求的任何「原始 URL 回显字段」（original-URL echo field）

执行器细节路由到 `../crypto/local-challenge-executor-playbook.md`。
若同一字段还有一个短的离线签名候选，把写入方选择路由到 `../observe/dual-writer-param-playbook.md`。

### 快速执行路径

1. **先给产物路径分类**。选一个：
   - 暴露的 getter
   - 拦截到的 XHR / fetch 出向流量
   - 捕获的导航或重定向目标
   - 破损门面之下的底层原语
   - 替代路径绕过

2. **保住调度器语义（scheduler semantics）**。当定时器、微任务、生命周期或自发请求重要时，选能保住它们的执行路径 —— 这些场景下**优先 DOM / 脚本插入式执行，而非阻塞 `vm` 求值**。

3. **只打最小且忠实的补丁**。好的补丁目标：
   - 一次缺失的环境读取
   - 一个代码生成边界
   - 一个本地请求钩子
   - 一个窄的成功桩（stub）

4. **摘取产物**。示例：
   - getter 的返回值
   - 发出的请求体
   - 决定性 header
   - 出站 `Cookie` 头
   - 派生 cookie
   - 最终重定向 URL 或同路由重放 URL
   - 最终 token

5. **把控制权交回 Python**。让 Python 做真实 HTTP 重放、重试、解析与落盘。

6. **必要时用新鲜的 bootstrap 重试**。若 bundle 是版本随机化的，**重新获取 bootstrap 资产**，而不是假设某个打过补丁的脚本永远稳定。

### 高价值检查项

- 产物是否在嘈杂的定时器回调跑完**之前**就已存在？
- 运行时是否在后续 DOM/导航错误冒出来**之前**，就已发出可重放的导航目标？
- 运行时需要的是脚本插入 / 页面 bootstrap，而不是阻塞求值？
- 那个自发请求能否在**不触碰线上站点**的前提下本地捕获？
- 一次经钩子的极小合成请求，是否已经证明了签名器注入边界，只剩业务载荷建模留给本地代码？
- 一个已产出的最终请求体或 header 集，是否已足够让 Python 重放（从而内层加密平价对首次稳定交付变成可选）？
- 运行时对被挑战的文档路由，是否已经吐出完整可重放的 `Cookie` 头（从而逐个 cookie 逆向着法对首次稳定交付变成可选）？
- 运行时是否暴露了一个**线上线（wire-shaped）出向记录**，比 `document.cookie`、jar 快照或中间 helper 值**更权威**？
- 外层 SDK 路径是否只在传输适配器或遥测胶水里失败，而下层模块已暴露决定性的 blob 构造器？
- 运行时是否只需要一个极小的假成功响应就能继续推进？
- 一个可恢复的补丁是否应当**只捕获一个确切的错误类**，而让结构性失败继续上抛？

## 判据（Verification criteria / Minimal handoff notes）

以下 9 项**全部**要在交接说明里显式写出来：

1. **哪条产物路径胜出**：getter / egress / bypass
2. 是否**跳过了外层门面**，改用更底层原语
3. **哪些调度器假设起了关键作用**
4. **需要了哪个窄补丁**（如果有）
5. **本地摘出的具体产物是什么**
6. 该产物是**单个 cookie 值 / 拼装出的出站 `Cookie` 头 / token / 包装请求体**中的哪一种
7. 是否有一个**经全局 hook 传输原语的合成请求**暴露了签名器边界
8. **为什么在所选边界上「拦截转发」比完整重建更便宜或更安全**
9. **Python 在最终重放中如何消费了那个产物**

外加三条可执行判据：

10. **产物形状已经理解之后，挑战运行时不再是隐藏依赖** —— 最终路径里它必须能被替换或至少显式化
11. **本地执行期间没有发出真实业务 HTTP**（第 6 步里的「让 Python 打真实 HTTP」是唯一允许的出网点）
12. 摘到的产物经一次**下游业务 replay** 验证被接受（一个「看起来对」的重定向 URL 不算通过）

## 常见坑（Common traps）

- 某个 getter 已经返回产物了，还在试图跑完每一个定时器回调
- 运行时早已暴露可重放的重定向目标，还在继续补导航 / DOM 平价
- 去补每一个缺失的 DOM 洞，而不是**拦截那个出向请求**
- 在没证明全局 hook 的请求原语免费注入了什么之前，就去逆向整个签名器
- 运行时早已吐出可重放的最终请求体或决定性 header，还在重建每一层内层加密
- 在没检查运行时是否已暴露权威重放 `Cookie` 头之前，就去逆每一个 cookie 写入方
- 因为本地运行时随后报「navigation not implemented」或别的**产物之后**的通知，就把已经拿到的重定向目标丢掉
- 存储的 cookie 状态与观测到的出站 `Cookie` 头不一致时，信前者
- 外层 init 路径失败就放弃整条 SDK 路线，没检查下层是否有可用的序列化器 / packer
- 用 catch-all 式的错误吞噬，掩盖递归、栈溢出或状态损坏
- 让本地运行时代发真实业务 HTTP，而本意只需要本地变更证据
- 产物形态已经理解之后，还把挑战运行时留作隐藏依赖
- **在有授权的测试目标上**，为了「跑通」而对真实业务接口施加超出授权范围的请求压力

## 相关（Related）

- `challenge-state-envelope-playbook.md` —— 姊妹篇：挑战输出作为协议状态、信封族与七层证明
- `cookie-provenance-playbook.md` —— 第 7 类「helper 拼装出站 `Cookie` 头」写入方溯源
- `server-js-cookie-bootstrap-playbook.md` —— 挑战以可执行 JS 返回时的执行路径
- `../crypto/local-challenge-executor-playbook.md` —— 本地挑战执行宿主搭建
- `../crypto/environment-patch-playbook.md` —— 判据 4「最小补丁」的补丁规程
- `../crypto/env-diff-playbook.md` —— 宿主环境差分
- `../observe/hook-techniques.md` —— 判据 7「全局 hook 暴露签名器边界」的具体手法
- `../observe/dual-writer-param-playbook.md` —— 判据 8 中的写入方选择
- `../deliver/pure-python-rebuild-playbook.md` —— 判据 10「不再是隐藏依赖」的交付形态
- `../contract/report-templates.md` —— 9 项交接说明的落盘模板

---

## 源文档勘误（改编时修正）

1. **源文档 `Delivery guidance` 有一处张力**：它同时写「local runtime harvest step」和「Not: Python orchestrates a hidden browser replacement」。两者字面冲突 —— 本地运行时 harvest 本身就是一种浏览器替代。本文消解为：本地运行时 harvest 允许存在，但必须**显式**（判据第 10 条），且**Python 必须拥有出网与重放**（判据第 11 条）。禁止的是「隐式」替代。
2. **源文档 `Core idea` 的 `Typical stable boundaries` 列表里，第 6 项「a cleaner alternate route that makes full challenge execution unnecessary」与其余 5 项性质不同** —— 前 5 项是「在哪一层拦截」，第 6 项是「换一条路」。混列容易让读者以为存在第 6 个「边界」。本文在「核心思想」段落中保留了原顺序但把第 6 项的换路性质用「替代路径」一词明确区分（并在快速执行路径第 1 步的分类里单列为 `alternate-route bypass`）。
3. **源文档通篇为「hostile runtime」框架**，但未给出授权边界声明。本文补了立场声明段，明确本文属协议研究方法论、不覆盖绕过验证码/风控的部分。
4. **源文档无独立 Verification 章节**，「Minimal handoff notes」9 条同时充当验收标准。本文保留这 9 条并补 3 条可执行判据（其中第 12 条「下游 replay 验证」是原文隐含但未写出的关键 —— 一个重定向 URL 被本地接受，不等于业务侧接受它）。