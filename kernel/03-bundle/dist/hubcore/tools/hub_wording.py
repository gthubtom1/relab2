# -*- coding: utf-8 -*-
"""confirm 措辞、占位符、空成功金句。字写清楚，不为卡行数挤掉。"""
import re
import unicodedata
from hub_io import KIND_TO_KEY, CANDIDATE_BOUND_ARTIFACTS, SKELETON_FIELDS as _SKELETON_FIELDS
_FAKE_EXACT = frozenset({
    "todo", "tbd", "xxx", "n/a", "na", "unknown", "未知", "unverified",
    "占位", "待填", "未测", "没测", "待确认", "未验证", "已处理", "处理好",
    "done", "ok", "pass",
})
_FAKE_SUB = ("todo", "tbd", "unverified", "占位符", "待填", "待确认", "未确认", "未验证", "尚未观察")
_LAUNCHER_TAINT = (
    "launcher-only", "仅启动器", "启动器亮", "启动器拉", "启动器起来",
    "窗口开了", "窗口出来", "窗口打开", "窗口亮了", "窗口亮",
    "主窗口已显示", "程序界面弹", "界面弹出来",
)
_EMPTY_TALK = ("核对无误", "可以继续", "符合预期", "用户点头", "用户确认", "没有明显问题", "看起来没有")
_SCOPE_CUT = (
    "测中枢", "测试中枢", "不深入", "跳过", "先这样",
    "不挡这次", "不挡这一次", "不必挡", "接着往下做", "合格就记下",
)
_SKIP_OK_STOPS = frozenset({"产品边界确认", "覆盖更新与官方更新确认"})
_SCRIPT_LAUNCH = (
    "脚本直开", "脚本实测", "直开核心", "直接开核心", "绕过启动器", "脚本运行核心",
)
_LICENSE_HARD = (
    "只拦了启动器", "只拦启动器", "检查授权就算", "检查授权即",
    "检查授权就是", "检查授权等于", "字段写了过期",
    "直接接正式", "先连生产", "先连上生产", "接到正式机", "正式租户",
    "藏页交差", "藏页当第一种", "页藏当第一种", "藏页即第一种", "页藏即第一种",
    "藏页就算第一种", "页藏就算第一种", "藏页过第一种", "页已藏即第一种",
    "宽限就是多台", "宽限等于同时", "宽限就是同时", "断网宽限当同时",
    "宽限当同时登录", "宽限就是同时登录",
    "最大设备数跟着已售", "已售跟着最大设备",
    "RATE_LIMITED就停", "RATE_LIMITED当停", "RATE_LIMITED当挤机",
    "限流就关", "限流当挤机", "暂时失败就关",
    "间隔塞进到期", "验证间隔交给核心", "cache_until交给核心",
    "20秒当到期", "用验证间隔过门",
    "自己关当挤机", "自己关了当挤机", "自己关当成挤机",
    "给核心的可用时长跟验证租约走", "核心租约=验证窗口",
    "核心租约等于验证窗口", "验证租约交给核心",
    "到期也必须再问才关", "到期也必须再问平台才关",
    "到期后等下一次验证才关", "到期后再问才关",
    "20秒硬刷", "客户端20秒硬刷",
)
_CUT_ALL = ("一刀切", "公共序列化", "全部开关", "所有开关", "全部布尔", "所有布尔")
_MUTUAL_VOTE = ("互攻同意", "评比通过", "评比后通过", "子代理一致通过", "互攻后认为可以")
_PACK_PY = (
    "依赖本机 Python", "依赖本机 python", "依赖本机Python", "依赖本机python",
    "PATH 里的 Python", "PATH 里的 python", "PATH里的Python", "PATH里的python",
)
_PACK_SYS = (
    "系统自带的 Python", "系统自带的 python",
    "系统自带的Python", "系统自带的python",
)
_PY_NEG = (
    "不调用", "不使用", "不用", "禁止调用", "禁止使用", "禁止用",
    "不再调用", "不再使用", "不要调用", "不要使用", "并非调用", "没有调用", "未调用",
)
_WRAP = set("「」『』“”‘’\"'()（）[]【】")
_OBEY_TAIL = ("不能confirm", "不能点绿", "不能过门")
_UPDATE_HARD = ("平台能下就算", "平台能下当", "平台能下 ZIP", "平台能下zip",
                "平台能下载zip", "平台能下载 ZIP", "平台能下.zip",
                "平台可以下zip", "平台能够下zip", "平台能下的zip",
                "换了一份没验", "没验过的字节", "以后再说",
                "只覆盖官方更新", "只覆盖官方")
_UPDATE_COVER_OK = (
    "覆盖安装", "盖成同一软件", "盖成同一个软件",
    "已装软件里点更新", "已装旧命令", "生产租户",
)
_UPDATE_OFFICIAL_OK = ("官方更新改道", "进三条通道", "按三条通道")
# 紧贴前缀才算否定。禁止 4 字窗里扫到「不/没/非/禁」（不错/没问题/非常/已禁用 会打穿跳过门）。
_NEG_IMMEDIATE = (
    "不要", "不再", "不是", "并非", "没有", "禁止", "不能", "不可",
    "不许", "决不", "绝不", "并未", "也未", "更未", "请勿", "切勿", "请别", "勿", "别", "没",
    "未", "不",
)
_ARCH_SWALLOW = (
    "形态已定", "先定架构", "架构就这样", "细节以后再说",
    "形态以后再说", "就这样定", "先按这个架构",
)
_FAKE_COVER = ("另装文件夹", "另装一个文件夹", "另一个目录", "另装一份")
_HTTP_EMPTY = (
    "健康检查", "打开页", "打开了页", "打开首页",
    "接口 200", "接口200", "HTTP 200", "HTTP200", "curl 200", "/health", "/healthz",
)
# 不要裸「全部通过」：主功能全部通过真人点测 会误伤。
_TEST_GREEN = (
    "测试绿", "测试全绿", "pytest 绿", "pytest绿", "单测绿", "单元测试绿",
    "pytest 全部通过", "pytest全部通过", "全部测试通过", "所有测试通过",
    "cargo test 全部通过", "cargo全部通过",
    "npm test 全部通过", "npm全部通过",
    "单测返回 0", "单测返回0",
    "功能已完成", "已搞定",
)
_MIG_0 = ("迁移脚本退出 0", "迁移脚本退出0")
_TEST_FAKE = _HTTP_EMPTY + ("报缺",)
_WIN_EMPTY = ("窗口亮了", "窗口亮", "按钮能点", "主按钮能点")
# 按停点名绑，不按阶段 id（桌面 6-update ≠ 二开覆盖更新）。
_EMPTY_BY_STOP = {
    "架构确认": _ARCH_SWALLOW,
    "架构与风险测绘确认": _ARCH_SWALLOW + ("模块表",),
    "核心功能实现确认": _TEST_GREEN + ("能编译", "编译过了") + _MIG_0 + _TEST_FAKE + _WIN_EMPTY,
    "核心可用确认": _TEST_GREEN,
    "界面与核心回归确认": _TEST_GREEN,
    "首次启动验收确认": ("开发机", "本机 docker", "本机 Docker", "本机容器") + _TEST_GREEN + _TEST_FAKE + _WIN_EMPTY,
    "更新回滚演练确认": _FAKE_COVER + _TEST_GREEN + _MIG_0,
    "覆盖更新与官方更新确认": _FAKE_COVER,
    "交付验收确认": _TEST_GREEN + _HTTP_EMPTY + _TEST_FAKE + _WIN_EMPTY,
    "核心接口与页面实现确认": _TEST_FAKE + _TEST_GREEN + _MIG_0 + _WIN_EMPTY
        + ("本机容器", "本机 docker", "本机 Docker"),
    "预发环境冒烟确认": ("本机容器", "本机 docker", "本机 Docker", "本机 curl", "本机curl", "首次启动") + _HTTP_EMPTY + _TEST_GREEN,
    "上线回滚演练确认": _HTTP_EMPTY + _TEST_GREEN,
    "数据迁移与备份确认": _MIG_0,
    "核心命令实现确认": ("--help",) + _TEST_GREEN + _MIG_0 + _WIN_EMPTY,
    "干净环境首次运行确认": ("--help", "开发机") + _TEST_GREEN,
    "分发包与跨平台确认": ("一个本机包", "只交一个本机包") + _TEST_GREEN,
    "现状盘点确认": ("读了说明书", "读说明书", "读了 README", "看了 README"),
    "构建测试基线确认": ("能编译", "缓存能编", "编译过了") + _TEST_GREEN,
    "构建候选确认": ("能编译", "编译过了") + _TEST_GREEN,
    "发布候选确认": ("能编译", "编译过了") + _TEST_GREEN,
    "安装包确认": _TEST_GREEN + _TEST_FAKE,
    "需求合同确认": _TEST_GREEN + _TEST_FAKE + _WIN_EMPTY,
    "给别人的包确认": _TEST_GREEN,
    "发布回滚演练确认": _FAKE_COVER + _TEST_GREEN,
    "安全网与改造计划确认": _TEST_GREEN,
    "改造实现确认": _TEST_GREEN + _MIG_0 + _WIN_EMPTY,
}
_HANG = ("下载卡住", "下载转圈", "下载未完成", "下载没完", "仍会转圈", "一直转圈")
_HANG_OK = ("不挡", "不拦", "不影响点头", "不阻碍", "不必挡")
_SEP = set(" \t\r\n,，、。.;；;:：/\\|!！?？()（）[]【】+=「」『』“”‘'")
_LATER_SEP = _SEP | set("·・…\u3000\u200b\u200c\u200d\ufeff\u2060-")
_TRANSPORT = frozenset({"installer", "exe", "zip", "in-place"})
def _tokens(text):
    out, buf = [], []
    for ch in text:
        if ch in _SEP:
            if buf:
                out.append("".join(buf))
                buf = []
        else:
            buf.append(ch)
    if buf:
        out.append("".join(buf))
    return out
