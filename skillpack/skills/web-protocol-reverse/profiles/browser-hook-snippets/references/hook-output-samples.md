# Hook 输出契约（Hook Output Contracts）

> **来源**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `hook-output-samples.md`。原文英文段落已中文化，**输出样例一字不改**（它们是格式契约）。
> **用途**：规定 Hook 日志的**元数据契约**。
> **前置**：无 npm 依赖。这些是**格式规范**，不是可直接运行的脚本。

⚠️ **这些是 metadata contract（元数据契约），不是"恢复现场值"的目标。** URL 必须去掉 query/hash；Cookie、header、storage、body、crypto 和 canvas 内容**默认只记录类型/长度**。

## XHR 与 Fetch

```text
[spider-xhr-send] {"target":"xhr","event":"send","method":"POST","url":"https://api.example.com/data","headers":[{"name":"x-sign","valueLength":184}],"bodyType":"ArrayBuffer","bodyLength":128}
[spider-xhr-response] {"target":"xhr","event":"response","method":"POST","url":"https://api.example.com/data","status":200,"responseType":"arraybuffer","responseLength":512}
[spider-fetch-send] {"target":"fetch","event":"send","method":"POST","url":"/api/login","headers":[{"name":"authorization","valueLength":220}],"bodyType":"string","bodyLength":96}
```

**绝不打印**原始 query 参数、header 值、请求体、响应体或 `Set-Cookie` 值。只有在 `CONFIG.logStack` 打开时，才允许跟随一条 stack。

## Cookie 与 Storage

```text
[spider-cookie-set] {"name":"session-token","valueLength":192}
[spider-storage] {"target":"localStorage","event":"set","key":"auth-token","valueLength":384}
```

Cookie 属性与 storage 值保持隐藏。

⚠️ `document.cookie` 观察**只是 JS 源码层面的证据**；HTTP `Set-Cookie` 仍然需要 Network（网络面板）来源证明。两者不可混为一谈。

## 加密

```text
[spider-webcrypto] {"method":"digest","algorithm":"SHA-256","inputType":"ArrayBuffer","inputLength":32}
[spider-webcrypto-result] {"method":"digest","outputType":"ArrayBuffer","outputLength":32}
[spider-cryptojs] {"method":"SHA256","inputType":"string","inputLength":48}
```

**不要**加字节预览，**不要**调用任意的 result serializer。未知对象用 `outputLength: null`。

## Canvas 或其他扩展

生成的项目专用 Hook 遵循同样的规则：**只有操作名、尺寸/类型和长度**。

Canvas data URL 表示为 MIME + 总长度，**绝不**给前缀预览。

## 降噪（Noise Control）

1. **先**收窄 URL / key / method 过滤器
2. **再**设 `maxEvents` 与 `logStack`
3. **不存在**持久的 `FULL_LOG` 选项

如果确实需要看完整值，用 `debugger` **一次性暂停**检查，**不要**把它写进 Console 或 case 文件。

## 相关

- `../index.md` — profile 入口与判据
- `snippets.md` — 片段索引与选点建议
- `network.md` / `storage.md` / `crypto.md` / `dom.md` / `runtime.md` — 各类 Hook 的选点约束