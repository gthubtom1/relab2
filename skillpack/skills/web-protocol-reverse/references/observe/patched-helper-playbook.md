# 补丁化 Helper 手册（Patched Helper Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `patched-helper-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。源文档为短篇，改编补齐了前置与判据段（本包硬性要求）。
>
> **什么时候用**：**helper 名字看起来标准，但输出和标准库对不上**。
>

---

## 适用信号（Recognition signals）

- 函数名叫 `md5`、`btoa`、`atob`、`sha1` 之类，**但行为古怪**
- 本地复现**总是失败**，尽管 helper 名字看着眼熟
- 输出**字符集**与标准 Base64 不同
- 摘要**既不匹配标准 MD5 也不匹配任何 SHA 家族**
- 输出**长度或填充规则**与标准实现不符
- helper **依赖 DOM 状态、旁路脚本、或奇怪的查表**

## 前置（Entry conditions）

1. **有一个固定的输入**，例如字符串 `"abc"` 或一个捕获的时间戳。**没有固定输入就没有判据。**
2. **有浏览器/页面的真实输出**作为对照（Doctrine 3：固定输入验证胜过命名）。
3. **有一个本地候选实现**（哪怕只是个占位）用于对比。

**本机两个固定输入的建议向量**（**未在任何目标上验证**，仅作为流程示例）：

```powershell
& (Resolve-ReverseToolSpec -Name 'pyre').Command -c "import hashlib,base64; print(hashlib.md5(b'abc').hexdigest()); print(base64.b64encode(b'abc'))"
```

## 步骤（Working method）

> **核心规则：名字不证明行为。固定输入验证才证明。**

### 最小验证循环

1. **选一个固定输入**，例如 `"abc"` 或一个捕获的时间戳
2. **记录浏览器/页面输出**
3. **运行本地候选实现**
4. **比较中间状态**，以及最终输出
5. **然后**才决定这个 helper 是标准的、被补丁过的、还是完全定制的

**第 4 步是本文的关键，也是最常被跳过的一步。** 只比最终输出，你分不清「编码错」和「前置规范化错」；中间值对不上才能定位到具体哪一层。

### 常见的「被补丁」迹象

- 输出字符集与正常 Base64 不同
- 摘要既不匹配标准 MD5 也不匹配 SHA 家族
- helper 使用 DOM 状态、旁路脚本，或异乎寻常的查表
- 输出长度或填充规则与标准实现不同

**「依赖 DOM 状态」这一条需要区分**：如果 helper 真的读 `document` / `navigator` / `screen`，那它**不是**「被补丁」，而是**宿主依赖**——那是 `../crypto/iv8-runtime-cheatsheet.md`（**iv8 本机无**）或 `../../profiles/env-patch/index.md`（Node 路径）要处理的问题。**不要**把它当成「补丁」去硬写 Python。

## 判据（Verification checklist）

**「helper 性质已判定」= 以下全部为真：**

1. **至少一个固定输入**上有浏览器输出与本地输出的成对记录。
2. **中间状态被比较过**，不只是最终输出。
3. **helper 被明确归类**为：标准 / 被补丁 / 完全定制 —— 三选一，不能悬置。
4. **若归类为「被补丁」**：字符集、长度、填充规则三项差异已被记录。
5. **若 helper 有宿主依赖**：该依赖被显式命名为宿主面（`document`/`navigator`/`screen`/定时器），**不被误报为「补丁」**。
6. **collector 随附固定输入自检（fixed-input self-checks）**，使站点日后变化时**响亮地失败**，而不是静默产出错误签名。

## 常见坑（Common traps）

- 相信名字，跳过固定输入验证（Doctrine 3）
- 只比最终输出，漏掉中间状态
- 把「宿主依赖」误判为「补丁」，于是把浏览器语义硬塞进 Python
- 采信了 SDK 里那个**只在某个从未触发的 flag 下运行**的分支（见 `./dual-writer-param-playbook.md`）
- 用一个「看起来合理」的 token 形状代替固定输入验证
- 自检只覆盖**成功路径** —— 站点变化时应该失败的输入没被覆盖
- **本机补充**：期待 `iv8` 可用来跑这个 helper —— **本机无**

## 相关（Related）

- `../principles/doctrine-index.md` —— **教条 3（固定输入验证胜过命名）**，本文是它的落地手册
- `../deliver/pure-python-rebuild-playbook.md` —— 判定之后，下一步是九步纯 Python 重建
- `./dual-writer-param-playbook.md` —— 「SDK 源码里的分支可能从未运行」
- `../../profiles/env-patch/index.md` —— 确认是宿主依赖时，Node 侧的定点改写路径（本机 `node v24.20.0` 可用）
- `../crypto/iv8-runtime-cheatsheet.md` —— **iv8 本机无**，该文档形态**未在本机验证**
- `../crypto/offline-inline-deob-playbook.md` —— 先离线还原，再谈性质判定
- `./transport-wrapper-playbook.md` —— 「值对」之外的「slot 对」

---

## 源文档勘误（改编时修正）

1. **源文档的 `Common signs of patching` 第 3 条「the helper uses DOM state, side scripts, or odd lookup tables」把两类不同问题混为一谈。** 「奇怪的查表」确实是补丁迹象；但**依赖 DOM 状态是宿主依赖（host dependence），不是补丁**——它的解法路线完全不同（一个要写 Python，一个要补宿主语义）。改编在步骤中显式拆分这一条，并在判据第 5 条把它变成必须点名宿主面的检查项。源文档未做此区分，是本篇最容易被误用之处。
2. **源文档的 `Delivery rule` 只说「ship fixed-input self-checks with the collector」，没说什么样的自检才算数。** 一个只跑成功路径的自检，在站点变化时会**静默通过**，起不到「响亮失败」的作用。改编在判据第 6 条要求自检必须覆盖**应当失败的输入**。
3. **源文档的 `Minimum validation loop` 第 4 步说「compare intermediate states as well as the final output」，但没解释为什么。** 只比最终输出时分不清「编码错」和「前置规范化错」，这是调试成本差异极大的一处。改编在步骤第 4 步后补上了这个理由，使它不是一条容易被跳过的建议。
4. **源文档只有 30 行且无前置、无判据**，作为独立手册无法验收。改编补入前置 3 条（含一个本机可跑的基线向量命令）与判据 6 条。
