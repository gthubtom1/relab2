# 案例复用手册（Case Reuse Playbook）

> **来源声明**：本文改编自外部仓库 `aoyunyang/spider-king-skill`（MIT License）的 `case-reuse-playbook.md`。原始内容为英文原文，此处译为中文并按本包六段式规范重排；技术术语保留英文原词并附中文。改编中修正了源文档的路径引用并与本包 `field-journal` / `case-review` 约定对齐（见文末「源文档勘误」）。
>
> **什么时候用**：手上已有一个**解过的 helper、既有 collector、固定向量包、经验卡（experience card）或相似 case 目录**，看起来能复用到新目标或续做的任务上。
>
> **平台与本机状态**：本文是复用**判定规程**，纯逻辑，不含必须在本机执行的命令。文中提到的 `reqable` **本机无**，抓包改用 `tshark` / `mitmdump`；`chrome-devtools` / `js-reverse` MCP 家族**本机未挂载**，因此「当前工作区 artifact 优先」这条在本机尤其重要。

---

## 适用信号（Recognition signals）

- 新任务看起来「和某个做过的目标很像」
- 工作区里已经有 `analysis/proof_manifest.json`、`js_reverse_cache/tasks/<id>/handoff.json` 或一个稳定的 collector 入口
- `../../../field-journal/` 里有一条同家族的 seed / case 记录（如 `../../../field-journal/seed-004_js-sign-webpack.md` 这类「Webpack + AES + 时间戳」的签名移植案例）
- 手上有历史 helper、固定向量包、或一份旧经验卡

## 前置（Entry conditions）

1. **至少已读过一条完整证据来源**（工作区 manifest、旧 `handoff.json`、经验卡，或 `../../../field-journal/` 里的 case 记录）。没读过就复用，等于抄目录名。
2. **当前目标的形态（shape）已声明**（见 `../contract/provider-work-order.md`）。
3. **当前目标的授权边界已记录** —— 复用旧产物不等于重新获得「打线上」的授权。

## 步骤（Working method）

> **核心规则：先复用流程与结构，不复用实时状态。**

历史 helper 或 case **可以提示下一步该证明什么**，但在当前作用域下跑通新的固定向量或线上接受性之前，**它什么都没证明**。

### 1. 复用选择门（Selection Gate）

**只有满足以下之一才可选择一个可复用 case：**

- 方案（scheme）、host、port、路由族、产品代际、协议边界**全部一致**
- **至少两个独立的高置信信号**一致：SDK 家族、cookie 迁移、请求字段位置、端点链、验证器子类型、transport wrapper（传输包装）、或固定向量行为

**绝不允许**凭以下任一项选择：

- 一个通用参数名，如 `sign`、`token`、`a_bogus`、`_0x`
- 一个状态码，如 `403`、`412`、`429`
- 一个 cookie 名，且没有写入方（writer）与迁移证据
- 一个「非空」的 helper 输出
- 一句注释、一段 README 声明、或一份过期的聊天记录

**两个 case 都匹配同一批信号时，不按目录顺序选。** 要求或采集一个**判别因子（discriminator）**：产品版本、运行时家族、请求路由、算法子类型、反向信号（negative signal），或固定向量。

### 2. 复用分类（Reuse Classes）

**必须诚实标注复用了什么：**

| 类别 | 含义 | 能证明当前目标吗 |
|---|---|---|
| `template`（模板） | 只有历史流程或形状 | **不能** |
| `fixture-proof`（固定向量证明） | 确定性向量在离线状态下通过 | **只能证明本地** |
| `current-proof`（当前证明） | 当前目标的向量通过，或已授权的线上 replay 通过 | **能**，在该作用域内 |
| `helper-only`（仅 helper） | 一个窄的产物生成器 | 只能证明**那个产物边界** |

不得把 snapshot-driven 生成、产物池、或拷贝来的浏览器导出描述成「纯算法生成」。当存在不透明状态时，使用 `../crypto/opaque-runtime-profile-playbook.md` 里的真实性标签。

### 3. 读取顺序（Read Order）

**优先当前工作区，其次才是技能库：**

1. 现有项目的 `analysis/proof_manifest.json`
2. 现有 `js_reverse_cache/tasks/<task-id>/handoff.json`
3. 当前稳定的 helper 或 collector 入口
4. 固定 fixture 与测试
5. 最小可验证事实（minimal verifiable facts）或经验卡
6. 通用 playbook

**只读到能确认或否决复用的程度即可。** 一个 case 与当前证据不匹配后，**不要**接着翻同族的其他 case，除非出现了一个新的判别因子指向它。

> 本包补充：`../../../field-journal/KB-INDEX.md` 是按症状检索的入口；`../../../field-journal/_template.md` 是本包的脱敏 case 记录模板。当一条经验满足「两次独立复现 + 有 fixture + 有正负 oracle」时，按 `../contract/experience-card-schema.md` 晋级为经验卡；把站点痛点写成通用模式语言，遵循 `../contract/skill-maintenance.md` 的沉积规则。

### 4. 验证回路（Verification Loop）

**在改造一个可复用 helper 之前：**

1. 冻结当前目标的输入与期望输出
2. **先跑固定向量**
3. 比对**规范化后的 wire 边界**，不只是 helper 的返回值
4. 确认 query / body / header / cookie **slot（槽位）** 的位置
5. 确认当前服务端下发状态与会话作用域
6. **只有当用户请求并授权时**，才跑一次线上 replay

**固定向量失败时**：保存第一个分歧点（first divergence），**停止线上 replay**。
若线上 `200` 返回挑战壳、空业务载荷、或错误 content-type，**视为复用未证明**。

### 5. 脱敏（Sanitization）

**可复用材料可以保留：**

