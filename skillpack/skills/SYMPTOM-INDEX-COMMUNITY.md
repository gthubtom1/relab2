# 症状索引·社区包（Symptom Index Community）——用户描述现象，直接定位社区技能

> 这是什么：一份"现象 → 社区技能"的路由表，是 skills/SYMPTOM-INDEX.md（canonical 43 技能）
> 的社区扩展。每一行是**用户会怎么描述需求**的现象句，配上该去哪个社区技能。
> 写法照 canonical 那份三列表格：现象句（用户口吻）/ 去向（纯文本）/ 备注（能力锚点）。
>
> 什么时候读：master-route 报 confidence: low / PRIMARY=R0 / "No strong keyword hit"，
> 且 community-route.py 报 no_match 需要换词重查之前——**先在这张表里对现象**，
> 对上哪行就经对应 wrapper 进入（hack-hub / ctf-hub / delivery / apk-extension），
> 进去之后一切以该 wrapper 的 SKILL.md 与下游为准。它不改任何路由逻辑，
> 只补社区侧关键词永远差一个字的"近失"。
>
> 去向说明（纯文本，无链接，满足 verify-doc-links）：形如"hack-hub · 401-403-bypass-techniques"
> 表示经 skills/community/hack-hub/SKILL.md 进入，下游找该原始技能名；
> ctf-hub 即 skills/community/ctf-hub/SKILL.md；delivery 即 skills/community/delivery/SKILL.md；
> apk-extension 即 skills/community/apk-extension/SKILL.md。
> 每行依据为 skills/community/registry.json 中该记录的 extensions.legacy_description
>（delivery 包该字段多为套话时，依据为 legacy_original_name 字面能力 + community-raw 正文前 20 行）。

## 症状 → 社区技能（一、hack-skills，经 hack-hub 进入）

| 用户这样说 | 去这里 | 备注 |
|---|---|---|
| "后台管理地址每次都回 403，换个大小写或加个斜杠说不定能混进去" | hack-hub · 401-403-bypass-techniques | 403 绕过/管理口 |
| "接口明明存在，登录后一点就提示没权限，想换种写法绕过这层拦截" | hack-hub · 401-403-bypass-techniques | 接口越权写法 |
| "管理员目录被拦了，想试试改请求方法和头能不能进去" | hack-hub · 401-403-bypass-techniques | 方法头混入 |
| "域里这个账号权限看着不大，但关系图上它能一路写到域控" | hack-hub · active-directory-acl-abuse | 误配权限提权 |
| "想看看这个组的写入权限能不能拿来提权" | hack-hub · active-directory-acl-abuse | 组误配利用 |
| "影子凭证那条路不知道通不通，得验一下" | hack-hub · active-directory-acl-abuse | 影子凭证验证 |
| "证书模板配得太松，好像能自己领一张高权限身份" | hack-hub · active-directory-certificate-services | 模板错配领证 |
| "证书服务那块听说有十几种模板毛病，得挨个验" | hack-hub · active-directory-certificate-services | 模板毛病普查 |
| "想拿张证书做持久化，机器掉了还能回来" | hack-hub · active-directory-certificate-services | 证书持久化 |
| "抓到一堆服务票据，想离线把服务账号口令啃出来" | hack-hub · active-directory-kerberos-attacks | 烤服务票据 |
| "有个账号开了免预认证，能不能直接要到票" | hack-hub · active-directory-kerberos-attacks | 免预认证要票 |
| "委派配得太宽，顺着它能不能跳到别的机器" | hack-hub · active-directory-kerberos-attacks | 委派跳机器 |
| "下载的模型权重不知干不干净，怕一加载就中招" | hack-hub · ai-ml-security | 权重投毒验货 |
| "线上问答模型总被人三绕两绕套出提示词" | hack-hub · ai-ml-security | 提示词被套 |
| "智能体能调好几个工具，怕一句话被骗去删库调接口" | hack-hub · ai-ml-security | 工具滥用 |
| "这安卓应用抓包全是钉死的证书，流量截不着" | hack-hub · android-pentesting-tricks | 钉死截流 |
| "应用检测到 root 就闪退，想绕过它再看" | hack-hub · android-pentesting-tricks | root 检测绕过 |
| "导出的组件好像没设权限，别的应用能直接调" | hack-hub · android-pentesting-tricks | 导出组件直调 |
| "一上调试器进程就退出，不知埋了哪种检测" | hack-hub · anti-debugging-techniques | 调试器检测点 |
| "断点一挂就失效，疑似有定时自检" | hack-hub · anti-debugging-techniques | 定时自检 |
| "想跟进去看，反调试点得先找出来处理掉" | hack-hub · anti-debugging-techniques | 反调试定位 |
| "这个令牌改个字段就验过了，签名像没验" | hack-hub · api-auth-and-jwt-abuse | 验签缺失伪造 |
| "接口的钥匙写死在客户端里，想看看能不能伪造身份" | hack-hub · api-auth-and-jwt-abuse | 钥匙伪造身份 |
| "令牌长期不过期，偷到一个能用好久" | hack-hub · api-auth-and-jwt-abuse | 令牌有效期 |
| "把请求里的用户编号换成别人的，数据直接就出来了" | hack-hub · api-authorization-and-bola | 编号换人看数 |
| "嵌套资源里别人的单子也能改" | hack-hub · api-authorization-and-bola | 嵌套资源越权 |
| "前端不显示的隐藏字段，提交了后端照收" | hack-hub · api-authorization-and-bola | 隐藏字段照收 |
| "只给了个域名，接口都藏在哪得先摸出来" | hack-hub · api-recon-and-docs | 接口摸排 |
| "找找有没有漏在网上的接口文档" | hack-hub · api-recon-and-docs | 文档外漏 |
| "版本号一堆，先盘清哪些还在跑" | hack-hub · api-recon-and-docs | 版本盘点 |
| "接口安全不知从哪下手，先要个检查顺序" | hack-hub · api-sec | 接口测试分诊 |
| "一堆接口，想先分分类再逐个测" | hack-hub · api-sec | 接口分类起手 |
| "授权和令牌哪块先查，得有人排个序" | hack-hub · api-sec | 检查顺序编排 |
| "手里有个能任意改内存的点，不知怎么改成执行命令" | hack-hub · arbitrary-write-to-rce | 写点转执行；与 heap-exploitation 二选一：手上已经有任意写原语，只差最后一步把它变成执行（GOT/hook/_IO_FILE/链表） → 本行；还在堆上找或造这个原语（UAF、double free、tcache/fastbin） → 078 |
| "越界写能改东西，但改哪才能拿控制权" | hack-hub · arbitrary-write-to-rce | 改哪拿控制；与 heap-exploitation 二选一：手上已经有任意写原语，只差最后一步把它变成执行（GOT/hook/_IO_FILE/链表） → 本行；还在堆上找或造这个原语（UAF、double free、tcache/fastbin） → 078 |
| "有个写原语，得找个钩子把它变成 shell" | hack-hub · arbitrary-write-to-rce | 钩子变 shell；与 heap-exploitation 二选一：手上已经有任意写原语，只差最后一步把它变成执行（GOT/hook/_IO_FILE/链表） → 本行；还在堆上找或造这个原语（UAF、double free、tcache/fastbin） → 078 |
| "就给了一个网址，先把能摸的入口列齐" | hack-hub · attack-surface-mapping | 单网址列入口 |
| "应用的脚本里藏了哪些接口，得盘一遍" | hack-hub · attack-surface-mapping | 脚本盘接口 |
| "子域名和暴露面先画张可测的图" | hack-hub · attack-surface-mapping | 暴露面成图 |
| "登录鉴权这块面太宽，不知先查哪" | hack-hub · auth-sec | 鉴权分诊起手 |
| "会话、令牌、单点混在一起，得先分诊" | hack-hub · auth-sec | 混合鉴权分诊 |
| "授权测试缺个起手顺序" | hack-hub · auth-sec | 起手顺序 |
| "登录框输啥都进不去，想试试逻辑上有没有洞" | hack-hub · authbypass-authentication-flaws | 登录逻辑洞 |
| "找回密码流程好像能改别人的口令" | hack-hub · authbypass-authentication-flaws | 找回改人口令 |
| "验证码能绕过，试错没人拦" | hack-hub · authbypass-authentication-flaws | 验证绕过试错 |
| "这程序的保护全开着，不知先拆哪个" | hack-hub · binary-protection-bypass | 保护项拆解 |
| "随机基址和金丝雀卡住了利用，得找绕法" | hack-hub · binary-protection-bypass | 基址金丝雀绕法 |
| "只读重定位开满了，改表那条路走不通" | hack-hub · binary-protection-bypass | 改表路被堵 |
| "浏览器一开特定页面就崩，像是引擎的毛病" | hack-hub · browser-exploitation-v8 | 特定页崩溃 |
| "引擎的即时编译看着能整出类型混乱" | hack-hub · browser-exploitation-v8 | 即时编译混乱 |
| "渲染进程拿下了，沙箱还没出来" | hack-hub · browser-exploitation-v8 | 渲染后出沙箱 |
| "价格和优惠券看着能动手脚，不知算不算洞" | hack-hub · business-logic-vuln | 业务分诊；与 054 二选一：还没定这算不算业务逻辑、要不要从注入转过来 → 本行（入口分诊）；已锁定业务逻辑要推演叠券/状态机/多步授权缺口 → 054 |
| "流程能跳步，多步状态机得捋捋" | hack-hub · business-logic-vuln | 跳步状态机；与 054 二选一：还没定这算不算业务逻辑、要不要从注入转过来 → 本行（入口分诊）；已锁定业务逻辑要推演叠券/状态机/多步授权缺口 → 054 |
| "注入扫了没东西，业务流程还没人看" | hack-hub · business-logic-vuln | 无注入看业务；与 054 二选一：还没定这算不算业务逻辑、要不要从注入转过来 → 本行（入口分诊）；已锁定业务逻辑要推演叠券/状态机/多步授权缺口 → 054 |
| "优惠券能叠加，结算金额越算越少" | hack-hub · business-logic-vulnerabilities | 叠券少钱；与 053 二选一：已经看到券被叠加、订单状态被改，要推演怎么打 → 本行（打法手册）；还没定这算不算业务逻辑 → 053 |
| "订单状态改改参数就变了，钱没付货先发了" | hack-hub · business-logic-vulnerabilities | 状态先货后钱；与 053 二选一：已经看到券被叠加、订单状态被改，要推演怎么打 → 本行（打法手册）；还没定这算不算业务逻辑 → 053 |
| "一人只能领一次的东西，换个姿势能领无数次" | hack-hub · business-logic-vulnerabilities | 限领变无限；与 053 二选一：已经看到券被叠加、订单状态被改，要推演怎么打 → 本行（打法手册）；还没定这算不算业务逻辑 → 053 |
| "拿到一串看不懂的替换密文，频率看着像老式密码" | hack-hub · classical-cipher-analysis | 替换密文频率 |
| "这段搅过的文字，得先分类再解" | hack-hub · classical-cipher-analysis | 搅文先分类 |
| "异或过的流量，密钥疑似很短能爆" | hack-hub · classical-cipher-analysis | 短钥爆破 |
| "敏感按钮疑似能被嵌进别人的页面里点" | hack-hub · clickjacking | 按钮被嵌点 |
| "页面能不能被框起来，得验一下" | hack-hub · clickjacking | 页面被框验证 |
| "点一下就中招的操作，怕被人罩层皮劫持" | hack-hub · clickjacking | 罩皮劫持点击 |
| "输入框里拼个分号，命令疑似被带进了解释器" | hack-hub · cmdi-command-injection | 分号带命令 |
| "上传的文件名一到后台就变了，像是被执行了" | hack-hub · cmdi-command-injection | 文件名被执行 |
| "导出功能巨慢，怀疑命令在后台跑，测测盲注" | hack-hub · cmdi-command-injection | 导出慢盲测 |
| "函数跳来跳去全是垃圾指令，主干看不清" | hack-hub · code-obfuscation-deobfuscation | 垃圾指令遮主干 |
| "字符串全加密了，逻辑连不成片" | hack-hub · code-obfuscation-deobfuscation | 加密串还原 |
| "控制流被压平了，得先捋直再看" | hack-hub · code-obfuscation-deobfuscation | 压平控制流 |
| "困在容器里了，想摸到宿主机上去" | hack-hub · container-escape-techniques | 容器摸宿主 |
| "容器挂了个奇怪的目录，疑似能钻出去" | hack-hub · container-escape-techniques | 挂目录钻出 |
| "特权容器里能看到宿主进程，得找逃逸路" | hack-hub · container-escape-techniques | 特权容器逃逸 |
| "跨域配得太松，别家页面能直接读这边的登录数据" | hack-hub · cors-cross-origin-misconfiguration | 松跨域读数据 |
| "来源没验，带凭证的请求随便发" | hack-hub · cors-cross-origin-misconfiguration | 来源未验 |
| "预检看着像摆设，实际全放行" | hack-hub · cors-cross-origin-misconfiguration | 预检摆设 |

