#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""经验卡体系的契约测试 —— 含**真会失败**的反例控制组。

这道门禁测三件事：

1. 仓内所有卡满足晋级门 7 条 + 无秘密检查（正例）。
2. 反例控制组：把每一类坏卡真的造出来，验证 `experience-card.py validate`
   对每一类都**转红**。只跑正例的话，「validate 永远返回 0」和
   「validate 真在检查」长得一模一样 —— 这正是经验卡
   `gate-self-must-prove-failure` 描述的那类同义反复门禁。
3. 索引与卡片不漂移：INDEX.md 里的卡数与磁盘上的卡数一致，且每个 id 都能被 search 命中。

反例在临时目录里造，**绝不写进仓库**。

退出码：0 全过 / 1 有失败。
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"
CARD_DIR = SKILLS / "experience-cards"
TOOL = ROOT / "skills" / "scripts" / "experience-card.py"


def run_validate(cards_dir: Path, work: Path) -> subprocess.CompletedProcess:
    """在指定卡目录上跑一次 validate（通过环境变量换目录，不改脚本默认行为以外的任何东西）。

    experience-card.py 的 CARDS 常量由仓库位置推导，所以这里用一个**仓库内**的
    临时目录做替身：把它放在仓库 skills/ 下的 .tmp-<rand> 里，跑完删掉。
    这样 import 与路径推导的语义和真实运行完全一致。
    """
    env = dict(os.environ)
    env["EXPERIENCE_CARD_DIR"] = str(cards_dir)
    return subprocess.run(
        [sys.executable, str(TOOL), "validate"],
        capture_output=True, text=True, env=env, timeout=120, cwd=str(work),
    )


def stage_bad_card(src: Path, cards_dir: Path) -> Path:
    """把一张真卡复制成替身目录，并施加一类具体的坏掉法。"""
    cards_dir.mkdir(parents=True, exist_ok=True)
    for p in src.glob("*.json"):
        shutil.copy2(p, cards_dir / p.name)
    return cards_dir


