# -*- coding: utf-8 -*-
"""30 张卡的 5 段结构件定制内容（L1.1 / L1.3）。

每个技能的 spec 键：
    not_use:      [(负例描述, 去向相对路径), ...]   近邻负例 ≥2
    not_use_pre:  可选，前置条件型负例（一句话）
    pivot:        [(触发证据, 去向相对路径), ...]    ≥2
    dod:          [外部可观测条件, ...]              ≥2
    conf:         (confirmed 判据, low 判据)
    extra:        可选附加 markdown

引用路径一律相对技能目录。
"""

ASSAULT = "../reverse-engineering/references/assault-entry.md"
RE_REF = "../reverse-engineering/references"
ADF = "../ops/analysis-decision-framework.md"

SPECS = {}

# ---------------------------------------------------------------- 安全攻防 12
SPECS["pentest-tools"] = dict(
    not_use=[
        ("目标已明确是单个 Web 界面/API，要做逐接口鉴权与越权验证", "../api-security/SKILL.md"),
        ("目标是源码仓库、要白盒审注入与鉴权", "../code-audit/SKILL.md"),
        ("已经从信息收集进到「多跳串联、要打通域控」", "../attack-chain/SKILL.md"),
    ],
    not_use_pre="前置条件：先落 `scope.md`（`templates/scope.md`）记下目标与网络面 —— 扫描结果要挂到它上面才可复现",
    pivot=[
        ("扫描命中一个具体接口的鉴权缺陷，需要逐参数验证", "../api-security/SKILL.md"),
        ("发现凭据/票据，要往内网横向", "../windows-ad/SKILL.md"),
        ("发现云元数据可达（169.254.169.254 有响应）", "../cloud-k8s/SKILL.md"),
        ("发现暴露的数据库端口且可连", "../database-security/SKILL.md"),
    ],
    dod=[
        "`scope.md` 存在且授权字段非空",
        "`evidence/E-*.md` 每条有 `repro_command`，第三方可跑",
        "报告落盘路径存在，含 Findings 表 + 至少 1 条 Path",
        "复现检查：`python skills/case-review/scripts/review_case.py <case> --verify-hashes --strict` PASS",
    ],
    conf=("漏洞有 ≥2 条独立证据（手工复现 + 工具命中口径一致）",
          "仅黑盒响应差异（状态码/长度变化），未确认根因"),
)

SPECS["api-security"] = dict(
    not_use=[
        ("目标是浏览器里跑的 JS 签名/加密参数，要还原成不依赖浏览器的采集器", "../web-protocol-reverse/SKILL.md"),
        ("目标是源码仓库，要白盒找注入与鉴权缺失", "../code-audit/SKILL.md"),
        ("目标是二进制客户端（exe/so），要静态看逻辑", "../ida-reverse/SKILL.md"),
    ],
    not_use_pre="前置条件：越权验证要先有**成对的请求**（原身份 + 目标身份），否则差异无法归因",
    pivot=[
        ("签名/加密参数在客户端本地算出（断点能看到明文入参）", "../js-reverse/SKILL.md"),
        ("登录态依赖 SAML/OIDC 联邦，不是本地 JWT", "../identity-federation/SKILL.md"),
        ("越权后拿到内网可达地址，要横向", "../attack-chain/SKILL.md"),
    ],
    dod=[
        "每个 Finding 有 `evidence_ids`（≥1），`validated` 的 ≥2 条独立证据",
        "越权/缺陷的复现命令落盘，且在同一环境可重放",
        "报告含接口清单 + 鉴权矩阵（谁能调什么）",
    ],
    conf=("同一条越权同时有「请求 A 成功 / 请求 B（换身份）成功」两条实测",
          "仅凭响应字段命名推断权限模型，未实际换身份验证"),
)

SPECS["code-audit"] = dict(
    not_use=[
        ("手里只有二进制/APK，没有源码", "../reverse-engineering/SKILL.md"),
        ("要看的是运行时行为（网络/文件/内存），源码看不到", "../malware-analysis/SKILL.md"),
        ("要审的是依赖与构建链，不是自家源码", "../supply-chain-security/SKILL.md"),
    ],
    not_use_pre="前置条件：先建 `scope.md` 记下审的是哪个版本/哪个 commit，否则结论无法复现",
    pivot=[
        ("SAST 报出 taint 路径，需要在运行时确认可达", "../pentest-tools/SKILL.md"),
        ("发现硬编码密钥/证书，要验证可否利用", "../attack-chain/SKILL.md"),
        ("发现 CI 配置里注入点", "../supply-chain-security/SKILL.md"),
    ],
    dod=[
        "Findings 表每行有 `location`（file:line）与 `evidence_ids`",
        "每条 Finding 有最小复现（单测/脚本/请求）",
        "修好后的验证：原 PoC 不再成立，且既有测试仍绿",
    ],
    conf=("污点路径从 source 到 sink 完整走通，且有可执行 PoC",
          "仅 grep 到危险 API 调用，未确认参数可控/可达"),
)

