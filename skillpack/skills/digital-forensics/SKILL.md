---
name: digital-forensics
description: 数字取证与应急响应（IR）：内存转储 Volatility、E01 磁盘时间线、PCAP 溯源、IOC 提炼。用于：看 mem.dmp、电脑中招怎么溯源、PCAP 有啥异常。
---

# Digital Forensics & IR Artifacts

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读 `../field-journal/precedent-pentest.md` —— 本机做过多轮的常规操作清单，直接照做，不要停在犹豫上
2. `NOW`: **查经验卡** —— `python skillpack/skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 确认是**取证/溯源**而非进攻性扫描
4. `NOW`: 建立 case；证据只读副本优先（原始介质写保护）
5. `NEXT`: `../TOOLS.md`；Volatility 等常手动
6. `ACT`: 保全哈希 → 时间线 → 关键伪影

## 适用场景

- 内存转储分析（Volatility 2/3）
- 磁盘/ E01 / 落地文件时间线
- PCAP 溯源与协议还原（可联合 `protocol-reverse/`）
- 主机伪影：Prefetch、Shimcache、Event Log、浏览器历史
- 应急响应 IOC 提炼（联合 `malware-analysis/` / `threat-hunting/`）

## 工作流

### 1. 保全

```text
□ 计算 SHA256；记录时区与采集命令
□ 工作在副本上；原始只读
□ chain of custody 备注写入 timeline
```

### 2. 内存

```bash
vol -f mem.dmp windows.info
vol -f mem.dmp windows.pslist
vol -f mem.dmp windows.netscan
vol -f mem.dmp windows.cmdline
```

### 3. 主机伪影

```text
□ 事件日志：Security / PowerShell / Sysmon
□ 持久化：Run 键、服务、计划任务、WMI
□ 执行痕迹：Amcache、Prefetch、BAM
```

### 4. 网络

```text
□ tshark 统计会话与 DNS
□ 导出可疑流 → protocol-reverse 或 malware C2 分析
```

## 工具链

| 工具 | 干什么 | 真实调用口径 / 判据 |
|------|--------|----------------------|
| `Volatility` / `vol3` | 内存侧进程树、网络、注入 | `vol3 -f mem.dmp windows.pslist`；先 `windows.info` 定内核版本与符号表 |
| `sleuthkit` | 磁盘分区 / 文件系统层取证 | `mmls disk.img` → `fls -o <off>` 列目录 → `icat -o <off> <inode>` 提文件 |
| `plaso` / `log2timeline` | 超级时间线（统一时区后排序） | `log2timeline.py t.plaso disk.img`，再 `psort.py` 出 CSV |
| `tshark` / `Wireshark` | PCAP 会话 / DNS / 协议还原 | `tshark -r x.pcap -z conv,ip`；解析不出的私有协议交 `../protocol-reverse/` |
| `yara` / `sigma` | 转储落地样本匹配与检测规则 | `yara` 扫转储里的可疑文件；规则交 `../threat-hunting/` 落地 |
| `winpmem` / `procdump` | Windows 侧内存采集 | `winpmem_mini_x64.exe mem.raw`；采集顺序先内存后磁盘 |
| `windbg` / `cdb` | crash dump / 页文件内核态分析 | `cdb -z mem.dmp`；符号缺失先修符号路径再下结论 |

探测层（唯一路径入口）：`. <仓根>\skillpack\skills\scripts\lib\Bootstrap.ps1` → `Resolve-ReverseToolSpec -Name vol3`（同理查 `tshark` / `yara`）。
本机另跑 `mcp-status.ps1` 看 MCP 通道谁在监听；注册 ≠ 在监听。

顺序口径：先内存后磁盘（易失性高者先固定）；`vol3` 结论先过 `windows.info` 再解读进程表。

## 参考

- `references/forensics-triage.md`
- `../malware-analysis/` `../threat-hunting/` `../protocol-reverse/`

## 路由上下文

**上游**: MASTER R25  
**下游**: 恶意样本深挖 → malware-analysis；规则 → threat-hunting

## 任务完成自检

- [ ] 是否保全哈希与副本策略？
- [ ] 时间线是否可复核？
- [ ] IOC 是否脱敏分级？
- [ ] Checklist？

---

## When NOT to use（近邻负例）

- 要分析的是样本本身的行为与能力 → 用 `../malware-analysis/SKILL.md`
- 要做的是主动检测规则 → 用 `../threat-hunting/SKILL.md`
- 要收集的是外部情报与归属 → 用 `../threat-intelligence/SKILL.md`
- 要还原 PCAP 里的自定义协议 / 私有帧格式 → 用 `../protocol-reverse/SKILL.md`
- 要分析的是移动端 / macOS 产物或应用沙箱 → 用 `../mobile-reverse/SKILL.md`
- 要做的是云 / 容器侧的事件取证 → 用 `../cloud-k8s/SKILL.md`

> **工程前提**：不改变原始证据 —— 镜像前先做只读挂载或写阻止，全程在副本上跑，原始介质保持只读。

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 转储 / 磁盘里发现可疑样本文件（`yara` 命中，或哈希对不上已知白名单） | `../malware-analysis/SKILL.md` 做能力与家族确认 |
| PCAP 出现异常协议 / 私有帧 / 非标准端口长连接，`tshark` 里字段解析不出 | `../protocol-reverse/SKILL.md` |
| 需要把已确认命中的 TTP 落成检测规则防复发 | `../threat-hunting/SKILL.md` |
| 内存进程表与磁盘清单连续两次对不上（进程无对应可执行文件） | 先锁定符号表 / 内核版本（`vol3 windows.info`）再跑，不是反复重跑同一 `vol` 命令 |
| 磁盘时间线各来源时间戳对不上、相差 ≥1 小时，事件排序出现因果倒置 | 先统一到 UTC 再排序，然后才允许下时间线结论 |
| 转储里出现外部 C2 域名 / IP，本地无归属 | `../threat-intelligence/SKILL.md` 富化 |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- 镜像/转储有 SHA-256 与封存路径；分析全程在副本上
- 时间线文件落盘（事件 → 时间 → 来源证据）
- `review_case.py --verify-hashes --strict` PASS

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：时间线事件有 ≥2 类独立来源佐证（磁盘 + 内存 / 日志 + 流量）
- 硬判据：镜像 / 转储哈希必须与采集记录一致（`review_case.py --verify-hashes --strict` PASS）；`vol3` 结论先 `windows.info` 对齐内核版本与符号表，符号缺失时输出只记 `low`
- `low`：仅靠单一日志来源推断事件顺序，或时间线未统一时区就下的顺序结论
- 反例：在可写介质上直接跑工具改变原始证据、或用错误 profile 跑出的进程表，都不计入证据