| "用户在地址栏里敲回车符，响应头被劈成两截" | hack-hub · crlf-injection | 回车劈响应头 |
| "跳转地址被动手脚后，连 cookie 都被带上了" | hack-hub · crlf-injection | 跳转带私货 |
| "日志里混进了伪造的记录，输入没过滤换行" | hack-hub · crlf-injection | 日志伪造记录 |
| "弹窗脚本被策略拦了，得找策略本身的口子" | hack-hub · csp-bypass-advanced | 策略拦脚本找口 |
| "数据偷不出去，策略把外发通道卡死了" | hack-hub · csp-bypass-advanced | 外发通道被卡 |
| "可信域名里有个能利用的端点，想借它绕过限制" | hack-hub · csp-bypass-advanced | 借可信端点 |
| "改资料的请求别人也能替我发，防伪令牌像没验" | hack-hub · csrf-cross-site-request-forgery | 替发改资料 |
| "登录状态下点个别站链接，账号设置就被改了" | hack-hub · csrf-cross-site-request-forgery | 点链接改设置 |
| "第三方登录回来那步，状态参数没人对" | hack-hub · csrf-cross-site-request-forgery | 回调状态未对 |
| "导出的表格一打开就往外发请求，格子里藏了公式" | hack-hub · csv-formula-injection | 表格公式外发 |
| "用户填的东西进了报表，打开表格就执行" | hack-hub · csv-formula-injection | 报表带执行 |
| "导入导出的字段直通电子表格，公式没清" | hack-hub · csv-formula-injection | 导入公式未清 |
| "脚本标签全被杀了，但还能往页面里钉钉子偷数据" | hack-hub · dangling-markup-injection | 无脚本钉钉偷数 |
| "过滤器把事件都剥了，令牌还是 leak 出去了" | hack-hub · dangling-markup-injection | 剥事件仍泄漏 |
| "弹窗出不来，但页面里的数据能一点点被钓走" | hack-hub · dangling-markup-injection | 数据被钓走 |
| "借闪电贷把池子价格砸歪，一进一出赚走差价" | hack-hub · defi-attack-patterns | 闪贷砸价差 |
| "预言机喂价被操纵，合约按错价结算了" | hack-hub · defi-attack-patterns | 喂价被操纵 |
| "跨链桥那边的资产证明看着能伪造" | hack-hub · defi-attack-patterns | 桥证明伪造 |
| "装的依赖包名字跟内部包一样，实际来自公网" | hack-hub · dependency-confusion | 内外同名包 |
| "构建时拉下来个没见过的版本，疑似被掉包" | hack-hub · dependency-confusion | 构建拉错版本 |
| "私有包的命名被人抢注到了公网上" | hack-hub · dependency-confusion | 私名被抢注 |
| "传过去的对象一反序列化就执行了东西" | hack-hub · deserialization-insecure | 反序列化执行 |
| "缓存里的序列化数据被改了，应用直接吃下" | hack-hub · deserialization-insecure | 缓存数据被改 |
| "老框架的反序列化接口还开着，得验能不能打" | hack-hub · deserialization-insecure | 老接口可打性 |
| "浏览器里配个恶意解析，就能摸到内网服务" | hack-hub · dns-rebinding-attacks | 解析摸内网 |
| "服务端扫不到的内网，换浏览器上下文能碰到" | hack-hub · dns-rebinding-attacks | 换上下文碰内网 |
| "域名一会指公网一会指内网，校验被绕过去了" | hack-hub · dns-rebinding-attacks | 解析跳变绕验 |
| "联系表单能往邮件头里塞换行，收件人被改了" | hack-hub · email-header-injection | 表单塞邮件头 |
| "找回密码的信发到了别人的邮箱" | hack-hub · email-header-injection | 重置信发错人 |
| "邮件接口的用户字段没过滤，能伪造发件人" | hack-hub · email-header-injection | 伪造发件人 |
| "模板里 ${} 那种写法，用户输入也被算了一遍" | hack-hub · expression-language-injection | 输入被求值；与 xslt-injection 二选一：可控输入是表达式串（Java EL/SpEL/OGNL/MVEL，落在 Spring/Struts2/Confluence） → 本行；可控输入是 XSLT 样式表或转换端点 → 136 |
| "框架的表达式语言吃了用户内容，得验算到哪" | hack-hub · expression-language-injection | 表达式吃输入；与 xslt-injection 二选一：可控输入是表达式串（Java EL/SpEL/OGNL/MVEL，落在 Spring/Struts2/Confluence） → 本行；可控输入是 XSLT 样式表或转换端点 → 136 |
| "老 Java 站的表达式注入点还开着" | hack-hub · expression-language-injection | 老站表达式点；与 xslt-injection 二选一：可控输入是表达式串（Java EL/SpEL/OGNL/MVEL，落在 Spring/Struts2/Confluence） → 本行；可控输入是 XSLT 样式表或转换端点 → 136 |
| "下载接口传个路径就能看任意文件" | hack-hub · file-access-vuln | 下载看任意文 |
| "上传流程缺个分诊，不知先查哪段" | hack-hub · file-access-vuln | 文件流程分诊 |
| "预览和解压那几步，文件边界没人看" | hack-hub · file-access-vuln | 预览解压边界 |
| "日志打印用户输入，进程直接崩了能读内存" | hack-hub · format-string-exploitation | 打印崩读内存 |
| "格式化串可控，想先把栈上的东西扒出来" | hack-hub · format-string-exploitation | 可控串扒栈 |
| "有个 %n 可写，得找改哪里能拿控制" | hack-hub · format-string-exploitation | 写哪拿控制 |
| "Java 接口的拦截对大小写变体全放行，疑似窄化绕过" | hack-hub · ghost-bits-cast-attack | 窄化绕拦截 |
| "上传校验被特殊字符骗过去了" | hack-hub · ghost-bits-cast-attack | 校验被骗过 |
| "拦截器看不懂的字节，后端照单全收" | hack-hub · ghost-bits-cast-attack | 后端照单收 |
| "接口的自描述开关还开着，表关系直接能摸出来" | hack-hub · graphql-and-hidden-parameters | 自描述摸表 |
| "文档里没写的字段，试出来真能用" | hack-hub · graphql-and-hidden-parameters | 未写字段可用 |
| "批量查一次能捞全库，得看看限没限" | hack-hub · graphql-and-hidden-parameters | 批量捞全库 |
| "渗透活不知从哪开工，先要个打法总纲" | hack-hub · hack | 开工打法总纲 |
| "手里一堆发现，不知先跟哪条利用路" | hack-hub · hack | 利用路排序 |
| "授权测试的范围和步骤，得先立个规矩" | hack-hub · hack | 范围步骤立规 |
| "旧哈希算法的碰撞看着能用，得验" | hack-hub · hash-attack-techniques | 旧算法碰撞 |
| "长度能续写的签名，尾巴上能挂东西" | hack-hub · hash-attack-techniques | 签名续写挂物 |
| "比对时间忽长忽短，疑似能逐字节猜" | hack-hub · hash-attack-techniques | 比对时间猜字节 |
| "释放后还用的那块堆，不知怎么改成写" | hack-hub · heap-exploitation | 释放后改写；与 arbitrary-write-to-rce 二选一：还在堆上找/造任意写原语（UAF、double free、溢出、tcache/fastbin/unsortedbin） → 本行；原语已有、只差转执行 → 047 |
| "堆越界差一字节，看看能不能滚成大洞" | hack-hub · heap-exploitation | 差一字节滚洞；与 arbitrary-write-to-rce 二选一：还在堆上找/造任意写原语（UAF、double free、溢出、tcache/fastbin/unsortedbin） → 本行；原语已有、只差转执行 → 047 |
| "堆上那个越界写看着能改东西，但怎么拿控制权没想明白" | hack-hub · heap-exploitation | 越界改拿控制；与 arbitrary-write-to-rce 二选一：还在堆上找/造任意写原语（UAF、double free、溢出、tcache/fastbin/unsortedbin） → 本行；原语已有、只差转执行 → 047 |
| "重置密码的链接发到了攻击者的域名下" | hack-hub · http-host-header-attacks | 重置链发错域 |
| "缓存里躺着别人的页面，疑似头被投毒了" | hack-hub · http-host-header-attacks | 头投毒串缓存 |
| "应用拿请求头拼链接，改改就跳到别处" | hack-hub · http-host-header-attacks | 头拼链跳转 |
| "同一个参数传两份，拦截器和应用各取了一份" | hack-hub · http-parameter-pollution | 两份各取一份 |
| "过滤器看的是第一个值，执行的却是第二个" | hack-hub · http-parameter-pollution | 看一执行二 |
| "代理和源站对重复参数理解不一，能钻空" | hack-hub · http-parameter-pollution | 理解不一钻空 |
| "目标开了新版协议，二进制分帧看着能玩花样" | hack-hub · http2-specific-attacks | 新协议分帧花样 |
| "协议降级那一下，请求被塞进了别人的连接" | hack-hub · http2-specific-attacks | 降级塞连接 |
| "伪头能注东西，后端解析和前端不是一套" | hack-hub · http2-specific-attacks | 伪头解析不一 |
| "切小号登进去，把序号挨个换，能捞到别人的单子" | hack-hub · idor-broken-object-authorization | 换序号捞单 |
| "租户隔离像纸糊的，改个标识就进别人家" | hack-hub · idor-broken-object-authorization | 改标识串户 |
| "删别人的东西居然也成功了，对象没验归属" | hack-hub · idor-broken-object-authorization | 删他人物成功 |
| "输入点太多，不知该按哪种注入去测" | hack-hub · injection-checking | 注入类型分诊 |
| "用户输入进哪种解析器，先分个类再动手" | hack-hub · injection-checking | 解析器分类 |
| "一堆注入面，得先排个优先级" | hack-hub · injection-checking | 注入面排序 |
| "网站根下能直接下到代码仓库目录" | hack-hub · insecure-source-code-management | 根下拖仓库 |
| "隐藏目录回 403，但备份文件能直接下" | hack-hub · insecure-source-code-management | 备份直下 |
| "配置文件里的钥匙被一起打包发布了" | hack-hub · insecure-source-code-management | 钥匙随包发布 |
| "苹果应用的数据包死活截不着，想让它走一遍代理" | hack-hub · ios-pentesting-tricks | 苹果包走代理 |
| "钥匙串里存的东西别的应用能读到" | hack-hub · ios-pentesting-tricks | 串存物被读 |
| "跳转链接没验归属，别的程序能劫走" | hack-hub · ios-pentesting-tricks | 跳转被劫走 |