SPECS["attack-chain"] = dict(
    not_use=[
        ("只有一个孤立漏洞点，还没拿到任何立足点", "../pentest-tools/SKILL.md"),
        ("已拿到域内凭据，只需域内提权与横向", "../windows-ad/SKILL.md"),
        ("目标只在云上（容器/K8s/元数据）", "../cloud-k8s/SKILL.md"),
    ],
    not_use_pre="前置条件：先跑 `case-init` 落 `scope.md`（目标 + network_profile），**后续所有证据都挂到它上面**",
    pivot=[
        ("拿到初始 shell，要枚举本机与域", "../windows-ad/SKILL.md"),
        ("拿到域控，要找数据出口与持久化评估", "../edr-bypass-re/SKILL.md"),
        ("发现云凭据，要评估容器逃逸", "../cloud-k8s/SKILL.md"),
    ],
    dod=[
        "`Path` 每条 step 关联 Evidence，终点 Finding 若声明「已拿权限」必须有 validated 证据",
        "攻击路径图（Mermaid）落盘，标出已证实/未证实节点",
        "`review_case.py --verify-hashes --strict` PASS",
    ],
    conf=("整条链每一跳都有独立的成功证据（不是从终点反推）",
          "链中某跳依赖未验证的推断"),
)

SPECS["thick-client"] = dict(
    not_use=[
        ("目标是纯 Web 应用/API", "../api-security/SKILL.md"),
        ("目标是 Android/iOS 应用", "../apk-reverse/SKILL.md"),
        ("目标是 Electron 渲染进程里的 JS 逻辑，不涉及本地能力", "../js-reverse/SKILL.md"),
    ],
    not_use_pre="前置条件：先画**信任边界表**（进程/用户/文件/网络的每一处跨界），再挑最有价值的一处深挖",
    pivot=[
        ("更新器校验可降级/可替换", "../supply-chain-security/SKILL.md"),
        ("本地存储发现可复用凭据，要打服务端", "../api-security/SKILL.md"),
        ("IPC/命名管道权限过宽，可被低权进程利用", "../windows-ad/SKILL.md"),
    ],
    dod=[
        "信任边界表落盘（进程/用户/文件/网络的每一处跨界）",
        "每处发现配最小复现命令或 PoC 脚本路径",
        "凭据存储位置与加密方式有实测结论（含「未加密」这一结论的证据）",
    ],
    conf=("客户端行为在两次以上干净环境复现，且与服务端交互抓包吻合",
          "仅静态看到一个 API 名就推断信任关系"),
)

SPECS["cloud-k8s"] = dict(
    not_use=[
        ("目标是自建机房的物理机/虚拟机，不涉及云元数据与容器", "../pentest-tools/SKILL.md"),
        ("目标只是应用层接口", "../api-security/SKILL.md"),
        ("要审的是构建流水线而非运行时集群", "../supply-chain-security/SKILL.md"),
    ],
    not_use_pre="前置条件：云资源变更不可逆 → 默认只读枚举；要变更先记录原配置以便回滚",
    pivot=[
        ("拿到云凭据，要评估能到哪些服务", "../attack-chain/SKILL.md"),
        ("容器内发现宿主机挂载/特权，要逃逸验证", "../kernel-exploit/SKILL.md"),
        ("发现 CI runner 可被投毒", "../supply-chain-security/SKILL.md"),
    ],
    dod=[
        "IAM 权限矩阵落盘（主体 × 动作 × 资源），每条有实测证据",
        "逃逸/越权的 PoC 命令落盘并可重放",
        "修复建议对应到具体配置项（不是泛泛而谈）",
    ],
    conf=("权限提升链每一跳都有 API 返回实测（不是策略文档推断）",
          "仅凭 IAM policy JSON 静态推断可达，未实际调用"),
)

