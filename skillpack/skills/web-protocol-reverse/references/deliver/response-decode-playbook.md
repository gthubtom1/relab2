# 响应解码手册（Response Decode Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `response-decode-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。源文档为短篇，改编补齐了判据段（本包硬性要求）。
>
> **什么时候用**：响应体返回 `200` 但**读不懂**；或者数据只有经过一层 decode helper（解码辅助）、字形图（glyph map）、protobuf parser（解析器）或解压器才出现。
>

---

## 适用信号（Recognition signals）

- 响应是 `200`，但 body（响应体）无法阅读
- 有用数据只在 decode helper、字形图、protobuf parser 或解压器跑过之后才出现
- **原始载荷（raw payload）、解析后载荷、最终业务数据**明显是三个不同阶段
- 长数字串、字形、转义 Unicode、或看起来像二进制的字节
- 响应处理函数在碰到业务字段之前先走了一串 helper 调用
- 网络 body 稳定，但可见数据依赖本地解码步骤
- **Content-Type 与实际载荷形状对不上**

## 前置（Entry conditions）

1. **必须能拿到未经任何改写的原始响应体。** 拿不到就不要开解码工作 —— 见「常见坑」第一条。
2. **至少有一个「解出来了」的对照样本**（页面上看到的正确值，或一份已知明文），否则你无法判断解码是否正确。
3. **抓取手段**：本机两条路都可用：
   - 从浏览器/wire 抓：`tshark -r <pcap> -T fields -e data.data` 或直接用 mitmproxy 落流
   - 若目标已授权 live replay：`requests` / `curl_cffi`（本机 0.16.3 可用）直接取 body，落盘为二进制文件
4. **落盘位置**：按 `../contract/project-artifact-contract.md`，原始载荷属于 volatile evidence（易失证据），放 `<project>/js_reverse_cache/tasks/<task-id>/`，**不要**写进本技能包目录。

## 步骤（Working method）

> **核心规则：在碰解码器之前，先把原始载荷冻结下来。**

1. **保存精确的原始载荷**（bytes，不是 re-save 过的字符串，不是 base64 后的文本）
2. **找出这份原始载荷的第一个消费者**（谁第一个读它）
3. **按顺序追解码链**：
   - 解压（decompression）
   - Base64 或字母表转换（alphabet conversion）
   - 字节 / 字符重映射（byte or char remapping）
   - protobuf / msgpack / JSON 解析
   - 字体或字形翻译（font or glyph translation）
4. **逐层在本地重建** —— **一层一层来**，不要跳
5. **在放大规模之前，先在捕获的载荷上验证本地解码**

**顺序纪律**：上表不是「固定要按这个顺序」，而是**排查顺序**。实际链路可能是「注入后再摘要 → 压缩 → 字母表替换 → protobuf」，也可能完全不同。**以捕获的字节和运行时实际使用的解析器为准**，不要拿这张表当规格。

**本机解码器的落地形态**（**未在本机对具体目标验证**，仅为依赖选择参考）：

```powershell
# 纯 Python 优先：protobuf / msgpack / zstd 都有现成库
& (Resolve-ReverseToolSpec -Name 'pyre').Command -c "import google.protobuf, msgpack; print('ok')"
```

若某层确实只有 JS 实现、短期内移植不划算，可保留一个**极窄的本地 helper**（交付门 `algorithmic` 标签与 `runtimeFree: false` 必须如实标注）—— 但它**不得**需要浏览器。

## 判据（Verification checklist）

**「响应解码完成」= 以下全部为真：**

1. **原始载荷已冻结并落盘**，字节级完整，可重放出同样的哈希。
2. **解码链的每一层都被显式命名**（哪一层做什么），没有「黑箱一步到位」。
3. **最终解码在 Python 本地完成**，或明确标注为一个不读浏览器上下文的窄 helper；**不得**需要浏览器渲染或页面上下文才能读载荷。
4. **至少一个已知对照样本上解码正确** —— 逐字段比对，不是「看着像」。
5. **至少两个不同载荷上验证过** —— 只在一个幸运载荷上验证过不算数。
6. **有一个负面边界（negative boundary）**：故意破坏一个字节/一个字段，解码必须以可解释的方式失败，而不是静默返回垃圾。
7. **原始载荷、解析后载荷、最终业务数据三个阶段都在产物中被区分记录**（不是只留最后一个）。

## 常见坑（Common traps）

- 在浏览器**已经把响应改写之后**才去解码，而不是从原始载荷解
- 跳过中间层，直接猜最后一层 parser
- 载荷其实是**重映射**或**压缩**，却被当成「加密」去硬解 AES
- 只在一个幸运载荷上验证
- 把解码器和「谁调用它」混在一起 —— 解码对了但 slot（位置）不对，仍会失败（参见 `../observe/transport-wrapper-playbook.md`）
- 以为解压顺序固定 —— 实际可能是「先解压再解码」或反过来，**以运行时解析器为准**
- 载荷开头有 prefix（非零起始偏移）时，直接从第 0 字节解；**前缀剥离本身就是协议的一部分**，不是解析器的脏活（见 `../principles/doctrine-index.md` 教条 12）
- 本机没有 `reqable` 却照抄原文的 reqable 导出流程 —— 本机用 `tshark` / `mitmdump`

## 相关（Related）

- `./delivery-gate-playbook.md` —— 第 5 条「decode 路径本地化」的验收位置
- `./pure-python-rebuild-playbook.md` —— 解码器本身的纯 Python 移植九步
- `../observe/structured-transport-playbook.md` —— protobuf / msgpack / gRPC 帧层的专门手册
- `../observe/transport-wrapper-playbook.md` —— 「解码对了但放在错误的 slot」
- `../state/challenge-state-envelope-playbook.md` —— 响应里带挑战子码/种子时的刷新契约
- `../principles/doctrine-index.md` —— 教条 12（包封装与密码学是两套独立契约）
- `../contract/report-templates.md` —— 报告里如何记录解码链与原始载荷哈希

---

## 源文档勘误（改编时修正）

1. **源文档没有判据段。** 本包硬性要求判据不能空，改编补入 7 条可检查的完成条件，其中第 6 条（负面边界）是从源文档「Common traps」里的「只在单个载荷上验证」反向提炼的。
2. **源文档「Working method」第 3 步把解码链写成一个有序列表**（解压 → Base64 → 重映射 → protobuf → 字体），容易被读成**固定规格**。但同文档的「Common traps」又说「以为响应是加密、其实只是重映射或压缩」—— 两处叠加会强化「顺序固定」的误读。改编在步骤段显式声明这是**排查顺序**，实际顺序以捕获字节和运行时解析器为准。
3. **源文档标题是 `Response Decode Playbook` 但正文小节名用的是 `Acceptable handoff`。** 改编统一并入「判据」与「相关」两段。
4. **源文档 `Acceptable handoff` 允许「Python + tiny local helper」**，但没说它不得读浏览器上下文。改编在判据第 3 条补上这一约束，与交付门对齐。