| "Java 日志里打个特殊字符串，服务器就去连了外部地址" | hack-hub · jndi-injection | 日志串连外部 |
| "老查找接口还开着，名字可控能指到别处" | hack-hub · jndi-injection | 查找名可控 |
| "输入一路走到了命名查找，得验能不能打" | hack-hub · jndi-injection | 输入进查找 |
| "令牌算法改成 none 居然也认" | hack-hub · jwt-oauth-token-attacks | 改算法也认 |
| "令牌里的身份字段随便改，改完照样进" | hack-hub · jwt-oauth-token-attacks | 身份字段随便改 |
| "第三方登录绑错了账号，拿 A 的号进了 B 的家" | hack-hub · jwt-oauth-token-attacks | 登录绑错号 |
| "内核模块有个可疑的读写口，想看看普通用户能不能打到提权" | hack-hub · kernel-exploitation | 内核口提权 |
| "新爆的内核洞，自家版本在不在影响里得验" | hack-hub · kernel-exploitation | 新洞影响验证 |
| "用户态洞走不通了，得往内核找路" | hack-hub · kernel-exploitation | 用户态转内核 |
| "集群的管控面没验身份，谁都能连上去看" | hack-hub · kubernetes-pentesting | 管控面裸奔 |
| "容器里捡到个服务账号，权限大得能管全场" | hack-hub · kubernetes-pentesting | 捡到大权账号 |
| "听说容器能直接跑到宿主机上，想验证下是不是真有这条路" | hack-hub · kubernetes-pentesting | 容器跑宿主验证 |
| "签名参数看着有点偏，能不能把私钥算出来" | hack-hub · lattice-crypto-attacks | 偏参数算私钥；与 rsa-attack-techniques 二选一：要的是格方法才解得动（小根、nonce 偏差、LLL/BKZ 归约） → 本行；只给了常规 RSA 参数要靠弱密钥/小指数/共模/padding oracle → 112 |
| "两把钥匙共了个因子，看看能不能一起拆了" | hack-hub · lattice-crypto-attacks | 共因子拆钥；与 rsa-attack-techniques 二选一：要的是格方法才解得动（小根、nonce 偏差、LLL/BKZ 归约） → 本行；只给了常规 RSA 参数要靠弱密钥/小指数/共模/padding oracle → 112 |
| "随机数歪了一点点，签名多攒几条能回推" | hack-hub · lattice-crypto-attacks | 歪随机回推；与 rsa-attack-techniques 二选一：要的是格方法才解得动（小根、nonce 偏差、LLL/BKZ 归约） → 本行；只给了常规 RSA 参数要靠弱密钥/小指数/共模/padding oracle → 112 |
| "一台 Linux 拿下了，内网还有一堆，得横着走" | hack-hub · linux-lateral-movement | 拿一横多台 |
| "密钥和票据散在机器上，得收一收再跳" | hack-hub · linux-lateral-movement | 收票据再跳 |
| "内网跳板缺条路，得搭个稳定的过去" | hack-hub · linux-lateral-movement | 跳板搭路 |
| "普通 shell 到手了，想变成本机最高权限" | hack-hub · linux-privilege-escalation | 普通变最高 |
| "特殊权限文件一堆，哪个能用来提权得筛" | hack-hub · linux-privilege-escalation | 特殊文件筛提权 |
| "定时任务跑的脚本谁都能改，等它触发就行" | hack-hub · linux-privilege-escalation | 定时脚本可改 |
| "受限 shell 啥也干不了，得先逃出来" | hack-hub · linux-security-bypass | 受限壳逃脱 |
| "只读目录卡死了操作，换条路写东西" | hack-hub · linux-security-bypass | 只读换路写 |
| "操作全被记下来了，想让记录睁只眼闭只眼" | hack-hub · linux-security-bypass | 记录睁闭眼 |
| "灌给模型的资料疑似被掺了沙子，答话总往沟里带" | hack-hub · llm-prompt-injection | 资料掺沙子 |
| "接进来的问答客服，三绕两绕就被人套出不该说的话" | hack-hub · llm-prompt-injection | 客服被套话 |
| "网页里藏了段看不见的字，助手读完就照做了" | hack-hub · llm-prompt-injection | 藏字指使助手 |
| "苹果机上想往运行中的进程里塞点代码" | hack-hub · macos-process-injection | 往进程塞代码 |
| "启动时库被调了包，进程起来就带了私货" | hack-hub · macos-process-injection | 启动库被调包 |
| "进程间聊天的通道没验身份，能冒充" | hack-hub · macos-process-injection | 通道冒充 |
| "系统弹窗老要权限，想查是哪家进程在要" | hack-hub · macos-security-bypass | 弹窗要权限溯源 |
| "下载的东西双击就跑，关卡像没拦" | hack-hub · macos-security-bypass | 下载直跑未拦 |
| "隔离沙箱里的程序想读通讯录，得看看拦没拦住" | hack-hub · macos-security-bypass | 沙箱读物验证 |
| "电脑中招了，导了个内存镜像，想看看坏东西藏在哪" | hack-hub · memory-forensics-volatility | 内存找坏东西；与 ctf 侧 CTF•数字取证 二选一：手上是内存转储、要找注入点/凭据/进程线索与时间线 → 本行；材料是磁盘镜像/PCAP/隐写混合包 → CTF 005 |
| "内存里扒出了账号口令，得捋出它从哪来的" | hack-hub · memory-forensics-volatility | 内存扒口令溯源；与 ctf 侧 CTF•数字取证 二选一：手上是内存转储、要找注入点/凭据/进程线索与时间线 → 本行；材料是磁盘镜像/PCAP/隐写混合包 → CTF 005 |
| "可疑进程藏得深，内存里把它揪出来" | hack-hub · memory-forensics-volatility | 内存揪藏进程；与 ctf 侧 CTF•数字取证 二选一：手上是内存转储、要找注入点/凭据/进程线索与时间线 → 本行；材料是磁盘镜像/PCAP/隐写混合包 → CTF 005 |
| "手机应用把证书钉死了，代理挂上也只剩握手失败" | hack-hub · mobile-ssl-pinning-bypass | 钉死握手失败 |
| "抓包看到的全是加密，看不到明文请求" | hack-hub · mobile-ssl-pinning-bypass | 加密不见明文 |
| "跨平台打包的应用，流量 pin 在奇怪的地方" | hack-hub · mobile-ssl-pinning-bypass | 打包应用 pin 位 |
| "内网有人在冒充网关，流量被拐走了" | hack-hub · network-protocol-attacks | 冒充网关拐流 |
| "名字解析总被抢答，credentials 飞到了别人家" | hack-hub · network-protocol-attacks | 解析被抢答 |
| "插网线就能进内网，接入层像没设防" | hack-hub · network-protocol-attacks | 插线直进内网 |
| "搜索框里塞个特殊对象，查出了不该看的数据" | hack-hub · nosql-injection | 特殊对象查数据 |
| "筛选条件传个正则，整库都被拖出来了" | hack-hub · nosql-injection | 正则拖整库 |
| "登录的比对被操作符骗过去了" | hack-hub · nosql-injection | 比对被骗过 |
| "打印机一叫，机器的身份票就飞出去了" | hack-hub · ntlm-relay-coercion | 一叫票飞出 |
| "截到的身份能转到别的服务上用" | hack-hub · ntlm-relay-coercion | 截身份转用 |
| "逼它来连我，把认证中继到数据库上" | hack-hub · ntlm-relay-coercion | 逼连中继库 |
| "第三方登录跳完回来，地址栏里多了不该有的东西" | hack-hub · oauth-oidc-misconfiguration | 跳回多东西 |
| "回调地址写得太宽，凭证被人半路截走" | hack-hub · oauth-oidc-misconfiguration | 回调太宽截证 |
| "免密登录的断言包好像没验签，得查查" | hack-hub · oauth-oidc-misconfiguration | 断言验签 |
| "链接参数里带了个网址，点登录跳到了别人家" | hack-hub · open-redirect | 参数网址跳别家；与 ctf 侧 Strix•开放重定向 二选一：定位哪个 URL 参数、表单动作、JS 汇控制跳转目标 → 本行；要钓鱼/令牌窃取的现成手法 → Strix 027 |
| "扫出来的跳转没验白名单，能拿去钓鱼" | hack-hub · open-redirect | 跳转可钓鱼；与 ctf 侧 Strix•开放重定向 二选一：定位哪个 URL 参数、表单动作、JS 汇控制跳转目标 → 本行；要钓鱼/令牌窃取的现成手法 → Strix 027 |
| "登录成功后的落地页随便指，得收一收" | hack-hub · open-redirect | 落地页随便指；与 ctf 侧 Strix•开放重定向 二选一：定位哪个 URL 参数、表单动作、JS 汇控制跳转目标 → 本行；要钓鱼/令牌窃取的现成手法 → Strix 027 |
| "下载链接改改就看到了系统文件" | hack-hub · path-traversal-lfi | 改链看系统文 |
| "模板包含能指到别处，页面吐出了源码" | hack-hub · path-traversal-lfi | 包含吐源码 |
| "解压出来的文件跑到了不该去的目录" | hack-hub · path-traversal-lfi | 解压跑错目录 |
| "配配置的合并把脏键吃进了原型" | hack-hub · prototype-pollution | 合并吃脏键 |
| "查询串拼出的对象多了一堆不该有的属性" | hack-hub · prototype-pollution | 对象多脏属性 |
| "前端库拿了不可信的键当配置，得查影响" | hack-hub · prototype-pollution | 脏键当配置 |
| "污染点确认了，下一步看能不能变执行" | hack-hub · prototype-pollution-advanced | 污染变执行 |
| "过滤看着严，但变体还能绕过去" | hack-hub · prototype-pollution-advanced | 变体绕过滤 |
| "客户端的小件能被污染带偏，得找利用链" | hack-hub · prototype-pollution-advanced | 小件带偏利用 |
| "一人一次的优惠，并发多点几次全成功了" | hack-hub · race-condition | 并发破限领 |
| "先到先得的券，卡着同一毫秒全拿到了" | hack-hub · race-condition | 同毫秒全拿 |
| "余额扣减和发货之间有缝，并发能钻" | hack-hub · race-condition | 扣发之间缝 |
| "新目标还没摸过，先列个侦察清单" | hack-hub · recon-and-methodology | 新目标清单；与 109 二选一：要把资产、端点、指纹汇成一份成体系的测试计划 → 本行；范围已收敛到一个应用、要挑第一条值得打的 → 109 |
| "指纹还没认全，技术栈得先盘出来" | hack-hub · recon-and-methodology | 指纹认技术栈；与 109 二选一：要把资产、端点、指纹汇成一份成体系的测试计划 → 本行；范围已收敛到一个应用、要挑第一条值得打的 → 109 |
| "端点散得到处是，得建个可测的清单" | hack-hub · recon-and-methodology | 端点建清单；与 109 二选一：要把资产、端点、指纹汇成一份成体系的测试计划 → 本行；范围已收敛到一个应用、要挑第一条值得打的 → 109 |
| "侦察缺个总分诊，不知先画哪块" | hack-hub · recon-for-sec | 侦察总分诊；与 108 二选一：要收敛授权范围、画出单个应用攻击面并选第一条高价值路径 → 本行（范围路由）；要成体系的测试计划 → 108 |
| "范围就一个应用，先把面画出来再动手" | hack-hub · recon-for-sec | 单应用画面；与 108 二选一：要收敛授权范围、画出单个应用攻击面并选第一条高价值路径 → 本行（范围路由）；要成体系的测试计划 → 108 |
| "资产盘点和端点清单，得排个先后" | hack-hub · recon-for-sec | 盘点排先后；与 108 二选一：要收敛授权范围、画出单个应用攻击面并选第一条高价值路径 → 本行（范围路由）；要成体系的测试计划 → 108 |
| "两个请求粘一起发，后端数出三个来" | hack-hub · request-smuggling | 粘发数多 |
| "前代理和源站对包长短理解不一，能塞私货" | hack-hub · request-smuggling | 长短理解不一 |
| "缓存里混进了别人的响应，疑似包边界被钻了" | hack-hub · request-smuggling | 包边界钻缓存 |

