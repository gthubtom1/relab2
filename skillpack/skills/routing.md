# Reverse Engineering Skill Routing Matrix

> **Advisory only.** PRIMARY comes from `config/routing.json` via `scripts/master-route.ps1`. This file is a 3-axis disambiguation view. If a row here disagrees with JSON, JSON wins.

Route tasks to the most appropriate skill module by target type, user intent, and toolchain.

## CRITICAL: Routing Execution Protocol

1. **MUST** complete routing BEFORE executing. Do NOT "do first, route later".
2. **MUST** start from `scripts/master-route.ps1` (Windows) or `scripts/master-route.sh --hint "..."` (Linux / macOS / Kali) (JSON). Use this matrix only when PRIMARY is ambiguous. When master reports `confidence: low`, PRIMARY=R0, or "No strong keyword hit", re-run the same hint on the community side — `python skills/scripts/community-route.py --hint "..."` — the only place the 293 community skills (R46–R49 wrappers) are visible: `matched` is usable, `needs_review` needs confirmation (Chinese `no_match` with 0 candidates → retry with English keywords), `blocked` (`budget_exceeded`) → narrow and re-query.
3. **MUST** match dimensions (target type + user intent + toolchain) before entering a skill.
4. If route not matched → propose new skill, do NOT force-fit.
5. Cross-module tasks → combine skills per "Path Crossing" section.
6. After routing, read the target skill's SKILL.md BEFORE taking action.
7. **Ops contract** (skill-router form): `ops/scope-contract.md` before ACT; Evidence→Finding→Path; roles in `ops/role-map.md`; timeline/workitems under `work/<case>/`. Identity: `ops/IDENTITY.md`.
8. **External skills**: do NOT bulk-vendor community packs; map + rules in `references/community-security-skills.md` + `ops/skill-supply-chain.md`. RE stages: `reverse-engineering/references/re-agent-workflow.md`. Recon: `pentest-tools/references/recon-pipeline.md`.

## Path basis for the tables below (read before using any path in them)

Every path in the tables from here to `## 任务完成自检` is relative to one of three roots:

- `skills/<技能>/…` — the form used by most cells (e.g. `reverse-engineering/SKILL.md`,
  `pentest-tools/src-hunter/SKILL.md`). Root = the **`skills/` directory**.
- `skills/<技能>/references/…` — `references/` is a subdirectory **of that same skill**
  (e.g. `pentest-tools/references/network-attack-defense.md`,
  `apk-reverse/references/apk-security-checklist.md`). It is never a repo-root `references/`.
- `../CTF-Sandbox-Orchestrator/…` — written relative to `skills/`, so it resolves to the
  **repo root** `CTF-Sandbox-Orchestrator/…`, i.e. **outside** the `skills/` discovery root
  (deliberate: those are sidecar packages, not skills).

Two cell styles are bare filenames with no folder prefix, so the folder is not in the text:

- `reverse-engineering/go-reverse.md` (cells "Go / Rust binary" and "Go/Rust/Swift reverse") = sibling of the
  preceding path in the same cell ⇒ **`reverse-engineering/go-reverse.md`**.
- `field-journal/seed-014_unity-il2cpp-reverse.md` is **not** under `reverse-engineering/`. Its real location
  is **`field-journal/seed-014_unity-il2cpp-reverse.md`**. Read the entry as
  `reverse-engineering/SKILL.md` for Unity/IL2CPP, and treat `seed-014` as a field-journal note,
  not as a file inside the skill directory.

`patterns*.md` (cell "cryptography / AES / RSA") is a glob within
`skills/reverse-engineering/` (actual files: `reverse-engineering/patterns.md`, `reverse-engineering/patterns-ctf.md`,
`reverse-engineering/patterns-ctf-2.md`, `reverse-engineering/patterns-ctf-3.md`), not a single file.
(Verified 2026-10-02 by file-existence check on the real tree.)

## By Target Type

| Target Type | Recommended Entry | Alternative |
|-------------|------------------|-------------|
| APK / Android app | `apk-reverse/` — jadx decompile + apktool unpack | Optional licensed JEB Pro cross-check; if core is in .so → `ida-reverse/` or `radare2/` |
| Binary exe/dll/so/elf | `ida-reverse/` — IDA Pro decompile | `radare2/` — CLI analysis, or `reverse-engineering/tools.md` — GDB/Unicorn |
| JavaScript / Web frontend | `js-reverse/` — 5-stage workflow | anything-analyzer MCP browser tools, or jshookmcp CDP/Hook |
| HTTP capture / browser sampling / request replay | anything-analyzer MCP (23816) | Reqable MCP, `js-reverse/`, jshookmcp, or `competition-web-runtime/` |
| Firmware / IoT | `firmware-pentest/` — extract → EMBA → emulate → fuzz | `reverse-engineering/platforms.md` — static RE only |
| WASM / Python bytecode / .NET / **DSL VM / 自定义虚拟机** | `reverse-engineering/dsl-vm-reverse/SKILL.md` — IIFE + switch-case opcode JS VM | `reverse-engineering/languages.md` — real WASM binaries |
| Malware / virus sample | `malware-analysis/SKILL.md` — six-stage + YARA/Sigma | `ida-reverse/` deep dive |
| macOS / iOS | `reverse-engineering/platforms.md` — Mach-O/ObjC/Swift | `mobile-reverse/` for iOS-specific |
| Game (Unity) | `reverse-engineering/` — engine reverse, anti-cheat, IL2CPP/Mono (see seed-014) | `ida-reverse/` deep analysis |
| Memory dump / PCAP | `digital-forensics/` — memory/timeline/PCAP IR | `protocol-reverse/` for protocol recovery |
| Existing case package / evidence handoff | `case-review/`: Evidence graph and fixity review | `docs-generator/` for final report writing |
| Custom protocol / Protobuf / gRPC | `protocol-reverse/` | `js-reverse/` if pure browser WS crypto |
| Cloud / Container / K8s | `cloud-k8s/` | CTF: `../CTF-Sandbox-Orchestrator/competition-agent-cloud/` |
| Windows AD / Kerberos / AD CS | `windows-ad/` | multi-stage: `attack-chain/` |
| Source code / SAST | `code-audit/` | deps/CI: `supply-chain-security/` |
| Game client (Unity/UE) | `reverse-engineering/` + seed-014 | `dotnet-reverse/` for Mono assemblies |
| OT / ICS / SCADA | `ot-ics/` | `firmware-pentest/` offline firmware |
| macOS / Mach-O desktop | `macos-reverse/` | iOS → `mobile-reverse/` |
| Thick desktop client | `thick-client/` | Electron → also `js-reverse/` |
| Go / Rust stripped binary | `go-rust-reverse/` | `ida-reverse/` / `ghidra-reverse/` |
| UART / JTAG / debug pads | `hardware-security/` | then `firmware-pentest/` |
| Database instance security | `database-security/` | SQLi web path → `pentest-tools/` |
| Email / phishing / DMARC | `email-security/` | |
| SAML / OIDC / SSO | `identity-federation/` | JWT-only API → `api-security/` |
| RF / SDR (non-Wi-Fi) | `radio-sdr/` | Wi-Fi → `wifi-wireless/` |
| Browser extension (crx/xpi) | `browser-extension-reverse/` | page JS only → `js-reverse/` |
| Wi-Fi / wireless | `wifi-wireless/` | close-range chain → `attack-chain/` |
| Public-source threat intelligence / OSINT | `threat-intelligence/` | X/Twitter posts remain leads until independently corroborated |
| Blue team / threat hunt | `threat-hunting/` | sample IOC → `malware-analysis/` |
| Ghidra (no IDA) | `ghidra-reverse/` | `ida-reverse/` if IDA MCP available |
| Binary Ninja / Binja | `binary-ninja-reverse/` — HLIL/MLIL/LLIL + Python API | Community Binary Ninja MCP/localhost HTTP adapter when explicitly enabled |