def _nosep(low):
    return "".join(ch for ch in low if ch not in _SEP)
def _later_nosep(text):
    return "".join(ch for ch in text if ch not in _LATER_SEP)
def _later_as_space(ch):
    """英文门：标点、零宽、表情当空格；汉字和字母数字留下。"""
    if ch.isspace() or ch in _LATER_SEP:
        return True
    if "\u4e00" <= ch <= "\u9fff":
        return False
    if ch.isascii() and ch.isalnum():
        return False
    return True
_FILLER_LETTERS = frozenset({
    "hello", "world", "helloworld", "helloworlds",
    "apply", "save", "applysave",
    "unknownerror", "errorunknown",
})
_JINGLE_RUNS = (
    "春夏秋冬子午卯酉",
    "乾坤坎离震巽艮兑",
    "甲乙丙丁戊己庚辛",
)
_CAMEL_API = re.compile(r"[A-Z][a-z]+[A-Z][a-z]+[A-Z]")
_ERROR_PAD = set("的了啊吗呢吧呀哦嗯")
_ERROR_PAD_TAIL = ("请重试", "请刷新", "请再试", "请稍候")
# 紧挨着的窗口动作，不是整段搜短词。长的先匹配。
_PAD_TAIL_REAL_FOLLOW = (
    "按确定继续", "点击确定", "点确定", "按确定", "点登录",
    "保存到云端", "继续办理", "登录按钮",
)
_PAD_TAIL_CONNECTOR = ("然后", "后")
_PAD_TAIL_END_OK = ("请刷新", "请稍候")
_ERROR_PAD_HEAD = ("弹出", "提示", "显示", "出现", "错误")
_GATE_LABEL = ("动作门",)
def _copied_window_error(inner):
    """整句是窗口报错才算。夹在瞎写英文里的 unknown error 不算。"""
    spaced = "".join(" " if _later_as_space(ch) else ch for ch in inner)
    body = "".join(spaced.split())
    low = body.lower()
    if body == "未知错误" or low in ("unknownerror", "errorunknown"):
        return True
    if re.fullmatch(r"unknownerror0x[0-9a-f]+", low):
        return True
    core = re.sub(r"^error[:\-]*", "", low)
    return core == "unknownerror"
def _later_filler_core(inner):
    """包装/垫字后仍是 hello world、口诀或垫过的报错句，就算空。"""
    if _copied_window_error(inner):
        return False
    letters = "".join(ch for ch in inner if ch.isascii() and ch.isalpha()).lower()
    if letters in _FILLER_LETTERS:
        # 只在「整句除掉英文后没剩下正经中文」时当废话。
        # 不要把「请点击 Apply 保存到云端」里的 Apply 抽出来判空。
        # 也不要在正经中文里搜「请刷新」子串：请刷新后点击 Apply 继续办理。
        rest_cjk = "".join(ch for ch in inner if "\u4e00" <= ch <= "\u9fff")
        if _cjk_rest_is_whole_pad(rest_cjk):
            return True
    if letters.startswith("unknownerror"):
        extra = letters[len("unknownerror"):]
        if extra in ("retry", "pleaseretry", "tryagain"):
            return True
    compact = _later_nosep(inner)
    if any(run in compact for run in _JINGLE_RUNS):
        return True
    if "未知错误" in compact and compact != "未知错误":
        rest = compact.replace("未知错误", "", 1)
        if _error_rest_is_pad(rest):
            return True
    return False
def _cjk_rest_is_whole_pad(rest):
    """抽出英文后剩下的中文：整段是垫字才空，不在句子里搜「请刷新」。"""
    if not rest:
        return True
    if all(ch in _ERROR_PAD for ch in rest):
        return True
    if rest in _ERROR_PAD_HEAD or rest in _ERROR_PAD_TAIL:
        return True
    for tail in _ERROR_PAD_TAIL:
        after = rest[len(tail):]
        before = rest[:-len(tail)] if len(rest) >= len(tail) else rest
        if rest.startswith(tail) and all(ch in _ERROR_PAD for ch in after):
            return True
        if rest.endswith(tail) and all(ch in _ERROR_PAD for ch in before):
            return True
    for head in _ERROR_PAD_HEAD:
        if not rest.startswith(head):
            continue
        after = rest[len(head):]
        if not after or all(ch in _ERROR_PAD for ch in after) or after in _ERROR_PAD_TAIL:
            return True
    return False
def _pad_after_is_real_window(after):
    """请重试后面必须先接「后/然后」再接完整动作，剩余只能是垫字或句尾请刷新/请稍候。"""
    if not after:
        return False
    s = after
    saw_conn = False
    saw_follow = False
    follows = tuple(sorted(_PAD_TAIL_REAL_FOLLOW, key=len, reverse=True))
    while s:
        step = False
        for c in _PAD_TAIL_CONNECTOR:
            if s.startswith(c):
                s = s[len(c):]
                saw_conn = True
                step = True
                break
        if step:
            continue
        if saw_conn:
            for h in _ERROR_PAD_HEAD:
                if s.startswith(h):
                    s = s[len(h):]
                    step = True
                    break
            if step:
                continue
            for m in follows:
                if s.startswith(m):
                    s = s[len(m):]
                    saw_follow = True
                    step = True
                    break
            if step:
                continue
        break
    if not (saw_conn and saw_follow):
        return False
    if not s or all(ch in _ERROR_PAD for ch in s):
        return True
    for tail in _PAD_TAIL_END_OK:
        if s == tail:
            return True
        if s.endswith(tail) and all(ch in _ERROR_PAD for ch in s[:-len(tail)]):
            return True
        if s.startswith(tail) and all(ch in _ERROR_PAD for ch in s[len(tail):]):
            return True
    return False
def _error_rest_is_pad(rest):
    if rest in _ERROR_PAD_HEAD or rest in _ERROR_PAD_TAIL:
        return True
    if rest and all(ch in _ERROR_PAD for ch in rest):
        return True
    for head in _ERROR_PAD_HEAD:
        if rest.startswith(head) and rest != head and _error_rest_is_pad(rest[len(head):]):
            return True
    lead_real = False
    for t in _ERROR_PAD_TAIL:
        after = rest[len(t):]
        if rest.startswith(t) and _pad_after_is_real_window(after):
            lead_real = True
            break
    for tail in _ERROR_PAD_TAIL:
        if tail not in rest:
            continue
        # 请重试后点击确定/保存到云端：真窗口。夹日记或中间再塞请重试仍空。
        # 句首已放行时，只豁免贴在句尾的请刷新/请稍候，不豁免请重试。
        if rest.startswith(tail):
            after = rest[len(tail):]
            if _pad_after_is_real_window(after):
                if tail in after:
                    return True
                continue
        if lead_real and any(rest.endswith(end) for end in _PAD_TAIL_END_OK):
            continue
        return True
    for head in _ERROR_PAD_HEAD:
        if rest.endswith(head) and rest != head:
            prefix = rest[:-len(head)]
            if prefix in _GATE_LABEL:
                continue
            return True
        for g in _GATE_LABEL:
            core = g + head
            if rest.startswith(core) and rest != core:
                return True
    return False