| "命令执行有了，但回显没有，得把 shell 反连出来" | hack-hub · reverse-shell-techniques | 无回显反连 |
| "拿到的 shell 一会就断，得换个稳的" | hack-hub · reverse-shell-techniques | 断连换稳壳 |
| "目标上没趁手工具，一行命令起个 shell" | hack-hub · reverse-shell-techniques | 一行起 shell |
| "给了公钥模数和指数，明文得想办法算回来" | hack-hub · rsa-attack-techniques | 给参算回明文；与 lattice-crypto-attacks 二选一：只给了 (n,e,c)，要靠弱密钥、小指数、共模、padding oracle 解明文 → 本行；必须用格方法才能解 → 090 |
| "两把钥匙看着像共了点东西，能一起拆" | hack-hub · rsa-attack-techniques | 共点一起拆；与 lattice-crypto-attacks 二选一：只给了 (n,e,c)，要靠弱密钥、小指数、共模、padding oracle 解明文 → 本行；必须用格方法才能解 → 090 |
| "小指数加密的东西，看看能不能直接开出来" | hack-hub · rsa-attack-techniques | 小指数开文；与 lattice-crypto-attacks 二选一：只给了 (n,e,c)，要靠弱密钥、小指数、共模、padding oracle 解明文 → 本行；必须用格方法才能解 → 090 |
| "单点登录的断言改改就认了，签名像没验" | hack-hub · saml-sso-assertion-attacks | 断言改改认 |
| "企业登录的票能拿到别处去用" | hack-hub · saml-sso-assertion-attacks | 票跨处用 |
| "断言包里的收件方没验，能转送" | hack-hub · saml-sso-assertion-attacks | 收件未验转送 |
| "脚本只能跑在笼子里，想钻出来执行任意东西" | hack-hub · sandbox-escape-techniques | 笼里钻出执行 |
| "沙箱的过滤看着严，换条调用路试试" | hack-hub · sandbox-escape-techniques | 换调用路 |
| "受限环境读写被卡，得找条缝出去" | hack-hub · sandbox-escape-techniques | 受限找缝出 |
| "合约里的钱能被反复掏，调用没锁住" | hack-hub · smart-contract-vulnerabilities | 反复掏钱未锁 |
| "小数算错一位，池子里的钱对不上了" | hack-hub · smart-contract-vulnerabilities | 算错对不上 |
| "管理员函数谁都能调，得看看" | hack-hub · smart-contract-vulnerabilities | 管理函数裸奔 |
| "登录框输个单引号，页面反应不一样了" | hack-hub · sqli-sql-injection | 单引号反应异；与 ctf 侧 Strix•SQL 注入 二选一：定位输入到达 SQL 查询、认证、排序、过滤、报表的位置 → 本行；要现成的 union/盲注/ORM 绕过串 → Strix 031 |
| "排序参数换个写法，数据出得不一样" | hack-hub · sqli-sql-injection | 排序写法异数；与 ctf 侧 Strix•SQL 注入 二选一：定位输入到达 SQL 查询、认证、排序、过滤、报表的位置 → 本行；要现成的 union/盲注/ORM 绕过串 → Strix 031 |
| "页面睡几秒才回，输入疑似进了查询" | hack-hub · sqli-sql-injection | 睡回疑进查询；与 ctf 侧 Strix•SQL 注入 二选一：定位输入到达 SQL 查询、认证、排序、过滤、报表的位置 → 本行；要现成的 union/盲注/ORM 绕过串 → Strix 031 |
| "填个网址服务器就去抓了，内网地址也抓" | hack-hub · ssrf-server-side-request-forgery | 填址内网也抓；与 ctf 侧 Strix•SSRF 测试 二选一：说的是生产侧代取/解析/导入远程内容 → 本行；题面是比赛靶场、要工具化打法 → Strix 033 |
| "导入功能传个内网地址，内容被读出来了" | hack-hub · ssrf-server-side-request-forgery | 导入读内网；与 ctf 侧 Strix•SSRF 测试 二选一：说的是生产侧代取/解析/导入远程内容 → 本行；题面是比赛靶场、要工具化打法 → Strix 033 |
| "云上的身份地址能被调到，可以换钥匙" | hack-hub · ssrf-server-side-request-forgery | 身份地址换钥；与 ctf 侧 Strix•SSRF 测试 二选一：说的是生产侧代取/解析/导入远程内容 → 本行；题面是比赛靶场、要工具化打法 → Strix 033 |
| "模板里写个算式，服务端真给算了" | hack-hub · ssti-server-side-template-injection | 算式真被算 |
| "预览功能把输入当模板跑了一遍" | hack-hub · ssti-server-side-template-injection | 预览跑模板 |
| "报错里吐出了模板引擎的名字，得试试" | hack-hub · ssti-server-side-template-injection | 报错吐引擎名 |
| "超长输入怼过去服务就崩，得做成稳的利用" | hack-hub · stack-overflow-and-rop | 崩做成稳利用 |
| "返回地址能盖了，下一步拼条链子" | hack-hub · stack-overflow-and-rop | 盖址拼链子 |
| "本地耍得通，一上远端就掉链，差临门一口气" | hack-hub · stack-overflow-and-rop | 本地通远端断 |
| "图片里疑似藏了东西，大小对不上" | hack-hub · steganography-techniques | 图大小不对 |
| "音频听着有杂音，频谱里可能有字" | hack-hub · steganography-techniques | 杂音频谱字 |
| "文件尾巴上多了一截，格式看着是拼的" | hack-hub · steganography-techniques | 尾多截拼格式 |
| "子域名指到了个没人要的服务，看看能不能接管" | hack-hub · subdomain-takeover | 野指接管 |
| "解析记录悬空了，指向的资源早下线了" | hack-hub · subdomain-takeover | 记录悬空 |
| "过期服务绑着自家域名，得验能不能认领" | hack-hub · subdomain-takeover | 过期绑域认领 |
| "校验逻辑太绕，手算走不动，得让机器解约束" | hack-hub · symbolic-execution-tools | 绕校验解约束 |
| "一堆输入条件拦着，想反推出钥匙" | hack-hub · symbolic-execution-tools | 反推钥匙 |
| "逆向卡在复杂判断上，符号执行探探路" | hack-hub · symbolic-execution-tools | 复杂判断探路 |
| "同样的明文每次出不同的错位，模式看着像 ECB" | hack-hub · symmetric-cipher-attacks | 同文异错位 |
| "改一个字节 downstream 全乱，填充可能能玩" | hack-hub · symmetric-cipher-attacks | 改字节玩填充 |
| "流密钥疑似被重用了，两段密文能对消" | hack-hub · symmetric-cipher-attacks | 密钥重用对消 |
| "网管导了份抓包，里面好像有异常外连" | hack-hub · traffic-analysis-pcap | 抓包翻外连 |
| "加密流量看不到内容，得从元数据找线索" | hack-hub · traffic-analysis-pcap | 加密看元数据 |
| "抓到的包打不开了，疑似坏了要修" | hack-hub · traffic-analysis-pcap | 坏包修复 |
| "内网的机器够不着，得借已拿下的搭条路" | hack-hub · tunneling-and-pivoting | 借机搭路 |
| "出口只剩 DNS，得把流量裹进去带出来" | hack-hub · tunneling-and-pivoting | 流量裹 DNS |
| "多层跳板串起来，代理链得排一排" | hack-hub · tunneling-and-pivoting | 跳板串代理链 |
| "密码比对用的松散相等，特殊值能蒙混" | hack-hub · type-juggling | 松散比对蒙混 |
| "签名校验没用严比对，假值能过" | hack-hub · type-juggling | 假值过校验 |
| "老系统的弱类型坑还在，得验影响" | hack-hub · type-juggling | 老弱类型验影响 |
| "缓存服务谁都能连，还能写文件" | hack-hub · unauthorized-access-common-services | 缓存裸连写文 |
| "管理后台没设密码，直接就进了" | hack-hub · unauthorized-access-common-services | 后台无密直进 |
| "暴露的中间件控制台能执行东西" | hack-hub · unauthorized-access-common-services | 控制台可执行 |
| "头像上传改个后缀就成了可执行，路径能猜到" | hack-hub · upload-insecure-files | 改后缀成执行；与 ctf 侧 Strix•不安全文件上传 二选一：查上传校验、落盘路径、处理与预览管线、覆盖风险、上传转 RCE 链 → 本行；卡扩展名/Content-Type/路径穿越 → Strix 024 |
| "传上去的文件被二次处理，处理环节能动手" | hack-hub · upload-insecure-files | 二次处理动手；与 ctf 侧 Strix•不安全文件上传 二选一：查上传校验、落盘路径、处理与预览管线、覆盖风险、上传转 RCE 链 → 本行；卡扩展名/Content-Type/路径穿越 → Strix 024 |
| "上传目录能直接访问，传完就能连上" | hack-hub · upload-insecure-files | 传完直连；与 ctf 侧 Strix•不安全文件上传 二选一：查上传校验、落盘路径、处理与预览管线、覆盖风险、上传转 RCE 链 → 本行；卡扩展名/Content-Type/路径穿越 → Strix 024 |
| "程序里住了个自家定的小解释器，指令全是私货" | hack-hub · vm-and-bytecode-reverse | 私货解释器 |
| "朋友丢来一段怪脚本，执行时像里头住了个翻译" | hack-hub · vm-and-bytecode-reverse | 脚本住翻译 |
| "调度循环绕来绕去，真实逻辑被藏起来了" | hack-hub · vm-and-bytecode-reverse | 调度藏逻辑 |
| "注入语句全被拦了，得换写法绕过这堵墙" | hack-hub · waf-bypass-techniques | 注入被拦换写 |
| "拦截规则看着死，编码变体能过去" | hack-hub · waf-bypass-techniques | 编码变体过 |
| "墙按指纹拦的，换种协议姿势试试" | hack-hub · waf-bypass-techniques | 换姿势过墙 |
| "登录后的页面被别人刷出来了，缓存钥匙没分清" | hack-hub · web-cache-deception | 缓存串他人页 |
| "静态资源路径加个后缀，命中的是别人的私货" | hack-hub · web-cache-deception | 路径后缀串私 |
| "代理缓存了带身份的内容，得验" | hack-hub · web-cache-deception | 身份内容被缓 |
| "聊天消息走实时通道，握手那步像没验身份" | hack-hub · websocket-security | 握手未验身份 |
| "实时推送能替别人订阅，号换换就行" | hack-hub · websocket-security | 换号替订阅 |
| "长连接里的消息没做边界，别人能插话" | hack-hub · websocket-security | 长连接被插话 |
| "小工具一落地就被系统自带的卫士吞了，得让它活下来" | hack-hub · windows-av-evasion | 落地被吞求活 |
| "脚本的每一步都被记得清清楚楚，想让记录睁只眼闭只眼" | hack-hub · windows-av-evasion | 记录睁闭眼 |
| "内存里的 shellcode 一跑就被杀，得换个姿势" | hack-hub · windows-av-evasion | 内存码被杀换姿 |
| "一台 Windows 拿下了，隔壁几台也想去" | hack-hub · windows-lateral-movement | 拿一去隔壁 |
| "抓到一串哈希，想看看能不能在别处直接拿来用" | hack-hub · windows-lateral-movement | 哈希别处用 |
| "远程管理口开着，凭证复用能登过去" | hack-hub · windows-lateral-movement | 管口凭证复用 |
| "普通权限的 shell，想变成本机管理员" | hack-hub · windows-privilege-escalation | 普通变管理 |
| "服务跑的程序谁都能换，等重启就行" | hack-hub · windows-privilege-escalation | 服务程序可换 |
| "弹窗点个是就提权了，确认框能绕过" | hack-hub · windows-privilege-escalation | 确认框绕过 |
| "模板转换的入口吃了用户内容，得看能算到哪" | hack-hub · xslt-injection | 转换吃输入；与 expression-language-injection 二选一：可控输入是 XSLT 样式表或转换端点，要处理器指纹、XXE/document()、EXSLT 写原语 → 本行；可控输入是表达式串 → 071 |
| "样式表能读外部文件，内网也能探" | hack-hub · xslt-injection | 样式读外文探内；与 expression-language-injection 二选一：可控输入是 XSLT 样式表或转换端点，要处理器指纹、XXE/document()、EXSLT 写原语 → 本行；可控输入是表达式串 → 071 |
| "转换引擎的扩展能执行东西，得验" | hack-hub · xslt-injection | 扩展可执行验；与 expression-language-injection 二选一：可控输入是 XSLT 样式表或转换端点，要处理器指纹、XXE/document()、EXSLT 写原语 → 本行；可控输入是表达式串 → 071 |
| "输入框里敲个弹窗，存进去每打开一次弹一次" | hack-hub · xss-cross-site-scripting | 存入次次弹；与 ctf 侧 Strix•XSS 测试 二选一：定位可控内容落到 HTML/属性/JS/DOM 汇或上传路径 → 本行；要三类向量与 CSP 绕过的现成打法 → Strix 035 |
| "链接里带的参数原样进了页面脚本" | hack-hub · xss-cross-site-scripting | 参数进脚本；与 ctf 侧 Strix•XSS 测试 二选一：定位可控内容落到 HTML/属性/JS/DOM 汇或上传路径 → 本行；要三类向量与 CSP 绕过的现成打法 → Strix 035 |
| "富文本过滤不严，换种标签又能弹" | hack-hub · xss-cross-site-scripting | 换标签再弹；与 ctf 侧 Strix•XSS 测试 二选一：定位可控内容落到 HTML/属性/JS/DOM 汇或上传路径 → 本行；要三类向量与 CSP 绕过的现成打法 → Strix 035 |
| "上传的表格文件被当成配置读了，里面能引外部" | hack-hub · xxe-xml-external-entity | 表格引外部 |
| "接口吃 XML，实体解析看着没关" | hack-hub · xxe-xml-external-entity | 实体解析未关 |
| "报错回显了文件内容，解析器能读本地" | hack-hub · xxe-xml-external-entity | 报错回显文件 |

## 症状 → 社区技能（二、ctf-super-hub，经 ctf-hub 进入）