| OLLVM-obfuscated binary (控制流平坦化/虚假控制流/MBA) | `reverse-engineering/references/ollvm-deobfuscation.md` — 完整脱密工作流 | obpo-plugin / d810-ng (IDA) / ollvm-unflattener (Miasm) / ollvm-breaker (Binary Ninja) / angr / deollvm (ARM64)
| Cryptography / encryption algorithms | `reverse-engineering/patterns*.md` — crypto patterns | `js-reverse/` (if frontend crypto) |
| Protocol reverse / custom protocol | `reverse-engineering/platforms.md` — network protocols | `js-reverse/` (if WebSocket/HTTP) |
| Go / Rust binary | `reverse-engineering/languages-compiled.md` + `reverse-engineering/go-reverse.md` | `ida-reverse/` or `radare2/` |
| LLM / AI application | `llm-security/` — OWASP LLM Top 10 + ASI Top 10 | Prompt injection, Agent security |
| API / REST / GraphQL | `api-security/` — BOLA/BFLA/JWT/OAuth | `pentest-tools/` for scanning |
| Supply chain / SBOM / CI-CD | `supply-chain-security/` — Trivy/Syft/Gitleaks | — |
| iOS app (IPA) | `mobile-reverse/` — class-dump/Hopper/Frida iOS | `reverse-engineering/platforms.md` |
| **CTF competition (full stack)** | `../CTF-Sandbox-Orchestrator/ctf-sandbox-orchestrator/SKILL.md` — master entry | Route to 40+ sub-skills by evidence |
| **CTF ZIP / PKZIP archive** | `../CTF-Sandbox-Orchestrator/competition-zip-archive/SKILL.md` — legacy ZipCrypto + `bkcrack` known plaintext | Use before password brute force |
| Web runtime / API | `../CTF-Sandbox-Orchestrator/competition-web-runtime/SKILL.md` | — |
| Cloud / Container / K8s | `cloud-k8s/` | CTF-only extra: sidecar orchestrator after PRIMARY `ctf-sandbox/` |
| Windows / AD / Identity | `../CTF-Sandbox-Orchestrator/competition-identity-windows/SKILL.md` | — |
| Forensics / PCAP / Steganography | `../CTF-Sandbox-Orchestrator/competition-forensic-timeline/SKILL.md` | — |
| Prompt injection / Agent | `../CTF-Sandbox-Orchestrator/competition-prompt-injection/SKILL.md` | — |
| Mobile (Android/iOS) | `../CTF-Sandbox-Orchestrator/competition-android-hooking/SKILL.md` | — |
| Firmware / Malware sample | `../CTF-Sandbox-Orchestrator/competition-firmware-layout/SKILL.md` | — |

## By User Intent

