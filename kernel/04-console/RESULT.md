# 04-console 验收记录
> **这是一份带日期的验收快照，反映的是那一天的状态，不是现状。**
> 里面的数字（如文件大小、段数）**不要再引用**——那之后规则又改过好几轮。
> 要看现在是什么，读 [`01-design/当前实测基线.md`](01-design/当前实测基线.md)。



日期：2026-09-27
机器：Windows，Python 3.12.0
服务绑定：只用 `127.0.0.1`
本次没有往任何真实家目录写过东西，全部装/卸都发生在 `04-console/TEMP/` 下。

## 交付文件

| 文件 | 作用 |
|---|---|
| `run.py` | 启动器。`python run.py` / `--no-open` / `--port N`，浏览器用 `os.startfile` |
| `server.py` | `ThreadingHTTPServer`、令牌鉴权、回环限制、四个接口、静态页 |
| `hosts.py` | 13 家宿主识别 + `tasklist` / CIM 活进程扫描 + 装没装判定 |
| `bundle_locator.py` | 定位 `03-bundle`、组装命令行、`stdio=inherit` 子进程调用 |
| `selftest.py` | 一键自测，把验收 1-5 真跑一遍 |
| `web/index.html` `web/app.js` `web/style.css` | 单页，完全离线自足 |
| `README.md` | 用法 |
| `TEMP/` | 假宿主家目录、假打包器、两份自测实录（可整个删掉） |

`TEMP/selftest-fake.txt` 是假打包器那一轮的原样输出，`TEMP/selftest-real.txt` 是真打包器那一轮的。

---

## 验收 1：`run.py --no-open` 起得来，`Invoke-WebRequest` 拿到 `/api/status`

终端输出（原样）：

```
已启动（只听本机）：http://127.0.0.1:58533
页面地址（带一次性令牌，打开就行）：http://127.0.0.1:58533/?t=A9TGK4WvkS-1aSaP67pQKi9MmFO3YPX_
令牌：A9TGK4WvkS-1aSaP67pQKi9MmFO3YPX_
Ctrl+C 关掉。
```

`Invoke-WebRequest`：

```powershell
$s = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:58533/api/status" -Headers @{'X-Token'=$token}
$s.StatusCode
```

```
HTTP 200
{
    "ok":  true,
    "version":  "0.1.0",
    "token":  "A9TGK4WvkS-1aSaP67pQKi9MmFO3YPX_",
    "package":  {
                    "ready":  true,
                    "reason":  "",
                    "missing":  [

                                ],
                    "bundle_dir":  "D:\\临时项目\\hub-dock\\work\\context-isolation\\03-bundle",
                    "source_dir":  "D:\\临时项目\\hub-dock\\work\\context-isolation\\03-bundle\\dist\\hubcore"
                },
    "installed_ids":  [

                      ],
    "counts":  {
                   "hosts_total":  13,
                   "hosts_present":  8,
                   "hosts_installed":  0,
                   "core_kb":  0,
                   "file_count":  0
               },
    "process_probe_known":  true,
    "hosts":  [ ... 13 家，每家 {id,name,installed,core_kb,file_count} ... ]
}
令牌对得上： True
```

没带令牌：

```
无令牌 -> {'http_status': 403, 'body': '{"ok": false, "error": "只听本机，且要带令牌。"}'}
```

---

## 验收 2：`/api/hosts` 在这台机器上扫出 8 个真实家目录