| 用户这样说 | 去这里 | 备注 |
|---|---|---|
| "题还没看明白，先把目标约束捋清楚再动手" | ctf-hub · 头脑风暴 | 动手前捋题 |
| "不知该用哪个工具，先理清思路再选路" | ctf-hub · 头脑风暴 | 理思路选路 |
| "一人一嘴方案乱了，先定个解法再分工" | ctf-hub · 头脑风暴 | 定解法分工 |
| "模型相关的题，对抗样本不知从哪下手" | ctf-hub · CTF•AI/ML 攻防 | 对抗样本起手 |
| "提示词注入的题，绕过姿势得备几个" | ctf-hub · CTF•AI/ML 攻防 | 注入绕过姿势 |
| "训练数据被下毒的题，中毒点怎么找" | ctf-hub · CTF•AI/ML 攻防 | 投毒点定位 |
| "刚入门不知先做哪类题，要个带路的" | ctf-hub · CTF•新手入口 | 新手带路；与 Strix•新手入口 二选一：连方向都没定，不知道是比赛题还是 Web 漏洞题、要先分流 → 本行；已确定做 Web 安全测试、只差选工具 → 016 |
| "题面都看不懂，先有人分诊再动手" | ctf-hub · CTF•新手入口 | 题面分诊；与 Strix•新手入口 二选一：连方向都没定，不知道是比赛题还是 Web 漏洞题、要先分流 → 本行；已确定做 Web 安全测试、只差选工具 → 016 |
| "工具链太多，先要个最小起手步骤" | ctf-hub · CTF•新手入口 | 最小起手；与 Strix•新手入口 二选一：连方向都没定，不知道是比赛题还是 Web 漏洞题、要先分流 → 本行；已确定做 Web 安全测试、只差选工具 → 016 |
| "给了公钥参数，弱密钥得挨个试" | ctf-hub · CTF•密码学 | 弱密钥试 |
| "格上的题，归约工具不会用" | ctf-hub · CTF•密码学 | 格归约工具 |
| "填充报错忽有忽无，预言机路子走走看" | ctf-hub · CTF•密码学 | 填充预言机 |
| "导了个内存镜像，坏东西藏哪得翻" | ctf-hub · CTF•数字取证 | 镜像翻坏东西；与 hack 侧 memory-forensics-volatility 二选一：手上是一整包混合材料（镜像/日志/PCAP/隐写/注册表）先分类 → 本行；手上只有内存转储要用 Volatility 跑 → 097 |
| "删掉的文件和凭据，还能捞回来不" | ctf-hub · CTF•数字取证 | 删物捞回；与 hack 侧 memory-forensics-volatility 二选一：手上是一整包混合材料（镜像/日志/PCAP/隐写/注册表）先分类 → 本行；手上只有内存转储要用 Volatility 跑 → 097 |
| "抓包里有 C2 的心跳，得提出来" | ctf-hub · CTF•数字取证 | 心跳提取；与 hack 侧 memory-forensics-volatility 二选一：手上是一整包混合材料（镜像/日志/PCAP/隐写/注册表）先分类 → 本行；手上只有内存转储要用 Volatility 跑 → 097 |
| "样本混淆得看不懂，行为先跑起来再说" | ctf-hub · CTF•恶意软件分析 | 混淆先跑行为 |
| "加密流量里藏着指令，得解出来" | ctf-hub · CTF•恶意软件分析 | 加密解指令 |
| "自启动和注入点埋哪了，得捋" | ctf-hub · CTF•恶意软件分析 | 启动注入捋 |
| "这题不像常规分类，编码奇奇怪怪" | ctf-hub · CTF•杂项 | 怪编码分类 |
| "沙箱笼子里的脚本，想让它跑出笼" | ctf-hub · CTF•杂项 | 笼 script 出逃 |
| "二维码和音频里藏答案的老套路，得走一遍" | ctf-hub · CTF•杂项 | 码音藏答案 |
| "就给了一张照片，人和地方得认出来" | ctf-hub · CTF•开源情报 | 看图认人地 |
| "用户名散得到处是，先把画像拼起来" | ctf-hub · CTF•开源情报 | 用户画像拼 |
| "历史快照里可能有删掉的东西，去翻翻" | ctf-hub · CTF•开源情报 | 快照翻删物 |
| "栈溢出的题，返回地址盖哪得算" | ctf-hub · CTF•二进制利用 | 盖址计算 |
| "堆题的利用链断了，缺临门一脚" | ctf-hub · CTF•二进制利用 | 堆链临门脚 |
| "沙箱把调用禁了大半，得找活路" | ctf-hub · CTF•二进制利用 | 禁调用找活路 |
| "二进制看不懂，虚拟机套壳了" | ctf-hub · CTF•逆向工程 | 虚拟套壳 |
| "APK 里的逻辑藏得深，反编译先走一遍" | ctf-hub · CTF•逆向工程 | APK 反编走 |
| "反调试缠住了，跟进去先清场" | ctf-hub · CTF•逆向工程 | 反调清场 |
| "不知做哪道题，先分个类再开工" | ctf-hub · CTF•超级总控 | 开工分类 |
| "综合题几类混一起，得排个顺序" | ctf-hub · CTF•超级总控 | 混题排序 |
| "边做边学，切换时机有人提醒" | ctf-hub · CTF•超级总控 | 切换提醒 |
| "登录绕过的题，注入和逻辑都得试" | ctf-hub · CTF•Web 漏洞 | 登录绕过试 |
| "文件上传的题，绕过姿势备几个" | ctf-hub · CTF•Web 漏洞 | 上传绕过姿势 |
| "令牌伪造的题，算法和声明都得看" | ctf-hub · CTF•Web 漏洞 | 令牌伪造看 |
| "打完比赛了，过程得写成能交的题解" | ctf-hub · CTF•题解写作 | 赛后写题解 |
| "解法散在聊天记录里，得收成复现文档" | ctf-hub · CTF•题解写作 | 聊天收复现 |
| "队友要复现，步骤得写到能跑通" | ctf-hub · CTF•题解写作 | 步骤写到跑通 |
| "一堆题不知先做哪个，先过一遍分分诊" | ctf-hub · CTF•挑战调度器 | 堆题分诊 |
| "类别看着像 Web，但又像逆向，得判一下" | ctf-hub · CTF•挑战调度器 | 类别判定 |
| "开局先轻量扫一圈，再定主攻" | ctf-hub · CTF•挑战调度器 | 开局轻扫 |
| "令牌改改就认了，测试手册先过一遍" | ctf-hub · Strix•JWT 身份认证测试 | 令牌测试手册 |
| "算法混淆那招，验一下认不认" | ctf-hub · Strix•JWT 身份认证测试 | 算法混淆验 |
| "声明里多写个身份，看看放不放行" | ctf-hub · Strix•JWT 身份认证测试 | 声明多写验 |
| "工具太多不知先用哪个，要个最小起手" | ctf-hub · Strix•新手入口 | 工具起手；与 CTF•新手入口 二选一：已确定做 Web 安全测试/漏洞验证，只是不知先用哪个 Strix 工具 → 本行；连分流方向都没定 → 003 |
| "刚接触 Web 测试，先给条不迷路的路" | ctf-hub · Strix•新手入口 | 新手不迷路；与 CTF•新手入口 二选一：已确定做 Web 安全测试/漏洞验证，只是不知先用哪个 Strix 工具 → 本行；连分流方向都没定 → 003 |
| "漏洞验证缺步骤，起手式来一个" | ctf-hub · Strix•新手入口 | 验证起手式；与 CTF•新手入口 二选一：已确定做 Web 安全测试/漏洞验证，只是不知先用哪个 Strix 工具 → 本行；连分流方向都没定 → 003 |
| "管理员功能普通号也能点，得验" | ctf-hub · Strix•功能级授权缺陷 | 普通号点管理；与 022 二选一：判据是「这个功能/接口换个身份还能不能被调」 → 本行（操作级）；判据是「某条记录换个身份还能不能读到」 → 022 |
| "操作接口换个身份还能调，得查" | ctf-hub · Strix•功能级授权缺陷 | 换身份调接口；与 022 二选一：判据是「这个功能/接口换个身份还能不能被调」 → 本行（操作级）；判据是「某条记录换个身份还能不能读到」 → 022 |
| "隐藏的管理端点，扫出来要验越权" | ctf-hub · Strix•功能级授权缺陷 | 藏端点验越权；与 022 二选一：判据是「这个功能/接口换个身份还能不能被调」 → 本行（操作级）；判据是「某条记录换个身份还能不能读到」 → 022 |
| "正常流程走完拿不到券，绕一步试试" | ctf-hub · Strix•业务逻辑漏洞 | 绕步拿券 |
| "状态机能跳步，约束没卡住" | ctf-hub · Strix•业务逻辑漏洞 | 跳步未卡 |
| "领域规则形同虚设，破坏一下看看" | ctf-hub · Strix•业务逻辑漏洞 | 规则破坏验 |
| "改资料的请求能被替发，令牌绕过测测" | ctf-hub · Strix•CSRF 测试 | 替发绕过测 |
| "跨站状态变更没人拦，得验" | ctf-hub · Strix•CSRF 测试 | 状态变更验 |
| "同站策略配得松，顺带把跨域也查了" | ctf-hub · Strix•CSRF 测试 | 同站跨域查 |
| "目录爆破参数不会调，抄个现成手册" | ctf-hub · Strix•ffuf 用法 | 爆破参数抄 |
| "匹配过滤写不对，结果里全是噪音" | ctf-hub · Strix•ffuf 用法 | 过滤降噪 |
| "自动化跑爆破，参数得稳" | ctf-hub · Strix•ffuf 用法 | 自动爆破稳参 |
| "存活探测命令拼不对，照手册来一条" | ctf-hub · Strix•httpx 用法 | 存活命令抄 |
| "探针输出格式乱，自动化吃不了" | ctf-hub · Strix•httpx 用法 | 输出格式调 |
| "批量探存活，参数给个省心的" | ctf-hub · Strix•httpx 用法 | 批量探省心 |
| "换个号就能看别人的数据，得验" | ctf-hub · Strix•IDOR 测试 | 换号看数据；与 017 二选一：判据是「某条记录换个身份还能不能读到」 → 本行（对象级）；判据是「这个功能/接口换个身份还能不能被调」 → 017 |
| "对象号挨个试，归属没验" | ctf-hub · Strix•IDOR 测试 | 挨试归属未验；与 017 二选一：判据是「某条记录换个身份还能不能读到」 → 本行（对象级）；判据是「这个功能/接口换个身份还能不能被调」 → 017 |
| "跨账户读了不该读的， boundary 补测" | ctf-hub · Strix•IDOR 测试 | 跨账户补测；与 017 二选一：判据是「某条记录换个身份还能不能读到」 → 本行（对象级）；判据是「这个功能/接口换个身份还能不能被调」 → 017 |
| "报错把栈和路径全吐了，得收" | ctf-hub · Strix•信息泄露测试 | 报错吐栈收 |
| "调试端点还开在外面，先关再说" | ctf-hub · Strix•信息泄露测试 | 调试端点关 |
| "源码映射文件能直接下，得验" | ctf-hub · Strix•信息泄露测试 | 映射文件下 |
| "头像上传改后缀能变脚本，得测" | ctf-hub · Strix•不安全文件上传 | 改后缀变脚本；与 hack 侧 upload-insecure-files 二选一：卡在扩展名、Content-Type、路径穿越这三处 → 本行；要查落盘路径、预览与处理管线、覆盖与上传转 RCE 链 → 128 |
| "上传类型只验了前端，后端照收" | ctf-hub · Strix•不安全文件上传 | 后端照收验；与 hack 侧 upload-insecure-files 二选一：卡在扩展名、Content-Type、路径穿越这三处 → 本行；要查落盘路径、预览与处理管线、覆盖与上传转 RCE 链 → 128 |
| "上传路径能跳目录，落点得控" | ctf-hub · Strix•不安全文件上传 | 跳目录控落点；与 hack 侧 upload-insecure-files 二选一：卡在扩展名、Content-Type、路径穿越这三处 → 本行；要查落盘路径、预览与处理管线、覆盖与上传转 RCE 链 → 128 |
| "爬虫深度不会控，一跑就炸" | ctf-hub · Strix•Katana 用法 | 深度控制 |
| "页面里的脚本链接爬不全，参数调调" | ctf-hub · Strix•Katana 用法 | 脚本链爬全 |
| "并发一高就被封，稳一点的参数来一个" | ctf-hub · Strix•Katana 用法 | 稳并发参数 |
| "模板扫出来一堆，不知先用哪个" | ctf-hub · Strix•Nuclei 用法 | 模板先用谁 |
| "高吞吐一开就被封，边界得控" | ctf-hub · Strix•Nuclei 用法 | 吞吐边界控 |
| "自动扫连着跑，命令给个能复用的" | ctf-hub · Strix•Nuclei 用法 | 复用扫命令 |
| "登录跳到了别人家，钓鱼能用" | ctf-hub · Strix•开放重定向 | 跳别家钓鱼；与 hack 侧 open-redirect 二选一：要的是钓鱼跳转、令牌窃取、白名单绕过的手法 → 本行；只是定位哪个参数/表单/JS 汇控制跳转 → 103 |
| "白名单写得松，变体能绕" | ctf-hub · Strix•开放重定向 | 白单松绕过；与 hack 侧 open-redirect 二选一：要的是钓鱼跳转、令牌窃取、白名单绕过的手法 → 本行；只是定位哪个参数/表单/JS 汇控制跳转 → 103 |
| "令牌跟着跳走了，得堵" | ctf-hub · Strix•开放重定向 | 令牌被带走堵；与 hack 侧 open-redirect 二选一：要的是钓鱼跳转、令牌窃取、白名单绕过的手法 → 本行；只是定位哪个参数/表单/JS 汇控制跳转 → 103 |
| "下载传个路径，系统文件出来了" | ctf-hub · Strix•路径穿越与文件包含 | 路径出系统文 |
| "包含点能指远端，代码执行链走走看" | ctf-hub · Strix•路径穿越与文件包含 | 远端包含执行 |
| "读文件到执行，还差一步" | ctf-hub · Strix•路径穿越与文件包含 | 读到执行差步 |
| "时间有限，先捡高危的打" | ctf-hub · Strix•快速扫描 | 限时捡高危 |
| "评估只有半天，模式切到最快" | ctf-hub · Strix•快速扫描 | 半天最快模式 |
| "先出高影响结论，覆盖以后再补" | ctf-hub · Strix•快速扫描 | 先高危后覆盖 |
| "输入进了命令执行，得做成稳的" | ctf-hub · Strix•远程代码执行 | 输入做稳执行 |
| "模板算了输入，执行链跟一下" | ctf-hub · Strix•远程代码执行 | 模板执行跟 |
| "反序列化点看着能打，验一下" | ctf-hub · Strix•远程代码执行 | 反序列可打验 |
| "登录框单引号反应不对，注入手册走一遍" | ctf-hub · Strix•SQL 注入 | 单引号走手册；与 hack 侧 sqli-sql-injection 二选一：要 union/盲注/报错/ORM 绕过的现成注入串 → 本行；要定位输入落到哪条查询、认证排序报表在哪 → 116 |
| "盲注睡几秒，手工跟一下" | ctf-hub · Strix•SQL 注入 | 盲注手工跟；与 hack 侧 sqli-sql-injection 二选一：要 union/盲注/报错/ORM 绕过的现成注入串 → 本行；要定位输入落到哪条查询、认证排序报表在哪 → 116 |
| "框架把注入藏起来了，绕过姿势换换" | ctf-hub · Strix•SQL 注入 | 框架藏注入绕；与 hack 侧 sqli-sql-injection 二选一：要 union/盲注/报错/ORM 绕过的现成注入串 → 本行；要定位输入落到哪条查询、认证排序报表在哪 → 116 |
| "注入命令拼不对，抄条能跑的" | ctf-hub · Strix•sqlmap 用法 | 抄条能跑 |
| "枚举库表，流程照手册走" | ctf-hub · Strix•sqlmap 用法 | 库表枚举走 |
| "无交互跑批，参数给稳的" | ctf-hub · Strix•sqlmap 用法 | 无交互稳参 |
| "填网址服务器去抓内网，测测" | ctf-hub · Strix•SSRF 测试 | 填址抓内网测；与 hack 侧 ssrf-server-side-request-forgery 二选一：靶场语境、要按手册拿云元数据与协议走私的具体打法 → 本行；生产侧排查服务器代取 URL、解析主机名 → 117 |
| "云身份地址能调，钥匙换换看" | ctf-hub · Strix•SSRF 测试 | 身份换钥看；与 hack 侧 ssrf-server-side-request-forgery 二选一：靶场语境、要按手册拿云元数据与协议走私的具体打法 → 本行；生产侧排查服务器代取 URL、解析主机名 → 117 |
| "协议玩出内网， smuggle 姿势试试" | ctf-hub · Strix•SSRF 测试 | 协议出内网试；与 hack 侧 ssrf-server-side-request-forgery 二选一：靶场语境、要按手册拿云元数据与协议走私的具体打法 → 本行；生产侧排查服务器代取 URL、解析主机名 → 117 |
| "时间够用，系统性扫一遍" | ctf-hub · Strix•标准扫描 | 系统扫一遍 |
| "覆盖和效率折中，标准模式走" | ctf-hub · Strix•标准扫描 | 折中标准走 |
| "全面但别太慢，平衡档来一个" | ctf-hub · Strix•标准扫描 | 平衡档 |
| "输入框弹窗存进去了，类型分分看" | ctf-hub · Strix•XSS 测试 | 弹窗类型分；与 hack 侧 xss-cross-site-scripting 二选一：要反射/存储/DOM 三类向量加 CSP 绕过的手法 → 本行；要定位可控内容落到哪个汇、多渲染上下文 → 137 |
| "参数进了脚本，载荷换换姿势" | ctf-hub · Strix•XSS 测试 | 载荷换姿势；与 hack 侧 xss-cross-site-scripting 二选一：要反射/存储/DOM 三类向量加 CSP 绕过的手法 → 本行；要定位可控内容落到哪个汇、多渲染上下文 → 137 |
| "策略拦了弹窗，绕过招备几个" | ctf-hub · Strix•XSS 测试 | 策略绕过备；与 hack 侧 xss-cross-site-scripting 二选一：要反射/存储/DOM 三类向量加 CSP 绕过的手法 → 本行；要定位可控内容落到哪个汇、多渲染上下文 → 137 |

## 症状 → 社区技能（三、ai-fullstack-delivery 代表性主题，经 delivery 进入）

| 用户这样说 | 去这里 | 备注 |
|---|---|---|
| "模型调好了，上线部署那套流程没人走过" | delivery · ai-deployment | 模型上线流程 |
| "线上问答想接大模型，对话链路不知怎么搭" | delivery · llm-integration | 对话链路搭建 |
| "改完模型效果是涨是掉，得有个评测数" | delivery · ml-evaluation | 效果涨掉评测 |
| "训练任务老是崩，数据和参数得捋捋" | delivery · model-training | 训练崩捋参 |
| "文档问答要联网查资料，检索链路怎么搭" | delivery · rag-pipeline | 检索问答搭建 |
| "登录鉴权那块，权限边界得先定下来" | delivery · auth-permission | 权限边界定 |
| "接口长啥样先定契约，前后端别打架" | delivery · endpoint-design | 契约先行 |
| "报错满天飞，失败重试得有个规矩" | delivery · error-handling | 失败重试规矩 |
| "重复请求下了两单，幂等得补上" | delivery · idempotency-retry | 重单补幂等 |
| "联调没后端，先整个假接口顶着" | delivery · openapi-mock | 假接口联调 |
| "列表翻页越翻越慢，筛选也卡" | delivery · pagination-filtering | 翻页筛选卡 |
| "流水线天天红，测试和集成先接起来" | delivery · ci-test-integration | 流水接测试 |
| "覆盖率多少算够，报告先跑出来" | delivery · coverage-reporting | 覆盖报告跑 |
| "端到端一跑就挂，场景得有人管" | delivery · e2e-testing | 端到端场景管 |
| "缓存一加上就脏读，策略得重定" | delivery · caching-strategy | 脏读重定策 |
| "慢查询拖垮页面，先抓出来" | delivery · query-review | 慢查询抓 |
| "表越加越多，结构得先设计好" | delivery · schema-design | 表结构设计 |
| "上线切流量怕炸，灰度步骤排一排" | delivery · release-strategy | 灰度切流量 |
| "半夜被告警吵醒，值班手册没有" | delivery · on-call-runbook | 值班手册补 |
| "事故复盘每次都忘，模板来一个" | delivery · postmortem | 复盘模板；与 retrospective 二选一：出的是线上 P1/P2 事故，要的是不追责的事故复盘 → 本行；是迭代/里程碑正常收尾 → 239 |
| "密钥直接写进代码了，得扫出来清掉" | delivery · auth-security-audit | 硬编码密钥扫 |
| "开源件版本一堆，哪个有洞得盘" | delivery · dependency-audit | 开源洞盘点 |
| "上线前威胁建模还没做，补一个" | delivery · threat-modeling | 上线前建模 |
| "发布说明每次现写，模板固定下" | delivery · release-notes | 发布说明模板 |
| "表单校验前后端两套，打架了" | delivery · forms-validation | 校验打架 |
| "页面状态到处飞，改崩了找不到源" | delivery · state-management | 状态源头找 |
| "首屏慢得离谱，性能得拆一拆" | delivery · performance-optimization | 首屏慢拆 |
| "需求排了一堆，先砍到最小能上" | delivery · mvp-scoping | 最小能上砍 |
| "排期天天变，关键路径先算出来" | delivery · critical-path | 关键路径算 |
| "事故复盘会开成甩锅会，流程正一正" | delivery · retrospective | 复盘正流程；与 postmortem 二选一：迭代、里程碑、项目或季度正常收尾 → 本行；出的是线上事故要事故复盘 → 269 |

