# 防漏总表

写代码前把本表勾完，贴进合同。每一行只能是 **有 / 无 / 未看见**。未看见不准当无。标「有」必须读对应分册。

禁止：只按今天走过的步骤勾；把「这单用不到」空着。用不到就写 **无**。

## 1. 任务类型（可多选）

| 类型| 本程序| 做成的证据（默认）|
|---|---|---|
| 登录 / 保活|| 账号专属名/头像 + 退出入口 + 受保护页内容|
| 填表 / 设置|| 字段回显 + 保存成功回执 + 再打开仍在|
| 点选 / 向导|| 当前步痕迹 + 下一步控件可点|
| 上传|| 成功文案 + 对象名 + 大小/时长 + 可操作下一步|
| 下载 / 导出|| 磁盘文件存在 + 扩展名 + 大小>0 + 不是 HTML 错误页|
| 发布 / 提交|| 平台唯一 ID + 标题/对象对得上（禁点则合同写死）|
| 抽取 / 翻页|| 唯一 ID 集合 + 条数对得上 + 不是挡板空壳|
| 巡检 / 截图|| 约定视口的图 + URL + 时间|
| 多账号窗口|| 每个 context 互不串 Cookie|
| 支付 / 删除 / 不可逆|| 默认停给人；合同未写死允许则禁止点|
| 邮件魔法链接 / passkey|| 停给人；做成仍看账号专属标记|
| 结账 / 填卡|| 停在支付前；禁止自动填完整卡号|

## 2. 操作总表

| 编号| 操作| 有/无/未看见| 分册|
|---|---|---|---|
| A1| 打开 URL / 刷新 / 前进后退|| [env.md](env.md)|
| A2| 单击 / 双击 / 触屏 tap|| [actions.md](actions.md)|
| A3| 悬停才出的菜单|| [actions.md](actions.md)|
| A4| 右键菜单|| [actions.md](actions.md)|
| A5| 键盘快捷键 / Tab 焦点|| [actions.md](actions.md)|
| A6| 拖拽排序 / 拖到投放区|| [actions.md](actions.md) [files.md](files.md)|
| A7| 滚动 / 滚到无限列表底部|| [actions.md](actions.md) [extract.md](extract.md)|
| A8| 剪贴板复制粘贴|| [actions.md](actions.md)|
| A9| 中文/日韩 IME 组字|| [actions.md](actions.md)|
| B1| 单行/多行输入、清空|| [forms.md](forms.md)|
| B2| 原生 select|| [forms.md](forms.md)|
| B3| 自制下拉 / 搜索建议|| [forms.md](forms.md)|
| B4| 勾选 / 单选 / 开关|| [forms.md](forms.md)|
| B5| 日期时间 / 日历|| [forms.md](forms.md)|
| B6| 滑块 range / 颜色|| [forms.md](forms.md)|
| B7| 富文本 / contenteditable|| [forms.md](forms.md)|
| B8| Monaco/CodeMirror 编辑器|| [forms.md](forms.md)|
| B9| 表单校验错误回执|| [forms.md](forms.md)|
| C1| input[type=file] 投文件|| [files.md](files.md)|
| C2| 系统文件框 filechooser|| [files.md](files.md)|
| C3| 拖文件到投放区|| [files.md](files.md)|
| C4| 大文件 / 远程浏览器|| [files.md](files.md)|
| C5| 下载文件到磁盘|| [files.md](files.md)|
| C6| 打印 / 另存 PDF|| [files.md](files.md)|
| D1| iframe / 嵌套框|| [windows.md](windows.md)|
| D2| 开放/封闭 Shadow|| [windows.md](windows.md)|
| D3| 新标签 / popup|| [windows.md](windows.md)|
| D4| 原生 alert/confirm/beforeunload|| [windows.md](windows.md)|
| D5| HTML dialog / 抽屉 / 多弹层|| [windows.md](windows.md)|
| D6| cookie/订阅/新手挡板|| [windows.md](windows.md)|
| D7| 权限气泡（通知/位置/剪贴板/相机）|| [windows.md](windows.md)|
| D8| Canvas / 地图 / 无 DOM 格子|| [windows.md](windows.md)|
| E1| 账密登录|| [auth.md](auth.md)|
| E2| OAuth / SSO 跳转或弹窗|| [auth.md](auth.md)|
| E3| 扫码 / 短信 / TOTP / 人机验证|| [auth.md](auth.md)|
| E4| 会话恢复 Cookie/storageState|| [auth.md](auth.md)|
| E5| 中途掉登录|| [auth.md](auth.md)|
| E6| 多账号隔离|| [auth.md](auth.md)|
| F1| 等某一个接口|| [network.md](network.md)|
| F2| WebSocket / 心跳|| [network.md](network.md)|
| F3| 限流 429 / 重试|| [network.md](network.md)|
| F4| 上传/下载进度接口|| [network.md](network.md)|
| G1| 表格/卡片列表抽取|| [extract.md](extract.md)|
| G2| 分页页码|| [extract.md](extract.md)|
| G3| 无限滚动 / 虚拟列表|| [extract.md](extract.md)|
| G4| 进详情再返回列表|| [extract.md](extract.md)|
| G5| 空列表 vs 被挡/未加载|| [extract.md](extract.md)|
| H1| 视口 / 移动端 / 暗色|| [env.md](env.md)|
| H2| 语言 / 时区 / 时钟|| [env.md](env.md)|
| H3| CDP 连已开窗口|| [env.md](env.md)|
| H4| 失败录像 / trace / 截图|| [env.md](env.md)|
| H5| 实验组 / A-B 两套布局|| [pitfalls.md](pitfalls.md)|
| I1| SPA 同文档导航 hash/pushState（无 load）|| [network.md](network.md)|
| I2| Service Worker 缓存旧数据|| [network.md](network.md)|
| I3| WebAuthn / passkey|| [auth.md](auth.md)|
| I4| 邮件魔法链接|| [auth.md](auth.md)|
| I5| File System Access 选文件（不是 input）|| [files.md](files.md)|
| I6| blob / createObjectURL 下载|| [files.md](files.md)|
| I7| 粘性头 / 同意条盖住点击点|| [actions.md](actions.md)|
| I8| IndexedDB 里的会话|| [auth.md](auth.md)|
| I9| 双提交 / 幂等|| [recovery.md](recovery.md)|
| I10| 域名白名单 / 提示注入|| [env.md](env.md)|
| I11| 页面崩溃 crash|| [env.md](env.md)|
| I12| 骨架屏 / 乐观 UI 假 next|| [proof.md](proof.md)|
| I13| 近义禁词（上传 vs 重新上传）|| [proof.md](proof.md)|

## 3. 默认保险点（按类型，合同里改成页上原文）

| 类型| current 至少凑| next 至少凑|
|---|---|---|
| 点击下一步| 按钮变态或消失、本步标题| 下一步标题、下一步主控件可点|
| 填一个字段| 输入值回显、计数/校验通过| 可点保存或下一项|
| 上传| 成功文案、对象名、大小/时长| 标题框/封面入口可点|
| 下载| 浏览器 download 事件、建议文件名| 磁盘 size>0、不是 `<html`|
| 登录| 登录表单卸掉| 专属昵称、退出、受保护内容|
| 抽取一页| 本页条数、第一条 ID| 下一页可点或「没有更多」原文|
| 关挡板| 挡板节点不可见| 主操作可点|

进度类数字进「指纹」，变了就重置冻结时钟，不要当卡住。每步另写否决（登录墙、近义按钮、骨架屏），见 [proof.md](proof.md)。
