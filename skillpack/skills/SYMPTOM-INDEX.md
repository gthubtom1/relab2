# 症状索引（Symptom Index）——用户描述现象，直接定位技能

> 这是什么：一份"现象 → 技能"的路由表。每一行不是技能名换皮，
> 而是**用户会怎么描述这个需求**的现象句，配上该去哪个技能。
> 写法照 `upstream/apk-reverse` 的 54 行 Symptom index（`What you observe → Load first`）。
>
> 什么时候读：`master-route` 报 `confidence: low` / PRIMARY=R0 /
> "No strong keyword hit"，或社区侧 `no_match` 需要换词重查之前——
> **先在这张表里对现象，对上哪行就进哪个技能**。路由命中后不需要读它；
> 它不改任何路由逻辑，只是补关键词永远差一个字的"近失"（`逃出去` vs `逃逸`、
> `集群` vs `k8s`、`效果掉了` vs `评估效果`这类）。
>
> 链接只指向各技能已存在的 `SKILL.md`；进去之后一切以该 `SKILL.md` 为准。
>
> **进了技能之后还有第二跳**：这张表只回答「进哪个技能」，不回答「读该技能的哪一篇技术文档」。
> 已经知道在 `reverse-engineering/`（或 `api-security/`、`ctf-sandbox/` …）里了，
> 接下来按症状找具体文档 → **[`field-journal/KB-INDEX.md`](field-journal/KB-INDEX.md)**（153 篇技术文档的症状索引）。

## 症状 → 技能