## 症状 → 社区技能（四、apk-reverse-community，经 apk-extension 进入）

| 用户这样说 | 去这里 | 备注 |
|---|---|---|
| "想把这个应用里的开屏广告和弹窗去掉，自己打包一个干净的装上" | apk-extension · apk-reverse | 去广告重打包 |
| "应用的安装包想拆开看看，顺带把多余的东西清掉" | apk-extension · apk-reverse | 拆包清多余 |
| "改完装不上，签名那步卡住了" | apk-extension · apk-reverse | 改后签名卡 |
| "服务器那边的接口也得探探，光改客户端不够" | apk-extension · apk-reverse | 服务端探接口 |
| "改完重新打出来的包，系统说解析不了，格式好像不对" | apk-extension · apk-reverse | R49 域｜改后重打包格式不对 |
| "想把某个统计上报的 SDK 从包里摘干净，摘完一启动就崩" | apk-extension · apk-reverse | R49 域｜摘 SDK 后启动崩 |
| "想让它别连我们自家的服务，换成我自己签的那一份" | apk-extension · apk-reverse | R49 域｜换签名组件改指向 |
| "包体太大装得慢，想把没用的资源和图都裁掉" | apk-extension · apk-reverse | R49 域｜资源瘦身 |
| "一个人只能开一份，想同时跑好几个互不干扰" | apk-extension · apk-reverse | R49 域｜能力矩阵改写多开 |
| "一改完它就自己退出，像是发现被动过" | apk-extension · apk-reverse | R1 域｜自校验退出属运行时反篡改 |
| "装上就提示风险不让继续，换机器也一样" | apk-extension · apk-reverse | R1 域｜装不上被拦属设备环境检测 |
| "它一启动就连了某个地址，想看清楚连的什么" | apk-extension · apk-reverse | R1 域｜启动外联行为在运行时层 |
| "后台莫名被另一个应用拉起来，想知道是谁干的" | apk-extension · apk-reverse | R1 域｜进程拉起来源属运行时层 |
| "抓包抓不到，证书好像被钉死了" | apk-extension · apk-reverse | R1 域｜证书钉定属传输层 |
| "想给某个函数挂钩子，看它运行时到底干了什么" | apk-extension · apk-reverse | R1 域｜函数挂钩属动态分析 |

_831 row(s) below the header. Every row's target names an existing community skill reachable via its wrapper SKILL.md (hack-hub / ctf-hub / delivery / apk-extension); no relative links are used in this file._

## 症状 → 社区技能（三补、ai-fullstack-delivery 剩余技能，经 delivery 进入）

| 用户这样说 | 去这里 | 备注 |
|---|---|---|
| "模型从训练到上线整套没人带，得捋一遍" | delivery · ai-ml-engineer-skills-index | 模型整套带 |
| "智能功能要从零搭，算法到部署缺整套" | delivery · ai-ml-engineer-skills-index | 算法上线串 |
| "模型效果和上线两头顾，得有人统管" | delivery · ai-ml-engineer-skills-index | 效果上线管 |
| "接口出入参字段老对不上，规则得先定死" | delivery · request-response | 字段规则定 |
| "返回结构每次都变，前端接得想骂人" | delivery · request-response | 返回结构稳 |
| "字段命名乱成一锅粥，校验也缺一块" | delivery · request-response | 命名校验补 |
| "业务对象不知怎么拆成资源，粒度定不下" | delivery · resource-modeling | 资源粒度定 |
| "订单和子单挂哪一层，关系捋不清" | delivery · resource-modeling | 层级关系捋 |
| "接口第一步就卡住，对象抽象不出来" | delivery · resource-modeling | 对象抽象化 |
| "接口整套设计没人把关，风格各写各的" | delivery · api-designer-skills-index | 接口风格统 |
| "从建模到版本一整套，得有人统一下" | delivery · api-designer-skills-index | 建模版本串 |
| "开放接口要长期维护，设计得成体系" | delivery · api-designer-skills-index | 长期成体系 |
| "接口一改老客户端就炸，兼容得想好" | delivery · versioning | 改动兼容保 |
| "开放平台要升级，弃用节奏定不下来" | delivery · versioning | 弃用节奏定 |
| "第三方对接老是断，平滑过渡没人排" | delivery · versioning | 平滑过渡排 |
| "支付成功后通知老丢，重试没人做" | delivery · webhook-async | 通知重试补 |
| "导出报表要等半天，异步链路没搭" | delivery · webhook-async | 异步链路搭 |
| "第三方回调验签没做，重复推就重单" | delivery · webhook-async | 验签去重做 |
| "前后端各说各的，联调天天对不上" | delivery · api-contract-testing | 联调对齐卡 |
| "接口一改就崩别人，缺个契约卡一下" | delivery · api-contract-testing | 改动契约卡 |
| "微服务互相调，一升级就断链" | delivery · api-contract-testing | 服务断链防 |
| "单测都过，一连库调接口就挂" | delivery · integration-testing | 连库调挂查 |
| "第三方接口不敢动，一动就炸" | delivery · integration-testing | 三方不敢动 |
| "消息和缓存混在一起，联调没覆盖" | delivery · integration-testing | 消息缓存盖 |
| "回归全靠人点，版本一多就漏" | delivery · automation-qa-skills-index | 人点回归漏 |
| "测试想成体系，单测到集成缺规划" | delivery · automation-qa-skills-index | 测试成体系 |
| "每次上线都心慌，自动化没搭起来" | delivery · automation-qa-skills-index | 上线心慌治 |
| "工具函数没单测，一改就心慌" | delivery · unit-testing | 函数单测补 |
| "分支逻辑绕来绕去，缺用例兜住" | delivery · unit-testing | 分支用例兜 |
| "状态和纯函数得补测试，不然不敢重构" | delivery · unit-testing | 不敢重构保 |
| "契约文档有了，落成代码没人写" | delivery · api-implementation | 契约落代码 |
| "参数校验和返回组装，各人写法不一" | delivery · api-implementation | 校验组装统 |
| "多框架混着用，分层得统一一下" | delivery · api-implementation | 分层统一管 |
| "发邮件报表卡住主流程，得拆出去" | delivery · async-jobs | 主流程拆分 |
| "任务一多就堆积，重试死信没做" | delivery · async-jobs | 堆积重试补 |
| "定时任务满天飞，失败了没人知" | delivery · async-jobs | 定时失败知 |
| "登录注册刚搭，令牌和权限没接好" | delivery · auth-implementation | 令牌权限接 |
| "不同角色看不同字段，鉴权漏了一块" | delivery · auth-implementation | 角色字段鉴 |
| "社交登录接进来，会话管理乱了" | delivery · auth-implementation | 会话管理理 |
| "代码风格各写各的，评审没标准" | delivery · code-quality | 评审标准立 |
| "坏味道越堆越多，重构不敢下手" | delivery · code-quality | 坏味重构治 |
| "扫描和规范没接，烂代码往上堆" | delivery · code-quality | 扫描规范接 |
| "列表一翻就慢，疑似查出连环套" | delivery · data-access | 翻页慢查治 |
| "事务边界不清，写一半就脏数" | delivery · data-access | 事务边界清 |
| "多数据源读写，仓储层得理理" | delivery · data-access | 仓储层理顺 |
| "订单审批状态满天飞，流转没收拢" | delivery · domain-modeling | 状态流转收 |
| "业务逻辑散在各层，改一处崩三处" | delivery · domain-modeling | 逻辑散落收 |
| "对象只有数据没行为，规则没处放" | delivery · domain-modeling | 行为规则放 |
| "上游一挂跟着挂，隔离熔断没做" | delivery · error-handling-resilience | 隔离熔断补 |
| "重试没规矩，把下游打得更惨" | delivery · error-handling-resilience | 重试规矩立 |
| "报错直接抛给用户，降级没人写" | delivery · error-handling-resilience | 降级兜底写 |
| "单体越长越大，不知从哪下刀拆" | delivery · microservice-design | 单体下刀拆 |
| "服务间调法不一，网关也没人管" | delivery · microservice-design | 调法网关管 |
| "新项目要拆微服务，通信选型定不下" | delivery · microservice-design | 通信选型定 |
| "线上出问题只能猜，日志链路接不上" | delivery · observability | 日志链路接 |
| "慢在哪看不见，指标和追踪缺一块" | delivery · observability | 慢点追踪补 |
| "报错靠用户截图，监控告警没响过" | delivery · observability | 告警没响修 |
| "后端从接口到容错整套缺人带" | delivery · backend-engineer-skills-index | 后端整套带 |
| "新服务要搭架子，分层测试没人定" | delivery · backend-engineer-skills-index | 架子分层定 |
| "业务要快速落地，后端一整套得捋" | delivery · backend-engineer-skills-index | 快速落地捋 |

| "测试只有单测，集成和契约是空白" | delivery · testing-implementation | 集成契约补 |
| "外部依赖掐不住，替身不会造" | delivery · testing-implementation | 依赖替身造 |
| "关键路径没人保，测试数据也乱" | delivery · testing-implementation | 路径数据保 |
| "新功能上线不知好不好，得对照验一把" | delivery · ab-testing | 对照验一把 |
| "改版后转化是涨是跌，缺个数说话" | delivery · ab-testing | 涨跌个数说 |
| "两套推荐并跑，哪个强得比比" | delivery · ab-testing | 并跑比强弱 |
| "周报只有数字，结论和建议写不出" | delivery · analysis-report | 结论建议写 |
| "流失转化做了分析，落不成决策" | delivery · analysis-report | 分析落决策 |
| "实验做完没结论，报告得有人收口" | delivery · analysis-report | 实验收口报 |
| "仪表盘堆了一堆图，看不出重点" | delivery · data-visualization | 堆图看重点 |
| "图表选型全靠猜，老板看不懂" | delivery · data-visualization | 选型看得懂 |
| "实时面板要搭，布局没人设计" | delivery · data-visualization | 面板布局设 |
| "指标口径各算各的，对不上账" | delivery · metric-design | 口径对账统 |
| "北极星定不下来，团队各忙各的" | delivery · metric-design | 北极星定下 |
| "漏斗口径没统一，增长无从谈" | delivery · metric-design | 漏斗口径统 |
| "数据分析从取数到报告缺整套" | delivery · data-analyst-skills-index | 取数报告串 |
| "业务要看数，指标到可视化没人串" | delivery · data-analyst-skills-index | 指标可视串 |
| "分析零散不成体系，得成套带" | delivery · data-analyst-skills-index | 零散成套带 |
| "漏斗留存要数，查询写得直冒烟" | delivery · sql-analysis | 查询冒烟优 |
| "同比环比和排名，语句越写越慢" | delivery · sql-analysis | 语句越写慢 |
| "层级链路要扒，递归不会写" | delivery · sql-analysis | 链路递归写 |
| "多租户数据串了，隔离没做好" | delivery · consistency-multitenancy | 串数隔离做 |
| "并发一高就写重，幂等锁没加" | delivery · consistency-multitenancy | 写重幂等加 |
| "软删归档审计缺一块，数据没法管" | delivery · consistency-multitenancy | 归档审计补 |
| "线上改表手抖，缺个上线前清单" | delivery · data-operations-safety | 改表清单列 |
| "批量修数不敢跑，怕把生产洗了" | delivery · data-operations-safety | 修数不敢跑 |
| "备份没验过，真炸了不知能否回" | delivery · data-operations-safety | 备份验恢复 |
| "筛选排序一多就慢，索引不知咋建" | delivery · index-access-pattern | 索引咋建定 |
| "新表上线没评估，索引全靠蒙" | delivery · index-access-pattern | 新表评估做 |
| "大表加索引怕锁死，在线方案没人给" | delivery · index-access-pattern | 在线加索引 |
| "大表加字段回填，步骤不敢定" | delivery · migration-rollout | 回填步骤定 |
| "拆库合库要搬数，回滚没人写" | delivery · migration-rollout | 搬数回滚写 |
| "新旧字段切换，兼容窗口排不出" | delivery · migration-rollout | 兼容窗口排 |
| "库端从建模到上线缺整套人带" | delivery · database-engineer-skills-index | 库端整套带 |
| "表越加越多，库端规范没人定" | delivery · database-engineer-skills-index | 库端规范立 |
| "数据变更全靠胆，库端体系得补" | delivery · database-engineer-skills-index | 变更体系补 |
| "上线全靠人肉打包，流水线没搭" | delivery · ci-cd-pipeline | 人肉打包改 |
| "多环境发布老串，门禁也没人加" | delivery · ci-cd-pipeline | 发布门禁加 |
| "构建慢得离谱，流水得优化" | delivery · ci-cd-pipeline | 构建慢优化 |
| "服务上容器，编排文件没人写" | delivery · container-orchestration | 编排文件写 |
| "本地能跑线上起不来，镜像有问题" | delivery · container-orchestration | 线上起不来 |
| "多服务联调起不来，编排得理理" | delivery · container-orchestration | 联调编排理 |
| "镜像大到离谱，构建慢还费钱" | delivery · containerization | 镜像大瘦身 |
| "容器跑在高权限，老是被扫出洞" | delivery · containerization | 高权扫洞治 |
| "老应用要搬容器，第一步不知咋走" | delivery · containerization | 搬容器起步 |
| "环境靠人点控制台，迟早点炸" | delivery · infrastructure-as-code | 点控制台改 |
| "三套环境各长各样，对都对不上" | delivery · infrastructure-as-code | 环境对不上 |
| "灾备重建没脚本，出事只能干瞪眼" | delivery · infrastructure-as-code | 重建脚本补 |
| "服务搬上集群，配置写不明白" | delivery · kubernetes-orchestration | 集群配置写 |
| "流量一高就崩，伸缩没配" | delivery · kubernetes-orchestration | 伸缩没配补 |
| "发布一滚就全挂，高可用缺一块" | delivery · kubernetes-orchestration | 高可用补块 |
| "半夜挂了没人知道，天亮才发现" | delivery · monitoring-alerting | 半夜挂不知 |
| "告警要么不响要么乱响，规则得调" | delivery · monitoring-alerting | 告警规则调 |
| "面板东一块西一块，值班没法看" | delivery · monitoring-alerting | 面板值班看 |
| "域名一堆，流量不知往哪转" | delivery · networking-gateway | 流量往哪转 |
| "证书老是过期，续期靠人记" | delivery · networking-gateway | 证书续期管 |
| "网关限流没做，一冲就全倒" | delivery · networking-gateway | 限流没做补 |
| "密码全写死在代码里，轮换不敢动" | delivery · secrets-config | 写死轮换改 |
| "多环境配置混一起，上线老串" | delivery · secrets-config | 配置混串治 |
| "密钥没人管，泄露了都不知道" | delivery · secrets-config | 泄露不知治 |

