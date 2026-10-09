# 分页路由切换手册（Pagination Route Pivot Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `pagination-route-pivot-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。改编中补齐了前置与判据段（本包硬性要求）。
>
> **什么时候用**：分页**不再遵循某一个明显的 URL 家族**；或者下一页的目标**藏在内联 pager 元数据里**，而不是一个普通链接。
>
> **平台与本机状态**：本文是纯方法论，但「比较原始 HTML 与解析后 DOM」这一步在本机需要一个 HTML 解析器 —— `python 3.12.0`（`D:\EXE\python\python.exe`）+ 标准库 `html.parser` 即可满足，无需第三方包。静态 AST 那套（`esprima`/`acorn`/`@babel/parser`）**本机未装**，仅在需要还原内联 JS 时才需先装。抓线路见 `tshark 4.6.8`（`D:\Tools\Wireshark\tshark.exe`）。MCP 浏览器家族**本机未挂载**。

---

## 适用信号（When to route here）

- 第 1 到 N 页走静态路径正常，**但后面的某个页码 404 或返回了错误内容**
- 可见的 pager **看起来是均匀的**，但线上下一页的目标指向了**另一个端点家族**，如 `/ui`、Ajax，或另一个模板路由
- 从首页 URL **猜测**后续页码，短暂有效，然后失败
- 真正的下一页 URL 在内联 `onclick`、`tagname`、隐藏模板，或 pager widget 里
- **DOM 解析出来的属性值与原始 HTML 不再匹配** —— 因为有未转义的 `&`、实体解码，或遗留标记修复
- 一个页面里的翻页控件存在，但采集器就是翻不过去

## 前置（Entry conditions）

1. **有一条正常的早期页 + 一条失败的晚期页**。两者都要保存。
2. **能取到原始 HTML**（不是 DOM 序列化后的字符串）。判定「原始 vs 解析」是本文的核心，不拿到原始字节就无从比较。
3. **已排除「单页例外」**的可能 —— 如果只有一页特殊且路由家族没变，先走 `./page-specific-exception-playbook.md`。

## 步骤（Working method）

### 核心思想

**分页是协议契约的一部分。**
正确的下一条路由**可能在序列中途改变**，而**最安全的真相来源可能是原始 HTML 片段，而不是修复过的 DOM 属性。**

### 快速执行路径

1. **冻结一条好的早期页 + 一条失败的晚期页。** 保存：
   - 当前页 URL
   - pager 附近的**原始 HTML**
   - 从线上页面得到的**精确下一页路由**
   - 你尝试过的那个失败的猜测 URL（若有）

2. **比较路由家族，而不只是页码。** 记录：
   - 早期页的 URL 家族
   - 晚期页的 URL 家族
   - 家族发生切换的**分界页码**
   - 是否有 category、mode 或其他隐藏状态随路由家族一起变化

3. **把 pager 元数据当作协议状态。** 检查：
   - `href`
   - 内联 `onclick`
   - `tagname` 或自定义属性
   - 隐藏模板或「跳转到第 N 页」的格式串

4. **比较原始源码与解析值。** 若路由住在内联标记里：
   - **保存原始标签片段**
   - 与 parser 返回的属性值做对比
   - 查找断裂的 `&`、实体解码、或模板修复对路由造成的改写

   **本机做法**（仅示意，未对具体目标验证）：
   ```python
   # D:\EXE\python\python.exe —— 用标准库对同一属性做「原始片段 vs 解析值」比对
   from html.parser import HTMLParser
   # 1) 先用正则冻结原始片段
   # 2) 再解析出属性值
   # 3) 打印两者差异；不一致则以原始片段为准
   ```

5. **从线上链重建分页。** 偏好顺序：
   - **跟随当前页面暴露出的下一页目标**
   - 显式保留窄的路由家族例外
   - **只有当后续页面证明了它稳定之后**，才外推一个 URL 模板

## 高价值检查（High-value checks）

- 验证第一页与后续页是否使用了**不同的 host、path 或 query-based 路由**
- 验证下一条路由是否**只存在于内联 JavaScript 或隐藏的跳转模板里**
- 验证**重新解析页面**是否会改变参数名或 query 分隔符
- 验证晚期页的路由是否需要**不同的 referer、category 或 mode 状态**
- 验证这次路由切换是**单页例外**，还是**一个新稳定家族的开端**

