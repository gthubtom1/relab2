#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读校验器：中文口语 -> 技能主题映射层。
只读：除 stdout/stderr 外不写任何文件，不改 routing.json / registry.json / 社区路由。
退出码（规范 4.7）：0 通过 | 20 阻断（校验项失败） | 21 缺输入（文件缺失/参数错误） | 30 失败（异常崩溃）。
仅标准库，无网络。
用法：
  python scripts/verify-nl-map.py [--map PATH] [--repo-root PATH] [--work-dir PATH]
默认相对本脚本定位：../skills/config/natural-language-map.json、仓库根、work/（与仓库根同级的 skills-hub/work）。
"""
import ast
import glob
import json
import os
import re
import sys

ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
# 整条 surface 就是无区分度词 -> 阻断（子串出现不算，如“安全评估”为合法领域词）
GENERIC_ONLY = {
    "测试", "分析", "工具", "检测", "检查", "扫描", "评估", "验证",
    "研究", "学习", "使用", "帮助", "问题", "方法", "教程", "攻略",
    "新手", "入门", "看看", "搞", "弄", "整", "test", "tool",
}

def fail_usage(msg):
    print("USAGE ERROR: " + msg, file=sys.stderr)
    return 21

def load_json(path, label, problems):
    if not os.path.isfile(path):
        print("MISSING INPUT: %s not found: %s" % (label, path), file=sys.stderr)
        return None, False
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh), True
    except (OSError, ValueError) as exc:
        print("UNREADABLE INPUT: %s %s: %s" % (label, path, exc), file=sys.stderr)
        return None, False

def collect_hint_texts(work_dir):
    """收集 work/hitrate-* 下全部压测 hint 文本（只读）。"""
    texts = []
    if not work_dir or not os.path.isdir(work_dir):
        return texts, []
    searched = []
    for name in sorted(os.listdir(work_dir)):
        if not name.startswith("hitrate-"):
            continue
        base = os.path.join(work_dir, name)
        for pat in ("hints*.json", "hints*.py", "base_hints.json",
                    "specials.json", "cases.json", "probe-*.json"):
            for path in sorted(glob.glob(os.path.join(base, pat))):
                searched.append(path)
                try:
                    with open(path, encoding="utf-8-sig") as fh:
                        raw = fh.read()
                except (OSError, ValueError, UnicodeError):
                    try:
                        with open(path, encoding="utf-16") as fh:
                            raw = fh.read()
                    except (OSError, ValueError, UnicodeError):
                        continue
                if path.endswith(".json"):
                    try:
                        data = json.loads(raw)
                    except ValueError:
                        continue
                    stack = [data]
                    while stack:
                        cur = stack.pop()
                        if isinstance(cur, dict):
                            if isinstance(cur.get("hint"), str):
                                texts.append(cur["hint"])
                            stack.extend(cur.values())
                        elif isinstance(cur, list):
                            stack.extend(cur)
                elif path.endswith(".py"):
                    try:
                        tree = ast.parse(raw)
                    except SyntaxError:
                        continue
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Constant) and isinstance(node.value, str):
                            texts.append(node.value)
    return texts, searched

def cjk_windows(text, n=6):
    """文本中全部长度>=n 的连续汉字串的 n 字窗口集合。"""
    out = set()
    for m in re.finditer(r"[\u4e00-\u9fff]{%d,}" % n, text):
        run = m.group(0)
        for i in range(len(run) - n + 1):
            out.add(run[i:i + n])
    return out

def main(argv):
    map_path, repo_root, work_dir = None, None, None
    i = 0
    while i < len(argv):
        if argv[i] == "--map" and i + 1 < len(argv):
            map_path = argv[i + 1]; i += 2
        elif argv[i] == "--repo-root" and i + 1 < len(argv):
            repo_root = argv[i + 1]; i += 2
        elif argv[i] == "--work-dir" and i + 1 < len(argv):
            work_dir = argv[i + 1]; i += 2
        else:
            return fail_usage("unknown arg '%s'. see module docstring." % argv[i])
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if repo_root is None:
        repo_root = os.path.dirname(script_dir)  # scripts/ 上一级即仓库根
    if map_path is None:
        map_path = os.path.join(repo_root, "skills", "config", "natural-language-map.json")
    if work_dir is None:
        work_dir = os.path.join(os.path.dirname(repo_root), "work")
    routing_path = os.path.join(repo_root, "skills", "config", "routing.json")
    registry_path = os.path.join(repo_root, "skills", "community", "registry.json")
    skills_dir = os.path.join(repo_root, "skills")

    nlmap, ok = load_json(map_path, "nl-map", None)
    routing, ok2 = load_json(routing_path, "routing.json", None)
    registry, ok3 = load_json(registry_path, "registry.json", None)
    if nlmap is None or routing is None or registry is None:
        return 21

    problems = []

    # --- 顶层结构 ---
    if nlmap.get("schemaVersion") != 1:
        problems.append("schemaVersion 必须为 1，实际 %r" % (nlmap.get("schemaVersion"),))
    entries = nlmap.get("entries")
    if not isinstance(entries, list) or not entries:
        problems.append("entries 必须是非空数组")
        entries = []

    # --- 目标全集（routing.json + registry.json + canonical 目录）---
    valid = set()
    routes = routing.get("routes", {}) if isinstance(routing, dict) else {}
    valid.update(routes.keys())
    for rid, r in routes.items():
        if isinstance(r, dict) and isinstance(r.get("skill"), str):
            valid.add(r["skill"])
            valid.add(os.path.basename(r["skill"].replace("\\", "/")).replace(".md", ""))
    for s in registry.get("skills", []) if isinstance(registry, dict) else []:
        if not isinstance(s, dict):
            continue
        if s.get("id"):
            valid.add(s["id"])
        sp = s.get("source_path", "")
        if sp:
            valid.add(os.path.basename(sp.replace("\\", "/")).replace(".md", ""))
    if os.path.isdir(skills_dir):
        for name in os.listdir(skills_dir):
            if os.path.isfile(os.path.join(skills_dir, name, "SKILL.md")):
                valid.add(name)

    seen_ids, seen_surfaces = set(), {}
    for idx, e in enumerate(entries):
        tag = "entries[%d]" % idx
        if not isinstance(e, dict):
            problems.append("%s 不是对象" % tag)
            continue
        eid = e.get("id")
        if not isinstance(eid, str) or not ID_RE.match(eid):
            problems.append("%s.id 非法（小写数字连字符）: %r" % (tag, eid))
        elif eid in seen_ids:
            problems.append("id 重复: %s" % eid)
        else:
            seen_ids.add(eid)
        surfs = e.get("surfaces")
        if not isinstance(surfs, list) or not surfs:
            problems.append("%s(%s).surfaces 必须是非空数组" % (tag, eid))
            surfs = []
        if len(surfs) > 8:
            problems.append("%s(%s).surfaces 有 %d 个，超过上限 8（防膨胀）" % (tag, eid, len(surfs)))
        for s in surfs:
            if not isinstance(s, str) or not s.strip():
                problems.append("%s(%s) 含空 surface" % (tag, eid))
                continue
            if s.strip() in GENERIC_ONLY:
                problems.append("%s(%s) surface 无区分度: %r" % (tag, eid, s))
            if len(s.strip()) < 2:
                problems.append("%s(%s) surface 过短无意义: %r" % (tag, eid, s))
            if s in seen_surfaces:
                problems.append("surface %r 跨 entry 重复（%s 与 %s，路由会歧义）"
                                % (s, seen_surfaces[s], eid))
            else:
                seen_surfaces[s] = eid
        if not isinstance(e.get("topic"), str) or not e["topic"].strip():
            problems.append("%s(%s).topic 缺失" % (tag, eid))
        tgts = e.get("targets")
        if not isinstance(tgts, list) or not tgts:
            problems.append("%s(%s).targets 必须是非空数组" % (tag, eid))
        else:
            for t in tgts:
                if t not in valid:
                    problems.append("%s(%s) target 不存在（routing/registry/技能目录均无）: %r"
                                    % (tag, eid, t))
        if not isinstance(e.get("evidence"), str) or len(e["evidence"].strip()) < 10:
            problems.append("%s(%s).evidence 缺失或过短（须写真实依据）" % (tag, eid))

    # --- 防抄题：surface 与 work/hitrate-* hint 不得有 >=6 连续汉字相同 ---
    hint_texts, searched = collect_hint_texts(work_dir)
    if not searched:
        problems.append("work/hitrate-* 下未找到任何 hint 文件，防抄题校验无输入（work_dir=%s）" % work_dir)
    else:
        hint_wins = set()
        for h in hint_texts:
            hint_wins.update(cjk_windows(h))
        for idx, e in enumerate(entries if isinstance(entries, list) else []):
            if not isinstance(e, dict):
                continue
            for s in e.get("surfaces", []) or []:
                if not isinstance(s, str):
                    continue
                for w in cjk_windows(s):
                    if w in hint_wins:
                        problems.append("防抄题：entry %s 的 surface %r 含连续 6 汉字与压测 hint 相同（%r）"
                                        % (e.get("id"), s, w))
                        break

    print("nl-map entries=%d surfaces=%d hint_files=%d hint_texts=%d"
          % (len(entries), len(seen_surfaces), len(searched), len(hint_texts)))
    if problems:
        print("VERIFY-NL-MAP BLOCKED (%d):" % len(problems))
        for p in problems:
            print("  - " + p)
        return 20
    print("verify-nl-map: PASS")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001 - 异常即规范 30
        print("VERIFY-NL-MAP FAILED: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        sys.exit(30)