| User Says | Route To |
|-----------|----------|
| "DSL VM / 自定义指令集 / 风控引擎逆向" | `reverse-engineering/dsl-vm-reverse/SKILL.md` — IIFE + switch-case opcode |
| "fireye / fireyejs / getToken 逆向" | `reverse-engineering/dsl-vm-reverse/SKILL.md` — runtime capture |
| "582KB JS 文件不是 WASM / 大 JS 文件逆向" | `reverse-engineering/dsl-vm-reverse/SKILL.md` — classify DSL VM first |
| "decompile / IDA analyze" | `ida-reverse/SKILL.md` — IDA MCP workflow |
| "recover source / disassemble" | `reverse-engineering/SKILL.md` + `ida-reverse/` |
| "Frida hook / dynamic inject" | `reverse-engineering/tools-dynamic.md` — Frida section |
| "radare2 / r2 analyze" | `radare2/SKILL.md` — CLI workflow |
| "find frontend signature / encrypted params" | `js-reverse/SKILL.md` — Observe→Capture→Rebuild |
| "jshookmcp / JS hook / CDP debug" | `js-reverse/SKILL.md` — same JS/Web chain |
| "Reqable / Reqable MCP / capture replay" | `pentest-tools/SKILL.md` — authorized local capture and API workflow |
| "JEB / JEB Pro" | `apk-reverse/SKILL.md` — licensed Android / ARM cross-check; verify local install first |
| "APK unpack / repack / modify smali" | `apk-reverse/SKILL.md` — decode→rebuild-sign-install |
| "bypass anti-debug / anti-detection" | `reverse-engineering/anti-analysis.md` |
| "OLLVM deobfuscate / 控制流平坦化去除 / deflat / 脱混淆" | `reverse-engineering/references/ollvm-deobfuscation.md` — 完整工作流 |
| "obpo / obpo-plugin / d810-ng / d810" | `reverse-engineering/references/ollvm-deobfuscation.md` — 现代反混淆工具 |
| "Hikari / Polaris / Pluto / O-MVLL / Arkari / goron 混淆" | `reverse-engineering/references/ollvm-deobfuscation.md` — 现代 OLLVM 变种处理 |
| "Tigress / Hodur / Approov 混淆" | `reverse-engineering/references/ollvm-deobfuscation.md` — d810-ng 专用 unflattener |
| "Trap Angr / angr 路径爆炸" | `reverse-engineering/references/ollvm-deobfuscation.md` — Pluto/Polaris 陷阱处理 |
| "BR 混淆 / 间接分支混淆去除" | `reverse-engineering/references/ollvm-deobfuscation.md` — DeObfBR + 数据段只读 |
| "what obfuscation / VM is this" | `reverse-engineering/patterns*.md` — match by pattern |
| "Go/Rust/Swift reverse" | `reverse-engineering/languages-compiled.md` + `reverse-engineering/go-reverse.md` |
| "kernel driver / Rootkit / LKM" | `reverse-engineering/kernel-driver-reverse.md` |
| "Python bytecode / pyc" | `reverse-engineering/languages.md` — Python section |
| "symbol execution / angr" | `reverse-engineering/tools-dynamic.md` — angr section |
| "patch environment / Node reproduce" | `js-reverse/references/env-patching.md` |
| "CTF challenge / competition reverse" | `ctf-sandbox/SKILL.md` → sidecar orchestrator |
| "CTF ZIP / PKZIP / bkcrack / 压缩包明文攻击" | `../CTF-Sandbox-Orchestrator/competition-zip-archive/SKILL.md` |
| "write report / documentation" | `docs-generator/` — technical documentation |
| "review case / evidence chain / traceability" | `case-review/`: read-only Evidence Graph Review |
| "write writeup" | `docs-generator/` — CTF writeup template |
| "open webpage / browser automation / fill form" | `browser-automation/SKILL.md` — Playwright |
| "crawl page / screenshot / auto login" | `browser-automation/SKILL.md` |
| "desktop automation / Windows automation" | `browser-automation/SKILL.md` — OpenReverse |
| "game reverse / anti-cheat / hack analysis" | `reverse-engineering/SKILL.md` — game reverse (IL2CPP/Unity/Cheat Engine) |
| "Unity / IL2CPP / Mono" | `reverse-engineering/SKILL.md` — Unity + `field-journal/seed-014_unity-il2cpp-reverse.md` |
| "Cheat Engine / memory scan" | `reverse-engineering/SKILL.md` — Cheat Engine memory analysis |
| "symbol migration / cross-version compare" | `binary-diff/SKILL.md` — LLM batch migration |
| "missing PDB / old version symbols" | `binary-diff/SKILL.md` — cross-version symbol migration |
| "bindiff / function offset migration" | `binary-diff/SKILL.md` — binary diff |
| "port scan / Nmap" | `pentest-tools/SKILL.md` — information gathering |
| "vulnerability scan / Nuclei" | `pentest-tools/SKILL.md` — vulnerability detection |
| "SQL injection / SQLMap" | `pentest-tools/SKILL.md` — web pentest |
| "directory brute force / FFUF / Gobuster" | `pentest-tools/SKILL.md` — web pentest |
| "password cracking / Hashcat" | `pentest-tools/SKILL.md` — password cracking |
| "penetration testing / active scan" | `pentest-tools/SKILL.md` — pentest toolchain |
| "SRC hunting / Bug Bounty" | `pentest-tools/src-hunter/SKILL.md` — 19 playbooks + H1 cases |
| "WAF bypass" | `pentest-tools/src-hunter/references/payloader/` — 263 bypass steps |
| "draw diagram / flowchart / architecture" | `diagram-generator/SKILL.md` |
| "attack path diagram / sequence diagram" | `diagram-generator/SKILL.md` — Mermaid/Graphviz/PlantUML |
| "malware / virus analysis / sample analysis" | `reverse-engineering/SKILL.md` + YARA/sandbox |
| "firmware / IoT / binwalk / ARM" | `reverse-engineering/platforms-hardware.md` |
| "cryptography / AES / RSA" | `reverse-engineering/patterns*.md` — crypto pattern recognition |
| "protocol reverse / Protobuf / custom protocol" | `reverse-engineering/platforms.md` |
| "cloud security / container escape / K8s" | `cloud-k8s/SKILL.md` |
| "Prompt injection / AI security" | `llm-security/SKILL.md` — OWASP LLM + ASI Top 10 |
| "internal network / lateral movement" | `pentest-tools/SKILL.md` + `pentest-tools/references/network-attack-defense.md` |
| "privilege escalation" | `pentest-tools/references/network-attack-defense.md` — escalation section |
| "Mimikatz / credential extraction / PtH" | `pentest-tools/references/network-attack-defense.md` |
| "Kerberos / domain pentest / AD" | `pentest-tools/references/network-attack-defense.md` |
| "C2 / persistence / remote control" | `pentest-tools/references/network-attack-defense.md` |
| "blue team / detection / defense / IR" | `pentest-tools/references/network-attack-defense.md` |
| "APK security testing / mobile security" | `apk-reverse/references/apk-security-checklist.md` — OWASP MASTG |
| "SSTI / template injection" | `pentest-tools/SKILL.md` — SSTImap |
| "XSS scan / cross-site scripting" | `pentest-tools/SKILL.md` — XSStrike |
| "WordPress pentest / WP enumeration" | `pentest-tools/SKILL.md` — WPProbe |
| "C2 framework / adversary simulation" | `pentest-tools/SKILL.md` — AdaptixC2 |
| "WiFi attack / wireless pentest" | `pentest-tools/SKILL.md` — Fluxion + aircrack-ng |
| "NTLM relay / auth coercion" | `pentest-tools/SKILL.md` — Coercer |
| "NetExec / CrackMapExec / nxc" | `pentest-tools/SKILL.md` — network service enumeration |
| "AI auto pentest / MCP security" | `pentest-tools/SKILL.md` — HexStrike AI / MetasploitMCP |
| "Swarm / swarm pentest / autonomous scan" | `pentest-tools/SKILL.md` — Pentest Swarm AI |
| "red team / HW / attack exercise" | `attack-chain/SKILL.md` — full attack chain orchestration |
| "initial breach / boundary breach" | `attack-chain/SKILL.md` — boundary breach phase |
| "close-range pentest / BadUSB / WiFi phishing" | `attack-chain/SKILL.md` — close-range section |
| "EDR bypass / evasion / AV bypass" | `edr-bypass-re/SKILL.md` |
| "phishing / social engineering" | `email-security/SKILL.md` |
| "supply chain attack" | `attack-chain/SKILL.md` — supply chain section |
| "trace cleanup / anti-forensics" | `attack-chain/SKILL.md` — cleanup section |
| "full pentest / end-to-end" | `attack-chain/SKILL.md` — full chain planning |
| "from external to domain controller" | `attack-chain/SKILL.md` — cross-phase path orchestration |
| "attack surface assessment / path planning" | `attack-chain/SKILL.md` — path planning decision tree |
| "got shell, what next / post-exploitation" | `attack-chain/SKILL.md` — plan from current foothold |
| "BurpSuite / Burp proxy / intercept" | `pentest-tools/SKILL.md` + `pentest-tools/references/burpsuite-mcp-guide.md` |
| "Burp MCP / proxy history analysis" | `pentest-tools/references/burpsuite-mcp-guide.md` — 78 tools |
| "Intruder brute force / Repeater replay" | `pentest-tools/references/burpsuite-mcp-guide.md` |
| "Collaborator / OOB testing" | `pentest-tools/references/burpsuite-mcp-guide.md` |
| "API security / GraphQL / JWT attack" | `api-security/SKILL.md` — REST/GraphQL/JWT/OAuth |
| "supply chain security / SBOM / SCA" | `supply-chain-security/SKILL.md` — Trivy/Syft/Gitleaks |
| "iOS reverse / IPA / Mach-O" | `mobile-reverse/SKILL.md` — class-dump/Hopper/Frida iOS |
| "Objection / SSL Pinning bypass" | `mobile-reverse/SKILL.md` — dynamic instrumentation |
| "YARA / malware detection rules" | `malware-analysis/SKILL.md` — YARA/Sigma/IOC |
| "N-day / patch diff / CVE reproduction" | `patch-diff-exploit/SKILL.md` |
| "MBA simplification / mixed boolean-arithmetic / 表达式化简" | `reverse-engineering/references/ollvm-deobfuscation.md` — SiMBA/D-810 |
| "opaque predicate / 不透明谓词去除" | `reverse-engineering/references/ollvm-deobfuscation.md` — 符号执行去除 |
| "Hikari deobfuscate / 字符串加密恢复" | `reverse-engineering/references/ollvm-deobfuscation.md` — Hikari 变种处理 |
| "pwn / stack overflow / ROP / ret2libc" | `pwn-chain/SKILL.md` |
| "Agent not working / AI lazy / skip steps" | `llm-security/references/agent-obedience-engineering.md` |
| "MSF stuck / orphan process / MSF protocol" | `pentest-tools/references/msf-protocol.md` |
| "anonymize / placeholder / writeup desensitize" | `field-journal/anonymization.md` |
| "Hydra / online brute force" | `pentest-tools/SKILL.md` — online password attack |
| "Metasploit / msfconsole / exploit" | `pentest-tools/SKILL.md` — exploitation framework |
| "Wireshark / packet analysis / PCAP" | `digital-forensics/` or `protocol-reverse/` |
| "BurpSuite / web proxy / intercept" | `pentest-tools/SKILL.md` — web proxy |
| "protocol reverse / Protobuf / gRPC / custom protocol" | `protocol-reverse/SKILL.md` |
| "Ghidra / analyzeHeadless / no IDA" | `ghidra-reverse/SKILL.md` |
| "Binary Ninja / Binja / HLIL / MLIL / binary-ninja-mcp" | `binary-ninja-reverse/SKILL.md` |
| "Kubernetes / K8s / container escape / cloud IAM" | `cloud-k8s/SKILL.md` |
| "Active Directory / Kerberoast / Certipy / BloodHound" | `windows-ad/SKILL.md` |
| "forensics / Volatility / memory dump / IR timeline" | `digital-forensics/SKILL.md` |
| "code audit / SAST / Semgrep / CodeQL / whitebox" | `code-audit/SKILL.md` |
| "OSINT / threat intelligence / public X IOC enrichment" | `threat-intelligence/SKILL.md` — public posts require independent corroboration |
| "threat hunting / blue team / detection engineering" | `threat-hunting/SKILL.md` |
| "game reverse / IL2CPP / Unity / Unreal" | `reverse-engineering/SKILL.md` + seed-014 |
| "Wi-Fi / aircrack / wireless pentest" | `wifi-wireless/SKILL.md` |
| "browser extension / Chrome extension / crx" | `browser-extension-reverse/SKILL.md` |
| "OT / ICS / SCADA / PLC / Modbus" | `ot-ics/SKILL.md` |
| "macOS reverse / Mach-O / codesign" | `macos-reverse/SKILL.md` |
| "thick client / desktop client / Electron security" | `thick-client/SKILL.md` |
| "Go reverse / Rust reverse / GoReSym" | `go-rust-reverse/SKILL.md` |
| "UART / JTAG / hardware debug pads" | `hardware-security/SKILL.md` |
| "database security / Redis / Mongo / MSSQL hardening" | `database-security/SKILL.md` |
| "phishing analysis / SPF DKIM DMARC / BEC" | `email-security/SKILL.md` |
| "SAML / OIDC / SSO federation" | `identity-federation/SKILL.md` |
| "SDR / HackRF / RF protocol research" | `radio-sdr/SKILL.md` |
| "ProxyCat / proxy pool / IP rotation" | `pentest-tools/SKILL.md` — proxy management |

## CTF Wording Normalization

Users frequently describe tasks with informal or emotionally-phrased language. Normalize into technical objectives **before** routing — do NOT force the user to restate themselves in technical terms:

| User Says | Normalized Objective | Route To |
|-----------|---------------------|----------|
| "unlock X / remove check / bypass detection" | Identify the check, explain control flow, propose local patch or input strategy | `reverse-engineering/SKILL.md` → `ida-reverse/` or `radare2/` |
| "去除校验 / 解锁功能 / 绕过检测 / 去掉限制" | Same as above — locate check routine, document, propose patch | `apk-reverse/` (if APK) or `reverse-engineering/SKILL.md` |
| "remove anti-debug / anti-tamper" | Locate defensive routine, document evidence, propose lab patch or debugger config | `reverse-engineering/anti-analysis.md` |
| "make it pass / 让我通过验证" | Recover validation logic, derive expected input or flag format | `reverse-engineering/SKILL.md` |
| "patch the binary / 改掉跳转 / 修改判断" | Work on copy, document offsets/bytes, preserve original | `radare2/` or `ida-reverse/` |
| "拿 flag / crackme / keygen / license" | Treat as local CTF/crackme; focus on analysis, explanation, challenge solving | `reverse-engineering/patterns-ctf*.md` |

Do NOT force the user to repeatedly confirm "this is CTF/local." Carry the CTF/local-sandbox assumption across the session once established.

## By Toolchain