```
命中 13 条
codex      家目录在=True  入口=AGENTS.md        入口文件在=True  已装=False 运行中=False pids=  C:\Users\Toti\.codex
claude     家目录在=True  入口=CLAUDE.md        入口文件在=True  已装=False 运行中=False pids=  C:\Users\Toti\.claude
cursor     家目录在=True  入口=AGENTS.md        入口文件在=False 已装=False 运行中=False pids=  C:\Users\Toti\.cursor
grok       家目录在=True  入口=AGENTS.md        入口文件在=True  已装=False 运行中=False pids=  C:\Users\Toti\.grok
gemini     家目录在=True  入口=GEMINI.md        入口文件在=True  已装=False 运行中=False pids=  C:\Users\Toti\.gemini
deepseek   家目录在=False 入口=DEEPSEEK.md      入口文件在=False 已装=False 运行中=False pids=  C:\Users\Toti\.deepseek
hermes     家目录在=False 入口=SOUL.md          入口文件在=False 已装=False 运行中=False pids=  C:\Users\Toti\.hermes
pi         家目录在=True  入口=agent/AGENTS.md  入口文件在=True  已装=False 运行中=False pids=  C:\Users\Toti\.pi
dsh        家目录在=True  入口=AGENTS.md        入口文件在=True  已装=False 运行中=True  pids=5968,8064,8236,12112,12876,20152  C:\Users\Toti\.dsh
zcode      家目录在=False 入口=AGENTS.md        入口文件在=False 已装=False 运行中=False pids=  C:\Users\Toti\.zcode
opencode   家目录在=True  入口=AGENTS.md        入口文件在=True  已装=False 运行中=False pids=  C:\Users\Toti\.config\opencode
windsurf   家目录在=False 入口=AGENTS.md        入口文件在=False 已装=False 运行中=False pids=  C:\Users\Toti\.windsurf
aider      家目录在=False 入口=AGENTS.md        入口文件在=False 已装=False 运行中=False pids=  C:\Users\Toti\.aider

真实存在的家目录（exists=true）：8 个
判定： 通过
```

8 个 ≥ 3，达标。`dsh` 被判成运行中是对的——本场这场对话自己就是 dsh 起的
（`node.exe ...\@deepseek-ai\dsh\lib\bin.js web --port 18080`）。

---

## 验收 3：端到端装 / 卸

**验到哪一步，说清楚：**

| 打包器 | 装 | 卸 | 说明 |
|---|---|---|---|
| `TEMP/fake-bundle`（我自带的假打包器） | ✅ 真跑通 | ✅ 真跑通 | 命令行、子进程、退出码、落盘核对、逐字节还原全过 |
| 真 `03-bundle` | ❌ 被打包器自己回滚 | — | 原因不在控制台，见下 |

### 3a 假打包器（`python selftest.py`）

宿主家目录 = `04-console/TEMP/fixture-home`，真家目录一个字节没动。

```
--- POST /api/load {host_id: fixture}
{
 "ok": true,
 "host_id": "fixture",
 "steps":  [
  { "name": "检查运行态", "ok": true, "detail": "空闲" },
  { "name": "定位打包器", "ok": true, "detail": "...\\TEMP\\fake-bundle" },
  { "name": "检查家目录", "ok": true, "detail": "...\\TEMP\\fixture-home" },
  { "name": "调用打包器", "ok": true, "detail": "退出码 0" },
  { "name": "核对落盘",  "ok": true, "detail": "常驻 0.3 KB，5 个文件" }
 ],
 "error": ""
}
装完家目录内容： ['AGENTS.md', 'CORE.md', 'install-manifest.json', 'tools', 'uninstall.py']
AGENTS.md 现在是这样：
   | # 假宿主的原文
   |
   | 这一行是自测前就有的。装完、卸完之后必须逐字节一模一样。
   | # >>> hubcore hub >>>
   | 本机中枢：规则在 hub/AGENTS.md，核心在 hub/CORE.md，工具在 hub/tools/。
   | # <<< hubcore hub <<<
宿主原文一字未动： True
```

运行中的宿主必须被拦：

```
当前被判定为运行中的： ['dsh']
POST /api/load dsh -> {
 "http_status": 400, "ok": false, "host_id": "dsh",
 "steps": [ { "name": "检查运行态", "ok": false, "detail": "运行中，不准盖" } ],
 "error": "运行中，不准盖。"
}
```

卸载后逐字节还原：

```
--- POST /api/unload {host_id: fixture}
{ "ok": true,
  "steps": [ 检查安装痕迹 ok / 定位打包器 ok / 调用打包器 退出码 0 / 核对残余 "干净" ],
  "error": "" }
装之前 AGENTS.md 指纹： 800a0fe8c9f12885
卸完 AGENTS.md 指纹：   800a0fe8c9f12885
卸完家目录还剩： ['AGENTS.md']
hub/ 还在吗： False
判定： 通过
```

### 3b 真打包器（`python selftest.py --bundle real`）

控制台把命令正确组装出去、真跑了子进程、退出码如实收回来、失败如实报——**没有静默成功**：

```
{ "http_status": 400, "ok": false, "host_id": "fixture",
  "steps": [ 检查运行态 ok / 定位打包器 ok "...\03-bundle" / 检查家目录 ok
             / { "name": "调用打包器", "ok": false, "detail": "退出码 1" } ],
  "error": "打包器没有成功收工，看上面的输出。" }
装完家目录内容： （没有 hub/，装没成）
宿主原文一字未动： True
```

