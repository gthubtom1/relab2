# Source bundle 与可离线复核的 attestation（T12+T14）

依据：规范第 12 节 T12、第 18 节 T14、第 17.26 / 17.28。
工具：`scripts/verify-source-attestation.py`、`scripts/verify-community-bundle.py`。
锁：`skills/community/source-lock.json`（`schemaVersion 1.0`）。

## 1. Bundle 成员（provenance 复核所需的全部输入）

```
community-raw/                        raw vendor 内容（发现根之外）
docs/community/<source-id>/           上游支持文档（4 个目录）
docs/community/CANONICAL-BASE-LOCK.md#attestation  母框架 base 摘要指针（第 5 条，不另存大 manifest）
skills/community/registry.json        登记表（owner T02，本卡只读）
skills/community/source-lock.json     本卡的锁：5 条 source attestation + registry 期望计数
```

五条 source：`ctf-super-hub`、`hack-skills`、`ai-fullstack-delivery`、`apk-reverse-community`
（4 个 community 源）+ `reverse-skill`（`source_kind = canonical-base` 母框架，T21 交付、
T21b 独立重算；`scan` 为快照根 `.`、`.git` 计入摘要）。
上游快照在仓库外的 `../upstream/<repo>`（只读），`scan` 子目录与 pin commit 见锁。

## 2. Digest 口径（冻结，不另发明）

以 `docs/community/IMPORTER-LIFECYCLE.md` §4 与 `scripts/adapt-community.py`
的 `DIGEST_CONTRACT_VERSION = "skills-hub/importer-digest/1"` 为准：

```
file line : b"f" NUL <path> NUL <content_sha256_hex> LF
dir  line : b"d" NUL <path> NUL LF
file_manifest_digest = sha256(排序后 file lines 串接)
tree_digest          = sha256(排序后 file+dir lines 串接)
```

`<path>` 为 NFC 规范化 POSIX 相对路径；文件内容 `sha256` 前把 CRLF 折叠为 LF
（孤立 CR 保留）；manifest 文本 LF；mode/uid/gid/mtime/inode/Windows 属性位不参
与；symlink 记录 `type=symlink` + link target 字符串、不贡献字节。

口径说明：任务卡片正文把该契约转述为"逐文件 `sha256(raw_bytes)`，不做行尾转
换"，与冻结契约（CRLF→LF 折叠，见 WORK-BOARD E16：不折叠则 Windows/Linux/no-git
结果不一致，违反 17.26）不一致。**以冻结契约为准**，两脚本与锁均按折叠口径实
现并与 `adapt-community.py` 的 `digest_of_tree` 实测一致（4 快照 live-checked）。

基线对账：`work/baseline-digest.json` 的 `file_manifest_digest = 6f57b141…f17` /
`tree_digest = d258ddc0…a30b` 是针对 `c9b8303` 的 1111 个覆盖路径（导入器写入
面），不是 per-source 上游摘要；两者口径同一契约，覆盖集合不同，不要直接比对。

## 3. Attestation 十字段（17.28，每条 source 全部产出、导入前校验）

`upstream_url`、`resolved_commit`（40 位 hex，且 `git cat-file -e` 可解析）、
`default_branch_commit`（离线记 `null` + 显式 note，不编造）、
`origin_head_commit`、`dirty`（必须 `false`）、`tree_digest`、`file_manifest_digest`、
`fetched_at`（UTC RFC 3339）、`fetch_tool_and_version`、`attestation_method`
（`git-commit`）。锁另带 `pinned_commit`、`file_count`、`dir_count`、
`snapshot_rel`（相对路径，跨机器可移植）。

当前实测（2026-09-30T19:04:00Z，4 快照全 clean、HEAD 与 pin 一致、可解析）：

