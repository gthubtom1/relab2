# Changelog

All notable changes to **reverse-skill** are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]
### Added
- **`verify-ps1-bom` —— 非 ASCII `.ps1` 必须有 UTF-8 BOM（新门，CI 第 42 道）** —— Windows PowerShell 5.1 加载无 BOM 的 `.ps1` 时按系统 ANSI 码页解码（本机 936），含中文的脚本被解错字节边界直接 `ParserError: MissingEqualsInHashLiteral`，**换机第一步就是死的**；而 `selfcheck` 还报「通过 6/失败 0」= 假绿。已有的 `verify-powershell-syntax.py` 拦不住它（那道门显式按 UTF-8 读入再 ParseInput，恰好绕开"PS5.1 自己加载时会怎样"），所以 BOM 必须由**独立**的门来查。门自带反例控制组（去掉 BOM → 判红 rc=1）。本轮同时给 6 个缺 BOM 的 `.ps1` 补了 BOM。见 `docs/KNOWN-BOUNDARIES.md` 第 21 条。
- **`test-diff-runner-parse-negctl.py` —— `cases:` 写法的负控（K1 防复发）** —— E2E 审计唯一的「照文档做就会卡死」项：`templates/assault.md` 的 cases 原写单行文本，而 `parse_assault()` 只认嵌套列表 → 按模板填完直接 `ERROR: no input given`、RC=2。修好后原本**没有任何门守护**（assault 负控验的是 `review_case.py`，不调 diff-runner）。本负控直接 import `parse_assault`，喂「嵌套列表 / 单行文本 / 真实模板」三种输入。
- **`relab2 known` —— 一条命令看「已知边界」** —— 此前「项目有哪些已知缺陷/约定」只存在于 `docs/KNOWN-BOUNDARIES.md` 正文里，被问到时只能"去翻文档"。现在 `.\relab2.ps1 known` 直接列出全部编号条目的编号 + 标题，`-Json` 出结构化数组（供脚本消费），并指向全文路径。**这是本轮唯一新增的用户可见命令**；它只读，不改任何状态。
- **安卓模拟器能力层**（夜神 / 雷电 / 蓝叠 / MuMu / MEmu / 官方 AVD）—— `skills/apk-reverse/scripts/emulator-lab.ps1`，18 个动作：发现 / 连接 / 实例启停 / 画像 / 输入注入 / 截图 / 抓包三层 / mitm CA / frida-server 部署。**不预装模拟器**：端口不写死，用「厂商 CLI 自报（MuMu 走 `MuMuManager info` 的 JSON）+ 端口扫描（走探测层 `Test-ReverseTcpPort`）+ `adb devices` 已有条目」三路合并去重，装上就自动认出来。配套 `references/emulator-lab.md` 记端口表、各家控制 CLI 语法与抓包三层的取舍；`test-emulator-lab.ps1` 是契约测试（含反例控制组与 MuMu JSON fixture，**不需要装任何模拟器**）。
- **经验卡体系落地** —— `skills/experience-cards/`（仓级共享目录，跨技能）+ `skills/scripts/experience-card.py`（`new` / `search` / `validate` / `stamp`）+ `skills/scripts/test-experience-card.py`（晋级门 + 8 类坏卡反例控制组 + 4 条检索质量用例）。判据的唯一来源仍是 `web-protocol-reverse/references/contract/experience-card-schema.md` 的 7 条晋级门，本目录只放**已晋级**的卡。首批 5 张卡全部来自实战（原生 stderr 中断脚本、`$script:` 作用域、门禁判据须外部可观测、minSdk 边界、PS 5.1 `ConvertFrom-Json` 顶层数组）。
- **「查经验卡」接进全部 45 个 skill 的 ACTION REQUIRED** —— 插在 precedent 那一步之后（纯防御类插在第一个编号步骤前），并重排后续序号。知识库只有出现在必经之路上才会被真的用起来。
- **R1 路由补模拟器维度** —— 模拟器是 APK 动态链路的一环，但裸词「模拟器」此前会把「模拟器抓包」路由到 js-reverse、把「雷电模拟器 adb 连接」判成 low confidence。判据轴 = 安卓语境（adb/frida/抓包/apk/install 任一，或雷电/夜神/蓝叠/MuMu/MEmu/nox 厂商名）。
- **CI 门禁 23 → 25 条** —— `test-experience-card`（python，经 `run-ci-gates` 间接接线）与 `test-emulator-lab`（powershell，直接写进 `ci.yml`）；`ci-gates.lock.json` 重新生成，`verify-gate-wiring` blocked=0 needs_review=0。
- **CI runs remaining unwired suites** — `test-p0-friction.ps1` on the Windows leg of `routing-tests` (Windows PowerShell 5.1); `case-review/tests/test_review_case.py` in the Linux `case-contract` job. `test-workflow-title-safety.ps1` was already wired.
- **Binary Ninja route and skill** — added `binary-ninja-reverse` for HLIL/MLIL/LLIL, Python API, and an explicitly enabled loopback community MCP bridge; Binary Ninja remains a manual commercial dependency.
- **Optional Codex adapter plugin** — added `plugins/reverse-skill/` without changing the client-neutral core or auto-registering MCP servers.
- **Benchmark coverage for R40 (case-evidence-review)** — the route had a single English case; added three cases covering its previously-untested branches (Chinese `证据链`/`证据图`/`可追溯性`/`案件审查`/`案例审计`, and English `evidence.?graph`/`fixity.?check`/`case.?audit`), each verified through both the PowerShell and Bash routers.
- **Route↔benchmark coverage gate** — `verify-routing-coherence.ps1` now fails when any `routing.json` route has no `routing-benchmark.json` case, enforcing the benchmark meta's "add a case when you add a route" rule (the reverse of the existing ghost-expect check).

