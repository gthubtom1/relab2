# 混淆指南（Obfuscation Guide）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `obfuscation-guide.md`。原文为英文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文，AI 检索时中英文均可命中。源文档的技术内容经逐条核对**未发现错误**，未作技术性修改。
>
> **什么时候用**：页面下发的 JavaScript 是 packed（打包）、flattened（控制流平坦化）、或 string-table-heavy（字符串表密集）的。
>
> **平台与本机状态**：Windows 10 x64。`node v24.20.0`（`D:\Tools\Node\node.exe`）、`python 3.12`（`D:\EXE\python\python.exe`）**本机可用**。⚠ `esprima` / `acorn` / `@babel/parser`（npm 解析器）**本机无**，需要静态 AST 的那部分要**先自行安装**；本文主路径**不依赖**这些包，用的是「文本切分 + 本地执行 decoder」的路子。本文不涉及 `iv8`。

---

## 适用信号（Recognition signals）

- 巨大的字符串数组
- `eval`、`Function`、或自改写（self-redefining）的包装器
- 控制流平坦化（control-flow flattening）
- 数字数组派发（numeric array dispatch）
- 极小的旁路资产（side assets）在控制真正的逻辑
- obfuscator.io 类 bundle 常见的 **rotate-then-decode** 字符串表
- member-map 对象，如 `{a:0x2aa,b:0x2ad}`，作为 decoder 调用的实参

## 前置（Entry conditions）

1. **原始字节先落盘**。任何改写之前先保存原始文件 —— 这是唯一能让你 diff 出「我改了什么」的基准。
2. **一个能执行 JS 的本机宿主**。本机 `node` 即可：
   ```powershell
   D:\Tools\Node\node.exe -v
   # v24.20.0
   ```
   decoder 只需要一个最小 harness（脚手架），不需要完整浏览器。
3. **一个 brace-aware（括号感知）的切分手段**。
   ⚠ 源文档强调「用括号匹配而不是脆弱的行切片」是**对的**，但它没给工具。本机两条路：
   - **推荐**：`node` 自带 JS 引擎，可直接求值闭包，天然处理转义引号
   - 需要真正 AST 时：`acorn` / `esprima` / `@babel/parser` —— **本机均无，须先 `npm install`**

## 步骤（Working method）

### 核心工作顺序（Working order）

1. **先**搜索真实 API 路径
2. 在「解包全部」之前，**先**找到传输层 wrapper（transport wrapper）
3. 只抽取当前请求所需的**最小逻辑切片**
4. 每次大改之前**保存一份干净快照**
5. 反调试噪音高时**尽早**转离线

### 字符串表密集的 bundle（String-table heavy bundles）

当 bundle 呈现「字符串数组 + decoder + rotate IIFE」形态时：

1. **先**保存原始源字节
2. 用 **brace matching（括号匹配）** 抽取字符串数组函数、decoder 函数、以及 rotate IIFE —— 不要用脆弱的行切片。匹配必须**尊重转义引号**
3. 在本地 `node` harness 中**只执行 decoder 这一层**，dump 出字符串表
4. **分两遍**改写调用点：
   - 第一遍**展开 member-map 对象**，把 `decoder(map.a)` 变成 `decoder(0x2aa)`
   - 第二遍把 `decoder(0xNNN)` 以及 decoder 的**别名**替换成 dump 出的字符串字面量
5. 若 dump 表的键是**纯 hex 文本**，匹配时要**去掉 `0x` 前缀**
6. **beautify（美化）放在第一次有效改写之后**；但如果文件是**一整行**、行号完全无用，则**立刻**美化
7. 在可读切片上**恢复协议搜索**；一旦 signer 的输入已经能拿到，**不要**再去清理死分支

> **若第一遍改写没有任何变化** —— 在发明新反混淆器之前，先假设
> **member-map 那遍**做错了，或 **hex 键归一化**做错了。

### 本机最小 harness（decoder 单独跑）

源文档未给可执行示例。以下骨架为本机 `node v24.20.0` 实测可用形态
（**注意**：这是 harness 形态验证，具体 bundle 未在本机跑过）：