SPECS["database-security"] = dict(
    not_use=[
        ("目标是应用层注入点，尚未接触数据库直连", "../api-security/SKILL.md"),
        ("目标是数据库里的数据本身（取证/恢复）", "../digital-forensics/SKILL.md"),
        ("目标是 DB 服务器的操作系统层", "../pentest-tools/SKILL.md"),
    ],
    not_use_pre="前置条件：生产库默认只读；要写先备好**回滚方案**（改前取快照 / 记录原值）",
    pivot=[
        ("确认弱口令可登录，要评估权限边界", "../windows-ad/SKILL.md"),
        ("Redis/Memcached 可写文件或 SSRF 可达", "../cloud-k8s/SKILL.md"),
        ("库里发现高价值数据，要评估外泄路径", "../attack-chain/SKILL.md"),
    ],
    dod=[
        "连接矩阵落盘（实例 × 端口 × 可达性 × 认证方式）",
        "权限清单有实测（`SHOW GRANTS` / `\\du` 等实际输出）",
        "每条结论附实际命令与返回",
    ],
    conf=("权限过高结论有实际 SQL 执行证据（如能读他人 schema）",
          "仅凭端口开放推断存在弱口令"),
)

SPECS["identity-federation"] = dict(
    not_use=[
        ("目标是本地 JWT 校验，不涉及 IdP 联邦", "../api-security/SKILL.md"),
        ("目标是 Windows 域内 Kerberos/NTLM（不是 Web SSO）", "../windows-ad/SKILL.md"),
        ("目标是 OAuth 客户端本身而非 IdP 配置", "../code-audit/SKILL.md"),
    ],
    not_use_pre="前置条件：先取一份**公开元数据**（`/.well-known/openid-configuration` 等）作为基线，再谈差异",
    pivot=[
        ("发现 assertion 可被篡改/重放", "../api-security/SKILL.md"),
        ("发现签名证书可控（自签被接受）", "../attack-chain/SKILL.md"),
        ("SAML 断言里带高权角色，要评估下游影响", "../api-security/SKILL.md"),
    ],
    dod=[
        "联邦流程逐跳落盘（IdP → SP → 会话），标注每跳的信任假设",
        "每条缺陷有实际构造的 assertion/请求与响应",
        "修复对应到具体配置（不是「加强校验」）",
    ],
    conf=("构造的 assertion 被 SP 接受且有会话建立实测",
          "仅从元数据里看到签名算法为 none/弱算法"),
)

SPECS["email-security"] = dict(
    not_use=[
        ("目标是邮件网关的 Web 界面", "../pentest-tools/SKILL.md"),
        ("要分析的是恶意附件本身", "../malware-analysis/SKILL.md"),
        ("要查的是邮件服务器主机层", "../windows-ad/SKILL.md"),
    ],
    not_use_pre="前置条件：验证发件路径用**受控邮箱**（自建或自己的别名），便于反复试且不打扰他人",
    pivot=[
        ("附件是宏文档/脚本，要静态+动态分析", "../malware-analysis/SKILL.md"),
        ("发现可伪造发件域，要评估下游可利用面", "../attack-chain/SKILL.md"),
        ("发现链接指向自家应用，要审该应用", "../api-security/SKILL.md"),
    ],
    dod=[
        "SPF/DKIM/DMARC 实测记录落盘（含原始 Received 头）",
        "每条结论附一份原始邮件（脱敏后）",
        "可利用性判定给出发送路径（能到达哪个 MTA）",
    ],
    conf=("伪造邮件实际投递到目标收件箱（有 Received 链佐证）",
          "仅解析 DNS 记录推断可以伪造"),
)

SPECS["windows-ad"] = dict(
    not_use=[
        ("还没有任何域内立足点（无凭据/无 shell）", "../pentest-tools/SKILL.md"),
        ("目标是 Linux 环境", "../kernel-exploit/SKILL.md"),
        ("要打的是 Web SSO 联邦", "../identity-federation/SKILL.md"),
    ],
    not_use_pre="前置条件：**域不属于你** → 只做只读枚举（BloodHound 采集），不做写操作",
    pivot=[
        ("拿到域管，要找出口与持久化评估", "../edr-bypass-re/SKILL.md"),
        ("发现 AD CS 配置错误（ESC1-ESC8）", "../attack-chain/SKILL.md"),
        ("发现 NTLM 可中继的目标", "../pentest-tools/SKILL.md"),
    ],
    dod=[
        "攻击路径图（BloodHound 导出 + Mermaid）落盘",
        "每条边有实测证据（不是理论可达）",
        "提权/横向的 PoC 命令落盘可重放",
    ],
    conf=("凭据可用性有实际认证成功证据（不是哈希格式判断）",
          "仅凭 BloodHound 边推断可达，未实际执行"),
)

