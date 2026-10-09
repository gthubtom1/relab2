# Node.js 特征检测说明（Node.js Detection Notes）

> **来源**：改编自 `aoyunyang/spider-king-skill`（MIT License）的 `node-detection.md`。**下方 JavaScript 代码块一字未改**（代码不译）。
> **用途**：安全 SDK 常通过 Node.js 特征检测运行环境。本篇列出常见检测项与对策。
> **前置（本机实测，2026-10-10）**：Node ✅ `D:\Tools\Node\node.exe` v24.20.0。文中"Node 18+ 有 `fetch`、Node 19+ 有 WebCrypto、Node 21+ 有 `navigator`"的说法与本机 v24.20.0 一致（该版本高于上述所有门槛），但**未逐个验证**这些全局对象在本机的实际行为。
> **用法**：**只在签名格式降级、长度不一致，或诊断报告无法解释偏差时**读本文。常规补环境流程不需要它。
>
⚠️ **重要**：这些对策**不能保证**绕过所有检测。VMP 可能在 opcode 层面完成检测，不经过外部 JS API —— 撞到这种情况时，正确动作是读 `limitations.md` 并如实报告天花板，不是继续堆对策。

安全 SDK 常通过 Node.js 特征检测运行环境。只在签名格式降级、长度不一致或诊断报告无法解释偏差时读取。

## 常见检测项

### Buffer

浏览器通常没有 `Buffer`，Node.js 有：

```javascript
const originalBuffer = globalThis.Buffer;
delete globalThis.Buffer;
// 目标执行完成后再按需恢复
globalThis.Buffer = originalBuffer;
```

不要用 getter 返回 `undefined` 伪装不存在；某些 VMP 会检查 `Object.getOwnPropertyDescriptor`，accessor 反而暴露异常。

### process

有些 webpack 浏览器包会注入 `process`，有些页面没有。不要盲删，先对照浏览器：

```javascript
const originalProcess = globalThis.process;
globalThis.process = { env: { BROWSER: true, BUILD_ENV: 'production' } };
// 目标执行完成后恢复
globalThis.process = originalProcess;
```

### Error.prepareStackTrace

Node.js V8 特有 API：

```javascript
delete Error.prepareStackTrace;
```

### module / exports / require

CommonJS 特征可能被检测。能从入口依赖数组或加载包装层移除最好；不能时再在运行上下文里隐藏。

### Node 新版内置 Web API

Node 18+ 有 `fetch`，Node 19+ 有 WebCrypto，Node 21+ 有 `navigator`。覆盖全局变量时优先用 `Object.defineProperty`：

```javascript
Object.defineProperty(global, 'navigator', {
  value: proxiedNavigator,
  writable: true,
  configurable: true,
  enumerable: true,
});
```

## toString / toStringTag

```javascript
Object.defineProperty(window, Symbol.toStringTag, { value: 'Window', configurable: true });
Object.defineProperty(document, Symbol.toStringTag, { value: 'HTMLDocument', configurable: true });
```

函数外形用 `env_core.js` 的 `setFuncNative()` 统一伪装，不要每个函数手写 `toString`。

## 注意

这些对策不能保证绕过所有检测。VMP 可能在 opcode 层面完成检测，不经过外部 JS API。遇到这种情况，参考 `limitations.md`。