## 判据（Verification checklist）

**「分页已解决」= 以下全部为真：**

1. **路由家族切换的位置已定位**：哪一页开始、切换前后的 URL 家族各是什么，有证据。
2. **真正的 pager 字段已被点名**：`href` / `onclick` / 自定义属性 / 隐藏模板 —— 不是「大概是某个属性」。
3. **原始 HTML 与解析值已实际比对过**，并明确判定**哪个是更安全的真相来源**。
4. **后续页面通过与前面相同的 collector 逻辑重放成功**，不是靠一条只对第 5 页生效的特判。
5. **路由家族例外是配置化的、窄的**（早晚期不同则分开配置），没有被扩展到全局。
6. **URL 模板的外推有后续页面证据支撑** —— 在此之前，collector **跟随线上链**。
7. **最终交付仍是无浏览器依赖的 Python collector**。

## 常见坑（Common traps）

- 从第一个 URL 猜页码，就宣称证明了整个序列
- 把分页当成**表现层**（presentation）而非协议
- 直接信任 DOM 解码后的 `onclick` 或自定义属性，**没和原始源码比过**
- 让 HTML parser 或 beautifier 在提取之前**重写了重放关键的 query 串**
- 把一次晚期页例外**泛化**成 collector 里每个请求的规则
- 只修了「页码」，没发现底层是**端点家族切换**（例：静态页 → `/ui`）
- 在拿到原始片段之前就信任了「看起来可读」的属性值

## 交付建议（Delivery guidance）

**首选交付形态：**

1. **沿真实 pager 链推进的 Python collector**
2. 早晚期不同时，对路由家族切换做**窄配置**
3. **最终路径无浏览器依赖**

## 交接最小笔记（Minimal handoff notes）

**显式报告以下各项：**

- 分页路由家族在哪里发生变化
- **哪个 pager 字段**才是下一页路由的真实来源
- **原始 HTML 还是解析后的 DOM** 是更安全的真相来源
- 后续页面需要哪条窄例外（若有）

## 相关（Related）

- `./page-specific-exception-playbook.md` —— 只有一页异常、但路由家族未变的情形
- `./decoy-and-real-request-playbook.md` —— 「页面写的路由不是真实路由」
- `./transport-wrapper-playbook.md` —— 下一页目标可能由 wrapper 改写产生
- `../principles/doctrine-index.md` —— **教条 13（分页是一个协议面）**、**教条 14（原始源码可能胜过解析后的 DOM）**
- `../deliver/delivery-gate-playbook.md` —— 第 20 条：collector 必须证明它承诺的分页边界
- `../deliver/pure-python-rebuild-playbook.md` —— 判据第 4 条：分页请求的序列化 roundtrip 无损

---

## 源文档勘误（改编时修正）

1. **源文档的 `Fast execution path` 第 4 步（比较原始源码与解析值）给了正确做法但没给工具**，读者拿到这一页往往直接跳过。改编在本机补入 Python 标准库做「原始片段 vs 解析值」比对的实际做法，并明确它不需要第三方包（避免读者以为要先装解析器）。
2. **源文档的 `When to route here` 第 4 条（内联 onclick / 隐藏模板携带真实下一页 URL）与第 5 条（DOM 解析值与原始 HTML 不匹配）其实有先后关系** —— 先要发现路由在原始标记里，才会去比解析值。改编保留两条但在步骤第 3、4 步里明确这个顺序。
3. **源文档的 `Common traps` 有五条，其中「assuming page arithmetic from the first URL proves the whole sequence」与 `Core idea` 的「分页是协议契约的一部分」是同一事实的两种表述。** 改编在判据第 6 条把「外推需有后续页面证据」变成硬要求，使它不再是重复陈述。
4. **源文档第 5 步写「only extrapolate a URL template after later pages prove it is stable」，但「stable」没有定义。** 改编在判据第 6 条明确：至少要「后续页面通过同一 collector 逻辑重放成功」（判据第 4 条），否则不算稳定。
5. **源文档的 `Delivery guidance` 第 1 条「Python collector that advances through the real pager chain」与 `Core idea` 的「follow the next-page target exposed by the current page」重复。** 改编保留前者为交付形态、后者为步骤顺序，角色分开。
