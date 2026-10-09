# 瑞数 VMP 与补环境（sdenv / rs-reverse）

**何时读**：目标页面在浏览器里看着正常，但脚本抓回来补环境跑不通；或页面用了瑞数（Riverbed）
这类自研 VMP 风控，cookie / 签名本地复现不出来。

**这两个是什么**：Node.js **工具**，不是独立技能。它们是本 skill 「Rebuild → Patch → DeepDive」
三阶段的现成实现，替代手写 shim。

| 工具 | 干什么 | 前置 |
|---|---|---|
| **rs-reverse** | 瑞数 VMP **纯算法**逆向：`makecode` 抠动态代码、`makecookie` 直接算 cookie | Node ≥18 |
| **sdenv** | 基于定制 jsdom 的**补环境框架**，把浏览器特性注进 `window` | Node ≥20.19.5 + node-gyp + MSVC C++ 生成工具 |

两者是兄弟项目：sdenv 跑 VMP 原文，rs-reverse 剥掉 VM 外壳直接走算法。**先用 rs-reverse，
兜不住再用 sdenv。**

## 前置门（不满足就别开始）

```powershell
# 1. Node 版本 —— sdenv 不支持 v21.7.3
(Get-Command node -ErrorAction SilentlyContinue).Source
node -v

# 2. 两个工具的真实位置（装法见 TOOLS.md §6）
(Get-Command rs-reverse -ErrorAction SilentlyContinue).Source
```

sdenv 未装时**不要先装**：先按 `node-env-rebuild.md` 手写最小 shim 试一次。
多数「补环境」问题（缺 `document.all` 之外的常规缺口）手写 20 行就够了，装 sdenv 的成本
（原生编译 + VS C++ 工作负载）不划算。**只有自研 VMP 风控才值得上 sdenv。**

## 路线一：rs-reverse 纯算法（优先，成本最低）

```powershell
# 抠动态代码：外层 VM 代码 + 内层动态代码 + 静态配置
npx rs-reverse makecode -u <204响应地址>
npx rs-reverse makecookie -u <204响应地址>

# 本地样本（不请求目标站，推荐）
npx rs-reverse makecookie -j ./main.js -f ./$_ts.json

# 两次请求的加密代码都解出来
npx rs-reverse makecode-high -u <地址>
```

常用参数：`-o` 输出目录（默认 `./output`）、`-l` log4js 日志级别、`--no-has-debug` 关掉
误判的 debugger 版本。

**产物**：原始 `$_ts` → `ts-full.json`、静态文本 `immucfg.json`、外层 VM 代码、内层
`-dynamic.js`。**`makecookie` 直接吐 cookie 字符串**，这是它相对 sdenv 的最大优势 ——
不跑浏览器就出结果。

**首次跑不通先读 example**，别对着目标站试：`node main.js makecookie` 用仓库自带的
`example/codes/` 样例，20ms 内出结果说明工具本身正常，是你的输入不对。

## 路线二：sdenv 补环境（rs-reverse 兜不住时）

```javascript
const { jsdomFromText, jsdomFromUrl, browser } = require('sdenv')

// 本地 HTML 文本 → 拿到 window 后注入浏览器特性
const dom = jsdomFromText('<html>...</html>', {
  url: 'https://host/path',
  referrer: 'https://host/path',
  runScripts: 'outside-only',   // 不自动执行 html 里的 js
})
browser(dom.window, 'chrome')   // 只支持 chrome（firefox/safari 未支持）
console.log(dom.cookieJar.getCookieStringSync('https://host'))

// 远程 URL：第二次必须沿用上一次的 cookieJar，否则 cookie 链断掉
const one = await jsdomFromUrl(url, { userAgent: '...' })
const two = await jsdomFromUrl(url, { userAgent: '...', cookieJar: one.cookieJar })
```

**window 代理**（对抗 `process` / `runScripts` 检测）：

```javascript
beforeParse: function (window, sdenv) {
  sdenv.getConfig('window')({ windowGetterErrorKeys: ['process'] })
  sdenv.getConfig('window')({ log: (type, prop) => { /* 打印取值链路 */ } })
}
```

链路固定为：`makecode` 抠代码 → sdenv 跑环境 → **cookie 对账**（sdenv 产出 vs 浏览器
DevTools 实测）。对不上就按 `env-patching.md` 的规则走最小补丁，一次一个。

## 何时**不该**用这两个

- **目标是 PE/ELF/APK** —— 这是浏览器 JS 层的事，滚去 `ida-reverse` / `apk-reverse`。
- **自研（非瑞数）VMP** —— 先读 `../../reverse-engineering/references/nonpe-format-cookbook.md`
  的 AD（JSVMP）章节，方法论通用，工具不一定通用。
- **普通加密参数** —— `ast-deobfuscation.md` + `instrumentation.md` 就够。

## 硬约束

- **对账才算数**：本地 cookie 与浏览器实测不一致 = 未完成，不许报「已复现」。
- **不要高频重跑**：`makecode-high` 连发会触发风控报错（上游明确警告）。
- **上游默认值不等于许可**：两个仓库都是 **BSD 3-Clause**（可商用），但含
  `sdenv-extend` / `sdenv-jsdom` / `sdenv-extract` 三个独立依赖，其许可需各自确认。
- **免责声明**：rs-reverse 仓库自带声明，仅供学习研究，其作者不鼓励直接请求研究站点。
  优先用 `-j`/`-f` 走本地样本。

上游：<https://github.com/pysunday/sdenv> · <https://github.com/pysunday/rs-reverse>