| "从构建到监控整套没人串起来" | delivery · devops-engineer-skills-index | 构建监控串 |
| "上线运维全靠吼，体系得搭" | delivery · devops-engineer-skills-index | 全靠吼改制 |
| "新项目要交付，运维一整套缺人" | delivery · devops-engineer-skills-index | 交付缺整套 |
| "键盘走不完表单，焦点乱跳" | delivery · accessibility-implementation | 焦点乱跳治 |
| "读屏软件一读就乱，标签没打好" | delivery · accessibility-implementation | 标签打好补 |
| "对比度和点击区太小，有人用不了" | delivery · accessibility-implementation | 点击区改大 |
| "本地能跑打包就炸，环境没对齐" | delivery · build-deploy | 打包炸对齐 |
| "包越打越大，首屏等到睡着" | delivery · build-deploy | 包大首屏慢 |
| "发版靠手动传文件，回滚全靠运气" | delivery · build-deploy | 手动发版改 |
| "页面越写越臃肿，拆分下不去手" | delivery · component-architecture | 臃肿拆分下；与 atomic-design 二选一：单个框架里组件结构、拆分粒度、容器/展示拆分与复合式用法 → 本行；要分层模型与组件库建设 → 279 |
| "同样组件到处复制，改崩好几处" | delivery · component-architecture | 复制改崩治；与 atomic-design 二选一：单个框架里组件结构、拆分粒度、容器/展示拆分与复合式用法 → 本行；要分层模型与组件库建设 → 279 |
| "组件接口各写各的，复用不起来" | delivery · component-architecture | 接口复用统；与 atomic-design 二选一：单个框架里组件结构、拆分粒度、容器/展示拆分与复合式用法 → 本行；要分层模型与组件库建设 → 279 |
| "列表加载转半天，缓存没做" | delivery · data-fetching | 加载缓存做 |
| "翻页和搜索一接就乱，状态兜不住" | delivery · data-fetching | 翻页状态兜 |
| "改完要等刷新，乐观更新没人写" | delivery · data-fetching | 乐观更新写 |
| "小程序要上三端，一套代码不知咋发" | delivery · miniprogram-development | 三端咋发定 |
| "小程序和网页跳来跳去，互通没做" | delivery · miniprogram-development | 跳转互通做 |
| "小程序越写越卡，优化没思路" | delivery · miniprogram-development | 越写越卡优 |
| "要做手机两端，人手只够一套代码" | delivery · mobile-hybrid | 两端一套码 |
| "跨端方案挑花眼，选型定不下" | delivery · mobile-hybrid | 方案选型定 |
| "原生功能调不通，桥接卡住了" | delivery · mobile-hybrid | 桥接卡住通 |
| "页面一多路由就乱，嵌套没人理" | delivery · routing-navigation | 路由嵌套理 |
| "没登录也能进后台，守卫漏了" | delivery · routing-navigation | 守卫漏补上 |
| "首屏全量加载，懒加载没拆" | delivery · routing-navigation | 懒加载拆分 |
| "前端从组件到发布缺整套人带" | delivery · frontend-engineer-skills-index | 前端整套带 |
| "新项目要起架子，规范没人定" | delivery · frontend-engineer-skills-index | 架子规范定 |
| "页面越堆越多，前端体系得理" | delivery · frontend-engineer-skills-index | 体系得理顺 |
| "亮暗切换要加，样式全写死了" | delivery · styling-system | 写死切换加 |
| "屏幕一换就错位，适配没人管" | delivery · styling-system | 错位适配管 |
| "样式到处复制，主题改不动" | delivery · styling-system | 复制主题改 |
| "组件点来点去没断言，行为没兜住" | delivery · testing-frontend | 行为兜底测 |
| "关键旅程没人走一遍，上线靠肉眼" | delivery · testing-frontend | 旅程肉眼改 |
| "样式一改就崩别处，回归没接住" | delivery · testing-frontend | 改崩回归接 |
| "假接口换真接口，一接就全红" | delivery · api-frontend-integration | 换真全红调 |
| "字段对不上，提示也乱套" | delivery · api-frontend-integration | 字段提示对 |
| "上传分页调不通，联调卡住了" | delivery · api-frontend-integration | 联调卡住通 |
| "注册登录权限串不起来，前后各一半" | delivery · auth-e2e | 串不起来接 |
| "第三方登录接进来，整链没调通" | delivery · auth-e2e | 整链调通接 |
| "前守卫后中间件，两头对不上" | delivery · auth-e2e | 两头对上接 |
| "新功能要建表，结构和迁移没人写" | delivery · database-schema-impl | 建表迁移写 |
| "种子数据没有，本地跑不起来" | delivery · database-schema-impl | 种子跑起来 |
| "索引缺一块，埋下慢查询雷" | delivery · database-schema-impl | 慢查雷排掉 |
| "每个改动想先看效果，预览环境没有" | delivery · deploy-preview | 改动预览看 |
| "小工具要快上，部署流程太重" | delivery · deploy-preview | 快上流程轻 |
| "演示环境老是挂，临时看都看不了" | delivery · deploy-preview | 演示挂修稳 |
| "小需求想一人干完，前后端来回扯" | delivery · e2e-feature-delivery | 一人干完链 |
| "内部工具要快做，人手不够" | delivery · e2e-feature-delivery | 快做人手补 |
| "从库到页整条链，缺人一杆到底" | delivery · e2e-feature-delivery | 整链一杆底 |
| "新项目选啥栈，吵了三天没定" | delivery · fullstack-architecture | 选栈吵定下 |
| "单仓还是分仓，一步走错后悔半年" | delivery · fullstack-architecture | 分仓决策定 |
| "起手模板没有，每次从零搭" | delivery · fullstack-architecture | 模板从零改 |
| "前后库部署一整套，缺人统管" | delivery · fullstack-engineer-skills-index | 整套统管带 |
| "小团队要全栈交付，链路没人串" | delivery · fullstack-engineer-skills-index | 链路串起来 |
| "项目从零到上线，全栈缺个主心骨" | delivery · fullstack-engineer-skills-index | 缺主心骨带 |
| "用户全流程走一遍，卡点捋不清" | delivery · customer-journey | 卡点捋不清 |
| "各部门各说各话，对齐缺张图" | delivery · customer-journey | 对齐缺图补 |
| "新功能从哪下手，得先看旅程" | delivery · customer-journey | 下手看旅程 |
| "功能算不算成，无数量化" | delivery · heart-metrics | 成败量化定 |
| "上线后效果咋样，复盘没依据" | delivery · heart-metrics | 复盘依据补 |
| "季度总结要数，口径没人定" | delivery · heart-metrics | 口径定数出 |

## 症状 → 社区技能（四补、ai-fullstack-delivery 剩余 64 技能，经 delivery 进入）

| 用户这样说 | 去这里 | 备注 |
|---|---|---|
| "目标定了，做啥功能还没影" | delivery · opportunity-tree | 功能还没影 |
| "几个方向都想要，不知砍哪个" | delivery · opportunity-tree | 方向砍不定 |
| "大家说的痛点各不一样，对不上" | delivery · opportunity-tree | 痛点对不上 |
| "有个想法，不知用户买不买账" | delivery · pol-probe | 买账先验验 |
| "大投入前想先小步试一把" | delivery · pol-probe | 小步先试错 |
| "方案好几个，先验哪个拿不准" | delivery · pol-probe | 先验拿不准 |
| "新产品一句话说不清是干啥的" | delivery · positioning | 说不清干啥 |
| "见人就得重新解释产品，太累了" | delivery · positioning | 解释太累人 |
| "团队对方向各说各话，得定个调" | delivery · positioning | 方向定个调 |
| "大版本为啥做，问三人三个说法" | delivery · pr-faq | 说法不统一 |
| "给高层讲愿景，总讲不到一块" | delivery · pr-faq | 愿景讲不拢 |
| "做了半年，回头看初心都散了" | delivery · pr-faq | 初心散了形 |
| "功能要开工，需求还只是几句话" | delivery · prd-writing | 需求几句话 |
| "评审总被问住，文档缺一块" | delivery · prd-writing | 文档缺一块 |
| "口头定的事，转头就不认了" | delivery · prd-writing | 口头不认账 |
| "待办堆成山，先做哪个吵翻天" | delivery · prioritization | 先做吵翻天 |
| "五十个想法，季度只能做十个" | delivery · prioritization | 五十选十难 |
| "都说自己的急，排序没人服" | delivery · prioritization | 排序没人服 |
| "下季度做啥，团队心里都没谱" | delivery · roadmap | 下季没谱气 |
| "功能一大堆，先后顺序排不出" | delivery · roadmap | 先后排不出 |
| "对外讲方向，缺张拿得出手的图" | delivery · roadmap | 缺张方向图 |
| "功能永远做不完，延期成常态" | delivery · shape-up | 延期成常态 |
| "排期估了个寂寞，上线总跳票" | delivery · shape-up | 上线总跳票 |
| "范围天天膨胀，得有个框框住" | delivery · shape-up | 范围框框住 |
| "产品从想法到落地缺人全程带" | delivery · product-manager-skills-index | 想法落地带 |
| "需求文档评审排期，一整套没人管" | delivery · product-manager-skills-index | 整套没人管 |
| "新产品从零起盘，得有人统全局" | delivery · product-manager-skills-index | 起盘统全局 |
| "大功能拆不细，开发不知咋下手" | delivery · user-story | 拆不细下手 |
| "做完算不算完，验收没个准绳" | delivery · user-story | 验收没准绳 |
| "故事写得太粗，联调天天返工" | delivery · user-story | 写粗天天返 |
| "做到一半加需求，排期全被打乱" | delivery · change-control | 加单打乱排 |
| "上游一改，下游跟着返工" | delivery · change-control | 上改下返工 |
| "中途变卦没规矩，团队天天救火" | delivery · change-control | 变卦天天救 |
| "团队快不快，全凭感觉在吵" | delivery · dora-metrics | 快慢凭感觉 |
| "季度复盘没数，改进无从谈起" | delivery · dora-metrics | 复盘没数谈 |
| "交付能力到底行不行，得量一量" | delivery · dora-metrics | 能力量一量 |
| "设计转开发总丢东西，天天补坑" | delivery · handoff-protocol | 交接天天补 |
| "交接靠口头，接过来全是坑" | delivery · handoff-protocol | 口头全是坑 |
| "跨阶段一交接，质量就掉一截" | delivery · handoff-protocol | 质量掉一截 |
| "阶段过没过，全凭领导一句话" | delivery · milestone-gate | 过凭一句话 |
| "上线前没人拍板，心里没底" | delivery · milestone-gate | 没人拍板慌 |
| "关键节点要不要过，缺个说法" | delivery · milestone-gate | 过缺个说法 |
| "项目和战略对上没，全靠猜" | delivery · okr-alignment | 对上全靠猜 |
| "为啥做这个，各部门讲法不一" | delivery · okr-alignment | 讲法不统一 |
| "排了一堆事，不知哪个真重要" | delivery · okr-alignment | 真重要难辨 |
| "几件事谁先谁后，搅成一团" | delivery · orchestration | 先后搅成团 |
| "多线并行互相等，卡住没人排" | delivery · orchestration | 互等没人排 |
| "计划赶不上变化，调度全靠吼" | delivery · orchestration | 调度全靠吼 |
| "进度全靠问，问完还是不清楚" | delivery · progress-tracking | 问完不清楚 |
| "卡住了没人报，爆雷才知道" | delivery · progress-tracking | 爆雷才知道 |
| "周会一问三不知，状态全是黑盒" | delivery · progress-tracking | 状态全黑盒 |
| "开工没盘过风险，走一步看一步" | delivery · risk-management | 走一步看步 |
| "评审只看进度，隐患没人提" | delivery · risk-management | 隐患没人提 |
| "一出事就抓瞎，早没人预警" | delivery · risk-management | 早没人预警 |
| "迭代拖拖拉拉，节奏带不起来" | delivery · shape-up-cycles | 节奏带不起 |
| "估时永远不准，计划总落空" | delivery · shape-up-cycles | 计划总落空 |
| "想要固定节奏出活，缺个章法" | delivery · shape-up-cycles | 出活缺章法 |
| "项目从开工到上线缺人总抓" | delivery · project-manager-skills-index | 开工缺总抓 |
| "多角色协作乱成粥，得有人串" | delivery · project-manager-skills-index | 乱成粥得串 |
| "排期风险交付，一整套没人管" | delivery · project-manager-skills-index | 整套没人管 |

