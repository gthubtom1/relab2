"""Persistent project understanding, with focused views and explicit freshness.

The journal is the authority; Markdown files are derived navigation. This is
not a completion ledger. Business results remain in state/work and receipts.
"""
import copy
import hashlib
import json
import os
import re
from pathlib import Path

from hub_io import _file_lock, _inside_no_links, now_iso

JOURNAL = "PROJECT-MEMORY.jsonl"
MARKER = "<!-- hub-memory: generated; edit with feature_set --apply -->"
NODE_FIELDS = {"id", "name", "purpose", "parent", "intent", "sources", "rationale",
               "implementation", "depends_on", "constraints", "questions", "drafts",
               "work_ids", "replaced_by"}
PROJECT_FIELDS = {"name", "purpose", "journey", "constraints"}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"重复 JSON 字段：{key}")
        result[key] = value
    return result


def decode(text):
    return json.loads(text, object_pairs_hook=_unique)


def _text(value, label, empty=False):
    if not isinstance(value, str) or (not empty and not value.strip()) or any(
            ord(c) < 32 or c in "|\u2028\u2029" for c in value):
        raise ValueError(f"{label} 须为非空单行文字，不能含竖线或控制字符")


def _strings(values, label):
    if not isinstance(values, list):
        raise ValueError(f"{label} 须为数组")
    for value in values:
        _text(value, label)
    if len(set(values)) != len(values):
        raise ValueError(f"{label} 有重复项")


def _relative(root, value):
    _text(value, "路径")
    if (":" in value or "\\" in value or value.startswith("/")
            or any(part in ("", ".", "..") for part in value.split("/"))):
        raise ValueError(f"须使用产品内普通相对路径：{value}")
    if value.split("/")[0].lower() in (".git", ".hub", "temp", "frozen"):
        raise ValueError(f"项目理解不能依赖临时目录或运行账本：{value}；责任用 work_ids 引用")
    return _inside_no_links(root, value)


def _references(root, refs, source=False):
    if not isinstance(refs, list):
        raise ValueError("sources / locations 须为数组")
    for ref in refs:
        allowed = {"path", "anchor"} if source else {"path", "symbol"}
        if not isinstance(ref, dict) or set(ref) - allowed or "path" not in ref:
            raise ValueError("引用须包含 path，可附来源 anchor 或代码 symbol")
        _relative(root, ref["path"])
        for key in set(ref) - {"path"}:
            _text(ref[key], key)


