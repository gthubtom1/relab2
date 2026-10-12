# 反例底册：diff-runner 的 input= 前缀剥离缺口

> 本文件是卡 `diff-runner-input-prefix-only-stripped-in-update-mode` 的 fixture（无秘密）。
> 观测命令见各节；旧版本 = commit f0b26f5 的 `skillpack/skills/scripts/diff-runner.py`，
> 新版本 = 2026-10-13 工作区（assault 模式加入时统一）。

## 复现 1（真实 case，CLI 层）

case：`work/assault-prng-upx`（assault 预设，2026-10-13）。

assault.md 的登记行：

```
- cases:
  - F-001 | input=0
  - F-002 | input=1
```

首跑命令（修复前）：

```
python skillpack/skills/scripts/diff-runner.py work/assault-prng-upx --assault --function F-001
```

观测（diff/F-001.md 草稿原文，修复前）：

```
| F-001 | input=0 | 7584<br>19164<br>... | Traceback (most recent call last):
  File "...\build\prng_rebuilt.py", line 31, in main
    mode = int(argv[1]) if len(argv) > 1 else 0
ValueError: invalid literal for int() with base 10: 'input=0' | PENDING | exit 0 vs 1 |
```

结论：新实现收到了字面量 `'input=0'`——`input=` 前缀没有被剥离。
修复并重跑后：两段原始 stdout 逐字节相同（79B=79B）、exit 0=0。

## 复现 2（函数层，确定性）

同一行 `- F-001 | input=0` 分别喂给旧/新两个版本的三处解析函数：

```
[OLD parse_rebuild]  ['input=0', 'input=1']   <- 未剥离
[OLD parse_update]   []                        （update 走表格行格式，此探针不适用）
[NEW parse_rebuild]  ['0', '1']                <- 已剥离
[NEW parse_assault]  ['0', '1']                <- 已剥离
[NEW parse_update]   []
```

生成脚本：把 `git show f0b26f5:skillpack/skills/scripts/diff-runner.py` 与工作区版本
分别 import，对同一 probe case 调 `parse_rebuild` / `parse_assault` / `parse_update`，
对比 `cases` 值列表。两次观测相互独立（一次经 CLI 真实驱动，一次纯函数对照）。

## 修法

剥离逻辑做成三支解析共用的入口（工作区版本在 `parse_rebuild` / `parse_assault` 内
各加同款剥离，与 `parse_update` 原语义对齐）；**不要**在单支上补丁。
