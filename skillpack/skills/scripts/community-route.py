#!/usr/bin/env python3
"""Read-only lookup for adapted community capabilities.

The canonical master route chooses a wrapper first. This helper only narrows the
wrapper's adapted references; it never returns a raw community skill as an
invocation path. Weak or ambiguous matches are reported as ``needs_review``.

Contract responsibilities added by T02 (the alias lexicon, the tokeniser, the
evidence-breadth score used for the wrapper score/confidence and the 4.7
ambiguity rule are unchanged):

* the order in which adapted references inside one wrapper are offered and
  truncated was added later: a hint token that matches the record's own name
  (upstream slug, directory, file name) now outranks a token that only appears in
  the description or keyword list. See ``NAME_HIT_WEIGHT`` and
  ``docs/community/ROUTE-RANKING.md``;

* every registry enum is validated; an unknown value fails closed instead of
  being passed through (spec 4.0 rule 2);
* wrapper metadata (path, route ids, reference ids, downstream) is read from
  ``registry.json.wrappers[]`` instead of being hardcoded here, so the registry is
  the fact source and a wrapper record that points at a missing file is a
  ``blocked`` result rather than a silent mismatch;
* ``allowed_context`` is resolved to exactly one canonical context profile per
  record through ``skills/config/profile-map.json`` (spec 4.6);
* status output implements all six frozen 4.7 statuses plus their exit codes.

T26 added the curated signal layer (``skills/community/routing-signals.json``)
as a third fail-closed input, and replaced the two separate token views with a
single ``routing_view``. The invariant the module now keeps is:

    routing_view(text) = tokens(text)
                       UNION hyphen parts of every token
                       UNION the alias prefix of every ``alias_``-prefixed token
                       UNION {token_aliases[t] for t in the set, if t in token_aliases}

ONE view is used for candidacy, for ``name_hits`` and for ``description_hits``, so
a record cannot be reachable by a token the ranker cannot see. The earlier design
("only the name view is widened; the evidence-breadth score keeps the strict
token set") is **withdrawn**: it was exactly the inconsistency that made the
widening unreachable, because candidacy was gated on the strict set while ranking
consulted the widened one afterwards. ``_score`` keeps the strict token set on
purpose -- it still measures evidence breadth and stays the only input to the
wrapper score and to ``confidence`` -- but it is no longer a candidacy gate. The
three frozen quantities are therefore distinct and none of them gates another:

* candidacy   : ``hint_terms & (routing_view(name) | routing_view(description))``
                is non-empty, OR a curated signal fired for this record;
* ``rank_score``: ``4*len(signal_hits) + 3*len(name_hits) + 1*len(description_hits)``
                -- recomputable by hand from ``routing-signals.json`` and the
                reported hit lists;
* ``_score``   : evidence breadth only; feeds the wrapper score and ``confidence``.

Normalisation from the same file is applied to the *record* only: ``noise[]`` is
substituted out of a record's routing text before it is tokenised and is never
applied to the hint, ``token_aliases`` folds both sides symmetrically, and
``short_tokens`` admits exactly its own literals at a length the global minimum of
3 characters still governs for everything else.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "skills" / "community" / "registry.json"
PROFILE_MAP = ROOT / "skills" / "config" / "profile-map.json"
ROUTING = ROOT / "skills" / "config" / "routing.json"
# T26: the curated signal layer is a third REQUIRED, fail-closed input, handled
# exactly like REGISTRY and PROFILE_MAP (see ``load_signals``). The shipped
# skeleton holds valid EMPTY arrays, so every array may be empty and then this
# layer contributes nothing at all -- the ranking model below is then unchanged.
SIGNALS = ROOT / "skills" / "community" / "routing-signals.json"
SIGNALS_SCHEMA_VERSION = "1.0"
REGISTRY_SCHEMA_VERSION = "1.0"
MIN_CONFIDENCE = 0.35
NEAR_TIE_DELTA = 0.20

# ---------------------------------------------------------------------------
# Reference ranking model (see docs/community/ROUTE-RANKING.md).
#
# ``_score`` above still measures *evidence breadth* (how many distinct hint
# tokens the record answers to anywhere) and stays the only input to the wrapper
# score and to confidence, so the 4.7 ambiguity/tie semantics are untouched.
# Ranking inside a wrapper uses a second, field-aware score: a curated signal
# that fires outranks any incidental overlap, a hint token that matches the
# record's own name (upstream slug, adapted directory, file name) outranks a
# token that only appears in the description or the keyword list.
#
# T26: candidacy, ``name_hits`` and ``description_hits`` all read the SAME
# ``routing_view``. The withdrawn "only the name view is widened" rule is what
# produced defect D1 -- candidacy was gated on the strict token set while the
# widening was consulted only afterwards, inside the ranker.
# ---------------------------------------------------------------------------
SIGNAL_HIT_WEIGHT = 4
NAME_HIT_WEIGHT = 3
DESCRIPTION_HIT_WEIGHT = 1
# Product decision: three adapted references per wrapper is what a caller can
# read before it has to re-query. Raising the cap would hide ranking defects
# instead of fixing them, so the cap is only ever changed together with an
# argued ranking change.
REFERENCE_LIMIT = 3

# T11 loading budget (spec 17.25). REFERENCE_LIMIT above is untouched: it bounds
# what one wrapper *shows*. The budget below bounds what one query may
# *consider*, and exceeding it stops with a report instead of silently
# truncating. Numbers are asserted in docs/community/LOADING-BUDGET.md.
MAX_WRAPPER_CANDIDATES = 5  # registry 初筛单次最多返回 5 个 wrapper
MAX_TOTAL_REFERENCES = 50  # 单次查询命中的 adapted reference 总数上限

# Frozen 4.7 status -> process exit code. T25 owns the final "script -> status"
# table; this helper already follows it.
STATUS_EXIT = {
    "matched": 0,
    "needs_review": 10,
    "blocked": 20,
    "missing_input": 21,
    "unavailable": 22,
    "failed": 30,
}

FAILURE_REASONS = (
    "auth_expired", "auth_target_mismatch", "scope_empty", "path_escape",
    "license_not_redistributable", "tool_missing", "timeout", "budget_exceeded",
    "untrusted_instruction", "schema_invalid", "internal_error",
)

# Replace high-signal phrases before tokenising so Chinese and English inputs
# share the same vocabulary without depending on upstream names.
#
# CJK alias (2026-10-01): “ssti/xxe/graphql”从 web/api 雕刻为独立 canonical
# （web 原 blast 22、api 原 blast 33，过宽）；“xss/sqli/space 形 sql injection”
# 留在 web（英文常用查询逐字稳定），中文靠跨站脚本/sql注入等精确变体命中，
# 记录侧由连字符 slug（xss-cross-site-scripting、sqli-sql-injection）桥接。
# 雕刻词的裸英文 hint（如 xxe/graphql）候选更少，属预期精度收益，见 work/cjk-alias/REPORT.md。
ALIASES: dict[str, tuple[str, ...]] = {
    "ctf": ("ctf", "capture the flag", "夺旗赛", "夺旗", "解题赛", "竞赛题"),
    "apk": ("apk", "aab", "android package", "android", "安卓", "安卓应用", "安卓逆向", "smali", "dex", "jadx", "apktool"),
    "jwt": ("jwt", "json web token", "jsonwebtoken", "令牌伪造", "令牌篡改"),
    "ssrf": ("ssrf", "server-side request forgery", "server side request forgery", "服务端请求伪造", "服务器端请求伪造", "请求伪造"),
    "web": ("web", "website", "网页", "web漏洞", "xss", "sqli", "sql injection"),
    "api": ("api", "rest api", "接口安全", "接口"),
    "delivery": ("full-stack", "full stack", "全栈", "delivery", "交付", "部署", "devops", "workflow", "工作流", "ci/cd", "pipeline"),
    "reverse": ("reverse engineering", "reversing", "逆向", "反编译", "反汇编"),
    # CJK alias (2026-10-01): pilot 8 组，依据 PLAN §3（blast: upload 3 / sqli 4 / idor 3 / smuggling 3 / race 4 / memory 2-3 / privilege 5）。
    # (“upload” canonical 已删：x-gap-upload 冻结 pin 要求“文件上传漏洞怎么测”零 wrapper（master R46 认领），见 DEVIATIONS。)
    "xss": ("cross-site-scripting", "cross site scripting", "跨站脚本", "跨站", "xss漏洞"),
    "sqli": ("sql-injection", "sql注入"),
    "idor": ("idor", "越权", "越权漏洞", "未授权访问", "平行越权", "垂直越权"),
    "smuggling": ("smuggling", "request-smuggling", "request smuggling", "请求走私", "http请求走私"),
    "race": ("race", "race-condition", "race condition", "条件竞争", "竞态", "竞态条件"),
    "memory": ("memory", "memory-forensics", "内存取证", "内存镜像", "volatility"),  # “内存转储”已删：x-neg-forensics 冻结 pin（master R25 认领）
    "privilege": ("privilege", "privilege-escalation", "privilege escalation", "提权", "权限提升", "本地提权", "privesc"),
    # CJK alias (2026-10-01): 全量 32 组。blast=命中该 canonical 的全库记录数（alias 级实测，见 REPORT），>6 拒收。
    "deserialization": ("deserialization", "反序列化", "反序列化漏洞", "java反序列化", "php反序列化"),  # blast 2
    "xxe": ("xxe", "xml外部实体", "xml外部实体注入", "外部实体注入", "xxe漏洞"),  # blast 4
    "ssti": ("ssti", "模板注入", "服务端模板注入", "ssti漏洞"),  # blast 3
    "crlf": ("crlf", "crlf注入", "回车换行注入", "响应拆分", "http响应拆分"),  # blast 3
    "host": ("host", "host-header", "host header", "host头", "host头注入", "host头攻击", "主机头"),  # blast 6（守门阈值内）
    "clickjacking": ("clickjacking", "点击劫持", "点击劫持漏洞"),  # blast 1
    "cors": ("cors", "cors配置错误", "跨域资源共享", "跨域配置错误", "cors漏洞"),  # blast 3
    "graphql": ("graphql", "graph-ql", "graphql注入", "graphql接口", "内省"),  # blast 2
    "oauth": ("oauth", "oauth漏洞", "第三方登录", "第三方登录漏洞"),  # blast 8（全为认证记录，接受并备注）
    "metadata": ("metadata", "云元数据", "元数据服务", "实例元数据"),  # blast 2
    "k8s": ("k8s", "kubernetes", "k8s逃逸", "k8s安全"),  # blast 5
    "escape": ("escape", "container-escape", "container escape", "容器逃逸", "容器逃逸漏洞", "逃逸", "沙箱逃逸"),  # blast 6（门槛线内；含 ctf-007 沙箱逃逸）
    "supply": ("supply", "supply-chain", "supply chain", "供应链", "供应链攻击", "供应链投毒"),  # blast 3
    "prompt": ("prompt", "prompt-injection", "prompt injection", "提示注入", "提示词注入", "间接提示注入"),  # blast 1
    "ios": ("ios", "ios逆向", "ios安全", "iphone逆向"),  # blast 3
    "firmware": ("firmware", "固件", "固件分析", "固件提取"),  # blast 1（ctf-010 中文描述自带“固件”）
    "uart": ("uart", "串口", "串口调试", "uart调试"),  # blast 0（见 DEVIATIONS）
    "sdr": ("sdr", "软件无线电", "无线电", "rf信号"),  # blast 1
    "bluetooth": ("bluetooth", "蓝牙", "蓝牙安全", "ble安全"),  # blast 0（见 DEVIATIONS）
    "wifi": ("wifi", "wi-fi", "wifi破解", "wifi安全", "握手包", "无线破解"),  # blast 1
    "certificate": ("certificate", "证书模板", "证书服务", "ad证书", "adcs"),  # blast 2
    "kerberoasting": ("kerberoasting", "kerberoast", "票据", "票据爆破", "spn爆破"),  # blast 1
    "ntlm": ("ntlm", "ntlm-relay", "ntlm中继", "中继攻击", "哈希传递", "ntlm哈希"),  # blast 2
    "phishing": ("phishing", "spear-phishing", "钓鱼", "钓鱼邮件", "鱼叉钓鱼", "邮件钓鱼"),  # blast 2
    "leak": ("leak", "leakage", "source-leak", "source leak", "数据泄露", "数据泄漏", "信息泄露", "源码泄露", "泄露排查"),  # blast 3
    "log": ("log", "logging", "日志", "日志分析", "日志取证", "日志审计"),  # blast 5
    "ransomware": ("ransomware", "勒索", "勒索软件", "勒索病毒", "勒索分析"),  # blast 0（见 DEVIATIONS）
    "malware": ("malware", "恶意样本", "恶意软件", "病毒分析", "木马分析"),  # blast 2
    "traffic": ("traffic", "协议逆向", "协议分析", "流量分析"),  # blast 2（"pcap"已删：golden-plural-pcaps 要求 pcaps→pcap 直连）
    "javascript": ("javascript", "js逆向"),  # blast 5（裸 js blast 10 超门已删；"js混淆"会吞混淆亦不收）
    "miniprogram": ("miniprogram", "小程序", "微信小程序", "小程序逆向", "wechat", "weixin", "wxapkg"),  # blast 1（目标为开发记录，见 DEVIATIONS）
    "obfuscation": ("obfuscation", "deobfuscation", "混淆", "代码混淆", "加固", "脱壳", "加固绕过"),  # blast 2（含 ai-190 容器加固，见 REPORT）
    # CJK delivery (2026-10-01): ai-fullstack-delivery 交付域 115 组。
    # cjk-delivery3 修订: LCS>=6 中文长语已删(133组值, 见 work/cjk-delivery3/lcs_table.md, 4英slug误伤保留);
    # 补12组通用词(blast<=6逐词实测, 见 REPORT)。裸英文通用词仍不收(只收全 slug)。
    "ai-deployment": ("ai-deployment", "还能回滚"),
    "llm-integration": ("llm-integration", "接大模型", "调用链路", "提示词"),  # 通用词+: 提示词
    "ml-evaluation": ("ml-evaluation", "搭评测集", "评估效果", "上线后效果", "效果变差", "效果下滑", "拿什么衡量", "衡量模型"),  # cjk-delivery4动词式+: 上线后效果/效果变差/效果下滑/拿什么衡量/衡量模型(blast全0, 依据ml-evaluation在线监控性能退化+评估报告模板)
    "model-training": ("model-training",),
    "rag-pipeline": ("rag-pipeline", "rag pipeline", "公司文档", "问答助手", "向量库"),
    "auth-permission": ("auth-permission",),
    "endpoint-design": ("endpoint-design",),
    "error-handling": ("error-handling", "错误码统一", "接口报错"),
    "idempotency-retry": ("idempotency-retry", "幂等和重试", "扣了两次钱", "接口幂等"),
    "openapi-mock": ("openapi-mock",),
    "pagination-filtering": ("pagination-filtering", "列表接口", "翻页筛选"),
    "request-response": ("request-response",),
    "resource-modeling": ("resource-modeling", "抽象成资源", "接口建模"),
    "versioning": ("versioning", "接口要升级", "怎么共存", "版本策略", "版本管理", "接口做版本管理", "老客户端"),  # 通用词+: 版本管理; 防抢专用: 接口做版本管理(C02, 消费"接口"使ctf/hack零候选)
    "webhook-async": ("webhook-async", "通知第三方", "异步通知", "订单状态"),
    "api-contract-testing": ("api-contract-testing", "契约测试"),
    "ci-test-integration": ("ci-test-integration",),
    "coverage-reporting": ("coverage-reporting", "测试覆盖率", "覆盖率数据"),
    "e2e-testing": ("e2e-testing", "端到端测试"),
    "integration-testing": ("integration-testing", "服务联调"),
    "unit-testing": ("unit-testing", "unit testing"),
    "api-implementation": ("api-implementation", "后端实现层"),
    "async-jobs": ("async-jobs", "选啥中间件", "耗时任务"),
    "auth-implementation": ("auth-implementation", "密码加密"),
    "caching-strategy": ("caching-strategy", "更新策略", "不脏读"),
    "data-access": ("data-access",),
    "error-handling-resilience": ("error-handling-resilience", "下游挂了"),
    "microservice-design": ("microservice-design", "微服务边界", "拆微服务", "单体", "拆开", "拆成小服务", "服务边界", "拆服务"),  # cjk-delivery4动词式+: 拆开/拆成小服务/服务边界/拆服务(blast全0, 依据microservice-design单体拆分+DDD限界上下文)
    "observability": ("observability", "两眼一抹黑", "链路追踪"),
    "testing-implementation": ("testing-implementation",),
    "ab-testing": ("ab-testing", "AB 实验", "样本量咋算"),
    "analysis-report": ("analysis-report", "有说服力"),
    "data-visualization": ("data-visualization", "图表怎么选", "看板"),  # 通用词+: 看板
    "metric-design": ("metric-design", "北极星指标", "指标体系", "埋点"),  # 通用词+: 埋点
    "sql-analysis": ("sql-analysis",),
    "data-operations-safety": ("data-operations-safety", "线上改数据", "删库跑路"),
    "index-access-pattern": ("index-access-pattern",),
    "migration-rollout": ("migration-rollout", "大表加字段", "在线迁移"),
    "query-review": ("query-review", "查询评审"),
    "schema-design": ("schema-design",),
    "ci-cd-pipeline": ("ci-cd-pipeline",),
    "container-orchestration": ("container-orchestration",),
    "containerization": ("containerization", "Dockerfile", "镜像瘦身"),
    "monitoring-alerting": ("monitoring-alerting", "告警风暴", "监控"),  # 通用词+: 监控
    "networking-gateway": ("networking-gateway", "多服务入口", "流量转发"),
    "release-strategy": ("release-strategy", "发版总翻车", "回滚预案", "灰度蓝绿"),
    "secrets-config": ("secrets-config",),
    "accessibility-implementation": ("accessibility-implementation", "无障碍检测", "读屏和键盘"),
    "component-architecture": ("component-architecture", "拆分和复用", "越写越耦合", "组件拆分"),
    "data-fetching": ("data-fetching", "请求层封装"),
    "forms-validation": ("forms-validation", "联动校验", "错误提示", "大表单"),
    "mobile-hybrid": ("mobile-hybrid", "内嵌 H5", "混合方案"),
    "performance-optimization": ("performance-optimization", "前端性能", "首屏打开"),
    "routing-navigation": ("routing-navigation", "多页面跳转", "权限拦截"),
    "state-management": ("state-management", "跨组件状态"),
    "styling-system": ("styling-system", "样式体系"),
    "testing-frontend": ("testing-frontend", "页面测试"),
    "api-frontend-integration": ("api-frontend-integration", "前后端联调"),
    "auth-e2e": ("auth-e2e", "全链路打通", "各端鉴权", "注册登录"),
    "database-schema-impl": ("database-schema-impl", "顺序和实现", "一起落地"),
    "deploy-preview": ("deploy-preview", "产品预览", "在线链接", "预览环境"),
    "fullstack-architecture": ("fullstack-architecture",),
    "customer-journey": ("customer-journey", "卡点怎么找", "旅程地图"),
    "mvp-scoping": ("mvp-scoping", "范围怎么砍"),
    "opportunity-tree": ("opportunity-tree", "机会树"),
    "pol-probe": ("pol-probe", "用户真要啥", "验证和试探", "轻量验证"),
    "positioning": ("positioning", "差异化卖点", "产品定位"),
    "user-story": ("user-story", "user story", "用户故事拆", "故事点估", "验收标准"),
    "change-control": ("change-control", "需求天天变"),
    "critical-path": ("critical-path", "关键路径"),
    "handoff-protocol": ("handoff-protocol", "上下游交接", "交接协议"),
    "milestone-gate": ("milestone-gate", "milestone gate", "里程碑评审", "准入准出", "门禁标准"),
    "orchestration": ("orchestration", "多线程协同", "工作线并行"),
    "progress-tracking": ("progress-tracking", "进度汇报"),
    "retrospective": ("retrospective", "开成甩锅会", "回顾会议"),
    "risk-management": ("risk-management", "风险登记"),
    "acceptance-testing": ("acceptance-testing",),
    "api-testing": ("api-testing",),
    "performance-testing": ("performance-testing", "系统扛不住", "压测方案"),
    "quality-gate": ("quality-gate",),
    "regression-testing": ("regression-testing", "回归到半夜", "回归范围"),
    "risk-based-testing": ("risk-based-testing",),
    "test-case-design": ("test-case-design", "覆盖思路"),
    "test-data-management": ("test-data-management", "数据构造"),
    "test-report": ("test-report", "结论和风险"),
    "test-strategy": ("test-strategy",),
    "auth-security-audit": ("auth-security-audit", "怕有漏洞", "登录鉴权"),
    "dependency-audit": ("dependency-audit", "依赖爆漏洞", "依赖审计"),
    "security-report": ("security-report", "漏洞等级"),
    "threat-modeling": ("threat-modeling", "威胁建模"),
    "web-vulnerability": ("web-vulnerability", "漏洞长啥样", "研发自查", "自查清单"),
    "capacity-planning": ("capacity-planning", "容量评估", "扩容计划", "容量", "要不要扩容", "扛不住", "机器不够", "并发上不去"),  # cjk-delivery4动词式+: 要不要扩容/扛不住/机器不够/并发上不去(blast全0, 依据capacity-planning日常扩缩容决策+容量评估公式)
    "incident-response": ("incident-response", "应急响应", "手忙脚乱", "止血流程", "事故"),  # 通用词+: 事故(C09第二证据, 266/269记录原文共有, ctf零含)
    "log-analysis": ("log-analysis", "日志海量"),
    "on-call-runbook": ("on-call-runbook", "值班手册", "半夜被叫"),
    "postmortem": ("postmortem", "复盘总敷衍", "复盘报告", "不甩锅", "复盘"),  # 通用词+: 复盘
    "reliability-engineering": ("reliability-engineering", "可靠性目标", "错误预算", "SLA"),
    "api-documentation": ("api-documentation", "文档总过期", "接口文档"),  # 通用词+: 接口文档
    "architecture-doc": ("architecture-doc", "新人看不懂", "架构讲不清", "项目文档"),  # 通用词+: 项目文档
    "postmortem-doc": ("postmortem-doc", "后人避坑", "文档沉淀"),
    "release-notes": ("release-notes", "变更记录", "更新日志", "迭代记录", "改了什么", "记在哪", "更新说明", "改动记录"),  # cjk-delivery4动词式+: 迭代记录/改了什么/记在哪/更新说明/改动记录(blast全0, 依据release-notes Changelog+change-control变更决策记录)
    "user-guide": ("user-guide", "用户手册", "重复问题"),
    "accessibility": ("accessibility",),
    "atomic-design": ("atomic-design",),
    "component-states": ("component-states", "状态画不全"),
    "design-handoff": ("design-handoff", "交付和标注", "还原不了"),
    "design-system-mapping": ("design-system-mapping", "映射和迁移"),
    "design-tokens": ("design-tokens",),
    "enterprise-patterns": ("enterprise-patterns", "B 端后台"),
    "information-architecture": ("information-architecture", "信息架构"),
    "page-structure": ("page-structure", "布局和结构"),
    "responsive-design": ("responsive-design", "响应式布局", "断点怎么定"),
    "usability-evaluation": ("usability-evaluation", "可用性评估"),
    "user-flow": ("user-flow", "任务流程图", "流程里迷路"),
    "visual-style": ("visual-style", "调性怎么定", "界面土气", "视觉风格"),
    # 2026-10-01: the hack-diag card measured 12 topics that the table could not
    # reach at all (0/2 on both Chinese and English hints). Five of them turn out
    # to have no registry record whatsoever (thinkphp/spring/shiro/log4j/fastjson
    # -> 0/293), so no alias can help those. The eight below DO have records
    # (community-hack-skills-{057,064,078,100,104,125,132} and
    # community-ctf-super-hub-{019,028}); only the vocabulary was missing.
    # Keys are the exact slugs that appear in those records' registry ``keywords``.
    # ``upload`` is deliberately absent: the golden pin ``x-gap-upload`` freezes it.
    "csrf": ("csrf", "cross-site request forgery", "跨站请求伪造", "伪造请求", "csrf token"),  # hack-alias1合并：英文全称+中文；blast 3/0/3
    "websocket-security": ("websocket-security", "websocket", "cswsh", "ws 劫持", "websocket 安全"),
    "heap-exploitation": ("heap-exploitation", "heap", "堆漏洞", "堆利用", "ptmalloc"),
    "tunneling-and-pivoting": ("tunneling-and-pivoting", "tunneling", "pivoting", "隧道", "内网穿透", "端口转发"),
    "cmdi-command-injection": ("cmdi-command-injection", "cmdi", "command injection", "命令注入", "命令执行"),
    "path-traversal-lfi": ("path-traversal-lfi", "path traversal", "lfi", "目录穿越", "路径穿越", "文件包含"),
    "nosql-injection": ("nosql-injection", "nosql", "nosql 注入", "mongo 注入", "mongo查询注入"),
    "csv-formula-injection": ("csv-formula-injection", "csv injection", "csv 注入", "表格公式注入"),
    # CJK alias (2026-10-01): hack-alias1 零覆盖 13 组（csrf 见上方合并行）。blast=加别名前单测 community matches 数，全<=6；依据见 work/hack-alias1/WORDS.md。
    "csv": ("csv", "csv注入", "表格公式注入", "公式注入"),  # blast 2/0/0；依据 csv-formula-injection（CSV spreadsheet formula injection）
    "websocket": ("websocket", "websocket劫持", "websocket安全", "长连接"),  # blast 1/2/0；依据 websocket-security（WebSocket handshake CSWSH）
    "heap": ("heap", "堆漏洞", "堆利用", "堆溢出"),  # blast 0/1/0；依据 heap-exploitation（Heap exploitation UAF double free）
    "tunnel": ("tunnel", "tunneling", "pivoting", "隧道", "内网穿透", "端口转发"),  # blast 0；依据 tunneling-and-pivoting（Tunneling and pivoting SSH tun）
    "cmdi": ("cmdi", "command-injection", "command injection", "命令注入", "命令执行", "分隔符执行"),  # blast 0；依据 cmdi-command-injection（Command injection shell commands）
    "traversal": ("traversal", "path-traversal", "目录穿越", "路径遍历"),  # blast 3/0；依据 path-traversal-lfi（Path traversal and LFI）
    "nosql": ("nosql", "nosql注入", "mongo注入"),  # blast 2/1；依据 nosql-injection（NoSQL injection MongoDB-style）
    "thinkphp": ("thinkphp", "thinkphp注入"),  # blast 0/1；依据 sqli-sql-injection（ThinkPHP5 array key injection）
    "spring": ("spring", "spring注入", "spring表达式注入"),  # blast 2/3/2；依据 expression-language-injection（SpEL SPRING EXPRESSION LANGUAGE）
    "shiro": ("shiro", "shiro反序列化", "shiro默认密钥"),  # blast 0/2/0；依据 deserialization-insecure（Apache Shiro rememberMe Deserialization SHIRO-550）
    "log4j": ("log4j", "log4shell", "log4j注入"),  # blast 0/0/1；依据 jndi-injection（Log4j2 Log4Shell CVE-2021-44228）
    "fastjson": ("fastjson", "fastjson反序列化"),  # blast 1/2；依据 deserialization-insecure（Fastjson @type gadget）
    # CJK alias (2026-10-01): hack-alias2 高频口语第二批 6 组。blast=加别名前单测 community matches 数，全<=6；依据见 work/hack-alias2/PLAN.md。
    # 英文桥一律用目标记录 description 原有词（cgroup/keychain/etcd/toctou/out-of-band），不用全 slug，
    # 避免长字面吞掉已有短别名在记录侧的匹配（sqli 全 slug 曾把 alias_sqli+alias_web 顶掉，排名门即挂）。
    # race 不收 race-condition 英文值（race 键已有，避免 LOOKUP 覆盖）；authbypass 域 ALIASES 零覆盖，全 slug 安全。
    "container-escape-techniques": ("cgroup", "逃出去"),  # blast 0；依据 container-escape-techniques（cgroup abuse；逃出去沙箱 0）
    "ios-pentesting-tricks": ("keychain", "苹果端", "苹果"),  # blast 0/0；依据 ios-pentesting-tricks（keychain extraction；苹果端怎么测 0）
    "kubernetes-pentesting": ("etcd", "集群"),  # blast 2；依据 kubernetes-pentesting（etcd access；集群安全怎么搞非直达）
    "race-condition": ("toctou", "并发", "抢券"),  # blast 并发1（误入 ai 域）/抢券0；依据 race-condition（Race condition and TOCTOU；并发抢券 0）
    "sqli-sql-injection": ("out-of-band", "拼接", "拼接sql"),  # blast 0/3；依据 sqli-sql-injection（out-of-band execution；有没有拼接SQL 仅通用 sql）
    "authbypass-authentication-flaws": ("authbypass-authentication-flaws", "绕过登录"),  # blast 0；依据 authbypass-authentication-flaws（怎么绕过登录 0）
    # CTF/APK diag (2026-10-01): 诊断卡 work/ctf-apk-diag/REPORT.md §4-A 类。只新增键，旧键一字不动；
    # 报告要求"给 ctf 值表追加"的入口词改由 ctf-entry 新键承载。去重：堆溢出→heap、脱壳→obfuscation 已有，不收。
    "ctf-entry": ("入门", "组队", "分工", "攻略", "战队", "靶场", "题解", "刷题", "做题", "解题", "夺旗流程", "新手村", "密码手"),  # 去掉新手：golden x-gap-beginner冻结"bare新手入口零候选"，新手在3条记录描述里有覆盖会造候选；入口意图master侧由R47-a承接（exclude入口保pin）
    "pwn": ("pwn", "pwn题", "栈溢出", "uaf"),  # 去掉ret2libc：ranking DESCRIPTION_ONLY要求ret2libc纯描述命中（ctf-pwn名含pwn，alias_pwn会造name hit）；pwn题照样经pwn桥到记录
    "misc": ("misc", "流量包", "取证题", "频谱"),  # 去掉隐写：ranking DESCRIPTION_ONLY要求隐写分析纯描述命中（ctf-misc名含misc，alias_misc会造name hit）；流量包/取证题照样桥到ctf-misc/取证记录
    "crypto": ("crypto", "古典密码", "RSA"),
    "writeup": ("writeup", "题解"),
    "emulator": ("模拟器", "模拟器检测"),
    "permission": ("权限", "危险权限", "权限分析"),
    # resign键整组删除：值（重签名/重新签名/改包名）0记录覆盖，只起稀释作用（confidence分母+1），把golden x-r49-resign从matched拉到needs_review；master侧R49 rule2已收重签名/改包名，能力不丢
    "unpack": ("加壳", "梆梆", "脱壳机"),
    "pinning": ("证书绑定", "证书校验", "ssl pinning"),
    "debloater": ("去广告", "debloat", "瘦身", "sdk移除"),
    # CTF 入门 recall2 (2026-10-01): C01-C10 社区入门 2/10→5/10。只新增键，旧键一字不动。
    # 机理: 双方中文词折叠到同一 alias 即 _score+1(中文按连续串捕获, 不切分子串永不出 token)。
    # key 均为 registry 真实触发名 slug(对应记录 keywords 实测存在); value 全新词, 不复用任何已有值:
    # “分工”已在 ctf-entry, 这里用“怎么分工/人员分工”长词避让(最长优先命中新键, ctf-entry 映射保留)。
    # blast(加桥前单测 community matches): 头脑风暴1/整理0/适合0/怎么分工1/人员分工1/分流0, 全<=6。
    # C01/C09/C10 记录侧零覆盖无桥可搭, 诚实维持(见 work/ctf-recall2/PLAN.md §3)。
    "brainstorming": ("头脑风暴",),  # -001 名+描述、-003/-011 描述; C08 1/3→2/5=0.4
    "ctf-writeup": ("整理",),  # -013 描述“整理成结构化”; C05 1/3→2/5=0.4
    "ctf-beginner-hub": ("适合",),  # -001/-003/-011/-013/-016 描述“适合…”; C03 1/4→2/5=0.4
    "ctf-super-hub": ("怎么分工", "分流"),  # -003/-011“自动分流”; C04 1/7→2/8(“人员分工”会给 C07 +分母不加分, 拒收)
    # community-T1 batch1 (13组; N108转signal: jwt-abuse吞alias_jwt致golden-api-auth红)
    "bypass-techniques": ("bypass-techniques", "输错几次", "换个方式"),  # N101
    "active-directory-certificate-services": ("active-directory-certificate-services", "管发证", "找它领"),  # N103
    "active-directory-kerberos-attacks": ("active-directory-kerberos-attacks", "冒充别人", "真进了"),  # N104
    "ai-ml-security": ("ai-ml-security", "传个特殊", "开始胡说"),  # N105
    "anti-debugging-techniques": ("anti-debugging-techniques", "动调跟进", "甩掉"),  # N107
    "api-auth-and-jwt-abuse": ("header spoofing", "改几个字符", "过期也不"),  # N108(避吞alias_jwt/alias_api, 用描述独有短语桥)
    "arbitrary-write-to-rce": ("arbitrary-write-to-rce", "写歪了一", "顺着写"),  # N111
    "attack-surface-mapping": ("attack-surface-mapping", "边边角角", "列个表"),  # N112
    "browser-exploitation-v8": ("browser-exploitation-v8", "打开特定", "解析出问"),  # N115
    "code-obfuscation-deobfuscation": ("code-obfuscation-deobfuscation", "故意搅过", "理顺再看"),  # N119
    "cors-cross-origin-misconfiguration": ("cors-cross-origin-misconfiguration", "这边全收", "来路检查"),  # N120
    "crlf-injection": ("crlf-injection", "加个换行", "跳过去"),  # N121
    "csp-bypass-advanced": ("csp-bypass-advanced", "防护策略", "换种写法"),  # N122
    "csrf-cross-site-request-forgery": ("csrf-cross-site-request-forgery", "一次性的", "把密码改"),  # N123(避"点一下"被N268含入)
    "dangling-markup-injection": ("dangling-markup-injection", "没闭合", "被带歪"),  # N124
    # community-T1 batch2 (15组, blast全0)
    "dependency-confusion": ("dependency-confusion", "抢注了个", "拉下来"),  # N125
    "deserialization-insecure": ("deserialization-insecure", "特制的文件", "解开它"),  # N126
    "dns-rebinding-attacks": ("dns-rebinding-attacks", "读内网", "当跳板"),  # N127
    "expression-language-injection": ("expression-language-injection", "插表达式", "真给算"),  # N128
    "file-access-vuln": ("file-access-vuln", "换成别的", "吐出来"),  # N129
    "hash-attack-techniques": ("hash-attack-techniques", "老算法", "跑一跑"),  # N132
    "http-parameter-pollution": ("http-parameter-pollution", "写两遍", "后面那个"),  # N135
    "kernel-exploitation": ("kernel-exploitation", "写内核", "碰到核心"),  # N140
    "linux-lateral-movement": ("linux-lateral-movement", "借它的", "碰旁边"),  # N142
    "llm-prompt-injection": ("llm-prompt-injection", "特殊的话", "照着做"),  # N145
    "mobile-ssl-pinning-bypass": ("mobile-ssl-pinning-bypass", "挂代理", "认我的证"),  # N149
    "network-protocol-attacks": ("network-protocol-attacks", "私有的", "对出来"),  # N150
    "oauth-oidc-misconfiguration": ("oauth-oidc-misconfiguration", "第三方账", "能被伪造"),  # N153
    "prototype-pollution": ("prototype-pollution", "加属性", "污染到"),  # N156
    "recon-for-sec": ("recon", "公开能查", "列个清单"),  # N158(for被strip, 用recon桥; 目标名命中+3压描述+1)
    "request-smuggling": ("desynchronization", "理解不一", "夹带的"),  # N159(避复写smuggling旧映射, 用描述独有词桥)
    "reverse-shell-techniques": ("reverse-shell-techniques", "弹个能交", "换条路"),  # N160
    "saml-sso-assertion-attacks": ("saml-sso-assertion-attacks", "返回的断", "混进去"),  # N161
    "smart-contract-vulnerabilities": ("smart-contract-vulnerabilities", "调个函数", "变到自己"),  # N162
    "ssrf-server-side-request-forgery": ("ssrf-server-side-request-forgery", "预览链接", "吐回来"),  # N164
    "ssti-server-side-template-injection": ("ssti-server-side-template-injection", "插代码", "那边跑"),  # N165
    "stack-overflow-and-rop": ("stack-overflow", "超长就崩", "回去的链"),  # N166(and被strip, 改用stack-overflow自桥)
    "subdomain-takeover": ("subdomain-takeover", "解析到外", "接过来"),  # N167
    "unauthorized-access-common-services": ("unauthorized-access-common-services", "没设密码", "直接连"),  # N170
    "web-cache-deception": ("web-cache-deception", "清缓存", "缓存串"),  # N173
    "windows-av-evasion": ("windows-av-evasion", "开着防护", "换个样子"),  # N175
    "windows-lateral-movement": ("windows-lateral-movement", "都不通", "往深处走"),  # N176
    "xslt-injection": ("xslt-injection", "特殊格式", "内容不对"),  # N178
    "xss-cross-site-scripting": ("xss-cross-site-scripting", "留的东西", "弹了奇怪"),  # N179
    # community-T1 batch4 (7组, blast全0; ai锅炉板7条转signals, 见PLAN §5)
    "e2e-feature-delivery": ("e2e-feature-delivery", "七八道手", "老返工"),  # N214
    "code-security-review": ("code-security-review", "过一遍", "留口子"),  # N233
    "ctf-crypto": ("ctf-crypto", "看不懂的", "手工解太"),  # N254
    "ctf-malware": ("ctf-malware", "睡半小时", "等超时"),  # N256
    "strix-csrf": ("strix-csrf", "让管理员", "构造个页"),  # N268(避"点一下"与N123合流)
    "strix-httpx": ("strix-httpx", "还活着", "状态码"),  # N270
    "strix-nuclei": ("strix-nuclei", "指纹模板", "中招的"),  # N275
    # cardB (2026-10-02) 数据桥域：把题面里的中文说法折到记录侧已有的规范 token 上。
    # 机理（源码级）：normalize() 对提示侧与记录侧做同一次替换，所以一条可命中的桥
    # 必须双边存在——①本字典新增一个题面真出现的中文说法；②目标记录的
    # legacy_original_name / path / keywords 里带着 canonical 字面本身。
    # ②对本批 21 条目标记录**天然已满足**：它们的 legacy_original_name 就是自身
    # slug（hack-skills 一律 slug 命名，ai-fullstack 的 159/171/190/212/216/238/272 同理），
    # 故 registry.json 无需改动，全部改动集中在本字典。blast=该 canonical 折叠后
    # 记录侧命中的记录数（alias 级实测，逐条贴数于 work/round1-verify/lab-cardB/），
    # 全部 <= 6；中文说法与 300 条题面的最长公共连续汉字同样逐条实测，全部 < 6。
    # 均为纯追加，未改动任何既有键、值、顺序。
    "cmdi-command-injection": ("cmdi-command-injection", "cmdi", "command injection", "命令注入", "命令执行", "文件名"),  # blast 1（hack-skills-057）；+文件名 → N118
    "path-traversal-lfi": ("path-traversal-lfi", "path traversal", "lfi", "目录穿越", "路径穿越", "文件包含", "跳目录"),  # blast 4；+跳目录 → N155
    "waf-bypass-techniques": ("waf-bypass-techniques", "换种编码"),  # blast 1（hack-skills-130）；→ N172
    "linux-privilege-escalation": ("linux-privilege-escalation", "定时跑"),  # blast 1（hack-skills-092）；→ N143
    "windows-privilege-escalation": ("windows-privilege-escalation", "变成管理员"),  # blast 1（hack-skills-135）；→ N177
    "macos-process-injection": ("macos-process-injection", "塞了东西"),  # blast 1（hack-skills-095）；→ N146
    "format-string-exploitation": ("format-string-exploitation", "格式化输出"),  # blast 1（hack-skills-073）；→ N130
    "idor-broken-object-authorization": ("idor-broken-object-authorization", "换成别人的"),  # blast 1（hack-skills-082）；→ N136
    "ntlm-relay-coercion": ("ntlm-relay-coercion", "旧协议"),  # blast 1（hack-skills-101）；→ N152
    "jndi-injection": ("jndi-injection", "系统自带的"),  # blast 1（hack-skills-086）；→ N138
    "upload-insecure-files": ("upload-insecure-files", "只看了后缀"),  # blast 1（hack-skills-128）；→ N171
    "traffic-analysis-pcap": ("traffic-analysis-pcap", "交换机上"),  # blast 1（hack-skills-124）；→ N168
    "linux-security-bypass": ("linux-security-bypass", "调用方法"),  # blast 1（hack-skills-093）；→ N144
    "macos-security-bypass": ("macos-security-bypass", "落上去了"),  # blast 1（hack-skills-096）；→ N147
    "ctf-reverse": ("ctf-reverse", "转逻辑"),  # blast 1（ctf-super-hub-010）；→ N260
    "e2e-testing": ("e2e-testing", "端到端测试", "从头来"),  # blast 1（ai-159）；+从头来 → N193
    "microservice-design": ("microservice-design", "微服务边界", "拆微服务", "单体", "拆开", "拆成小服务", "服务边界", "拆服务", "切成小块"),  # blast 1（ai-171）；+切成小块 → N197
    "containerization": ("containerization", "Dockerfile", "镜像瘦身", "镜像和配置"),  # blast 1（ai-190）；+镜像和配置 → N203
    "fullstack-architecture": ("fullstack-architecture", "搅在一起"),  # blast 1（ai-216）；+搅在一起 → N215
    "progress-tracking": ("progress-tracking", "进度汇报", "统一看板"),  # blast 1（ai-238）；+统一看板 → N224
    "api-documentation": ("api-documentation", "文档总过期", "接口文档", "没文档"),  # blast 1（ai-272）；+没文档 → N242
    # cardB 未做成（如实登记，不硬塞）：N131/hack-skills-075、N180/hack-skills-138、
    # N213/ai-212。桥本身两侧都成立（各自 name view 命中 rank=3），但同一 wrapper 内
    # 另有 4–6 条同 rank=3 的记录（题面里的“接口”折成 alias_api，落在它们的**名字**上），
    # 按 _reference_sort_key 的 path 末位把它们压在前面，REFERENCE_LIMIT=3 一截就掉出去了。
    # 要救只能动 REFERENCE_LIMIT 或给目标再加命中，两者都属硬约束禁止项，故维持 miss。
}

# The adapter injects these into every entry; they must not create matches.
#
# T26 (D6): ``community-raw`` and ``skills-hub`` are importer provenance, not
# capability vocabulary. They were carried by all 293 records (every ``path``
# starts with ``community-raw/`` and every keyword list repeats ``skills-hub``),
# so they matched every record and could discriminate nothing. Listing them as
# stopwords is the same rule as every other entry above: a word the adapter
# injects everywhere must not create a match. ``workflow`` is already listed
# here, which is what makes the D5 strip below necessary.
#
# T26 follow-up wave: ``adapted`` and ``capability`` are the two words of the
# synthetic description the adapter wrote -- exactly 30 of the 293 records carry
# the literal string "Adapted capability from workflows/<path>." and nothing
# else, so both words are pure description boilerplate. Measured per-source
# fraction: 30/154 = 19% of ai-fullstack-delivery, and 0/35, 0/103 and 0/1 of
# ctf-super-hub, hack-skills and apk-reverse-community -- so "30/30 of one
# source" is FALSE and no source even has 30 records. Both words appear in the
# routing text of 30/293 records and in the *name* text of 0/293, so stopping
# them removes a description-only hit and cannot orphan a record's own slug.
#
# They therefore may NOT be expressed as ``noise[]`` entries: design-freeze
# rule 1.3 admits a noise pattern only at >= 80% of the records of one source,
# and 19% is far below that. An earlier wave reported "30/30 of one source" and
# was wrong. STOPWORDS is the correct home for them for the same reason the two
# entries above live here: a word the adapter injects into a description is
# provenance/boilerplate, not capability vocabulary.
#
# U9: ``融合`` joins them on the separate ground that it is a template-grade
# connective, not capability vocabulary. Measured: 56/154 = 36% of
# ai-fullstack-delivery legacy_descriptions carry it in the fixed frame
# "融合 <method A> + <method B>" (backend-engineer workflow prose), so as a
# routing token it discriminates nothing -- 42 candidates in a pure
# description-only tie at rank 1, led path-first by an arbitrary API record at
# matched/confidence 1.0. No record owns it as a subject (it is a verb
# describing how the document was composed, never the capability), and 36% is
# below the noise[] >= 80% admission rule, so STOPWORDS -- which has no 80%
# rule -- is the mechanism. Multi-word hints still route on their other terms;
# a future record genuinely ABOUT blending/integration must be reached by a
# curated signal, not by this bare connective.
STOPWORDS = {
    "project", "skills", "skill", "hub", "upstream", "community", "source",
    "methodology", "workflow", "workflows", "use", "used", "using", "task",
    "tasks", "this", "that", "with", "from", "for", "and", "the", "into", "token",
    "community-raw", "skills-hub", "adapted", "capability", "融合",
}

# Matching lexicon only. Paths, route ids, references and downstream capabilities
# come from registry.json.wrappers[] (spec 1.4 blocker: "wrapper/downstream
# relations hardcoded in the helper").
WRAPPER_ALIASES: dict[str, set[str]] = {
    "ctf-super-hub": {"ctf", "reverse", "web", "api", "apk", "jwt", "ssrf"},
    "hack-skills": {"web", "api", "jwt", "ssrf", "reverse"},
    "ai-fullstack-delivery": {"delivery"},
    "apk-reverse-community": {"apk", "reverse"},
}

class RegistryError(Exception):
    """A fail-closed condition with an explicit 4.7 status."""

    def __init__(self, status: str, detail: str, failure_reason: str | None = None, **extra: Any) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.failure_reason = failure_reason
        self.extra = extra

def _alias_regex() -> tuple[re.Pattern[str], dict[str, str]]:
    variants: list[tuple[str, str]] = []
    lookup: dict[str, str] = {}
    for canonical, values in ALIASES.items():
        for value in values:
            variants.append((canonical, value))
            lookup[value.casefold()] = canonical
    variants.sort(key=lambda pair: len(pair[1]), reverse=True)
    expressions = []
    for _, value in variants:
        escaped = re.escape(value)
        # Avoid matching ``api`` inside unrelated words such as ``capability``.
        if re.search(r"[a-z]", value, re.IGNORECASE):
            escaped = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
        expressions.append(escaped)
    expression = "|".join(expressions)
    return re.compile(expression, re.IGNORECASE), lookup

ALIAS_RE, ALIAS_LOOKUP = _alias_regex()

# T26 (D5): the stopword list must be applied BEFORE the alias substitution, or a
# listed stopword can never be stopped. ``normalize()`` used to rewrite the whole
# text first, so ``workflow`` became ``alias_delivery`` and the STOPWORDS filter
# below never saw the word it was supposed to reject -- ``tokens("workflow")``
# returned ``{'alias_delivery'}`` and 154 ai-fullstack records answered
# ``workflow``/``delivery``/``交付`` at confidence 1.0. Stripping the stopword from
# the word-form first makes ``tokens("workflow") == set()``. The hyphenated
# provenance entries are matched as whole literals (longest first), so
# ``community-raw`` is removed as one token and never partially as ``community``.
STOPWORD_RE = re.compile(
    r"(?<![a-z0-9])(?:" + "|".join(re.escape(word) for word in sorted(STOPWORDS, key=len, reverse=True))
    + r")(?![a-z0-9])"
)

def normalize(text: str) -> str:
    value = unicodedata.normalize("NFKC", text or "").lower()
    # Replace with a space, never with "", so that removing a stopword cannot glue
    # its neighbours into one new token (``...使用workflow交付...``).
    value = STOPWORD_RE.sub(" ", value)
    # One combined substitution prevents a replacement such as ``alias_ssrf``
    # from being matched again by the ``ssrf`` alias.
    return ALIAS_RE.sub(lambda match: f" alias_{ALIAS_LOOKUP[match.group(0).casefold()]} ", value)

# T26: ``short_tokens`` from routing-signals.json admits exactly its own literals
# at a length the global minimum (3) still governs for everything else. It is a
# module global because ``tokens()`` is also called directly by the read-only
# measurement harness; ``load_signals()`` refreshes it on every ``lookup()``.
SHORT_TOKENS: set[str] = set()

# T26: ``token_aliases`` from routing-signals.json, folded symmetrically onto the
# hint side and inside ``routing_view`` (never inside ``_score``, whose evidence
# breadth stays on the strict token set).
TOKEN_ALIASES: dict[str, str] = {}

# Compiled ``noise[]`` entries as ``(pattern, scope)``, and the ``signals[]``
# indexed by the registry record id they are allowed to fire for. Both start
# empty so that an un-loaded (or empty) layer is a no-op rather than a crash.
NOISE_PATTERNS: list[tuple[str, str]] = []
SIGNALS_BY_ID: dict[str, list[dict[str, Any]]] = {}
SIGNAL_LAYER: dict[str, Any] | None = None

class SignalLayer:
    """Validated view over the frozen ``routing-signals.json`` contract.

    Every array may be empty (that is the shipped skeleton and it is a valid
    state); every array that is NOT empty must hold well-formed entries, and an
    uncompilable regex or an unknown scope fails closed instead of being ignored.
    Evidence and the noise-justification rule are the verifier's
    responsibility (``skills/scripts/verify-routing-signals.py``), not this
    consumer's: the engine only needs the matching semantics.
    """

    def __init__(self, document: dict[str, Any], digest: str) -> None:
        self.document = document
        self.digest = digest
        self.token_aliases: dict[str, str] = {}
        self.short_tokens: set[str] = set()
        self.noise: list[tuple[str, str]] = []
        self.signals: dict[str, list[dict[str, Any]]] = {}
        self._validate()

    def _validate(self) -> None:
        problems: list[str] = []
        p = problems.append
        if self.document.get("schemaVersion") != SIGNALS_SCHEMA_VERSION:
            p(f"signals.schemaVersion must be {SIGNALS_SCHEMA_VERSION}, "
              f"got {self.document.get('schemaVersion')!r}")
        for key in ("token_aliases", "short_tokens", "noise", "signals"):
            if key not in self.document:
                p(f"signals missing {key}")

        aliases = self.document.get("token_aliases") or {}
        if not isinstance(aliases, dict):
            p("signals.token_aliases must be an object")
        else:
            for token, canonical in aliases.items():
                if token != str(token).lower() or canonical != str(canonical).lower():
                    p(f"signals.token_aliases {token!r}->{canonical!r} must be lowercase")
                elif not re.fullmatch(r"[a-z][a-z0-9-]*", str(token)):
                    p(f"signals.token_aliases key {token!r} must be a lowercase token")
                elif not re.fullmatch(r"[a-z][a-z0-9-]*", str(canonical)):
                    p(f"signals.token_aliases value {canonical!r} must be a lowercase token")

        short = self.document.get("short_tokens") or []
        if not isinstance(short, list):
            p("signals.short_tokens must be an array")
        else:
            for literal in short:
                if not re.fullmatch(r"[a-z][a-z0-9-]*", str(literal)):
                    p(f"signals.short_tokens entry {literal!r} must be a lowercase token")

        noise = self.document.get("noise") or []
        if not isinstance(noise, list):
            p("signals.noise must be an array")
        else:
            for index, entry in enumerate(noise):
                where = f"signals.noise[{index}]"
                if not isinstance(entry, dict):
                    p(f"{where} must be an object")
                    continue
                if entry.get("scope") not in {"any", "description"}:
                    p(f"{where}.scope must be 'any' or 'description', got {entry.get('scope')!r}")
                try:
                    re.compile(str(entry.get("pattern", "")))
                except re.error as error:
                    p(f"{where}.pattern does not compile: {error}")

        signals = self.document.get("signals") or []
        if not isinstance(signals, list):
            p("signals.signals must be an array")
        else:
            for index, signal in enumerate(signals):
                where = f"signals.signals[{index}]"
                if not isinstance(signal, dict):
                    p(f"{where} must be an object")
                    continue
                signal_id = signal.get("id")
                if not signal_id:
                    p(f"{where}.id must name a registry record")
                    continue
                must = signal.get("must") or []
                if not isinstance(must, list) or not must:
                    p(f"{where}.must must hold 1..16 regexes")
                    continue
                compiled_must: list[re.Pattern[str]] = []
                for pattern in must:
                    try:
                        compiled_must.append(re.compile(str(pattern), re.IGNORECASE))
                    except re.error as error:
                        p(f"{where}.must entry does not compile: {error}")
                compiled_exclude: list[re.Pattern[str]] = []
                for pattern in signal.get("exclude") or []:
                    try:
                        compiled_exclude.append(re.compile(str(pattern), re.IGNORECASE))
                    except re.error as error:
                        p(f"{where}.exclude entry does not compile: {error}")
                if not signal.get("note"):
                    p(f"{where}.note must explain the signal to a human")
                if compiled_must:
                    self.signals.setdefault(str(signal_id), []).append({
                        "id": str(signal_id),
                        "must": compiled_must,
                        "exclude": compiled_exclude,
                        "note": str(signal.get("note", "")),
                    })

        if problems:
            raise RegistryError("blocked", "routing-signals contract violation", "schema_invalid",
                                violations=problems[:10], violation_count=len(problems))
        self.token_aliases = {str(k): str(v) for k, v in (aliases or {}).items()}
        self.short_tokens = {str(literal) for literal in (short or [])}
        self.noise = [(str(entry.get("pattern", "")), str(entry.get("scope", "any")))
                      for entry in (noise or []) if isinstance(entry, dict)]
        # Deterministic firing order so ``signal_hits`` is reproducible.
        for records in self.signals.values():
            records.sort(key=lambda signal: signal["id"])

def _publish_signals(layer: SignalLayer) -> SignalLayer:
    """Install a validated layer into the tokeniser's module-level state."""
    global SIGNAL_LAYER, NOISE_PATTERNS, SIGNALS_BY_ID, SHORT_TOKENS, TOKEN_ALIASES
    SIGNAL_LAYER = layer
    NOISE_PATTERNS = layer.noise
    SIGNALS_BY_ID = layer.signals
    SHORT_TOKENS = set(layer.short_tokens)
    TOKEN_ALIASES = dict(layer.token_aliases)
    return layer