```javascript
// dump-table.js  —— 只执行 decoder 表面，不执行业务逻辑
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync(process.argv[2], 'utf8');

const table = {};                     // hex 键 -> 字符串字面量
const ctx = {
  console,
  atob: s => Buffer.from(s, 'base64').toString('binary'),
  btoa: s => Buffer.from(s, 'binary').toString('base64'),
};
ctx.window = ctx; ctx.globalThis = ctx;
vm.createContext(ctx);

// 关键：把「数组声明 + decoder 定义 + rotate IIFE」这一段喂进去，
// 捕获 decoder 函数句柄，而不是执行整个 bundle。
// 具体切分范围因 bundle 而异，这里不给通用正则 —— 会骗人。
vm.runInContext(src.slice(0, /* rotate IIFE 结束位置 */), ctx);

const decoder = ctx[/* decoder 的实际名字 */];
for (let i = 0; i < /* 表长度 */; i++) {
  try { table[i.toString(16)] = decoder(i); } catch (_) {}
}
console.log(JSON.stringify(table, null, 1));
```

运行：
```powershell
D:\Tools\Node\node.exe dump-table.js .\bundle.js > table.json
```

> ⚠ `atob`/`btoa` 的 Latin-1 语义必须正确。`btoa` 遇到 `0xff` 以上的码元要**抛错**，不能做 UTF-8 编码。
> 自测向量（**本机实测**）：`btoa("\x00\xffAz")` 应为 `"AP9Beg=="`。
> 验证：
> ```powershell
> D:\Tools\Node\node.exe -e "console.log(Buffer.from([0x00,0xff,0x41,0x7a]).toString('base64'))"
> # AP9Beg==
> ```

## 判据（Verification checklist）

只有满足以下**全部 5 条**，才可以说「混淆拆完了」：

1. **目标 signer 的输入已被还原** —— 不是「整个 bundle 可读」，而是「当前请求要的那份 preimage / 签名输入**已经拿到**」
2. **字符串表 dump 成功，且调用点两遍改写都完成了** —— member-map 展开 + `decoder(hex)`/别名替换，两遍都跑过，不是只跑了一遍
3. **改写后的代码能产出与原始 bundle **一致**的签名值** —— 用一条固定输入向量验证，不是「看起来对」
4. **原始字节快照已保留**，且能 diff 出改写前后的差异
5. **明确写下了「到此为止」的边界** —— 哪些逻辑还原了、哪些刻意没还原及原因

> ⚠ **不构成完成**的情况：
> - 「美化完了，能读了」 —— 读得懂 ≠ 能 replay
> - 「大部分替换了」 —— 剩下的一小段可能正好是 signer
> - **花费超过协议 replay 所需的去混淆量**（违反源文档的核心约束，见下）

## 常见坑（Common traps）

- 在找到真实请求之前就把整个 bundle 美化（例外：单行文件导致搜索完全不可用）
- 忽略 inline scripts（内联脚本）和旁路资产
- 丢掉原始变量名，导致后续无法 diff
- **只替换 hex 字面量，漏掉 `decoder(map.key)` 形态** —— 这是最高频的漏网形式
- 把 dump 键（如 `"c7"`）当成与源码记号（`0xc7`）不匹配
- 把逗号表达式（comma-expression）的返回值读成 `void`，而真实值是右侧那个调用
- 用**行切片**代替括号匹配去抽 decoder —— 遇到转义引号就崩

## 相关（Related）

- `offline-inline-deob-playbook.md` —— 完整的离线还原流程（含内联 payload、Unicode 分隔符陷阱）
- `crypto-patterns.md` —— 还原之后再判断算法是否被魔改
- `pattern-atlas.md` —— Pattern G「极小的旁路资产承载整个 signer」
- `../../../js-reverse/references/ast-deobfuscation.md` —— 需要真正 AST 时（本机需先装解析器）
- `../observe/anti-debug-playbook.md` —— 转离线的触发条件
- `../deliver/pure-python-rebuild-playbook.md` —— 判据第 3 条之后的移植路径
