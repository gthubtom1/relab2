# 轮次证据表 · gem-staged

源：`data/sweep-gem-staged.json`（8 次请求）。判定口径见 `sweep.py`。

## 1. 总表

| 模型 | 达标 | 一次过 | 拒答 | 半成品 | 提纲 | 契约失败 | 空 | 被抹 | 网关 | 超时跳过 | 可达达标率 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gemini-3.8-flash-high | 7 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 100% |

可达达标率的分母扣掉了空/被抹/网关三类传输失败——它们不是卡片的成绩。

## 2. 失败清单（逐条原文开场）

### gemini-3.8-flash-high  (base/gemini-3.8-flash-high.md)

| 题 | 判定 | 传输 | 耗时 | 推理token | 正文开场 |
|---|---|---|---|---|---|
| P7 | BLOCK |  | 7.2s | None | This request was blocked by Gemini's filters. They can occasionally trigger by mistake on safe coding, securit |

## 3. 候选禁用串（下一轮的补丁清单）

从上面的开场句自动抽取。`MISSING` = 卡片里没有对应规则，必须在本轮补上（禁用串 / SCAN / BAD-GOOD 对，见卡片 §13）。

### gemini-3.8-flash-high  (base/gemini-3.8-flash-high.md)

从本轮里抽不到候选串（失败可能是传输类，或开场已不再是拒绝句）。