SPECS["llm-security"] = dict(
    not_use=[
        ("目标是传统注入（SQLi/XSS/命令注入）", "../api-security/SKILL.md"),
        ("目标是模型权重与训练数据本身", "../reverse-engineering/SKILL.md"),
        ("要审的是 agent 供应链（依赖/构建）", "../supply-chain-security/SKILL.md"),
    ],
    not_use_pre="前置条件：攻击要有**可重放的输入序列**（单次命中可能是采样随机性，不足为证）",
    pivot=[
        ("发现 agent 能调工具，要评估工具滥用链", "../attack-chain/SKILL.md"),
        ("发现 RAG 数据源污染", "../supply-chain-security/SKILL.md"),
        ("发现提示注入可越权访问内部系统", "../api-security/SKILL.md"),
    ],
    dod=[
        "每条攻击有可重放的 prompt/输入序列落盘",
        "命中率有多次运行统计（不是单次成功）",
        "影响评估写到具体被突破的边界（数据/工具/权限）",
    ],
    conf=("同一 payload 在 ≥3 次独立运行中稳定触发",
          "单次触发，可能是采样随机性"),
)

SPECS["supply-chain-security"] = dict(
    not_use=[
        ("要审的是自家业务源码逻辑", "../code-audit/SKILL.md"),
        ("要打的是运行时集群/容器", "../cloud-k8s/SKILL.md"),
        ("要逆向的是单个二进制样本", "../reverse-engineering/SKILL.md"),
    ],
    not_use_pre="前置条件：上游包不要就地改（下次安装会覆盖）→ 缓解写在本地（patch/overlay/wrapper）",
    pivot=[
        ("发现可执行依赖（postinstall 等）", "../malware-analysis/SKILL.md"),
        ("发现构建产物与源码不一致", "../binary-diff/SKILL.md"),
        ("发现 CI 凭据可窃取", "../attack-chain/SKILL.md"),
    ],
    dod=[
        "SBOM 落盘（含版本与直接/传递依赖标记）",
        "每条 CVE 有可达性判定（不只列版本）",
        "CI 审计的每条发现对应到 workflow 文件的具体行",
    ],
    conf=("可达性结论有实际调用链证据（源码或反编译）",
          "仅按版本号匹配 CVE 未判可达性"),
)

# ---------------------------------------------------------------- 其余 18
SPECS["pwn-chain"] = dict(
    not_use=[
        ("还没定位到漏洞点（只是拿到一个陌生二进制）", "../reverse-engineering/SKILL.md"),
        ("目标是内核态提权/逃逸", "../kernel-exploit/SKILL.md"),
        ("有 CVE 但没有 PoC，要从前后的补丁差异反推", "../patch-diff-exploit/SKILL.md"),
    ],
    not_use_pre="前置条件：利用要在**可重启的目标**上验证（崩溃是常态，目标不可重启会中断迭代）",
    pivot=[
        ("利用被缓解机制挡住（SMEP/SMAP/KASLR/KPTI）", ASSAULT),
        ("目标是内核对象", "../kernel-exploit/SKILL.md"),
        ("目标带壳/反调试，动态都进不去", ASSAULT),
    ],
    dod=[
        "PoC 脚本落盘，在目标上 **≥3 轮稳定命中**（shell/flag/目标回连）",
        "利用链每跳的偏移/地址写进报告，可复现",
        "缓解绕过有单独说明（绕了什么、怎么绕的）",
    ],
    conf=("同一 exploit 连续 3 轮命中且 ASLR 开启下仍稳",
          "单次命中，可能是地址运气/未开 ASLR"),
)

SPECS["kernel-exploit"] = dict(
    not_use=[
        ("目标是用户态程序漏洞", "../pwn-chain/SKILL.md"),
        ("只是要分析驱动文件结构，不涉及利用", "../reverse-engineering/SKILL.md"),
        ("目标是 Android 应用层", "../apk-reverse/SKILL.md"),
    ],
    not_use_pre="前置条件：内核操作可能使宿主不可恢复 → 在**可快照回滚的 VM** 上做，先记内核版本与缓解开关",
    pivot=[
        ("确认漏洞点，要写用户态利用", "../pwn-chain/SKILL.md"),
        ("目标是容器逃逸", "../cloud-k8s/SKILL.md"),
        ("需要分析驱动二进制逻辑", "../ida-reverse/SKILL.md"),
    ],
    dod=[
        "提权/逃逸 PoC 落盘并在目标内核版本上 **≥3 轮稳定**",
        "记录内核版本、配置、缓解开关（SMEP/SMAP/KPTI/kptr_restrict）",
        "崩溃现场（dmesg/oops）留档作为判据",
    ],
    conf=("在目标内核版本上多轮稳定提权，且无 panic",
          "仅在某一内核版本单次成功"),
)