def tokens(text: str) -> set[str]:
    value = normalize(text)
    found = set(re.findall(r"alias_[a-z0-9-]+|[a-z][a-z0-9-]{2,}|[\u4e00-\u9fff]{2,}", value))
    if SHORT_TOKENS:
        # Only the declared literals become eligible, so the global minimum of 3
        # characters is unchanged for every other token.
        pattern = r"(?<![a-z0-9])(?:" + "|".join(
            re.escape(literal) for literal in sorted(SHORT_TOKENS, key=len, reverse=True)) + r")(?![a-z0-9])"
        found.update(re.findall(pattern, value))
    return {token for token in found if token not in STOPWORDS}

def fold_aliases(term_set: set[str]) -> set[str]:
    """Symmetric ``token_aliases`` fold: applied to the hint and to each view."""
    if not TOKEN_ALIASES:
        return set(term_set)
    return set(term_set) | {TOKEN_ALIASES[token] for token in term_set if token in TOKEN_ALIASES}

def routing_view(text: str) -> set[str]:
    """The one view used for candidacy AND for both hit classes (T26 / D1).

    A hyphenated slug is a single token for the tokeniser (``prototype-
    pollution``, ``BloodHound-guided``) and an aliased slug keeps its suffix
    (``alias_ssrf-server-side-request-forgery``), so both hide a match the caller
    plainly made. The view therefore adds the hyphen parts, the alias prefix and
    the symmetric alias fold.

    ``text`` must already be noise-stripped for a record (see ``_record_views``)
    and must never be noise-stripped for the hint.
    """
    found = tokens(text)
    view = set(found)
    for token in found:
        if token.startswith("alias_") and "-" in token:
            view.add(token.split("-", 1)[0])
        view.update(part for part in token.split("-") if part)
    return fold_aliases(view)

