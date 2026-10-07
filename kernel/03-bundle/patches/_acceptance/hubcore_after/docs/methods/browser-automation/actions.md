# 点、键、拖、滚、剪贴板、组字

先勾 [catalog.md](catalog.md) A2–A9、I7。

## 点

- 默认 `locator.click()`。要 **可见 + 稳定 + 可点 + 接到指针**。
- 双击、tap 合同单独写，不要拿单击冒充。
- 同名多按钮：先缩到父级（对话框、卡片、当前步），再精确文本。
- 点完立刻从新快照认状态。禁止保存 `@e3` 跨动作复用。
- 禁止 `force: true`（会点穿遮罩，页没收到）。
- 禁止 `page.evaluate` / `dispatchEvent` 当点击。那种事件 `isTrusted=false`，很多站当没点。主路径只用 locator 的真实输入。
- 点击点被挡住（同意条、粘性头、新手层）：Playwright 可能报 covered by…，或静默点到遮罩。先关掉合同白名单挡板，滚到不被挡，再点。被挡不算保险点命中。
- `scrollIntoView` 之后仍可能藏在粘性头下面。保险点要「真正接到指针」。
- 需要用户手势的（popup、剪贴板、相机）：必须跟这次点击同一拍，不要 `click` 完 `await` 一阵再 `window.open`。
- 禁止按截图像素点。Canvas/地图没有无障碍节点就不要做关键操作，停给人。
- 右键：`click({ button: 'right' })`，再等菜单出现才点子项。

## 悬停

菜单合同写「先 hover 再等菜单」。没悬停就点子项会点到隐藏节点或空。

## 键盘

- 快捷键用 `press('Control+s')` 这类，不要逐字符冒充快捷键。
- Tab 走焦点时，保险点是「谁获得了焦点」，不是按了几次 Tab。
- 有的控件只认真实按键：`pressSequentially`，不要 `fill`。

## 拖

- 元素拖到元素：`dragTo`，保险点是目标槽位的原文/顺序变了。
- 文件拖入投放区见 [files.md](files.md)。
- 拖的过程有动画：等 stable，不要在飞行中点中心。

## 滚

- 先 `scrollIntoViewIfNeeded`，再等目标行出现。
- 无限列表：滚到底部 → 等「新唯一 ID 增加」或「没有更多」原文。条数不变且没有结束原文 = 卡住或被挡，见 [extract.md](extract.md)。
- 虚拟列表 DOM 只有可见行，禁止按下标/总数当全量。

## 剪贴板

- 先在 context 授 `clipboard-read` / `clipboard-write`（合同写清）。
- 权限气泡弹出来要进「停给人」或合同白名单，不要当普通挡板乱关。
- 富文本粘贴：页内构造 `DataTransfer` 派 `paste`，不要假设系统剪贴板在 CI 里可用。
- 做成证据：目标字段的值，不是「调用过 clipboard」。

## 中文 / IME

- `fill()` 一次塞字符串，很多搜索框/评论框可以。
- 依赖组字过程的（@提及、搜索建议、富文本插件）必须 `pressSequentially` 或真人 IME。headless 往往**模拟不了**真实输入法上屏。
- 组字过程中不要抢点建议列表。等 composition end 再核字段值。
- 保险点是上屏后的汉字，不是拼音中间态。

## 滚动条、缩放、选区

- 页面缩放会让像素方案全废（本来就禁止像素）。
- 选中文本用 `selectText` 或三击，保险点是 `window.getSelection` 或后续「复制」按钮可点。