SPECS["edr-bypass-re"] = dict(
    not_use=[
        ("只是要分析样本行为，不涉及交付躲避", "../malware-analysis/SKILL.md"),
        ("目标是 Linux 主机", "../kernel-exploit/SKILL.md"),
        ("目标根本没有 EDR/AV 驻守", "../pentest-tools/SKILL.md"),
    ],
    not_use_pre="前置条件：载荷交付前先确认目标机**可快照回滚**（EDR 会拦，回滚是常态操作）",
    pivot=[
        ("载荷落地后被静态查杀", "../reverse-engineering/SKILL.md"),
        ("需要分析 EDR 自身的用户态 hook", "../x64dbg-reverse/SKILL.md"),
        ("发现内存扫描命中", "../malware-analysis/SKILL.md"),
    ],
    dod=[
        "载荷在目标环境 **≥3 轮**投放成功（不是一次偶然）",
        "记录具体绕过项（unhook/直接系统调用/AMSI/ETW）与对应证据",
        "检测侧对照：给出该载荷的检测规则（Sigma/YARA）并验证可触发",
    ],
    conf=("多轮投放稳定且检测侧规则能命中（攻防都有证据）",
          "单轮成功，未确认是否为白名单放行"),
)

SPECS["patch-diff-exploit"] = dict(
    not_use=[
        ("手上只有单个版本，没有 before/after 对照", "../reverse-engineering/SKILL.md"),
        ("只是要把旧版符号迁到新版，不需要利用", "../binary-diff/SKILL.md"),
        ("目标是源码可见的开源项目", "../code-audit/SKILL.md"),
    ],
    not_use_pre="前置条件：PoC 要在**受影响版本与修复版双向验证**（只在一个版本上成功不足以定论）",
    pivot=[
        ("定位到新增检查点，要写利用", "../pwn-chain/SKILL.md"),
        ("目标是内核补丁", "../kernel-exploit/SKILL.md"),
        ("目标是驱动", "../ida-reverse/SKILL.md"),
    ],
    dod=[
        "patch diff 落盘（变更函数清单 + 反编译对照）",
        "bug class 判定有依据（OOB/UAF/溢出各对应什么代码特征）",
        "PoC 在受影响版本上 **≥3 轮稳定**触发；在修复版不复现",
    ],
    conf=("PoC 在受影响版本稳定触发且在修复版失效（双向证据）",
          "仅从 diff 推断可利用，未实测"),
)

SPECS["binary-diff"] = dict(
    not_use=[
        ("要的是从补丁差异写利用，不只是迁移符号", "../patch-diff-exploit/SKILL.md"),
        ("只有单个版本，没有对照对象", "../reverse-engineering/SKILL.md"),
        ("目标是 .NET 程序（去混淆更直接）", "../dotnet-reverse/SKILL.md"),
    ],
    not_use_pre="前置条件：两个二进制需同源（否则符号匹配无意义）—— 先验证 `.text` 相似度",
    pivot=[
        ("迁移中发现新增函数，怀疑是安全修复", "../patch-diff-exploit/SKILL.md"),
        ("符号在目标版本被剥离，需要重建", "../ida-reverse/SKILL.md"),
        ("目标语言为 Go/Rust（有自身元数据）", "../go-rust-reverse/SKILL.md"),
    ],
    dod=[
        "匹配结果表落盘（旧地址 → 新地址 → 置信度）",
        "未匹配项单独列出并说明原因",
        "在目标版本上验证：迁移后的符号指向的函数与预期一致（抽样 ≥3 个）",
    ],
    conf=("匹配有多特征交叉（调用图 + 字符串 + 常量），且抽样验证通过",
          "仅凭字节相似度匹配"),
)

SPECS["go-rust-reverse"] = dict(
    not_use=[
        ("目标是 C/C++ 编译的普通 PE/ELF", "../ida-reverse/SKILL.md"),
        ("目标是托管代码（.NET）", "../dotnet-reverse/SKILL.md"),
        ("只是要快速看 strings/结构", "../radare2/SKILL.md"),
    ],
    not_use_pre="前置条件：先用 `diec` 确认语言（Go 有 buildid，Rust 有 mangled 符号）",
    pivot=[
        ("确认是 Go 且带 panic 字符串", RE_REF + "/triage-first-30-min.md"),
        ("符号被剥离需要重建函数名", "../binary-diff/SKILL.md"),
        ("目标是恶意样本（Go 恶意软件常见）", "../malware-analysis/SKILL.md"),
    ],
    dod=[
        "恢复的函数名/类型表落盘（含置信度）",
        "关键逻辑定位有实际反编译输出作为证据",
        "在样本上验证：恢复的符号指向的字符串/调用符合预期",
    ],
    conf=("用 pclntab/GoReSym 等元数据恢复，且抽样在反编译中核对一致",
          "仅凭字符串模式猜测函数用途"),
)