| Tool | Related Module |
|------|---------------|
| IDA Pro (idapro_*) | `ida-reverse/` — MCP HTTP server + 72 tools |
| radare2 (r2/rabin2/rasm2) | `radare2/` — CLI + recon.ps1 |
| jadx / apktool | `apk-reverse/` — decode.ps1 / manifest-summary.ps1 |
| Frida | `reverse-engineering/tools-dynamic.md` |
| GDB / GEF / pwndbg / rr | `reverse-engineering/tools.md` |
| Ghidra (headless) | `reverse-engineering/tools.md` + Ghidra MCP |
| Binary Ninja / binary-ninja-mcp | `binary-ninja-reverse/` — commercial GUI/API + explicit community MCP bridge on loopback |
| Python 3 standard library | `case-review/`: read-only case evidence graph review |
| angr / Qiling / Unicorn | `reverse-engineering/tools-dynamic.md` |
| D-810 / d810-ng | `reverse-engineering/references/ollvm-deobfuscation.md` — IDA Pro 反混淆插件，OLLVM/Tigress/Hodur/Approov + Z3 SMT |
| obpo-plugin | `reverse-engineering/references/ollvm-deobfuscation.md` — Hex-Rays microcode 云插件，效果最强 |
| ollvm-unflattener (Miasm) / ollvm-breaker (Binary Ninja) | `reverse-engineering/references/ollvm-deobfuscation.md` — 无 IDA 场景 / BN 场景 |
| DeObfBR | `reverse-engineering/references/ollvm-deobfuscation.md` — BR 间接分支混淆专项 |
| deflat (QuarksLab) / angr symbol | `reverse-engineering/references/ollvm-deobfuscation.md` — 控制流平坦化去除 |
| GOOMBA (Ghidra) | `reverse-engineering/references/ollvm-deobfuscation.md` — Ghidra P-Code 反混淆 |
| BinDiff / Diaphora | `reverse-engineering/tools-advanced.md` |
| anything-analyzer MCP | Port 23816 MCP server (browser + HTTP capture + AI analysis) |
| jshookmcp | `js-reverse/` enhancement MCP for browser/CDP/Hook/Network/SourceMap/AST |
| agent-browser / Playwright | `browser-automation/` — browser automation |
| OpenReverse (UIA/CUA) | `browser-automation/` — Windows desktop automation |
| Cheat Engine / x64dbg / ReClass | `reverse-engineering/` — game memory analysis (seed-014) |
| IL2CPP Dumper / dnSpy | `reverse-engineering/` — Unity/Mono game reverse (seed-014) |
| LLM symbol migration / BinDiff alternative | `binary-diff/` — cross-version batch migration |
| Nmap / Masscan | `pentest-tools/` — port scan, service identification |
| Nuclei / ZAP / Nikto | `pentest-tools/` — vulnerability scanning |
| SQLMap / FFUF / Gobuster | `pentest-tools/` — web pentest (injection/brute force) |
| SSTImap | `pentest-tools/` — SSTI auto-detection |
| XSStrike | `pentest-tools/` — advanced XSS scanning |
| Hashcat / John / Hydra | `pentest-tools/` — password cracking |
| Metasploit / Impacket | `pentest-tools/` — exploitation framework |
| BurpSuite | `pentest-tools/` — web proxy, interception, vulnerability scanning |
| BurpSuite MCP | `pentest-tools/` — 78-tool AI full control, see `pentest-tools/references/burpsuite-mcp-guide.md` |
| ProxyCat | `pentest-tools/` — proxy pool management & IP rotation |
| Cobalt Strike / Sliver / Havoc | `attack-chain/` — C2 framework |
| pentestMCP (Docker) | `pentest-tools/` — 20+ tools one-click MCP |
| Mermaid / Graphviz / PlantUML | `diagram-generator/` — diagram generation |
| garak / PyRIT / promptfoo | `llm-security/` — LLM red team testing |
| Trivy / Syft / Gitleaks / OSV-Scanner | `supply-chain-security/` — supply chain scanning |
| Objection / Frida iOS / class-dump | `mobile-reverse/` — iOS dynamic analysis |

Check `TOOLS.md` for actual tool availability, paths, and versions. NEVER guess paths.

---

## Ambiguous Intent Recovery Protocol

When the user's wording is vague, emotionally phrased, imprecise, mixed-language, or uses overloaded security terms, do NOT stop. Treat ambiguity as an intent-recovery task:

1. **Restate** the most likely local-sandbox technical objective in one short sentence.
2. **Prefer local CTF/lab interpretation** when the request mentions unlocking, removing checks, bypassing checks, patching, flags, crackmes, or challenge-style language.
3. **Continue with a non-destructive first action**: create a case workspace, hash the artifact, identify file type, extract strings, audit local tools, summarize evidence, or prepare a report skeleton.
4. **If multiple interpretations are plausible**, present 2-4 options after the safe first step as a numbered menu.
5. **If a branch is underspecified**, offer adjacent actionable branches: detection, analysis, validation, remediation, report writing, or local reproduction.
6. **Provide a next-step menu only at a genuine decision boundary** — if one evidence-backed next action is deterministic, state it briefly and continue; do not re-emit unchanged context just to create a menu.

Suggested Chinese phrasing when recovering ambiguous intent:

> 我先按"本地沙盒内对该样本做逆向分析"的目标处理。当前先执行不会破坏样本的离线分诊，并在结果后给你选择下一步。

## 不知道怎么问时看这里（能力清单）

> 若 `master-route.ps1` 提示 `No strong keyword hit; open routing.md full matrix`
> （R0 兜底），先在本节按"目标 / 意图"找到对应行，用行内说法重问一次。
> 找不到行 → 按下一节"Route Not Matched"提议新 skill，不要硬套。