| source | files | dirs | file_manifest_digest（前 12） | tree_digest（前 12） |
|---|---|---|---|---|
| ctf-super-hub | 215 | 62 | `eb0977b3a789` | `03e9f6bf5a95` |
| hack-skills（scan `skills`） | 166 | 103 | `56a497d85286` | `40367cf305f2` |
| ai-fullstack-delivery（scan `workflows`） | 998 | 587 | `5a3f3e4d80d0` | `3dbbea82d5b1` |
| apk-reverse-community（scan `skills/apk-reverse`） | 114 | 7 | `f3dbb21f8891` | `8c7644aed787` |
| reverse-skill（canonical-base，scan `.`、`.git` 计入） | 627 | 295 | `05a9e63c3eef` | `e04b0b454e52` |

合计 2120 个扫描文件（1493 社区 + 627 母框架，symlink 0）。每个数字可用 `verify-source-attestation.py` 重算；
base 一行另可用 `scripts/verify-canonical-base-lock.py --json` 的 `recomputed` 交叉核对
（T21b 已用独立实现重算：627 / 295 / 0 与上表完全一致，见任务回报 MEASUREMENT）。

## 4. 离线复核（T12 验收：复制体单独可复核）

```powershell
$env:PYTHONIOENCODING='utf-8'
# 把 integrated-skill-hub 复制到任何位置（不需要 .git，不需要 ../upstream）
& (Resolve-ReverseToolSpec -Name 'pyre').Command scripts\verify-source-attestation.py
& (Resolve-ReverseToolSpec -Name 'pyre').Command scripts\verify-community-bundle.py
```

有快照时两脚本 exit 0；复制体旁没有 `../upstream` 时 attestation 脚本 exit 10，
并具名报出不可核对项（见 §5），bundle 脚本对 sources 本身仍全量复核。
这正是 HANDOFF §2.1 那条验收项的落点：`verify-triage-lock.py` 在克隆体降级为
10 是因为"声称的上游路径是否真实存在"无法核对——本卡把同一降级语义做进
source attestation，且锁摘要本身在复制体里仍可验证。

## 5. 降级表（哪一项不可核对、为什么）

| 缺失 | 不可核对的项 | 仍可核对的项 | 退出码 |
|---|---|---|---|
| 无 `../upstream` | 快照存在性、HEAD 是否等于 `resolved_commit`、commit 可解析性、`dirty` 实测、digest 重算 | 十字段格式、`resolved_commit == pin`、`dirty == false` 记录值、digest 格式、大小写冲突（fallback 扫 `community-raw/`）、registry schema 与计数 | 10（逐条具名） |
| 无 `.git` | bundle 自身 commit pin | 上表全部 + bundle 成员完整性 | 10（具名一项） |

## 6. 阻断项（T14，每类真实非零退出，见任务回报 NEGATIVE CONTROLS）

`dirty source` / `digest mismatch` / 大小写或 Unicode 路径冲突 / 旧 schema /
统计漂移 → exit 20。每类至少一条真实对照。

## 7. 给 T02 的字段需求（registry.json 16 个 `null` 的写入径）

`registry.json` 里 4 条 source 的 `tree_digest` / `source_manifest` /
`snapshot_root` / `importer_version` 为 `null` 是已登记状态（owner T12/T05），
不是 bug。待 T02 写入的值：

- `tree_digest`：本锁同 `id` 条目的 `tree_digest`（§3 表）。
- `source_manifest`：指向本锁同 `id` 条目 + `digest_contract`（manifest 按 §2
  口径离线可复算；不另存一份大 manifest，避免双源漂移）。
- `snapshot_root`：本锁 `snapshot_rel`（`upstream/<repo>`，相对路径）。
- `importer_version`：`adapt-community.py` 当前无版本常量，T02 定标识后回填；
  本卡不编造。

`last_verified_at` 建议与锁 `fetched_at`（2026-09-30T19:04:00Z）对齐，由 T02 定。

## 8. 未动项

- `.gitignore`：`.candidates/`、`__pycache__/`、`skillpack/skills/TOOLS.md` 均已覆盖，
  无需新增（bundle 脚本逐项断言，见 ACCEPTANCE）。
- `scripts/validate-integration.py`：硬编码 `== 4 sources` / `== 55 excluded`
  已由 T04 改为从 registry 推导（文件头 docstring），本卡无需变更请求。
- `skills/community/registry.json`（T02）、`scripts/adapt-community.py`（卡 A）
  未触碰。
