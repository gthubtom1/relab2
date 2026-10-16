> ⚠️ **这是一份「生成快照」，不是现状。** 由下列命令在某个时间点生成，仓库一变它就过期。
> **读之前先重跑对应命令**：线路树 `feature-tree.py` · 功能图 `feature-graph.py [--body]` ·
> 逐树杈核验 `verify-leaves.py`。权威说明见 `docs/PROJECT-MAP.md`。

---

# 功能可达图（技能 × 工具 × 知识）

> 主人 2026-10-16：「各个树干和树杈是**互通**的。**树杈是功能**呀！…
> 逆向的时候可能还会用**渗透的技能和工具**…所有东西都是可能关联的。
> 你要把各个功能做的**和 ai 模型的手和四肢一样**。这个才是一个树杈，就是**不停分支的树状**。」
>
> 所以本图查的不是「文件有没有入口」，而是**从任意起点能不能顺手拿到下一步需要的东西**。

- 技能节点 **63** · 指向边 **517** · **跨战场边 252** · 孤岛 **0**
- 战场分布：{'开发': 14, '协议': 8, '渗透': 17, '固件': 1, '逆向': 20}

## 跨战场边（模型换战场的那只手）

| 从 | 战场 | 到 | 战场 |
|---|---|---|---|
| `api-security` | 渗透 | `code-audit` | 开发 |
| `api-security` | 渗透 | `ida-reverse` | 逆向 |
| `api-security` | 渗透 | `js-reverse` | 协议 |
| `api-security` | 渗透 | `mobile-reverse` | 逆向 |
| `api-security` | 渗透 | `protocol-reverse` | 协议 |
| `api-security` | 渗透 | `web-protocol-reverse` | 协议 |
| `apk-reverse` | 逆向 | `web-protocol-reverse` | 协议 |
| `attack-chain` | 渗透 | `code-audit` | 开发 |
| `attack-chain` | 渗透 | `delivery` | 其它 |
| `attack-chain` | 渗透 | `edr-bypass-re` | 逆向 |
| `attack-chain` | 渗透 | `reverse-engineering` | 逆向 |
| `attack-chain` | 渗透 | `windows-ad` | 协议 |
| `binary-diff` | 逆向 | `patch-diff-exploit` | 渗透 |
| `binary-ninja-reverse` | 逆向 | `js-reverse` | 协议 |
| `binary-ninja-reverse` | 逆向 | `pwn-chain` | 渗透 |
| `browser-automation` | 开发 | `api-security` | 渗透 |
| `browser-automation` | 开发 | `apk-reverse` | 逆向 |
| `browser-automation` | 开发 | `browser-extension-reverse` | 逆向 |
| `browser-automation` | 开发 | `js-reverse` | 协议 |
| `browser-automation` | 开发 | `mobile-reverse` | 逆向 |
| … | | 另有 232 条 | |

## 孤岛（别的战场需要它时伸手够不着）

- 无

## 每个技能伸得出去的手（前 40 个节点）