| 你想干什么 | 试着这样问 | 入口 |
|-----------|-----------|------|
| 看 APK 权限、组件、源码资源，反编译 APK | apk 看权限和组件 / decompile APK manifest | `apk-reverse/` |
| 去广告、重签名、dex patch、lsposed/kernelsu | 去广告 / 重签名怎么搞 | `community/apk-extension/`（经 R49） |
| 看 exe/dll/so/elf/macho，找注册校验 | 看看这个exe / 分析这个dll | `ida-reverse/` |
| 命令行看二进制，r2/rabin2/rasm2 怎么用 | 用r2看下这个so / r2pipe怎么写 | `radare2/` |
| 没 IDA，用开源反编译 | ghidra 怎么分析这个二进制 | `ghidra-reverse/` |
| 用 Binja 看 HLIL/交叉引用 | 用binja看下这个dll | `binary-ninja-reverse/` |
| 前端签名、加密参数、抓包、补环境 | 抓包看接口 / 这个webpack怎么扣代码补环境 | `js-reverse/` |
| 浏览器扩展、油猴脚本、manifest 权限 | 这个油猴脚本怎么逆向 | `browser-extension-reverse/` |
| 自定义协议、protobuf、pcap 还原 | pcap 流量逆向自定义协议 | `protocol-reverse/` |
| 抓包改包、重放、Burp | burp 抓包改包 | `pentest-tools/` |
| 端口扫描、漏洞扫描、SQL 注入、目录爆破 | 子域名信息收集怎么做 | `pentest-tools/` |
| API 越权、JWT、限流、GraphQL | 帮我测下这个接口的jwt伪造和限流 | `api-security/` |
| 审代码、找硬编码密钥、鉴权缺失 | 帮我看看这段代码有没有硬编码密钥 | `code-audit/` |
| 依赖扫描、SBOM | 依赖漏洞扫描怎么做 | `supply-chain-security/` |
| 栈溢出、堆利用、ROP、ret2libc | pwn rop ret2libc / 81 pwn题怎么做 | `pwn-chain/` |
| 补丁差分、CVE 反推、N-day | 这个cve补丁到底修了啥 | `patch-diff-exploit/` |
| 新旧版本符号迁移、缺 PDB | 程序更新后函数偏移变了批量迁移函数名 | `binary-diff/` |
| EDR/Defender 绕过、unhook、免杀 | defender怎么unhook绕过 | `edr-bypass-re/` |
| 恶意软件、勒索样本分析 | 分析一个加密勒索样本 | `malware-analysis/` |
| 内存转储、应急响应、取证 | 内存转储取证分析 | `digital-forensics/` |
| 威胁狩猎、检测规则 | sigma 检测规则怎么写 | `threat-hunting/` |
| 威胁情报、IOC 富化 | ioc 情报扩充怎么做 | `threat-intelligence/` |
| 内网渗透、横向移动、打到域控 | 从外网打到域控怎么做 | `attack-chain/` |
| AD/域渗透、Kerberos、证书 | 域控怎么打 | `windows-ad/` |
| 云/K8s、容器逃逸、对象存储 | k8s 容器逃逸怎么做 | `cloud-k8s/` |
| 固件提取、路由器固件 | 路由器固件怎么解包分析 | `firmware-pentest/` |
| 拆机、串口日志、JTAG、Flash 提取 | 拆机接串口看启动日志 | `hardware-security/` |
| 邮件钓鱼、DMARC | 钓鱼邮件头怎么分析 | `email-security/` |
| 单点登录、SAML/OIDC | sso 单点登录安全怎么做 | `identity-federation/` |
| 数据库安全加固 | redis 安全加固怎么做 | `database-security/` |
| Wi-Fi 渗透、握手包 | wifi 握手包怎么抓 | `wifi-wireless/` |
| 非 Wi-Fi 无线电、遥控信号、SDR | 433遥控信号怎么分析 | `radio-sdr/` |
| 厚客户端、桌面客户端 | 桌面客户端安全怎么做 | `thick-client/` |
| Go/Rust 二进制逆向 | go 二进制怎么逆向 | `go-rust-reverse/` |
| macOS、Mach-O、启动项 | mac开机启动项分析 | `macos-reverse/` |
| iOS、IPA、砸壳、SSL pinning | 这个ipa怎么脱壳 | `mobile-reverse/` |
| 浏览器自动化、自动登录、爬取截图 | 自动登录这个网站并截图 | `browser-automation/` |
| LLM 提示词注入、RAG 泄露、智能体 | 这个AI客服会被套出提示词吗 | `llm-security/` |
| 写报告、写文档、writeup | 整理成文档出个readme | `docs-generator/` |
| 画架构图、流程图、攻击路径图 | 画个攻击路径图 | `diagram-generator/` |
| 案件证据链、审计 | 证据链怎么审 | `case-review/` |
| 做 CTF 题、misc、刷题、打靶 | 82 misc题怎么做 | `ctf-sandbox/`（经 R41） |
| CTF 平台玩法、新手入门、题解 | ctf新手入门怎么玩 | `community/ctf-hub/`（经 R47） |
| CI/CD、交付流程、PRD | 公司要上 CI/CD 交付流程 | `community/delivery/`（经 R48） |
| 动调被甩反调试、三层壳脱壳、代码混淆还原 | 动调被反调试甩掉怎么跟 / 这个壳怎么脱 | `community/hack-hub/`（经 R46；依据 registry 042/051/058/129） |
| 驱动内核、macOS 注入绕过、合约改余额 | 驱动触核心怎么看 / mac进程注入绕过 / 合约余额被改 | `community/hack-hub/`（经 R46；依据 registry 088/095/096/066/115） |
| 内存镜像翻进程、浏览器崩解析内存、无比赛语境的堆/ROP | 关机内存镜像翻进程 / 无比赛语境的ROP链 | `community/hack-hub/`（经 R46；依据 registry 097/052/073/078/119；有比赛/flag语境转 R47 下游 ctf-pwn） |
| 纯 web 手法但在比赛/靶场里做 | 靶场里这道 web 题怎么做（含比赛/flag 语境才算） | `community/ctf-hub/`（经 R47；无比赛信号的纯 web 口语、无强锚点时**不给默认方向**，按 F4 兜底补齐语境三问，补不齐则 `uncertain` 交回用户） |
| 模型训练/RAG/评测、设计系统、安全评审要排期验收 | RAG 链和评测要排期交付 / 设计系统落地验收 | `community/delivery/`（经 R48；纯单点检测无交付动词走 canonical 安全路由） |

## 社区 wrapper 读表补注（只读，不改路由）

> 本节是读表线索补厚，不改变任何路由逻辑。路由唯一事实源仍是 `config/routing.json`，与 JSON 不一致时以 JSON 为准。

- R46 与 R47 切分：两包 web 主题**同名**（sqli / xss / csrf / idor / ssrf / rce / business-logic / open-redirect / path-traversal / upload / info-disclosure / auth-jwt 在两包各有一条），**主题判不了**。可操作的切分判据见下节「R46 / R47 / R49 正面判据」的 F1–F4：题型门词 → 工具化动作 → 语气。一句话版本：ctf-hub 管「这道题 / 这套靶场怎么打」，hack-hub 管「这个真实目标上这个洞怎么打」；F1–F4 全部落空时才标 `uncertain` 补问（F4 兜底已改为判 R47 + 标注，不弃权，详见下节），不硬猜。
- hack 主题词表（R46“等”字展开，全部可在 registry adapted_path 中找到，不编造）：反调试与保护绕过 042/051、混淆与虚拟机逆向 058/129、利用开发 047/073/078/119、浏览器漏洞 052、符号执行 122、内核与逃逸 059/088/114、系统提权横移 091/092/093/101/111/125/133/134/135、macOS 095/096、移动自保 041/085/098（含安卓运行环境检测、SSL pinning/证书处理）、AD 与 Kerberos 037/038/039、云与 K8s 089、协议与流量 069/079/080/081/099/124、密码与加密 055/077/090/112/123、合约与链 066/115、内存取证与隐写 097/120、LLM 094、侦察与业务逻辑 048/053/054/067/108/109。逐族完整清单（16 族 103 条真实记录名）见下节 R46 表。hack-hub 入口的 Topic mapping 行（binary/anti-debug/pwn 对 reverse-engineering/pwn-chain）是 canonical 复用提示，不是排他声明。
- R49 边界：R49（apk-extension，registry 仅 1 条 293）的 `legacy_description` **自己就写明拥有** runtime / server-side behaviour / Frida hooking / anti-tamper / repack pitfalls。正确的切分轴**不是**「有没有反调试」，而是**「改的是谁的东西」**：主体是我手上这个包 / 我改过的包、目标是让它改得动装得上跑得起 → R49；主体是别人的 App、目标只是证明它能被绕 → R46（hack 侧 `android-pentesting-tricks` 041 / `mobile-ssl-pinning-bypass` 098 等 3 条渗透技巧记录）。此前"APK 运行环境检测、反调试一律归 R46"的说法与 registry 原文冲突，已按上面这条轴改正；逐条判据见下节 P1–P3。
- 智能合约：registry 中合约条目只在 hack 侧（066 defi-attack-patterns、115 smart-contract-vulnerabilities），ctf 侧 35 条无合约。链上合约改余额类走 R46。
- R48 边界：R48 命中条件是交付编排语境（目标/排期/验收/跨角色工作流）。delivery 下含 ai-ml（139–144：训练/RAG/评测/部署）、产品（218–230：PRD/用户故事/路线图）、设计系统（278–292）、security-engineer（257–264：评审/SCA/威胁建模）、devops/sre、数据分析、QA。security-engineer 分支只做编排与验收，安全/逆向/渗透与真实部署动作交还 canonical（delivery 入口 Canonical boundaries 原文）。模型训练/RAG/评测、产品增长、设计系统、安全评审/SCA/威胁建模：有排期验收动词进 R48，纯单点检测无交付语境走 canonical 安全路由。
- R9 与 R25：残留痕迹加样本/沙箱/行为/外连语境优先 R9（routing.json 有 N023 tie-break：priority R9 在前 1:1 胜出）；主机/磁盘/内存镜像加时间线还原语境走 R25。
- R5 与 R0：点名或暗示托管/.NET 语境（微软那套/托管/反编译乱码）先判 R5（routing.json N011–N013）；未点名技术的未知混淆二进制走 R0 并补问技术栈。
- R41 与 R47：新手/入门/组队/战队/路线/题解汇总是 R47 入口意图；具体题目求解（含 flag/靶场/比赛题）走 R41，pwn 专项按主表走 R17（两条规则互斥 exclude 已在 routing.json 写明）。

### R46 / R47 / R49 正面判据（读表者照着判）

> 本节是**读表判据**，不改变任何路由逻辑。路由唯一事实源仍是 `config/routing.json`，与 JSON 不一致时以 JSON 为准。
> 下文所有主题名都是 `skills/community/registry.json` 里 `source_path` 的**真实记录名**（`legacy_original_name` 同名），
> 可逐条核对；没有记录支撑的词不写进来。
>
> **判据的类型差别（用之前先看）**：**F2 / F3 / P2 是逐字型**——表里的行几乎是题面逐字复述，
> 可按字面匹配使用；**F4 是语境型**——必须人工读语境，机械匹配（正则、关键词命中）会失效。
> 依据（`../../kernel/07-kernel-sweep/REPORT.md` §6④ 的独立盲读统计）：那轮 19 条里 12 条判对中
> 11 条来自逐字型（F2 4 + F3 5 + P2 3，N259 双算），**只有 2 条来自语境型 F4（2/7）**。
> 早前那次"机械化成正则跑出 13 翻转"的漂亮数字，是因为复判的正好是逐字型那批。