| 用户这样说 | 去这里 | 备注 |
|---|---|---|
| "这程序加了花指令，函数跳来跳去看不清主干，想先把它捋直再看逻辑" | [R0 reverse-engineering](reverse-engineering/SKILL.md) | 去混淆/控制流整理 |
| "一上调试器它就退出，普通手段跟不进去，想知道它在哪埋的检测" | [R0 reverse-engineering](reverse-engineering/SKILL.md) | 反调试定位 |
| "这东西看着像被套了壳，又不确定是哪种，得先验明正身再决定怎么脱" | [R0 reverse-engineering](reverse-engineering/SKILL.md) | 加壳判定/脱壳前分类 |
| "页面里那堆判定全塞在一个大转发里，指令集还是它自家定的，看到头晕" | [R0 reverse-engineering](reverse-engineering/SKILL.md) | 自定指令集/小解释器 |
| "朋友丢来一段怪脚本，执行时像里头住了个翻译，算的啥全看不穿" | [R0 reverse-engineering](reverse-engineering/SKILL.md) | 脚本内解释器行为 |
| "孩子手机里这个应用，一连网流量就猛涨，想知道它半夜都在跟谁说话" | [R1 apk-reverse](apk-reverse/SKILL.md) | 应用网络行为 |
| "装好的软件一打开就闪退回桌面，怀疑它嫌这台机子不干净" | [R1 apk-reverse](apk-reverse/SKILL.md) | 环境检测/闪退 |
| "想把这个应用里的开屏广告和弹窗去掉，自己打包一个干净的装上" | [R1 apk-reverse](apk-reverse/SKILL.md) | 改包/重打包/重签 |
| "朋友的手机装它好好的，我的一打开就悄没声，不知道它暗地里查了啥" | [R1 apk-reverse](apk-reverse/SKILL.md) | 机型/环境判断差异 |
| "家里那台苹果机，应用的数据包死活截不着，想让它经我的中间人过一遍好开箱验货" | [R2 mobile-reverse](mobile-reverse/SKILL.md) | iOS 抓包/走代理 |
| "老人那台苹果装了个测试版，点开就闪没，八成跟这机器越没越狱这类底细有关" | [R2 mobile-reverse](mobile-reverse/SKILL.md) | iOS 安装/机器状态 |
| "这苹果应用疑似把证书钉死了，代理挂上也只剩一堆握手失败" | [R2 mobile-reverse](mobile-reverse/SKILL.md) | SSL 钉死 |
| "安卓和苹果两个版本行为对不上，想对照看看苹果版到底多干了什么" | [R2 mobile-reverse](mobile-reverse/SKILL.md) | 双端行为对照 |
| "网页上按完登录，发出去的全是天书乱码，得顺进页面里看它是现拼的还是藏好的" | [R3 js-reverse](js-reverse/SKILL.md) | 签名链路定位 |
| "填表时有个一刷就变的校验串，明显页面现场算的，得在本地把它复刻出来" | [R3 js-reverse](js-reverse/SKILL.md) | 补环境复现 |
| "密码输完一提交，出去的数据跟填的判若两人，页面里埋了几道手脚得拆" | [R3 js-reverse](js-reverse/SKILL.md) | 页面观察取证 |
| "网页里那个令牌不知哪来的，一刷新就换，想在浏览器里当场抓住它算出来的瞬间" | [R3 js-reverse](js-reverse/SKILL.md) | 运行时采样 |
| "甲方丢来个 Windows 下跑的玩意，像是微软那套框架编的，符号搅得面目全非" | [R5 dotnet-reverse](dotnet-reverse/SKILL.md) | .NET 反编译/去混淆 |
| "后台登录那块埋在托管代码堆里，名儿全被搅过，得想法子抠开看" | [R5 dotnet-reverse](dotnet-reverse/SKILL.md) | 托管代码/搅过的名 |
| "C# 写的小工具想改掉里面一个判断，不重编直接改完就能跑" | [R5 dotnet-reverse](dotnet-reverse/SKILL.md) | IL 改判断 |
| "有个双击即跑的工具，翻出来的串全是驴唇不对马嘴，逻辑根本连不成片" | [R5 dotnet-reverse](dotnet-reverse/SKILL.md) | 字符串错乱/逻辑还原 |
| "手里有个 PC 程序的本体，进主界面前它先验了些啥，得捋出来" | [R6 ida-reverse](ida-reverse/SKILL.md) | 启动检查/静态跟 |
| "同一份程序挪台机子就报许可失效，它到底抄了本机哪些底细得查明白" | [R6 ida-reverse](ida-reverse/SKILL.md) | 许可/机器码校验 |
| "so 里有个函数进出全是加密过的字节，想静态跟一下它到底怎么算的" | [R6 ida-reverse](ida-reverse/SKILL.md) | .so 静态分析 |
| "程序里弹的那个报错是从哪蹦出来的，想顺着字符串找到背后的判断" | [R6 ida-reverse](ida-reverse/SKILL.md) | 字符串找判定 |
| "出门只带了台纯命令行的机器，样本还非看不可，只能在黑框框里把它拆开" | [R7 radare2](radare2/SKILL.md) | 纯终端分析 |
| "想写个脚本把一批样本的字符串和导入表全扒出来，图形工具一个个点太慢" | [R7 radare2](radare2/SKILL.md) | 批处理扒字符串/导入表 |
| "服务器上不让装大家伙，只能用轻量命令行的东西先看看这个二进制" | [R7 radare2](radare2/SKILL.md) | 轻量无 GUI 环境 |
| "逆向时想在终端里顺手查个函数的调用关系，不想开图形界面" | [R7 radare2](radare2/SKILL.md) | 终端查调用关系 |
| "摄像头那升级包，疑似留了个能钻进去的洞，得验验是不是娘胎里带的" | [R8 firmware-pentest](firmware-pentest/SKILL.md) | 固件后门/出厂残留 |
| "路由器官方包下下来了，拆了半天文件系统出不来，卡在第一步" | [R8 firmware-pentest](firmware-pentest/SKILL.md) | 解包卡住 |
| "想把这个固件在模拟器里跑起来，看看它的管理页面到底有哪些接口" | [R8 firmware-pentest](firmware-pentest/SKILL.md) | 仿真跑管理面 |
| "这固件拆开后冒出好几个带网口的程序，得挑一个重点挖" | [R8 firmware-pentest](firmware-pentest/SKILL.md) | 网络面挖洞 |
| "邮箱躺着封带附件的信，手贱点开后机器就开始对外喊话，这玩意干了啥得查" | [R9 malware-analysis](malware-analysis/SKILL.md) | 可疑附件行为 |
| "杀软报了个东西但说不清是啥，想自己动手验验它到底干了哪些坏事" | [R9 malware-analysis](malware-analysis/SKILL.md) | 静态+动态验样本 |
| "这台机器半夜自己往外传东西，抓到个可疑进程，想提炼点能封堵的特征" | [R9 malware-analysis](malware-analysis/SKILL.md) | IOC/封堵特征 |
| "同事传的破解补丁越看越像捆了东西，运行前想先查查它干净不干净" | [R9 malware-analysis](malware-analysis/SKILL.md) | 第三方构建审计 |
| "外网有台能落脚的肉鸡了，下一步顺着它去够里头藏宝的那几台" | [R10 attack-chain](attack-chain/SKILL.md) | 横向/路径规划 |
| "老板让做一次从外网到拿下核心系统的完整演练，得先有个整体打法" | [R10 attack-chain](attack-chain/SKILL.md) | 完整渗透演练 |
| "手里有个能执行的入口，接下来是提权还是先看内网，得有人给排个顺序" | [R10 attack-chain](attack-chain/SKILL.md) | 入口下一步编排 |
| "这个口子能利用到什么程度，是只能看数据还是能直接进内网，得评估清楚" | [R10 attack-chain](attack-chain/SKILL.md) | 利用程度评估 |
| "上线前想把这批端口和常见漏洞先扫一遍，用工具跑个基线再说" | [R11 pentest-tools](pentest-tools/SKILL.md) | 端口/漏洞基线 |
| "登录框想试试万能口令和注入点，得有个趁手的家伙批量测" | [R11 pentest-tools](pentest-tools/SKILL.md) | 注入批量测 |
| "网站后台目录想扫一遍看看有没有漏出来的备份和测试页" | [R11 pentest-tools](pentest-tools/SKILL.md) | 目录爆破 |
| "授权书上就一个公司名，网段都没给，先从公开渠道把能摸的入口列齐" | [R11 pentest-tools](pentest-tools/SKILL.md) | 授权信息收集 |
| "切小号登进去，把请求里的序号挨个换，发现能捞到别人的单子" | [R12 api-security](api-security/SKILL.md) | 越权/编号遍历 |
| "这个接口的登录凭证好像随便伪造，改个字段就进了别人的会话" | [R12 api-security](api-security/SKILL.md) | 凭证伪造/鉴权 |
| "小程序抓出来的接口没做鉴权，不登录直接调也能拿数据" | [R12 api-security](api-security/SKILL.md) | 未授权直调 |
| "它家那种能随便问结构的查询口开着，不用猜就能把表关系摸出来" | [R12 api-security](api-security/SKILL.md) | 可内省的查询口 |
| "代码仓里拖了一堆开源件，哪个版本被人下过手心里没数，得挨个盘" | [R13 supply-chain-security](supply-chain-security/SKILL.md) | 依赖盘点 |
| "流水线里不知哪个环节被塞了东西，想查构建过程干不干净" | [R13 supply-chain-security](supply-chain-security/SKILL.md) | 构建完整性 |
| "镜像越堆越大，里面藏了几个高危洞，得扫出来看看" | [R13 supply-chain-security](supply-chain-security/SKILL.md) | 镜像扫洞 |
| "提交的代码里疑似有人把密钥直接写进去了，得翻出来清掉" | [R13 supply-chain-security](supply-chain-security/SKILL.md) | 密钥泄漏翻查 |
| "接进来的问答客服，三绕两绕就被人套出不该说的话" | [R14 llm-security](llm-security/SKILL.md) | 诱导套话 |
| "灌给模型的资料疑似被掺了沙子，答起话来总往沟里带" | [R14 llm-security](llm-security/SKILL.md) | 资料投毒 |
| "智能助手能调好几个工具，怕一句话就被骗去删库调接口" | [R14 llm-security](llm-security/SKILL.md) | 工具滥用 |
| "打算上线一个 AI 功能，上线前想让人从攻击者角度先捅一遍" | [R14 llm-security](llm-security/SKILL.md) | 上线前评估 |
| "一老一新两份摆一块，符号全换了脸，当初认出来的得想法子再对上" | [R15 binary-diff](binary-diff/SKILL.md) | 符号再对上 |
| "程序更新后当初记的函数地址全变了，得重新定位" | [R15 binary-diff](binary-diff/SKILL.md) | 更新后找偏移 |
| "新版的符号文件下不到了，只能抱着旧版的硬往上对" | [R15 binary-diff](binary-diff/SKILL.md) | 缺符号推导 |
| "补丁前后两份放一起，想看看厂商到底改了哪几处" | [R15 binary-diff](binary-diff/SKILL.md) | 两版比对 |
| "厂商刚发的安全补丁就一个包，它堵的到底是哪个窟窿得反推" | [R16 patch-diff-exploit](patch-diff-exploit/SKILL.md) | 补丁反推窟窿 |
| "圈子里传某编号洞已被人拿来打了，打法还没公开，只能抱着补丁倒着啃" | [R16 patch-diff-exploit](patch-diff-exploit/SKILL.md) | 无公开打法反推 |
| "补丁日又来了一堆，得挑跟自家资产有关的先跟" | [R16 patch-diff-exploit](patch-diff-exploit/SKILL.md) | 补丁日跟进 |
| "只知道编号没有现成利用，想从补丁里搓一个能用的出来" | [R16 patch-diff-exploit](patch-diff-exploit/SKILL.md) | 搓可用利用 |
| "往那服务怼超长输入就崩，想整条稳的、能带回结果的利用链" | [R17 pwn-chain](pwn-chain/SKILL.md) | 崩溃到稳定利用 |
| "靶机那吃输入的口子，本地耍得通，一上远端就掉链，卡的就是临门一口气" | [R17 pwn-chain](pwn-chain/SKILL.md) | 本地通远端断 |
| "堆上那个越界写看着能改东西，但怎么改成拿控制权还没想明白" | [R17 pwn-chain](pwn-chain/SKILL.md) | 堆越界写 |
| "内核模块有个可疑的读写口，想看看普通用户能不能打到提权" | [R17 pwn-chain](pwn-chain/SKILL.md) | 内核读写口 |
| "演练时带的小工具一落地就被系统自带的卫士吞了，得让它活下来" | [R18 edr-bypass-re](edr-bypass-re/SKILL.md) | 授权演练投递存活 |
| "挂钩老是被杀软拔掉，听说得把系统调用那条路换了才稳" | [R18 edr-bypass-re](edr-bypass-re/SKILL.md) | 钩子存活/调用路 |
| "脚本的每一步都被记得清清楚楚，想让那套记录睁一只眼闭一只眼" | [R18 edr-bypass-re](edr-bypass-re/SKILL.md) | 记录绕过 |
| "这游戏的开挂检测专拦调试器，想研究它的检测点都埋在哪" | [R18 edr-bypass-re](edr-bypass-re/SKILL.md) | 反作弊检测点 |
| "这个报名表单几十页，手工填太费人，想让机器自动点完" | [R19 browser-automation](browser-automation/SKILL.md) | 自动填表 |
| "每天都要登录后台导一份数据，想定时自动跑完截图留底" | [R19 browser-automation](browser-automation/SKILL.md) | 定时登录导数 |
| "页面内容得登录后翻好几页才看全，想一次性爬下来" | [R19 browser-automation](browser-automation/SKILL.md) | 登录后爬取 |
| "桌面上那个老客户端没接口，只能模拟鼠标键盘去点它" | [R19 browser-automation](browser-automation/SKILL.md) | 桌面模拟点击 |
| "渗透活干完了，得交一份像样的报告，截图和结论得排好" | [R20 docs-generator](docs-generator/SKILL.md) | 渗透报告 |
| "比赛打完教练要复盘文档，得把解题过程写成能看的记录" | [R20 docs-generator](docs-generator/SKILL.md) | 复盘记录 |
| "仓库里那个说明还是空的，接口文档也得补上" | [R20 docs-generator](docs-generator/SKILL.md) | 说明/接口文档 |
| "逆向分析做完了，领导要一份能直接递上去的结论材料" | [R20 docs-generator](docs-generator/SKILL.md) | 逆向结论落盘 |
| "这个软件装完就自动连了几个奇怪的地址，想知道它到底在传什么" | [R21 protocol-reverse](protocol-reverse/SKILL.md) | 奇怪外连解包 |
| "抓到的包全是看不懂的二进制，疑似自己定的格式，得拆开看看" | [R21 protocol-reverse](protocol-reverse/SKILL.md) | 私有格式拆解 |
| "它用的那种没说明书的数据格式，抓包只能看到一堆数字和串" | [R21 protocol-reverse](protocol-reverse/SKILL.md) | 无说明书格式解码 |
| "客户端和服务器聊的通道全是加密帧，想复原出通信内容" | [R21 protocol-reverse](protocol-reverse/SKILL.md) | 加密帧复原 |
| "没买那套收费的反编译工具，想用免费的把这个二进制翻开看看" | [R22 ghidra-reverse](ghidra-reverse/SKILL.md) | 免费反编译；与 R45 二选一：没有商业授权、要用免费的或批量 headless 跑 → 本行；已装 Vector35、要 HLIL/MLIL 数据流与类型重理 → R45 |
| "手头一堆样本要批量翻出伪代码，图形界面一个个点不现实" | [R22 ghidra-reverse](ghidra-reverse/SKILL.md) | 批量翻伪代码；与 R45 二选一：没有商业授权、要用免费的或批量 headless 跑 → 本行；已装 Vector35、要 HLIL/MLIL 数据流与类型重理 → R45 |
| "字符串在哪被引用了，想顺藤摸瓜找到用它的函数" | [R22 ghidra-reverse](ghidra-reverse/SKILL.md) | 引用找函数；与 R45 二选一：没有商业授权、要用免费的或批量 headless 跑 → 本行；已装 Vector35、要 HLIL/MLIL 数据流与类型重理 → R45 |
| "上一套工具的结果看着别扭，想换个免费的交叉验证下这个函数" | [R22 ghidra-reverse](ghidra-reverse/SKILL.md) | 交叉验证；与 R45 二选一：没有商业授权、要用免费的或批量 headless 跑 → 本行；已装 Vector35、要 HLIL/MLIL 数据流与类型重理 → R45 |
| "同事说容器里能直接跑到宿主机上，想验证下是不是真有这条路" | [R23 cloud-k8s](cloud-k8s/SKILL.md) | 容器跑到宿主机验证 |
| "我们那一堆机器的管控面，权限配得乱七八糟，怕有人一步登天" | [R23 cloud-k8s](cloud-k8s/SKILL.md) | 集群管控面权限 |
| "对象存储的桶好像谁都能读，得确认下是不是真公开了" | [R23 cloud-k8s](cloud-k8s/SKILL.md) | 存储桶公开确认 |
| "有个接口能打到云的元数据，怕被人拿去换凭证" | [R23 cloud-k8s](cloud-k8s/SKILL.md) | 元数据换凭证 |
| "进了内网一台机，想看看能不能顺着信任关系摸到管全场的机器" | [R24 windows-ad](windows-ad/SKILL.md) | 信任关系摸域控 |
| "有个服务账号的票据好像能伪造，得验一下这条路通不通" | [R24 windows-ad](windows-ad/SKILL.md) | 票据伪造验证 |
| "证书服务配得好像有问题，听说能直接领一张好使的身份" | [R24 windows-ad](windows-ad/SKILL.md) | 证书服务错配 |
| "抓到一串哈希，想看看能不能在别处直接拿来用" | [R24 windows-ad](windows-ad/SKILL.md) | 哈希传递他用 |
| "电脑中招了，导了个内存镜像，想看看坏东西藏在哪" | [R25 digital-forensics](digital-forensics/SKILL.md) | 内存镜像找坏东西 |
| "这台机器半夜被碰过，想按时间线捋出它都干了什么" | [R25 digital-forensics](digital-forensics/SKILL.md) | 时间线捋操作 |
| "网管导了一份抓包，里面好像有异常外连，得翻出来" | [R25 digital-forensics](digital-forensics/SKILL.md) | 抓包翻异常外连 |
| "员工离职前删了一堆东西，得看看还能不能找回点痕迹" | [R25 digital-forensics](digital-forensics/SKILL.md) | 删除痕迹找回 |
| "上线前这仓库的代码，得请人通读挑刺，专找注入和越权" | [R26 code-audit](code-audit/SKILL.md) | 上线前过代码 |
| "登录那块的鉴权看着像漏了分支，空条件可能直接放行" | [R26 code-audit](code-audit/SKILL.md) | 鉴权分支遗漏 |
| "想拿扫描器把仓库先扫一遍，高危的先修" | [R26 code-audit](code-audit/SKILL.md) | 仓库先扫一遍 |
| "修完的洞得有人复验，确认补丁真堵住了" | [R26 code-audit](code-audit/SKILL.md) | 补丁复验 |
| "上了新规则后拦截量反而往下掉，想看看检测效果是不是真变好了" | [R27 threat-hunting](threat-hunting/SKILL.md) | 拦截掉量/效果评估 |
| "情报里给了批指标，想在自家日志里扫一遍看有没有中招" | [R27 threat-hunting](threat-hunting/SKILL.md) | 指标扫日志 |
| "这条检出天天误报，想改成能用的规则再上线" | [R27 threat-hunting](threat-hunting/SKILL.md) | 误报改规则 |
| "蓝队想先演一遍，看看现在的监控能不能抓住模拟攻击" | [R27 threat-hunting](threat-hunting/SKILL.md) | 监控抓模拟攻击 |
| "厂里的老控制器还在裸奔，想先分区分级再看暴露面" | [R28 ot-ics](ot-ics/SKILL.md) | 分区分级看暴露 |
| "工控协议长啥样心里没数，得先被动听听再说话" | [R28 ot-ics](ot-ics/SKILL.md) | 被动听协议 |
| "有台控制器的管理口好像直接挂在网上，得确认下" | [R28 ot-ics](ot-ics/SKILL.md) | 管理口暴露确认 |
| "生产网不敢主动扫，只能先镜像流量慢慢看" | [R28 ot-ics](ot-ics/SKILL.md) | 不敢扫只看流量 |
| "会议室的无线总感觉有人蹭，想抓包看看连入情况" | [R29 wifi-wireless](wifi-wireless/SKILL.md) | 蹭网抓包 |
| "楼下冒出个同名热点，怕是有人钓鱼，得定位下" | [R29 wifi-wireless](wifi-wireless/SKILL.md) | 同名热点钓鱼 |
| "自家无线的口令强度心里没底，想在实验环境里验一下" | [R29 wifi-wireless](wifi-wireless/SKILL.md) | 口令实验验证 |
| "仓库那片无线覆盖到了围墙外，想看看边界漏到哪了" | [R29 wifi-wireless](wifi-wireless/SKILL.md) | 覆盖边界外漏 |
| "装的这个插件老在后台偷跑流量，怀疑它在偷数据" | [R30 browser-extension-reverse](browser-extension-reverse/SKILL.md) | 插件偷跑流量 |
| "扩展要的权限多得离谱，通讯录都想读，得看看它到底用没用" | [R30 browser-extension-reverse](browser-extension-reverse/SKILL.md) | 权限多得离谱 |
| "浏览器首页老被改，卸了又回来，像是扩展在搞鬼" | [R30 browser-extension-reverse](browser-extension-reverse/SKILL.md) | 首页被改 |
| "同事发了个外部插件，装之前想先验验它干净不干净" | [R30 browser-extension-reverse](browser-extension-reverse/SKILL.md) | 装前验插件 |
| "苹果电脑上这个程序打不开，提示签名有问题，想看看它动过哪" | [R31 macos-reverse](macos-reverse/SKILL.md) | 签名问题查改动 |
| "苹果机上的木马样本，想捋它的持久化和外连" | [R31 macos-reverse](macos-reverse/SKILL.md) | 苹果木马行为 |
| "这个苹果应用的界面逻辑藏在它家那套框架里，普通工具看不清" | [R31 macos-reverse](macos-reverse/SKILL.md) | 框架内逻辑还原 |
| "系统弹窗老要权限，想查是哪家进程在要" | [R31 macos-reverse](macos-reverse/SKILL.md) | 权限弹窗溯源 |
| "公司配的桌面客户端，本地存的东西好像没加密，想翻翻" | [R32 thick-client](thick-client/SKILL.md) | 本地存物翻查 |
| "客户端每次启动都去拉更新，怕更新通道能被动手脚" | [R32 thick-client](thick-client/SKILL.md) | 更新通道安全 |
| "两个本地进程聊来聊去，想看看它们传的东西有没有校验" | [R32 thick-client](thick-client/SKILL.md) | 本地进程通信 |
| "这个桌面客户端套了层网页壳，页面和本地能力的边界在哪得摸清楚" | [R32 thick-client](thick-client/SKILL.md) | 网页壳边界 |
| "这个 Go 写的马，函数名全没了，调用关系一团麻" | [R33 go-rust-reverse](go-rust-reverse/SKILL.md) | Go 符号全没 |
| "Rust 程序崩出来的那堆报错信息，想拿它当路标定位" | [R33 go-rust-reverse](go-rust-reverse/SKILL.md) | 崩溃信息当路标 |
| "Go 程序的接口地址藏在运行时表里，静态看全是间接跳" | [R33 go-rust-reverse](go-rust-reverse/SKILL.md) | 运行时表找接口 |
| "拿到的样本疑似新语言编的，普通流程图根本对不上" | [R33 go-rust-reverse](go-rust-reverse/SKILL.md) | 新语言二进制 |
| "板子上的排针看着像调试口，想认认哪个是串口" | [R34 hardware-security](hardware-security/SKILL.md) | 排针认串口 |
| "芯片里的东西想完整倒出来，得先找到下手的地方" | [R34 hardware-security](hardware-security/SKILL.md) | 芯片倒数据 |
| "设备拆开有个没焊的接口，量量看是不是留的调试通道" | [R34 hardware-security](hardware-security/SKILL.md) | 空焊接口量调试口 |
| "固件从官网下不到，只能从硬件上想办法抠出来" | [R34 hardware-security](hardware-security/SKILL.md) | 硬件抠固件 |
| "数据库好像被人拖过库，想查查是从哪漏的" | [R35 database-security](database-security/SKILL.md) | 拖库溯源 |
| "这个缓存服务配得像谁都能连，还能写文件，得看看危害" | [R35 database-security](database-security/SKILL.md) | 缓存裸奔/写文件 |
| "业务账号的权限大得离谱，删库都够格，得收一收" | [R35 database-security](database-security/SKILL.md) | 账号权限过大 |
| "数据库口令弱得像纸糊的，扫一遍看看有多少重灾区" | [R35 database-security](database-security/SKILL.md) | 弱口令扫一遍 |
| "刚收到封催打款的邮件，落款像老板，越看越不对" | [R36 email-security](email-security/SKILL.md) | 冒充老板催款 |
| "自家域名的邮件配置不知道齐没齐，怕被人冒充发信" | [R36 email-security](email-security/SKILL.md) | 发信配置查冒充 |
| "附件里的链接点进去是个登录框，长得跟真的一样" | [R36 email-security](email-security/SKILL.md) | 假登录框链接 |
| "最近好几封诈骗信盯着财务，得总结下长啥样好培训" | [R36 email-security](email-security/SKILL.md) | 诈骗信特征总结 |
| "单点登录跳来跳去，有个应用好像能拿 A 站的票去 B 站用" | [R37 identity-federation](identity-federation/SKILL.md) | 票据跨站用 |
| "对接的登录协议配错了参数，怕有能绕过身份的地方" | [R37 identity-federation](identity-federation/SKILL.md) | 协议错配绕身份 |
| "第三方登录回调地址写得太宽，怕凭证被人半路截走" | [R37 identity-federation](identity-federation/SKILL.md) | 回调太宽截凭证 |
| "免密登录的断言包好像没验签，得查查" | [R37 identity-federation](identity-federation/SKILL.md) | 断言验签 |
| "停车场里收到段看不懂的无线信号，不是 Wi-Fi，想认认是啥" | [R38 radio-sdr](radio-sdr/SKILL.md) | 非 Wi-Fi 信号辨认 |
| "车钥匙的信号想在屏蔽房里录下来看看长啥样" | [R38 radio-sdr](radio-sdr/SKILL.md) | 屏蔽房录信号 |
| "那段免费频段老有东西在叫，想解出它到底在发什么" | [R38 radio-sdr](radio-sdr/SKILL.md) | 免费频段解内容 |
| "无人机遥控链路用的啥协议，心里没底想扫一眼" | [R38 radio-sdr](radio-sdr/SKILL.md) | 遥控链路协议 |
| "这套流程太绕了，画张图给大伙讲讲" | [R39 diagram-generator](diagram-generator/SKILL.md) | 流程画图讲清 |
| "表结构口说说不清，来张关系图一目了然" | [R39 diagram-generator](diagram-generator/SKILL.md) | 表结构成图 |
| "攻击路径串了好几步，画个先后图把顺序讲明白" | [R39 diagram-generator](diagram-generator/SKILL.md) | 路径顺序图 |
| "新架构评审前，先来张架构图摆桌上" | [R39 diagram-generator](diagram-generator/SKILL.md) | 评审架构图 |
| "报告交出去前，想请人把证据到结论的链条审一遍" | [R40 case-review](case-review/SKILL.md) | 证据链审一遍 |
| "这个案子包里的东西散得七零八落，交之前得收拢验一遍" | [R40 case-review](case-review/SKILL.md) | 交前收拢验 |
| "哈希对不上，怕交上去被人挑刺，先自查" | [R40 case-review](case-review/SKILL.md) | 哈希自查 |
| "动手范围和当初定的对没对上，交前得有人拍板" | [R40 case-review](case-review/SKILL.md) | 范围拍板 |
| "来道题练练手，环境帮我先跑起来" | [R41 ctf-sandbox](ctf-sandbox/SKILL.md) | 练手题起环境 |
| "比赛平台上那道内存题，本地复现环境还没搭" | [R41 ctf-sandbox](ctf-sandbox/SKILL.md) | 复现环境搭建 |
| "周末有个攻防赛，想先把两端的架子支起来" | [R41 ctf-sandbox](ctf-sandbox/SKILL.md) | 攻防赛备场 |
| "小孩想入门打比赛，先从哪类题起手，得有个带路的" | [R41 ctf-sandbox](ctf-sandbox/SKILL.md) | 新手带路分诊 |
| "社媒上有人在传这次攻击的事，先别信，得交叉验验" | [R44 threat-intelligence](threat-intelligence/SKILL.md) | 传闻交叉验 |
| "手里一串坏名声的地址，想知道它背后是哪拨人" | [R44 threat-intelligence](threat-intelligence/SKILL.md) | 指标背后归因 |
| "有人冒充我们家客服行骗，想摸摸这拨骗子的盘子" | [R44 threat-intelligence](threat-intelligence/SKILL.md) | 冒充客服团伙 |
| "新出的团伙报告，得翻成自家能用的防御动作" | [R44 threat-intelligence](threat-intelligence/SKILL.md) | 报告转防御 |
| "听说有个看数据流清楚的第三方工具，想用它过一遍这个函数" | [R45 binary-ninja-reverse](binary-ninja-reverse/SKILL.md) | 第三方看数据流；与 R22 二选一：点名用 BN、要中间语言数据流、类型重理或对上一套工具做交叉验证 → 本行；只是没 IDA 要免费的、或要批量 headless → R22 |
| "这个调用链太长，想跟出来看看头尾" | [R45 binary-ninja-reverse](binary-ninja-reverse/SKILL.md) | 调用链跟头尾；与 R22 二选一：点名用 BN、要中间语言数据流、类型重理或对上一套工具做交叉验证 → 本行；只是没 IDA 要免费的、或要批量 headless → R22 |
| "上一套工具的结果对不上，来个第二意见" | [R45 binary-ninja-reverse](binary-ninja-reverse/SKILL.md) | 第二意见；与 R22 二选一：点名用 BN、要中间语言数据流、类型重理或对上一套工具做交叉验证 → 本行；只是没 IDA 要免费的、或要批量 headless → R22 |
| "类型猜得乱七八糟，想换个工具重新理一遍" | [R45 binary-ninja-reverse](binary-ninja-reverse/SKILL.md) | 类型重理；与 R22 二选一：点名用 BN、要中间语言数据流、类型重理或对上一套工具做交叉验证 → 本行；只是没 IDA 要免费的、或要批量 headless → R22 |