def _legacy(item: dict[str, Any], key: str, default: Any = "") -> Any:
    return (item.get("extensions") or {}).get(key, default)

def _reference_text(item: dict[str, Any]) -> str:
    return " ".join(str(value) for value in (
        _legacy(item, "legacy_original_name"), _legacy(item, "legacy_description"),
        item.get("path", ""), item.get("source_path", ""),
    )) + " " + " ".join(str(value) for value in item.get("keywords", []))

def _score(item: dict[str, Any], hint_terms: set[str]) -> tuple[int, set[str]]:
    """Evidence breadth: distinct hint tokens found anywhere in the record.

    Unchanged on purpose. This is what the wrapper score, the confidence and the
    cross-source tie rule are built from, so the 4.7 status semantics stay
    exactly as they were before the ranking fix.
    """
    overlap = hint_terms & tokens(_reference_text(item))
    return len(overlap), overlap

def _name_text(item: dict[str, Any]) -> str:
    """Only the fields that *name* the capability."""
    return " ".join(str(value) for value in (
        _legacy(item, "legacy_original_name"), item.get("path", ""), item.get("source_path", ""),
    ))

def _description_text(item: dict[str, Any]) -> str:
    """Only the fields that *describe* the capability."""
    return " ".join(str(value) for value in (
        _legacy(item, "legacy_description"),
    )) + " " + " ".join(str(value) for value in item.get("keywords", []))

