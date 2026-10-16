# 已知边界（Known Boundaries）

> **这份文件回答一个问题**：哪些事这个项目**做不到**，以及为什么。
>
> 不是待办清单 —— 待办是「还没做」，这里是「**在当前环境下做不到**」。
> 写下来是为了让以后接手的你（或 agent）不必反复撞同一堵墙，
> 也不必把「环境限制」误判成「项目没做完」。
>
> **什么时候读**：想知道某件事为什么没做 / 怀疑项目有缺陷时。先看这里，再看别的。

---

## 0. 一句话

**技术侧已闭环。** 剩下的三条全部是**环境或法律层面的边界**，不是代码缺陷。

---

## 1. Linux / macOS 下的实际行为未实跑

**做不到的原因**：本机装了 `wsl.exe` 本体但**没有任何发行版**（`wsl --list` 为空），
装一个要几 GB 且通常需要重启。macOS 更不可能。

**已经做到的**：
- CI 引用的 27 个文件**全部存在**（`verify-workflow-refs.py` 逐条核对）
- CI 里 3 处指向空气的 `.sh` 已删除并加注释（它们在 Windows 本机执行不到，
  只有 runner 会红 —— 已由 `verify-workflow-refs` 挪到本地发现）
- `test-bash-workflow.sh` 的 BSD `sed` 不兼容已修（macOS runner 上的真实故障）

**仍然依赖**：ubuntu / macOS runner 上的实际执行。CI 每次 push 都会跑。

**判断影响**：如果你只在 Windows 上用，这条**完全不影响**。

---

## 2. `community-raw/` 1089 个文件的逐个功能测试

**做不到的原因**：占全仓 38%，是 vendored 的第三方内容（上游快照），
不是本项目写的代码。逐个测既不现实，也超出了「技能包」的职责边界。

**已经做到的**：
- 每个 vendored root 都有 registry 归属与锁定提交（`verify-repository-security` 检查）
- 路由层面有**反例门禁**守着它们不被误触发（`test-community-decoys.py` 57 条用例）
- 供应链 pin gate：所有自动安装源都钉了版本/提交

**判断影响**：这些是**参考资料**，用的时候按需读，不需要逐个验证。

---

## 3. 三个门禁不在 `ci-gates.json` 清单里（设计取舍，非缺陷）

```
check-fences.py
audit-doc-code.py
test-audit-doc-code-negctl.py
```

**为什么没塞进去**：那份清单的 `script` 路径按 **skillpack 根**解析
（`run-ci-gates.py:58` 的 `ROOT = parents[2]`），而这三个脚本在仓根另一层。
硬塞会破坏 resolve 语义，也会让 `verify-gate-wiring` 的「清单 ↔ workflow 对撞」失真。

**补救措施**（已经做了）：
- 三者都有**独立负控**，且已接进 `ci.yml` 直接调用
- `test-check-fences-negctl.py`（10 个用例，覆盖全部四个出口）
- `test-audit-doc-code-negctl.py`（25 常规 + 8 对抗）
- `test-ci-negative-controls.py` 的 7 条负控**够不着**它们 —— 这是已知的空隙

**判断影响**：**功能上不缺失**（它们照常在 CI 里跑、照常会红）。
唯一的差别是「负控的覆盖范围」少了一层。

---

## 4. 任何真实目标上的效果

**做不到的原因**：这是技能包，不是测试环境。真实目标的验证依赖你
在**授权范围内**的实操。本包所有能力都已在本机可复现的范围内验证过。

**已经做到的**：所有「验证」都以本机实跑为准 —— 落盘文件、改动字节、
协议响应、断点命中。不接受「看起来对了」。

---

## 5. 许可证分发方案（需要你判断，不是技术问题）

**现状**：仓库含 **209 篇 GPL-3.0 改编内容**（源自 `LING71671/open-reverselab`；数字与 `skillpack/NOTICE` 同判据，现算见 `verify-gpl-distribution-boundary.py`）。
- `skillpack/NOTICE` 正确记录了每个来源的许可范围与锁定提交
- 根 `LICENSE` 有免责声明
- `plugin.json` 的 `license` 字段已从 `MIT` 改为 `SEE-PARENT-REPO`

**三条路**：

| 方案 | 后果 |
|---|---|
| A. 整体转 GPL-3.0 | 合法最稳，但不能再以 MIT 分发 |
| B. 隔离 GPL 内容 | 知识库少 209 篇 |
| C. 保持现状（当前） | **私有不对外分发**技术上不触发义务 |

**判断影响**：**只要你不对公分发，现在完全没问题。**
对公分发前需要你（或律师）拍板。

---

## 6. 测量假象：长跑脚本不能用后台子 shell 测

**这不是项目缺陷，是操作陷阱** —— 但长期使用一定会重复踩，所以写在这里。

**现象**：用 `( ... &)` 或 `cmd &` 在后台跑长脚本，然后 `sleep N` 去看日志，
会看到「零输出」「卡住几百秒」。**全是假象** —— 后台子 shell 被回收时
输出一起丢了。

**实例**：`apk-debug doctor` 先后测出「150 秒零输出」「710 秒」，
实际前台跑**只要 21.7 秒**、rc=0。围绕这个假象排查了很久，
还一度以为是自己新加的代码把脚本拖慢了。

**正确做法**：

```powershell
# ✅ 前台 + 重定向到文件，用工具的 timeout 兜底
time (timeout 600 powershell -File script.ps1 > "$TEMP/out.log" 2>&1)
tail -5 "$TEMP/out.log"

# ❌ 后台子 shell —— 输出会随进程被回收而丢失
( powershell -File script.ps1 > log.txt 2>&1 & ) ; sleep 90 ; cat log.txt
```

**同类陷阱**（今天都踩过）：
- `Invoke-Native` 原本只收 stdout —— dumpcap 的进度全在 stderr，
  抓到 17227 包却报「什么都没抓到」
- 门禁运行**期间**改文件 → 后面几条读到中间态，报出假红
  （`kernel hubcore` / `verify-routing-coherence` / `test-p0-friction`
   三条都这样红过一次，干净复跑全绿）

**判断影响**：遇到「脚本卡住」时，**先换个测量方式再下结论**。

---

## 7. `git status` 永远显示两个 kernel 文件被改（预期行为，不是脏）

```
 M kernel/03-bundle/bundle-meta.json
 M kernel/05-tests/RESULT.md
```

**为什么**：这两个文件是 `kernel/05-tests/run_all.py` 的**实跑证据存档** ——
每次跑都写入生成时间、总用时、每条断言的实测数字。
所以只要跑过门禁，它们就变了。

**差异性质**（实测确认）：
- `built_at` / `生成时间`：刷新
- `总用时`、各场景毫秒数：随机器负载波动
- **断言结果完全不变**（151 通过 / 0 红）