_173 row(s) below the header. Every row's target exists as `skills/<dir>/SKILL.md`（本包未落地）._

## Web 端 JS 协议逆向（web-protocol-reverse）

| 症状 | 先看 |
|------|------|
| 页面能出数据，但 Python 请求就 403/签名错 | `web-protocol-reverse/references/state/cookie-provenance-playbook.md`（cookie 溯源）|
| 签名字段看不懂，怀疑 JS 虚拟机 | `web-protocol-reverse/references/crypto/jsvmp-analysis-playbook.md` |
| Node 里跑通了但没法交付（依赖浏览器） | `web-protocol-reverse/references/deliver/pure-python-rebuild-playbook.md` |
| 抓到的 cookie 刷新就没了 | `web-protocol-reverse/references/state/session-contract-playbook.md` |
| 要补浏览器环境（navigator/document/window） | `web-protocol-reverse/references/crypto/environment-patch-playbook.md` |
| 分页在后面几页换了接口 | `web-protocol-reverse/references/observe/pagination-route-pivot-playbook.md` |
| 挑战/风控请求看不懂 | `web-protocol-reverse/references/state/challenge-artifact-harvest-playbook.md` |
| 不知道该用哪个工具 | `web-protocol-reverse/references/triage/tool-playbook.md` |