def _name_view(item: dict[str, Any]) -> set[str]:
    """Name tokens as the engine sees them: noise-stripped, then widened.

    Kept as the named entry point the read-only D1 measurement harness calls.
    The withdrawn rule ("only the name view is widened") no longer describes the
    engine: the identical widening is now applied to the description view too, and
    candidacy uses the same ``routing_view`` as both hit classes.
    """
    return routing_view(_strip_noise(_name_text(item), "name"))

def _strip_noise(text: str, scope: str) -> str:
    """Substitute ``noise[]`` out of a RECORD's routing text, never out of a hint.

    ``scope: "any"`` applies to name + description + keywords; ``scope:
    "description"`` applies to the description only. The substitution happens on
    the text, before tokenising, so a noise pattern can also break a compound
    (``skills-hub`` -> ``skills hub``) instead of only deleting whole tokens.
    """
    value = text
    for pattern, pattern_scope in NOISE_PATTERNS:
        if pattern_scope == "any" or pattern_scope == scope:
            value = re.sub(pattern, " ", value, flags=re.IGNORECASE)
    return value

def _record_views(item: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Return ``(name_view, description_view)``, both from the ONE routing_view."""
    name_text = _strip_noise(_name_text(item), "name")
    description_text = _strip_noise(_description_text(item), "description")
    return routing_view(name_text), routing_view(description_text)

def _fired_signals(record_id: str, lowered_hint: str) -> tuple[list[str], list[str]]:
    """Return ``(signal_ids, notes)`` for the signals that fire on this hint.

    A signal fires iff at least one of its ``must`` regexes matches the
    lower-cased hint AND none of its ``exclude`` regexes matches. Both are
    ``re.search``, case-insensitive, so the layer speaks the same regex language
    as ``skills/config/routing.json``.
    """
    fired: list[str] = []
    notes: list[str] = []
    for signal in SIGNALS_BY_ID.get(record_id, ()):  # type: ignore[union-attr]
        if not any(must.search(lowered_hint) for must in signal["must"]):
            continue
        if any(exclude.search(lowered_hint) for exclude in signal["exclude"]):
            continue
        fired.append(signal["id"])
        notes.append(signal["note"])
    return fired, notes

def _rank(item: dict[str, Any], hint_terms: set[str],
          signal_ids: list[str]) -> tuple[int, set[str], set[str]]:
    """Return ``(rank_score, name_hits, description_only_hits)`` for one record.

    Every weight is charged on a disjoint hit class, so the frozen invariant
    holds exactly and can be recomputed by hand from ``routing-signals.json``:

        rank_score == SIGNAL_HIT_WEIGHT * len(signal_hits)
                    + NAME_HIT_WEIGHT * len(name_hits)
                    + DESCRIPTION_HIT_WEIGHT * len(description_hits)

    A hint token that appears in both the name and the description is charged the
    name weight only, and a fired signal is charged the signal weight on top.
    """
    name_view, description_view = _record_views(item)
    name_hits = hint_terms & name_view
    description_only = (hint_terms & description_view) - name_hits
    score = (SIGNAL_HIT_WEIGHT * len(signal_ids)
             + NAME_HIT_WEIGHT * len(name_hits)
             + DESCRIPTION_HIT_WEIGHT * len(description_only))
    return score, name_hits, description_only

def _reference_sort_key(reference: dict[str, Any]) -> tuple:
    """Deterministic order: field-aware rank, then name hits, then path.

    ``-rank_score`` keeps a name match above any number of description-only
    mentions; ``-name_hits`` breaks a rank tie in the same direction; the path
    keeps the order total and reproducible.

    T26: the routing-view widening (D1) surfaces description hits that the strict
    ``_score`` gate used to hide, which can tie two records that were previously
    ordered. When the rank AND the name-hit count tie, a name hit that is a
    canonical ``alias_`` token is preferred over a name hit that is a plain generic
    word: a curated capability token is a stronger self-name than an incidental
    one. This changes no weight, no ``REFERENCE_LIMIT``, no wrapper score and no
    confidence -- it only makes the intra-wrapper order match the documented
    "name match x3 > description mention x1" intent when the widened description
    view creates a new tie.
    """
    alias_name_hit = any(hit.startswith("alias_") for hit in reference["name_hits"])
    return (-reference["rank_score"], -len(reference["name_hits"]),
            0 if alias_name_hit else 1, reference["item"].get("path", ""))

def _wrapper_field_fit(result: dict[str, Any]) -> tuple[int, int, int]:
    """Best field-aware evidence quality among a wrapper's SHOWN references.

    Returns ``(rank_score, name_hits, alias_name_hit)`` maximised over the shown
    references, i.e. exactly the first three elements of ``_reference_sort_key``.
    Nothing new is measured here and no new weight is introduced: the wrapper
    level now reads the SAME field-aware model the reference level already uses,
    so a wrapper whose best shown reference names the capability (``alias_`` or
    plain name hit, x3) or carries a curated signal (x4) is ranked above a wrapper
    that only ever matched by description breadth (x1).
    """
    best = (0, 0, 0)
    for reference in result.get("references") or ():
        name_hits = reference.get("name_hits") or []
        fit = (int(reference.get("rank_score") or 0),
               len(name_hits),
               1 if any(hit.startswith("alias_") for hit in name_hits) else 0)
        if fit > best:
            best = fit
    return best

def _wrapper_sort_key(result: dict[str, Any]) -> tuple:
    """Deterministic order ACROSS wrappers: score, then field fit, then path.

    T27 (ctf-steal). Measured root cause: the wrapper order used
    ``(-score, path)`` only, so whenever two wrappers tied on score the winner was
    decided by the alphabetical order of the wrapper SKILL.md path. Measured over
    the 29 still-missing natural cases: 15 had a tie at the top and 14 of those
    lost the expected wrapper to that path comparison --
    ``skills/community/ctf-hub/SKILL.md`` sorts before
    ``skills/community/delivery/SKILL.md`` and ``.../hack-hub/SKILL.md``, so
    ctf-super-hub took first place on every tie even when its only evidence was
    description breadth. The score itself was NOT inflated (measured: ctf
    descriptions are ~1/3 the length of hack's, and ctf and hack slug sets are
    disjoint), so the defect is the tie-break, not the weights.

    The fix inserts the field-aware fit BETWEEN score and path. It therefore
    changes only WHICH equally-scored wrapper is offered first:

    * ``score`` is untouched, so ``confidence``, the ambiguity/tie rule, the
      budget and the candidate SET are all bit-identical;
    * the path stays the last key, so the order remains total and reproducible.
    """
    fit = _wrapper_field_fit(result)
    return (-result["score"], -fit[0], -fit[1], -fit[2], result["path"])

def _load_json(path: Path, label: str) -> Any:
    if not path.is_file():
        raise RegistryError("unavailable", f"{label} missing: {path}",
                            dependency=str(path),
                            limits=["registry, profile map and routing signals must be present"])
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RegistryError("blocked", f"{label} is not valid JSON: {error}", "schema_invalid") from None

def _require_keys(obj: Any, keys: tuple[str, ...], where: str, problems: list[str]) -> None:
    if not isinstance(obj, dict):
        problems.append(f"{where}: not an object")
        return
    for key in keys:
        if key not in obj:
            problems.append(f"{where}: missing {key}")

def _check_enum(value: Any, allowed: tuple[str, ...], where: str, problems: list[str]) -> None:
    if value not in allowed:
        problems.append(f"{where}: {value!r} not in {sorted(allowed)}")

SOURCE_FIELDS = ("id", "source_kind", "source_url", "commit", "tree_digest", "source_manifest",
                 "snapshot_root", "source_root", "license_declared", "license_status",
                 "third_party_review", "notice_file", "maturity", "distribution",
                 "adaptation_status", "importer_version", "last_verified_at")
SKILL_FIELDS = ("id", "source", "source_path", "adapted_path", "entrypoint", "discovery",
                "license_status", "maturity", "distribution", "allowed_context", "risk",
                "content_type", "keywords", "canonical_downstream", "reference_ids",
                "content_hash", "path_status")
WRAPPER_FIELDS = ("id", "path", "source", "route_ids", "reference_ids", "allowed_downstream",
                  "input_schema", "output_schema", "context_map", "default_action",
                  "auto_execute", "maturity")
SKILL_ENUMS = {
    "discovery": ("manifest-only", "reference-only", "disabled"),
    "maturity": ("verified", "partial", "unverified"),
    "distribution": ("local-only", "redistributable"),
    "risk": ("low", "medium", "high"),
    "content_type": ("methodology", "workflow", "tooling", "reference"),
    "path_status": ("clean", "needs-rewrite", "broken", "quarantined"),
    "license_status": ("verified", "review-required", "missing-license", "mixed"),
}
SOURCE_KINDS = ("community", "canonical-base", "first-party")
LICENSE_STATUSES = ("verified", "review-required", "missing-license", "mixed")
MATURITIES = ("verified", "partial", "unverified")
DISTRIBUTIONS = ("local-only", "redistributable")
THIRD_PARTY = ("required", "not-required")
ADAPTATION = ("candidate", "imported", "verified", "quarantined")
WRAPPER_ENUMS = {
    "default_action": ("review", "execute"),
    "maturity": ("verified", "partial", "unverified"),
}

class Contract:
    """Validated view over the frozen registry contract."""

    def __init__(self, registry: dict[str, Any], profile_map: dict[str, Any],
                 routing: dict[str, Any], digest: str) -> None:
        self.registry = registry
        self.profile_map = profile_map
        self.routing = routing
        self.digest = digest
        self.skills: list[dict[str, Any]] = registry["skills"]
        self.wrappers: dict[str, dict[str, Any]] = {w["source"]: w for w in registry["wrappers"]}
        self.problems: list[str] = []
        # skill id -> reasons why its allowed_context must stay needs_review
        self.needs_review_context: dict[str, list[str]] = {}
        self._validate()

    # -- profile derivation -------------------------------------------------
    @property
    def canonical_profiles(self) -> tuple[str, ...]:
        return tuple(self.profile_map["profiles"].keys())

    def resolve_profiles(self, values: list[str], sample_present: bool = False) -> tuple[list[str], list[str], list[str]]:
        """Return (canonical_profiles, needs_review_reasons, unknown_values).

        Three outcomes, all fail-closed:

        * a canonical profile, or a listed legacy alias that maps to one;
        * a listed alias that must stay ``needs_review`` (4.6 ``unrestricted_lab``,
          and ``offline``/``offline_only`` without a sample);
        * an unlisted value, which is a contract violation and never guessed.
        """
        aliases = self.profile_map["legacy_aliases"]
        found: list[str] = []
        review: list[str] = []
        unknown: list[str] = []
        for value in values:
            if value in self.canonical_profiles:
                found.append(value)
                continue
            entry = aliases.get(value)
            if entry is None:
                unknown.append(value)
                continue
            if entry.get("resolution") == "unsupported":
                review.append(f"{value}: listed as unsupported, must stay needs_review")
                continue
            if "profile" in entry:
                found.append(entry["profile"])
                continue
            if entry.get("resolution") == "needs_review_if_no_sample":
                if sample_present:
                    found.append(entry["conditional"]["then"])
                else:
                    review.append(f"{value}: no sample present, must stay needs_review")
                continue
            unknown.append(value)
        return sorted(set(found)), review, unknown

    def select_profile(self, values: list[str]) -> str:
        """Deterministic single-profile resolution (spec 4.6: one value per record)."""
        precedence = self.profile_map["resolution"]["precedence"]
        return sorted(set(values), key=precedence.index)[0]

    def network_mode(self, profile: str) -> str:
        return self.profile_map["profiles"][profile]["network_mode"]

    # -- validation ---------------------------------------------------------
    def _validate(self) -> None:
        p = self.problems
        canonical: list[str] = []
        routing = self.routing

        _check_enum(self.registry.get("schemaVersion"), (REGISTRY_SCHEMA_VERSION,), "registry.schemaVersion", p)
        _require_keys(self.registry, ("sources", "wrappers", "skills", "stats"), "registry", p)
        if p:
            return

        for source in self.registry["sources"]:
            _require_keys(source, SOURCE_FIELDS, f"source {source.get('id')}", p)
            where = f"source {source.get('id')}"
            _check_enum(source.get("source_kind"), SOURCE_KINDS, f"{where}.source_kind", p)
            _check_enum(source.get("license_status"), LICENSE_STATUSES, f"{where}.license_status", p)
            _check_enum(source.get("maturity"), MATURITIES, f"{where}.maturity", p)
            _check_enum(source.get("distribution"), DISTRIBUTIONS, f"{where}.distribution", p)
            _check_enum(source.get("third_party_review"), THIRD_PARTY, f"{where}.third_party_review", p)
            _check_enum(source.get("adaptation_status"), ADAPTATION, f"{where}.adaptation_status", p)
            if source.get("distribution") == "redistributable":
                if not (source.get("license_status") == "verified"
                        and source.get("third_party_review") == "not-required"
                        and source.get("maturity") == "verified"
                        and source.get("notice_file")):
                    p.append(f"{where}: redistributable without verified license/notice (4.1)")

        source_ids = {s["id"] for s in self.registry["sources"]}
        for skill in self.registry["skills"]:
            where = f"skill {skill.get('id')}"
            _require_keys(skill, SKILL_FIELDS, where, p)
            if p:
                return
            for field, allowed in SKILL_ENUMS.items():
                _check_enum(skill.get(field), allowed, f"{where}.{field}", p)
            if skill.get("source") not in source_ids:
                p.append(f"{where}: unknown source {skill.get('source')!r}")
            if skill.get("adapted_path") != skill.get("path"):
                p.append(f"{where}: adapted_path must equal path during the transition")
            if not (ROOT / str(skill.get("path"))).is_file():
                p.append(f"{where}: path missing on disk: {skill.get('path')}")
            if not re.match(r"^community-[a-z0-9-]+-\d{3}$", str(skill.get("id"))):
                p.append(f"{where}: id pattern")
            if not re.match(r"^sha256:[0-9a-f]{64}$", str(skill.get("content_hash"))):
                p.append(f"{where}: content_hash pattern")
            contexts = skill.get("allowed_context")
            if not isinstance(contexts, list) or not contexts:
                p.append(f"{where}: allowed_context must be a non-empty array")
                continue
            resolved, review_reasons, unknown = self.resolve_profiles(contexts)
            if unknown:
                p.append(f"{where}: unknown allowed_context {unknown}")
            elif review_reasons:
                self.needs_review_context[skill["id"]] = review_reasons
            elif len(resolved) != 1:
                p.append(f"{where}: allowed_context resolves to {resolved}, expected exactly one profile")
            canonical.append(resolved[0] if len(resolved) == 1 else "")
            keywords = skill.get("keywords")
            if not isinstance(keywords, list) or not 1 <= len(keywords) <= 32:
                p.append(f"{where}: keywords must hold 1-32 entries")
            elif len(set(keywords)) != len(keywords) or any(k != k.lower() for k in keywords):
                p.append(f"{where}: keywords must be lowercase and unique")

        for wrapper in self.registry["wrappers"]:
            where = f"wrapper {wrapper.get('id')}"
            _require_keys(wrapper, WRAPPER_FIELDS, where, p)
            if p:
                return
            _check_enum(wrapper.get("default_action"), WRAPPER_ENUMS["default_action"], f"{where}.default_action", p)
            _check_enum(wrapper.get("maturity"), WRAPPER_ENUMS["maturity"], f"{where}.maturity", p)
            if wrapper.get("source") not in source_ids:
                p.append(f"{where}: unknown source {wrapper.get('source')!r}")
            if wrapper.get("auto_execute") is not False:
                p.append(f"{where}: auto_execute must be false")
            if not (ROOT / str(wrapper.get("path"))).is_file():
                p.append(f"{where}: path missing on disk: {wrapper.get('path')}")
            if wrapper.get("input_schema") != "schemas/community-handoff-input.json":
                p.append(f"{where}: input_schema must be schemas/community-handoff-input.json")
            if wrapper.get("output_schema") != "schemas/community-handoff-output.json":
                p.append(f"{where}: output_schema must be schemas/community-handoff-output.json")
            if not wrapper.get("route_ids"):
                p.append(f"{where}: route_ids must be non-empty")
            for route_id in wrapper.get("route_ids") or []:
                if route_id not in routing.get("routes", {}):
                    p.append(f"{where}: route id {route_id!r} missing from routing.json")
            context_map = wrapper.get("context_map") or {}
            if not context_map:
                p.append(f"{where}: context_map must be non-empty")
            for profile, mode in context_map.items():
                if profile not in self.canonical_profiles:
                    p.append(f"{where}: context_map key {profile!r} is not a canonical profile")
                elif mode != self.network_mode(profile):
                    p.append(f"{where}: context_map[{profile}]={mode!r} contradicts profile-map network mode")
            for downstream in wrapper.get("allowed_downstream") or []:
                if not (ROOT / "skills" / downstream / "SKILL.md").is_file():
                    p.append(f"{where}: downstream {downstream!r} is not a canonical skill (17.23)")
            for reference_id in wrapper.get("reference_ids") or []:
                match = next((s for s in self.registry["skills"] if s["id"] == reference_id), None)
                if match is None:
                    p.append(f"{where}: reference id {reference_id!r} does not exist")
                elif match.get("discovery") != "reference-only":
                    p.append(f"{where}: reference id {reference_id!r} is not discovery=reference-only")

        if self.registry["wrappers"]:
            kind_by_source = {s.get("id"): s.get("source_kind") for s in self.registry["sources"]}
            for source in source_ids:
                # canonical-base is the canonical tree itself (exposed without a
                # wrapper); every other kind stays fail-closed and requires one.
                if kind_by_source.get(source) == "canonical-base":
                    continue
                if source not in self.wrappers:
                    p.append(f"source {source}: no wrapper record")

        stats = self.registry.get("stats") or {}
        if stats.get("adapted_skill_count") != len(self.registry["skills"]):
            p.append("registry.stats.adapted_skill_count does not match skills[]")
        if stats.get("excluded_framework_skill_count") != len(self.registry.get("excluded", [])):
            p.append("registry.stats.excluded_framework_skill_count does not match excluded[]")

NL_MAP = ROOT / "skills" / "config" / "natural-language-map.json"
_NL_CACHE: list[tuple[str, str, bool]] | None = None
_NL_DOMAIN_NOUNS = ("订单", "文件", "路径", "上传", "权限", "密码", "验证码", "令牌", "模板", "内存", "票据", "应用", "集群", "容器", "跨域", "弹窗", "请求", "签名", "抓包", "证书", "shell", "token", "url", "ios", "k8s", "内网", "数据", "注入", "漏洞", "提权", "后缀", "木马", "报错", "回显", "评论", "页面", "链接", "登录", "框架", "分块", "目录", "斜杠", "穿越", "绑定", "模拟器", "防护", "转储", "通讯录", "外发", "绕过", "爆破", "伪造", "篡改", "复用")

def _nl_topic_extra(hint: str) -> str:
    global _NL_CACHE
    if _NL_CACHE is None:
        _NL_CACHE = []
        try:
            _doc = _load_json(NL_MAP, "natural language map")
        except RegistryError:
            _doc = {}
        for _entry in _doc.get("entries", []) if isinstance(_doc, dict) else []:
            if not isinstance(_entry, dict):
                continue
            _topic = str(_entry.get("topic") or "")
            _core = (_topic.split(":", 1)[1] if ":" in _topic else _topic).split("(", 1)[0].strip()
            for _surface in _entry.get("surfaces") or []:
                _lower = str(_surface or "").lower()
                if _lower:
                    _weak = _topic.startswith("VERB-ONLY") or not any(_d in _lower for _d in _NL_DOMAIN_NOUNS)
                    _NL_CACHE.append((_lower, _core, _weak))
    _norm = unicodedata.normalize("NFKC", hint).lower()
    _extra: list[str] = []
    for _lower, _core, _weak in _NL_CACHE:
        if _core and _lower in _norm and _core not in _extra and (not _weak or any(_domain in _norm for _domain in _NL_DOMAIN_NOUNS)):
            _extra.append(_core)
    return " ".join(_extra)

def load_signals() -> SignalLayer:
    """Load the curated signal layer. Fail-closed, exactly like REGISTRY.

    A missing file is ``unavailable`` with ``dependency`` and ``limits`` set; a
    malformed one is ``blocked`` with ``schema_invalid``. An empty-but-valid file
    is not an error: it means the layer currently contributes nothing, which is
    the state the skeleton ships in and the state the ranking model must survive.
    """
    document = _load_json(SIGNALS, "routing signals")
    if not isinstance(document, dict):
        raise RegistryError("blocked", "routing signals must be a JSON object", "schema_invalid")
    return _publish_signals(SignalLayer(document, "sha256:" + hashlib.sha256(
        SIGNALS.read_bytes()).hexdigest()))

def load_contract() -> Contract:
    registry_bytes = REGISTRY.read_bytes() if REGISTRY.is_file() else None
    registry = _load_json(REGISTRY, "community registry")
    profile_map = _load_json(PROFILE_MAP, "profile map")
    routing = _load_json(ROUTING, "canonical routing table")
    load_signals()
    for key in ("profiles", "legacy_aliases", "resolution"):
        if key not in profile_map:
            raise RegistryError("blocked", f"profile map missing {key}", "schema_invalid")
    digest = "sha256:" + hashlib.sha256(registry_bytes or b"").hexdigest()
    contract = Contract(registry, profile_map, routing, digest)
    if contract.problems:
        raise RegistryError("blocked", "registry contract violation", "schema_invalid",
                            violations=contract.problems[:10],
                            violation_count=len(contract.problems))
    return contract

def _wrapper_result(contract: Contract, source: str, wrapper: dict[str, Any],
                    references: list[dict[str, Any]], hint_terms: set[str]) -> dict[str, Any]:
    # Evidence breadth is the maximum over the references, exactly what the old
    # ``references[0]["score"]`` read: the previous sort put the highest breadth
    # first, so the wrapper score and the confidence are unchanged by the new
    # field-aware ordering.
    best_score = max(reference["score"] for reference in references)
    shown = references[:REFERENCE_LIMIT]
    matched = sorted({term for reference in shown for term in reference["matched_terms"]})
    wrapper_hits = sorted(hint_terms & {f"alias_{term}" for term in WRAPPER_ALIASES[source]})
    score = best_score + len(wrapper_hits)
    # Confidence is based on matched registry evidence, not wrapper aliases;
    # otherwise a generic wrapper label could make an unrelated hint look strong.
    confidence = min(1.0, best_score / max(1, len(hint_terms)))
    license_values = sorted({str(reference["item"].get("license_status", "unknown")) for reference in references})
    maturity_values = sorted({str(reference["item"].get("maturity", "unknown")) for reference in references})
    profiles: set[str] = set()
    unresolved: set[str] = set()
    for reference in references:
        item = reference["item"]
        resolved, review_reasons, unknown = contract.resolve_profiles(item.get("allowed_context") or [])
        profiles.update(resolved)
        unresolved.update(review_reasons)
        unresolved.update(f"unknown allowed_context {value}" for value in unknown)
        recorded = contract.needs_review_context.get(item["id"])
        if recorded:
            unresolved.update(recorded)
    ordered_profiles = sorted(profiles, key=contract.profile_map["resolution"]["precedence"].index)
    profile = ordered_profiles[0] if len(ordered_profiles) == 1 and not unresolved else None
    network_profile = contract.network_mode(profile) if profile else None
    route_ids = list(wrapper["route_ids"])
    # T26: report the curated signal hits with their human notes, so a reader can
    # see WHY a record won instead of only a number.
    signal_ids = sorted({signal for reference in shown for signal in reference["signal_hits"]})
    signal_notes: list[str] = []
    for reference in shown:
        for note in reference["signal_notes"]:
            if note not in signal_notes:
                signal_notes.append(note)
    signal_text = f"curated signal x{SIGNAL_HIT_WEIGHT}: {', '.join(signal_ids)}" if signal_ids \
        else f"curated signal x{SIGNAL_HIT_WEIGHT}: none"
    if signal_notes:
        signal_text += " (" + "; ".join(signal_notes) + ")"
    explanation = (
        f"matched {best_score} registry term(s) ({', '.join(matched[:12]) or 'none'}) in "
        f"{len(references)} adapted reference(s) of wrapper {wrapper['id']} (route {', '.join(route_ids)}); "
        f"score={score} confidence={round(confidence, 3)}; access=wrapper-only; "
        f"profile={profile or 'unresolved'} -> network_profile={network_profile or 'unresolved'}; "
        f"{signal_text}; "
        f"reference order: curated signal x{SIGNAL_HIT_WEIGHT} > name match x{NAME_HIT_WEIGHT} > "
        f"description mention x{DESCRIPTION_HIT_WEIGHT}, top {len(shown)} of {len(references)} shown"
    )
    return {
        "score": score,
        "confidence": round(confidence, 3),
        "id": wrapper["id"],
        "source": source,
        "path": wrapper["path"],
        "entrypoint": wrapper["path"],
        "route_ids": route_ids,
        "access": "wrapper-only",
        "downstream": list(wrapper["allowed_downstream"]),
        "references": [{"id": reference["item"].get("id"), "source_path": reference["item"].get("source_path"),
                        "score": reference["score"], "rank_score": reference["rank_score"],
                        "signal_hits": reference["signal_hits"], "signal_notes": reference["signal_notes"],
                        "name_hits": reference["name_hits"], "description_hits": reference["description_hits"],
                        "matched_terms": reference["matched_terms"]} for reference in shown],
        "signal_hits": signal_ids,
        "signal_notes": signal_notes,
        "matched_terms": matched,
        "maturity": maturity_values[0] if len(maturity_values) == 1 else "mixed",
        "license_status": license_values[0] if len(license_values) == 1 else "mixed",
        "risk": sorted({str(reference["item"].get("risk", "unknown")) for reference in references}),
        "allowed_context": ordered_profiles,
        "profile": profile,
        "network_profile": network_profile,
        "unresolved_context": sorted(unresolved),
        "route_explanation": explanation,
    }

def _collect_candidates(contract: Contract, hint_text: str,
                        source: str | None) -> tuple[dict[str, list[dict[str, Any]]], set[str]]:
    """Run the exact candidacy path for one hint string.

    Shared by the main query and by the budget-exceeded recovery planner, so a
    narrowing suggestion is measured with the same code that will execute it --
    a suggestion is only offered when this function reports it fits the budget.
    Returns ``(candidates, hint_terms)``; an empty ``hint_terms`` means the text
    carries no usable tokens (stopwords only).
    """
    hint_terms = fold_aliases(tokens(hint_text))
    candidates: dict[str, list[dict[str, Any]]] = {}
    if not hint_terms:
        return candidates, hint_terms
    lowered_hint = unicodedata.normalize("NFKC", hint_text or "").lower()
    for item in contract.skills:
        item_source = item.get("source")
        if item_source not in contract.wrappers or (source and item_source != source):
            continue
        signal_ids, signal_notes = _fired_signals(str(item.get("id", "")), lowered_hint)
        # T26 / D1: candidacy reads the SAME routing_view as the ranker, so a
        # record reachable through the widening is no longer invisible. It is no
        # longer gated on ``_score``; ``_score`` is still computed (unchanged) and
        # is still the only input to the wrapper score and to confidence.
        name_view, description_view = _record_views(item)
        if not signal_ids and not (hint_terms & (name_view | description_view)):
            continue
        score, matched_terms = _score(item, hint_terms)
        rank_score, name_hits, description_hits = _rank(item, hint_terms, signal_ids)
        candidates.setdefault(item_source, []).append({
            "item": item,
            "score": score,
            "matched_terms": sorted(matched_terms),
            "rank_score": rank_score,
            "signal_hits": signal_ids,
            "signal_notes": signal_notes,
            "name_hits": sorted(name_hits),
            "description_hits": sorted(description_hits),
        })
    return candidates, hint_terms

def _verified_narrows(contract: Contract, hint_text: str,
                      source: str | None) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """Probe each single word of the failed hint as its own query.

    Returns ``(fits, misses)``: ``fits`` holds ``(word, total)`` pairs with
    ``1 <= total <= MAX_TOTAL_REFERENCES`` -- re-running the query with that
    word (and the same ``--source``) is therefore verified to fit the budget;
    ``misses`` holds ``(word, total)`` pairs that are still over budget
    (``total == -1`` means the word carries no usable tokens at all).
    Matching is a union, so a single word can never match MORE than the full
    hint under the same filter; every figure here is measured, never estimated.
    """
    fits: list[tuple[str, int]] = []
    misses: list[tuple[str, int]] = []
    seen: set[str] = set()
    for word in hint_text.split():
        key = word.casefold()
        if key in seen:
            continue
        seen.add(key)
        words, terms = _collect_candidates(contract, word, source)
        if not terms:
            misses.append((word, -1))
            continue
        total = sum(len(references) for references in words.values())
        if total > MAX_TOTAL_REFERENCES or total == 0:
            misses.append((word, total))
        else:
            fits.append((word, total))
    fits.sort(key=lambda pair: pair[1])
    return fits, misses

def lookup(hint: str, source: str | None = None, limit: int = 5) -> dict[str, Any]:
    contract = load_contract()
    budget = {
        "max_wrapper_candidates": MAX_WRAPPER_CANDIDATES,
        "max_total_references": MAX_TOTAL_REFERENCES,
        "reference_limit_per_wrapper": REFERENCE_LIMIT,
        "minimum_confidence": MIN_CONFIDENCE,
        "near_tie_delta": NEAR_TIE_DELTA,
    }
    # T11: --limit can never widen the first-screen candidate set beyond the
    # budget. Clamping (not failing) keeps existing callers working.
    effective_limit = min(max(1, limit), MAX_WRAPPER_CANDIDATES)
    payload: dict[str, Any] = {
        "hint": hint,
        "registry": str(REGISTRY),
        "registry_digest": contract.digest,
        "routing_signals": str(SIGNALS),
        "routing_signals_digest": SIGNAL_LAYER.digest if SIGNAL_LAYER else None,
        "source_filter": source,
        "status": "matched",
        "needs_review": False,
        "failure_reason": None,
        "review_reason": [],
        "minimum_confidence": MIN_CONFIDENCE,
        "budget": dict(budget),
        "matches": [],
        "route_explanation": "",
    }
    # The hint is tokenised WITHOUT noise (noise applies to records only) and is
    # folded through ``token_aliases`` symmetrically, so both sides of the
    # comparison speak the same vocabulary.
    hint_terms = fold_aliases(tokens(hint))
    if not hint_terms:
        payload.update({
            "status": "missing_input",
            "needs_review": True,
            "missing_fields": ["hint"],
            "route_explanation": "no usable hint tokens were supplied; a non-empty hint is required (4.4)",
        })
        return payload

    search_hint, nl_extra = hint, _nl_topic_extra(hint)
    if nl_extra:
        _orig_candidates, _ = _collect_candidates(contract, hint, source)
        _best = max([min(1.0, max(_r["score"] for _r in _refs) / max(1, len(hint_terms))) for _refs in _orig_candidates.values()] or [0.0])
        if _best < MIN_CONFIDENCE:
            _exp_candidates, _ = _collect_candidates(contract, hint + " " + nl_extra, source)
            if sum(len(_r) for _r in _exp_candidates.values()) <= MAX_TOTAL_REFERENCES or sum(len(_r) for _r in _orig_candidates.values()) > MAX_TOTAL_REFERENCES:
                search_hint = hint + " " + nl_extra
                hint_terms = fold_aliases(tokens(search_hint))
    candidates, _ = _collect_candidates(contract, search_hint, source)

    matches = []
    for item_source, references in candidates.items():
        references.sort(key=_reference_sort_key)
        matches.append(_wrapper_result(contract, item_source, contract.wrappers[item_source], references, hint_terms))
    matches.sort(key=_wrapper_sort_key)
    all_matches = matches
    # T11 (spec 17.25): over budget stops and reports (blocked /
    # budget_exceeded, exit 20) instead of silently truncating. Checked before
    # --limit so a caller cannot hide the overflow by requesting fewer rows.
    total_references = sum(len(references) for references in candidates.values())
    budget["total_references"] = total_references
    budget["wrapper_candidates"] = len(all_matches)
    budget["requested_limit"] = limit
    budget["effective_limit"] = effective_limit
    payload["budget"] = dict(budget)
    if total_references > MAX_TOTAL_REFERENCES:
        detail = (
            f"loading budget exceeded: {total_references} adapted reference(s) "
            f"matched across {len(all_matches)} wrapper candidate(s), "
            f"budget is {MAX_TOTAL_REFERENCES} references / "
            f"{MAX_WRAPPER_CANDIDATES} wrappers / {REFERENCE_LIMIT} shown per wrapper; "
            f"refusing to silently truncate"
        )
        # P1-3: the recovery path must stay executable after --source is
        # already applied. Every narrowing below is MEASURED with the same
        # candidacy code that will execute it (see _verified_narrows) -- a word
        # is only suggested when re-querying it under the same filter is
        # verified to fit the budget. Exit/status semantics are untouched:
        # still blocked / budget_exceeded / exit 20.
        scope = f"--source {source}" if source else "no --source filter"
        fits, misses = _verified_narrows(contract, hint, source)
        if fits:
            shown = "; ".join(
                f"hint {word!r} matches {count} reference(s)"
                for word, count in fits[:3]
            )
            narrow = (
                f"measured single-word narrows under the same filter ({scope}): "
                f"{shown}; re-run with one of those words as the hint"
                + (f" and the same --source {source}" if source else "")
                + f" (each is under the {MAX_TOTAL_REFERENCES}-reference budget)"
            )
        else:
            parts = []
            for word, count in misses[:5]:
                if count < 0:
                    parts.append(f"{word!r} carries no usable tokens")
                elif count == 0:
                    parts.append(f"{word!r} alone matches nothing")
                else:
                    parts.append(f"{word!r} alone still matches {count} (> budget)")
            measured = "; ".join(parts) if parts else "n/a"
            narrow = (
                "no single word of this hint fits the budget "
                f"(measured under {scope}: {measured}); reformulate with a "
                "different, more specific capability term (one technology or "
                "task, not a source-family word) and re-query"
                + (f" with the same --source {source}" if source else "")
            )
        if source:
            recovery = (
                f"the --source filter is already applied (--source {source}) and "
                f"{total_references} references still exceed the "
                f"{MAX_TOTAL_REFERENCES}-reference budget, so re-querying per "
                "source cannot help further. Matching is a union: appending "
                "words widens, never narrows -- replace the hint instead of "
                "extending it. " + narrow +
                ". Run the narrower queries sequentially: the budget is per "
                "query (stateless, no cross-call accumulator). --limit only "
                "trims the display and is checked after the budget, so it "
                "cannot clear this error"
            )
            confirmation = (
                f"state the narrowed hint (keep --source {source}), "
                "then wait for human confirmation"
            )
        else:
            recovery = (
                "narrow the hint to one capability per query, or re-query per source with "
                "--source <ctf-super-hub|hack-skills|ai-fullstack-delivery|apk-reverse-community>. "
                "Matching is a union: appending words widens, never narrows -- replace "
                "the hint instead of extending it. " + narrow +
                ". Run the narrower queries sequentially: the budget is per query "
                "(stateless, no cross-call accumulator). --limit only trims the "
                "display and is checked after the budget, so it cannot clear this error; "
                "references beyond the per-wrapper display cap are second-level loads: "
                "re-run with --source and confirm each additional reference before reading it"
            )
            confirmation = "state the narrowed hint and the --source value, then wait for human confirmation"
        payload.update({
            "status": "blocked",
            "needs_review": True,
            "failure_reason": "budget_exceeded",
            "reason": detail,
            "matches": [],
            "route_explanation": detail,
            "required_action": recovery,
            "confirmation": confirmation,
        })
        return payload
    matches = all_matches[: max(1, effective_limit)]
    payload["matches"] = matches

    needs_review = False
    review_reason: list[str] = []
    if not matches:
        needs_review = True
        review_reason.append("no_match")
    else:
        top = matches[0]
        if top["confidence"] < MIN_CONFIDENCE:
            needs_review = True
            review_reason.append("low_confidence")
        # Evaluate ambiguity before applying ``--limit`` so a caller cannot hide
        # a tie merely by requesting one visible result.
        if len(all_matches) > 1:
            second = all_matches[1]
            if second["score"] == top["score"] or (top["score"] and (top["score"] - second["score"]) / top["score"] <= NEAR_TIE_DELTA):
                needs_review = True
                review_reason.append("ambiguous_tie")
        if top["profile"] is None:
            needs_review = True
            review_reason.append("profile_unresolved")

    payload["needs_review"] = needs_review
    payload["review_reason"] = review_reason
    payload["status"] = "needs_review" if needs_review else "matched"
    if needs_review:
        payload["reason"] = ", ".join(review_reason)
        payload["candidates"] = [match["id"] for match in all_matches]
        payload["confidence"] = matches[0]["confidence"] if matches else 0.0
        payload["route_explanation"] = (
            f"needs_review: {', '.join(review_reason)}; "
            f"{len(all_matches)} wrapper candidate(s), top confidence={matches[0]['confidence'] if matches else 0.0}"
        )
    else:
        payload["route_explanation"] = matches[0]["route_explanation"]
    return payload

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hint", required=True)
    parser.add_argument("--source", choices=sorted(WRAPPER_ALIASES))
    parser.add_argument("--limit", type=int, default=5,
                        help=f"wrappers shown, clamped to 1..{MAX_WRAPPER_CANDIDATES} (spec 17.25)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.limit < 1 or args.limit > MAX_WRAPPER_CANDIDATES:
        parser.error(f"--limit must be 1..{MAX_WRAPPER_CANDIDATES} "
                     f"(loading budget, spec 17.25); got {args.limit}")
    try:
        payload = lookup(args.hint, args.source, args.limit)
    except RegistryError as error:
        payload = {
            "hint": args.hint,
            "registry": str(REGISTRY),
            "source_filter": args.source,
            "status": error.status,
            "needs_review": True,
            "failure_reason": error.failure_reason,
            "reason": error.detail,
            "matches": [],
            "route_explanation": error.detail,
        }
        payload.update(error.extra)
        if error.status == "blocked":
            payload.setdefault("policy", "registry contract (spec 4.0-4.3)")
            payload.setdefault("required_action", "fix the registry or the profile map before routing")
        if error.status == "unavailable":
            payload.setdefault("limits", ["read-only lookup cannot run without its inputs"])
    except Exception as error:  # pragma: no cover - defensive fail-closed path
        payload = {
            "hint": args.hint,
            "registry": str(REGISTRY),
            "status": "failed",
            "needs_review": True,
            "failure_reason": "internal_error",
            "reason": f"{type(error).__name__}: {error}",
            "matches": [],
            "route_explanation": "internal error while resolving the community route",
        }

    status = payload["status"]
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return STATUS_EXIT[status]

    print(f"community matches: {len(payload['matches'])} (status={status}; wrapper-only)")
    if payload.get("budget"):
        budget = payload["budget"]
        print(f"budget: {budget.get('total_references', '?')}/{budget.get('max_total_references', '?')} references, "
              f"{budget.get('wrapper_candidates', '?')}/{budget.get('max_wrapper_candidates', '?')} wrappers, "
              f"{REFERENCE_LIMIT} shown per wrapper")
    if payload.get("failure_reason"):
        print(f"failure reason: {payload['failure_reason']}")
    if payload.get("required_action") and status == "blocked":
        print(f"required action: {payload['required_action']}")
    if payload.get("review_reason"):
        print(f"review reason: {', '.join(payload['review_reason'])}")
    if payload.get("reason") and status in {"blocked", "unavailable", "failed", "missing_input"}:
        print(f"reason: {payload['reason']}")
    for result in payload["matches"]:
        print(f"{result['score']:>2} {result['source']} -> {result['path']} [{result['maturity']}/{result['risk']}]")
        print(f"   confidence={result['confidence']} context={','.join(result['allowed_context']) or 'unresolved'}"
              f" profile={result['profile'] or 'unresolved'} network={result['network_profile'] or 'unresolved'}"
              f" license={result['license_status']}")
        print(f"   routes={','.join(result['route_ids'])} downstream={','.join(result['downstream'])}")
        print(f"   why: {result['route_explanation']}")
    if payload["matches"] and not payload.get("review_reason"):
        print(f"route explanation: {payload['route_explanation']}")
    return STATUS_EXIT[status]

if __name__ == "__main__":
    raise SystemExit(main())
