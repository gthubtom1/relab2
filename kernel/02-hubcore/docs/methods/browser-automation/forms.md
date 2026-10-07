# 表单

先勾 [catalog.md](catalog.md) B1–B9。

## 普通输入

- 优先 `getByLabel` / `getByRole` / `getByPlaceholder`，不要拿当前已填的值当定位（值一变就丢）。
- `fill` 会清空再填。要追加用 `pressSequentially`。
- 填完保险点：`inputValue` 对得上 **且** 失去焦点后校验通过（或错误提示明确消失）。
- 密码框不要写进日志、截图打码、不要提交到仓库。

## 下拉

| 种类| 怎么做| 保险点|
|---|---|---|
| 原生 `<select>`| `selectOption`| 选中 value + 可见标签|
| 自制列表| 点开 → 等选项节点（或对应接口）→ 再点选项| 关闭后触发器显示新值|
| 可搜索 combobox| 输入 → 等建议 → 点匹配项| 不要在建议未到时回车|

点开瞬间选项还没来、列表被刷新关掉 = 时机赛跑，等选项或接口，不要加 sleep。

## 勾选 / 开关

- `check` / `uncheck` / `setChecked`。先读当前态，已经对了不要再点（会弹回去）。
- 保险点：`aria-checked` / `input.checked` + 旁边说明文案。

## 日期时间

- 原生 `input[type=date]`：直接 `fill('YYYY-MM-DD')`。
- 自制日历：角色 `gridcell` + 可访问名；过滤跨月灰字，避免点到「上个月的 1 号」。
- 「今天/明天」会随墙上时钟跑。第三方站不要乱改对方时钟；自己的测试站才用 `page.clock`，且必须在 `goto` 前。
- 时区：合同写清用哪套，不要用运行机本地「今天」当唯一证据。
- 保险点：输入值 + 摘要文案，不要只看日历是否关上。

## 滑块 / 颜色

- range 优先键盘方向键或 `fill`，不要拖像素。
- 颜色：填 `#rrggbb`，再读 value。

## 富文本 / contenteditable

- 点 **真正** `contenteditable=true` 的节点，不是外层包装（TipTap/Quill/Lexical 常见套娃）。
- 纯塞正文可用 `fill`；要触发 @、斜杠菜单、快捷键用 `pressSequentially`。
- 保险点：编辑器内可见文本 **加上** 保存后预览/接口里的正文。两处不一致以保存后的为准。
- 不要用 `innerHTML` 当成功（一堆包装标签）。

## Monaco / CodeMirror

- 表面节点往往不可见或离屏。点编辑器表面，再用 `keyboard` 输入。
- 保险点：编辑器 `getValue` 或保存回显，不是 textarea 的 value。

## 校验错误

- 提交后先认错误桶：字段旁红字是材料问题；整页 toast 可能是登录/限流。
- 有错误时不要当「下一步出现了」。错误原文进合同「材料拒绝」或「校验失败」列。