def validate(root, model):
    project, nodes = model["project"], model["nodes"]
    if not isinstance(project, dict) or set(project) - PROJECT_FIELDS:
        raise ValueError("project 字段不合法")
    for key in ("name", "purpose"):
        _text(project.get(key), "project." + key)
    for key in ("journey", "constraints"):
        _strings(project.get(key, []), "project." + key)
    for key, node in nodes.items():
        if not isinstance(node, dict) or set(node) - NODE_FIELDS or node.get("id") != key:
            raise ValueError(f"功能 {key} 的字段或身份不合法")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", key):
            raise ValueError("稳定 ID 使用小写字母数字、横线或下划线；显示名称可用中文")
        if key.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)),
                          *(f"LPT{i}" for i in range(10))}:
            raise ValueError("功能 ID 不能是 Windows 保留文件名")
        for field in ("name", "purpose", "intent"):
            _text(node.get(field), f"{key}.{field}")
        if node.get('parent') is not None and (not isinstance(node['parent'], str) or not node['parent']):
            raise ValueError('parent 应为已有功能 ID 或 null')
        _text(node.get("rationale", ""), f"{key}.rationale", empty=True)
        for field in ("constraints", "questions", "drafts", "work_ids", "replaced_by"):
            _strings(node.get(field, []), f"{key}.{field}")
        _references(root, node.get("sources", []), source=True)
        impl = node.get("implementation")
        if impl is not None:
            if not isinstance(impl, dict) or set(impl) != {"summary", "locations"}:
                raise ValueError(f"{key}.implementation 需要 summary 和 locations")
            _text(impl["summary"], "implementation.summary")
            _references(root, impl["locations"])
            if not impl["locations"]:
                raise ValueError("实现说明必须指向实际材料；尚未定位时用 implementation: null")
        deps = node.get("depends_on", [])
        if not isinstance(deps, list):
            raise ValueError("depends_on 须为数组")
        targets = []
        for dep in deps:
            if not isinstance(dep, dict) or set(dep) != {"id", "reason"}:
                raise ValueError("依赖需要 id 与 reason，说明实际如何使用它")
            _text(dep["reason"], "依赖理由")
            targets.append(dep["id"])
        if len(set(targets)) != len(targets):
            raise ValueError("不能重复登记同一依赖")
        links = targets + node.get("replaced_by", [])
        if node.get("parent"):
            links.append(node["parent"])
        if any(target not in nodes or target == key for target in links):
            raise ValueError(f"{key} 含悬空关系或自引用")
        if any(nodes[target].get("replaced_by") for target in targets):
            raise ValueError(f"{key} 仍依赖已替代功能，请在同一次变更中接好消费者")
        if node.get('parent') and nodes[node['parent']].get('replaced_by') and not node.get('replaced_by'):
            raise ValueError(f'{key} 的父目录已替代，请接回当前树')
    # Parentage is a tree; actual data dependencies may contain cycles.
    for key in nodes:
        seen, cursor = set(), key
        while cursor:
            if cursor in seen:
                raise ValueError("父子目录不能成环")
            seen.add(cursor)
            cursor = nodes[cursor].get("parent")
        seen, todo = set(), list(nodes[key].get("replaced_by", []))
        while todo:
            cursor = todo.pop()
            if cursor == key:
                raise ValueError("替代关系不能成环")
            if cursor not in seen:
                seen.add(cursor)
                todo.extend(nodes[cursor].get("replaced_by", []))
    generated = {p.casefold() for p in (JOURNAL, 'MAP.md', 'FEATURES.md', *(f'features/{k}.md' for k in nodes))}
    for node in nodes.values():
        refs = node.get('sources', []) + (node.get('implementation') or {}).get('locations', [])
        if any(ref['path'].casefold() in generated or any(p.startswith(ref['path'].casefold() + '/')
                   for p in generated) for ref in refs):
            raise ValueError('不能把地图自身当作决定来源或实现材料')


def load_memory(root):
    root = Path(root).resolve()
    path = _inside_no_links(root, JOURNAL)
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8")
    if not raw or not raw.endswith("\n"):
        raise ValueError("项目记忆为空或末条记录不完整；保留现场，从 Git/原材料恢复")
    model = {"revision": 0, "project": {}, "nodes": {}, "reviews": {}, "history": []}
    previous = None
    for line in raw.split("\n")[:-1]:
        event = decode(line)
        if (not isinstance(event, dict) or event.get("schema") != 1
                or type(event.get("revision")) is not int
                or event["revision"] != model["revision"] + 1 or event.get("previous") != previous
                or not isinstance(event.get("nodes"), dict) or not isinstance(event.get("reviews"), dict)
                or not isinstance(event.get("project"), dict)):
            raise ValueError("项目记忆记录损坏、缺页或顺序冲突，不能当作新项目覆盖")
        model["project"].update(event["project"])
        model["nodes"].update(event["nodes"])
        for key, review in event['reviews'].items():
            if key not in model['nodes'] or not isinstance(review, dict):
                raise ValueError('项目记忆的材料核对记录形状损坏')
            for dependency, facts in review.items():
                if (dependency not in model['nodes'] or not isinstance(facts, dict)
                        or set(facts) != {'definition', 'materials'}
                        or not _hash_value(facts['definition']) or not isinstance(facts['materials'], dict)):
                    raise ValueError('项目记忆的核对定义/材料绑定损坏')
                for token, value in facts['materials'].items():
                    if not isinstance(token, str) or not _material_value(value):
                        raise ValueError('项目记忆的材料摘要损坏')
        model["reviews"].update(event["reviews"])
        model["revision"] = event["revision"]
        model["history"].append(event)
        previous = digest(event)
    validate(root, model)
    return model


