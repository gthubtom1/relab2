#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""经验卡（experience card）工具：生成 / 检索 / 校验 / 生成症状索引。

## 为什么存在

`skills/web-protocol-reverse/references/contract/experience-card-schema.md`
定义了一整套经验卡 schema（晋级门、消费规则、退役判据），但那张文档自己也
承认：晋级目标目录 `references/experience-cards/` **在本包尚未建立**。
本脚本把那一环补上，并且**不改动**那张 schema —— 它仍然是唯一判据，本脚本
只负责机械执行它。

## 经验卡和 field-journal 的分工

| | 经验卡（本目录） | field-journal |
|---|---|---|
| 形态 | **结构化 JSON**，可被程序消费 | 散文 Markdown |
| 内容 | 一条可判定的**规则**：什么条件下、做什么、怎么算成功 | 一次任务的现场：走了哪些弯路 |
| 数量 | 少（几十张），每张都有 fixture + oracle | 多（按任务累积） |
| 消费方 | `search` 命令，agent 在动手前先查 | 人读的回顾 |

**不要把两者合并成一个目录**：现场是发散的，规则是可判定的。混在一起时，
规则会被现场叙述淹没，最后谁也读不到。

## 检索入口

`INDEX.md` 由 `stamp` 自动重建，不手工维护（手工维护必漂移）。
检索用 `search` —— 它按症状词命中，比读 INDEX 更准。

## 退出码

0 ok / 1 有校验失败 / 2 用法或环境错误。
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # .../skillpack
CARDS = ROOT / "skills" / "experience-cards"
FIXTURES = CARDS / "fixtures"
INDEX = CARDS / "INDEX.md"
SCHEMA_DOC = ROOT / "skills" / "web-protocol-reverse" / "references" / "contract" / "experience-card-schema.md"
PLACEHOLDER = "0" * 64

sys.path.insert(0, str(ROOT / "skills" / "scripts"))
try:  # 复用仓库里已有的秘密形态正则，不另立第二套
    import verify_repository_security as _sec  # type: ignore
    SECRET_PATTERNS = dict(_sec.SECRET_PATTERNS)