### Fixed
- **32 位目标只能看到「请您用 x32dbg 来调试这个程序」，且被误判成「MCP 坏了」** —— 症状：拖一个 32 位 PE 进 x64dbg，弹窗拒绝加载，`LoadBinary` 永远 `NO_TARGET`，而错误信息里**不写**"架构不匹配"。三处真缺陷串成一条：① `register-mcp.py` **只生成 `x64dbg-mcp`(9094) 一条**，`x32dbg-mcp`(9095) 只能手工加 —— 于是它带着 `D:\Tools\cli\start-x64dbg-mcp.ps1` 这种**机器专属**路径，换机或重新注册就丢；② `read_x64dbg_token()` 只 glob `release/x64/`，x32 永远拿不到自己的 token；③ `x64dbg-reverse/scripts/start.ps1` 只能靠人记着传 `-Arch x32`，忘了就起 x64dbg。修法：`start.ps1` 新增 **`-Target <样本>`**，读 PE `e_lfanew(0x3C)`→`Machine`（`0x014C`→x32/9095、`0x8664`→x64/9094、其它→exit 2），显式 `-Arch` 仍优先；`register-mcp.py` 改为按 arch 循环生成两条通道、token 按 `Port` 字段配对（不会串），启动器统一指向**随仓库走**的 `x64dbg-reverse/scripts/start.ps1`。新增第 43 道门 **`verify-debugger-arch`**（阻塞码 20）钉住这三处，并带反例控制组（删掉 `-Target` → rc=20）。实测：`-Target easy_crackme.exe` → `Machine=0x014C -> x32` → 冷起 9095 监听成功；`-Target gh.exe` → `0x8664 -> x64` → 9094 已在听直接返回 0。
- **工具桥（`relab2-tools-mcp.py`）三处真缺陷，37 道文本门 + 46 条配方全都看不见** —— ① **编码**：PowerShell 往管道写 stdout 用的是 `[Console]::OutputEncoding`（本机 cp936/GBK），而 Python 侧一律按 UTF-8 解码 → **凡是路径带非 ASCII 的工具，解析结果全成乱码**（`aapt`/`dexdump`/`zipalign`/`dex2jar` 都躺在 `Android逆向助手_v2.2` 这种中文目录下），`exists=False`、调起来 `WinError 2`。修法：`PROBE_PS`/`PROBE_ONE_PS` 开头把控制台编码钉成 UTF-8。② **GUI 闸**：`run_tool('x64dbg', …)` 会去跑项目自己的启动器、`run_tool('ida', …)` 会弹 GUI 窗口 —— 而 `capability-index.py` 早有 `GUI_HINTS`/`NEVER_EXEC` 两道闸，这条路径一道都没有。补 `_GUI_TOOL_IDS`（31 个 id，各带理由与 CLI 孪生），在 resolve 之前就拒并报出替身。③ **探测表落盘缓存**：新进程第一次问 `local_tools` 要 **25.0 s**，而调用方超时 30 s（本次审计真踩到）。加 `%LOCALAPPDATA%\reverse-skill\tools-mcp\probe-cache.json`（10 分钟新鲜度）→ **25.0 s 降到 0.00 s**，`refresh=true` 仍强制实探。
- **`agent-browser` 装了却每次判「未安装」→ 反复全局安装** —— 它由 `npm -g` 装进了 **node 安装目录**（`D:\Tools\runtime\node\node-v22.23.3-win-x64\`），而该目录**不在 PATH**（本机 `node` 靠 `D:\Tools\cli\node.cmd` shim 暴露）。于是 `browser-automation/scripts/setup.ps1` 用 `Get-Command agent-browser` 判"已装"时永远判未装，每次重跑一遍全局安装。照 `ROPgadget.cmd`/`capa.cmd` 先例，在 `D:\Tools\cli\agent-browser.cmd` 放**显式路径** shim 并登记进 `_map.json`。★ 两个坑：不能直接复制 npm 生成的 `.cmd`（它用 `%~dp0` 找同目录 `node_modules`）；`.cmd` 必须 **CRLF + 纯 ASCII**（LF + GBK 中文注释会让 cmd.exe 报 `'""' 不是内部或外部命令`）。
- **`test-assault-behavior.py --run` 的 `--timeout` 形同虚设（实测挂 2104 秒），且运行失败会被当成答复打出假分** —— ① **死锁**：`subprocess.run(capture_output=True, timeout=…)` 在 Windows 上遇到 `omp` 拉起的孙进程（bun/node **继承了 stdout/stderr 管道**），父进程被 kill 后管道写端仍在 → `communicate()` 等不到 EOF → `--timeout 600` 实际挂了 **35 分 04 秒**，只有人工 `taskkill /T /F` 才返回。改成**输出落临时文件**（不占管道）+ 超时后杀**进程树**再读文件（超时前已产生的输出仍拿得到）。② **假分**：失败分支 `return "<运行失败: …>"` 被 `score()` 照常打分，输出 `1/4 条通过`——看上去像"模型只做到 1/4"，实际是**根本没跑成**。改成返回 `(正文, 错误说明)`，调用方见错误即判红 + 明写「未验」+ **不打分**（退出码 2），台账写 `"pass": null, "verified": false` 与"0 分"区分。**实证**：假 `omp`（含孙进程）+ `--timeout 10` → 10 秒准时返回、孙进程 0 残留。
- **回归表 `cases/` 的门有两个盲区：两条 case 同 `id` 静默 PASS；`lesson_refs` 从不校验** —— ① 两个代理并行写 case 各用了 `case-004`/`case-005`，8 条里两组重号，门照报 `PASS`（旧实现只把 `id` 当必填字段，从不查唯一性）。② `case-002` 的 `lesson_refs` 写着 `field-journal/seed-005 等 seed 系列（正控语料）`，而 `seed-005` 真名是 `seed-005_ad-certipy-esc1.md`（ADCS ESC1，与该 case 的 PRNG/UPX 无关），全 17 篇 seed 里 grep `upx|prng|加壳` **零命中**——一条**没有对应文件的"经验来源"**。修法：`run-regression.py` 加三道检查（`id` 唯一 / 文件名与 `id` 一致 / `lesson_refs` 不悬空），**绝对路径必须显式标 `[外部]`** 才放行（不静默跳过，否则打错字的外部路径会混进来当"已核验"）。三道都验过反例控制组。同时收口编号：001–008 连续、无空号。
- **`switch-mcp.py` 会静默删掉 MCP 通道** —— `daily` / `full` 两个分支都是 `shutil.copy(mcp.all.json → mcp.json)` **整份覆盖**。而 `mcp.json` 里可能比 `mcp.all.json` **多**若干条（本机实测多一个 `rea`），于是跑一次切换就把那条通道**拷没**，且不报任何错。修法改成**合并**语义：`mcp.all.json` 为准，但 `mcp.json` 独有的通道一律**保留并回写**进 `mcp.all.json`（两个文件不再漂移），输出里明确列出保留了哪几条。实测：修前跑 `daily` → `rea` 消失；修后跑 `daily` → 输出「保留了 1 条…rea」，两个文件都变成 6 条。
- **`relab2.ps1 known` 的两处输出污染** —— ① `exit (Invoke-Known)` 里的 `(…)` 会**捕获函数输出流**并当成 `exit` 的参数，于是 `known -Json` 的 JSON 被整段吞掉（实测输出为空）；② 函数里写 `return 0` / `return 2` 会把 `0` / `2` **打进输出流**（消费者会读到一个孤零零的 `0`，JSON 解析报 Extra data）。修法：switch 分支改为先调用再 `exit 0`，函数内用 `exit 2` 退码、正常路径不写 `return 0`。三路调用（普通 / `-Json` / 退码）已逐个实测。
- **`kernel/05-tests` 长期「永远 2 红」，且两个红都是假红** —— ① 场景 9.2「工作区干净」拿的是"跑完后的**绝对** `git status`"，于是**任何人的未提交改动**都会判红（实测统筹当时 130+ 处未提交改动 → 必然红）；② 场景 9.1「真仓库 guard check」在**没有基线**时判红，而脚本自己的注释写着"本轮不新建（会覆盖统筹的基线）"＝**有意不建**。**「永远红」的门等于没有门。** 修法：`run_all.py` 跑前把 `git status --porcelain` 存进 `TEMP/.git-status-before`，9.2 只算**新增**行（别人的改动不计）；9.1 改为 `s.note` 如实报告（guard 有没有用由 9.1e 用合成产品真验）。实测：**148 断言 146 通过 2 红 → 147 断言 147 通过 0 红，退出码 0**。
- **`scan-defect-classes.py` 的 D6 用正则扫子进程超时，误报淹掉真缺陷** —— 26 条候选里**核心生产路径全是误报**：正则把 **docstring / 注释**里的 `subprocess.run(` 也当代码（`relab2-tools-mcp.py` 的改造说明就被抓了）；而 `Popen` **没有** `timeout=` 参数、用 `proc.wait(timeout=…)`+`kill()` 才是**正确**写法，旧判据只看"同一括号里有没有 timeout"于是把正确写法全报了。改成 **AST**（只认真代码调用节点 + `Popen` 所在函数里有 `wait(timeout=)`/`kill(` 就跳过）。26 条 → 22 条，剩下的才是真的。
- **`diagram-generator/scripts/render_diagram.py` 的外部渲染器没有超时（D6 扫出的唯一真缺陷）** —— `run()` 调 mmdc / dot / plantuml / `java -jar` / rsvg / inkscape 六种渲染器全无超时，`java -jar plantuml.jar` 碰上大图或内存不足会**挂住不放**，把调用方一起卡死。已加默认 300s（`REL2_RENDER_TIMEOUT` 可覆盖）。
- **PS 5.1 `ConvertFrom-Json` 顶层数组只得到 1 个元素** —— 在 Windows PowerShell 5.1 上，`$x | ConvertFrom-Json` 对顶层 JSON 数组返回的是一个**数组对象**，`@()` 包住只得到 1 个元素；PS 7 改成了自动展开，所以同一段代码在 7 上是对的、5.1 上是错的。实测后果：MuMuManager 的 2 个实例被算成 1 个，端点列表渲染成 `System.Object[]:System.Object[]`；空数组 `[]` 同样被算成 1 —— 两个方向都错，说明不是边界情况而是解析语义问题。修法：显式 `@($parsed | ForEach-Object { $_ })`。被 `test-emulator-lab.ps1` 的 MuMu JSON 用例抓到。
- **经验卡检索的两处静默失效** —— ① 整段中文当一个词做 `in` 匹配 → 永远不命中（卡里没有这几个字连在一起）；② 把 `scope` 整个 JSON 塞进检索语料 → `appliesWhen` / `stopsWhen` 这些**键名**也成了可匹配文本，于是「stops 条件」这种查询命中每一张卡。修法：中文二元切词（早先的条件 `re.search(r"[a-z0-9]", bigram)` 在汉字上**不匹配**，纯中文片段一个词都切不出来）+ 语料只取人写字段。两种失效都不报错只是「有输出」，已各补一条用例。
- **R27 自然语言用例自 `876614a` 起从未通过** —— 「蓝队那边想主动出去找找坏人留下的痕迹，而不是等告警」expect=R27 实得=R0，因为 R27 只认 `threat.?hunt` / `blue.?team` 这类术语，不认口语。旧的 36 条门禁跑的是 `work/envinit/run_all_gates.py`，没覆盖 `test-routing-natural.ps1`，所以一直没被发现；今天把 `run-ci-gates` 接进全量门禁后才浮出。给 R27 补一条口语规则（判据轴 = 蓝队/狩猎语境）。
- **经验卡插入器的静默空跑** —— 给每个 skill 插入「查经验卡」那一步时，仓根算错一层导致 `glob` 返回 0 个文件，脚本却报告「改 0 个 / 跳过 0 个」：**看上去跑过了，实际一个文件都没碰到**。现在显式断言目录存在，不存在就 exit 2。
- **macOS BSD sed in bash workflow tests** — `test-bash-workflow.sh` used GNU-only `sed -i 's/…/…/'`. BSD `sed` (macOS) treats the expression as a backup suffix and aborts with `invalid command code`, so Test 4/5 (case-guard reject paths) never ran on macOS. Replaced with a portable `mktemp` + `sed` + `mv` helper and wired `test-bash-workflow.sh` into `macos-bash-compat.yml` so the reject-path contract is covered on macOS CI (closes #135).
- **Kali tool discovery: `yara`** — `yara` is in the Kali bootstrap manifest and the Windows tool catalog and is referenced by four skills, but was missing from `kali/scripts/lib/tool-discovery.sh`, so （工具索引已废止） never reported its path on Kali. Added the catalog entry (`malware-analysis`), matching its sibling analysis CLIs (`binwalk`, `bkcrack`).
- **binwalk could never auto-install on Windows** — `skills/scripts/bootstrap-manifest.json` declared `"bootstrapKind": "winget-package"` with `"wingetId": "ReFirmLabs.binwalk"`, but that id does not exist in the winget community repository (`winget show --id ReFirmLabs.binwalk --exact` → `0x8A150014 NO_APPLICATIONS_FOUND`), and binwalk ships no prebuilt binaries on any GitHub release (`assets: 0` for v3.1.0 and the seven preceding releases), so `bootstrap-reverse.ps1 -Capability binwalk` could only ever fail with a package-not-found error. The Windows entry is now `"bootstrapKind": "manual"` + `"canAutoInstall": false` with a `manualInstallHint` pointing at the Rust toolchain (`winget install Rustlang.Rustup` → `cargo install binwalk`), matching what `firmware-pentest/SKILL.md` already documents. Linux / Kali / macOS are unaffected: `bootstrap-reverse.sh` installs binwalk through apt/brew and does not read this entry. `TOOLS.md`.template` updated to match.
- **IDA MCP HTTP stall** — `run-supervisor.py` patches stock `idalib_supervisor` onto `ThreadingHTTPServer` and accepts Streamable HTTP GET `/mcp` (patch failure is skipped, supervisor still starts). Keep-alive deadlock is **time since last healthy `tools/list`**, not process `CreationDate`; `open.ps1` holds `opening.lock` so in-flight opens are never `-Force`d. New `recover.ps1` is an immediate `-Force` path. Never `taskkill`s `ida.exe`.
- **Broken internal doc links + guard** — removed a dangling `phishing-case-study.md` reference and redirected the missing payloader `反弹shell.md` index entry to its tracked raw data. Added `skills/scripts/verify-doc-links.py`, wired into CI, so internal Markdown links are checked from Git index blobs even when Defender quarantines a working-tree payload file.
- **Windows PowerShell 5.1 encoding** — added a UTF-8 BOM to five non-ASCII `.ps1` scripts (`skills/scripts/verify-doc-facts.ps1`, `apk-reverse/scripts/frida-run.ps1`, `apk-reverse/scripts/rebuild-sign-install.ps1`, `ida-reverse/scripts/start.ps1`, `radare2/scripts/recon.ps1`). Without a BOM, PS 5.1 parses these files as the system ANSI codepage and garbles their Chinese / em-dash string literals; `verify-doc-facts.ps1` was failing four checks under 5.1 (CI only ran it under `pwsh`, which defaults to UTF-8). CI now guards every non-ASCII `.ps1` for a BOM.
- **Evidence-consolidation test fixed + two suites wired into CI** — `test-consolidate-evidence.ps1` printed its success marker but leaked exit 1: it ran `review_case.py --verify-hashes` on a case whose consolidation had (by design) rewritten `E-001.md`, so hash fixity could never pass. Dropped `--verify-hashes`, added an explicit exit-code assertion, and wired both it and `test-bootstrap-codex-encoding.ps1` into the Windows leg of `routing-tests` (both shipped in the repo but were never run by CI).

- **换机 P0：全新 clone 的第一入口是死的（BOM）** —— 6 个非 ASCII `.ps1` 缺 UTF-8 BOM；真 PS 5.1 + 936 码页下 `relab2.ps1 doctor` 与 `setup -DryRun` 都 rc=1（`MissingEqualsInHashLiteral`），而 `selfcheck` 仍报「通过 6/失败 0」= 假绿。已补 BOM，并在 fresh 副本上用真 PS5.1 复验通过。见 `docs/KNOWN-BOUNDARIES.md` 第 21 条。
- **CI `shell script syntax check` 的 step4 永久红，连带 step5(PSParser)/step6(BOM) 永远 skipped** —— `test-bootstrap-manifest.sh` 的 no-python 负例与 `bootstrap-reverse.sh` 的 `exit 2` 互相矛盾（2026-10-08 起 58 个 run 全部没跑到 step6）。已修：bootstrap 无解释器时改走安装分支（`apt-get install -y python3` 实测真被调用）；夹具的 MSYS 工具改包装脚本 + 无 python 负例加平台守卫。
- **`Resolve-ReverseToolSpec` 的 PATH 级命中遮住 `_map.json` 别名** —— 本机 `D:\Tools\cli` 在 PATH 第 13 位、而 `%APPDATA%\...\Scripts`（无扩展名 `ROPgadget`、裸 `capa.exe`）在第 11 位 → 别名表里登记的正确形态永远够不着，`tool.ropgadget` 报 `WinError 193`、`triage.capabilities` 报 `default embedded rules not found`。已修：`lib/Bootstrap.ps1` 让 `cli` **始终前置**；`_map.json` 给 capa 补 deny。`test-tool-recipes` 从 `ok=67 fail=2` → `ok=69 fail=0`。
- **门登记口径漂移**：`validate-integration` 的 `blocking_exits` 由 `[1]` 改为 `[20]`（脚本从不返回 1）；`verify-leaves` 的 `why` 由过期的「1620 片/131 断」更新为实测「1898 片/0 断」。
- **`master-route` 收尾措辞与事实不符** —— 硬编码 `Open PRIMARY SKILL.md … execute ACTION REQUIRED`，但 PRIMARY 可以是 references 文件（R54 即 `assault-entry.md`，且该文件无 "ACTION REQUIRED" 字样）。已改为打印真实路径。

- **换机「假人工」四步搬进 `doctor`（只读）** —— 审计实测手册 §11.5 里 4/5/6/9 四步**纯只读、无凭据、无交互**，只是没人搬进脚本。现 `doctor` 新增：**死路径**（用户级变量死路径 + PATH 死段，含反例控制组）、**宿主家目录**（哪家宿主真装了）、**旧状态清点**（10 个易污染目录，只清点不删）。「核工具根映射」原已有（`toolmap prefer`）。见 `docs/_history/HANDOFF-2026-10-16-本轮收尾.md`。

- **两处门假绿（在全新 clone 上实测抓到）** —— `verify-powershell-syntax.py` 的 `$skip` 里有 `TEMP`，而 PowerShell 的 `-notmatch`/`-contains` **默认不区分大小写** → clone 到 `%TEMP%\...` 时**所有 .ps1 被 skip**，门报「扫了 0 个，0 个错误 ✓」= 绿（实测：主仓 52 个，clone 0 个）。改为**只按相对仓库根的目录段、区分大小写**匹配。同时两门都加「**扫到 0 个必须判红**」（本仓不可能没有 .ps1，0 个只能是门自己坏了）。反例控制组：空树 → rc=1；clone 里塞未闭合 `{` → 报 1 个错误。

### Changed
- **Coherence clamp (identity-preserving)** — `RULES.md` hot path is `master-route` → `case-init` → PRIMARY. `routing.json` remains the only route table; `MASTER-ROUTING.md` priority order is verified against JSON. `routing.md` is advisory. `precedent-auth.md` no longer grants auth.
- **IDA open** — lock files may force a temp copy; `.i64` / `.idb` are never deleted.
- **IDA MCP keep-alive** — `start.ps1` reuses a healthy HTTP server, launches `idalib_supervisor` via windowless Python, never `taskkill`s `ida.exe` (no `/T`). A listening 13337 with `tools/list` timeout is treated as busy, not dead, so the 1-minute watchdog cannot kill a supervisor mid-`idb_open`. `open.ps1` talks ida-pro-mcp 2.x `idb_open`/`idb_list`.
- **IDA discovery** — `ToolDiscovery.ps1` now catalogs `idalib-mcp`, `ida-pro-mcp`, and `ida` with Program Files + per-user Python fallbacks.

### Added
- `ida-reverse` watchdog / scheduled-task installer / GUI launcher / supervisor wrapper (`watchdog.ps1`, `install-autostart.ps1`, `start-gui.ps1`, `run-supervisor.py`) plus portable `LOCAL-SETUP.md`.

## [1.0.1] — 2026-08-08
### Added
- **Routing single source of truth** — `skills/config/routing.json` (R0–R39 keyword rules with `must` / `mustAll` / `exclude` semantics). `master-route.ps1` now reads this file; hardcoded routing tables removed from scripts. Routing knowledge lives in one place.
- **Routing regression benchmark** — `skills/tests/routing-benchmark.json` (163 bilingual cases, 40 quick) + `skills/scripts/test-routing.ps1` runner. Any routing change must keep the benchmark green.
- **Routing keyword coverage expansion** (benchmark-driven): burp suite family, pcap/wireshark, root-detection/certificate-pinning, buffer overflow, `.so`/native/JNI, go binaries (中文), js-encrypt, webshell, privilege escalation, S3/object storage, memory dump, incident response, Bluetooth/BLE, USB, Unity/game reverse, security assessment, and more.
- **Supply-chain pin gate** — `verify-routing-coherence.ps1` now fails on any auto-install capability lacking `pinnedVersion` / `pinnedCommit` / `pinPolicy` / asset hash. Pinned: frida-tools 14.10.4, pwntools 4.15.0, agent-browser 0.31.1, ida-pro-mcp @commit, SecLists/ProxyCat @commit, nuclei v3.9.0; winget sources annotated with `winget-latest` policy.
- **Client-neutral integration contract** — routing, tests, manifests, and case workflows remain independent of Claude Code, Codex, Cursor, OpenCode, or any other client; client adapters are optional and must not define repository identity.
- **Skill navigation index** — `skills/INDEX.md` auto-generated from SKILL.md frontmatter by `extract-summaries.ps1` (`-Check` mode for CI drift detection).
- **CI pipeline** — `.github/workflows/ci.yml`: Windows + Ubuntu matrix (PowerShell shim for Linux) running test-routing / verify / smoke / INDEX check / JSON validation, plus `bash -n` syntax checks.
- **Example case** — `examples/ctf-demo/` full workflow walkthrough (route → scope gate → timeline → evidence → report).
- **frontmatter completion** — `dsl-vm-reverse/SKILL.md` gained name/description frontmatter (was the only module missing it).
- **README refresh** — updated the multilingual project overview, release badge, current capabilities, and sponsor showcase layout.
- `case-review/`: read-only Evidence Graph Review with scope, timeline, work item, Finding, Path, and optional SHA-256 fixity checks
- Domain skills R21–R27, R29–R30: `protocol-reverse`, `ghidra-reverse`, `cloud-k8s`, `windows-ad`, `digital-forensics`, `code-audit`, `threat-hunting`, `wifi-wireless`, `browser-extension-reverse`
- High-quality skills R28, R31–R38: `ot-ics`, `macos-reverse`, `thick-client`, `go-rust-reverse`, `hardware-security`, `database-security`, `email-security`, `identity-federation`, `radio-sdr`
- Wired into `MASTER-ROUTING.md`, `master-route.ps1`, routing tables, domain map, role-map, coherence tests

### Removed
- `game-reverse/` (not a product focus; Unity/IL2CPP remains via `reverse-engineering` + seed-014)

### Fixed
- **Upstream mixed-EOL files** — 3 markdown files committed with CRLF while `.gitattributes` declares `*.md eol=lf`; normalized to LF so `git status` stays clean on fresh clones.
- Routing: sigma vs malware, LLM 越狱 vs iOS 越狱, 完整渗透/打到域控 vs AD 域控, forensics vs OT ics; master-route.ps1 rewritten UTF-8 BOM for PS 5.1 CJK
- Linux/macOS bootstrap: register PentestSwarm MCP with a verified executable path after Go install or when already installed

### Security
- Core scripts do not write client-global instruction files; client-specific integration remains outside the routing core.
- Added `docs/PACKAGE-SECURITY-AUDIT.md`: static audit of package executables (no backdoor / no auto DB wipe found)
- Pin supply-chain floating tags: jshook `@0.3.4`, pentestswarm `v0.1.0`
- Bootstrap integrity: GitHub zip/jar downloads verify `assetSha256` (manifest) or GitHub API `digest`; mismatch deletes file and fails
- Pin jadx `v1.5.6` and apktool `v3.0.2` with published SHA256
- Remove shell evaluation from Kali user-home resolution and pass Frida hosts through argument arrays
- Write the Burp MCP token atomically with owner-only permissions on POSIX filesystems
- Reconnect the Burp MCP bridge when Burp starts after the bridge and parse one stdio message per line
- Enable authentication for bootstrapped Anything Analyzer MCP servers and register the bearer token with supported clients
- Stop each stale IDA MCP process individually before starting a replacement
- Add Bash case initialization, authorization guard, and a structured router that reads the same `routing.json` as PowerShell
- Verify Bash routing parity in CI without introducing a client-specific plugin manifest
- Enforce immutable Kali/Windows bootstrap sources for Frida, IDA MCP, Agent Browser, ProxyCat, Nuclei, and pwntools
- Reject path-like Bash case names and scope authorization checks to the contract's auth/network/signoff sections
- Align Bash network defaults with PowerShell: authorized URLs use `authorized_target_only`, while offline readiness requires an explicit local sample
- Pin GitHub Actions checkout to the immutable v4.2.2 commit and keep the CI case count synchronized
- Create a functional Kali `proxycat` wrapper after installing the pinned source checkout
- Scope PowerShell authorization fields to their contract sections and reject unsupported network modes in both guards
- Reject unsupported network profiles during case initialization so invalid scopes are never emitted as ready
- Reject unknown case presets in Bash and PowerShell before creating case artifacts, preventing mistyped presets from silently falling back to pending/offline defaults
- Generate `skills/INDEX.md` from tracked skills only, excluding ignored local modules so clean-clone CI stays reproducible
- Fail routing coherence when a configured skill is missing or only exists as an untracked local file

## [1.0.0] — 2026-07-18

First **formal** public release of the reverse-skill skill-router pack.

### Added

#### Ops / combat contract layer (`skills/ops/`)

- `IDENTITY.md` — product identity: lightweight skill router + bootstrap + field-journal (not a Z3r0-style platform)
- `scope-contract.md` — case scope + `network_profile`; **auth not granted → no ACT on target**
- `evidence-finding-path.md` — Evidence → Finding → Path chain
- `role-map.md` — lead / specialist role mapping and handoff
- `timeline-workitem.md` — timeline + workitem coverage
- `sandbox-profile.md` — tool profile mapping
- `skill-supply-chain.md` — Agent Skill / MCP install gate (AST10-lite)

#### PRIMARY routing & case tooling (`skills/scripts/`)

- `master-route.ps1` — PRIMARY route from task hint
- `case-init.ps1` / `case-guard.ps1` — case bootstrap + scope guard
- `append-evidence.ps1` — structured evidence append
- `smoke.ps1` — package smoke checks
- `verify-routing-coherence.ps1` — routing / ops coherence verification
- `test-p0-friction.ps1` — P0 client-side lab friction regression tests

#### Core skills & docs

- Full skill matrix: APK / IDA / radare2 / JS / .NET / mobile / malware / pwn / firmware / EDR / pentest / API / LLM / supply-chain / crypto / binary-diff / patch-diff / attack-chain / docs & diagrams
- `MASTER-ROUTING.md` + `routing.md` / `routing_zh.md` three-axis matrix
- Bootstrap + runtime tool discovery (`bootstrap-reverse.ps1` / `.sh`, `Get-Command`)
- `field-journal` precedent library + completion checklist
- Multi-platform paths: Windows primary, Linux / macOS / Kali docs and scripts
- CTF-Sandbox-Orchestrator competition sub-skills
- Burp MCP extension package (`burp-mcp-full/`)

#### Quality / localization

- UTF-8 integrity for Chinese docs (`RULES_zh`, `routing_zh`, related guides)
- Client-side lab playbook and recon pipeline references for authorized testing friction reduction

### Notes

- `skillpack/skills/TOOLS.md` are **machine-local** and intentionally gitignored; locate tools with `(Get-Command <id> -ErrorAction SilentlyContinue).Source` after clone.
- This tag freezes the skill-router product surface at commit `9fc280b` plus this release metadata.

### Links

- Tag: `v1.0.0`
- Repository: https://github.com/zhaoxuya520/reverse-skill

[Unreleased]: https://github.com/zhaoxuya520/reverse-skill/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/zhaoxuya520/reverse-skill/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/zhaoxuya520/reverse-skill/releases/tag/v1.0.0