SPECS["hardware-security"] = dict(
    not_use=[
        ("目标只有固件文件，没有物理板子", "../firmware-pentest/SKILL.md"),
        ("目标是软件层的调试接口（不是 JTAG/SWD/UART）", "../x64dbg-reverse/SKILL.md"),
        ("目标是无线射频信号", "../radio-sdr/SKILL.md"),
    ],
    not_use_pre="前置条件：物理接触可能不可逆 → 动手前先留**可恢复的备份/快照**（Flash 读数、焊点照片）",
    pivot=[
        ("从 Flash 提取到固件镜像", "../firmware-pentest/SKILL.md"),
        ("从串口拿到 shell，要分析系统内进程", "../reverse-engineering/SKILL.md"),
        ("发现无线芯片，要分析射频协议", "../radio-sdr/SKILL.md"),
    ],
    dod=[
        "接口识别结果落盘（引脚 → 信号 → 波特率/时序实测值）",
        "提取的镜像/固件有 SHA-256 与落盘路径",
        "可重复：给出下一个人照着做能复现的接线与命令",
    ],
    conf=("接口用途有实测数据（示波器/逻辑分析仪抓到的波形或成功读写）",
          "仅凭引脚排布猜测 UART TX/RX"),
)

SPECS["ot-ics"] = dict(
    not_use=[
        ("目标是 IT 网络/办公网", "../pentest-tools/SKILL.md"),
        ("目标是 IoT 消费设备固件", "../firmware-pentest/SKILL.md"),
        ("目标只是工控软件的桌面客户端", "../thick-client/SKILL.md"),
    ],
    not_use_pre="前置条件：写寄存器/下装会动到**物理过程** → 默认只读被动；确要写先确认有物理回退手段（旁路/急停）",
    pivot=[
        ("需要看 PLC 固件内部逻辑", "../firmware-pentest/SKILL.md"),
        ("发现工程站 Windows 主机可打", "../windows-ad/SKILL.md"),
        ("需要被动嗅探工业协议流量", "../protocol-reverse/SKILL.md"),
    ],
    dod=[
        "被动识别结果落盘（协议 → 设备 → 点位清单），全程无写操作记录",
        "Purdue 分层图落盘，标出已观测到的跨层通信",
        "任何主动测试都有授权记录 + 影响评估（会不会动到物理过程）",
    ],
    conf=("协议/设备识别有被动抓包多次佐证，且未对过程产生任何扰动",
          "仅从端口开放推断是某 PLC 型号"),
)

SPECS["radio-sdr"] = dict(
    not_use=[
        ("目标是 Wi-Fi（802.11）", "../wifi-wireless/SKILL.md"),
        ("目标是固件里的无线配置", "../firmware-pentest/SKILL.md"),
        ("目标是蓝牙以外的普通网络协议", "../protocol-reverse/SKILL.md"),
    ],
    not_use_pre="前置条件：**默认只收不发**；发射（重放/干扰）会污染现场 → 只在屏蔽室或物理隔离环境做",
    pivot=[
        ("识别出具体协议，需要还原报文结构", "../protocol-reverse/SKILL.md"),
        ("信号来自某设备，需要看其固件", "../firmware-pentest/SKILL.md"),
        ("目标是 Wi-Fi 握手", "../wifi-wireless/SKILL.md"),
    ],
    dod=[
        "IQ 采样或解调结果有落盘路径与参数（中心频率/带宽/采样率）",
        "调制识别有依据（星座图/频谱特征），不是猜",
        "可重放性评估写明「是否需要发射」以及是否已获授权",
    ],
    conf=("解调出的比特流有 CRC/结构校验通过（不是噪声里挑出来的）",
          "仅凭频谱形状猜测调制方式"),
)

SPECS["wifi-wireless"] = dict(
    not_use=[
        ("目标是非 Wi-Fi 射频（遥控/ADS-B/传感器）", "../radio-sdr/SKILL.md"),
        ("目标是网卡的固件本身", "../firmware-pentest/SKILL.md"),
        ("目标是域内主机", "../windows-ad/SKILL.md"),
    ],
    not_use_pre="前置条件：**监听本身也可能违法** → 只对自有/授权网络抓包与评估",
    pivot=[
        ("抓到握手包，要离线评估口令强度", "../pentest-tools/SKILL.md"),
        ("发现企业无线接入了内网，要横向", "../windows-ad/SKILL.md"),
        ("需要分析网卡驱动/固件", "../firmware-pentest/SKILL.md"),
    ],
    dod=[
        "抓包文件落盘（cap/pcapng）+ 抓包参数记录（信道/带宽/时间）",
        "评估结果：握手/PMKID 是否捕获成功，口令评估是否得出结果",
        "给出可复现的抓包命令",
    ],
    conf=("口令评估成功复原口令，或用握手包验证了口令正确",
          "仅捕获到流量，未形成可验证结论"),
)