except Exception:  # pragma: no cover - 只在缺模块时退化
    SECRET_PATTERNS = {
        "aws-access-key-id": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
        "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
        "private-key-block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    }

TOP_FIELDS = ("id", "status", "title", "invariant", "scope", "reproductions",
              "fixture", "oracles", "firstDivergence", "decision", "validation")
ID_OK = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

REPO = ROOT.parent          # 仓库根（.github/workflows 所在层）

CARDS = ROOT / "skills" / "experience-cards"
FIXTURES = CARDS / "fixtures"
INDEX = CARDS / "INDEX.md"
SCHEMA_DOC = (ROOT / "skills" / "web-protocol-reverse" / "references"
              / "contract" / "experience-card-schema.md")
PLACEHOLDER = "0" * 64

# 反例控制组要在临时目录上跑 validate（见 test-experience-card.py）。
# 环境变量是唯一的注入点 —— 不加它就只能改脚本默认行为，那会让门禁与被测对象
# 共享状态，判断就不可靠了。必须放在所有常量之后，覆盖才生效。
if os.environ.get("EXPERIENCE_CARD_DIR"):
    CARDS = Path(os.environ["EXPERIENCE_CARD_DIR"]).resolve()


def resolve_ref(rel: str) -> Path:
    """卡里的路径一律**仓库根相对**（与 git 路径、门禁输出保持一致）。

    早先按 ROOT（skillpack/）解析，写成 "skillpack/skills/..." 的路径会拼成
    skillpack/skillpack/skills/... —— fixture 明明存在却报「不存在」。
    """
    return (REPO / rel).resolve()


# ── 基础设施 ──────────────────────────────────────────────────────
def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_cards() -> list[tuple[Path, dict]]:
    out = []
    if not CARDS.is_dir():
        return out
    for p in sorted(CARDS.glob("*.json")):
        try:
            out.append((p, json.loads(p.read_text(encoding="utf-8-sig"))))
        except Exception as exc:                     # 坏 JSON 要报，不能静默跳过
            print(f"BADJSON {p.name}: {exc}", file=sys.stderr)
    return out


def dump_errors(card_path: Path, errs: list[str]) -> list[str]:
    return [f"{card_path.name}: {e}" for e in errs]


def validate_card(card_path: Path, card: dict) -> list[str]:
    """按 experience-card-schema.md 的晋级门逐条检查一张 promoted 卡。

    判据只有一处权威来源：schema 文档 A 节列了 7 条晋级门，C 节是无秘密检查。
    这里不重新发明判据，只把它们变成可执行断言。
    """
    errs: list[str] = []
    for f in TOP_FIELDS:
        if f not in card:
            errs.append(f"缺字段 {f}")

    cid = card.get("id")
    if not isinstance(cid, str) or not ID_OK.match(cid):
        errs.append(f"id 不合法（要求小写连字符 slug）: {cid!r}")
    elif card_path.stem != cid:
        errs.append(f"文件名({card_path.stem}) 与 id({cid}) 不一致")

    if card.get("status") != "promoted":
        errs.append(f"status 必须是 promoted（本目录只收已晋级卡），实得 {card.get('status')!r}")

    # 条 1：>= 2 次真正独立的复现
    repros = card.get("reproductions") or []
    if not isinstance(repros, list) or len(repros) < 2:
        errs.append(f"晋级门 1：需要 >= 2 次独立复现，实得 {len(repros) if isinstance(repros, list) else '非列表'}")
    else:
        fps = [r.get("jobFingerprint") for r in repros if isinstance(r, dict)]
        for r in repros:
            if not isinstance(r, dict):
                errs.append("reproductions 项必须是对象")
                continue
            for k in ("jobFingerprint", "observedAt", "artifactSha256"):
                if not r.get(k):
                    errs.append(f"复现条目缺 {k}")
        if len(set(fps)) != len(fps):
            errs.append("晋级门 1：存在重复的 jobFingerprint（那不是独立复现）")
        if len(set(fps)) == 1:
            errs.append("晋级门 1：所有复现同指纹")

    # 条 2：fixture + 哈希
    fx = card.get("fixture")
    if not isinstance(fx, dict):
        errs.append("晋级门 2：fixture 必须是对象")
    else:
        if not fx.get("secretFree") is True:
            errs.append("晋级门 2/C：fixture.secretFree 必须为 true（且需核对过，不是照抄）")
        rel = fx.get("path")
        if not rel:
            errs.append("晋级门 2：fixture.path 为空")
        else:
            target = resolve_ref(rel)
            if not target.exists():
                errs.append(f"晋级门 2：fixture 不存在 {rel}（编造路径是本 schema 明令禁止的）")
            else:
                real = sha256_of(target)
                want = fx.get("sha256")
                if want == PLACEHOLDER:
                    errs.append(f"晋级门 2：fixture.sha256 仍是占位符，跑 stamp 填真实哈希")
                elif want != real:
                    errs.append(f"晋级门 2：fixture.sha256 与实际不符（{want} != {real}）")

    # 条 3/4：正负 oracle 都必须是外部可观测的判据
    oracles = card.get("oracles") or {}
    if not isinstance(oracles, dict):
        errs.append("oracles 必须是对象")
    else:
        for k in ("positive", "negative"):
            if not oracles.get(k):
                errs.append(f"晋级门 {'3' if k == 'positive' else '4'}：oracles.{k} 为空")

    # 条 5：首个分歧
    if not isinstance(card.get("firstDivergence"), dict):
        errs.append("晋级门 5：firstDivergence 必须是对象")
    elif not card["firstDivergence"].get("stage"):
        errs.append("晋级门 5：firstDivergence.stage 为空")

    # 条 6：适用与停止边界
    sc = card.get("scope") or {}
    if not isinstance(sc, dict):
        errs.append("scope 必须是对象")
    else:
        for k in ("appliesWhen", "stopsWhen"):
            v = sc.get(k)
            if not isinstance(v, list) or not v:
                errs.append(f"晋级门 6：scope.{k} 必须是非空数组")

    # 条 7：本地验证命令
    val = card.get("validation") or {}
    if not isinstance(val, dict):
        errs.append("validation 必须是对象")
    else:
        if not val.get("command"):
            errs.append("晋级门 7：validation.command 为空（编造验证命令是明令禁止的）")
        if not val.get("lastVerifiedAt"):
            errs.append("晋级门 7：validation.lastVerifiedAt 为空")

    # 消费侧信息：symptoms 是检索入口，必须有，否则这张卡搜不到
    if not card.get("symptoms"):
        errs.append("缺 symptoms：这是本仓库唯一的机器检索入口")

    # 无秘密：卡全文不得含秘密形态
    text = json.dumps(card, ensure_ascii=False)
    for label, pat in SECRET_PATTERNS.items():
        if pat.search(text):
            errs.append(f"无秘密检查：卡内命中 {label}")
    return errs


# ── 命令 ──────────────────────────────────────────────────────────
def cmd_validate(args: argparse.Namespace) -> int:
    cards = load_cards()
    if not cards:
        print(f"经验卡目录为空或不存在：{CARDS}")
        return 1
    if not SCHEMA_DOC.exists():
        print(f"schema 判据来源缺失：{SCHEMA_DOC}", file=sys.stderr)
        return 2
    all_errs: list[str] = []
    for p, c in cards:
        all_errs.extend(dump_errors(p, validate_card(p, c)))
    print(f"经验卡 {len(cards)} 张，判据来源 {SCHEMA_DOC.name}")
    for e in all_errs:
        print("  FAIL " + e)
    if all_errs:
        print(f"结论：{len(all_errs)} 项校验失败")
        return 1
    print("结论：全部通过（晋级门 7 条 + 无秘密检查）")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    cards = load_cards()
    q = args.query.strip().lower()
    terms = [t for t in re.split(r"[\s,，/]+", q) if t]
    hits = []
    for p, c in cards:
        hay = " ".join([
            c.get("title", ""), c.get("invariant", ""),
            " ".join(c.get("symptoms", []) or []),
            json.dumps(c.get("scope", {}), ensure_ascii=False),
            (c.get("links") or {}).get("skill", ""),
        ]).lower()
        score = sum(1 for t in terms if t in hay)
        if score:
            hits.append((score, p, c))
    if not hits:
        print(f"没有经验卡命中「{args.query}」。")
        print("这张表是活的：新症状没被收录时，用 `new` 建一张候选，晋级门见 "
              f"{SCHEMA_DOC.relative_to(ROOT).as_posix()}。")
        return 0
    hits.sort(key=lambda x: -x[0])
    limit = args.limit if args.limit > 0 else len(hits)
    print(f"命中 {len(hits)} 张经验卡（按症状词匹配，显示前 {limit}）")
    for score, p, c in hits[:limit]:
        print()
        print(f"[{c.get('id')}]  {c.get('title')}")
        print(f"  文件: {p.relative_to(ROOT).as_posix()}")
        print(f"  技能: {(c.get('links') or {}).get('skill', '?')}   命中词: {score}")
        print(f"  规则: {c.get('invariant', '')[:150]}")
        print(f"  先读: {(c.get('links') or {}).get('script', '-')}")
        aw = (c.get("scope") or {}).get("appliesWhen") or []
        if aw:
            print(f"  前提: {aw[0]}")
    return 0


def cmd_stamp(args: argparse.Namespace) -> int:
    """回填 fixture 真实哈希 + validation.lastVerifiedAt，并重建 INDEX.md。"""
    changed = 0
    for p, c in load_cards():
        dirty = False
        fx = c.get("fixture")
        if isinstance(fx, dict):
            rel = fx.get("path")
            if rel:
                target = resolve_ref(rel)
                if target.exists():
                    real = sha256_of(target)
                    if fx.get("sha256") != real:
                        fx["sha256"] = real
                        dirty = True
        val = c.get("validation")
        if isinstance(val, dict) and args.today:
            if val.get("lastVerifiedAt") != args.today:
                val["lastVerifiedAt"] = args.today
                dirty = True
        if dirty:
            p.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed += 1
    if changed:
        print(f"回填 {changed} 张卡的 fixture 哈希 / 验证日期")
    build_index()
    print(f"索引已重建：{INDEX}")
    return 0


def build_index() -> None:
    """重建症状索引。手工维护索引必漂移，所以这里只从卡里生成。"""
    cards = load_cards()
    lines = [
        "# 经验卡症状索引（自动生成，勿手工编辑）",
        "",
        "> 由 `skills/scripts/experience-card.py stamp` 重建。手工改这里会在下次 stamp 被覆盖。",
        "> 机器检索直接用 `python skills/scripts/experience-card.py search \"<症状>\"`，比读本表准。",
        "",
        "## 怎么用",
        "",
        "1. 动手前先 `search` 你的症状；命中就读那张卡的 `invariant` 与 `decision.action`。",
        "2. **对照 `scope.appliesWhen` 逐条查**——少一条就停，别硬套。",
        "3. **出现任一 `scope.stopsWhen` 条件就停用这张卡**，不要因为「以前这么干过」就继续。",
        "4. 历史卡**不替代**当前目标的实测证据；它只替你省掉从零摸索。",
        "5. 没命中不是「没有经验」，而是可以沉淀：用 `new` 建一张候选，晋级门见",
        "   `skills/web-protocol-reverse/references/contract/experience-card-schema.md`。",
        "",
        f"## 卡片（共 {len(cards)} 张）",
        "",
        "| 症状 / 信号（我看到了什么） | 卡 | 规则 | 技能 |",
        "|---|---|---|---|",
    ]
    rows = []
    for p, c in cards:
        for s in (c.get("symptoms") or ["-"])[:2]:
            rows.append((s, c.get("id", "-"), c.get("invariant", "-"),
                         (c.get("links") or {}).get("skill", "-"), p))
    rows.sort(key=lambda r: r[0])
    for sym, cid, inv, skill, p in rows:
        short = inv if len(inv) <= 90 else inv[:88] + "…"
        lines.append(f"| {sym} | [{cid}]({p.name}) | {short} | `{skill}` |")
    lines += [
        "",
        "## 分工（别混）",
        "",
        "| | 经验卡（本目录） | field-journal |",
        "|---|---|---|",
        "| 形态 | 结构化 JSON，可被程序消费 | 散文 Markdown |",
        "| 内容 | 一条**可判定**的规则 | 一次任务的**现场** |",
        "| 数量 | 少（几十张），每张都有 fixture + 正负 oracle | 多（按任务累积） |",
        "| 谁读 | `experience-card.py search` | 人读的回顾 |",
        "",
        "> 经验卡的判据（晋级门 7 条 / 消费规则 / 退役判据）唯一来源：",
        "> `skills/web-protocol-reverse/references/contract/experience-card-schema.md`。",
        "> 本目录只放**已晋级**的卡；候选留在任务本地。",
    ]
    INDEX.write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_new(args: argparse.Namespace) -> int:
    cid = args.id
    if not ID_OK.match(cid):
        print(f"id 必须是小写连字符 slug：{cid}", file=sys.stderr)
        return 2
    target = CARDS / f"{cid}.json"
    if target.exists() and not args.force:
        print(f"已存在：{target}（要覆盖加 --force）", file=sys.stderr)
        return 2
    CARDS.mkdir(parents=True, exist_ok=True)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    now = args.today or date.today().isoformat()
    card = {
        "schemaVersion": 1,
        "id": cid,
        "status": "promoted" if args.promoted else "candidate",
        "title": args.title or "",
        "invariant": args.invariant or "",
        "scope": {"family": args.family or "", "boundary": "",
                  "appliesWhen": [], "stopsWhen": []},
        "reproductions": [],
        "fixture": {"path": "", "sha256": PLACEHOLDER,
                    "generator": None, "secretFree": True},
        "oracles": {"positive": "", "negative": ""},
        "firstDivergence": {"stage": "", "path": "", "kind": ""},
        "decision": {"preferredRoute": "", "action": "", "fallback": ""},
        "validation": {"lastVerifiedAt": "", "command": ""},
        "links": {"skill": args.skill or "", "script": "",
                  "journal": "", "derivation":
                  "web-protocol-reverse/references/contract/experience-card-schema.md"},
        "symptoms": args.symptom or [],
    }
    target.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已生成 {target}")
    if not args.promoted:
        print("这是 candidate：不满足晋级门不能被当经验消费。"
              f"晋级门见 {SCHEMA_DOC.relative_to(ROOT).as_posix()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="经验卡：生成 / 检索 / 校验 / 索引")
    ap.add_argument("--today", default=None,
                    help="把 validation.lastVerifiedAt 回填成这个日期（默认今天）")
    sub = ap.add_subparsers(dest="cmd")

    s = sub.add_parser("new", help="建一张卡")
    s.add_argument("id")
    s.add_argument("--title")
    s.add_argument("--invariant")
    s.add_argument("--family")
    s.add_argument("--skill")
    s.add_argument("--symptom", action="append")
    s.add_argument("--promoted", action="store_true",
                   help="直接按 promoted 建（默认 candidate，避免没证据就被当经验消费）")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_new)

    s = sub.add_parser("search", help="按症状检索经验卡")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=0)
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("validate", help="按晋级门逐条校验")
    s.set_defaults(func=cmd_validate)

    s = sub.add_parser("stamp", help="回填 fixture 哈希并重建 INDEX.md")
    s.set_defaults(func=cmd_stamp)

    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())