def _fake_text(value):
    if not isinstance(value, str):
        return True
    s = unicodedata.normalize("NFKC", value).strip()
    if not s:
        return True
    low = s.lower()
    compact = "".join(low.split())
    nosep = _nosep(low)
    if (compact in _FAKE_EXACT or nosep in _FAKE_EXACT
            or compact.startswith("todo") or compact.startswith("tbd")
            or nosep.startswith("todo") or nosep.startswith("tbd")):
        return True
    if any(m in low for m in _FAKE_SUB):
        return True
    return any(t in _FAKE_EXACT or t.startswith("todo") or t.startswith("tbd") for t in _tokens(low))
def _later_placeholder(value):
    """later-use 专用：整句占位才空。引号里的 done 不把整句作废。"""
    if not isinstance(value, str) or not str(value).strip():
        return True
    s = value.strip()
    low = s.lower()
    compact = "".join(low.split())
    nosep = _nosep(low)
    if (compact in _FAKE_EXACT or nosep in _FAKE_EXACT
            or compact.startswith("todo") or compact.startswith("tbd")
            or nosep.startswith("todo") or nosep.startswith("tbd")):
        return True
    if any(m in low for m in _FAKE_SUB):
        return True
    # unknown / 未知 整格仍由 compact∈_FAKE_EXACT 拦；句子里交给 _later_unobserved。
    skip = {"done", "ok", "pass", "unknown", "未知"}
    return any((t in _FAKE_EXACT or t.startswith("todo") or t.startswith("tbd"))
               and t not in skip for t in _tokens(low))
def _later_unobserved(value):
    s = str(value or "").strip()
    if not s:
        return True
    inner = _unwrap_later(s)
    compact = _later_nosep(inner)
    compact_low = compact.lower()
    if compact_low in ("未知", "unknown"):
        return True
    gate = r"(当前)?(入口门|动作门|第二道门)"
    if re.search(gate + r"未知(?!错误)", compact):
        return True
    if re.search(gate + r".{0,8}未知(?!错误)", compact):
        return True
    if re.search(gate + r"(未知错误|不明|不清楚|没抄到)", compact):
        return True
    claim_unseen = (
        r"(没有看见|没有看到|没看见|没看到|"
        r"未看见|未看到|未观察(到)?|观察不到|"
        r"没能抄到|未能抄到|没抄到|抄不到|"
        r"瞧不见|瞅不见|没瞧见|没瞅见|未瞧见|"
        r"瞧不到|瞅不到|看不清|看不着)"
    )
    # 窄认「看不见」自称，不要裸搜三个字（按钮看不见请点确定是窗口原文）。
    # 不要用电脑/屏幕/这边当说话人：电脑看不见网络 是窗口说明。
    see_fail = r"(看不见|看不到|看不着)"
    on_chars = r"(窗口|界面)(上面|上|里面|里边|里)的(文字|字)"
    cantsee_claim = (
        see_fail + r".{0,6}" + on_chars
        + r"|" + on_chars + r".{0,6}" + see_fail
        + r"|(我|我们|其实|肉眼|什么都|压根|完全|用户).{0,8}" + see_fail
    )
    # 「如果没看见请刷新」才是窗口条件句。同一句里再出现「我没看见」
    # 或「看不见窗口上的字」，不要整句洗白。
    if re.search(claim_unseen, compact) or re.search(cantsee_claim, compact):
        if re.search(r"(我|我们|其实)", compact):
            return True
        if re.search(see_fail + r".{0,6}" + on_chars
                     + r"|" + on_chars + r".{0,6}" + see_fail, compact):
            return True
        if re.search(r"(如果|若是|要是|万一)" + claim_unseen, compact):
            return False
        return True
    return False
def _glued_fake(value):
    nosep = _nosep(str(value or "").lower())
    for w in ("pass", "done", "todo", "tbd"):
        if not nosep.endswith(w) or len(nosep) <= len(w):
            continue
        prefix = nosep[:-len(w)]
        if not prefix.isascii() or (len(prefix) == 1 and prefix.isalpha()):
            return True
    return False
# 「以后还能用」格子专用：说明书套话。不要写进上面的全局空话名单。
# 不要用过短的「重定位」「见脚本」当子串，以免「资源重定位」「看见脚本」误伤。
_LATER_USE_NEEDLE = (
    "拦截进入核心", "拦住进核心", "拦住进入核心", "拦截进核心",
    "拦下进核心", "拦下进入核心", "拦着进核心", "拦着进入核心",
    "挡住进入核心", "挡住进核心", "不让进核心", "不让进入核心",
    "触发写动作", "触发一次写动作", "触发了写动作",
    "自己点了 Apply", "自己点了Apply", "自己动手点了 Apply", "自己动手点了Apply",
    "自己触发", "两层都有自己触发",
    "触发了写操作", "触发写操作",
    "与入口门分开", "分开取证",
    "特征重找", "特征重定位",
    "入口门说明", "动作门说明",
    "入口授权页", "写动作第二道门",
    "启动后授权页",
    "随便写几", "另外记几", "一二三四", "五六七八", "甲乙丙丁",
    "call characteristic", "relocate by", "relocated by", "relocate using", "relocate via",
)
_CN_JINGLE = frozenset("一二三四五六七八九十零〇两")
_STEM_JINGLE = frozenset("甲乙丙丁戊己庚辛壬癸")
_BRANCH_JINGLE = frozenset("子丑寅卯辰巳午未申酉戌亥")
_CYCLE_JINGLE = frozenset("春夏秋冬乾坤坎离震巽艮兑东南西北上下左右")
_JINGLE_CHARS = _CN_JINGLE | _STEM_JINGLE | _BRANCH_JINGLE | _CYCLE_JINGLE
_OPENING_STOPS = frozenset({
    "目标与访问路线确认", "需求合同确认", "现状盘点确认",
})
def _unwrap_later(value):
    s = unicodedata.normalize("NFKC", str(value or "")).strip()
    wraps = (("「", "」"), ("『", "』"), ("“", "”"), ("《", "》"), ("〈", "〉"),
             ("【", "】"), ("（", "）"), ("(", ")"), ('"', '"'), ("'", "'"))
    prefixes = (
        "下次凭", "入口门：", "动作门：", "入口门:", "动作门:",
        "例如：", "例如:", "例如", "窗口上写着", "窗口写着",
        "界面上写着", "界面写着",
    )
    lead = set("：:。；;,.，、！!")
    for _ in range(8):
        changed = False
        for a, b in wraps:
            if len(s) >= 2 and s[0] == a and s[-1] == b:
                s = s[1:-1].strip()
                changed = True
        for p in prefixes:
            if s.startswith(p):
                s = s[len(p):].strip()
                changed = True
        if s.endswith("认出"):
            s = s[:-2].strip()
            changed = True
        while s and s[0] in lead:
            s = s[1:].strip()
            changed = True
        while s and s[-1] in lead:
            s = s[:-1].strip()
            changed = True
        if not changed:
            break
    return s
def _later_use_empty(value):
    if not isinstance(value, str) or _later_placeholder(value):
        return True
    inner = _unwrap_later(value)
    if _later_placeholder(inner) or _later_unobserved(inner) or _later_filler_core(inner):
        return True
    compact = _later_nosep(inner)
    low = inner.lower()
    if compact in ("窗口上的字", "窗口原文", "窗口上的字样"):
        return True
    letters = set(compact)
    if len(compact) >= 4 and letters and letters <= _JINGLE_CHARS:
        return True
    cjk = "".join(ch for ch in compact if "\u4e00" <= ch <= "\u9fff")
    if len(cjk) >= 4 and set(cjk) <= _JINGLE_CHARS:
        return True
    if re.search(r"按(调用特征|导出名).{0,24}重(新)?定位", compact):
        return True
    if re.search(r"按.{0,24}调用特征", compact):
        return True
    if re.search(r"[拦挡截阻].{0,6}进(入)?核心", compact):
        return True
    if re.search(r"无法进(入)?核心", compact) or "进不了核心" in compact:
        return True
    if re.search(r"不让.{0,4}进(入)?核心", compact):
        return True
    if re.search(r"(?<![看详参请可])见脚本", compact):
        return True
    if re.search(r"\brelocated?\b", low) or re.search(r"\brelocation\s+(using|by|via)\b", low):
        return True
    return any(n in compact or n in low for n in _LATER_USE_NEEDLE)
