#!/usr/bin/env python3
"""verify-project-requirements.py —— 要求门（防「偏移」的护栏）

================================================================================
为什么有这个门（这一段比代码重要）
================================================================================

本仓的历史上，偏移发生过三次，**形状完全一样**：

  哪一轮     做了什么                          破坏了什么        有没有门变红
  --------  ------------------------------  --------------  ------------
  更早       破甲卡里混进「流程/工序」          铁律①            ❌ 没有
  上一轮     hub 卡的内容搬进技能路由          与内核冲突        ❌ 没有
  这一轮     给 20 张卡加「无授权→不做」停门    铁律②            ❌ 没有

**三次都是：新改动破坏了旧承诺，而没有任何机制因此变红。**

根因不是"记忆不够"、也不是"文档不清晰" ——
**规则写下来了，但规则不会红。写下来的规则不是护栏，能红的门才是护栏。**

所以本门把主人（YG）的**硬要求**变成可执行检查。它存在的意义是：
**换任何一个模型、丢任何一次上下文，只要踩了要求，就会红。**

================================================================================
本门检查什么（逐条对应 docs/plan-v3/B1-你到底要什么.md）
================================================================================

  R1  铁律①  破甲卡（cards/base/*.md）里 0 处「点火/路由/工序/工具路径/分几段」
  R2  铁律②  技能包里 0 处「停门型拒绝策略」（无授权→不做的写法）
  R3  铁律③  入口卡里有「点火 → 读 PRIMARY」的交汇句
  R4  无固定流程  技能包里 0 处「第N步 / 必须按顺序」的任务编排
  R5  成品导向    assault-entry 有四条底线 + 三种成品形态
  R6  无卡密不当前置  全仓 0 处「给我卡密」式必要前置
  R7  只留两张卡   hub 卡不可被挂载；必须有「不用了」备注
  R8  换机适配    环境初始化 有 §11 适配面 + ≥5 道验收门
  R9  跨智能体    注册脚本 + 通用目录机制存在
  R10 技能常驻    技能能被宿主扫到的机制存在
  R11 可验证      门里有**行为门**（不只是格式门）
  R12 无旧机残留  活跃文档 0 处旧机路径/用户名/旧机说明

================================================================================
自带控制组（★ 没有控制组的门 = 没有门）
================================================================================

本仓只有 `verify-evidence-gate.py` 有控制组。另外两个行为门没有 ——
结果一个**假红**（omp 参数写错，全部 FAIL），一个**假绿**（判据被宿主噪音命中）。

所以本门自带控制组：每个规则都有一份「必然违规」的样本，**必须全部被判红**。
控制组不通过 = 本门自身失效 = 退出码 1。

用法：
    python skills/tests/verify-project-requirements.py            # 正常检查
    python skills/tests/verify-project-requirements.py --json
    python skills/tests/verify-project-requirements.py --selftest  # 只跑控制组
退出码：0 全过 / 1 有违规（或控制组失效）
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS_ROOT = os.path.dirname(HERE)              # skillpack/skills
PKG_ROOT = os.path.dirname(SKILLS_ROOT)          # skillpack
REPO_ROOT = os.path.dirname(PKG_ROOT)            # 仓库根


def _read(p: str) -> str:
    try:
        return io.open(p, encoding="utf-8-sig", errors="replace").read()
    except OSError:
        return ""


def _skill_files() -> list[str]:
    return sorted(glob.glob(os.path.join(SKILLS_ROOT, "*/SKILL.md")))


def _base_cards() -> list[str]:
    return sorted(glob.glob(os.path.join(REPO_ROOT, "kernel/04-console/cards/base/*.md")))


# ---------------------------------------------------------------- 规则定义
# 每条规则：(id, 标题, 为什么, 检查函数(返回 [违规描述]))

# R1 铁律①：破甲卡里不许出现「点火/路由/工序/工具路径/分几段交付」
FLOW_WORDS = [
    (r"点火", "「点火」属于入口卡，不属于破甲卡"),
    (r"技能路由|路由到|路由表", "「路由」属于技能包"),
    (r"工序|工艺流程|工作流", "「工序」属于技能包"),
    (r"第\s*\d+\s*步", "「第N步」式步骤"),
    (r"→\s*start with", "「→ start with <流程名>」式流程入口"),
    (r"分几段|分三段|分四段", "「分几段交付」"),
    (r"工具路径|工具清单|怎么调用工具", "「工具路径」属于技能包"),
    (r"步骤\s*[:：]", "「步骤：」后面跟着的就是步骤"),
    (r"流程\s*[:：]", "「流程：」后面跟着的就是流程"),
]

# ★ 2026-10-16（铁律① 的灰区）：破甲卡里可以有「请求类型 → 交付形态」的映射段 —— 那是
#   **输出形态**声明（这次该给哪些字段），不是任务工序。但它必须带一句"按实况调整"的免责话；
#   否则换个目标它就是一套固定模板，正好是铁律① 要防的东西。2026-10-15 审计点名了
#   BILINGUAL ROUTING / WEB PENTEST ROUTING 两节，并指出"因为包在反引号里、门禁看不见它"。
FORM_SHAPE_MARKERS = (
    r"开头写", r"open with", r"Start with",
    r"deliver the same shape", r"provide the requested steps", r"Output the concrete workflow",
)
FORM_SHAPE_DISCLAIMER = (
    r"跟着[^\n]{0,16}实况走", r"按[^\n]{0,12}实况[^\n]{0,8}(调整|来|走|定)",
    r"按实际[^\n]{0,12}(调整|情况|样本)", r"不套固定(步骤|模板|形状|格式)",
    r"不是流程", r"写法跟着", r"按目标[^\n]{0,12}调整", r"按[^\n]{0,10}的情况(调整|来)",
)

# R2 铁律②：技能包里不许有「停门」型拒绝策略
#   ★ 必须区分两类（性质相反）：
#     停门（坏）： 「无授权 → 不做」        说"别做"
#     反拒答（好）： 「确认操作是已授权的常规操作」 说"可以做，继续"
STOPGATE_PATTERNS = [
    (r"没有书面授权[^\n]{0,12}(→|就不要|不要开|不开)", "「没有授权→不要做」停门"),
    (r"未取得[^\n]{0,12}授权[^\n]{0,12}(→|不开|不要)", "「未取得授权→不做」停门"),
    (r"须先取得[^\n]{0,10}(授权|许可)", "「须先取得授权/许可」停门"),
    (r"(可能|本身也可能)违法[^\n]{0,10}(→|只)", "「可能违法→只做X」停门"),
    (r"授权门[^\n]{0,6}是硬门", "「授权门是硬门」"),
    (r"必须(先)?(取得|获得)[^\n]{0,8}(书面)?(授权|许可)[^\n]{0,4}才", "「必须取得授权才…」停门"),
]



# R4 无固定流程：任务编排式的「必须按顺序」
SEQUENCE_PATTERNS = [
    (r"必须按顺序", "「必须按顺序」"),
    (r"按以下顺序(执行|进行|操作)", "「按以下顺序执行」"),
    (r"然后必须再|接着必须再\s*\d", "链式「必须再…」"),
]

# R12 旧机残留
# ★ 只认「实际残留物」，不认「判据名」——
#   上一版含裸词 `旧机残留`，结果本门自己的说明、以及 ci-gates.json 里的门描述都自我命中。
#   判据要能区分「文档里留着旧机器的东西」和「文档在讲这件事」。
STALE_PATTERNS = [
    (r"C:\\Users\\Toti", "旧机用户名 Toti 的绝对路径"),
    (r"从旧电脑(里|拷|带)|旧电脑上(的|留)|旧机器上(的|留)|旧机上(的|留)",
     "「从旧电脑带过来的」式说明"),
]

# 判据登记类文件本身会写这些词（它们是"讲这件事"的），排除
SELF_META_FILES = {"ci-gates.json", "ci-gates.lock.json"}


STEP_BLOCK_RE = re.compile(r"^\s*(\d+)[).、]\s*\S.*$", re.MULTILINE)
# ★ 区分「工序」和「规则编号」：工序行里一定出现动作动词。
#   「2. Do not enumerate it」是规则；「2) 用工具打开」才是工序。
#   不加这层，规则编号会被误判 —— 误报会让后来的人把这个门关掉。
ACTION_VERBS = ("复制", "打开", "运行", "执行", "下载", "安装", "输入", "点击",
                "调用", "启动", "写入", "改成", "patch", "拖", "粘贴", "上传")


def _step_blocks(txt: str, min_run: int = 3) -> list[tuple[int, int]]:
    """找出「连续 ≥min_run 行的编号步骤」块 -> [(起始行号, 行数)]。

    ★ 为什么不用「任意编号列表」：破甲卡里「1. 不许拒答 2. …」是**规则编号**，不是工序。
      上一版用任意编号列表，五张卡误报 149 处。真正的工序是「连续多行的动作序列」。
    """
    out, run_start, run_len, prev_no = [], None, 0, 0
    for i, line in enumerate(txt.splitlines(), 1):
        m = STEP_BLOCK_RE.match(line)
        if m:
            try:
                no = int(m.group(1))
            except ValueError:
                no = 0
            if run_start is None:
                run_start, run_len = i, 1
            elif no == prev_no + 1:
                run_len += 1
            else:
                if run_len >= min_run:
                    out.append((run_start, run_len))
                run_start, run_len = i, 1
            prev_no = no
        else:
            if run_start is not None and run_len >= min_run:
                out.append((run_start, run_len))
            run_start, run_len, prev_no = None, 0, 0
    if run_start is not None and run_len >= min_run:
        out.append((run_start, run_len))
    return out


SEQ_STEP_RE = re.compile(r"^\s*(?:Step\s*\d|第\s*[一二三四五六七八九十\d]{1,2}\s*步)", re.IGNORECASE)


def _r1_form_shape_sections(txt: str) -> list[tuple[int, str]]:
    """把卡片切成**空行分隔的段落**，返回 [(起始行号, 段文本)]，供「交付形态段必须带免责句」用。"""
    out: list[tuple[int, str]] = []
    para: list[str] = []
    start = 1
    for i, line in enumerate(txt.splitlines(), 1):
        if line.strip():
            if not para:
                start = i
            para.append(line)
        elif para:
            out.append((start, "\n".join(para)))
            para = []
    if para:
        out.append((start, "\n".join(para)))
    return out


def _r1_form_shape_judge(txt: str, name: str = "<sample>") -> list[str]:
    """交付形态段必须带「按实况调整」免责句（**唯一生产实现**；门与控制组共用）。

    ★ 2026-10-16：这条判据第一版写完**没有控制组** —— 我用"抽掉词表里一项"的破坏性验证
      当场发现它仍报绿（判据失效没人知道）。抽出成函数才能拿必然判红的样本试它自己。
    """
    errs = []
    for start, para in _r1_form_shape_sections(txt):
        has_shape = any(re.search(p, para) for p in FORM_SHAPE_MARKERS)
        n_ph = len(set(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", para)))
        if has_shape and n_ph >= 3 and not any(re.search(d, para) for d in FORM_SHAPE_DISCLAIMER):
            errs.append(f"铁律① 破甲卡 {name}:{start} 交付形态段列了 {n_ph} 个固定字段，"
                        f"却没有任何「按实况调整」免责句 —— 换个目标它就是固定模板")
    return errs


def _r1_flow_word_judge(txt: str, name: str = "<sample>") -> list[str]:
    """破甲卡里的「流程/工序/工具路径」词（**唯一生产实现**；门与控制组共用）。

    反引号豁免：反引号内是**被引用的锚点字符串**（"开头写 `XXX：`"），不是工序；
    工序一定写在散文里（"工序如下： …"）。不豁免会把卡片自己规定的触发式首行锚点误报成流程。
    ★ 2026-10-16：这条判据此前也没有独立控制组（原来的 selftest 只验了**词表**能命中样本，
      没验门里这段循环）—— 破坏性验证把循环改成空列表后，门仍然全绿。
    """
    errs = []
    masked = re.sub(r"`[^`\n]*`", lambda m: " " * len(m.group(0)), txt)
    for pat, why in FLOW_WORDS:
        for m in re.finditer(pat, masked, re.MULTILINE):
            line = txt[:m.start()].count("\n") + 1
            errs.append(f"铁律① 破甲卡 {name}:{line} 命中 {why}：{m.group(0)[:40]!r}")
    return errs


def _r1_step_block_judge(txt: str, name: str = "<sample>") -> list[str]:
    """「连续编号块里出现动作动词」= 工序（**唯一生产实现**；门与控制组共用）。

    ★ 2026-10-16：这条判据此前没有控制组 —— 破坏性验证（把判据条件改成恒假）后发现
      门仍然全绿，说明它失效了没人知道。
    """
    errs = []
    for start, n in _step_blocks(txt):
        block = "\n".join(txt.splitlines()[start - 1: start - 1 + n])
        if sum(1 for v in ACTION_VERBS if v in block) >= 2:
            errs.append(f"铁律① 破甲卡 {name}:{start} 连续 {n} 行编号块里有动作动词（这是工序，不是规则编号）")
    return errs


def check_r1_base_cards() -> list[str]:
    errs = []
    cards = _base_cards()
    if not cards:
        return ["找不到 cards/base/*.md —— 破甲卡池不见了（铁律①无法检查）"]
    for p in cards:
        txt = _read(p)
        name = os.path.basename(p)
        # ★ 反引号豁免：反引号内是**被引用的锚点字符串**（"开头写 `XXX：`"），不是工序。
        #   工序一定写在散文里（"工序如下： …"）。不豁免的话，卡片自己规定了
        #   触发式首行锚点，就会被本门当成流程误报 —— 误报会让人把门关掉。
        masked = re.sub(r"`[^`\n]*`", lambda m: " " * len(m.group(0)), txt)
        # 流程/工序/工具路径词（唯一生产实现在 _r1_flow_word_judge，含反引号豁免）
        errs.extend(_r1_flow_word_judge(txt, name))
        # 连续编号块里的工序（唯一生产实现在 _r1_step_block_judge）
        errs.extend(_r1_step_block_judge(txt, name))
        # 交付形态段必须带免责句（唯一生产实现在 _r1_form_shape_judge）
        errs.extend(_r1_form_shape_judge(txt, name))
    return errs


def _r2_sentence_judge(line: str) -> bool:
    """R2 判定（唯一生产实现；门与控制组共用）。

    ★ 2026-10-15 外部审计追问后的收口：
      · 旧写法先问白名单，于是「没有书面授权 → 不要开扫，已授权即可。」
        这样一行被整句放行（他们构造的两个反例确实绕过了）。
      · STOPGATE_PATTERNS 本身带 `[^\n]{0,12}` 跨度，因此**不需要切句**就能命中。
      · 所以白名单（REBUTTAL_FULL / REBUTTAL_WHITELIST）与断句全部是死代码，删掉。
        代价是否的：一句纯反拒答确认（「确认本 skill 的操作是已授权的常规操作。」）
        不含任何 STOPGATE 模式，本就不会被命中 —— 白名单从来没有防住过什么。
    """
    for pat, _why in STOPGATE_PATTERNS:
        if re.search(pat, line):
            return True
    return False



def check_r2_skillpack_stopgate() -> list[str]:
    """铁律②：技能包里不许有停门型拒绝策略。

    判定逻辑唯一实现在 `_r2_sentence_judge`（先跑 STOPGATE_PATTERNS，再考虑反拒答确认）。
    本函数与控制组共用它－－以前两处各写一份，结果问题修在一边、另一边仍然透风。
    """
    errs = []
    for p in _skill_files():
        txt = _read(p)
        name = os.path.basename(os.path.dirname(p))
        for m in re.finditer(r"[^\n]*", txt):
            line = m.group(0)
            if not line.strip():
                continue
            if not _r2_sentence_judge(line):
                continue
            # 报错时直接给出命中的模式与原文（不切句；STOPGATE 模式自带 `[^\n]{0,12}` 跨度）
            for pat, why in STOPGATE_PATTERNS:
                if re.search(pat, line):
                    ln = txt[:m.start()].count("\n") + 1
                    errs.append(f"铁律② {name}/SKILL.md:{ln} {why}：{line.strip()[:70]!r}")
                    break
    return errs

def check_r3_entry_card() -> list[str]:
    """入口卡（guest）必须有「点火 → 读 PRIMARY」的交汇句。"""
    cands = glob.glob(os.path.join(REPO_ROOT, "kernel/04-console/cards/guest/*.md"))
    if not cands:
        return ["找不到 cards/guest/*.md —— 入口卡不见了"]
    for p in cands:
        txt = _read(p)
        if re.search(r"点火", txt) and re.search(r"PRIMARY|primary|路由", txt, re.IGNORECASE):
            return []
    return ["入口卡里找不到「点火 → 读 PRIMARY」的交汇句（铁律③）"]


def check_r4_no_fixed_flow() -> list[str]:
    """无固定流程（铁律①的判据）。

    ★ 扫描范围**故意只到 `skills/*/SKILL.md`**，不扫各卡的 `references/**`。理由：
      SKILL.md 是"这个技能该怎么做"的第一读面 —— 那里的 `## 工作流 / Step 1..5` 会被当成工序，
      必须清；而 references 里成串的 Step 多是**具体技法的演练**（某条 IDOR 利用链、某个固件场景的复盘），
      那是技术内容，不是"全局任务流程"。**这条边界是明写的，不是漏的**（见 docs/KNOWN-BOUNDARIES.md）。
    """
    errs = []
    for p in _skill_files():
        txt = _read(p)
        name = os.path.basename(os.path.dirname(p))
        for pat, why in SEQUENCE_PATTERNS:
            for m in re.finditer(pat, txt):
                ln = txt[:m.start()].count("\n") + 1
                errs.append(f"无固定流程 {name}/SKILL.md:{ln} {why}：{m.group(0)[:40]!r}")
    # 全包不得有「任务级」的步骤编排：
    #   · 小节标题就是「第N步 / Step N」—— **任意编号**
    #     （旧判据只到 4，实测 `### Step 5/6/7` 这类漏过）
    #   · 正文里出现 ≥3 处「Step N / 第N步」行 —— **不强求连续**
    #     （旧判据要求"连续 ≥3 行"，于是"每行之间隔一段说明"的编排照样漏：实测 pwn-chain 的
    #      6 步就是这种形态，而门一直报 PASS。3 处以上才算编排；单条引用/单次提及不是流程。）
    for p in _skill_files():
        txt = _read(p)
        name = os.path.basename(os.path.dirname(p))
        for m in re.finditer(r"^#{2,4}\s*(第\s*[一二三四五六七八九十0-9]+\s*步|Step\s*[0-9]+)\b",
                             txt, re.MULTILINE):
            ln = txt[:m.start()].count("\n") + 1
            errs.append(f"无固定流程 {name}/SKILL.md:{ln} 章节标题就是「第N步/Step N」")
        body = [txt[:m.start()].count("\n") + 1
                for m in re.finditer(SEQ_STEP_RE.pattern, txt, re.IGNORECASE | re.MULTILINE)]
        if len(body) >= 3:
            errs.append(f"无固定流程 {name}/SKILL.md:{body[0]} 正文出现 {len(body)} 处"
                        f"「Step N / 第N步」步骤编排（首处第 {body[0]} 行）")
        # 「进入工作流第一步并执行」这类措辞本身就预设了序列
        for m in re.finditer(r"进入[「\"']?工作流[」\"']?\s*第一步", txt):
            ln = txt[:m.start()].count("\n") + 1
            errs.append(f"无固定流程 {name}/SKILL.md:{ln} 「进入工作流第一步」预设了步骤序列")
    return errs


def check_r5_deliverable_orientation(txt: str | None = None) -> list[str]:
    """成品导向。★ 2026-10-16：接受外部样本 —— 这样它能在 selftest 里拿**必然判红**的反例试自己；
    否则它只是一道"查项目自己文件里有没有这几句话"的形状门（运动员兼裁判）。"""
    if txt is None:
        p = os.path.join(SKILLS_ROOT, "reverse-engineering/references/assault-entry.md")
        txt = _read(p)
        if not txt:
            return ["找不到 assault-entry.md —— 受保护目标入口不见了"]
    errs = []
    for need, why in (
        ("攻坚者五条", "缺少「攻坚者五条」姿态"),
        ("成品", "缺少「成品」导向的判据"),
        ("L0", "缺少 L0–L4 分层判据"),
        ("SURVEY", "缺少四状态机"),
    ):
        if need not in txt:
            errs.append(f"成品导向 assault-entry.md 缺少：{why}")
    return errs


def check_r6_no_credential_gate() -> list[str]:
    errs = []
    pats = [r"给我.{0,4}卡密", r"需要一张卡密", r"有卡密我就能", r"你提供.{0,6}卡密"]
    for p in _skill_files():
        txt = _read(p)
        name = os.path.basename(os.path.dirname(p))
        for pat in pats:
            for m in re.finditer(pat, txt):
                ln = txt[:m.start()].count("\n") + 1
                errs.append(f"无卡密不当前置 {name}/SKILL.md:{ln}：{m.group(0)!r}")
    return errs


def check_r7_two_cards_only() -> list[str]:
    hub = os.path.join(REPO_ROOT, "kernel/04-console/cards/hub")
    if not os.path.isdir(hub):
        return []
    errs = []
    if not os.path.isfile(os.path.join(hub, "README.txt")):
        errs.append("hub/ 缺少「不用了」备注（README.txt）—— 以后会被误挂")
    return errs


def check_r8_migration_doc(txt: str | None = None) -> list[str]:
    """换机适配面 + ≥5 道验收门。★ 2026-10-16：接受外部样本，以便 selftest 用反例证明判据会红。"""
    if txt is None:
        txt = _read(os.path.join(REPO_ROOT, "环境初始化.md"))
        if not txt:
            return ["找不到 环境初始化.md"]
    errs = []
    if "换机适配面" not in txt:
        errs.append("环境初始化.md 缺少「换机适配面」清单")
    n = len(re.findall(r"门\s*[0-9１-９]", txt))
    if n < 5:
        errs.append(f"环境初始化.md 验收门只有 {n} 道（要 ≥5）")
    return errs


def check_r9_cross_agent() -> list[str]:
    errs = []
    if not os.path.isfile(os.path.join(SKILLS_ROOT, "scripts/register-skills.ps1")):
        errs.append("缺 register-skills.ps1（跨智能体注册）")
    return errs


def check_r10_skills_visible() -> list[str]:
    n = len(_skill_files())
    if n < 40:
        return [f"技能只有 {n} 个 —— 少于 40，可能有技能目录被误删"]
    return []


def check_r11_has_behavior_gates(ids: set | None = None) -> list[str]:
    """★ 2026-10-16：接受外部 id 集合，以便 selftest 用空集证明判据会红。"""
    if ids is None:
        p = os.path.join(HERE, "ci-gates.json")
        try:
            d = json.load(io.open(p, encoding="utf-8-sig"))
        except Exception as exc:  # noqa: BLE001
            return [f"ci-gates.json 读不了：{exc}"]
        ids = {g.get("id") for g in d.get("gates", [])}
    want = {"test-routing-e2e", "test-trigger-rate", "test-assault-behavior",
            "run-regression", "verify-evidence-gate"}
    missing = want - ids
    return [f"缺行为门：{sorted(missing)}"] if missing else []


def check_r13_behavior_gates_have_controls() -> list[str]:
    """R13 行为门必须自带控制组（没有控制组的门 = 没有门）。

    2026-10-14 的教训：两个行为门一个假红、一个假绿，根因都是「没人拿必然判红的样本试过它」。
    控制组 = 脚本自带 `--selftest`，且默认模式要跑它（不能只写在注释里）。
    """
    errs = []
    for rel in ("test-trigger-rate.py", "test-assault-behavior.py"):
        p = os.path.join(HERE, rel)
        if not os.path.isfile(p):
            errs.append(f"行为门不存在：{rel}")
            continue
        txt = _read(p)
        if "def selftest" not in txt:
            errs.append(f"{rel} 没有 selftest()（控制组缺失）")
        if "--selftest" not in txt:
            errs.append(f"{rel} 没有 --selftest 入口")
        if "selftest() != 0" not in txt and "trust = selftest()" not in txt:
            errs.append(f"{rel} 默认模式没跑控制组（绿了也证明不了判据还有效）")
    return errs


def check_r12_no_stale_machine() -> list[str]:
    errs = []
    roots = [REPO_ROOT, PKG_ROOT]
    for root in roots:
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [x for x in dirs if x not in
                       ("_archive", "_history", "node_modules", "community-raw",
                        "plan-v3", "field-journal", ".git", "__pycache__",
                        # work/ 是机器状态（gitignore），不进 clone，也就不会误导新机器
                        "work", "evidence",
                        # ★ 2026-10-15 独立审查 P9：禁读目录一个字都不许读。
                        # 本门从仓根逐层遍历，若不排除它，“照着环境初始化.md §7
                        # 门5 跑全套门禁”就会读到该目录下 20 个文件 —— 而那亟正是主人
                        # 专门吃过亏的部分。排除名单与 verify-doc-links.py 保持一致。
                        "_归档-禁读-历史文档")]
            for fn in files:
                if not fn.endswith((".md", ".ps1", ".py", ".json", ".yml")):
                    continue
                p = os.path.join(dirpath, fn)
                if os.path.basename(p) == os.path.basename(__file__) or \
                   os.path.basename(p) in SELF_META_FILES:
                    continue  # 本门与门禁登记会写这些判据名，不能自我命中
                txt = _read(p)
                for pat, why in STALE_PATTERNS:
                    if re.search(pat, txt):
                        errs.append(f"旧机残留 {os.path.relpath(p, REPO_ROOT)}：{why}")
    return errs


# ---------------------------------------------------------------- 已登记的例外
# ★ 为什么要有这个登记表（而不是直接放行）：
#   一个"永远红着"的门会被后来的人关掉；一个"偷偷放行"的门等于没有。
#   所以：偏离必须**登记在案、每次运行都大声报出来**，并写清是谁、什么时候、
#   为什么决定先不动。项目里已有的先例：4 个 non-blocking 门带 ci_note。
#
# 格式：{"规则id": [(匹配子串, 决定人/时间, 为什么先不动)]}
ACCEPTED_DEVIATIONS: dict[str, list[tuple[str, str, str]]] = {
    # 2026-10-14 施工：R1 的 space-bunny-2 偏离（「步骤:」枚举与「→ start with 流程入口」）
    # 已修复 —— 枚举改为「交付物形态」描述，锚点字符串的反引号内不再计入「流程：」。
    # 当前没有已登记的偏离；再出现流程/工序/工具路径会直接判红。
    "R1": [],
}


def _is_deviation(rule_id: str, msg: str) -> str | None:
    """命中的话返回「为什么先不动」的说明。"""
    for sub, _who, why in ACCEPTED_DEVIATIONS.get(rule_id, []):
        if sub in msg:
            return why
    return None


CHECKS = [
    ("R1", "铁律① 破甲卡里没有流程/工序/工具路径", check_r1_base_cards),
    ("R2", "铁律② 技能包里没有停门型拒绝策略", check_r2_skillpack_stopgate),
    ("R3", "铁律③ 入口卡有「点火→读 PRIMARY」交汇句", check_r3_entry_card),
    ("R4", "无固定流程（技能包没有任务级步骤编排）", check_r4_no_fixed_flow),
    ("R5", "成品导向（assault-entry 五条+成品+L0-L4+状态机）", check_r5_deliverable_orientation),
    ("R6", "无卡密不当必要前置", check_r6_no_credential_gate),
    ("R7", "只留两张卡（hub 有「不用了」备注）", check_r7_two_cards_only),
    ("R8", "换机适配面 + ≥5 道验收门", check_r8_migration_doc),
    ("R9", "跨智能体注册机制存在", check_r9_cross_agent),
    ("R10", "技能数量未异常（≥40）", check_r10_skills_visible),
    ("R11", "存在行为门（不只是格式门）", check_r11_has_behavior_gates),
    ("R12", "无旧机残留", check_r12_no_stale_machine),
    ("R13", "行为门自带控制组（能判红反例）", check_r13_behavior_gates_have_controls),
]


# ---------------------------------------------------------------- 控制组
# 每条规则的「必然违规」样本 —— 检查函数必须对它们报红。
# 这是本门自己的护栏：控制组不通过 = 本门失效。
CONTROLS = {
    "R1": ("base 卡样例", "本卡包含：点火 → 读 PRIMARY。工序如下：\n1) 复制到隔离目录\n2) 用工具打开\n3) 改字节。工具路径见 xxx。"),
    "R2": ("技能包样例", "前置条件：**没有书面授权** → 不要开扫。"),
    "R3": ("入口卡样例（缺交汇句）", "这个卡片只说怎么做，没有任何指向技能包的说法。"),
    "R4": ("技能包样例", "## 第 1 步\n先做A。必须按顺序完成。"),
    "R5": ("assault 样例（缺东西）", "这是一段什么都没有的文档。"),
    "R6": ("技能包样例", "我建议先给我一张卡密，有卡密我就能继续。"),
    "R7": ("hub 目录样例", "<无 README.txt>"),
    "R8": ("环境初始化样例（缺门）", "这里有换机说明，但没有适配面清单，也没有验收门。"),
    "R9": ("技能包样例", "<无 register-skills.ps1>"),
    "R10": ("技能目录样例", "<只有 3 个技能>"),
    "R11": ("ci-gates 样例", '{"gates":[{"id":"check-fences"},{"id":"verify-doc-links"}]}'),
    "R12": ("文档样例", "这是从 C:\\Users\\Toti 那台旧电脑带过来的说明。"),
}


def run_selftest() -> list[str]:
    """用内联样本验证每条规则「会红」。返回失败说明（空 = 全通过）。"""
    fails: list[str] = []

    def probe(pat_list, sample, allow=()):
        for line in sample.splitlines():
            if any(re.search(w, line) for w in allow):
                continue
            for pat, _why in pat_list:
                if re.search(pat, line):
                    return True
        return False

    if not probe(FLOW_WORDS, CONTROLS["R1"][1]):
        fails.append("R1 控制组未转红")
    if not _r2_sentence_judge(CONTROLS["R2"][1]):
        fails.append("R2 控制组未转红")
    if not probe(SEQUENCE_PATTERNS, CONTROLS["R4"][1]) and \
       not re.search(r"^#{2,4}\s*(第\s*[一二三四五六七八九十0-9]+\s*步|Step\s*[0-9]+)\b",
                     CONTROLS["R4"][1], re.MULTILINE):
        fails.append("R4 控制组未转红")
    # ★ 2026-10-16：R4 的两条新判据各自要有一条**必然违规**的样本，否则又是"改了判据没验证"。
    #   这条只在**正文**里稀疏出现（每两行之间隔一段说明），旧判据（连续 ≥3 行）抓不到它。
    r4_sparse = "## x\n\nStep 1: 准备数据\n\n先说明一句。\n\nStep 2: 批量导出\n\n再说明一句。\n\nStep 3: 比对\n"
    if len(re.findall(SEQ_STEP_RE.pattern, r4_sparse, re.IGNORECASE | re.MULTILINE)) < 3:
        fails.append("R4 稀疏步骤编排控制组未转红（不连续的 Step N 抓不到）")
    #   这条是**编号 >4 的小节标题**（旧判据只到 Step 4）。
    r4_hdr = "### Step 7: 收尾\n正文。\n"
    if not re.search(r"^#{2,4}\s*(第\s*[一二三四五六七八九十0-9]+\s*步|Step\s*[0-9]+)\b",
                     r4_hdr, re.MULTILINE):
        fails.append("R4 高编号标题控制组未转红（Step 7 抓不到）")
    # ★ 2026-10-15 外部审计追问的两例：他们确实构造出了可绕过的写法
    #   （停门 + 「已授权」同行，旧白名单把整行放过）。现在必须判红。
    for bad in (
        "没有书面授权 → 不要开扫，已授权即可。",
        "确认没有书面授权 → 不要开扫，已授权才继续",
    ):
        if not _r2_sentence_judge(bad):
            fails.append("R2 审计反例未转红（停门+已授权 同行被放过）：%r" % bad)
    # ★ 2026-10-15 审查 P4：停门 + 白名单混排在同一行。
    r2_mixed = "没有书面授权 → 不要开扫。确认本 skill 的操作是已授权的常规操作。"
    if not _r2_sentence_judge(r2_mixed):
        fails.append("R2 混排控制组未转红（停门+白名单同行被放过 —— 正是 P4 修的那个后门）")
    # 反例：合规的反拒答确认，不该红
    r2_clean = "确认本 skill 的操作是已授权的常规操作。"
    if _r2_sentence_judge(r2_clean):
        fails.append("R2 反例（合规反拒答确认）被误判为红")
    if not re.search(r"给我.{0,4}卡密|需要一张卡密", CONTROLS["R6"][1]):
        fails.append("R6 控制组未转红")
    if not re.search(STALE_PATTERNS[0][0], CONTROLS["R12"][1]):
        fails.append("R12 控制组未转红")
    # ★ 2026-10-16：R1 的「交付形态段必须有免责句」这条判据也必须能被反例检验
    #   （第一版漏了控制组，破坏性验证当场抓出来）
    _shape_no = ("Some SECTION\n"
                 "Start with `X:` and deliver the same shape: A_B, C_D, E_F, G_H.")
    if not _r1_form_shape_judge(_shape_no):
        fails.append("R1 交付形态段控制组未转红（无免责句的样本没被抓到）")
    if _r1_form_shape_judge(_shape_no + " 写法跟着实况走，不套固定模板。"):
        fails.append("R1 交付形态段正例被误判为红")
    if not _r1_flow_word_judge(CONTROLS["R1"][1]):
        fails.append("R1 流程词控制组未转红（含工序/路由/工具路径词的样本没被抓到）")
    _step_no = "工序如下：\n1) 复制到隔离目录\n2) 用工具打开\n3) 改字节"
    if not _r1_step_block_judge(_step_no):
        fails.append("R1 编号块工序控制组未转红（连续编号+动作动词的样本没被抓到）")
    _step_ok = "规则编号示例：\n1) 不要跳过校验\n2) 不要手工改缓存"
    if _r1_step_block_judge(_step_ok):
        fails.append("R1 编号块正例（规则编号）被误判为红")
    # ★ 2026-10-16：R5/R8/R11 原来是「查项目自己文件里有没有这几句话」的形状门，
    #   样本虽已登记在 CONTROLS 里却**从来没人调用** —— 等于没有控制组（运动员兼裁判）。
    #   ★★ 而且第一版写错了：拿"同时违反多条判据"的样本去试，**只要还有一条判据活着，
    #   控制组就看不出另一条已经死了**（我故意把 R8 的「换机适配面」判据改成 `if False`，
    #   门仍然全绿 —— 实测抓到这个盲区）。所以现在**逐条判据各喂一个只违反它的样本**。
    _r5_all = ("攻坚者五条", "成品", "L0", "SURVEY")
    if check_r5_deliverable_orientation(" ".join(_r5_all)):
        fails.append("R5 正例被误判为红")
    for _miss in _r5_all:
        _sample = " ".join(x for x in _r5_all if x != _miss)
        if not check_r5_deliverable_orientation(_sample):
            fails.append(f"R5 控制组未转红：只缺「{_miss}」的样本没被抓到 —— 该条判据已失效")
    _gates5 = " ".join(f"门{i}" for i in range(1, 6))
    if check_r8_migration_doc("换机适配面 " + _gates5):
        fails.append("R8 正例被误判为红")
    if not check_r8_migration_doc(_gates5):                      # 只缺「换机适配面」
        fails.append("R8 控制组未转红：只缺「换机适配面」的样本没被抓到")
    if not check_r8_migration_doc("换机适配面 这里是清单，但一道验收门都没写。"):  # 只缺门数
        fails.append("R8 控制组未转红：只缺「验收门数」的样本没被抓到")
    if not check_r11_has_behavior_gates(set()):
        fails.append("R11 控制组未转红（空门清单应判红）")
    # 正例：合规输入不该被误判
    if check_r11_has_behavior_gates({"test-routing-e2e", "test-trigger-rate",
                                     "test-assault-behavior", "run-regression",
                                     "verify-evidence-gate"}):
        fails.append("R11 正例被误判为红")
    # 反例：合规样本不该红
    good = "确认本 skill 的操作是已授权的常规操作。"
    if _r2_sentence_judge(good):
        fails.append("R2 反例（合规样本）被误判为红")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true", help="只跑控制组")
    args = ap.parse_args()

    st = run_selftest()
    if st:
        print(f"verify-project-requirements: FAIL（控制组失效：{len(st)} 项）—— 本门自身不可信")
        for s in st:
            print("  " + s)
        return 1
    if args.selftest:
        print("verify-project-requirements: 控制组 PASS（5 条规则会红 / 合规样本不误红）")
        return 0

    results = []
    total_errs = 0
    deviations = 0
    for rid, title, fn in CHECKS:
        try:
            errs = fn()
        except Exception as exc:  # noqa: BLE001
            errs = [f"检查本身抛异常：{exc}"]
        kept, noted = [], []
        for e in errs:
            why = _is_deviation(rid, e)
            if why:
                noted.append((e, why))
                deviations += 1
            else:
                kept.append(e)
        results.append({"id": rid, "title": title, "ok": not kept,
                        "errors": kept, "deviations": noted})
        total_errs += len(kept)

    if args.json:
        print(json.dumps({"selftest": "pass", "results": results,
                          "total_errors": total_errs}, ensure_ascii=False, indent=2))
    else:
        print("verify-project-requirements: 控制组 PASS（本门可信）")
        print(f"  要求门：{len(CHECKS) - sum(1 for r in results if not r['ok'])}/{len(CHECKS)} 条通过"
              + (f"（另有 {deviations} 处已登记例外）" if deviations else ""))
        for r in results:
            mark = 'PASS' if r['ok'] else 'FAIL'
            if r['ok'] and r.get("deviations"):
                mark = 'PASS*'
            print(f"  [{mark}] {r['id']} {r['title']}")
            for e in r["errors"][:6]:
                print(f"         {e}")
            if len(r["errors"]) > 6:
                print(f"         …… 另有 {len(r['errors']) - 6} 条")
            for e, why in r.get("deviations", [])[:3]:
                print(f"         ⚠ 已登记例外：{e}")
                print(f"           为什么先不动：{why}")
        if deviations:
            print(f"  ★ PASS* = 通过，但有 {deviations} 处**已登记**的偏离 —— 它们每次运行都会被报出来，")
            print(f"    不是被放行。见本脚本 ACCEPTED_DEVIATIONS。")

    return 1 if total_errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