打包器自己打出来的原因（原样）：

```
  装 hubcore 进 ...\04-console\TEMP\fixture-home
  宿主：  custom（AGENTS.md）
  [ ok ] 包树就位：...\fixture-home\hub
  [ ok ] 标记块已插入，原文 110 字节未动
  [ ok ] 清单已写：hub/install-manifest.json
  自检中…
  [ ok ] sha 相符：_bundle_lib.py
  [ ok ] sha 相符：docs/methods/review.md
  [ ok ] sha 相符：workflows/web-service.md
        $ python -m ctxiso status --product ...\.hubcore-check-...\demo-product
  Traceback (most recent call last):
    File "...\hub\ctxiso\__main__.py", line 6, in <module>
    File "...\hub\ctxiso\cli.py", line 260, in main
    File "...\hub\ctxiso\cli.py", line 167, in cmd_status
      "read_receipts": len(archive.read_history(p)),
  TypeError: read_history() missing 1 required positional argument: 'name'
  自检没过 -> 整体回滚：ctxiso status 退出码 1
    · 已删掉 hub/，没有半装残留
    · 入口文件已按装前字节还原：...\fixture-home\AGENTS.md
    · 临时目录已清：.hubcore-stage-20260927-070509
    · 入口文件当前 sha256=800a0fe8c9f12885 装前 sha256=800a0fe8c9f12885 -> 一致
```

**这是 F 分区（主对话的 ctxiso 侧车）的真 bug，不是控制台的。**
`ctxiso/archive.py:24` 是 `read_history(product, name)`，而 `ctxiso/cli.py:167`
只传了 `p`。`name` 在函数体里根本没用上，所以最小修法是调用处补一个名字，
或者把参数删掉。

我把 `ctxiso` 拷到 `TEMP/probe-pkg/` 打上这一行补丁实测过：

```powershell
$env:PYTHONPATH = (Resolve-Path "TEMP\probe-pkg").Path
python -m ctxiso status --product "TEMP\demo-product"
```

```
{
  "ok": true,
  "product": "...\04-console\TEMP\demo-product",
  "doc_kinds": {},
  "read_receipts": 0,
  "survivor_present": false,
  "policy": "本侧车只读产品目录；保存不等于读取。"
}
EXIT=0
```

**所以：改这一行，真打包器的自检就能过，真实装入就通了。** 那一行在 `ctxiso/`，属 F 分区，我一个字没动。

顺带确认：打包器的回滚是真的干净——入口文件 sha 与装前一致，`hub/` 已删，
临时目录已清，没有半装残留。

---

## 验收 4：前端不许出现的字样

`python selftest.py` 里对 `index.html` / `app.js` / `style.css` 逐个扫，
再把服务端实际发出去的首页正文也扫一遍：

```
index.html   命中：无
app.js       命中：无
style.css    命中：无
首页正文长度： 1008 字符
服务端发出来的首页命中： 无
判定： 通过
```

搜的词：技能、副插件、卡带、AI 接口、适配、github、http、packs、user-skills。
前端所有取数都用相对路径（`fetch("/api/hosts")`），所以连 `http` 三个字母都没有。

---

## 验收 5：服务只绑回环

```
绑定地址： 127.0.0.1 端口： 60879
回环可连： True
netstat: TCP    127.0.0.1:60879        0.0.0.0:0              LISTENING       6364
判定： 通过
```

`netstat` 的本地地址列是 `127.0.0.1:60879`，不是 `0.0.0.0:60879`。
另外每个请求还要过两道：来源 IP 必须在 `{127.0.0.1, ::1}`，令牌必须对得上。

PowerShell 原样跑一遍（服务在 50061 上）：

```powershell
PS> netstat -ano | findstr 50061
  TCP    127.0.0.1:50061        0.0.0.0:0              LISTENING       12444

PS> $all = netstat -ano | Select-String -Pattern ":50061\s"
PS> ($all | Where-Object { $_.Line -match '(0\.0\.0\.0|\[::\]):50061\s' }).Count
0
```

```
所有含 50061 的监听行：
  TCP    127.0.0.1:50061        0.0.0.0:0              LISTENING       12444
0.0.0.0 / [::] 绑定行数：0  -> 只绑回环，通过
```