SPECS["threat-hunting"] = dict(
    not_use=[
        ("要分析的是样本本体（静态/动态）", "../malware-analysis/SKILL.md"),
        ("要做的是磁盘/内存取证", "../digital-forensics/SKILL.md"),
        ("要收集的是外部威胁情报", "../threat-intelligence/SKILL.md"),
    ],
    not_use_pre="前置条件：查询生产 SIEM 前先确认查询范围与配额，避免拖垮日志平台",
    pivot=[
        ("假设命中，需要样本确认", "../malware-analysis/SKILL.md"),
        ("需要落盘检测规则", RE_REF + "/re-agent-workflow.md"),
        ("需要外部 IOC 富化", "../threat-intelligence/SKILL.md"),
    ],
    dod=[
        "假设清单 + 对应查询语句 + 结果落盘",
        "每条检测规则在实际数据上验证过「能触发且不误报」",
        "规则文件路径 + 触发样本证据",
    ],
    conf=("规则在真实数据上实测触发，且控制组不误报",
          "规则只在理论上能匹配，未跑过数据"),
)

SPECS["threat-intelligence"] = dict(
    not_use=[
        ("要落地检测规则到 SIEM", "../threat-hunting/SKILL.md"),
        ("要分析样本本体", "../malware-analysis/SKILL.md"),
        ("目标是内部威胁（不是外部情报）", "../digital-forensics/SKILL.md"),
    ],
    not_use_pre="前置条件：**只使用公开来源**；不收集非公开个人数据",
    pivot=[
        ("获得 IOC，要在日志里找落地", "../threat-hunting/SKILL.md"),
        ("需要样本层面确认", "../malware-analysis/SKILL.md"),
        ("发现仿冒站点，要评估其技术面", "../web-protocol-reverse/SKILL.md"),
    ],
    dod=[
        "情报包落盘，每条 IOC 附来源 URL 与采集时间",
        "归属结论标注置信度，并写明「不足以支撑结论的部分」",
        "可复用：给出查询语/jq 表达式，第三方可复现",
    ],
    conf=("多源交叉且时间线自洽（≥2 个独立来源指向同一活动）",
          "单一来源，或时间线存在无法解释的冲突未解决"),
)

SPECS["digital-forensics"] = dict(
    not_use=[
        ("要分析的是样本本身的行为与能力", "../malware-analysis/SKILL.md"),
        ("要做的是主动检测规则", "../threat-hunting/SKILL.md"),
        ("要收集的是外部情报", "../threat-intelligence/SKILL.md"),
    ],
    not_use_pre="前置条件（硬性）：**不改变原始证据**；镜像前先做只读挂载或写阻止",
    pivot=[
        ("转储里发现可疑样本，要分析", "../malware-analysis/SKILL.md"),
        ("PCAP 里发现异常协议", "../protocol-reverse/SKILL.md"),
        ("需要落检测规则防复发", "../threat-hunting/SKILL.md"),
    ],
    dod=[
        "镜像/转储有 SHA-256 与封存路径；分析全程在副本上",
        "时间线文件落盘（事件 → 时间 → 来源证据）",
        "`review_case.py --verify-hashes --strict` PASS",
    ],
    conf=("时间线事件有 ≥2 类独立来源佐证（磁盘 + 内存 / 日志 + 流量）",
          "仅靠单一日志来源推断事件顺序"),
)

SPECS["ctf-sandbox"] = dict(
    not_use=[
        ("目标是真实生产系统/真实客户资产", "../attack-chain/SKILL.md"),
        ("任务是长期项目而非单次解题", "../docs-generator/SKILL.md"),
        ("只是要审一段代码", "../code-audit/SKILL.md"),
    ],
    not_use_pre="前置条件：长期项目走 `../reverse-engineering/references/assault-entry.md`；本卡只管比赛/靶场的**单次编排**",
    pivot=[
        ("题目归类为 pwn", "../pwn-chain/SKILL.md"),
        ("题目归类为逆向", "../reverse-engineering/SKILL.md"),
        ("题目要求写 writeup 交付", "../docs-generator/SKILL.md"),
    ],
    dod=[
        "flag/预期解 落盘；解题步骤记录到 `timeline`",
        "每题的技能选择在 route-scope 里有记录",
        "writeup 落盘（若需要交付）",
    ],
    conf=("flag 已取得并有原始输出证据",
          "仅推断出解法但未实际跑通"),
)