| "需求一大坨，不知从哪下刀拆" | delivery · wbs-decomposition | 下刀拆分难 |
| "排期总拍脑袋，任务没拆细" | delivery · wbs-decomposition | 拍脑袋排期 |
| "大活分不下去，卡在第一步" | delivery · wbs-decomposition | 分解卡首步 |
| "开发说做完了，业务不认账" | delivery · acceptance-testing | 做完不认账 |
| "上线前没人点头，不敢发版" | delivery · acceptance-testing | 没人点头慌 |
| "客户演示前，心里一点底没有" | delivery · acceptance-testing | 演示心里虚 |
| "接口改个字段，前端全炸了" | delivery · api-testing | 改字段全炸 |
| "权限测没测全，心里没底" | delivery · api-testing | 权限没测全 |
| "并发一高就重单，幂等没验过" | delivery · api-testing | 幂等没验过 |
| "口头报的错，转头没人认" | delivery · bug-reporting | 口头没人认 |
| "复现步骤说不清，开发直摇头" | delivery · bug-reporting | 复现说不清 |
| "修完算不算好，缺个闭环" | delivery · bug-reporting | 缺个闭环跟 |
| "用例写不全，心里总不踏实" | delivery · exploratory-testing | 写不全不实 |
| "重构完功能看着对，不敢打包票" | delivery · exploratory-testing | 不敢打包票 |
| "上线前想再扫一遍，怕有漏网" | delivery · exploratory-testing | 怕有漏网鱼 |
| "大促前心里虚，不知能扛多少" | delivery · performance-testing | 不知扛多少 |
| "版本越更越慢，慢在哪没人说" | delivery · performance-testing | 慢在哪不明 |
| "机器要加多少，全凭感觉拍" | delivery · performance-testing | 加机凭感觉 |
| "发不发版靠吵架，缺个硬标准" | delivery · quality-gate | 发版靠吵架 |
| "流水线想设道闸，不知卡什么" | delivery · quality-gate | 设闸不知卡 |
| "紧急修复走啥通道，没人说得清" | delivery · quality-gate | 通道说不清 |
| "修一个崩三个，每次上线心慌" | delivery · regression-testing | 修崩上线慌 |
| "依赖升个版，不知会炸哪里" | delivery · regression-testing | 升级炸哪里 |
| "改配置就手抖，怕牵一发动全身" | delivery · regression-testing | 手抖怕牵连 |
| "时间不够全测，先保哪块拿不准" | delivery · risk-based-testing | 先保拿不准 |
| "没测到的地方，风险有多大" | delivery · risk-based-testing | 未测风险估 |
| "紧急上线测多深，心里没谱" | delivery · risk-based-testing | 测深没谱气 |
| "测试从策略到报告缺人整套带" | delivery · qa-engineer-skills-index | 策略报告带 |
| "新模块测多深，没人拍得了板" | delivery · qa-engineer-skills-index | 测深没人拍 |
| "手工自动两拨人，边界分不清" | delivery · qa-engineer-skills-index | 边界分不清 |
| "功能测了还漏，场景没想全" | delivery · test-case-design | 场景没想全 |
| "表单分支绕来绕去，测不全" | delivery · test-case-design | 分支测不全 |
| "回归用例越堆越多，不知留啥" | delivery · test-case-design | 用例不知留 |
| "造点测试数据，比开发还费劲" | delivery · test-data-management | 造数真费劲 |
| "线上数据不敢用，脱敏没人做" | delivery · test-data-management | 脱敏没人做 |
| "环境数据串来串去，越测越乱" | delivery · test-data-management | 数据串越乱 |
| "测完没个总结，发版没人敢拍板" | delivery · test-report | 总结没人拍 |
| "缺陷一堆，老板问不清大局" | delivery · test-report | 大局问不清 |
| "到底能不能上，缺句话定心" | delivery · test-report | 缺句定心话 |
| "新模块从哪测起，全无章法" | delivery · test-strategy | 从哪测无章 |
| "时间紧任务重，取舍没人定" | delivery · test-strategy | 取舍没人定 |
| "啥该自动啥该手拿，分不清" | delivery · test-strategy | 手自难分清 |
| "合码只看功能，安全没人扫一眼" | delivery · code-security-review | 安全没人扫 |
| "新引的包安不安全，没人评估" | delivery · code-security-review | 引包没评估 |
| "敏感操作混在代码里，没人审" | delivery · code-security-review | 敏感没人审 |
| "漏扫出一堆，不知先堵哪个" | delivery · security-report | 先堵拿不准 |
| "合规要材料，临时抱佛脚" | delivery · security-report | 临时抱佛脚 |
| "修没修完没人跟，漏洞一直挂着" | delivery · security-report | 漏洞一直挂 |
| "安全从代码到上线缺人整套看" | delivery · security-engineer-skills-index | 代码上线看 |
| "评审扫描应急，散在各处没人统" | delivery · security-engineer-skills-index | 散落没人统 |
| "新业务要上线，安全缺个把关的" | delivery · security-engineer-skills-index | 缺个把关人 |
| "引的包有没有雷，全靠运气" | delivery · supply-chain-security | 有雷靠运气 |
| "镜像里带了啥漏洞，没人扫过" | delivery · supply-chain-security | 镜像没人扫 |
| "流水线被人动手脚都不知道" | delivery · supply-chain-security | 动手脚不知 |
| "输入框直接拼语句，心里发毛" | delivery · web-vulnerability | 输入心里毛 |
| "上传口没人看，啥都能传上去" | delivery · web-vulnerability | 上传没人看 |
| "页面弹过奇怪脚本，不知哪漏的" | delivery · web-vulnerability | 不知哪漏了 |
| "大促机器备多少，心里没数" | delivery · capacity-planning | 备机没数气 |
| "平时空转烧钱，高峰又扛不住" | delivery · capacity-planning | 空转又扛住 |
| "新服务要多少资源，估不出来" | delivery · capacity-planning | 资源估不出 |

| "服务挂了半天，群里才有人吭声" | delivery · incident-response | 挂半天吭声 |
| "一出故障就乱套，没人知道先干啥" | delivery · incident-response | 乱套不知先 |
| "第三方挂了跟着挂，预案一张没有" | delivery · incident-response | 预案一张无 |
| "线上报错一堆，不知从哪查起" | delivery · log-analysis | 不知从哪查 |
| "慢请求偶发出现，抓不到现场" | delivery · log-analysis | 抓不到现场 |
| "日志满天飞，出事捞不到关键" | delivery · log-analysis | 捞不到关键 |
| "可用性目标喊了等于没喊" | delivery · reliability-engineering | 目标等于喊 |
| "故障演练从没搞过，真出事抓瞎" | delivery · reliability-engineering | 从没搞演练 |
| "容灾就是摆设，切不切没人知道" | delivery · reliability-engineering | 摆设不知切 |
| "运维救火到上线缺人整套扛" | delivery · sre-operations-skills-index | 救火缺整扛 |
| "半夜告警靠人肉，没人值守" | delivery · sre-operations-skills-index | 人肉没值守 |
| "稳定性没人背，出事才有人问" | delivery · sre-operations-skills-index | 没人背稳定 |
| "对接靠猜参数，文档还是上版的" | delivery · api-documentation | 猜参上版档 |
| "错误码啥意思，问遍全组没人懂" | delivery · api-documentation | 错误没人懂 |
| "示例跑不通，照着写全是坑" | delivery · api-documentation | 示例全是坑 |
| "系统长啥样，全在老员工脑子里" | delivery · architecture-doc | 长相脑子里 |
| "当初为啥这么定，没人说得清" | delivery · architecture-doc | 当初说不清 |
| "新人看代码猜架构，猜完还错了" | delivery · architecture-doc | 猜完还错了 |
| "故障复盘开完就散，结论没人记" | delivery · postmortem-doc | 开完就散会 |
| "同样的坑半年踩了三回" | delivery · postmortem-doc | 半年踩三回 |
| "时间线捋不清，根因全靠猜" | delivery · postmortem-doc | 根因全靠猜 |
| "文档散在各处，找篇靠谱的难" | delivery · technical-writer-skills-index | 散落找篇难 |
| "写文档全看自觉，风格各写各的" | delivery · technical-writer-skills-index | 风格各写各 |
| "一堆能力没人写出来，新人全靠问" | delivery · technical-writer-skills-index | 新人全靠问 |
| "用户天天问同样的操作，答烦了" | delivery · user-guide | 同问答烦了 |
| "功能上线了，教用户的话术没有" | delivery · user-guide | 话术没有备 |
| "截图教程过时了，照着走走不通" | delivery · user-guide | 过时走不通 |
| "读屏一开页面全乱，视障用不了" | delivery · accessibility | 读屏全乱套 |
| "老人说字太小按不动，改不动" | delivery · accessibility | 老人按不动 |
| "合规要过无障碍，不知从哪下手" | delivery · accessibility | 下手不知从 |
| "组件到处复制粘贴，改一处漏三处" | delivery · atomic-design | 改漏三处惨；与 component-architecture 二选一：要的是分层模型与设计系统那一套（原子→分子→有机体→模板→页面） → 本行；要的是单个框架里组件怎么拆、状态怎么分 → 200 |
| "页面越堆越沉，拆不出可复用的块" | delivery · atomic-design | 拆不出复用；与 component-architecture 二选一：要的是分层模型与设计系统那一套（原子→分子→有机体→模板→页面） → 本行；要的是单个框架里组件怎么拆、状态怎么分 → 200 |
| "设计和代码各搞各的，对不上" | delivery · atomic-design | 各搞对不上；与 component-architecture 二选一：要的是分层模型与设计系统那一套（原子→分子→有机体→模板→页面） → 本行；要的是单个框架里组件怎么拆、状态怎么分 → 200 |
| "按钮加载中长啥样，设计没画过" | delivery · component-states | 加载没画过 |
| "空态报错态缺一堆，前端自己编" | delivery · component-states | 缺态自己编 |
| "只给了静态图，动效交互全靠猜" | delivery · component-states | 动效全靠猜 |
| "设计稿丢过来，标注全靠猜" | delivery · design-handoff | 标注全靠猜 |
| "设计一改前端不知，联调才发现" | delivery · design-handoff | 改不知联调 |
| "切图量尺寸全靠肉眼，累个半死" | delivery · design-handoff | 肉眼累半死 |
| "后台页面又多又杂，风格各异" | delivery · design-system-mapping | 又多又杂乱 |
| "表格表单一多，排版就翻车" | delivery · design-system-mapping | 排版就翻车 |
| "想抄成熟后台的规范，不知抄啥" | delivery · design-system-mapping | 不知抄啥好 |
| "换个主题色，全站改到手软" | delivery · design-tokens | 改到手发软 |
| "多品牌共用一套，样式打起架来" | delivery · design-tokens | 样式打架惨 |
| "暗黑模式要上，颜色值散得到处是" | delivery · design-tokens | 颜色散到处 |
| "后台越做越像补丁摞补丁" | delivery · enterprise-patterns | 补丁摞补丁 |
| "权限审批流绕晕了，不知咋排" | delivery · enterprise-patterns | 绕晕不知排 |
| "数据一多页面就卡，不知咋摆" | delivery · enterprise-patterns | 卡摆不知咋 |
| "两端体验各玩各的，切过去别扭" | delivery · hig-principles | 各玩切别扭 |
| "苹果审总被打回，不知犯了哪条" | delivery · hig-principles | 打回不知犯 |
| "原生感做不出来，处处像网页套壳" | delivery · hig-principles | 像网页套壳 |
| "功能藏得太深，用户找不着" | delivery · information-architecture | 藏深找不着 |
| "菜单越加越长，层级乱成麻" | delivery · information-architecture | 层级乱成麻 |
| "老产品要改版，结构不知咋重组" | delivery · information-architecture | 重组不知咋 |
| "一屏塞了十几个按钮，不知点哪" | delivery · page-structure | 不知点哪个 |
| "列表详情表单，每个长得都不一样" | delivery · page-structure | 长得不一样 |
| "主次操作分不清，用户总点错" | delivery · page-structure | 总点错操作 |
| "手机一开页面挤成一团" | delivery · responsive-design | 挤成一团糟 |
| "平板横竖一切换，布局就崩" | delivery · responsive-design | 切换布局崩 |
| "一屏在小屏上要滑半天" | delivery · responsive-design | 小屏滑半天 |

| "设计从流程到视觉缺人整套带" | delivery · ui-ux-designer-skills-index | 流程视觉带 |
| "体验问题一堆，不知从哪开刀" | delivery · ui-ux-designer-skills-index | 不知从开刀 |
| "改版凭感觉拍，依据一张没有" | delivery · ui-ux-designer-skills-index | 依据一张无 |
| "上线前想请人挑刺，不知找谁" | delivery · usability-evaluation | 挑刺不知找 |
| "老页面难用到哪，得有人诊断" | delivery · usability-evaluation | 得有人诊断 |
| "对手比我们好，好在哪说不清" | delivery · usability-evaluation | 好哪说不清 |
| "流程走一半断了，断点没人管" | delivery · user-flow | 断点没人管 |
| "异常分支没人画，线上现挂" | delivery · user-flow | 线上现挂惨 |
| "页面跳来跳去，用户晕头转向" | delivery · user-flow | 跳晕转向惨 |
| "界面千篇一律，看不出自家样" | delivery · visual-style | 看不出自样 |
| "风格定不下来，每稿都像换人" | delivery · visual-style | 每稿像换人 |
| "深色浅色各一套，切过去违和" | delivery · visual-style | 切过去违和 |