def _later_use_ok(value, min_len=8):
    if not isinstance(value, str):
        return False
    inner = _unwrap_later(value)
    if (len(inner) < min_len or _later_placeholder(inner) or _glued_fake(inner)
            or len(set(inner.replace(" ", ""))) < 4):
        return False
    spaced = "".join(" " if _later_as_space(ch) else ch for ch in inner)
    body = "".join(spaced.split())
    copied_error = _copied_window_error(inner)
    # 纯字母数字：双门一律不算。锚点只放过像 CreateFileW 这种驼峰接口名。
    if not copied_error and body.isascii() and body.isalnum():
        if min_len <= 4 or not _CAMEL_API.search(inner):
            return False
    if _has_empty_talk(inner):
        return False
    return not _later_use_empty(value)
def _phase_needs_later_use(phase):
    sp = (phase or {}).get("stop_point") or ""
    return bool(sp) and sp not in _OPENING_STOPS
def _usable_claim(value, min_len=8):
    s = str(value or "").strip()
    if len(s) < min_len or _fake_text(s) or _glued_fake(s):
        return False
    if len(set(s.replace(" ", ""))) < 4:
        return False
    # 无空格的纯字母数字不算一句话；有空格的英文句子可以过。
    if " " not in s and "\t" not in s:
        body = "".join(s.split())
        if body.isascii() and body.isalnum() and not _CAMEL_API.search(s):
            return False
    if _has_empty_talk(s):
        return False
    return True
def _require_claim(value, min_len=8):
    s = str(value or "").strip()
    if len(s) < min_len:
        return False
    if len(set(s.replace(" ", ""))) < 4:
        return False
    low = unicodedata.normalize("NFKC", s).strip().lower()
    compact = "".join(low.split())
    if (compact in _FAKE_EXACT or compact.startswith("todo") or compact.startswith("tbd")):
        return False
    if " " not in s and "\t" not in s:
        body = "".join(s.split())
        if body.isascii() and body.isalnum() and not _CAMEL_API.search(s):
            return False
    return True
def _strip_independent_skip(text):
    s = str(text or "")
    up = s.upper()
    out, i, n = [], 0, len(s)
    while i < n:
        if (up.startswith("SKIP", i)
                and not (up[i - 1] if i else " ").isalpha()
                and not (up[i + 4] if i + 4 < n else " ").isalpha()):
            out.append(" ")
            i += 4
            continue
        out.append(s[i])
        i += 1
    return "".join(out)
def _explicit_skip(text):
    s = str(text or "")
    return _strip_independent_skip(s) != s
_ARCH_STOPS = frozenset({"架构确认", "架构与风险测绘确认"})
_WRITE_STOPS = frozenset({
    "核心功能实现确认", "核心接口与页面实现确认",
    "核心命令实现确认", "改造实现确认",
})
_ARCH_WRITE = ("写动作", "写库")
_ARCH_SHIP = ("分发", "安装包", "怎么交", "交给别人")
_ARCH_OPEN = ("还没定", "以后再说", "形态未决", "还拒", "未决", "未证", "没证")
_WRITE_HARD = ("还拒", "还没测", "没测", "以后再说", "写动作未测", "写动作没测", "写库还没", "未决", "未证", "没证", "仍需授权")
_WRITE_DONE = ("写动作", "写库", "落库", "下单", "主流程", "真实输入", "真实输出")
_PAGE_SOUND = ("进了主界面", "进入主界面", "进入了主界面", "进了页", "进页", "进的是主界面")
_GATE_CLAIM = ("已定位",)
_SIDECAR_MARK = ("--help", "sidecar", "wad-make")
_SIDECAR_NOT = (
    "卡住", "等回车", "没跑完", "未跑完", "还没跑完", "尚未跑完",
    "不能当跑完", "不算跑完", "不跑完", "未能跑完", "没能跑完",
    "跑完前", "还没等跑完",
)
def _skip_ok(phase):
    p = phase or {}
    return p.get("stop_point") in _SKIP_OK_STOPS
def _arch_thin(blob):
    if _phrase_hit(blob, _ARCH_OPEN):
        return True
    return not (_phrase_hit(blob, _ARCH_WRITE) and _phrase_hit(blob, _ARCH_SHIP))
_LICENSE_STOPS = frozenset({"授权页启动器确认", "自有授权闭环确认"})
_ORIG_PACK_LICENSE_STOPS = frozenset({
    "安装包确认", "分发包与跨平台确认", "预发环境冒烟确认",
    "发布候选确认",
    "首次启动验收确认", "干净环境首次运行确认",
    "数据迁移与备份确认",
    "更新回滚演练确认", "上线回滚演练确认", "发布回滚演练确认",
    "交付验收确认",
})
_LICENSE_THIN_MSG = (
    "拒绝：授权须走启动器三种基础加第四种：有效才开核心，无效不开，"
    "用到一半过期要关核心并关掉授权页；卡还没到期但这台被挤掉/"
    "DEVICE_NOT_BOUND/解绑后停也要停。只有一台时超过验证间隔主程序还在，"
    "没人挤不会自己关。两套钟不准改混：到期靠 expires_at 本地关；"
    "挤机必须再 verify，下一次验证内停。expiry 是卡还剩多久，禁止把验证间隔/"
    "cache_until/next_verify_at/20 秒/60 秒交给核心或标题栏。RATE_LIMITED 不是停机。"
    "开着还要周期性验证，只 activate 不算。"
    "作废/断网按这场合同，不是每场必测。检查授权不能当进入程序。"
)
_LICENSE_BASICS_SKIP = (
    "三种基础先不测", "三种基础不测", "三种基础没测", "三种基础未测",
    "三种基础先不做", "三种基础不做",
    "先不测三种基础", "不测三种基础", "没测三种基础", "未测三种基础",
    "基础三种先不测", "先不测基础三种",
    "先不测有效无效过期", "不测有效无效过期", "有效无效过期先不测",
)
_LICENSE_MID = ("用到一半", "用着用着", "中途过期", "运行中过期")
_LICENSE_KICK = (
    "被挤掉", "挤掉第一台", "第二台挤掉", "DEVICE_NOT_BOUND",
    "设备未绑定", "这台被解绑", "解绑后停", "被挤掉会停",
)
_LICENSE_KICK_WINDOW = (
    "下一次验证内停", "下次验证内停", "下一次验证内关", "下次验证内关",
    "下一次verify内", "下次verify内",
    "下次再问之内", "下一次再问之内",
)
_LICENSE_VERIFY_LIVE = (
    "周期性验证", "周期验证", "开着还要问", "开着仍验证",
    "不只 activate", "不只activate", "激活后还要验证",
)
_LICENSE_SOLO = (
    "没人挤不会自己关",
)
_LICENSE_CLOSE_CORE = ("关核心", "关掉核心", "关闭核心")
_LICENSE_STOP_CORE = _LICENSE_CLOSE_CORE + ("关掉授权页", "授权页一起退")
_LICENSE_STOP_DESK = _LICENSE_STOP_CORE + ("停掉程序", "到期停程序", "关掉程序", "关闭程序")
_LICENSE_STOP_CLI = ("停主命令", "停掉主命令", "到期停主命令", "关掉主命令", "关闭主命令")
_LICENSE_STOP_WEB = ("停服务", "停掉服务", "到期停服务", "关掉服务", "关闭服务", "停止服务")
_LICENSE_STOP_ANY = _LICENSE_STOP_DESK + _LICENSE_STOP_CLI + _LICENSE_STOP_WEB
_WEB_KILL_APP = ("关软件", "关掉软件", "关闭软件")
def _license_gate(phase):
    p = phase or {}
    return p.get("id") in ("4-license", "2-license") or p.get("stop_point") in _LICENSE_STOPS