def main() -> int:
    fails = 0
    real_cards = sorted(CARD_DIR.glob("*.json"))
    if not real_cards:
        print("经验卡目录为空：经验卡体系必须至少有真卡，门禁才有东西可测")
        return 1

    print("=== 经验卡 · 契约测试 ===")

    # ── 1. 正例：仓内全部卡过关 ─────────────────────────────────
    r = run_validate(CARD_DIR, ROOT)
    if r.returncode != 0:
        print("  [FAIL] 正例：仓内卡未通过晋级门")
        print("    " + (r.stdout or "").strip().replace("\n", "\n    "))
        fails += 1
    else:
        print(f"  [PASS] 正例：{len(real_cards)} 张卡通过晋级门 + 无秘密检查")

    # ── 2. 反例控制组：每一类坏卡都必须被抓 ────────────────────
    # 取第一张真卡当模板，施加单点破坏。判据是「validate 必须返回非 0 且指出该类问题」。
    template = json.loads(real_cards[0].read_text(encoding="utf-8"))
    tmpl_name = real_cards[0].name

    def mutated(fn) -> tuple[str, Path]:
        d = Path(tempfile.mkdtemp(prefix="card-negctl-"))
        cards = d / "cards"
        cards.mkdir()
        card = copy.deepcopy(template)
        fn(card)
        (cards / tmpl_name).write_text(
            json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(d), cards

    def drop_second_repro(c):
        c["reproductions"] = c["reproductions"][:1]

    def fabricate_fixture(c):
        c["fixture"]["path"] = "skills/experience-cards/fixtures/does-not-exist.json"

    def stale_fixture_hash(c):
        c["fixture"]["sha256"] = "1" * 64

    def empty_applies_when(c):
        c["scope"]["appliesWhen"] = []

    def empty_oracle(c):
        c["oracles"]["negative"] = ""

    def drop_validation(c):
        c["validation"] = {}

    def back_to_candidate(c):
        c["status"] = "candidate"

    def secret_in_card(c):
        c["note"] = "token ghp_" + "a" * 36

    cases = [
        ("只有 1 次复现", drop_second_repro, "晋级门 1"),
        ("编造 fixture 路径", fabricate_fixture, "晋级门 2"),
        ("fixture 哈希不符", stale_fixture_hash, "晋级门 2"),
        ("空的 appliesWhen", empty_applies_when, "晋级门 6"),
        ("空的 negative oracle", empty_oracle, "晋级门 4"),
        ("没有验证命令", drop_validation, "晋级门 7"),
        ("status 退回 candidate", back_to_candidate, "status 必须是 promoted"),
        ("卡里塞了 GitHub token", secret_in_card, "无秘密检查"),
    ]

    neg_root = Path(tempfile.mkdtemp(prefix="card-negctl-root-"))
    try:
        for label, fn, expect in cases:
            tmp, cards = mutated(fn)
            try:
                rr = run_validate(cards, neg_root)
                out = (rr.stdout or "") + (rr.stderr or "")
                red = rr.returncode != 0
                named = expect in out
                if red and named:
                    print(f"  [PASS] 反例「{label}」-> validate 转红并点名「{expect}」")
                else:
                    print(f"  [FAIL] 反例「{label}」-> rc={rr.returncode} "
                          f"（应非 0），是否点名「{expect}」={named}")
                    print("    " + out.strip().replace("\n", "\n    ")[:400])
                    fails += 1
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
    finally:
        shutil.rmtree(neg_root, ignore_errors=True)

    # ── 3. 索引不漂移 ──────────────────────────────────────────
    index = CARD_DIR / "INDEX.md"
    if not index.exists():
        print("  [FAIL] 缺 INDEX.md —— 经验卡没有机器可读的检索入口等于没沉淀")
        fails += 1
    else:
        text = index.read_text(encoding="utf-8")
        missing = [p.stem for p in real_cards if p.stem not in text]
        if missing:
            print(f"  [FAIL] INDEX.md 漏了卡：{missing}（跑 experience-card.py stamp）")
            fails += 1
        else:
            print(f"  [PASS] INDEX.md 覆盖全部 {len(real_cards)} 张卡")

    # ── 4. 检索质量（正例 + 反例）─────────────────────────────
    # 为什么必须测检索：2026-10-11 实测两处**静默失效** ——
    #   * 把整段中文当一个词做 `in` 匹配 → 永远不命中（卡里没有这几个字连在一起）
    #   * 把 scope 整个 JSON 塞进语料 → 「stops 条件」这种查询命中每一张卡（实测 4/4）
    # 两者都不报错，都「有输出」，所以不测就只能靠人肉发现。
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "experience_card_mod", str(TOOL.parent / "experience-card.py"))
    ec = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(ec)

    print()
    print("=== 检索质量 ===")

    def qcase(label: str, ok: bool, detail: str = "") -> None:
        nonlocal fails
        if ok:
            print(f"  [PASS] {label}")
        else:
            print(f"  [FAIL] {label}  {detail}")
            fails += 1

    terms = ec.search_terms("安装失败 闪退")
    qcase("中文症状能二元切词", "失败" in terms and "安装" in terms,
          f"实得 {terms}")
    latin = ec.search_terms("adb install 失败")
    qcase("英文术语整词保留", "adb" in latin and "install" in latin,
          f"实得 {latin}")

    by_id = {c.get("id"): c for _, c in ec.load_cards()}
    scope_card = by_id.get("powershell-script-scope-does-not-follow-callstack")
    if not scope_card:
        qcase("作用域卡存在（检索用例的前提）", False, "卡片文件缺失")
    else:
        hay = ec.card_search_text(scope_card)
        hit = sum(1 for t in ec.search_terms("变量读不到") if t in hay)
        qcase("「变量读不到」能命中作用域卡", hit > 0,
              f"一个症状词都没命中；卡片语料前 80 字={hay[:80]}")
        # 反例：键名一旦进入语料，「stops 条件」这类查询就会命中每一张卡
        qcase("scope 键名不进入检索语料",
              "applieswhen" not in hay and "stopswhen" not in hay,
              "键名泄漏会让无关查询命中全部卡（2026-10-11 实测 4/4）")

    print()
    if fails:
        print(f"结论：{fails} 项失败")
        return 1
    print("结论：全部通过 —— 正例过关，且每一类坏卡都被反例控制组证明会转红。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())