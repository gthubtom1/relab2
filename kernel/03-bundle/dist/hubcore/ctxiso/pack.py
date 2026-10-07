"""上下文包：把"这一轮要看到什么"变成一个有预算、可解释的集合。

原则落地：
  · 当前任务优先     —— 意图在包首，占最大权重。
  · 保存≠读取       —— 长期资料只以索引行出现，正文一律不出现。
  · 知道存在≠读内容 —— 索引行是路径/类型/大小/一行用途，不是正文。
  · 总量有上限      —— pack_budget_bytes 硬顶，超了截断并说明截了什么。
  · 不重算真相      —— 阶段/停点/门禁的权威仍是 state status，包里给指针。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import paths, store


def _utf8_len(s: str) -> int:
    return len(s.encode("utf-8"))


def _read_contract(product: Path) -> dict:
    f = paths.hub_dir(product) / "contract.json"
    if not f.is_file():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _line(head: str, body: str = "") -> str:
    return (f"{head}  {body}").rstrip()


def build(product: Path, *, intent: str, stage: str = "", budget: int = 0) -> dict:
    cfg = paths.load_config()
    budget = budget or int(cfg["pack_budget_bytes"])
    max_gap = int(cfg["pack_max_gap_items"])
    max_rows = int(cfg["pack_max_index_rows"])

    if paths.env_off(product):
        return {"ok": True, "off": True, "text": "# ctxiso 关闭（CTXISO_OFF=1）：本包为空。",
                "bytes": 0, "budget": budget}

    con = store.connect(product)
    try:
        doc_rows = store.docs(con, limit=500)
        kinds = store.doc_kinds(con)
        total_docs = sum(kinds.values())
        total_doc_bytes = sum(r["size"] for r in con.execute("SELECT size FROM doc"))
        indexed_events = con.execute("SELECT COUNT(*) c FROM ledger").fetchone()["c"]

        out: list[str] = []
        omitted: list[str] = []

        out.append("# 当前任务包（ctxiso 0.1.0）")
        out.append("")
        out.append(_line("【任务意图】", intent or "(未声明意图——先说清这轮要干什么)"))
        if stage:
            out.append(_line("【阶段】", stage))

        contract = _read_contract(product)
        mission = contract.get("mission") or {}
        if mission:
            out.append(_line("【本项目目标】", str(mission.get("goal", ""))[:300]))
            out.append(_line("【可观察成功】", str(mission.get("success", ""))[:300]))

        # ---- 本阶段当前为 fail 的探针（只取每个检查的最新一次结果）
        # 实测踩到的坑：按 result='fail' 过滤，会把"已经修好、只是历史上失败过"
        # 的检查当成当前阻塞。必须先按 ident 取最新，再看最新那次的结果。
        phase = stage or ""
        if phase:
            rows = con.execute(
                "SELECT ident, summary, result, ts, seq FROM ledger"
                " WHERE kind='physical_probe' AND phase=? ORDER BY seq DESC",
                (phase,)).fetchall()
            latest: dict = {}
            for r in rows:                      # rows 已按 seq DESC 排好
                latest.setdefault(r["ident"] or "?", r)
            failing = [r for r in latest.values() if r["result"] == "fail"]
            passing = len(latest) - len(failing)
            out.append("")
            if failing:
                out.append(f"【本阶段当前为 fail 的探针检查】（{len(failing)} 个 fail / "
                           f"共 {len(latest)} 个检查；已通过的 {passing} 个不再列）")
                for r in failing[:max_gap]:
                    out.append("- " + _line(r["ident"] or "?", (r["summary"] or "")[-90:]))
                if len(failing) > max_gap:
                    omitted.append(f"fail 检查还有 {len(failing) - max_gap} 个未列出"
                                   f"（全量：`ctxiso query --kind physical_probe --phase {phase}`）")
            else:
                out.append(f"【本阶段探针检查】（{len(latest)} 个检查，最新一次都没有 fail）")

        # ---- 长期资料索引（只有元数据）
        if doc_rows:
            out.append("")
            out.append(f"【长期资料索引】（共 {total_docs} 份 / {total_doc_bytes} 字节；"
                       f"下面只列元数据，正文未读）")
            for kind in ("current", "project", "history"):
                rows = [r for r in doc_rows if r["kind"] == kind]
                # 总数必须来自 GROUP BY 的真实计数，不能拿"截断后还剩几行"当总数——
                # 那样会少报（2000 份说成 490 份），主人就不知道历史到底有多少。
                real_total = int(kinds.get(kind, 0))
                if not real_total:
                    continue
                out.append(f"- {kind}（共 {real_total} 份；下面列前 {min(max_rows, real_total)}）")
                for r in rows[:max_rows]:
                    out.append("    - %s｜%d B｜%d 行｜%s" % (
                        r["path"], r["size"], r["lines"] or 0, r["one_line"] or ""))
                if real_total > max_rows:
                    omitted.append(f"{kind} 资料还有 {real_total - max_rows} 份未列"
                                   f"（全量：`ctxiso archive list --kind {kind}`，"
                                   f"那是索引不是正文）")

        # ---- 明确划出"不在包里"的东西
        out.append("")
        out.append("【本包刻意不含】")
        out.append("- 历史事件正文、探针收据正文、observed/assertions 原文")
        out.append("- 长期资料正文（OWNER-SPEECH / CHANGES / 旧版本资料）")
        out.append("- 任何 Skill 内容")
        out.append("理由：保存不等于读取；要读必须自己提出读取意图。")
        # 底线随包一起回来（约 90 B，仍在 6000 B 预算内）。
        # 之前这里只有"保存≠读取"一条，证据分级和点头不会每轮出现——
        # 那是 T5 复核时拆掉的 overclaim，补在这里。
        out.append("【底线·每轮都在】文字报告不是物理证据，探针没过＝没完成。"
                   "点头只认主人本人。")

        text = "\n".join(out) + "\n"
        if _utf8_len(text) > budget:
            # 硬顶：先砍索引行，再砍说明段，保留任务意图。
            text = _shrink(out, budget)
            omitted.append("已按预算截断")
        return {
            "ok": True, "text": text, "bytes": _utf8_len(text), "budget": budget,
            "indexed_events": indexed_events, "doc_count": total_docs,
            "doc_bytes": total_doc_bytes, "omitted": omitted,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    finally:
        con.close()


def _shrink(lines: list[str], budget: int) -> str:
    head = [l for l in lines if l.startswith("#") or l.startswith("【任务意图】")
            or l.startswith("【阶段】") or l.startswith("【本项目目标】")
            or l.startswith("【可观察成功】")]
    tail_idx = next((i for i, l in enumerate(lines) if l.startswith("【本包刻意不含】")), len(lines))
    tail = lines[tail_idx:]
    body = [l for l in lines if l not in head and l not in tail]
    out = head + body + tail
    text = "\n".join(out) + "\n"
    while _utf8_len(text) > budget and body:
        body.pop()
        text = "\n".join(head + body + tail) + "\n"
    if _utf8_len(text) > budget:
        text = ("\n".join(head)
                + "\n（预算已用尽；索引段与说明段已折叠，用 ctxiso archive list 按需取。）\n")
    return text
