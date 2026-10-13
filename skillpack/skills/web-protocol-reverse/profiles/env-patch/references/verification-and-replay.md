# 验证与重放（Verification And Replay）

> **来源**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `verification-and-replay.md`。**下方 JavaScript / Python 代码块一字未改**（代码不译）。
> **用途**：在 `env-diagnose.js` **已经能加载**目标脚本之后，走完"功能验证 → 封装可调用接口 → HTTP 重放校验"这三步。
> **前置（本机实测，2026-10-10）**：Node ✅ `(Resolve-ReverseToolSpec -Name 'node').Command` v24.20.0；Python ✅ `(Resolve-ReverseToolSpec -Name 'pyre').Command` 3.12.0，`curl_cffi` ✅ 已安装。⚠️ `env-diagnose.js` **未随本包落地**，本机跑不了第一步；下文示例中的 `curl_cffi` 与 `requests` API 形态**未在本机对真实目标验证**，示例 URL 均为 `example.com` / `target.example` 占位。
> **用法**：本篇的核心结论是 —— **加载成功只是语法/运行时里程碑，不证明目标的 sign / token / cookie / 加密字段会被服务端接受。** 这一条在 `../index.md` 的「非协商项」和 `../../../SKILL.md` 的「判据」里都重复了，别跳过。

在 `env-diagnose.js` 能加载目标脚本之后使用本参考。加载成功只是语法/运行时里程碑，**不证明**目标的 sign、token、cookie 或加密字段会被服务端接受。

## Contents

- [Function Verification](#function-verification)
- [Packaging A Callable Interface](#packaging-a-callable-interface)
- [HTTP Replay Checks](#http-replay-checks)

## Function Verification

`success: true` is not functional success. Verify the target behavior in a task-local runner such as `js_reverse_cache/tasks/<task-id>/env/run.js`, using the same environment modules selected during diagnosis.

Recommended flow:

1. Build `js_reverse_cache/tasks/<task-id>/env/run.js` with the same env modules and the target script.
2. Trigger the target behavior, such as an SDK init call, an XHR send, or a direct sign function call.
3. Check output shape against browser evidence, such as `a_bogus` length, prefix, segment count, encoding, or cookie name.
4. Only then package the callable sign/token interface or try HTTP replay.

For hook-style SDKs, keep this loading order:

```text
env modules -> fake XMLHttpRequest -> target JS -> capture hook -> init(config) -> trigger request
```

Important details:

1. Fake `XMLHttpRequest` must exist before loading the target JS if the target patches its prototype at load time.
2. Capture hooks such as `URLSearchParams.append` should be injected after the target JS if the target may replace native APIs with polyfills.
3. SDK `init` or `setup` parameters must be captured from the browser when they decide path matching or feature switches.

Common failures after load succeeds:

| Symptom | Likely Cause | Check |
|---|---|---|
| Sign is `undefined` | Missing crypto/performance dependency | Review selected env modules |
| Hook runs but does not sign | Missing SDK init params or path whitelist | Capture init params in the browser |
| Capture hook never fires | Hook injected before a target polyfill overwrote it | Move capture hook after target JS |
| JSVMP silently fails | Internal try/catch swallowed errors | Instrument known error exits cautiously |
| Sign length differs from browser | Environment fingerprint mismatch | Collect real browser seeds and patch minimally |

## Packaging A Callable Interface

After function verification passes, extract the runner into a small callable module, commonly `js_reverse_cache/tasks/<task-id>/env/sign.js`:

```javascript
function sign(url) {
  window.__captured_a_bogus = null;
  const xhr = new XMLHttpRequest();
  xhr.open('GET', url, true);
  xhr.setRequestHeader('Accept', 'application/json, text/plain, */*');
  xhr.send(null);
  return window.__captured_a_bogus;
}

module.exports = sign;

if (require.main === module) {
  const url = process.argv[2] || process.env.SIGN_URL;
  if (!url) {
    console.error('Usage: node sign.js <url>');
    process.exit(1);
  }
  process.stdout.write(sign(url) || '');
}
```

Prefer an HTTP middleware for Python replay when process environment differences affect subprocess execution:

```javascript
const http = require('http');
const sign = require('./sign');
const PORT = 3456;

const server = http.createServer((req, res) => {
  if (req.method !== 'POST' || req.url !== '/sign') {
    res.writeHead(404);
    res.end('Not Found');
    return;
  }

  let body = '';
  req.on('data', (chunk) => body += chunk);
  req.on('end', () => {
    try {
      const { url } = JSON.parse(body);
      const result = sign(url);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ result: result || '', length: (result || '').length }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: e.message }));
    }
  });
});

server.listen(PORT, () => console.log(`sign server on http://localhost:${PORT}/sign`));
```

## HTTP Replay Checks

Validate in this order:

1. Format check: run `node js_reverse_cache/tasks/<task-id>/env/run.js` and compare sign shape with browser evidence.
2. Middleware check: call `POST http://localhost:3456/sign` with a known URL.
3. Request replay: send the real API request with the returned sign and the same browser-side request contract.

Python request rules:

1. Use `requests.get(base_url, params=params, cookies=cookies)` or the equivalent `curl_cffi.requests` call.
2. Keep `cookies` as a dict or cookie jar; do not stuff a raw cookie string into `headers["cookie"]` unless the target explicitly requires manual header replay.
3. Do not manually pre-quote the generated sign unless browser evidence proves the exact encoded form.
4. Rebuild time-sensitive sign/header/token values inside pagination or retry loops.

Minimal replay skeleton:

```python
from curl_cffi import requests

SIGN_SERVER = "http://localhost:3456/sign"


def get_sign(url):
    resp = requests.post(SIGN_SERVER, json={"url": url}, impersonate="chrome136")
    return resp.json().get("result") or None


headers = {"user-agent": "...", "referer": "..."}
cookies = {"ttwid": "...", "odin_tt": "..."}
params = {"aid": "6383", "sec_user_id": "...", "msToken": "..."}

base_url = "https://target.example/api/path/"
prepared = requests.Request("GET", base_url, params=params).prepare()
params["a_bogus"] = get_sign(prepared.url)

response = requests.get(base_url, headers=headers, cookies=cookies, params=params, impersonate="chrome136")
print(response.status_code, response.text)
```