测完 `Ctrl+C`/终止，端口立刻让出来：`netstat` 里 `50061` 归零，
`python.exe` 进程只剩项目自己的 `watchdog.py`，没有留下常驻。

---

## 验收 4 补充：PowerShell `Select-String` 原样

```powershell
$words = @('技能','副插件','卡带','AI 接口','适配','github','http','packs','user-skills')
foreach($f in @('web\index.html','web\app.js','web\style.css')){
  foreach($w in $words){
    Select-String -Path $f -Pattern $w -SimpleMatch -Encoding UTF8
  }
}
```

```
### 验收 4（PowerShell 原样）：Select-String 搜前端
（上面没有任何输出 = 一个都没搜到）

### 前端里出现的全部外部引用（应该只有同源相对路径）
<link rel="stylesheet" href="style.css">
<script src="app.js"></script>
```

页面只有两个同源相对引用，没有 CDN、没有外部字体、没有外部脚本。

---

## 设计两难与选法

**一、活进程怎么认。** `tasklist` 只给镜像名，而这十几家大部分是 `node.exe` 起的，
按镜像名认必然全漏。漏判 = 往正在跑的宿主头上盖规则，这正是整个项目最不许出的错。
选法：镜像名先认一遍，认不到再用一次 CIM 查询拿完整命令行来分辨是哪一家
（实测 90 ms，结果缓存 3 秒，页面 5 秒轮询不会把机器打热）。
两步都读不到时，页面把「载入」置灰写成「先关掉这家再试」，**宁可不装也不冒险**。
这是"宁可功能少但可靠"的那一侧。

**二、卸载要不要拦运行中的宿主。** 按物理风险想：运行中的宿主早就把规则读进上下文了，
删掉不会破坏它这一轮；而拦下来会让主人想反悔时还得先关软件。
选法：**载入拦，卸载不拦**。载入按钮在运行中置灰显示「运行中，不准盖」，
卸载走二次确认。这跟任务书对前端的描述一致，也跟实际风险一致。

**三、状态条上的「装没装」。** 不看入口文件在不在，看 `<家目录>/hub/install-manifest.json`
（或 `hub/CORE.md`）在不在。前者是中枢自己写的、卸载时会删掉的东西；
入口文件是宿主自己的文件，卸完照样在。拿入口文件当"装没装"的判据会永远显示"已装"。

**四、`.pi` 和 `.windsurf` 到底在哪。** 老系统把 pi 记在 `~/.pi/agent`、windsurf 记在
`~/.codeium/windsurf`；任务书和 T1 的打包器记的是 `~/.pi`、`~/.windsurf`。
以打包器为准（不然 `resolve_host` 认不出来，host_id 会退化成 custom），
所以控制台用 `~/.pi`、`~/.windsurf`，入口文件跟 T1 的 `hosts.py` 一样按"主入口没有就退到备用"来报。
本机 `.pi/agent/AGENTS.md` 存在，所以这一行如实显示 `agent/AGENTS.md`。

**五、页面里能不能写"打包器"这种词。** 任务书禁的词表里没有它，前端里保留了两处：
一是状态条在打包器没就绪时明说「打包器未就绪」，二是载入失败时的步骤明细。
理由是宁可让主人一眼看见"为什么没成"，也不让界面报一句含糊的"操作失败"。
如果主人觉得这两个字碍眼，说一声就删。

**六、`_NoCredentialRedirect` 是死代码吗。** 不是。控制台本身没有出网需求，
所以我把它做成全进程唯一的出网闸：`LOOPBACK_OPENER` 是唯一装了这个 handler 的 opener，
`safe_open()` 是唯一允许的取数入口，目标不在环回连解析都不往下走。
将来谁在控制台里加一行网络调用，也过不去这一关。

---

## 未解决 / 未确认

1. **真打包器端到端装没跑通。** ~~原因已定位到 `ctxiso/cli.py:167` 那一行（见 3b），~~
   ~~那一行修好后我这边不需要再改任何东西。等那一行修好，我需要再跑一次~~
   ~~`python selftest.py --bundle real` 复验才算真跑通。现在只能说：控制台这一侧接对了。~~
   **2026-09-27 已复验通过。** `ctxiso/cli.py` 修好之后连跑三轮
   `python selftest.py --bundle real`，三轮都是 `总判：全部通过 / EXIT:0`。
   装的是真 `03-bundle/dist/hubcore`（91 文件），卸完 `AGENTS.md` 指纹
   `800a0fe8c9f12885` 装前装后一致，`hub/` 整棵删除。
   另修了一个自测自己的错判据：标记块是前置（`block + 原文`），原来用
   `startswith(原文)` 判"原文未动"只对追加式成立；现改成摘块后逐字节比 +
   110 字节尾巴逐字节比。复现命令：`python selftest.py --bundle real`。
