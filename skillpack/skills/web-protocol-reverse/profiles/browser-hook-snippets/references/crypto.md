# 加密 Hook 选点（Crypto Hook Selection）

> **来源**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `crypto.md`。
> **用途**：决定观察 WebCrypto / CryptoJS / 随机数 / 编码时的 Hook 点与记录边界。
> **前置**：无 npm 依赖，Hook 为纯 JS。上游 `../scripts/crypto_api.js` **本包未落地**。
> **用法**：WebCrypto、CryptoJS 和随机数的可执行实现**统一使用** `../scripts/crypto_api.js`。该脚本记录 method、algorithm、输入/输出类型与长度，具有事件上限和恢复函数，**不输出 key、明文、签名或随机字节**。

## WebCrypto

按 `CONFIG.subtleMethods` **只开启目标方法**。

- `digest`、`sign`、`encrypt`、`decrypt` 的参数位置各不相同，所以**只记录算法摘要 + 末尾 buffer 的类型/长度**。
- Promise 的 resolve / reject 语义必须保持不变 —— 改掉就等于改掉了目标的行为。

## CryptoJS

**只 Hook 已存在且证据相关的方法。**

- 输入和结果只记类型/长度。
- **不要隐式调用可能有副作用的自定义 serializer。**
- 恢复时**仅在属性仍指向本 Hook 时**写回原函数（避免覆盖掉页面自己后装的 polyfill）。

## 随机数

`getRandomValues` 默认**只记录 typed array 的类型和长度**。

完整随机字节会改变秘密边界 —— 它本身就是签名材料的一部分，打出来等于泄漏。不作为默认日志。

## 编码（Encoding）

需要观察 `atob`、`btoa`、`TextEncoder` 或 `TextDecoder` 时，在**任务工程**里按 `crypto_api.js` 的 `registry` / `emit` / `restore` 结构增加一个窄 Hook：

- 过滤调用栈或长度
- 字符串和 buffer **都只给类型/长度**

**不得复制全值日志片段。**

## 转交

用户要的是算法入口、脚本 URL 或完整调用链时，停止扩写 Hook，按 `../index.md`「触发边界」表的 capability-aware 契约转交（`../../../../js-reverse/SKILL.md`）；专用技能不可用时返回 Spider core loop。

要在本地执行已知入口时，转 `../../env-patch/index.md`。

## 观察之后

拿到"某处调了 `crypto.subtle.digest('SHA-256', 32 字节)`"这类证据之后，真正的下一步是**把算法移植成纯 Python**，并在固定向量上验证 —— 而不是继续在浏览器里观察。见 `../../../references/crypto/crypto-patterns.md`（被魔改的标准摘要、uint32 端口）与 `../../../references/deliver/pure-python-rebuild-playbook.md`。

⚠️ 常见坑：看到算法名是 `SHA-256` 就直接信任标准库。被魔改的摘要（改常量、换轮数、改截断）外观完全一样，只有固定输入能分辨。见 `../../../SKILL.md` 的「常见坑」。

## 本包实况

上游 `../scripts/crypto_api.js` 未随包落地。要生成 crypto Hook：

- 从上游 MIT 仓库取基准实现，或
- 按 `network.md` 描述的 filter → cap → registry → restore 四段结构自行实现

输出格式参照 `hook-output-samples.md`。

## 相关

- `../index.md` — profile 入口与判据
- `runtime.md` — 动态执行与 Blob/Worker
- `hook-output-samples.md` — 输出契约
- `../../../references/crypto/crypto-patterns.md` — 摘要算法识别与 Python 移植