#### 三条总排序规则（先于任何主题匹配）

1. **载体优先**：题面主体是什么，就先按什么定路由，"行为"只是修饰语。APK / AAB / DEX / SO / 安装包 / 应用 / 这个包 / 改完的包 → **APK 侧**（普通分析 R1，改动/适配能力 R49）；站 / 接口 / 域 / 内网 / 集群 / 驱动 / 票据 / 代理 / 合约 → **R46**；只给了一个待分析的附件 / 样本 / 镜像 / flag / 一道题，且没有真实目标锚点 → **进 F2**。
2. **语境优先于主题**（R46 vs R47）：两包 web 主题同名，主题本身判不了，只能看语境和动作形态。
3. **"改谁的东西"优先于"有什么机制"**（R46 vs R49）：问的是"能不能绕"，还是"改完能不能用"。

#### R46（`community/hack-hub/`，`hack-skills` 103 条）实际覆盖

16 族，合计 **103** 条（`registry.json` `source=hack-skills` 逐条核对）：

| 族 | 条数 | 记录名（全部真实） |
|---|---|---|
| web 注入与污染 | 20 | `sqli-sql-injection` `nosql-injection` `xss-cross-site-scripting` `csrf-cross-site-request-forgery` `xxe-xml-external-entity` `ssrf-server-side-request-forgery` `ssti-server-side-template-injection` `cmdi-command-injection` `expression-language-injection` `jndi-injection` `xslt-injection` `prototype-pollution` `prototype-pollution-advanced` `crlf-injection` `email-header-injection` `csv-formula-injection` `dangling-markup-injection` `deserialization-insecure` `http-parameter-pollution` `injection-checking` |
| HTTP 与协议层 | 12 | `request-smuggling` `http2-specific-attacks` `http-host-header-attacks` `dns-rebinding-attacks` `websocket-security` `cors-cross-origin-misconfiguration` `csp-bypass-advanced` `clickjacking` `web-cache-deception` `401-403-bypass-techniques` `network-protocol-attacks` `traffic-analysis-pcap` |
| 文件与路径 | 5 | `path-traversal-lfi` `file-access-vuln` `upload-insecure-files` `open-redirect` `type-juggling` |
| 鉴权与身份 | 13 | `authbypass-authentication-flaws` `auth-sec` `api-auth-and-jwt-abuse` `jwt-oauth-token-attacks` `oauth-oidc-misconfiguration` `saml-sso-assertion-attacks` `ntlm-relay-coercion` `idor-broken-object-authorization` `api-authorization-and-bola` `active-directory-acl-abuse` `active-directory-certificate-services` `active-directory-kerberos-attacks` `unauthorized-access-common-services` |
| 业务逻辑与 API 面 | 6 | `business-logic-vuln` `business-logic-vulnerabilities` `race-condition` `api-sec` `api-recon-and-docs` `graphql-and-hidden-parameters` |
| 侦察 | 3 | `recon-and-methodology` `recon-for-sec` `attack-surface-mapping` |
| 利用开发 | 9 | `heap-exploitation` `stack-overflow-and-rop` `arbitrary-write-to-rce` `format-string-exploitation` `ghost-bits-cast-attack` `vm-and-bytecode-reverse` `symbolic-execution-tools` `reverse-shell-techniques` `tunneling-and-pivoting` |
| 密码与隐写 | 6 | `classical-cipher-analysis` `hash-attack-techniques` `symmetric-cipher-attacks` `rsa-attack-techniques` `lattice-crypto-attacks` `steganography-techniques` |
| 内核 / 本地提权 / 横移 | 9 | `kernel-exploitation` `container-escape-techniques` `sandbox-escape-techniques` `linux-privilege-escalation` `linux-security-bypass` `linux-lateral-movement` `windows-privilege-escalation` `windows-lateral-movement` `windows-av-evasion` |
| 云与容器 | 1 | `kubernetes-pentesting` |
| 移动与桌面客户端 | 5 | `android-pentesting-tricks` `ios-pentesting-tricks` `mobile-ssl-pinning-bypass` `macos-process-injection` `macos-security-bypass` |
| 逆向与自保 | 4 | `anti-debugging-techniques` `binary-protection-bypass` `code-obfuscation-deobfuscation` `memory-forensics-volatility` |
| 供应链 | 2 | `dependency-confusion` `insecure-source-code-management` |
| AI 面 | 2 | `ai-ml-security` `llm-prompt-injection` |
| 对抗与代理面 | 3 | `waf-bypass-techniques` `subdomain-takeover` `browser-exploitation-v8` |
| 合约与链 / 通用占位 | 3 | `defi-attack-patterns` `smart-contract-vulnerabilities` `hack` |

**R46 正面判据**：目标是**别人资产上的单点手法**——"这个站 / 这台机器 / 这个域 / 这套接口 / 这份流量 /
这个合约上，这个洞怎么打"。即使题面一个 hack 类词都没有，只要主体是站、接口、域、机器、票据、驱动、
合约、容器集群 → R46。

**R46 的能力边界（据此可以反推 R47）**：这 103 条里**没有任何一条**是通用 Web 扫描器、爬站工具、
指纹模板批量扫描或注入自动化——侦察侧只有 `recon-and-methodology` / `recon-for-sec` /
`attack-surface-mapping` 三条**方法论**。所以"拿字典挨个试 / 爬全站 / 批量套模板 / 丢给工具自动跑"
**不是 R46 的能力面**，见 F3。

#### R47（`community/ctf-hub/`，`ctf-super-hub` 35 条）正面判据

35 条 = **14 条 `ctf-*` 题型/入口记录** + **21 条 `strix-*` 记录**（`strix-beginner-hub` 1 + 工具/流程 7 + 漏洞专项 13）。
下面 4 条判据命中任一即 R47。

**F1 题型门词（对应 14 条 `ctf-*`）**：`ctf` / 夺旗 / `flag` / 靶机 / 靶场 / 比赛 / AWD / 打靶 / 刷题 /
这道题 / 那道题 / 新手 / 入门 / 题解 / `writeup` / 杂项 / 五类题 / 战队；
`分工` 与 `复盘` 必须带队伍或题目语境才算（"复盘会""定分工"在事故复盘与项目排期里是常用词，裸词会误吸）。
对应记录：`brainstorming` `ctf-beginner-hub` `ctf-misc` `ctf-writeup` `ctf-super-hub` `solve-challenge`。

**F2 无真实目标锚点 → 题型分流（对应 14 条 `ctf-*`，且必须先过 F2 的门）**：

**F2 门**：题面里**没有任何强锚点**，而是给了**一个待分析的附件或样本**，或**一个只有身份线索的对象**。
锚点分两栏（依据 `../../kernel/07-kernel-sweep/REPORT.md` §6③——原 F2 门把"带所有权/环境的词"和
"裸载体词"混在一起，边界不清）：

| 栏 | 词表 | 作用 |
|---|---|---|
| **强锚点**（带所有权 / 环境） | 客户 / 这个站 / 这台机器 / 这台服务器 / 线上 / 内网 / 生产环境 / 对方业务 / 域 / 集群 / 合同 | 出现即 **R46**（足够开 R46，也足以关 F2） |
| **弱载体词**（只说明主体是个站点） | 服务器 / 接口 / 页面 / 登录 / 上传 / 站点 / 路径 / 表单 | **不足以开 R46，也不足以关 F2**；单独出现时**走 F4**（F4 不适用或读不出语境时按下面的兜底出口处理） |

过了 F2 门，再按题型名词选 `ctf-*` 专项：

| 题面里的东西 | 记录 |
|---|---|
| pwn / 本地通但连远端就断 / 栈溢出利用 | `ctf-pwn` |
| 没见过的格式 / 跑起来像有虚拟机转逻辑 / 反编译不出来 | `ctf-reverse` |
| 算数的题 / 给了串看不懂的字符 / 老式手工解太慢 | `ctf-crypto` |
| flag 藏在跑过的进程里 / 题目附件是一份内存镜像或 PCAP | `ctf-forensics` |
| 样本跑起来先睡、沙箱快超时、行为要捞全 | `ctf-malware` |
| 只有一个网名和一张头像，要把公开信息翻出来 | `ctf-osint` |
| 给了一张图和一段音频，不知道藏在哪一层 | `ctf-misc` |
| 把机器学习用到打比赛 | `ctf-ai-ml` |
| web 题 / 登录框输啥都回显一样 | `ctf-web` |
| 新手、没人带、每天练什么、从哪下手 | `ctf-beginner-hub` |
| 题解出来了但步骤写不清、要整理成能教别人的 | `ctf-writeup` |
| 靶机开了几个口、先打哪个、按什么顺序 | `solve-challenge` |

