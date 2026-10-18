# U9 — 9 条过宽规则的机制层处置（wave 5 卡 L）

改前实测（`test-community-decoys.py --report`）：decoy 21/30 = 0.7000，
positive 27/27 = 1.0000，combined 48/57 = 0.8421。
改后实测：decoy **25/30 = 0.8333**，positive **27/27 = 1.0000**，
combined **52/57 = 0.9123**。门（0.50 / 0.75）未动。

## 机制总览

正解都在机制层，不在词表层：

1. **STOPWORDS 收敛（非 1.3 机制）**：`noise[]` 的"单来源 ≥80%"拦不住 36% 的
   真实词。`融合` 实测是 56/154 描述里的固定框式连接词
   （"融合 A + B"），零区分度（42 候选纯描述并列，path 首字母任意领先），
   且无任何记录以它为主题。STOPWORDS 无 80% 约束，是 capability/adapted
   （19%）先例的同一条路。
2. **Alias 族字面归属信号（新机制）**：`delivery/pipeline/devops/交付` 五个
   不同概念折叠进同一个 `alias_delivery` token，29 条记录同分并列时只能按
   path 首字母排，RAG pipeline 记录永远第一。修法不是拆 alias（会伤召回），
   而是给折叠命中做字面归属：裸词 hint 只靠折叠 token 命中时，+4 信号把
   top 还给字面拥有者（197/188/215）。新增 3 条 signals，全 `evidence_kind: raw`，
   逐条有本目录原文证据（devops 多文件 / pipeline 模板 / delivery+交付 13 次）。
3. **登记为不可修的（5 条）**：见下表，原因都是"任何确定性排序都只是把红点
   搬到下一条 path 排序的记录"，或"目标词是记录正文里的真领域词，停掉它
   是杀伤召回"。

## 逐条结论

| # | 用例 | 结论 | 机制 |
|---|---|---|---|
| 1 | governance-fusion-cjk（融合） | 修好 | STOPWORDS +1（融合）。hint → missing_input，无 wrapper 应答 |
| 2 | governance-word-governance | 登记不可修 | 义项碰撞：目标记录（defi-attack-patterns）正文 "governance exploits" 是真 DeFi 领域词；1 条记录不满足 noise 1.3，停词会杀伤 "governance takeover" 类合法多词查询 |
| 3 | governance-word-wrapper | 登记不可修 | 同上结构：path-traversal 记录正文 "wrapper behavior" 指 PHP stream wrappers，是真领域词；按 DEFECTS 登记口径，本用例编码的是比"错"更严的标准 |
| 4 | alias-delivery-word（delivery） | 修好 | 信号→215（e2e-feature-delivery，slug 字面拥有 delivery）。top 从 RAG 纠为 215 |
| 5 | alias-pipeline-word（pipeline） | 修好 | 信号→188（ci-cd-pipeline，全篇主题 + 模板证据）。top 从 RAG 纠为 188 |
| 6 | alias-devops-word（devops） | 修好 | 信号→197（devops-engineer，path+正文多文件拥有，RAG 目录 0 次）。top 从 RAG 纠为 197 |
| 7 | alias-delivery-cjk（交付） | 登记不可修（wrapper 层）；reference 层已归位 | 信号已把 top 从 RAG 纠为 215（端到端功能交付，正当答案）；但 29 候选全在同一 wrapper，wrapper 级"不得领先"断言任何排序都满足不了，只能靠停词（missing_input）转绿——那会删掉刚归位的正当 top，拒绝以压制正确召回换绿 |
| 8 | hypernym-endpoint-top | 登记不可修 | 裸上位词 11 候选描述并列（多条经复数折叠，score=0），每条都合法含词，无证据偏向任一 leader；重排只是把红点搬到下一条 path 记录 |
| 9 | hypernym-application-top | 登记不可修 | 同上，14 候选，Android 记录仅凭一条描述提及领先；裸词无所属答案，缺排序所需的 relevance 模型 |

`s3 bucket`（absence-s3-bucket）：正确行为，保持通过，未动（语料 293 条无
S3/对象存储技能，按 1.2 不得编造关键词）。

## 有意不用的方向

- 来源一致性判据扩展（如把 1.3 从 80% 下调到 30% 收编融合）：会把"半个来源
  的习惯用词"写成全库噪声，污染面不可控；STOPWORDS 已覆盖该case 且无此副作用。
- 权重/归一化调整（名字 ×3 / 描述 ×1）：9 条里 5 条是描述并列、4 条是名字
  同分，调权重改变的是两类命中的相对位置，动不了同类内的任意领先；且冻结
  权重是 T26 合同，不碰。
- 别名族共用 token 之外再拆 alias（如把 pipeline 移出 delivery 族）：RAG 记录
  slug 字面含 pipeline，拆完仍是名字命中并列，top 不动；白伤中文交付类召回。
- 上位词/下位词区分：语料无类目记录可承接上位词，无处可分；登记。

## 复现

```text
$env:PYTHONIOENCODING='utf-8'
& (Resolve-ReverseToolSpec -Name 'pyre').Command skills\scripts\test-community-decoys.py --report
& (Resolve-ReverseToolSpec -Name 'pyre').Command skills\scripts\verify-routing-signals.py
& (Resolve-ReverseToolSpec -Name 'pyre').Command skills\scripts\test-routing-signals.py
& (Resolve-ReverseToolSpec -Name 'pyre').Command skills\scripts\test-route-ranking.py
& (Resolve-ReverseToolSpec -Name 'pyre').Command skills\scripts\test-community-route.py
```