**该怎么处理**：**不用管**。

- 它们**不是脏文件**，是「最近一次实跑的记录」
- 想让 `git status` 干净就 `git checkout -- kernel/`（记录回退到上次提交的版本，
  不影响功能）；但下次跑门禁又会变
- 仓库历史上就是这么用的（`71f5613 chore(kernel): 刷新场景套件实跑时间戳`），
  想留痕就随跑随交

**判断影响**：看到这两个文件变了**不要以为有未完成的改动** —— 先 `git diff` 看一眼，
如果只有时间戳和毫秒数，就是正常的。

---

## 附：这份清单本身怎么维护

1. **不要把它变成待办列表** —— 待办在 `docs/HANDOFF-*.md`，那份会随工作推进更新。
2. **边界消失时要删条目** —— 比如哪天你装了 WSL 发行版并跑通，第 1 条就该删。
3. **新边界要说明「为什么做不到」** —— 只写「没做」没有价值，
   要写清是环境不允许、还是设计取舍、还是需要人拍板。

---

## 相关

- [`HANDOFF-2026-10-11.md`](../_归档-禁读-历史文档/_history/HANDOFF-2026-10-11.md) —— 最近一轮的交付与**待办**（**已归档，AI 禁读**；只有人需要追溯时再翻）
- [`AUDIT-2026-10-10-FINAL.md`](../_归档-禁读-历史文档/_history/AUDIT-2026-10-10-FINAL.md) —— 20 小时全项目终审，含 6 个「从未真正工作过」的门禁（**已归档，AI 禁读**）
- [`../START-HERE.md`](../START-HERE.md) —— 项目入口

---

## 8. `check_r4_no_fixed_flow` 的扫描边界（明写的取舍，不是漏的）

2026-10-15 独立审计指出：「无固定流程」这条门的旧判据只抓**章节标题**式的 `## 第 1 步 / Step 1`，
正文里成串的 `Step 1 / Step 2 / Step 3 …` 全部漏过 —— 实测 `binary-diff`、`patch-diff-exploit`、
`firmware-pentest`、`ida-reverse` 四张卡都中招，门却一直报 PASS。

**已修**：判据加了「连续 ≥3 行的 `Step N / 第N步` 正文块」检测 + 自带控制组（喂一份只在正文成串的样本必须判红）。
那四张卡已全部改成**判据表 / 信号标题**（`Step 1..9` → 「信号：… → 动作」，`完整流程` → `怎么走（判据，不是流程）`）。

**边界**：本判据**只扫 `skills/*/SKILL.md`**，不扫各卡 `references/**` 下成串的 `Step N`。理由：
- `SKILL.md` 是"这个技能该怎么做"的**第一读面**，那里的工序会被当成流程 → 必须清；
- `references/**` 里成串的 `Step` 多是**具体技法的演练**（某条 IDOR 利用链、某个固件场景的复盘），
  属于技术内容，不是"全局任务流程"。

**这不是"没做"，是"明写不做"**：如果你（主人）认为 references 里那一层也该清，说一声，判据扩一行就行。

已知仍在 `references/**` 里的成串 Step（截至 2026-10-15）：
`api-security/references/dos/05-http2-continuation.md`、`dos/09-cache-cdn-dos.md`、
`idor/01-idor-enumeration.md`、`rate-limit/02-brute-force-tactics.md`、
`patch-diff-exploit/references/diff-tools-comparison.md`。

---

## 9. 已知未闭环项（2026-10-15 独立审计披露，**明写在此，不是藏着**）

> 下面每一条都是**审计用证据指出来的真问题**，本轮能修的都修了，修不完的**明写在这里**，
> 好让下一个接手的人（和下一次审查）一眼看到，而不是被"全绿"晃过去。