def _hash_value(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def _material_value(value):
    if value is None:
        return True
    if not isinstance(value, dict) or len(value) != 1:
        return False
    if 'files' in value:
        return isinstance(value['files'], dict) and all(isinstance(k, str) and _hash_value(v)
                                                       for k, v in value['files'].items())
    return set(value) <= {'sha256', 'anchor'} and all(_hash_value(v) for v in value.values())


def _file_facts(root, ref, source=False):
    path = _relative(root, ref["path"])
    if not path.exists():
        return None
    if path.is_dir():
        if source or ref.get("symbol"):
            raise ValueError("带文字锚点的引用必须指向文件")
        files = {}
        for child in sorted(path.rglob("*")):
            _inside_no_links(root, child)
            if child.is_file():
                files[child.relative_to(path).as_posix()] = hashlib.sha256(child.read_bytes()).hexdigest()
        return {"files": files}
    if source and ref.get("anchor"):
        text = path.read_text(encoding="utf-8-sig")
        anchor = ref["anchor"]
        # Exact local quote/event text survives unrelated append-only speech.
        return {"anchor": digest(anchor)} if text.count(anchor) == 1 else None
    symbol = ref.get("symbol")
    if symbol and symbol not in path.read_text(encoding="utf-8-sig"):
        return None
    return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _closure(nodes, start):
    seen, todo = set(), [start]
    while todo:
        key = todo.pop()
        if key not in seen:
            seen.add(key)
            todo.extend(dep["id"] for dep in nodes[key].get("depends_on", []))
            # A split keeps its predecessor's context reachable. Work itself
            # still lives in the responsibility ledger and is never retired here.
            todo.extend(prior for prior, node in nodes.items() if key in node.get('replaced_by', []))
    return sorted(seen)


def binding(root, model, key, cache=None):
    result = {}
    cache = cache if cache is not None else {}
    for current in _closure(model["nodes"], key):
        node = model["nodes"][current]
        meaning = {k: v for k, v in node.items()
                   if k not in ("name", "parent", "questions", "drafts", "work_ids")}
        meaning['project_context'] = {k: v for k, v in model['project'].items() if k != 'name'}
        refs = [(ref, True) for ref in node.get("sources", [])]
        if not node.get('replaced_by'):
            refs += [(ref, False) for ref in (node.get("implementation") or {}).get("locations", [])]
        facts = {}
        for ref, source in refs:
            token = json.dumps([ref, source], sort_keys=True, ensure_ascii=False)
            if token not in cache:
                cache[token] = _file_facts(root, ref, source)
            facts[token] = cache[token]
        result[current] = {"definition": digest(meaning), "materials": facts}
    return result


def freshness(root, model):
    result, cache = {}, {}
    for key, node in model["nodes"].items():
        current = binding(root, model, key, cache)
        old = model["reviews"].get(key)
        missing = [ref for facts in current.values() for ref, value in facts["materials"].items() if value is None]
        changed = [dep for dep in set(current) | set(old or {}) if current.get(dep) != (old or {}).get(dep)]
        if node.get('replaced_by'):
            state = 'retired'
        elif missing:
            state = "missing"
        elif not node.get("implementation"):
            state = "planned"
        elif old is None:
            state = "unreviewed"
        else:
            state = "current" if not changed else "stale"
        result[key] = {"state": state, "changed": sorted(changed), "missing": missing}
    return result


LABELS = {"current": "说明对应已核对材料；业务结果另查收据", "planned": "方案；尚无实现记录",
          "unreviewed": "实现说明尚未对照材料", "stale": "相关材料或设计已变，待重新核对",
          "missing": "实现位置或来源已缺失/锚点不符", "retired": "已替代，旧责任沿替代关系继续对账"}


def resolve_node(model, value):
    if value in model["nodes"]:
        return value
    matches = [key for key, node in model["nodes"].items() if node["name"] == value]
    if not matches:
        matches = sorted({key for event in model['history'] for key, node in event['nodes'].items()
                          if node['name'] == value})
    if len(matches) != 1:
        raise ValueError(f"找不到唯一功能「{value}」；先看总图或 --search")
    return matches[0]


def impact(model, key):
    return [other for other in model["nodes"] if key in _closure(model["nodes"], other) and other != key]


def inherited_context(model, key):
    nodes, result, todo = model['nodes'], {}, [key]
    while todo:
        target = todo.pop()
        for prior, node in nodes.items():
            if target in node.get('replaced_by', []) and prior not in result:
                result[prior] = {field: node.get(field, [] if field != 'name' else '')
                                 for field in ('name', 'constraints', 'sources', 'work_ids')}
                todo.append(prior)
    return result


def overview(model, states=None):
    project, nodes = model["project"], model["nodes"]
    lines = [f"# {project['name']} · 项目总图", "", project["purpose"], ""]
    if project.get("journey"):
        lines += ["实际使用：" + " → ".join(project["journey"]), ""]
    lines += ["共同约束：" + value for value in project.get("constraints", [])]
    for key, node in nodes.items():
        if node.get('parent') is None and not node.get('replaced_by'):
            label = f" [{LABELS[states[key]['state']]}]" if states else ""
            children = sum(n.get('parent') == key and not n.get('replaced_by') for n in nodes.values())
            lines.append(f"- {node['name']} ({key})：{node['purpose']}{label}" +
                         (f"；下有 {children} 个分支，--id {key} 继续展开" if children else ''))
    lines += ["", "按功能 ID 或名称打开一叉；当前方案、实现位置、依赖与草稿在局部卡片。",
              "业务是否完成查看 state work；历史改法仅在 --history 中展开。"]
    return "\n".join(lines) + "\n"


def card(model, key, state=None, include_drafts=False):
    node = model["nodes"][key]
    impl = node.get("implementation")
    lines = [f"# 功能名：{node['name']}（{key}）", "", f"- 作用是什么：{node['purpose']}",
             f"- 稳定 ID：{key}", f"- 当前有效方案：{node['intent']}",
             f"- 现在人看见（申报）：{impl['summary'] if impl else '尚无实现记录'}"]
    lines += ['- 项目目的：' + model['project']['purpose']]
    lines += ['- 项目共同约束：' + value for value in model['project'].get('constraints', [])]
    if state:
        lines += ["- 材料状态：" + LABELS[state["state"]]]
        if state["changed"] and state["state"] in ("stale", "missing"):
            lines += ["- 待核对分支：" + "、".join(state["changed"])]
    if node.get("rationale"):
        lines += ["- 这样安排的理由：" + node["rationale"]]
    for child_key, child in model['nodes'].items():
        if child.get('parent') == key and not child.get('replaced_by'):
            lines += [f"- 下一层：{child['name']} ({child_key})：{child['purpose']}；--id {child_key}"]
    lines += ["- 有效约束：" + value for value in node.get("constraints", [])]
    for ref in node.get("sources", []):
        lines += [f"- 决定/事实来源：{ref['path']}" + (f"；锚点：{ref['anchor']}" if ref.get("anchor") else "")]
    for ref in (impl or {}).get("locations", []):
        lines += [f"- 实现位置：{ref['path']}" + (f"；符号：{ref['symbol']}" if ref.get("symbol") else "")]
    for dep in node.get("depends_on", []):
        lines += [f"- 使用 {model['nodes'][dep['id']]['name']} ({dep['id']})：{dep['reason']}"]
    consumers = impact(model, key)
    if consumers:
        lines += ["- 改动后需核对的消费者：" + "、".join(consumers)]
    lines += ["- 责任与观察入口：state work → " + value for value in node.get("work_ids", [])]
    for prior, inherited in inherited_context(model, key).items():
        lines += [f"- 拆分来源：{inherited['name']} ({prior})；旧责任须在 state 中明确承接，地图替代不等于撤回"]
        lines += ['- 前身仍需对账的约束：' + value for value in inherited['constraints']]
        lines += ['- 前身责任入口：state work → ' + value for value in inherited['work_ids']]
        lines += ['- 前身来源：' + ref['path'] + ('；' + ref['anchor'] if ref.get('anchor') else '')
                  for ref in inherited['sources']]
    lines += ["- 未决问题：" + value for value in node.get("questions", [])]
    if include_drafts:
        lines += ["- 草稿（尚未采用）：" + value for value in node.get("drafts", [])]
    elif node.get('drafts'):
        lines += [f"- 另有 {len(node['drafts'])} 项尚未采用的想法：用 --id {key} --drafts 按需展开"]
    if node.get("replaced_by"):
        lines += ["- 此功能已替代，当前入口：" + "、".join(node["replaced_by"])]
    lines += ["", "此卡片保存项目理解和定位，不能替代阅读相关代码及真实消费者验证。"]
    return "\n".join(lines) + "\n"


def projections(model):
    result = {"MAP.md": MARKER + "\n" + overview(model)}
    rows = [MARKER, "# 当前实现说明（派生视图，不是业务验收）", "",
            "| 功能名 | 作用是什么 | 现在人看见（申报） | 卡片 |", "|---|---|---|---|"]
    for key, node in model["nodes"].items():
        result[f"features/{key}.md"] = MARKER + "\n" + card(model, key)
        if node.get("implementation") and not node.get("replaced_by"):
            rows.append(f"| {node['name']}（{key}） | {node['purpose']} | {node['implementation']['summary']} | features/{key}.md |")
    result["FEATURES.md"] = "\n".join(rows) + "\n"
    return result


def projection_gaps(root, model):
    gaps = []
    for relative, expected in projections(model).items():
        path = _inside_no_links(root, relative)
        if not path.is_file() or path.read_text(encoding="utf-8-sig") != expected:
            gaps.append(relative)
    return gaps


def _atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _inside_no_links(path.parent, path.name + f".tmp-{os.getpid()}")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def publish(root, model):
    payload = projections(model)
    # The authority is already durable. Interrupted view publication is detected
    # by every consumer and can be rebuilt without approving old observations.
    for relative, content in payload.items():
        path = _inside_no_links(root, relative)
        if path.exists() and MARKER not in path.read_text(encoding="utf-8-sig"):
            raise ValueError(f"不覆盖旧人工记忆：{relative}；先核对并移入持久历史目录，再迁移")
    for relative, content in payload.items():
        _atomic(_inside_no_links(root, relative), content)


def render_memory(root):
    root = Path(root).resolve()
    path = _inside_no_links(root, JOURNAL)
    _inside_no_links(root, JOURNAL + '.lock')
    with _file_lock(path):
        model = load_memory(root)
        if model is None:
            raise ValueError('尚无持久项目记忆，不能凭旧表自动猜测设计')
        publish(root, model)
        return model


def apply_update(root, update):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("项目目录不存在")
    allowed = {"expected_revision", "reason", "project", "features", "reviewed"}
    if not isinstance(update, dict) or set(update) - allowed:
        raise ValueError("变更字段应为 expected_revision/reason/project/features/reviewed")
    _text(update.get("reason"), "变更理由")
    path = _inside_no_links(root, JOURNAL)
    _inside_no_links(root, JOURNAL + ".lock")
    with _file_lock(path):
        model = load_memory(root) or {"revision": 0, "project": {}, "nodes": {}, "reviews": {}, "history": []}
        if type(update.get("expected_revision")) is not int or update["expected_revision"] != model["revision"]:
            raise ValueError(f"项目记忆已变化；当前 revision={model['revision']}，重新读取受影响分支后再更新")
        changes, project = {}, update.get("project", {})
        if not isinstance(project, dict):
            raise ValueError("project 须为对象")
        model["project"].update(project)
        patches = update.get("features", [])
        if not isinstance(patches, list):
            raise ValueError("features 须为数组")
        for patch in patches:
            if not isinstance(patch, dict) or not isinstance(patch.get("id"), str):
                raise ValueError("每个功能变更需要稳定 id")
            key = patch["id"]
            if key in changes:
                raise ValueError("一次变更中同一功能只能出现一次")
            node = copy.deepcopy(model["nodes"].get(key, {}))
            node.update(patch)  # Omitted fields survive edits and renames.
            model["nodes"][key] = node
            changes[key] = node
        validate(root, model)
        reviewed = update.get("reviewed", [])
        _strings(reviewed, "reviewed")
        reviews = {}
        for key in reviewed:
            if key not in model["nodes"]:
                raise ValueError(f"不能核对不存在的功能：{key}")
            facts = binding(root, model, key)
            if any(value is None for item in facts.values() for value in item["materials"].values()):
                raise ValueError(f"{key} 材料缺失，不能登记为已核对")
            reviews[key] = facts
        model["reviews"].update(reviews)
        # Preflight all derived targets before the single authority commit.
        for relative in projections(model):
            target = _inside_no_links(root, relative)
            if target.exists() and MARKER not in target.read_text(encoding="utf-8-sig"):
                raise ValueError(f"已有人工记录 {relative}，须先迁移保存，不能覆盖")
        event = {"schema": 1, "revision": model["revision"] + 1,
                 "previous": digest(model["history"][-1]) if model["history"] else None,
                 "at": now_iso(), "reason": update["reason"], "project": project,
                 "nodes": changes, "reviews": reviews}
        raw = path.read_text(encoding="utf-8") if path.exists() else ""
        _atomic(path, raw + json.dumps(event, ensure_ascii=False) + "\n")
        model["revision"] = event["revision"]
        model["history"].append(event)
        publish(root, model)
        return model


def memory_context(root, focus_work=None):
    """Small recovery context; never expands the full journal into the model."""
    try:
        model = load_memory(root)
        if model is None:
            return None
        states = freshness(root, model)
        selected = [key for key, node in model['nodes'].items() if not node.get('replaced_by') and
                    (focus_work in node.get('work_ids', []) or any(focus_work in prev['work_ids']
                     for prev in inherited_context(model, key).values()))] if focus_work else []
        return {"revision": model["revision"], "project": model["project"],
                "focus_features": selected,
                "needs_reconcile": [key for key, value in states.items()
                                    if value["state"] in ("stale", "missing", "unreviewed")
                                    and not model["nodes"][key].get("replaced_by")],
                "projection_gaps": projection_gaps(root, model),
                "read": "map_show.py --product <项目根>" + (" --id " + selected[0] if len(selected) == 1 else ""),
                "boundary": "只覆盖声明材料与关系；完成和实际观察沿用 state work，不以图表为证据"}
    except (ValueError, TypeError, KeyError, OSError, UnicodeError) as exc:
        return {"error": str(exc), "read": "保留项目记忆，从 Git/原话/相关代码恢复；不要重建空账"}


def memory_gate_gap(root):
    """Compatibility guard on declared implemented features, not future plans."""
    try:
        model = load_memory(root)
        if model is None:
            return None
        gaps = projection_gaps(root, model)
        if gaps:
            return '项目记忆派生视图不同步：' + '、'.join(gaps)
        states = freshness(root, model)
        bad = [key for key, node in model['nodes'].items() if node.get('implementation')
               and not node.get('replaced_by') and states[key]['state'] != 'current']
        if bad:
            return '实现记忆待对照当前材料：' + '、'.join(bad)
        return None
    except (ValueError, TypeError, KeyError, OSError, UnicodeError) as exc:
        return '项目记忆无法核验：' + str(exc)