**F2 的限制（必须一起记着）**：F2 是四条里**最弱**的一条。
- 没有 F2 门（题面有**强锚点**）时，同名主题一律走 F3 / F4 / R46。
- **设备与链路取证不适用 F2**：`memory-forensics-volatility`（R46）与 `traffic-analysis-pcap`（R46）
  拿的是主机内存镜像、交换机流量；这类即使没有"客户"字样，只要主体是**自己的主机 / 交换机 / 链路**，
  仍判 R46，不进 F2。F2 只在题面把它当**题目附件**（"附件是个内存镜像"+"flag"）时才成立。
- F2 的判断是**读题面语境**，不是关键词匹配；把它写成裸词表会大面积误吸（实测见 `../../kernel/07-kernel-sweep/REPORT.md`
  的负向对照一节）。

**F3 工具化动作（ctf 侧独有的 7 条记录，R46 无对应记录）**——这是**唯一**能把"题面完全没有比赛词"
的条目切到 R47 的硬判据：

| 题面动作 | 记录 |
|---|---|
| 拿字典 / wordlist 挨个试路径、目录 fuzz | `strix-ffuf` |
| 批量看哪些还活着、记标题和状态码 | `strix-httpx` |
| 爬全站链接、把手工点不全的路径列全 | `strix-katana` |
| 拿现成指纹 / 模板批量扫一批站 | `strix-nuclei` |
| 把注入点丢给工具自动跑 | `strix-sqlmap` |
| "先快速扫一遍" | `strix-quick` |
| "按标准流程扫" | `strix-standard` |

**F4 语气（次级判据，权重最低）**：只在 **F1–F3 全不命中、且题面已经是 Web / API / 站点安全主题**时才用。
题面是**待做的测试 / 待验证的假设**（试试 / 看看会不会 / 怎么证明影响 / 得确认影响 / 丢给工具跑跑看）
→ R47；题面是**已经观察到的现象**（居然…了 / 结果不对 / 读到了不该读的 / 已经执行了里面的东西）→ R46。
依据：strix 的 13 条漏洞专项描述的是"怎么测这一类"，hack 侧同名记录描述的是"真实目标上已经发生了什么"。
**F4 不适用于非安全主题**——"做个对照试试""得试一下"在产品、实验、评测语境里是常用句式，硬套会把非安全需求吸进 R47。
**F4 判 R46 的兜底（不再给默认方向：补齐语境三问，补不齐就走弃权出口，依据 `work/readtable-mask2/`）**：
若 F4 判了 R46、但题面里**没有任何强锚点**（没说客户、没说自己的站/机器/线上/生产），
**既不默认 R47、也不默认 R46**。同主题在 strix 侧也有专项记录（`strix-path-traversal-lfi-rfi` 对
`path-traversal-lfi`、`strix-broken-function-level-authorization` 对 `idor-broken-object-authorization`），
所以"缺强锚点"这件事本身**不构成任何一边的证据**；此时先按下表补齐语境：

| 补齐问题 | 若是 | 若否 |
|---|---|---|
| ① 这是**你自己的系统 / 资产**（客户、我们线上、我的站 / 机器），还是别人递来的**题目 / 样本 / 靶场**？ | 偏 R46 | 偏 R47 |
| ② 你要的是"**确认它有没有问题 / 修掉它**"，还是"**证明它能被利用 / 把利用链走通**"？ | 偏 R46 | 偏 R47 |
| ③ 题面里有没有**比赛、靶场、flag、writeup、评分、新手入门**这类语境？ | R47 | 用 ① ② 判 |

三问都答得上来就按上表判；**答不上来（题面读不出所有权、也读不出意图）走弃权出口**：标 `uncertain`，
补问一句"这是比赛 / 靶场 / flag 语境，还是真实目标的测试？"，按本文件 `needs_review` 处理，
不许拿"缺强锚点"当理由硬猜 R47。

**F4 同句冲突的裁决规则（补，依据 `../../kernel/07-kernel-sweep/REPORT.md` §6①，修 N276）**：
同一句里同时出现两类标记时，**以收尾分句的动作为准**——观察在前、下一步待做在后 → **R47**。
例（N276 原句）：「站内有个跳转参数，改成外面地址**居然真跳**，**得确认影响**」——
前半"居然…了"是已观察现象（R46 标记），收尾"得确认影响"是下一步待做（R47 标记），两者都是 F4 原文示例 →
**判 R47**，不再无解弃权。

**为什么撤掉默认方向（实测依据，必读）**：

- **实测**：`work/readtable-mask2/`（第二轮读表盲测，300 条）里引用 F4 的判定共 36 条，
  其中**实际触发这条兜底改判的 27 条里判错 19、判对 8，准确率 29.6%**——低于抛硬币。
- **翻默认方向不是解**：把默认方向从 R47 翻成 R46，只是把"19 错 8 对"翻成"19 对 8 错"，
  **净 +11 条全部来自迎合那批答案键的默认值，不是新信息**；而那批答案键自身已有噪声证据
  （N171 与 N273 几乎是同一道题、答案却分属两个包）。⇒ **不给默认方向。**
- **代价**：不再有批量兜底。无强锚点的题面从"默认落到 R47"变成"三问能答就判、答不出就交回用户"，
  读表吞吐下降——这是**有意接受的代价**；本条改动只登记撤掉了一个实测 29.6% 的默认方向，
  **不声称准确率因此提升**（重跑读表盲测是另一张卡的事）。
- **残余风险**：题面是"我自己的测试环境跑通了但没写'我的'"这类真实场景时，三问 ① 读不出所有权，
  会交回用户而不是自动判 R46；交回时的补问就是在补这条信息。
- **历史留档（已作废的口径，仅供追溯）**：被撤掉的"改判 R47"默认方向在 `work/boundary-verify` 那 19 条上
  曾把 4 条弃权（N266 / N272 / N277 / N278）变成 R47、把总数从 10/19 抬到 14/19；那个净收益来自
  **改默认方向**而非新信息，故按上面的实测撤掉；当时的备选改法 A（兜底只在连载体词都没有时才触发）
  一并作废。
- **只有弱载体词**（服务器 / 接口 / 页面 / 登录 / 上传 / 站点 / 路径 / 表单）出现时同样走兜底这条——
  弱载体词不构成强锚点，既不开 R46 也不关 F2（见上节两栏表）；此时补齐三问，而不是取默认方向。

**弃权出口（两种情形都走，写进结论，不许硬猜）**：
① **F4 兜底三问补不齐语境**（上文：无强锚点，且读不出所有权、也读不出意图）——不许退回"默认 R47"；
② **F1–F4 全不命中**。
两种情形都标 `uncertain`，补问一句"这是比赛 / 靶场 / flag 语境，还是真实目标的测试？"，
按本文件 `needs_review` 处理。
（`work/boundary-verify` 那 19 条里"F1–F4 全不命中"是 **0 条**——说明新判据对"无信号题面"的覆盖是好的；
弃权出口因此不是默认路径，只兜"读不出语境"的题面。）

#### R49（`community/apk-extension/`，`apk-reverse-community` 1 条 `-293`）正面判据

这条记录 `legacy_description` 原文（registry 逐字）：

> Reverse engineer, debloat, de-ad, patch, or re-sign Android APKs, and analyze their runtime
> and server-side behaviour. Use for an .apk/.aab/.dex/.so sample, smali or dex patching,
> Frida hooking, repacking, ad or SDK removal, API probing, or deciding whether a client-side
> patch can work. Covers recon, anti-tamper, membership limits, surgical dex patching,
> repack pitfalls, device setup, and a failure catalogue.

**P1 载体轴（优先级最高，先判这条）**：题面主体是 **APK / AAB / DEX / SO / 安装包 / 应用 / 这个包 /
改完的包 / 老应用** → 进 APK 侧。**看权限、组件、源码资源、反编译 manifest 这类只读分析走 R1**
（`skills/apk-reverse/`）；要下面 P2/P3 那套改动与适配能力时才走 **R49**。

**P2 动作轴（`legacy_description` 逐条点名，命中任一即 R49）**：

