#!/usr/bin/env python3
"""check-route-evidence.py —— 路由证据完备性检查（R57 的真实现）。

为什么需要它：
    `work/_benchmark/routes/R*/result.json` 是本仓 63 条路由的唯一验收记录。
    但「status=pass」曾经可以在**没有任何证据文件、observed 只有 7 个字符**的情况下写出来
    —— 门只查字段存在，不查证据是否真的落地。于是 32 个 pass 里混进了 14 个「写文档跑断言」
    得来的假 pass，覆盖率的数字是真的、结论是假的。

它查什么（每条都是可执行判据，不是风格建议）：
    E1  result.json 存在且含 9 个必需 key
    E2  status ∈ {pass, partial, boundary}
    E3  route 字段与所在目录名一致（防止复制粘贴串号）
    E4  pass          -> observed ≥ --min-observed（默认 80）字符
    E5  pass          -> evidence_files 非空，且**列出的每个文件真实存在**
    E6  partial/boundary -> blocked_by ≥ 40 字符（必须贴真实失败，不是「需要 X」）
    E7  evidence_files 里的路径不得越出该路由目录（防 ../ 逃逸）
    E8  observed 不得为占位式空话（"见 xxx.md" / "ok" / "已闭环" 这类单独成句的）

用法：
    python skills/scripts/check-route-evidence.py --routes work/_benchmark/routes
    ... --json            机器可读
    ... --min-observed 120
    ... --strict          E8 也当违规（默认只报 warn）
退出码：0 通过 / 20 有违规 / 2 用法错误
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

REQUIRED_KEYS = {"route", "label", "status", "sample", "criterion",
                 "method", "observed", "blocked_by", "evidence_files"}
ALLOWED_STATUS = {"pass", "partial", "boundary"}
MIN_BLOCKED = 40

# observed 里出现这些**单独成句**就说明它没写实测结果，只是指向另一份文档
PLACEHOLDER_PATTERNS = (
    "见 ", "见见", "详见", "参考 ", "见文档", "同上", "略",
    "ok", "OK", "已闭环", "已完成", "待补充", "TBD",
)


# 以这些短语**开头**的 observed 一定是"指向另一份文档"，无论多长 ——
# 真实测结果不会这样开头（它会先给事实，再（可选）指向证据文件）。
_LEADING_PLACEHOLDERS = ("见 ", "详见", "参考 ", "参见", "同上", "略", "tbd", "todo", "待补")


def _is_placeholder(observed: str) -> bool:
    s = (observed or "").strip()
    if not s:
        return True
    low = s.lower()
    for p in _LEADING_PLACEHOLDERS:
        if low.startswith(p.lower()):
            return True
    if len(s) <= 24:
        for p in PLACEHOLDER_PATTERNS:
            if low == p.lower():
                return True
    return False


def check_one(route_dir: str, min_observed: int, strict: bool):
    """返回 (route_name, problems, warnings)。problems 非空即违规。"""
    name = os.path.basename(route_dir.rstrip("\\/"))
    path = os.path.join(route_dir, "result.json")
    problems, warns = [], []

    if not os.path.isfile(path):
        return name, ["E1 result.json 不存在: %s" % path], warns
    try:
        with io.open(path, encoding="utf-8") as f:
            d = json.load(f)
    except ValueError as exc:
        return name, ["E1 result.json 不是合法 JSON: %s" % exc], warns
    if not isinstance(d, dict):
        return name, ["E1 result.json 顶层不是对象"], warns

    miss = REQUIRED_KEYS - set(d)
    if miss:
        problems.append("E1 缺必需 key: %s" % sorted(miss))
        return name, problems, warns

    status = d.get("status")
    if status not in ALLOWED_STATUS:
        problems.append("E2 status 非法: %r" % (status,))

    if d.get("route") != name:
        problems.append("E3 route 字段(%r) 与目录名(%r) 不一致" % (d.get("route"), name))

    observed = d.get("observed") or ""
    if status == "pass":
        if len(observed) < min_observed:
            problems.append("E4 pass 但 observed 只有 %d 字符 (< %d)" % (len(observed), min_observed))
        ev = d.get("evidence_files") or []
        if not ev:
            problems.append("E5 pass 但 evidence_files 为空（没有任何落地证据）")
        for rel in ev:
            if not isinstance(rel, str) or not rel:
                problems.append("E5 evidence_files 含非字符串项: %r" % (rel,))
                continue
            full = os.path.normpath(os.path.join(route_dir, rel))
            if not full.startswith(os.path.normpath(route_dir) + os.sep):
                problems.append("E7 evidence_files 越出路由目录: %r" % rel)
                continue
            if not os.path.exists(full):
                problems.append("E5 evidence_files 列出的文件不存在: %r" % rel)
    elif status in ("partial", "boundary"):
        blocked = d.get("blocked_by") or ""
        if len(blocked) < MIN_BLOCKED:
            problems.append("E6 %s 但 blocked_by 只有 %d 字符 (< %d)"
                            % (status, len(blocked), MIN_BLOCKED))

    if _is_placeholder(observed):
        msg = "E8 observed 像占位式空话: %r" % observed[:60]
        (problems if strict else warns).append(msg)

    return name, problems, warns


def iter_route_dirs(routes_root: str):
    for entry in sorted(os.listdir(routes_root)):
        full = os.path.join(routes_root, entry)
        if os.path.isdir(full) and entry.upper().startswith("R"):
            yield full


def main(argv=None):
    ap = argparse.ArgumentParser(description="路由证据完备性检查")
    ap.add_argument("--routes", required=True, help="routes 根目录（含 R0..R64）")
    ap.add_argument("--min-observed", type=int, default=80)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="E8 也当违规")
    ap.add_argument("--only", default="", help="只查这些路由，逗号分隔（如 R22,R35）")
    ap.add_argument("--expect-routes", default="",
                    help="routing.json 路径：给了就核对「routes 键集合」与「实际存在的路由目录」"
                         "是否一致（缺目录/多目录都报 E0）")
    a = ap.parse_args(argv)

    if not os.path.isdir(a.routes):
        print("用法错误：--routes 不是目录: %s" % a.routes, file=sys.stderr)
        return 2

    only = {x.strip().upper() for x in a.only.split(",") if x.strip()}
    results = []
    for rd in iter_route_dirs(a.routes):
        name = os.path.basename(rd)
        if only and name.upper() not in only:
            continue
        n, probs, warns = check_one(rd, a.min_observed, a.strict)
        results.append({"route": n, "problems": probs, "warnings": warns})

    # ★ E0：与 routing.json 的 routes 键做集合核对。
    #   不加这一步时，删掉一条 result.json 目录只会让 checked 从 63 变 62，
    #   输出里**看不出少了哪条** —— 「覆盖 63 条」这个结论就不可信了。
    missing_dirs, extra_dirs = [], []
    if a.expect_routes:
        try:
            with io.open(a.expect_routes, encoding="utf-8") as f:
                cfg = json.load(f)
            expected = set(cfg.get("routes") or {})
        except (OSError, ValueError) as exc:
            print("用法错误：--expect-routes 读不了: %s" % exc, file=sys.stderr)
            return 2
        seen = {r["route"].upper() for r in results}
        expected_u = {x.upper() for x in expected}
        missing_dirs = sorted(expected_u - seen, key=lambda s: (len(s), s))
        extra_dirs = sorted(seen - expected_u, key=lambda s: (len(s), s))
        for name in missing_dirs:
            results.append({"route": name,
                            "problems": ["E0 routing.json 声明了 %s 但没有对应的路由目录/result.json" % name],
                            "warnings": []})
        for name in extra_dirs:
            results.append({"route": name,
                            "problems": ["E0 路由目录 %s 不在 routing.json 的 routes 里" % name],
                            "warnings": []})

    total = len(results)
    bad = [r for r in results if r["problems"]]
    warn = [r for r in results if r["warnings"]]

    # ★ 修：--only 里只要有一个路由名对不上真实目录，就是**用法错误**，不是「通过」。
    #   旧行为是静默忽略不存在的名字，于是 `--only R999` 得到 checked=0 / rc=0，
    #   与「真的全部通过」完全不可区分 —— CI 里任何按子集校验的用法都会被骗成绿。
    if only:
        found = {r["route"].upper() for r in results}
        unknown = sorted(only - found)
        if unknown:
            print("用法错误：--only 指定了不存在的路由: %s（routes_root=%s 下找不到）"
                  % (",".join(unknown), a.routes), file=sys.stderr)
            if a.json:
                print(json.dumps({"routes_root": a.routes, "error": "unknown_routes",
                                  "unknown": unknown, "checked": total},
                                 ensure_ascii=False, indent=2))
            return 2

    if a.json:
        print(json.dumps({"routes_root": a.routes,
                          "expect_routes": a.expect_routes or None,
                          "missing_dirs": missing_dirs, "extra_dirs": extra_dirs,
                          "checked": total,
                          "violations": len(bad), "warnings": len(warn),
                          "results": results}, ensure_ascii=False, indent=2))
    else:
        print("check-route-evidence: routes_root=%s checked=%d violations=%d warnings=%d"
              % (a.routes, total, len(bad), len(warn)))
        for r in bad:
            for p in r["problems"]:
                print("  [VIOLATION] %s %s" % (r["route"], p))
        for r in warn:
            for w in r["warnings"]:
                print("  [warn]      %s %s" % (r["route"], w))
        if not total:
            print("  (no route dirs found under %s)" % a.routes)

    return 20 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