def _license_kick_ok(blob):
    """第四种：卡仍有效，但这台被挤掉/解绑，且须看见下一次验证内停。"""
    return (
        _phrase_hit(blob, _LICENSE_KICK)
        and _phrase_hit(blob, _LICENSE_KICK_WINDOW)
    )


def _license_verify_live_ok(blob):
    """开着还要周期性 verify。一句激活/验证/解绑都要不算。"""
    return _phrase_hit(blob, _LICENSE_VERIFY_LIVE)


def _license_solo_ok(blob):
    """只有一台时超过验证间隔还在。少了会把自己关当成挤机。"""
    return _phrase_hit(blob, _LICENSE_SOLO)


def _license_basics_ok(blob):
    """有效/无效/过期/用到一半，加上被挤掉停、单机还在、周期性验证。"""
    if _license_hard_hit(blob):
        return False
    if _phrase_hit(blob, _LICENSE_BASICS_SKIP):
        return False
    # 「有效」不认有效性/有效期/看起来有效。只写「过期」不算第三种。
    return (
        _license_valid_hit(blob)
        and _unnegated_hit(blob, "无效", True)
        and _phrase_hit(blob, ("过期", "到期"), True)
        and _phrase_hit(blob, _LICENSE_MID)
        and _license_kick_ok(blob)
        and _license_solo_ok(blob)
        and _license_verify_live_ok(blob)
    )
def _license_thin(blob):
    # 二开授权格：必须走启动器，用到一半过期要关核心。
    if not _license_basics_ok(blob):
        return True
    if not _unnegated_hit(blob, "启动器"):
        return True
    return not _phrase_hit(blob, _LICENSE_CLOSE_CORE, True)
def _orig_pack_license_thin(blob, product_type=None):
    """接了自己的授权后，原创打包/预发按形态写三种基础加第四种，并写购买/更新。"""
    if product_type == "exe-rebuild":
        return False
    if not _license_basics_ok(blob):
        return True
    kind = product_type or ""
    license_a = (
        _phrase_hit(blob, ("购买",))
        and _phrase_hit(blob, ("网盘", "更新"))
    )
    if kind == "cli-tool":
        if _forged_launcher(blob):
            return True
        if not _unnegated_hit(blob, "主命令"):
            return True
        if not license_a:
            return True
        return not _phrase_hit(blob, _LICENSE_STOP_CLI)
    if kind == "web-service":
        if _forged_launcher(blob):
            return True
        if _phrase_hit(blob, _WEB_KILL_APP):
            return True
        if not _phrase_hit(blob, ("提供服务",) + _LICENSE_STOP_WEB + ("收费门",)):
            return True
        if not license_a:
            return True
        return not _phrase_hit(blob, _LICENSE_STOP_WEB)
    if kind == "desktop-product":
        if _unnegated_hit(blob, "启动器"):
            return True
        if _phrase_hit(blob, ("关核心", "关掉核心", "关闭核心"), True):
            return True
        if not _unnegated_hit(blob, "授权页"):
            return True
        if not license_a:
            return True
        return not _phrase_hit(blob, (
            "关掉程序", "关闭程序", "停掉程序", "到期停程序",
            "关掉后面的程序",
        ))
    if _forged_launcher(blob):
        return True
    desk_like = _phrase_hit(blob, ("放行程序", "关掉程序", "关闭程序"))
    if desk_like and not _unnegated_hit(blob, "授权页"):
        return True
    if not license_a:
        return True
    return not _phrase_hit(blob, _LICENSE_STOP_ANY)
def _orig_pack_license_msg(product_type=None):
    kind = product_type or ""
    if kind == "cli-tool":
        return (
            "拒绝：接了自己的授权后，须按命令行形态写三种基础加第四种："
            "有效才放行主命令，无效不放行，用到一半过期要停主命令；"
            "卡还没到期但这台被挤掉/DEVICE_NOT_BOUND 也要停主命令。"
            "开着还要周期性验证，只 activate 不算。只有一台时超过验证间隔还在，"
            "没人挤不会自己关。两套钟不准改混。expiry 是卡还剩多久，禁止验证间隔/20 秒/60 秒过门。下一次验证内停。"
            "RATE_LIMITED 不是停机。"
            "还要写购买/联系跟下游、更新带版本号问平台有新版才打开网盘。"
            "不要为过关造启动器。检查授权不能当进入程序。"
        )
    if kind == "web-service":
        return (
            "拒绝：接了自己的授权后，须按网站形态写三种基础加第四种："
            "有效才提供服务，无效不提供，用到一半过期要停服务；"
            "卡还没到期但这台被挤掉/DEVICE_NOT_BOUND 也要停服务，不要关软件。"
            "开着还要周期性验证，只 activate 不算。只有一台时超过验证间隔还在，"
            "没人挤不会自己关。两套钟不准改混。expiry 是卡还剩多久，禁止验证间隔/20 秒/60 秒过门。下一次验证内停。"
            "RATE_LIMITED 不是停机。"
            "还要写购买/联系跟下游、更新带版本号问平台有新版才打开网盘。"
            "不要造启动器。检查授权不能当进入程序。"
        )
    if kind == "desktop-product":
        return (
            "拒绝：接了自己的授权后，须按桌面形态写三种基础加第四种："
            "有效才放行程序，无效不放行，用到一半过期要关掉程序和授权页；"
            "卡还没到期但这台被挤掉/DEVICE_NOT_BOUND 也要停。"
            "开着还要周期性验证，只 activate 不算。只有一台时超过验证间隔还在，"
            "没人挤不会自己关。两套钟不准改混。expiry 是卡还剩多久，禁止验证间隔/20 秒/60 秒过门。下一次验证内停。"
            "RATE_LIMITED 不是停机。"
            "还要写购买/联系跟下游、更新带版本号问平台有新版才打开网盘。"
            "不要把没源码的核心当载荷再套一层。桌面要授权页验卡密，不要用二开那句走启动器关核心交差。"
        )
    return (
        "拒绝：接了自己的授权后，须按产品形态写三种基础加第四种："
            "有效才放行后面的程序/服务，无效不放行，用到一半过期则停掉；"
            "卡还没到期但这台被挤掉/DEVICE_NOT_BOUND 也要停。"
            "开着还要周期性验证，只 activate 不算。只有一台时超过验证间隔还在，"
            "没人挤不会自己关。两套钟不准改混。expiry 是卡还剩多久，禁止验证间隔/20 秒/60 秒过门。下一次验证内停。"
            "RATE_LIMITED 不是停机。"
            "还要写购买/联系跟下游、更新带版本号问平台有新版才打开网盘。"
            "不要把没源码的核心当载荷再套一层。有窗要授权页验卡密，不要用二开那句走启动器关核心交差。"
    )
def _plat_zip_hit(blob):
    return bool(re.search(
        r"平台[上到先都里已经刚面]*?(?:可以|能够|都能|已能|能|可)?[上到先都里已经刚面]*下[载到先的上都了完着过个份毕（）()【】]*\.?zip",
        _compact_ws(blob)))
def _update_thin(blob):
    if (_hard_hit(blob, _UPDATE_HARD) or _taint_hit(blob, _UPDATE_HARD)
            or _plat_zip_hit(blob)):
        return True
    return not (_phrase_hit(blob, _UPDATE_COVER_OK)
                and _phrase_hit(blob, _UPDATE_OFFICIAL_OK))
_EAT_UP_MARK = ("吃新上游", "跟上新上游", "跟上新版", "按改动图")
_CUSTOMER_UPD = _UPDATE_COVER_OK + _UPDATE_OFFICIAL_OK + (
    "软件里点更新", "本项 SKIP", "本项SKIP",
)


def _eat_as_customer_update(blob):
    """把跟上新版本说成客户已经点了更新。"""
    if not _phrase_hit(blob, _EAT_UP_MARK):
        return False
    if _explicit_skip(blob) or _phrase_hit(blob, _CUSTOMER_UPD):
        return False
    return True
_ROLLBACK_STOPS = frozenset({
    "更新回滚演练确认", "上线回滚演练确认", "发布回滚演练确认",
})
def _rollback_thin(blob):
    return not _unnegated_hit(blob, "回滚")
def _data_mig_thin(blob):
    return not (_unnegated_hit(blob, "迁移") and _unnegated_hit(blob, "备份")
                and _unnegated_hit(blob, "回滚"))