| 技能 | 战场 | 指向技能 | 点名工具 |
|---|---|---|---|
| `api-security` | 渗透 | `attack-chain`, `cloud-k8s`, `code-audit`, `ida-reverse` | apk, ffuf, httpx, nuclei, python, sqlmap |
| `apk-reverse` | 逆向 | `apk-extension`, `ida-reverse`, `macos-reverse`, `malware-analysis` | apk, apksigner, apktool, frida, ghidra, hook |
| `attack-chain` | 渗透 | `cloud-k8s`, `code-audit`, `delivery`, `edr-bypass-re` | apk, burpsuite, hashcat, hook, httpx, java |
| `binary-diff` | 逆向 | `apk-reverse`, `dotnet-reverse`, `ghidra-reverse`, `go-rust-reverse` | apk, binary-diff, diec, ghidra, httpx, ida |
| `binary-ninja-reverse` | 逆向 | `apk-reverse`, `binary-diff`, `dotnet-reverse`, `ghidra-reverse` | apk, binary-diff, capture, diec, ghidra, ida |
| `browser-automation` | 开发 | `api-security`, `apk-reverse`, `browser-extension-reverse`, `js-reverse` | frida, git, hook, ida, mitmdump, mitmproxy |
| `browser-extension-reverse` | 逆向 | `apk-reverse`, `browser-automation`, `digital-forensics`, `email-security` | apk, frida, node, python, yara |
| `case-review` | 逆向 | `code-review`, `diagram-generator`, `digital-forensics`, `docs-generator` | apktool, binwalk, frida, ghidra, git, hashcat |
| `cloud-k8s` | 渗透 | `api-security`, `attack-chain`, `code-audit`, `database-security` | cloud, ffuf, nmap, nuclei, python |
| `code-audit` | 开发 | `api-security`, `attack-chain`, `binary-diff`, `js-reverse` | apk, binary-diff, cdb, gdb, ghidra, java |
| `code-review` | 开发 | `case-review`, `code-audit`, `docs-changelog`, `implement-feature` | cdb, git, tshark, wireshark |
| `ctf-sandbox` | 渗透 | `api-security`, `attack-chain`, `case-review`, `code-audit` | apk, apktool, binwalk, diec, ffuf, frida |
| `database-security` | 渗透 | `api-security`, `attack-chain`, `case-review`, `cloud-k8s` | cloud, hashcat, nmap, nuclei, python, sqlmap |
| `design-slice` | 开发 | `code-audit`, `diagram-generator`, `implement-feature`, `pr-ship` | git, nmap, tshark, wireshark |
| `diagram-generator` | 开发 | `browser-automation`, `case-review`, `digital-forensics`, `docs-generator` | binwalk, frida, gdb, ghidra, git, hook |
| `digital-forensics` | 协议 | `cloud-k8s`, `malware-analysis`, `mobile-reverse`, `protocol-reverse` | cdb, python, tshark, wireshark, yara |
| `docs-changelog` | 开发 | `case-review`, `code-audit`, `code-review`, `diagram-generator` | git, python |
| `docs-generator` | 开发 | `case-review`, `code-audit`, `diagram-generator`, `digital-forensics` | apk, apktool, binwalk, diec, frida, ghidra |
| `dotnet-reverse` | 逆向 | `apk-reverse`, `binary-diff`, `diagram-generator`, `game-reverse` | apk, binary-diff, de4dot, die, diec, dotnet |
| `edr-bypass-re` | 逆向 | `attack-chain`, `js-reverse`, `kernel-exploit`, `macos-reverse` | capa, cdb, diec, git, hardware, hook |
| `email-security` | 渗透 | `api-security`, `attack-chain`, `identity-federation`, `malware-analysis` | cloud, mitmdump, nmap, python, tshark, yara |
| `firmware-pentest` | 渗透 | `api-security`, `apk-reverse`, `attack-chain`, `binary-diff` | apk, binary-diff, binwalk, gdb, ghidra, git |
| `fix-bug` | 开发 | `code-audit`, `design-slice`, `digital-forensics`, `implement-feature` | cdb, gdb, git, python |
| `game-reverse` | 逆向 | `api-security`, `apk-reverse`, `edr-bypass-re`, `ida-reverse` | apk, hook, java, python |
| `ghidra-reverse` | 逆向 | `apk-reverse`, `binary-diff`, `binary-ninja-reverse`, `dotnet-reverse` | apk, binary-diff, diec, frida, gdb, ghidra |
| `go-rust-reverse` | 逆向 | `binary-diff`, `dotnet-reverse`, `ghidra-reverse`, `ida-reverse` | apk, binary-diff, cdb, die, diec, frida |
| `hardware-security` | 固件 | `firmware-pentest`, `malware-analysis`, `mobile-reverse`, `ot-ics` | binwalk, diec, gdb, ghidra, ghidra_headless, hardware |
| `ida-reverse` | 逆向 | `apk-reverse`, `binary-diff`, `binary-ninja-reverse`, `dotnet-reverse` | apk, binary-diff, diec, frida, ghidra, git |
| `identity-federation` | 渗透 | `api-security`, `attack-chain`, `cloud-k8s`, `code-audit` | ffuf, hashcat, mitmdump, nmap, python |
| `implement-feature` | 开发 | `design-slice`, `fix-bug`, `pr-ship`, `req-clarify` | cdb, git, python, tshark, wireshark |
| `js-reverse` | 协议 | `apk-reverse`, `browser-automation`, `browser-extension-reverse`, `ida-reverse` | apk, capture, hook, js-runtime, node, python |
| `kernel-exploit` | 渗透 | `apk-reverse`, `binary-diff`, `cloud-k8s`, `edr-bypass-re` | ROPgadget, binary-diff, gdb, ghidra, git, ida |
| `llm-security` | 渗透 | `api-security`, `apk-reverse`, `attack-chain`, `browser-extension-reverse` | apk, hashcat, mitmdump, nmap, python, sqlmap |
| `macos-reverse` | 逆向 | `dotnet-reverse`, `ghidra-reverse`, `ida-reverse`, `identity-federation` | frida, ghidra, hook, ida, python, radare2 |
| `malware-analysis` | 逆向 | `apk-reverse`, `attack-chain`, `digital-forensics`, `edr-bypass-re` | apk, die, diec, floss, ghidra, hook |
| `mobile-reverse` | 逆向 | `api-security`, `apk-reverse`, `game-reverse`, `ida-reverse` | apk, apktool, frida, ghidra, hook, jadx |
| `ot-ics` | 协议 | `attack-chain`, `firmware-pentest`, `hardware-security`, `pentest-tools` | binwalk, diec, gdb, ghidra, ghidra_headless, hashcat |
| `patch-diff-exploit` | 渗透 | `apk-reverse`, `binary-diff`, `code-audit`, `dotnet-reverse` | apk, binary-diff, ghidra, git, ida, idat |
| `pentest-tools` | 渗透 | `api-security`, `attack-chain`, `cloud-k8s`, `code-audit` | burpsuite, ffuf, ghidra, git, hashcat, httpx |
| `pr-ship` | 开发 | `case-review`, `code-review`, `diagram-generator`, `docs-changelog` | git |

