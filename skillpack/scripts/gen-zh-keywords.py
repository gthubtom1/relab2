#!/usr/bin/env python3
"""Community 293 records Chinese keyword suggestions generator (read-only on registry).

Reads: skills/community/registry.json, skills/scripts/community-route.py (ALIASES only).
Writes (OUT dir only): suggestions.json, checks.json, sampling.json, REPORT.md.
Never modifies registry.json / router / routing.json / tests / SKILL.md.

Usage:
  python scripts/gen-zh-keywords.py            # generate + checks
  python scripts/gen-zh-keywords.py --sample  # 20-hint live sampling -> sampling.json
  python scripts/gen-zh-keywords.py --report  # REPORT.md from existing outputs
"""
import ast
import json
import os
import re
import subprocess
import sys
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(REPO, "skills", "community", "registry.json")
ROUTER = os.path.join(REPO, "skills", "scripts", "community-route.py")
BENCH1 = os.path.join(REPO, "skills", "tests", "routing-benchmark.json")
BENCH2 = os.path.join(REPO, "skills", "tests", "routing-benchmark-natural.json")

# work/ 目录：默认取「仓库根的同级 work/」，可用 REVERSE_SKILL_WORK_DIR 覆盖。
# 换机器 clone 后无需改代码；缺题库时明确报错，不静默跳过。
WORK_DIR = os.environ.get("REVERSE_SKILL_WORK_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(REPO)), "work")
CASES = os.path.join(WORK_DIR, "natural-300", "cases.json")
HITRATE_GLOB_DIR = WORK_DIR
OUT = os.path.join(WORK_DIR, "zh-keywords")
for _a in sys.argv[1:]:
    if _a.startswith("--out="):
        OUT = _a.split("=", 1)[1]
if not os.path.isfile(CASES):
    sys.stderr.write(
        "ERROR: cases file not found: {0}\n"
        "  This generator needs the natural-300 case bank (work/natural-300/cases.json),\n"
        "  which lives outside the repository. Point REVERSE_SKILL_WORK_DIR at the work/\n"
        "  directory that contains it (current: {1}).\n".format(CASES, WORK_DIR))
    sys.exit(2)

CJK = r"\u4e00-\u9fff"
HAS_CJK = re.compile("[" + CJK + "]")

def has_cjk(s):
    return bool(HAS_CJK.search(s))

def cjk_runs(s):
    return re.findall("[" + CJK + "]{2,}", s)

# ---------------------------------------------------------------- lexicon
def load_aliases():
    src = open(ROUTER, encoding="utf-8").read()
    start = src.find("ALIASES: dict")
    i = src.find("{", start)
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return ast.literal_eval(src[i:j + 1])
    raise RuntimeError("ALIASES block not found")

def load_registry():
    d = json.load(open(REGISTRY, encoding="utf-8"))
    return d["skills"]

def name_text(r):
    ext = r.get("extensions") or {}
    return " ".join(str(v) for v in (
        ext.get("legacy_original_name", ""), r.get("path", ""),
        r.get("source_path", "")))

def evidence_of(r):
    ext = r.get("extensions") or {}
    ld = (ext.get("legacy_description", "") or "")[:140].replace("\n", " ")
    return "legacy_description: %r" % ld

# ------------------------------------------------- capability topic tables
# slug-fragment (longest first) -> (Chinese topic, frame group)
HACK_TOPICS = [
    ("401-403-bypass", ("后台拦路", "bypass")),
    ("403-bypass", ("后台拦路", "bypass")),
    ("active-directory-acl-abuse", ("域权限配错", "cred")),
    ("active-directory-certificate-services", ("域证书服务", "cred")),
    ("certificate-services", ("域证书服务", "cred")),
    ("kerberos-attacks", ("域票据", "cred")),
    ("kerberos", ("域票据", "cred")),
    ("ai-ml-security", ("模型供应链", "test")),
    ("android-pentesting", ("安卓应用", "test")),
    ("anti-debugging", ("反调试", "bypass")),
    ("api-auth-and-jwt-abuse", ("接口令牌", "test")),
    ("api-authorization-and-bola", ("接口越权", "test")),
    ("api-recon-and-docs", ("接口文档", "test")),
    ("api-sec", ("接口安全", "test")),
    ("arbitrary-write-to-rce", ("任意写", "exploit")),
    ("attack-surface-mapping", ("攻击面", "test")),
    ("auth-sec", ("登录鉴权", "test")),
    ("authbypass-authentication-flaws", ("登录绕过", "bypass")),
    ("binary-protection-bypass", ("二进制防护", "bypass")),
    ("browser-exploitation-v8", ("浏览器漏洞", "exploit")),
    ("business-logic-vuln", ("业务逻辑", "test")),
    ("business-logic-vulnerabilities", ("业务流程", "test")),
    ("classical-cipher", ("古典密码", "crypto")),
    ("clickjacking", ("点击劫持", "test")),
    ("cmdi-command-injection", ("命令注入", "exploit")),
    ("code-obfuscation-deobfuscation", ("代码混淆", "binary")),
    ("container-escape", ("容器逃逸", "escape")),
    ("cors-cross-origin-misconfiguration", ("跨域配置", "test")),
    ("crlf-injection", ("回车换行", "test")),
    ("csp-bypass", ("内容安全策略", "bypass")),
    ("csrf-cross-site-request-forgery", ("跨站请求伪造", "test")),
    ("csv-formula-injection", ("表格公式", "test")),
    ("dangling-markup", ("悬空标记", "test")),
    ("defi-attack-patterns", ("合约闪电贷", "test")),
    ("dependency-confusion", ("依赖混淆", "test")),
    ("deserialization-insecure", ("反序列化", "exploit")),
    ("dns-rebinding", ("DNS重绑定", "test")),
    ("email-header-injection", ("邮件头", "test")),
    ("expression-language-injection", ("表达式注入", "exploit")),
    ("file-access-vuln", ("文件下载", "test")),
    ("format-string-exploitation", ("格式化串", "exploit")),
    ("ghost-bits-cast-attack", ("Java类型", "exploit")),
    ("graphql-and-hidden-parameters", ("GraphQL接口", "test")),
    ("hack", ("渗透总控", "test")),
    ("hash-attack-techniques", ("哈希算法", "crypto")),
    ("heap-exploitation", ("堆漏洞", "exploit")),
    ("http-host-header-attacks", ("Host头", "test")),
    ("http-parameter-pollution", ("参数污染", "test")),
    ("http2-specific-attacks", ("HTTP2协议", "test")),
    ("idor-broken-object-authorization", ("越权访问", "test")),
    ("injection-checking", ("注入分流", "test")),
    ("insecure-source-code-management", ("源码泄露", "test")),
    ("ios-pentesting", ("苹果应用", "test")),
    ("jndi-injection", ("JNDI注入", "exploit")),
    ("jwt-oauth-token-attacks", ("令牌算法", "test")),
    ("kernel-exploitation", ("内核漏洞", "exploit")),
    ("kubernetes-pentesting", ("集群权限", "test")),
    ("lattice-crypto-attacks", ("格密码", "crypto")),
    ("linux-lateral-movement", ("内网横移", "move")),
    ("linux-privilege-escalation", ("Linux提权", "privesc")),
    ("linux-security-bypass", ("受限shell", "bypass")),
    ("llm-prompt-injection", ("提示词注入", "test")),
    ("macos-process-injection", ("苹果进程注入", "exploit")),
    ("macos-security-bypass", ("苹果防护绕过", "bypass")),
    ("memory-forensics-volatility", ("内存镜像", "binary")),
    ("mobile-ssl-pinning-bypass", ("证书绑定", "bypass")),
    ("network-protocol-attacks", ("局域网协议", "test")),
    ("nosql-injection", ("NoSQL注入", "exploit")),
    ("ntlm-relay-coercion", ("NTLM中继", "cred")),
    ("oauth-oidc-misconfiguration", ("第三方登录", "test")),
    ("open-redirect", ("开放重定向", "test")),
    ("path-traversal-lfi", ("路径穿越", "test")),
    ("prototype-pollution-advanced", ("原型链进阶", "exploit")),
    ("prototype-pollution", ("原型链污染", "test")),
    ("race-condition", ("条件竞争", "test")),
    ("recon-and-methodology", ("信息收集", "test")),
    ("recon-for-sec", ("信息收集", "test")),
    ("request-smuggling", ("请求走私", "test")),
    ("reverse-shell-techniques", ("反弹shell", "exploit")),
    ("rsa-attack-techniques", ("RSA参数", "crypto")),
    ("saml-sso-assertion-attacks", ("单点登录断言", "test")),
    ("sandbox-escape-techniques", ("沙箱逃逸", "escape")),
    ("smart-contract-vulnerabilities", ("智能合约", "test")),
    ("sqli-sql-injection", ("SQL注入", "exploit")),
    ("ssrf-server-side-request-forgery", ("服务端请求伪造", "test")),
    ("ssti-server-side-template-injection", ("模板注入", "exploit")),
    ("stack-overflow-and-rop", ("栈溢出", "exploit")),
    ("steganography-techniques", ("隐写图片", "binary")),
    ("subdomain-takeover", ("子域名接管", "test")),
    ("symbolic-execution-tools", ("符号执行", "binary")),
    ("symmetric-cipher-attacks", ("分组密码", "crypto")),
    ("traffic-analysis-pcap", ("流量包", "binary")),
    ("tunneling-and-pivoting", ("内网隧道", "move")),
    ("type-juggling", ("弱类型比较", "bypass")),
    ("unauthorized-access-common-services", ("中间件未授权", "test")),
    ("upload-insecure-files", ("文件上传", "test")),
    ("vm-and-bytecode-reverse", ("虚拟机壳", "binary")),
    ("waf-bypass-techniques", ("防护墙", "bypass")),
    ("web-cache-deception", ("缓存投毒", "test")),
    ("websocket-security", ("长连接", "test")),
    ("windows-av-evasion", ("杀软免杀", "bypass")),
    ("windows-lateral-movement", ("域内横移", "move")),
    ("windows-privilege-escalation", ("Windows提权", "privesc")),
    ("xslt-injection", ("样式表注入", "exploit")),
    ("xss-cross-site-scripting", ("跨站脚本", "test")),
    ("xxe-xml-external-entity", ("外部实体", "test")),
]

FRAMES = {
    "test": ["看看有没有{t}问题", "{t}怎么测", "{t}从哪下手", "帮忙看下{t}", "这块{t}能过吗"],
    "bypass": ["{t}被拦了怎么办", "{t}怎么绕", "看看{t}能不能绕过", "{t}有办法进吗"],
    "exploit": ["{t}怎么打", "{t}从哪突破", "怀疑有{t}怎么验证"],
    "binary": ["这个{t}怎么看", "{t}从哪入手", "{t}跑不起来怎么办"],
    "crypto": ["这组{t}参数怎么解", "{t}从哪下手", "拿到了{t}怎么还原"],
    "cred": ["{t}配错了能怎么利用", "抓到{t}之后怎么走", "{t}这条线怎么打"],
    "move": ["进来之后{t}怎么做", "{t}走不通换啥", "内网里{t}怎么弄"],
    "escape": ["卡住了{t}怎么做", "{t}有路子吗", "从这儿{t}出去看看"],
    "privesc": ["拿到低权限shell怎么{t}", "{t}有哪些路子", "这台机器能{t}吗"],
}

CTF_FRAMES = ["这道{t}从哪下手", "{t}题怎么做", "帮我看看这道{t}", "{t}没思路了", "这道{t}卡住了"]
TOOL_FRAMES = ["{t}命令怎么配", "用{t}先扫什么", "{t}跑不出结果怎么办", "{t}参数老错怎么调"]
DELIVERY_FRAMES = ["{t}这块怎么做", "{t}出问题了从哪查", "帮忙弄一下{t}", "{t}有现成的章法吗"]
DESC_FRAMES = ["{t}怎么做", "{t}从哪下手"]
DESC_STRIP_HEAD = ("适用于", "适合", "用于", "覆盖", "包括", "提供", "支持", "实现")
DESC_STRIP_TAIL = ("场景", "能力", "相关")
DESC_STOP = {"适用于", "场景", "融合", "能力", "覆盖", "支持", "提供",
             "实现", "构建", "以及", "包括", "例如", "通过", "进行",
             "使用", "可以", "需要", "相关", "对应", "以及", "以及"}

def desc_cjk_topics(record, maxn=3):
    """Chinese capability topics mined from a rich Chinese legacy_description."""
    ext = record.get("extensions") or {}
    desc = ext.get("legacy_description", "") or ""
    if not has_cjk(desc) or desc.startswith("Adapted capability"):
        return []
    topics, seen = [], set()
    for seg in re.split(r"[、。；，,：:；（）()\[\]/+\s×·\-—]+", desc):
        for run in re.findall("[" + CJK + "]{2,8}", seg):
            for h in DESC_STRIP_HEAD:
                if run.startswith(h) and len(run) > len(h) + 1:
                    run = run[len(h):]
                    break
            for t_ in DESC_STRIP_TAIL:
                if run.endswith(t_) and len(run) > len(t_) + 1:
                    run = run[:-len(t_)]
                    break
            if run in DESC_STOP or len(run) < 2:
                continue
            if run not in seen:
                seen.add(run)
                topics.append(run)
            if len(topics) >= maxn:
                return topics
    return topics
WORKFLOW_ZH = {
    "ai-ml-engineer": "模型落地", "api-designer": "接口设计",
    "automation-qa": "自动化测试", "backend-engineer": "后端实现",
    "data-analyst": "数据分析", "database-engineer": "数据库",
    "devops-engineer": "运维发布", "frontend-engineer": "前端页面",
    "fullstack-engineer": "全栈联调", "product-manager": "产品规划",
    "project-manager": "项目排期", "qa-engineer": "质量保障",
    "security-engineer": "安全自查", "sre-operations": "线上运维",
    "technical-writer": "技术文档", "ui-ux-designer": "界面设计",
}
WORKFLOW_FRAMES = ["{t}怎么做", "{t}卡住了找谁", "帮忙把{t}理一理", "{t}出问题从哪查"]

# EN tech word -> Chinese (delivery slug humanize fallback)
TECH_ZH = {
    "api": "接口", "auth": "鉴权", "permission": "权限", "endpoint": "端点",
    "design": "设计", "error": "报错", "handling": "处理", "idempotency": "幂等",
    "retry": "重试", "openapi": "文档", "mock": "造数", "pagination": "翻页",
    "filtering": "筛选", "request": "请求", "response": "响应", "resource": "资源",
    "modeling": "建模", "versioning": "版本", "webhook": "回调", "async": "异步",
    "contract": "契约", "testing": "测试", "coverage": "覆盖率", "reporting": "报告",
    "e2e": "端到端", "integration": "联调", "unit": "单测", "implementation": "实现",
    "jobs": "任务", "caching": "缓存", "strategy": "策略", "data": "数据",
    "access": "访问", "resilience": "容错", "microservice": "微服务", "observability": "可观测",
    "ab": "AB实验", "analysis": "分析", "report": "报告", "visualization": "可视化",
    "metric": "指标", "sql": "SQL", "safety": "安全", "index": "索引",
    "migration": "迁移", "rollout": "上线", "query": "查询", "review": "评审",
    "schema": "表结构", "ci": "流水线", "cd": "发布", "pipeline": "流水线",
    "container": "容器", "orchestration": "编排", "monitoring": "监控",
    "alerting": "告警", "networking": "网络", "gateway": "网关", "release": "发版",
    "secrets": "密钥", "config": "配置", "accessibility": "无障碍", "component": "组件",
    "architecture": "架构", "fetching": "请求", "forms": "表单", "validation": "校验",
    "mobile": "移动端", "hybrid": "混合", "performance": "性能", "optimization": "优化",
    "routing": "路由", "navigation": "导航", "state": "状态", "management": "管理",
    "styling": "样式", "system": "体系", "frontend": "前端", "customer": "用户",
    "journey": "旅程", "mvp": "最小版本", "scoping": "划范围", "opportunity": "机会",
    "tree": "树", "probe": "试探", "positioning": "定位", "user": "用户",
    "story": "故事", "change": "变更", "control": "管控", "critical": "关键",
    "path": "路径", "handoff": "交接", "protocol": "协议", "milestone": "里程碑",
    "gate": "门禁", "progress": "进度", "tracking": "跟踪", "retrospective": "复盘",
    "risk": "风险", "acceptance": "验收", "regression": "回归", "case": "用例",
    "audit": "审计", "dependency": "依赖", "threat": "威胁", "vulnerability": "漏洞",
    "capacity": "容量", "planning": "规划", "incident": "事故", "response": "响应",
    "log": "日志", "call": "值班", "on": "值班", "runbook": "手册", "postmortem": "复盘",
    "reliability": "可靠性", "engineering": "工程", "documentation": "文档",
    "doc": "文档", "notes": "记录", "guide": "手册", "atomic": "原子", "states": "状态",
    "tokens": "变量", "enterprise": "后台", "patterns": "模式", "information": "信息",
    "page": "页面", "structure": "结构", "responsive": "自适应", "usability": "易用",
    "evaluation": "评估", "flow": "流程", "visual": "视觉", "style": "风格",
    "llm": "大模型", "rag": "知识库问答", "ml": "模型", "ai": "智能",
    "deployment": "部署", "training": "训练", "engineer": "工程",
    "backend": "后端", "operations": "运维", "security": "安全", "quality": "质量",
    "writer": "写作", "designer": "设计", "manager": "管理", "test": "测试",
    "delivery": "交付", "fullstack": "全栈", "product": "产品", "project": "项目",
    "technical": "技术", "database": "数据库", "devops": "运维", "sre": "稳定性",
    "qa": "测试", "ui": "界面", "ux": "体验", "analyst": "分析",
    "consistency": "一致性", "multitenancy": "多租户", "infrastructure": "基础设施",
    "code": "代码", "prioritization": "排优先级", "wbs": "任务分解",
    "decomposition": "拆分", "backup": "备份", "restore": "恢复",
    "seeding": "造数", "masking": "脱敏", "retention": "留存",
}

BANNED_BARE = {"测试", "漏洞", "分析", "注入", "安全", "检测", "扫描", "审计",
               "评估", "检查", "利用", "攻击", "防御", "加固", "渗透", "绕过",
               "提权", "越权", "取证", "逆向", "部署", "运维", "文档", "设计"}

# canonical -> record anchor overrides (alias value lives in body/desc, not slug)
ANCHOR_OVERRIDE = {
    "spring": ["expression-language-injection"],
    "shiro": ["deserialization-insecure"],
    "log4j": ["jndi-injection"],
    "fastjson": ["deserialization-insecure"],
    "thinkphp": ["sqli-sql-injection"],
    "nosql": ["nosql-injection"],
    "csv": ["csv-formula-injection"],
    "heap": ["heap-exploitation"],
    "cmdi": ["cmdi-command-injection"],
    "traversal": ["path-traversal-lfi"],
    "tunnel": ["tunneling-and-pivoting"],
}

def name_tail(record):
    """Original name with importer boilerplate stripped (delivery prefix, CTF bullets)."""
    ext = record.get("extensions") or {}
    orig = (ext.get("legacy_original_name", "") or "").strip()
    low = orig.lower()
    for pre in ("community-ai-fullstack-delivery-", "community-",
                "ctf-", "ctf•", "strix-", "strix•"):
        if low.startswith(pre):
            orig = orig[len(pre):]
            low = orig.lower()
            break
    return orig

# generic canonicals: anchor only on a long/specific value, never on the bare key
GENERIC_CANON = {"ctf", "web", "api", "reverse", "delivery", "apk", "ios"}

def alias_anchored(record, aliases):
    """Chinese alias values whose canonical is anchored in the record's name text.

    Match surface = boilerplate-stripped original name + source_path slug dir.
    A generic canonical (ctf/web/api/...) anchors only via a specific value
    (EN len>=5 or a CJK value literally present), never via its bare short key.
    """
    ext = record.get("extensions") or {}
    slug = (record.get("source_path", "") or "").lower()
    slugdir = slug.split("/")[-2] if "/" in slug else slug
    tail = name_tail(record).casefold()
    surface = tail + " " + slugdir
    out = []
    for canon, values in aliases.items():
        vals = [str(v) for v in values]
        generic = str(canon) in GENERIC_CANON
        anchored = False
        for v in vals:
            vl = v.casefold()
            if has_cjk(v):
                if vl in surface:
                    anchored = True
                    break
            elif len(v) >= 5 and vl in surface:
                anchored = True
                break
            elif (not generic) and len(v) >= 3 and vl in slugdir.split("-"):
                anchored = True
                break
        if not anchored:
            for frag in ANCHOR_OVERRIDE.get(str(canon), []):
                if frag in slug:
                    anchored = True
                    break
        if anchored:
            for v in vals:
                if has_cjk(v) and 2 <= len(v) <= 12:
                    out.append(v)
    seen, res = set(), []
    for v in out:
        if v not in seen:
            seen.add(v)
            res.append(v)
    return res

def hack_topic(record):
    slug = (record.get("source_path", "") or "").lower()
    for frag, (topic, group) in HACK_TOPICS:
        if frag in slug:
            return topic, group
    return None, None

def humanize_slug(slugdir):
    parts = re.split(r"[-_]", slugdir.lower())
    zh = [TECH_ZH.get(p, "") for p in parts]
    zh = [z for z in zh if z]
    return "".join(zh) if zh else ""

def gen_candidates(record, aliases):
    src = record.get("source", "")
    ext = record.get("extensions") or {}
    orig = ext.get("legacy_original_name", "") or ""
    slug = (record.get("source_path", "") or "")
    slugdir = slug.split("/")[-2] if "/" in slug else slug.replace("/SKILL.md", "")
    cands = []
    cands += alias_anchored(record, aliases)
    if src == "hack-skills":
        topic, group = hack_topic(record)
        if topic and group:
            for f in FRAMES[group]:
                cands.append(f.format(t=topic))
        else:
            cands.append("这个%s从哪下手" % slugdir.replace("-", ""))
    elif src == "ctf-super-hub":
        short = re.sub(r"^(CTF.|Strix.)", "", orig)
        if re.search(r"(ffuf|httpx|katana|nuclei|sqlmap)", slugdir, re.I):
            tool = slugdir.split("-")[-1]
            for f in TOOL_FRAMES:
                cands.append(f.format(t=tool))
        else:
            for f in CTF_FRAMES:
                cands.append(f.format(t=short))
    elif src == "ai-fullstack-delivery":
        if slug.endswith("skills/SKILL.md"):
            wf = slug.split("/")[-3] if slug.count("/") >= 2 else slugdir
            topic = WORKFLOW_ZH.get(wf, wf)
            for f in WORKFLOW_FRAMES:
                cands.append(f.format(t=topic))
        else:
            topic = humanize_slug(slugdir)
            if topic:
                for f in DELIVERY_FRAMES:
                    cands.append(f.format(t=topic))
            else:
                for f in DELIVERY_FRAMES:
                    cands.append(f.format(t=slugdir.replace("-", "")))
        for dt in desc_cjk_topics(record):
            for f in DESC_FRAMES:
                cands.append(f.format(t=dt))
        if len(cands) < 3:
            # last resort: distinctive tool word from the record's own keywords
            for kw in record.get("keywords", []):
                kl = str(kw).lower()
                if kl in ("project", "skills-hub", "upstream",
                          "ai-fullstack-delivery-workflow", "workflows",
                          "adapted", "capability"):
                    continue
                if re.search(r"[a-z0-9]", kl) and len(kl) >= 3:
                    cands.append("%s这块怎么做" % kw)
                    cands.append("用%s从哪开始" % kw)
                    break
    elif src == "apk-reverse-community":
        cands += ["这个安装包能瘦身吗", "这包弹广告能去吗", "这包抓包抓不到怎么办"]
    seen, res = set(), []
    for c in cands:
        c = c.strip()
        if not c or c in seen:
            continue
        if c in BANNED_BARE:
            continue
        if len(c) < 2 or len(c) > 20:
            continue
        seen.add(c)
        res.append(c)
    return res

# ------------------------------------------------------------- corpus check
def load_corpus_text():
    texts = []
    for p in (BENCH1, BENCH2, CASES):
        try:
            d = json.load(open(p, encoding="utf-8"))
            texts.append(json.dumps(d, ensure_ascii=False))
        except Exception as e:
            print("corpus skip %s: %s" % (p, e))
    try:
        for name in sorted(os.listdir(HITRATE_GLOB_DIR)):
            if not name.startswith("hitrate-"):
                continue
            dp = os.path.join(HITRATE_GLOB_DIR, name)
            for root, _, files in os.walk(dp):
                for fn in files:
                    if fn.endswith((".json", ".md", ".csv")):
                        fp = os.path.join(root, fn)
                        try:
                            if os.path.getsize(fp) > 600000:
                                continue
                            texts.append(open(fp, encoding="utf-8",
                                              errors="ignore").read())
                        except Exception:
                            pass
    except Exception as e:
        print("hitrate walk skip: %s" % e)
    return "\n".join(texts)

def windows8(s):
    runs = cjk_runs(s)
    out = set()
    for r in runs:
        for i in range(len(r) - 7):
            out.add(r[i:i + 8])
    return out

def main():
    mode_sample = "--sample" in sys.argv
    mode_report = "--report" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    if mode_report:
        write_report()
        return
    records = load_registry()
    print("records: %d" % len(records))
    aliases = load_aliases()
    print("aliases canonical: %d" % len(aliases))
    assert len(records) == 293, "registry count changed: %d" % len(records)

    corpus = load_corpus_text()
    corpus_wins = set()
    for m in re.finditer("[" + CJK + "]{8,}", corpus):
        run = m.group(0)
        for i in range(len(run) - 7):
            corpus_wins.add(run[i:i + 8])
    print("corpus 8-windows: %d" % len(corpus_wins))

    entries = []
    no_suggest = []
    copy_hits = []
    for r in records:
        cands = gen_candidates(r, aliases)
        clean, reserve = [], []
        for c in cands:
            bad = windows8(c) & corpus_wins
            if bad:
                copy_hits.append({"id": r["id"], "dropped": c,
                                  "window": sorted(bad)[0]})
                reserve.append(c)
            else:
                clean.append(c)
        picked = clean[:6]
        if len(picked) < 3:
            no_suggest.append({"id": r["id"], "source": r.get("source"),
                               "reason": "candidates<3 after filters",
                               "candidates": clean})
            picked = clean
        entries.append({
            "id": r["id"], "source": r.get("source", ""),
            "existing_keywords": r.get("keywords", []),
            "suggested_zh": picked,
            "_reserve": [c for c in clean[6:] + reserve],
            "evidence": evidence_of(r),
        })

    cnt = Counter()
    for e in entries:
        for s in e["suggested_zh"]:
            cnt[s] += 1
    over = sorted([s for s, n in cnt.items() if n > 8])
    dropped_disc = []
    for e in entries:
        keep = []
        for s in e["suggested_zh"]:
            if s in over:
                dropped_disc.append({"id": e["id"], "dropped": s,
                                     "count": cnt[s]})
            else:
                keep.append(s)
        e["suggested_zh"] = keep
    for e in entries:
        while len(e["suggested_zh"]) < 3 and e["_reserve"]:
            c = e["_reserve"].pop(0)
            if c in over or (windows8(c) & corpus_wins):
                continue
            if c in e["suggested_zh"]:
                continue
            e["suggested_zh"].append(c)
    still_short = [e["id"] for e in entries if len(e["suggested_zh"]) < 3]
    covered = sum(1 for e in entries if len(e["suggested_zh"]) >= 3)

    for e in entries:
        e.pop("_reserve", None)
    doc = {"schemaVersion": 1,
           "note": "由 gen-zh-keywords.py 生成；供后续卡决定如何接入",
           "entries": entries}
    json.dump(doc, open(os.path.join(OUT, "suggestions.json"),
                        "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    checks = {"total": len(records), "covered_ge3": covered,
              "no_suggestion": no_suggest, "still_short": still_short,
              "discrimination_dropped": dropped_disc,
              "discrimination_over8": [{"s": s, "count": cnt[s]} for s in over],
              "copy_dropped": copy_hits}
    json.dump(checks, open(os.path.join(OUT, "checks.json"),
                           "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("covered>=3: %d/293  no_suggest: %d  still_short: %d" %
          (covered, len(no_suggest), len(still_short)))
    print("discrimination drops: %d  copy drops: %d" %
          (len(dropped_disc), len(copy_hits)))

    if mode_sample:
        run_sampling(entries)

SAMPLE_PLAN = [
    ("community-hack-skills-063", 0), ("community-hack-skills-116", 0),
    ("community-hack-skills-082", 0), ("community-hack-skills-036", 0),
    ("community-hack-skills-137", 0), ("community-hack-skills-117", 0),
    ("community-hack-skills-092", 1), ("community-hack-skills-057", 0),
    ("community-ai-fullstack-delivery-139", 0),
    ("community-ai-fullstack-delivery-140", 0),
    ("community-ai-fullstack-delivery-153", 1),
    ("community-ai-fullstack-delivery-207", 2),
    ("community-ai-fullstack-delivery-252", 0),
    ("community-ai-fullstack-delivery-261", 1),
    ("community-ctf-super-hub-004", 0), ("community-ctf-super-hub-009", 1),
    ("community-ctf-super-hub-012", 2), ("community-ctf-super-hub-031", 0),
    ("community-ctf-super-hub-032", 0), ("community-ctf-super-hub-002", 0),
    ("community-apk-reverse-community-293", 2),
]

def route_hint(hint):
    p = subprocess.run(
        [sys.executable, os.path.join(REPO, "skills", "scripts",
                                      "community-route.py"),
         "--hint", hint, "--json"],
        capture_output=True, text=True, timeout=120)
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"status": "ERROR", "raw": (p.stdout + p.stderr)[:500]}

def run_sampling(entries):
    by_id = {e["id"]: e for e in entries}
    results = []
    for rid, idx in SAMPLE_PLAN:
        e = by_id[rid]
        sugg = e["suggested_zh"][min(idx, len(e["suggested_zh"]) - 1)]
        d = route_hint(sugg)
        refs = []
        for m in d.get("matches", []) or []:
            for ref in m.get("references", []) or []:
                refs.append(ref.get("id"))
        hit = rid in refs
        results.append({"id": rid, "hint": sugg, "status": d.get("status"),
                        "hit": hit, "top_refs": refs[:6]})
        print("%s %s -> %s hit=%s" % (rid, sugg, d.get("status"), hit))
    json.dump(results, open(os.path.join(OUT, "sampling.json"),
                            "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n_hit = sum(1 for r in results if r["hit"])
    print("sampling hit: %d/20" % n_hit)

def write_report():
    sug = json.load(open(os.path.join(OUT, "suggestions.json"), encoding="utf-8"))
    chk = json.load(open(os.path.join(OUT, "checks.json"), encoding="utf-8"))
    try:
        samp = json.load(open(os.path.join(OUT, "sampling.json"), encoding="utf-8"))
    except Exception:
        samp = []
    n_hit = sum(1 for r in samp if r.get("hit"))
    from collections import Counter as C
    per_src = C(e["source"] for e in sug["entries"])
    lines = []
    lines.append("# zh-keywords 报告（建议文件，不改 registry）")
    lines.append("")
    lines.append("- 产出：`suggestions.json`（schemaVersion 1），共 %d 条；" % len(sug["entries"])
                 + "来源分布：" + "、".join("%s %d" % kv for kv in sorted(per_src.items())) + "。")
    lines.append("- 覆盖度：%d/293 达标（每条 3-6 个中文说法）；" % chk["covered_ge3"]
                 + "给不出建议：%d 条。" % len(chk["no_suggestion"]))
    for n in chk["no_suggestion"]:
        lines.append("  - %s（%s）：%s" % (n["id"], n["source"], n["reason"]))
    if chk["still_short"]:
        lines.append("- 补足后仍不足 3 条：" + ", ".join(chk["still_short"]))
    else:
        lines.append("- 区分度过滤后不足 3 条：无（全部补足）。")
    lines.append("")
    lines.append("## 区分度过滤（>8 条命中即删）")
    if chk["discrimination_over8"]:
        for o in chk["discrimination_over8"]:
            lines.append("- `%s`：%d 条 → 已删并记录" % (o["s"], o["count"]))
    else:
        lines.append("- 无：没有任何建议词同时出现在 >8 条记录里。")
    lines.append("- 明细：删 %d 条次（见 checks.json discrimination_dropped）。"
                 % len(chk["discrimination_dropped"]))
    lines.append("")
    lines.append("## 抄题校验（与 hitrate-*/benchmark/cases 比 ≥8 连续汉字）")
    lines.append("- 删 %d 条（见 checks.json copy_dropped），"
                 % len(chk["copy_dropped"]) + "剩余建议与语料无 ≥8 连续汉字相同。")
    for c in chk["copy_dropped"][:20]:
        lines.append("  - %s：`%s`（窗 `%s`）" % (c["id"], c["dropped"], c["window"]))
    lines.append("")
    lines.append("## 抽样实测（建议词直跑 community-route.py --hint）")
    lines.append("- 结果：%d/20 命中目标记录（sampling.json 存逐条 status/top_refs）。" % n_hit)
    for r in samp:
        lines.append("  - %s | `%s` | %s | 命中=%s | %s" %
                     (r["id"], r["hint"], r["status"], r["hit"],
                      ",".join(r["top_refs"][:3])))
    if samp:
        miss = [r for r in samp if not r["hit"]]
        lines.append("- 未命中 %d 条的原因：当前 registry/别名层尚无这些中文说法，"
                     % len(miss) + "正是本建议文件要补的缺口；命中多集中在已有别名锚定的词。")
    lines.append("")
    lines.append("## 建议的接入方式（供后续卡定夺）")
    lines.append("- 方案 A：把 suggestions.json 作为 curated 信号层读入（仿 routing-signals.json），"
                 + "每条建议词正则锚定到对应记录 id；改 router，不改 registry。")
    lines.append("- 方案 B：并入 community-route.py ALIASES（每记录 1-2 个高区分度词），"
                 + "走别名替换+命中权重；同样不碰 registry。")
    lines.append("- 两种都不改 registry.json（导入器产物），与并行卡的 routing.json 机制正交；"
                 + "建议先小批量（如 20 条）灰度看 hitrate 变化。")
    open(os.path.join(OUT, "REPORT.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("REPORT.md written")

if __name__ == "__main__":
    main()