def _write_done(blob):
    s = str(blob or "")
    if _phrase_hit(blob, tuple(p for p in _WRITE_DONE if p != "写动作")):
        return True
    start = 0
    while True:
        i = s.find("写动作", start)
        if i < 0:
            return False
        if s[i:i + 4] != "写动作门" and not _immediate_neg(s, i):
            return True
        start = i + 3
def _write_unsettled(blob):
    if _phrase_hit(blob, _WRITE_HARD):
        return True
    return not _write_done(blob)
def _sidecar_done(blob):
    s = str(blob or "").replace(" ", "")
    if any(p in s for p in _SIDECAR_NOT):
        return False
    return _unnegated_hit(blob, "跑完")
def _immediate_neg(s, i, cjk_one=False):
    while i > 0 and s[i - 1] in _WRAP:
        i -= 1
    for p in _NEG_IMMEDIATE:
        b = i - len(p)
        if b < 0 or s[b:i] != p:
            continue
        if len(p) == 1 and not (cjk_one and p in "未不没") and b > 0 and s[b - 1] not in _SEP and s[b - 1] not in _WRAP:
            continue
        return True
    if i >= 1 and s[i - 1] in "不未" and s[i:i + 3] == "能编译":
        return True
    return False
def _clause_at(s, i):
    seps = "。！？；;\n，"
    start = 0
    for j in range(i - 1, -1, -1):
        if s[j] in seps:
            start = j + 1
            break
    end = len(s)
    for j in range(i, len(s)):
        if s[j] in seps:
            end = j
            break
    return s[start:end]
def _quoted_ban(s, i):
    left = s.rfind("「", 0, i + 1)
    if left < 0:
        return False
    right = s.find("」", i)
    if right < 0:
        return False
    return _immediate_neg(s, left)
def _obeyed_ban(s, i, n):
    tail = s[i + n:i + n + 28].replace(" ", "")
    return any(t in tail for t in _OBEY_TAIL)
def _ban_lookback(s, i):
    head = s[max(0, i - 8):i]
    return any(k in head for k in (
        "不要改成", "不要写成", "不要再用", "作废", "禁止", "不准",
    ))
def _license_hard_hit(blob):
    s = str(blob or "")
    for p in _LICENSE_HARD:
        start = 0
        while True:
            i = s.find(p, start)
            if i < 0:
                break
            if (not _immediate_neg(s, i) and not _quoted_ban(s, i)
                    and not _obeyed_ban(s, i, len(p)) and not _ban_lookback(s, i)):
                return True
            start = i + len(p)
    compact = _compact_ws(s)
    for p in (
        "核心租约=验证窗口", "核心租约等于验证窗口",
        "给核心的可用时长跟验证租约走",
        "到期也必须再问才关", "到期也必须再问平台才关",
        "到期后等下一次验证才关", "到期后再问才关",
        "20秒硬刷", "客户端20秒硬刷",
    ):
        needle = _compact_ws(p)
        if not needle:
            continue
        j = 0
        while True:
            j = compact.find(needle, j)
            if j < 0:
                break
            if not _ban_lookback(compact, j):
                return True
            j += len(needle)
    return False
def _span_py_neg(s, i):
    return any(p in _clause_at(s, i) for p in _PY_NEG)
_LOOKS_VALID = ("看起来", "看上去", "看似")
_LOOKS_FILL = frozenset("很是还挺")
_LOOKS_FILL_WORDS = ("非常", "貌似", "似乎")
_LOOKS_WS = " \t\r\n\u3000\xa0：:。，,、"
def _looks_valid_hedge(s, j, need_look=False):
    k = j
    peeled_any = False
    while True:
        for look in _LOOKS_VALID:
            n = len(look)
            if k >= n and s[k - n:k] == look:
                return True
        peeled = False
        for word in _LOOKS_FILL_WORDS:
            wn = len(word)
            if k >= wn and s[k - wn:k] == word:
                k -= wn
                peeled = True
                peeled_any = True
                break
        if not peeled and k >= 2 and s[k - 2:k] == "已经":
            k -= 2
            peeled = True
        if not peeled and k > 0 and s[k - 1] == "已":
            k -= 1
            peeled = True
        if not peeled and k > 0 and s[k - 1] in _LOOKS_FILL:
            k -= 1
            peeled = True
            peeled_any = True
        if not peeled:
            return False if need_look else peeled_any
        while k > 0 and s[k - 1] in _LOOKS_WS:
            k -= 1
def _license_valid_hit(blob):
    s = str(blob or "")
    start = 0
    while True:
        i = s.find("有效", start)
        if i < 0:
            return False
        if i + 2 < len(s) and s[i + 2] in "性期":
            start = i + 2
            continue
        if s[i + 2:i + 4] in ("未测", "没测", "不测"):
            start = i + 2
            continue
        j = i
        while j > 0 and s[j - 1] in _LOOKS_WS:
            j -= 1
        if _looks_valid_hedge(s, j):
            start = i + 2
            continue
        if not _immediate_neg(s, i, True):
            return True
        start = i + 2
def _unnegated_hit(blob, phrase, cjk_one=False):
    s = str(blob or "")
    if not phrase:
        return False
    hay, needle = (s.lower(), phrase.lower()) if phrase.isascii() else (s, phrase)
    start, step = 0, len(needle)
    while True:
        i = hay.find(needle, start)
        if i < 0:
            return False
        if not _immediate_neg(s, i, cjk_one):
            return True
        start = i + step
def _forged_launcher(blob):
    """真写了启动器才算抄壳。说明书里「不要为过关造启动器」不算。"""
    s = str(blob or "")
    start = 0
    while True:
        i = s.find("启动器", start)
        if i < 0:
            return False
        if not _immediate_neg(s, i, True):
            cl = _clause_at(s, i)
            if not any(b in cl for b in ("不要", "禁止", "不准", "不为", "别造")):
                return True
        start = i + 3
def _python_exe_taint(blob):
    s = str(blob or "")
    low = s.lower()
    start = 0
    while True:
        i = low.find("python.exe", start)
        if i < 0:
            return False
        if not _span_py_neg(s, i):
            return True
        start = i + 10
def _py_neg_at(s, i, skip_ascii_ws=False):
    while i > 0 and s[i - 1] in _WRAP:
        i -= 1
    if skip_ascii_ws:
        while i > 0 and s[i - 1] in " \t":
            i -= 1
        while i > 0 and s[i - 1] in _WRAP:
            i -= 1
    return any(i >= len(p) and s[i - len(p):i] == p for p in _PY_NEG)
def _pack_py_taint(blob):
    s = str(blob or "")
    for p in _PACK_PY:
        start, step = 0, len(p)
        while True:
            i = s.find(p, start)
            if i < 0:
                break
            # PATH 行才让路：依赖本机 不能被「不调用」否定后把 .exe 交给整句洗白。
            if ("PATH" in p and s[i + step:i + step + 4].lower() == ".exe"
                    and _py_neg_at(s, i, True)):
                start = i + step
                continue
            if not _immediate_neg(s, i, True):
                return True
            start = i + step
    return False
def _sys_py_taint(blob):
    s = str(blob or "")
    for p in _PACK_SYS:
        hay, needle = (s.lower(), p.lower())
        start = 0
        while True:
            i = hay.find(needle, start)
            if i < 0:
                break
            if not _immediate_neg(s, i, True) and not _py_neg_at(s, i):
                return True
            start = i + len(needle)
    return False
def _compact_ws(blob):
    s = unicodedata.normalize("NFKC", str(blob or "")).replace("\u200b", "")
    return re.sub(r"\s+", "", s).lower()
def _hard_hit(blob, phrases):
    raw = str(blob or "")
    compact = _compact_ws(raw)
    return any(p and (p in raw or _compact_ws(p) in compact) for p in phrases)
def _taint_hit(blob, phrases, cjk_one=False):
    return _phrase_hit(blob, phrases, cjk_one) or _phrase_hit(_compact_ws(blob), phrases, cjk_one)
def _norm_empty(blob):
    s = unicodedata.normalize("NFKC", str(blob or ""))
    for ch in "\u3000\xa0，,、":
        s = s.replace(ch, " ")
    s = s.lower()
    return re.sub(r"[ \t\r\n]+", " ", s)
def _has_empty_talk(value):
    compact = re.sub(r"\s+", "", _norm_empty(value))
    return any(re.sub(r"\s+", "", _norm_empty(p)) in compact for p in _EMPTY_TALK)