SPECS["case-review"] = dict(
    not_use=[
        ("要新建一个 case（不是审已完成的）", "../ops/scope-contract.md"),
        ("要写报告正文", "../docs-generator/SKILL.md"),
        ("要画图", "../diagram-generator/SKILL.md"),
    ],
    not_use_pre="本技能是**只读**审查：不修 case 内容，只报缺陷",
    pivot=[
        ("发现证据链断裂，要补证据", "../ops/evidence-finding-path.md"),
        ("发现 scope 缺失，要补授权", "../ops/scope-contract.md"),
        ("审查通过，要出报告", "../docs-generator/SKILL.md"),
    ],
    dod=[
        "审查报告落盘：每条缺陷 → case 里的具体文件与行",
        "`review_case.py --verify-hashes --strict` 的原始输出贴回",
        "给出「可交 / 不可交」的明确判定与缺口清单",
    ],
    conf=("哈希与证据链全部核对过，且审查结论有具体行号支撑",
          "仅通读了报告文本，未跑哈希校验"),
)

SPECS["docs-generator"] = dict(
    not_use=[
        ("要画的是图不是文", "../diagram-generator/SKILL.md"),
        ("要审 case 完整性而不是写文档", "../case-review/SKILL.md"),
        ("要写的是代码注释/README 之外的代码", "../code-audit/SKILL.md"),
    ],
    not_use_pre="前置条件：报告里的技术结论必须来自 case 的 Evidence，不许自创",
    pivot=[
        ("报告里需要图，先画图", "../diagram-generator/SKILL.md"),
        ("报告要交出去，先审 case", "../case-review/SKILL.md"),
        ("需要补技术证据", "../ops/evidence-finding-path.md"),
    ],
    dod=[
        "文档落盘路径存在，含 Scope / Evidence / Findings / ≥1 Path",
        "每条结论可追到 Evidence ID",
        "Executive Summary 面向非技术读者，无术语堆砌",
    ],
    conf=("报告中每条技术主张都能在 Evidence 里找到对应",
          "报告中出现无法追溯的结论"),
)

SPECS["diagram-generator"] = dict(
    not_use=[
        ("要写的是大段文字文档", "../docs-generator/SKILL.md"),
        ("要审 case 完整性", "../case-review/SKILL.md"),
        ("要画的图超出 Mermaid/PlantUML 表达能力（复杂拓扑/3D）", "../docs-generator/SKILL.md"),
    ],
    not_use_pre="图必须来自真实结构，不许为好看编造节点",
    pivot=[
        ("图里需要嵌入文档正文", "../docs-generator/SKILL.md"),
        ("图表达不了（需要位图/截图）", "../browser-automation/SKILL.md"),
        ("需要审图所依据的 case", "../case-review/SKILL.md"),
    ],
    dod=[
        "图源文件（.mmd/.puml）落盘，可再编辑",
        "在目标渲染器上能正确渲染（无语法错误）",
        "图中每个节点/边可追溯到实际代码或案例事实",
    ],
    conf=("图渲染通过且节点数与实际结构核对一致",
          "仅凭文字描述想象出结构图"),
)

SPECS["browser-automation"] = dict(
    not_use=[
        ("要做的是还原站点签名/加密算法（不是驱动界面）", "../web-protocol-reverse/SKILL.md"),
        ("目标没有 UI，只有 API", "../api-security/SKILL.md"),
        ("要逆向的是扩展代码本身", "../browser-extension-reverse/SKILL.md"),
    ],
    not_use_pre="前置条件：脚本要能在**干净会话**里重复跑通（依赖手动状态的脚本不算资产）",
    pivot=[
        ("页面里的参数是本地算的，要还原算法", "../js-reverse/SKILL.md"),
        ("需要抓包分析接口", "../web-protocol-reverse/SKILL.md"),
        ("操作的是 Windows 原生 GUI（非浏览器）", "../reverse-engineering/SKILL.md"),
    ],
    dod=[
        "脚本落盘 + 可重复运行（同一输入同一结果）",
        "关键步骤有截图或 DOM 快照留档",
        "失败路径也有记录（哪一步不可自动化、为什么）",
    ],
    conf=("流程在干净会话中 ≥3 次完整跑通",
          "单次跑通，依赖了当时的手动状态"),
)