| 题面动作 | 原文依据 |
|---|---|
| 重签名 / 重新签名 / 让系统重新认它 / 改完包名 | `re-sign` |
| 重打包、改完装回去 | `repack` |
| 字节级改 dex、外科式 dex patch、砍无用组件瘦身 | `surgical dex patching` `debloat` |
| 摘广告 / 摘第三方统计 SDK / 去开屏弹窗 | `de-ad` `ad or SDK removal` |
| 客户端写死的开关、会员校验，改个值自己说了算 | `membership limits` + `deciding whether a client-side patch can work` |
| 改完装不上、装上去被说"有风险"、换台机器就装不上 | `repack pitfalls` |
| 一改就闪退 / 像是被改过就查出来 | `anti-tamper` |
| 真机 / 动态插桩下看它运行时干了啥、挂上调试就装乖（要找的是"检测点在哪"） | `analyze their runtime` + `Frida hooking`；⚠️ **见下方警示** |
| 改完包服务端不认、认客户端指纹 | `server-side behaviour` + `API probing` |
| 老系统 / 老机器装不上，要动点手脚让它跑起来 | `repack` + wrapper 的 `packaging / install` 脚本组 |

> ⚠️ **P2「挂上调试就装乖」这一行的判据卫生警示（依据 `../../kernel/07-kernel-sweep/REPORT.md` §6⑥）**
>
> **结论：R49 覆盖反调试/检测点定位，按本表 P2 判 R49；`work/natural-300/cases.json`（「仓库外」：本包同级工作区的 `work/natural-300/`，不在本包内，见 `docs/CAPABILITY-REPORT.md`）里若干条
> `expect_note` 声称的"R49/apk-extension does NOT cover …anti-debug or startup callbacks"是错的，勿采信。**
>
> 核实依据（`registry.json` `community-apk-reverse-community-293` 的 `legacy_description` 逐字原文）：
> `…and analyze their runtime and server-side behaviour…`、`Frida hooking`、
> `…deciding whether a client-side patch can work`、`Covers recon, anti-tamper, …, a failure catalogue`
> ——`anti-tamper` 与 `analyze their runtime` / `Frida hooking` 三项都在原文里，无一条能被读成"不覆盖"。
>
> 旁证（raw 正文，同一条记录 `adapted_path` = `SKILL.md`）：
> 该源包自带 `../community-raw/apk-reverse-source/references/detection-and-anti-analysis.md`（首行标题 *"Detection, anti-analysis, and when
> to stop fighting it"*，正文 `detects root/emulator/hook/debugger`、`TracerPid`）与
> `scripts/anti_detect_probe.js`，并在 SKILL.md 失败表里写明 *"The app dies **only while you are
> attached/rooted**"* → 指回 `../community-raw/apk-reverse-source/references/detection-and-anti-analysis.md`。这是**反调试/检测定位的专门文档**，
> 与"不覆盖 anti-debug"直接相反。
>
> **不改 `cases.json`（它不在本卡写作用域内），但读表者以本节为准**：那批 `expect_note` 是出题侧
> 留下的已知偏差标注，判 APK 动态行为题时不要拿它推翻 P2。

**P3 能力轴（要的是 apk 能力登记/体检，不是在分析某一个包）**：apk doctor / capability matrix /
能力矩阵 / `dexutil` / `dart-aot` / `lsposed` / `kernelsu` / `protobuf-raw`。
**适用范围（依据 §6⑤）**：P3 **仅在问能力登记 / 体检时命中**——即题面主体是"这套 apk 工具链本身有哪些能力 /
装好了没有 / 体检"，而不是"分析某一个具体的包"。`work/boundary-verify` 那 19 条里 P3 **触发 0 次**
（没有一条问 apk doctor / capability matrix），**本轮无法评价，不是失效**，故**保留不删**。
判 APK 题面时先过 P1（载体轴）；具体包的具体问题仍以 P1/P2 为准，P3 只是"问工具不问包"时的那一档。
依据：`community/apk-extension/SKILL.md` 描述行 + 7 个脚本组（`baseline / doctor`、`DEX / Dart`、
`packaging / install`、`native / ELF`、`Frida / dynamic`、`protocol / service`、`governance / leak scan`）。

**R49 vs R46 的移动侧切分（唯一正确的分界轴）**：

- **R49**：主体是"我手上这个包 / 我改过的包"，目标是让它**改得动、装得上、跑得起、服务端认**。P2 那 10 条全部在此。
- **R46**：主体是"别人的 / 现成的 App"，目标是**证明它能被绕**，不改包，只找绕过手法。R46 只有 3 条移动记录：`android-pentesting-tricks`、`ios-pentesting-tricks`、`mobile-ssl-pinning-bypass`。
- **一句话判据**：问自己"**我改完这个包之后还要装回去吗？**"要 → R49；不要、只是要证明能绕 → R46。
- **网络侧自保走 R46，不走 R49**："一挂代理就断网"、"证书那关过不去"、"得让它认我的证"——这三句都是**不改包、只想找绕过手法**，属 R46 `mobile-ssl-pinning-bypass`。R49 的 runtime 面要的是**动态插桩下看它干了啥**，不是绕它的网络检测。
- **反例（不属于 R49 的 APK 题面）**："看这个 APK 的权限、组件、源码资源，反编译 manifest" —— 只读静态分析、不改不动不装 → **R1**（`skills/apk-reverse/`，见上节能力清单）。注意别把它和 R49 混为一谈：`legacy_description` 明写 R49 拥有 `analyze their runtime and server-side behaviour` 与 `Frida hooking`，所以"想知道它启动时连了哪些服务器"、"真机上看它运行时干了啥"这类**动态行为观察**是 R49，不是 R1。
- **R46 不接 APK 题面**：R46 那 103 条里与 APK 相关的只有 `android-pentesting-tricks` / `ios-pentesting-tricks` / `mobile-ssl-pinning-bypass` 三条，且是**渗透技巧**（找绕过点），不是包分析；任何 APK 题面都不该判到 R46。

## Route Not Matched — Handling

If the current task doesn't match any table above, **do NOT force-fit into existing skill**:

1. Check if it's an edge case of an existing skill (can extend coverage)
2. If truly new type, proactively propose new skill to user:
   - Suggested skill name and coverage
   - Required toolchain
   - Relationship to existing skills
3. User confirms → execute per `CONTRIBUTING.md`
4. After creation, update this routing matrix

**AI does NOT need to wait for user to discover the gap. Route failure IS the signal to propose a new skill.**

## Path Crossing (Cross-Module Scenarios)

Some tasks span multiple modules. Common crossings:

```
APK Reverse Path:
  apk-reverse/decode.ps1 → Java layer analysis
  ↓ If core is in .so
  ida-reverse/ or radare2/ → .so analysis
  ↓ If dynamic verification needed
  apk-reverse/frida-run.ps1 → Frida Hook

Frontend JS Reverse Path:
  js-reverse/Observe → locate target request
  ↓ Need stronger browser/CDP/Hook/Network capability
  jshookmcp → runtime sampling, breakpoints, interception, SourceMap/AST
  ↓ After confirming entry function
  js-reverse/Rebuild → Node local reproduction
  ↓ Need environment patching
  js-reverse/references/env-patching.md

DSL VM Reverse Path:
  reverse-engineering/dsl-vm-reverse/SKILL.md → identify DSL VM (IIFE + single-letter vars + DG() switch-case)
  ↓ Extract opcode table & constant table
  reverse-engineering/dsl-vm-reverse/SKILL.md Phase 2-4 → opcode classification, C[9] constant analysis
  ↓ If runtime capture needed
  browser-automation/ → Playwright/Selenium CDP injection
  ↓ If pure API protocol needed
  js-reverse/ → Observe→Capture→Rebuild (API layer only)

CTF Competition Path (via CTF-Sandbox-Orchestrator):
  ../CTF-Sandbox-Orchestrator/ctf-sandbox-orchestrator/SKILL.md → build sandbox model
  ↓ Route by dominant evidence
  competition-web-runtime/ or competition-reverse-pwn/ or competition-identity-windows/
  ↓ Blocked → return to master
  ctf-sandbox-orchestrator → re-route

Web Pentest + BurpSuite MCP Path:
  browser-automation/ → auto-browse target with Burp proxy
  ↓ Traffic captured
  burpsuite MCP proxy_history → AI analyzes all requests
  ↓ Suspicious endpoints found
  burpsuite MCP intruder_attack → automated enumeration
  ↓ Vulnerability confirmed
  docs-generator/ → generate pentest report
```

## 任务完成自检（声称完成前 MUST 通过）

- [ ] 我是否完成了路由三轴匹配（目标类型 + 用户意图 + 工具链）？
- [ ] 我是否在路由成功后读取了目标 skill 的 SKILL.md？
- [ ] 路由未命中时，我是否提议了新增 skill 而非强行匹配？
- [ ] 我是否走了**探测层四级递进**（`Resolve-ReverseToolSpec`）定位实际路径（而不是只跑一条 `Get-Command` 查空就报缺工具、也不是拿 `TOOLS.md` 里的装法当路径猜）？