def _open_page_empty(blob, needle="打开页"):
    s = str(blob or "")
    start = 0
    n = len(needle)
    while True:
        i = s.find(needle, start)
        if i < 0:
            return False
        if s[i + n:].startswith("面"):
            start = i + 1
            continue
        if not _immediate_neg(s, i, True):
            return True
        start = i + 1
def _stop_empty_hit(blob, phrases):
    raw = str(blob or "")
    norm = _norm_empty(raw)
    compact = re.sub(r"\s+", "", norm)
    for p in phrases:
        pn = _norm_empty(p)
        pc = re.sub(r"\s+", "", pn)
        if pn in ("打开页", "打开了页"):
            if _open_page_empty(raw, "打开了页" if pn == "打开了页" else "打开页"):
                return True
            continue
        if pn == "--help":
            helped = "--help" in norm
            real = (_unnegated_hit(raw, "真实输入") or _unnegated_hit(raw, "落盘")
                    or _unnegated_hit(raw, "落库"))
            if helped and not real:
                return True
            continue
        if _unnegated_hit(norm, pn) or (pc and _unnegated_hit(compact, pc)):
            return True
    return False
def _phrase_hit(blob, phrases, cjk_one=False):
    return any(_unnegated_hit(blob, p, cjk_one) for p in phrases)
def _has_mark(blob, marks):
    s = str(blob or "")
    low = s.lower()
    return any((m.lower() in low) if m.isascii() else (m in s) for m in marks)
def _scope_cut(text):
    return _phrase_hit(text, _SCOPE_CUT, True)
def _download_hang_as_ok(text):
    s = str(text or "").replace(" ", "")
    return any(h in s for h in _HANG) and any(o in s for o in _HANG_OK)
def _confirm_usable(text, phase):
    if _usable_claim(text):
        return True
    if not _explicit_skip(text):
        return False
    if not _skip_ok(phase):
        return False
    # 只把独立词 SKIP 换成够长的句子；未验证/UNVERIFIED 继续当占位符拒。
    masked = str(text or "").replace("SKIP", "已标明范围").replace("skip", "已标明范围")
    return _usable_claim(masked)
def _walk_strings(obj, out):
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k not in _SKELETON_FIELDS:
                _walk_strings(v, out)
    elif isinstance(obj, (list, tuple)):
        for x in obj:
            _walk_strings(x, out)
def _phase_receipt_text(phase, evidence, note, manifest, fp, cand_sha, epoch):
    parts = [str(evidence or ""), str(note or "")]
    pid = (phase or {}).get("id") or ""
    for r in (phase or {}).get("requires") or []:
        key = KIND_TO_KEY.get(r, r)
        if key not in (manifest or {}):
            continue
        for entry in reversed(manifest.get(key, []) or []):
            if not isinstance(entry, dict) or entry.get("fp") != fp:
                continue
            if cand_sha and key in CANDIDATE_BOUND_ARTIFACTS and entry.get("cand_sha") != cand_sha:
                continue
            if phase.get("artifact_phase") and entry.get("phase_id") not in (None, pid):
                continue
            if entry.get("epoch", 0) != epoch:
                continue
            _walk_strings(entry, parts)
            break
    # 换行已是分句符：evidence / note / 制品不能空格拼成一句，让前头「不调用」洗白后头的 python.exe。
    return "\n".join(parts)
def confirm_multi_stop(requested, phases):
    names = [p.get("stop_point") for p in phases if p.get("stop_point")]
    hits = [n for n in names if n and n in (requested or "")]
    return len(hits) > 1
def _opened_skill_empty(blob):
    s = str(blob or "")
    if "技能" not in s:
        return False
    return ("已打开" in s) or ("打开了" in s)
def _ledger_green_empty(blob):
    compact = re.sub(r"\s+", "", str(blob or ""))
    return ("status全绿" in compact) or ("账本点齐" in str(blob or ""))
def _pack_license_check_blob(text, evidence, note):
    # 只核 --evidence 和 note；未传 evidence 时（措辞单测）退回 text。
    # 不要把 _phase_receipt_text 拼进的孪生/制品字段拿来判瘦。
    ev = str(evidence if evidence is not None else text or "")
    note_s = str(note or "")
    return "\n".join(x for x in (ev, note_s) if x.strip())
def confirm_wording_error(phase, text, evidence=None, asked_own_license=False,
                          note=None, product_type=None):
    pid = (phase or {}).get("id") or ""
    sp = (phase or {}).get("stop_point") or ""
    blob = str(text or "")
    ev = str(evidence if evidence is not None else text or "")
    if _scope_cut(blob) and not (_explicit_skip(blob) and _skip_ok(phase)):
        return ("拒绝：测中枢/测试中枢/不深入/跳过/先这样/不挡这次/接着往下做/合格就记下"
                "不能把停点点绿（除非同条写明 SKIP 且该格允许）。")
    if _explicit_skip(blob) and not _skip_ok(phase):
        return "拒绝：SKIP 只记账，不能把该停点点绿。"
    if _opened_skill_empty(blob) or _opened_skill_empty(ev):
        return "拒绝：打开技能名不能把停点点绿。"
    if _ledger_green_empty(blob) or _ledger_green_empty(ev):
        return "拒绝：status 全绿 / 账本点齐不能把停点点绿。"
    if pid == "1-access" or sp == "核心可用确认":
        if _download_hang_as_ok(blob):
            return "拒绝：核心可用不能把下载卡住写成不挡。"
        if _has_mark(blob, _SIDECAR_MARK) and not _sidecar_done(blob):
            return "拒绝：sidecar/--help 不能当核心可用齐了；卡住或没跑完不能点绿（SKIP 只记账）。"
        if _phrase_hit(blob, _WRITE_HARD) or _phrase_hit(ev, _WRITE_HARD):
            return "拒绝：进页之后写动作未证不能把核心可用点绿（SKIP/未决只记账）。"
        if _has_mark(blob, _PAGE_SOUND) or _has_mark(ev, _PAGE_SOUND):
            return "拒绝：进页不能当写动作已证，不能把核心可用点绿。"
        if _has_mark(blob, _GATE_CLAIM) or _has_mark(ev, _GATE_CLAIM):
            return "拒绝：门已定位不能当写动作已证，不能把核心可用点绿。"
        if _phrase_hit(blob, _CUT_ALL) or _phrase_hit(ev, _CUT_ALL):
            return "拒绝：核心可用不能把公共序列化/全部开关一刀切当许可判定。"
        if _phrase_hit(blob, _MUTUAL_VOTE) or _phrase_hit(ev, _MUTUAL_VOTE):
            return "拒绝：互攻评比不能当核心可用授权，也不能推翻只改许可判定。"
        if _taint_hit(blob, _LAUNCHER_TAINT) or _taint_hit(ev, _LAUNCHER_TAINT):
            return "拒绝：窗口出来/启动器亮了不能当核心可用。"
    if _license_gate(phase):
        if _phrase_hit(blob, _SCRIPT_LAUNCH):
            return "拒绝：授权闭环不能用脚本直开核心当收据。"
        if _license_thin(blob) or _license_thin(ev):
            return _LICENSE_THIN_MSG
        if _phrase_hit(blob, _MUTUAL_VOTE) or _phrase_hit(ev, _MUTUAL_VOTE):
            return "拒绝：互攻评比不能当授权闭环。"
    if (asked_own_license and product_type != "exe-rebuild"
            and sp in _ORIG_PACK_LICENSE_STOPS):
        pack_blob = _pack_license_check_blob(text, evidence, note)
        if _orig_pack_license_thin(pack_blob, product_type):
            return _orig_pack_license_msg(product_type)
    if pid == "5-pack" or sp == "给别人的包确认":
        if (_pack_py_taint(blob) or _pack_py_taint(ev)
                or _python_exe_taint(blob) or _python_exe_taint(ev)
                or _sys_py_taint(blob) or _sys_py_taint(ev)):
            return "拒绝：客户包不能依赖本机 PATH 里的 Python。"
    empty = _EMPTY_BY_STOP.get(sp)
    if empty and _stop_empty_hit(blob, empty):
        return ("拒绝：空成功信号不能把该停点点绿"
                "（测试绿/健康检查/--help/能编译/开发机/另装文件夹/读说明书等）。")
    if sp in _ARCH_STOPS and _arch_thin(blob):
        return ("拒绝：架构停点不能只交一句决定把形态吞掉；"
                "须写清写动作在哪和怎么分发/交给别人。答不出不能点绿（SKIP/未决只记账）。")
    if sp == "覆盖更新与官方更新确认":
        if _eat_as_customer_update(blob) or _eat_as_customer_update(ev):
            return ("拒绝：吃新上游不是客户点更新。"
                    "客户路径要软件里覆盖或本项 SKIP；跟上新版本走档案和改动图，两句不能焊成一句做成。")
        if _update_thin(blob) or _update_thin(ev):
            return ("拒绝：覆盖更新和官方更新是两条通道，不能合成一次交差；"
                    "须对着刚验过的那份包，平台能下不算覆盖做成。")
    if sp in _ROLLBACK_STOPS:
        if _eat_as_customer_update(blob) or _eat_as_customer_update(ev):
            return ("拒绝：吃新上游不是客户点更新。"
                    "客户路径要软件里覆盖或本项 SKIP；跟上新版本走档案和改动图，两句不能焊成一句做成。")
        if _rollback_thin(ev):
            return "拒绝：回滚演练须写清失败回滚并复验，只写主流程真跑不能点绿。"
    if sp == "数据迁移与备份确认" and _data_mig_thin(ev):
        return "拒绝：数据迁移须写清迁移、备份和失败回滚，只写主流程真跑不能点绿。"
    if sp in _WRITE_STOPS:
        if _phrase_hit(blob, _WRITE_HARD) or _phrase_hit(ev, _WRITE_HARD):
            return ("拒绝：第一声成功之后须写清写动作还拒不拒；"
                    "未证不能点绿（SKIP/未决只记账）。")
        if _write_unsettled(ev):
            return ("拒绝：第一声成功之后须写清写动作还拒不拒；"
                    "未证不能点绿（SKIP/未决只记账）。")
    return None