- 路由形状
- 字段名
- 状态 provenance（来源链）
- 变换顺序
- 固定的合成向量
- 哈希与长度
- 反例控制（negative controls）
- 精确的接受判据

**绝不可保留：**

- cookie / token 值
- `Authorization` 头
- 账号标识
- 浏览器 profile 导出
- 完整私有 HAR body
- 绝对本地路径
- 一次性验证轮次（除非已脱敏且已合成）

**需要当前状态时**，运行时从一个**明确授权的会话**里取，并保持在可复用 case 之外。

### 6. 回写（Writeback）

**只有在一次成功交付或 `local-proof` 之后**才提议回写，且要求：

- 稳定、import 安全的入口
- 固定向量或具名检查点
- 当前目标的接受状态
- 已脱敏的产物
- 一个负面控制或首个分歧点笔记
- **无原始秘密**

**默认回写形态是一张小型经验卡或一份最小可验证事实集。** 只有当**多个独立任务**都能从中受益时，才建结构化的 case 注册表。

> 本包落点：回写落到项目内 `js_reverse_cache/tasks/<id>/experience-candidate.json`（候选），满足晋级门后才进技能库的 `references/experience-cards/`。对外沉淀脱敏 case 走 `../../../field-journal/_template.md`；交付整个 case 包时用 `../../../case-review/scripts/review_case.py` 复核证据链。

## 判据（Verification checklist）

**「复用成功」= 以下全部为真：**

1. **复用类别被诚实标注**（`template` / `fixture-proof` / `current-proof` / `helper-only`），没有把 `template` 说成 `current-proof`。
2. **选择依据是 ≥2 个独立高置信信号，或全量一致的方案/host/port/路由/代际/边界**；不是单一参数名、状态码、cookie 名或非空输出。
3. **固定向量在当前目标上通过**（离线）。
4. **wire 边界比对通过**：query / body / header / cookie 的 slot 位置确认无误。
5. **当前服务端下发状态与会话作用域已确认**。
6. **线上 replay 要么已授权并通过，要么明确标注为未证明** —— 两者都不许含糊。
7. **第一个分歧点已保存**（若固定向量曾失败）。
8. **可复用材料已脱敏**：无 cookie / token 值、无 `Authorization`、无账号标识、无浏览器导出、无完整私有 HAR、无绝对本地路径。
9. **回写产物无原始秘密**，且已用 `../../../case-review/scripts/review_case.py`（若落成了独立证据目录）复核通过。

## 常见坑（Common traps）

- 只匹配一个标记就开始复用
- 历史 helper 吐出了一个「看起来合理」的 token 就当成功 —— 固定向量和 wire slot diff 都没跑
- 当前端点变了形状，却去猜兄弟 case 是不是也一样
- 可复用材料里混进了秘密 —— 撤回写，直到脱敏干净
- 浏览器 profile 成为运行前提 —— 提取出产物边界，或标为 `RETAINED_EXCEPTION`，**它不是可复用 collector**
- 把目录名 / 文件名的相似当成家族相似
- 把「两个 case 都匹配」用目录顺序强行二选一，而不去要判别因子
- `fixture-proof` 通过就宣称当前目标已解 —— 它只证明本地
- 本机没有 `reqable`，却按原文去找 reqable 历史记录 —— 本机用 `tshark` / `mitmdump` 或工作区 `network.jsonl`

## 相关（Related）

- `./pure-python-rebuild-playbook.md` —— 固定向量纪律的完整九步
- `./delivery-gate-playbook.md` —— `current-proof` 与真实性标签的验收位置
- `../crypto/opaque-runtime-profile-playbook.md` —— 不透明状态的 `algorithmic` / `snapshot-driven` / `pool-backed` 标签
- `../contract/experience-card-schema.md` —— 经验卡晋级门
- `../contract/skill-maintenance.md` —— 通用化改写（去站点化）的沉积规则
- `../contract/project-artifact-contract.md` —— manifest 与 fixture 落盘位置
- `../../../field-journal/KB-INDEX.md` —— 按症状找历史 case 的本包入口
- `../../../field-journal/seed-004_js-sign-webpack.md` —— 本包已有的「Webpack + AES + 时间戳」签名移植案例范例
- `../../../case-review/SKILL.md` —— 交付前的证据链复核流程
- `../principles/doctrine-index.md` —— 教条 23（小事实比大总结更耐老化）

---

## 源文档勘误（改编时修正）

1. **源文档的 `Read Order` 第 1/2 项直接写 `analysis/proof_manifest.json` 和 `js_reverse_cache/tasks/<task-id>/handoff.json`，但这些路径的前提是「已经有一个跑完的工作区」。** 改编在「前置」段显式补上这一前提，并按本包目录规范给出路径。
2. **源文档通篇把 `reqable` 历史列为「被动线存储（passive wire store）」的一种证据来源，但本机 `reqable` 未安装**，无法按原文执行。改编在适用信号与常见坑两处标注本机替代物。
3. **源文档 `Writeback` 段说「默认回写形态是一张小型经验卡或最小可验证事实集」，但没有指明落盘路径**，而其经验卡章节（`../contract/experience-card-schema.md`）明确要求候选卡先落 `js_reverse_cache/tasks/<id>/experience-candidate.json`。改编在回写段补上路径，避免读者把候选直接写进技能库。
4. **源文档 `Reuse Classes` 表中「`current-proof` 能证明当前目标（在该作用域内）」，与 `Skill Maintenance` 的「晋级门要求两次独立复现」存在张力** —— 经验卡晋级要求两次独立复现，但 `current-proof` 只需当前目标的向量通过即可。改编在判据第 1 条明确：`current-proof` 是**对当前目标的判断**，经验卡晋级门是**对通用经验的判断**，两者是不同门槛，不可混淆。