| # | 问题 | 证据 | 现状 |
|---|---|---|---|
| 1 | **行为门在 CI 里从不带 `--run`** —— 只跑结构检查，模型行为一次没验 | `test-trigger-rate`/`test-assault-behavior` 在 `ci-gates.json` 里 `args: []`（已复核） | **2026-10-16 已真跑并拿到数据**（不再是"一次没验"）：<br>· `test-trigger-rate --run --limit 10` → **10 技能 / 200 次调用 / 0 运行错误**，触发率全部达标（正例 ≥0.5、近邻负例 <0.5）；重复测量稳定（attack-chain 1.0/0.0、apk-reverse 0.6/0.1 两轮一致）。<br>· `test-assault-behavior --run --probe` → **2/4**（C3「自己发现并说明 MCP 通道」两次都判红 —— 正是这门要抓的历史故障）。<br>· 台账：`%LOCALAPPDATA%\reverse-skill\behavior-runs.jsonl`。<br>**CI 接线仍未做**（要真调模型＝花钱+慢，按设计挂 non-blocking 手动跑）；但**门本身已修好两个会让实跑失效的缺陷**（超时形同虚设 + 失败打假分，见第 18 条）—— 修前那次实跑挂 35 分钟还给出假分，修后 10 秒准时返回。 |
| 2 | **路由主门原本没有任何反例** —— 最该被证伪的「这句话该路由到哪」最没保护 | 审计独立复算 | **部分已修**：主门 `scripts/test-routing.ps1` 已加**默认必跑的前置控制组** —— 先拿「期望值故意写成不存在的路由 id」的用例跑一遍，必须判红，否则整门 exit 1；然后**照旧跑全量 247 条真基准**（控制组不参与、不干扰）。其余三道（`verify-routing-signals` / `test-routing-signals` / `test-route-ranking`）**仍是纯断言、无负控** |
| 3 | **路由基准里大量问句由被测路由自己的关键词拼成** —— 自己出题自己考（原来写的「223/227 = 98.24%」给不出算法） | 审计独立复算 + `python skillpack/skills/scripts/route-benchmark-tautology.py` | **已改为可复算**：判据固化进脚本 docstring（hint 的 token　en≥4 / 中文 2-gram　里 ≥90% 落在预期路由的 must/mustAll 词项表里 ⇒ 自证）。**分母**：基准 247 条 = 20 条主人原话 + 227 条非标记；可测量 225 条（另 2 条无 token / 无路由词项，不能算）。实测：62/225 = 27.56%（严格自证）；216/225 = 96.0%（含至少一个被测词项）。原 98.24% 应该是宽口径 + 不同分词，不再当已知事实。替换成真实语料仍未做。★ 2026-10-17 复算：`route-benchmark-tautology.py` 仍报 62/225 = 27.56%（严格自证）、216/225 = 96.0%（含至少一个被测词项），与上一致 —— 这条不是过期读数，是**仍然成立**的开放项。
| 4 | **固件战场工具层是空的** | `binwalk`（pip 包缺 `binwalk.core`，死壳已删）、`unblob` 都没装；`qemu-system`/`openocd` 也没有 | **试过了，本机做不了**：装了 Rust 1.99 后 `cargo install binwalk` 失败 —— ①MSVC 工具链缺 `link.exe`（PATH 里的 `link` 是 Git 自带的 GNU coreutils）；②改走 `stable-x86_64-pc-windows-gnu` 时 **rustup 解包 OOM**（`memory allocation of 16777216 bytes failed`，这台 VM 内存不够）。半装的工具链已卸干净、默认已回 MSVC。**要补这一块，需要**：给 VM 加内存 + 装 MSVC Build Tools（或换台机器）。★ 2026-10-16 又试了另一条路：`pip install unblob`（纯 Python 解包器，本以为是绕开 Rust 的那条）→ 其依赖 `pyperscan` 仍走 maturin/cargo 编译原生库 → `Failed to build wheel for pyperscan`，**同一根因**（没有可用的编译链），未安装成功、环境未改变。**结论**：固件战场在本机短期补不上，属**环境未就绪**而非代码缺口 —— 现在 `selfcheck` 的分战场分母会显式报 `固件 0/6`，不再被"逆向 25/25 全绿"盖住。★ **2026-10-16 工具层逐条实测推翻了这个结论**：固件那块的刀**已经躺在机上**了 —— `binwalk` 换成了 **v3 独立可执行版**（`D:\Tools\firmware\binwalk\binwalk.exe`，`binwalk --version` → `binwalk 3.1.1`；v3 是 Rust 独立构建，**不再依赖 pip 的 `binwalk.core`**，当初那个"死壳"根因已不存在）；`qemu-system-arm` / `qemu-system-mips`（11.1.0）、`openocd`（xPack 0.12.0+dev）、`flashrom`（v1.7.0）、`unsquashfs` / `mksquashfs`（squashfs-tools 4.7.5）、`jefferson`、`ubireader_extract_files`、`innoextract` / `innounp` **全部能被探测层解析、也都真跑得起来**，且都已写进配方表（`tool.binwalk` / `tool.qemu-system-arm` / `tool.qemu-system-mips` / `tool.openocd` / `tool.flashrom` / `tool.unsquashfs` / `tool.mksquashfs` / `tool.jefferson` / `tool.ubireader` / `tool.innoextract` / `tool.innounp`），`python skillpack\skills\tests\test-tool-recipes.py` 实测 **ok=69 skip=0 fail=0**。**仍缺的只有 `unblob`**（探测层解析不到，无配方），已在 `skills/config/tool-recipes.json` 的 `_no_recipe` 里登记理由
| 5 | 换机「一条命令」的代劳口径（**12 步口径**，与 `环境初始化.md` §11.5 一致） | `relab2.ps1 setup` 已串：仓根/环境变量/技能挂载/MCP 注册 | **脚本 / `doctor` 覆盖 1–6、8、9**（`doctor` 只读代劳 4/5/6/9，分别报 `死路径` / `toolmap prefer` / `宿主家目录` / `旧状态清点`）；**真人工只剩第 7 步**（卡片载入，走 `kernel/04-console` 工作台，会写宿主的入口文件）与**第 10 步**（`gh auth login`，机器凭据）。★ 2026-10-16 补：剩下那两步**不再沉默** —— `doctor` 现在显式报「GitHub CLI 登录」与「行为门实跑」（从未跑/超 30 天都 WARN），所以"还差哪一步"一眼可见，而不是把它算进"就绪" |
| 6 | 文档 vs 代码体量比 **4.64 : 1** | 审计实测：md 23.71MB/2339 个 vs 代码 5.11MB/354 个 | **部分**：本轮把 10 项历史文档归档进 `_归档-禁读-历史文档/`，并写了禁读口令 |
| 7 | 宿主装机卡与仓库卡漂移，**此前没有门禁比对** | 审计实测 | **已修**：实测 `~/.omp/agent/PERSONALITY.md` 比仓库卡**旧 6 行**（还带着已删的 `步骤: 1)…5)` 工序）——也就是「仓库修好了、机器上跑的还是旧的」。已把宿主文件同步到与仓库卡**逐行一致**（留了 `.bak-carddrift-*` 备份），并在 `relab2.ps1 doctor` 加了**装机卡漂移检查**（逐行比对 `PERSONALITY.md`/`RULES.md` 与 `cards/base|guest/*.md`，不一致就 WARN）。现 doctor 报「宿主入口文件与仓库卡逐行一致」|
| 8 | `x64dbg` 的探测结果指向 `headless.exe`，而项目自己的规则说「不得拉起 GUI / headless 也不等于能交互」 | 审计实测（`START-HERE.md:187-189`） | **2026-10-16 已处理**：`x64dbg-reverse/scripts/start.ps1` 现在自己解析可执行文件（探测层 → 工具根扫描），并把 `headless` 归一成同目录的 GUI 版（headless 不加载 MCP 插件，9094 永远不监听）；只有 headless 时**明确报错退出 2**，不再把死路当启动目标。探测层给的 `Command` 只用于"知道它在哪"，起 MCP 一律走该脚本（卡里已写清）。三条路径有 DryRun 验收记录 |
| 9 | `triage_target` 的第一步调 `diec --extended` —— **不是合法参数**，本机 `diec.exe` 因此**永不返回**（只无限刷 `libpng warning: iCCP: known incorrect sRGB profile`）。一条 triage 会卡满 240 s 超时、stdout 0 字节，还留下 ghost 进程 | 2026-10-16 用 `subprocess.run(timeout=60)` 复现；`TOOLS.md:195` 记的正确形态是 `-d -e -j` | **2026-10-16 已修**：`triage_target` 改回 `diec -d -e -j`（同一样本 0.6 s 返回结构化 JSON），并补一步 `r2 -q -c "iI;q"` 给格式/位数/canary/PIE；`读法` 里写死「diec 只能用 `-d -e -j`，参数写错会挂」。残留的两个 `diec.exe` 已 `taskkill` |
| 10 | **`C:\relab2` 与 `D:\Tools` 是主人定死的约定路径**（换机之后依然是这两个），文档/技能卡里写它们**不是缺陷** | 2026-10-16 主人当场纠正 | **已记入规矩**：我一度把它们当成"本机读数过期"，批量改了 283 处 → 被纠正后**全部回滚**（296 处恢复），并在 `tests/scan-defect-classes.py` 的 D3 里把这两个路径加进白名单，只报**约定之外**的机器路径。★ 以后不许再"推翻"这类已定好的约定 |
| 11 | **本机 `upx`（3.91，Universal Extractor 自带）压-解往返会产出跑不起来的 exe** | 2026-10-16 端到端实测：`ffmpeg.exe` 压壳 rc=0（→ 更小）、解壳 rc=0、大小完全恢复，但**解出来的 exe 运行 rc=0xC0000005**；换 `jq.exe` 同现象（3044 字节与原始不同，13 字节在 PE 头）。`diec` 确认壳已解掉（`含UPX=False`）。 | **2026-10-16 已修**：探测层首选已换成**官方 UPX 5.2.1（win64）** —— `D:\Tools\pack\Unpackers\upx-5.2.1-win64\upx.exe`（`D:\Tools\_map.json` 的 `aliases.upx`），旧首选 3.91w 仍在盘上但不再被解析到。判据按本条写的那样改成了**功能等价**：用 `gcc` 现编一个 `hello.exe`（跑出 `HELLO_OK`）→ `upx -o hp.exe h.exe` rc=0 → `upx -d -o hd.exe -f hp.exe` rc=0 → **跑 `hd.exe` 得到 `HELLO_OK`**（不再用"字节是否逐字节还原"当判据，那是 UPX 本来就不保证的）。`tool.upx` 配方实测 rc=0 且 `upx --version` 给 `upx 5.2.1` |
| 12 | **扫描器余项：D4（不查退出码）/ D5（数据类静默吞异常）/ D6（缺 timeout）** —— 扫得出，但要**逐条人工判**（启发式，含大量误报） | `python skillpack/skills/tests/scan-defect-classes.py`（2026-10-16 实扫） | **D6 已逐条判定完（26 条→真缺陷只有 1 处）**：核心生产路径**全是误报** —— `Popen` **没有** `timeout=` 参数，作者用 `proc.wait(timeout=…)`+`kill()` 才是**正确**写法（`relab2-tools-mcp.py` / `capability-index.py` 都是）；`mcp-lazy-http.py` 是**故意"发射后不管"**（MCP 服务器要常驻）；还有 docstring 里的字符被正则误抓。**真缺陷 1 处已修**：`diagram-generator/scripts/render_diagram.py` 的 `run()` 无超时（`java -jar plantuml.jar` 会挂住）→ 加 300s + `REL2_RENDER_TIMEOUT`。**扫描器 D6 已改用 AST**（不再把 docstring/注释/`wait(timeout=)` 当缺陷）。**剩余**：`verify-doc-links.py:280,320`、`verify-repository-security.py:422,435`（都是 `git` 调用，中风险）+ `register-mcp.py:118` + 10 处 `test-*`（低风险）。**D4/D5/D6 余项已逐条判定清零**（2026-10-16：三类各 **0 处**未判定候选；33 处"有意"已带理由登记，**59 处真缺陷已修**（29+8+22）、**5 处是扫描器误报**（判据已收紧），外加 1 处只有真跑才看得见的（§11.4））。**要动之前先跑扫描器拿最新清单**，别凭这份记录里的数字 —— 逐条处置见下方 **§11** |
| 13 | **`pyghidra-mcp` 通道起不来：`LockException: Unable to lock project!`** —— 根因是**孤儿 `javaw.exe` 持有 Ghidra 项目锁** | 2026-10-16 真调实测：6 条 MCP 通道里只有它 FAIL。查进程发现 `javaw.exe`(PID 6940) 启动于 06:57:13、**父进程已不存在**（孤儿）、活了 41 分钟仍占着锁；项目目录里的 `my_project.lock` 时间戳与它一致 | **已修**：`taskkill /F /PID <孤儿JVM>` → 锁释放 → 真调 `list_project_binaries` 成功（tools=20）。**可复用的判据**：Ghidra 的 `.lock` 文件**不含 PID**（只记 hostname/时间/用户），所以「锁在不在」要靠**找孤儿 JVM**而不是读锁内容；`my_project.lock~` 删不掉（"另一个程序正在使用"）就是**铁证**——真有进程持有。★ 换机/重启后如果 pyghidra 起不来，先 `Get-CimInstance Win32_Process -Filter "Name='javaw.exe'"` 看有无孤儿 |
| 14 | **6 条 MCP 通道的"真调用"（不只 `list_tools`）已全部验过** | 2026-10-16 逐条实测 | `relab2-tools`→`local_tools` ✓ · `rea`(桥)→`binary_session` ✓（33 工具）· `x64dbg-mcp`→`GetDebugState` ✓（80 工具）· `pyghidra-mcp`→`list_project_binaries` ✓（20 工具，清孤儿后）· `angr-mcp`(18 工具) / `idapro`(69 工具) 可达且报"缺参数"属工具自身要求（非通道故障） |
| 15 | **`kernel/05-tests` 曾长期"永远 2 红"（假红），已修成真绿** | 2026-10-16 实测：修前「9 场景 / 148 断言 / 146 通过 / **2 红**」；修后「147 断言 / **147 通过 / 0 红 / 退出码 0**」 | 两个红**都不是缺陷**，是**判据写错**：<br>· **9.2**「工作区干净」拿的是"跑完后的绝对 `git status`" → **任何人的未提交改动都判红**（统筹当时 130+ 处 → 必然红）。**修法**：`run_all.py` 跑前存基线到 `TEMP/.git-status-before`，9.2 只算**新增**行（别人的改动不计）。<br>· **9.1**「真仓库 guard check」在**没有基线**时判红，而同一段注释自己写着"本轮不新建（会覆盖统筹的基线）"= **有意不建**。**修法**：改 `s.note` 如实报告（guard 有没有用由 9.1e 用合成产品真验）。<br>★ **教训**：「永远红」的门等于没有门（没人看）。判据要盯**本轮引入的变化**，不是**绝对状态** |
| 16 | **`switch-mcp.py` 的 `daily` / `full` 会用 `mcp.all.json` **整份覆盖** `mcp.json` → **静默删掉只存在于活跃配置里的通道** | 2026-10-16 DocConverge2 实测发现、父代理核实：本机 `mcp.json` 有 **6** 条（含 `rea`），`mcp.all.json` 只有 **5** 条（缺 `rea`），而两个分支都是 `shutil.copy(full → active)` | **已修**：改成**合并**语义 —— `mcp.all.json` 为准，但 `mcp.json` 独有的通道**保留 + 回写进 all**（两文件不再漂移），输出明确列出保留了哪几条；`show` 也会提示"只在活跃、不在 all 的通道"。**实测**：修前跑 `daily` → `rea` 消失；修后跑 `daily` → 输出「保留了 1 条…rea」，两个文件都变 6 条。备用件在 `%TEMP%\mcp-backup-20261016\` |
| 17 | **回归表 `cases/` 的门有两个盲区：① 两条 case 同 `id` 竟静默 PASS ② `lesson_refs` 从不校验（悬空引用一直没人管）** | 2026-10-16 两个代理并行写 case，各自都用了 `case-004` / `case-005`（素材互补、都是真事，只是编号撞了）→ 8 条 case 里两组重号，门报 `PASS`。另一路复核发现 `case-002` 写着 `field-journal/seed-005 等 seed 系列（正控语料）`，而 `seed-005` 真名是 `seed-005_ad-certipy-esc1.md`（ADCS ESC1，与本 case 的 PRNG/UPX 无关），全 17 篇 seed 里 grep `upx\|prng\|加壳` **零命中** —— 一条**没有对应文件的"经验来源"** | **已修**（`run-regression.py` 加三道检查，每道都验过反例控制组）：<br>① `id` **必须唯一**（重号直接 FAIL 并指出撞了谁）；② **文件名必须与 `id` 一致**（否则按文件名找与按 id 找指向不同东西）；③ **`lesson_refs` 不许悬空**（它和 `expect_chain` 一样是承诺，却从来没被校验）。<br>判据要点：允许 `路径（说明）` / `:行号` / `；` 分隔多条；**绝对路径必须显式标 `[外部]`** 才放行（本仓确有 case 的经验来自已归档的外部项目报告，但**不静默跳过** —— 不标就 FAIL，否则打错字的外部路径会混进来当"已核验"）。<br>**反例实证**：塞同 id → FAIL 报两处；塞 `D:/somewhere/else/REPORT.md` + 不存在的仓内路径 → 两条都被抓；还原后 PASS。**已收口编号**：001–008 连续、无空号、文件名与 id 逐个一致（取证域仍缺真实 case，见 `cases/README.md`）。★ 教训：**"每条 case 一个身份、每条经验有出处"是回归表的前提** |
| 18 | **`test-assault-behavior.py --run` 的 `--timeout` 形同虚设（实测挂 2104 秒），且运行失败会被当成答复打出假分 `1/4`** | 2026-10-16 BehaviorRun 实跑抓到、父代理复核并修：`--timeout 600` 实际挂 **35 分 04 秒**，只有人工 `taskkill /PID … /T /F` 才返回；返回的 `1/4 条通过` 是 `run_session` 失败分支的占位符 `<运行失败: …>` 被 `score()` 照常打分得来的 | **已修**（两个根因）：<br>① **死锁**：`subprocess.run(capture_output=True, timeout=…)` 在 Windows 上遇到 `omp` 拉起的孙进程（bun/node **继承了 stdout/stderr 管道**）→ 父进程被 kill 后管道写端仍在 → `communicate()` 等不到 EOF → **永不超时**。改成**输出落临时文件**（不占管道）+ 超时后 `_kill_tree`（`taskkill /T /F`）再读文件 —— 顺带**超时前已产生的输出仍然拿得到**。<br>② **假分**：失败分支 `return "<运行失败: …>"` 会被当答复打分，看上去像"模型只做到 1/4"，实际是**根本没跑成**。改成返回 `(正文, 错误说明)`，调用方见错误即**判红 + 明写"未验" + 不打分**（退出码 2）；台账写 `"pass": null, "verified": false`，与"0 分"区分开。<br>**实证**：假 `omp`（含孙进程）+ `--timeout 10` → **10 秒准时返回**、孙进程 **0 残留**、输出「未验（超时 10s 已杀进程树）」。<br>★ 同类教训本仓早有：`skills/scripts/test-subprocess-capture-deadlock.py` |
| 19 | **`agent-browser` 装了却每次判「未安装」→ 反复全局安装** —— 它由 `npm -g` 装进了 **node 安装目录**，而该目录**不在 PATH** | 2026-10-16 技能层审计发现、父代理复核修复：`agent-browser 0.27.0` 的真身在 `D:\Tools\runtime\node\node-v22.23.3-win-x64\`（`agent-browser.cmd` + `node_modules\agent-browser\`），而本机的 `node` 是靠 `D:\Tools\cli\node.cmd` 这个 **shim** 暴露的 —— 该目录不在 PATH。于是 `browser-automation/scripts/setup.ps1` 用 `Get-Command agent-browser` 判"已装"时**永远判未装**，每次都重跑一遍全局安装 | **已修**（照 `ROPgadget.cmd` / `capa.cmd` 的先例）：在 `D:\Tools\cli\agent-browser.cmd` 放一个**显式路径** shim，并登记进 `D:\Tools\_map.json` 的 `aliases`。**实证**：shim 直接跑 → `agent-browser 0.27.0`；`Resolve-ReverseToolSpec -Name agent-browser` → `Available=True Via=PATH`；`Get-Command agent-browser` → 解析到 shim。★ **两个坑**（都踩过）：① **不能**把 npm 生成的 `agent-browser.cmd` 直接复制过来 —— 它用 `%~dp0` 找同目录的 `node_modules`，搬走就指错；② `.cmd` 必须 **CRLF + 纯 ASCII**（LF 行尾 + GBK 码页下的中文注释会让 cmd.exe 报 `'""' 不是内部或外部命令`）。★ 与第 11 条（upx）/ 第 9 条（diec）同属「工具本身在，但调用形态错」这一类 |
| 20 | **工具桥（`run_tool`）有三处真缺陷，37 道文本门 + 46 条配方**全都看不见**** | 2026-10-16 工具层逐条实测：① `ctx.resolve('dexdump')` 返回 `D:\Tools\android\Android????????_v2.2\lib\dexdump.exe`、`os.path.exists=False`，而同一条路径在 PowerShell 里逐字完好；② `run_tool('x64dbg', …)` 会去跑 `D:\Tools\cli\start-x64dbg-mcp.ps1`（**项目自己的启动器**，不是调试器本体），`run_tool('ida', …)` 会弹 GUI 窗口；③ 新起一个 MCP 进程第一次问 `local_tools` 要 **25.0 s**，而调用方客户端超时是 **30 s** —— 本次审计真踩到超时 | **三处都已修**（都在 `skillpack/skills/scripts/relab2-tools-mcp.py`）：<br>① **编码**：PowerShell 往管道写 stdout 用的是 `[Console]::OutputEncoding`（本机 cp936/GBK），而这侧一律按 UTF-8 解码 → **凡是路径带非 ASCII 的工具，解析结果全成乱码**、`exists=False`、调起来 `WinError 2`。修法：`PROBE_PS` / `PROBE_ONE_PS` 开头把控制台编码钉成 UTF-8（`$false`=不带 BOM，与 `mcp-status.ps1` 同源）。修完 `aapt` / `dexdump` / `zipalign` / `dex2jar`（都躺在中文目录 `Android逆向助手_v2.2` 下）全部 `exists=True`。<br>② **GUI 闸**：补 `_GUI_TOOL_IDS`（31 个 id，各带理由与 CLI 孪生），`run()` 在 resolve 之前就拒并报出替身 —— `capability-index.py` 早有 `GUI_HINTS` / `NEVER_EXEC` 两道闸，而这条路径此前**一道都没有**。<br>③ **探测表落盘缓存**：`%LOCALAPPDATA%\reverse-skill\tools-mcp\probe-cache.json`，10 分钟新鲜度与内存缓存同义（工具装/卸是低频事件）；实测**新进程第一次问从 25.0 s 降到 0.00 s**，`refresh=true`（ttl=0）仍强制实探。落盘写入 best-effort（失败只意味着下次冷跑，绝不改变探测结果） |
| 21 | **换机第一入口在全新 clone 上是死的（BOM），而本该拦住它的两道 CI 门从未跑过** —— `relab2.ps1` 等 **6 个非 ASCII `.ps1`** 在 HEAD 上缺 UTF-8 BOM；Windows PowerShell 5.1 按系统 ANSI 码页（本机 936）解码 → `ParserError: MissingEqualsInHashLiteral`、入口直接崩。更糟的是 `selfcheck` 仍报「通过 6/失败 0」= **假绿**，新机 agent 会以为装好了。| 2026-10-16 用**真 PS 5.1 + 936 码页**在 HEAD clone 上复现：`relab2.ps1:33 字符: 45` + 乱码 `椤?= $Name`（rc=1）。CI 侧 `shell script syntax check` 的 step4 `Structured routing parity (Bash)` **永久红**（`test-bootstrap-manifest.sh` 的 no-python 负例与 `bootstrap-reverse.sh` 的 `exit 2` 互相矛盾）→ **step5 PSParser 门与 step6 BOM 门永远被 skip**，58 个 run 全部没跑到。| **2026-10-16 已修（4 处）**：<br>① `bootstrap-reverse.sh`：探测不到解释器时不再硬 `exit 2`，改为**交给 `ensure_python_interpreter` 先装再复探**（原注释写的就是这个意图，代码却相反）——CI 的 `apt-get install -y python3` 分支现在真被走到（本地强制 Linux 路径实测 `CALLED:sudo apt-get install -y python3`）。<br>② `test-bootstrap-manifest.sh`：MSYS 工具不能 `ln -s`（DLL 依赖）→ 改**包装脚本**；no-python 负例加**平台守卫**（非 Linux/Darwin 明确 SKIP，不再误红）。本机实测 rc=0。<br>③ 新增**独立 BOM 门** `skills/tests/verify-ps1-bom.py`（已有的 `verify-powershell-syntax.py` 显式按 UTF-8 读入再 ParseInput，**恰好绕开**"PS5.1 自己加载时会怎样"，拦不住 BOM）。登记进 `ci-gates.json`（42 道）+ 重锁 + `verify-gate-wiring` 通过。<br>④ 给 6 个缺 BOM 的 `.ps1` 补 BOM（`relab2.ps1` / `master-route.ps1` / `switch-mcp.ps1` / `scope-probe.ps1` / `browser-automation/setup.ps1` / `ida-reverse/open.ps1`）。<br>**反例控制组**：临时去掉 `relab2.ps1` 的 BOM → 门判红 rc=1；还原 → 绿。 |
| 22 | **`Resolve-ReverseToolSpec` 的 PATH 级命中会遮住 `_map.json` 别名 —— 别名表形同虚设** —— 解析是**四级递进、命中即停**（env → PATH → `_map.json` 别名 → 工具根）。第 2 级 PATH 只要命中就返回，**永远轮不到第 3 级别名**。本机 `D:\Tools\cli` 在 PATH 第 **13** 位，而 `%APPDATA%\Python\Python314\Scripts`（里面有无扩展名的 POSIX 脚本 `ROPgadget`、以及**裸** `capa.exe`）在第 **11** 位 → 长期命中跑不起来的形态。| 2026-10-16 工具层逐条实测：`test-tool-recipes` 的 `tool.ropgadget` 报 `WinError 193`（不是有效 Win32 应用）、`triage.capabilities` 报 `default embedded rules not found`。两处别名表（`aliases.ROPgadget`→`cli\ROPgadget.cmd`、`aliases.capa`→`cli\capa.cmd`）**都登记了正确形态，但都够不着**。| **2026-10-16 已修（两处，缺一不可）**：<br>① **仓库侧** `lib/Bootstrap.ps1`：原逻辑 `if ($pathList -notcontains $cliCandidate) { 前置 }` —— 只要 `cli` 已在 PATH 就什么都不做（不管排第几）。改成**「`cli` 不是第一个 PATH 段就挪到最前」**（幂等）。这把别名从"够不着"变成"第 2 级就能命中正确形态"。<br>② **工具根侧** `D:\Tools\_map.json`：给 `capa` 的 deny 补 `*\Tools\cli\capa.exe`（`cli\capa.exe` 也是**裸 exe**、同样缺 rules 包装；`cli\capa.cmd` 才是带 `--signatures/--rules` 的正确形态）。原 deny 只拦了 `*Roaming\Python*\capa.exe`，漏了 cli 下的裸 exe。<br>**实证**：修前 `ROPgadget`/`capa` 解析到 `%APPDATA%\...Scripts\` 下跑不起来的形态；修后都解析到 `D:\Tools\cli\*.cmd`。`test-tool-recipes` 从 `ok=67 fail=2` → `ok=69 fail=0`。 |
| 23 | **换机手册 §11.5 的「步 4/5/6/9」被列为人工，实测全是只读** | 2026-10-16 换机审计（`work/_full-audit/report-newmachine.md` §5.2）：四步**纯只读、无凭据、无交互**，只差把它们从手册搬进脚本；手册与 `KNOWN-BOUNDARIES` 第 5 条对「代劳几步」的口径还互相矛盾（12 步 vs 10 步）。| **2026-10-17 已搬进 `doctor`（只读）**：新增 `死路径`（用户级环境变量死路径 + PATH 死段，**含反例控制组**：塞 `E:\nope-not-here` 报 WARN）、`宿主家目录`、`旧状态清点`（10 个易污染目录，**只清点不删**）；「核工具根映射」原已有（`toolmap prefer`）。**真人工只剩 2 步**：卡片载入（走 `kernel/04-console` 工作台）、凭据（`gh auth login`）。 |
| 24 | **两处门假绿：扫到 0 个文件仍报绿** | 2026-10-17 在**全新 clone** 上实测抓到：`verify-powershell-syntax.py` 的 `$skip` 含 `TEMP`，而 PowerShell 的 `-notmatch`/`-contains` **默认不区分大小写** → clone 到 `%TEMP%\...`（祖先目录叫 Temp）时**全部 .ps1 被 skip**，门报「扫了 **0** 个 .ps1，有解析错误的 0 个 ✓」= 绿（主仓实测 52 个，clone 0 个）。`verify-ps1-bom.py` 同型：非 git 目录 / 路径算错时 `git ls-files` 返回空 → 「被跟踪 .ps1 **0** 个 …… 全部合规 ✓」。| **2026-10-17 已修**：① PS 门改为**只按相对仓库根的目录段、区分大小写**（`-ccontains`）匹配排除项，不再误伤 `%TEMP%` 里的仓库；② 两门都加「**扫到 0 个必须判红**」（本仓有 52 个 .ps1 / 62 个被跟踪 .ps1，0 个只可能是门自己坏了）。**反例控制组**：空树 → rc=1；clone 里塞未闭合 `{` → 报 1 个错误、rc=1；去掉 `relab2.ps1` 的 BOM → rc=1。 |

---

## 10. 核验工具箱在哪（换模型/接手时先看这里）

**判定"项目到底做完了没"不要读任何文档的自述，跑命令**：

```powershell
python skillpack\skills\tests\run-ci-gates.py            # 全量门禁（应 blocked=0 failed=0）
python skillpack\skills\tests\verify-leaves.py           # 逐树杈：每片叶子要有入口
python skillpack\skills\tests\branch-walk.py             # 入口层：自述 vs 独立复算
python skillpack\skills\tests\test-tool-recipes.py       # 工具调用真跑 + 输出内容断言
python skillpack\skills\tests\full-simulation.py --full  # 逐线路真跑（含 MCP 真起）
python skillpack\skills\tests\scan-defect-classes.py     # 缺陷类型扫描（7 类）
python skillpack\skills\tests\feature-tree.py            # 15 层线路树
python skillpack\skills\tests\feature-graph.py --body    # AI 身体图（全部类型节点互通）
```

各层的**权威说明**见 `docs/PROJECT-MAP.md`；**带数字的快照**在 `docs/_snapshots/`（会过期，读前先重跑命令）。

---

## 11. 缺陷扫描 D4 / D5 / D6 余项：逐条判定清零（2026-10-16）

> 对应 §9 表格第 12 条。**结论：三类各 0 处未判定候选。**
> 每个候选都有归宿，三选一：**真错 → 已修**、**有意 → 已登记（带理由，可逐条核对）**、
> **扫描器误报 → 收紧判据**（判据只认代码，不认字符串/注释）。

**复跑（一切数字以实跑为准）**：

```powershell
python skillpack\skills\tests\scan-defect-classes.py                          # 全量（7 类）
python skillpack\skills\tests\scan-defect-classes.py --only D5 --show-exempt    # 只列豁免+理由
```

实测（2026-10-16）：`D4 0 处（另有 1 处已登记豁免）`、`D5 0 处（另有 31 处）`、`D6 0 处（另有 1 处）`。

### 11.1 两种"登记"机制（豁免不是消失）

| 机制 | 写在哪 | 用在什么情况 |
|---|---|---|
| `# scan-ok: <理由>` | **那行代码旁边**（Python 写在 `pass` 行 / `except` 行；PS 写在 `catch { }` 同行） | 文件可以改 |
| `JUDGED_ELSEWHERE` 登记表 | `skillpack/skills/tests/scan-defect-classes.py` | 文件**不许改**（例如正由他人维护）：必须与命中行命中同一段代码文本 |

三条硬规矩（已写成代码，不是口号）：理由**必填**且 ≥8 字符（空理由/占位理由照报）；
豁免**不消失** —— 报告里单列「另有 N 处已登记豁免」，`--show-exempt` 逐条打印理由；
登记表**自我失效检查** —— 登记过的行/代码变了（条目没被任何命中用上）会被当缺陷报出来，
防止它变成一块长期遮丑的补丁。

### 11.2 "有意"的 33 条（证据 = 代码旁注释 + `--show-exempt` 输出）

| 组 | 条数 | 为什么这样是安全的 |
|---|---|---|
| 超时后的**收尸**（`Kill()` / `communicate()` 失败） | 5 | 超时**已经**被 `Warn2` / `note` / `status=fail` 报出；收尸失败不改变结论（`apk-debug.ps1:499,533`、`emulator-lab.ps1:229`、`master-route.ps1:215`、`test-tool-recipes.py:114`） |
| **轮询探测**：异常＝这一轮没就绪 | 2 | 循环重试，总超时由 `ERR:open_timeout` 统一报出（`ida-reverse/scripts/open.ps1:281,306`） |
| **探测失败本身就是判据**（状态机分流成 busy/down/stale） | 1 | `ida-reverse/scripts/start.ps1:77`：失败后按 listening/guiOwners 分流，不会冒充 healthy |
| 失败会**落到后面的统一报错** | 3 | `$procId` 保持 0 → 后面的 `exit 2`（`ida-reverse/scripts/start.ps1:491,509`、`x64dbg-reverse/scripts/start.ps1:96`） |
| 多层**兜底**里的一层（失败＝没有这一层，≠"成功"） | 6 | `lib/Bootstrap.ps1:258`（种子层）`:469`（工具根候选之一）`:501`（带预算的目录扫描）、`lib/HostRuntime.ps1:56` / `smoke.ps1:64`（取不到就退回 `Get-Command pwsh`）、`switch-mcp.ps1:12`（退回 `python`） |
| 只影响**显示/编码**，不影响任何判定 | 3 | `mcp-status.ps1:34`、`register-skills.ps1:45`、`x64dbg-reverse/scripts/start.ps1:40`（`[Console]::OutputEncoding`） |
| 探测/自愈是 best-effort（注释已写明不抛） | 2 | `lib/PsModulePathInit.ps1:42`、`lib/Bootstrap.ps1:551`（`Sync-ReverseEnvironment` 幂等） |
| 抛异常的**就是断言本身** | 1 | `test-contract-v2.py:690`：不抛才由 `else` 记 FAILURES |
| 坏条目**不会算成功**（被记成 `<missing>` 并判 `ok=False`） | 1 | `experiments/desc-ab/ab_runner.py:143` |
| 规范化**对称**（allow 集与候选走同一个函数） | 1 | `verify-path-and-target.py:179`：IDNA 转不了就按原串比，不会放宽允许集 |
| `try` 只用于**探测合法性**，非法正是本分支的设计语义 | 2 | `parse-skill-frontmatter.py:154,161`：非法 `\uXXXX` / `\xHH` 按字面量处理 |
| MCP 启动器**刻意"发射后不管"** | 1 | `mcp-lazy-http.py:156`：等它会挂死（后端子进程被 detach）；挂死上限由端口轮询 deadline 强制 |
| 判据**比退出码更强** | 1 | `x64dbg-reverse/scripts/start.ps1:155`：紧随其后的 `Test-Listening` 才是判据，没起就 `exit 2` |
| 只包住一次 `Write-Host`（展示用） | 1 | `master-route.ps1:352`（影子建议） |
| 内层探测，**外层统一报错** | 1 | `selfcheck-newmachine.ps1:162`：外层 catch 会 `Bad`「探测层载入失败」 |
| 防御性包裹（块内语句本身不抛），失败表现为"不打印" | 1 | `browser-automation/scripts/setup.ps1:92` |
| 懒通道的 listening 本就置 `$null` | 1 | `mcp-status.ps1:135`：URL 解析失败 → 未知，不冒充"在监听" |

### 11.3 判成"真错"并已修的

| 类 | 处数 | 修法 |
|---|---|---|
| D4 不查退出码 | **29** | 逐处补上判定：`radare2/recon.ps1` **6**（合并成一个 `Invoke-R2Section`，失败即抛；另见 §11.4 实跑追加的 1 处）· `test-p0-friction.ps1` **8**（都改成 `Bad`）· `apk-debug.ps1` **5**（adb install 走 `$script:AdbRc`；`adb devices`/`scrcpy`/`frida` 分别 `Die`/`Warn2`）· `bootstrap-reverse.ps1` **4**（postInstall / npx / setup 失败即抛）· `smoke.ps1` **2** · `verify-routing-coherence.ps1` **2**（`Bad`）· `case-init.ps1` **1**（`master-route` 降级保留兜底，但改 `Write-Warning` 说清）· `switch-mcp.ps1` **1**（转发退出码） |
| D5 数据类静默吞 | **8** | `capability-index.py` 收窄异常（`(OSError, subprocess.TimeoutExpired)`）并注释；`mcp-lazy-http.py` / `relab2-tools-mcp.py` 改成**留日志**（后者原先把 `sha256=""` 当成正常）；`test-subprocess-capture-deadlock.py` 收窄；`feature-graph.py` / `verify-leaves.py` 的 `ci-gates.json` 解析失败改 **stderr 警告**（原来会让图/引用表悄悄少一截）；`emulator-lab.ps1` 设备解析中断改 `Write-Warning`；`master-route.ps1` **2 条**：fuse 超时补 note（收尸那半条见 §11.2）、fuse 整段失败补 `fuse-skip` note（原来静默退回 fallback） |
| D6 缺 timeout | **22** | 21 处本轮补 + 1 处此前已修（`render_diagram.py`，见 §9 第 12 条）：`git` 类 60–120s、CLI/门禁脚本类 300s（`test-golden-route.py:138` 600s）、`test-tool-recipes.py` / `ab_runner.py` 的 `communicate/wait(timeout=)`、`relab2-tools-mcp.py` 三处。都在门禁/工具调用路径上；门禁总入口另有 30 分钟兵底 |
| 扫描器**误报**（判据已收紧） | **5** | D5 两条：`verify-no-forbidden-reads.py:244`、`scan-defect-classes.py:18` —— 都是**文档字符串里的** `except: pass`；D6 三条：`relab2-tools-mcp.py:20`、`register-mcp.py:118`、`test-subprocess-capture-deadlock.py:7` —— 都是 docstring 里的 `subprocess.run(...)` 说明文字。D5/D6 检测器已改用 **AST**（`_d5_python` / `_subprocess_calls`）：字符串与注释一律不算调用 |

> 另有 **1 处扫描器看不见的同类真缺陷**（实跑 recon.ps1 才暴露，报告各段全空而 rc=0）——见 §11.4。

### 11.4 实跑又抓出 1 处同类真缺陷（扫描器只能看语句形态，这条要真跑）

| 步骤 | 命令 | 实测结果 |
|---|---|---|
| before | `radare2/scripts/recon.ps1 -TargetPath notepad.exe`（内部为 `r2 -q -c iI -- <target>`） | 五个段**全空**，退出码 0 → 人看到的是"成功" |
| 定位 | `r2 -q -c ij -- notepad.exe` | `{}` —— r2（Windows, 6.2.4）把 `--` 当成了**文件名本身**，等于一个文件都没打开 |
| 对照 | `r2 -q -c ij notepad.exe` | 真 JSON：`"file":"C:\\Windows\\System32\\notepad.exe","format":"pe64"…` |
| 对照 | `r2 -q -c iI <不存在的文件>`（**不带** `--`） | 打不开时**有**报错、rc=1 → 所以退出码检查是有效判据，只是被 `--` 那条路径绕过了（rc=0） |
| after | `recon.ps1 -TargetPath notepad.exe` | 基本信息段 30 行真数据（arch/bits/bintype/subsys…），节区 7 条（.text/.rdata/.data/.pdata/.didat/.rsrc/.reloc） |
| after（负例） | `recon.ps1 -TargetPath <目录>` | 抛出「r2 对 'iI' 零输出（exit 0）—— 目标没被真正打开」 |

修法两条（都在 `radare2/scripts/recon.ps1`）：① 去掉目标前的 `--`；② 把"这一**段**零输出"当
**功能性**判据（基本信息段只要能打开文件就必然有内容）—— 只判退出码兜不住"静默空报告"。
★ 这同时解释了 `radare2/SKILL.md` 里那条验收（"侦察产物落盘：stdout 重定向到文件，文件含
imports/strings 段且非空"）为什么以前**永远做不到** —— 修前它只能产出空壳。

**跨平台差异（如实标注，未在本机验证）**：Linux 孪生脚本 `radare2/scripts/recon.sh` 同样写了
`rabin2 -I -- "$TARGET"` / `r2 … -- "$TARGET"`。**[推断]** glibc 的 getopt 会把 `--` 当**选项终止符**
吃掉、不当作参数，所以那边本来就正常 —— 即这是 **POSIX getopt 与 Windows 侧 r2 自带解析的差异**，
不是笔误。本机没有可用 Linux（§1），因此 **`recon.sh` 保持原样**，只把这条差异记在这里：
**在 Windows 上调 r2/rabin2，不要加 `--`**。

### 11.5 顺带修掉的**扫描器自身**缺陷

1. **按行切分与 tokenizer 不一致**：`str.splitlines()` 会额外在 `\v \f \x85 U+2028 U+2029` 上断行，
   而 Python 的 tokenizer 只认 `\n / \r\n / \r` —— 于是**含 U+2028/U+2029 的文件行号整体偏移**。
   `parse-skill-frontmatter.py` 里正好各有一个（实测：LS=1 PS=1），导致该文件行号偏 2：
   写好的 `# scan-ok:` 理由**永远定位不到**（实测复现），报告的行号也会指错行。
   已改成统一的 `_lines()`（按代码行切分，与 `ast` 一致）。
2. **字符串不是调用**：D5/D6 的 Python 检测器改成 **AST**（`_d5_python` / `_subprocess_calls`）——
   旧正则会命中**文档字符串里**的 `except: pass`（本脚本自己的 docstring、`verify-no-forbidden-reads.py`
   注入给子进程的审计钩子源码）与 `subprocess.run(...)` 的**说明文字**（`relab2-tools-mcp.py` /
   `register-mcp.py` / `test-subprocess-capture-deadlock.py` 的 docstring）。这 5 条已按"误报"计
   （见 §11.3 第 4 行），AST 顺带给出准确行号。