def test_record_error(phase, data):
    if isinstance(data, dict):
        blob = " ".join(str(data.get(k, "")) for k in ("outcome", "evidence"))
    else:
        blob = str(data or "")
    if _stop_empty_hit(blob, _TEST_FAKE) or _phrase_hit(blob, _MIG_0):
        return "拒绝：HTTP 200 / 报缺 / 迁移脚本退出 0 不能当业务做成，不能记入 test。"
    return None


def road_stop_lines(product_type, phase_id, missing_items):
    """授权格还没证明核心打不开时，对人说停。不是工程师清单。"""
    blob = " ".join(str(x) for x in (missing_items or []))
    lines = []
    if phase_id in {"0-discover-plan", "0-spec", "0-intake"}:
        low = blob.lower()
        if ("mission" in low or "manifest.spec" in low or "record --kind spec" in low
                or "就改了程序" in blob):
            lines.extend([
                "停住：你没点头「方案可以」，不许改程序。",
                "先把方案讲清。没点头之前，不要改产品文件。",
            ])
        if "就改了程序" in blob:
            lines.append("程序文件已经被改过了。先停，不要继续改。")
    if product_type == "exe-rebuild" and phase_id == "4-license" and "core_closed" in blob:
        lines.extend([
            "停住：还没看见「单独点核心进不了主功能」。不许开始接授权。",
            "你现在只要看一件事：单独点核心，会不会出现主程序窗口。",
            "马上退出、没有主窗口 = 关上了，才可以测接卡密。",
            "出现主窗口 = 还没修好，不许往下接卡密。",
        ])
    if "发给用户的那一份" in blob:
        lines.extend([
            "停住：已经发给用户的那一份，核心还能进主功能。",
            "工作拷贝里关掉了不算。要关的是人家机器上那一份。",
        ])
    if "先填了中枢表" in blob:
        lines.extend([
            "停住：主程序还能进，不要先填中枢表。",
            "先自己跑主程序，再改账本。",
        ])
    if "请主人当质检" in blob or "回我「可以」" in blob:
        lines.extend([
            "停住：中枢自测不要请主人点「可以」。",
            "看盘交差，不要把人拉来当质检。",
        ])
    if "启动器或授权壳有了" in blob:
        lines.extend([
            "停住：旁边有了启动器，核心还能进。不算授权做成。",
            "先自己跑核心：还能进主功能，就还没修好。",
        ])
    if product_type == "exe-rebuild" and phase_id == "6-update" and (
            "update_flow" in blob or "还不是这一版" in blob or "吃新上游不是客户" in blob):
        lines.extend([
            "停住：还没证明「已经装好的软件里点了更新」。",
            "本机再装一次、在文件夹里点，都不算。没接平台却发明开浏览器顶原来的下载，也不算。",
            "你现在只要看：旧电脑上已经装着的那份软件，里面的更新按钮。",
            "停住：客户点更新和跟上新版本是两件事。",
            "客户路径看已装软件里的更新按钮；跟上新版本看档案和改动图。",
            "两句不能焊成一句做成。",
        ])
    pack_update = {
        "5-pack", "6-update", "3-ship", "4-package", "4-staging", "5-build", "6-release",
    }
    if phase_id in pack_update and "没冻住" in blob:
        lines.extend([
            "停住：这一版还没冻住，不许让旧用户去下下一版。",
            "半成品、试包、空白对照，不准放到客户会下到的地址。",
            "你现在只要看：冻本对照填了没有。空白纸不算冻住。",
        ])
    if ("作用列" in blob or "作用是空" in blob or "地址/偏移" in blob
            or (phase_id in pack_update and "功能表没有真实行" in blob)):
        lines.extend([
            "停住：功能对照清单要写作用是什么，不能只写地址。",
            "人能看见功能的那天就记。空表、只写二进制，都不能当清单。",
        ])
    if product_type == "exe-rebuild" and phase_id in ({"1-access"} | pack_update) and (
            "改动图" in blob or "怎么找到" in blob):
        lines.extend([
            "停住：改过的每一刀还没记下怎么找到。",
            "下一版上游不能靠旧脚本。先写窗口原文或命令名。",
        ])
    if phase_id in {"6-update", "6-release"} and (
            "照抄" in blob or "新门" in blob or "还能认" in blob):
        lines.extend([
            "停住：清单是核对用的，不是答案。",
            "先判断这一条还能认还是新门。大变就重做，不许照抄。",
        ])
    opening = phase_id in {"0-discover-plan", "0-spec", "0-intake"}
    if (not opening) and ("物理收据" in blob or "manifest.tests" in blob
            or "说做好了" in blob or "请主人当质检" in blob):
        lines.extend([
            "停住：还没按客户会走的路看见。不许说「做好了」。",
            "请你看窗之前，自己必须先走过客户会碰到的那一份。",
            "停住：不许请主人当质检员。",
            "你看窗之前，它自己必须先按客户路径走过。",
        ])
    if (phase_id in {"3-ui", "2-impl", "4-change", "4-license"} and (
            "物理收据" in blob or "manifest.tests" in blob or "manifest.ui" in blob
            or "已经能用的播放" in blob or "把别处弄坏了" in blob)):
        lines.extend([
            "停住：改这一处，已经能用的别处还要在。",
            "动完必须再走没改名的那些功能。走不通就回退这一刀。",
        ])
    if "不要为过关造窗" in blob:
        lines.extend([
            "停住：命令行不要为过关造窗。",
            "三种基础是有效才放行主命令、无效不放行、到期停主命令。",
        ])
    if "接手安全网缺了" in blob:
        lines.extend([
            "停住：接手带来的安全网丢了。",
            "改功能之前，原来的测试和主程序还要在。",
        ])
    if "不要关软件" in blob:
        lines.extend([
            "停住：网站不要关软件过收费门。",
            "有效才提供服务，无效不提供，到期停服务。收费走页面或接口。",
        ])
    if "核心载荷加启动器" in blob or "不要抄二开" in blob:
        lines.append("停住：不要抄二开的核心载荷加启动器壳。")
        if product_type == "cli-tool":
            lines.append("命令行不要为过关造授权页。有效才放行主命令，无效不放行。")
        elif product_type == "web-service":
            lines.append("网站走站点收费门，不要造桌面授权页。")
        else:
            lines.append("桌面接了授权要自己的授权页验卡密再进主页面，不是扔掉授权页。")
    return lines