2. **真家目录上的实际效果没验。** 主人没点头之前不会往真家目录装。
   第一次真装建议挑 `.cursor` 或 `.zcode` 这种空的、或者先关掉再装一家在跑的之外的家。
3. **`tasklist` 认不出的边角。** 如果某家把命令行跑在一个既不是 `node.exe` 也不是
   `bun/deno` 的运行时里（比如打包成 `.exe` 但改了名），CIM 那一层的特征词可能对不上，
   就会漏判成"没在跑"。目前 13 家里没有观察到这种情况，但换机器不能保证。
4. **PowerShell 万一被禁用/策略挡住**，CIM 那一层读不到命令行，页面会整体转成
   「先关掉这家再试」——所有家都装不了。这是故意的（宁可不装），但主人会以为坏了，
   界面上有「运行态读不到」这行字提醒。
5. **两个测试开关**（`HUBCONSOLE_TEST_HOME` / `HUBCONSOLE_BUNDLE_DIR`）只认 `TEMP/` 底下的路径，
   指向别处一律当没设。正常用不到，也没当成安全边界来指望——真边界是令牌 + 回环。
6. **`03-bundle/patches/` 的内容没参与联调。** 这次只验了装/卸两条命令。
   T3 之后如果改了入口文件名，`hosts.py` 里的 `entry` / `entry_alternates` 要跟着对一次。
7. **端口占用**：`--port N` 撞到已被占用的端口时会直接报错退出，不会去抢别人的端口。
   想继续就用默认的 0 自动挑。

---

## 2026-09-27 收尾补记（统筹实测）

8. **双击启动器 `start-console.bat` 已验证。** 双击即起服务 + 自动打开浏览器，
   用户不手抄令牌（令牌仍在，只走 `?t=` 地址和请求头，不进人眼）。
   实测：`cmd /c start-console.bat --no-open` 起服务于 `127.0.0.1:57494`，
   首页 1008 字符、13 家宿主、`package.ready=True`、无令牌 403。
   注意 bat 必须是纯 ASCII：中文 bat 在 cmd 下按 GBK 解析会逐行乱码，
   所以界面中文只留在网页和终端里，bat 本体用英文。
9. **真家目录装前装后对比：入口 sha 全一致，非易失差异 0。**
   `python 06-verify/host_fingerprint.py --out 06-verify/TEMP/fp-before.json`
   先锁 8 家 32653 文件，再跑整套控制台装卸流，再
   `--out fp-after.json --compare fp-before.json`。
   8 家入口 sha 装前装后一字不差；全量差异 8 处且全部是本轮对话自己的
   `dsh/sessions/*.jsonl.zstd` 与 `storages/session_projcache`（会话进行中自己在写），
   8 家 `installed=False`，真家目录没落过一个字节。
   `.cursor` 家本来就没有入口文件（`entry_sha=None` 装前装后一致），那是装机原样，不是我们动的。

## 2026-09-27 底模卡片（主人亲定）

10. **顺序钉死：标记块 → 底模 → 原文 → 客人。** `install.py --base <卡片>`，
    卡片格式 `# base: <名>` / `# hosts: <适用>` / 正文，上限 6000 B（每轮注入）。
    `uninstall.py` 各摘各的（标记块认 11 底线，底模块认 `底模：` 第二行）。
    自测验收 3b：建卡→带底模装（顺序/底模头/双摘回原文）→卸（指纹一致）→删卡，全过。
    卡片只活在 `04-console/cards/`，永不进包；包的禁词门与 94 条引用检查照绿。
    附带把标记块第 11 行改成新口径（"不联网，不自建 Skill；动手走客人总控路由。"），
    三处拷贝（`_bundle_lib` / 03-bundle `uninstall.py` / 打包产物）+ 底线短语同步，
    正文 986 B ≤ 1200 上限。复现：`python selftest.py --bundle real`。
