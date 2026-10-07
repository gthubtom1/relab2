"""Cumulative responsibilities and derived evidence. No writable 'done' field.

This is a control contract, not semantic understanding or an OS security boundary.
Definitions and scope changes are append-only events in the existing ledger.
"""
import hashlib
import json
from pathlib import Path

from hub_io import (PHYSICAL_RECEIPT_EVENT, _file_lock, _inside_no_links, append_ledger,
                    die, read_json, read_ledger, read_text_utf8, sha256_file)
from hub_flow import (candidate_pointers, contract_fingerprint, _candidate_live,
                      phase_physical_checks, physical_receipts_for, phase_epoch)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def requirements(hub):
    path = hub / 'requirements.jsonl'
    if not path.exists():
        return []
    rows, seen = [], set()
    for number, line in enumerate(read_text_utf8(path, '需求原话').split('\n'), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        try:
            row = json.loads(line)
        except ValueError:
            raise ValueError(f'需求原话第 {number} 行不是 JSON') from None
        if not isinstance(row, dict):
            raise ValueError(f'需求原话第 {number} 行不是对象')
        rid, speech = row.get('requirement_id'), row.get('verbatim_intent')
        if not isinstance(rid, str) or not rid.strip() or rid in seen:
            raise ValueError(f'需求原话第 {number} 行身份缺失或重复')
        if not isinstance(speech, str) or not speech.strip():
            raise ValueError(f'需求 {rid} 缺少原话')
        if row.get('status', 'captured') not in ('captured', 'verified'):
            raise ValueError(f'需求 {rid} 不能靠 status 撤销；保留原话，用有决定来源的 work 撤回')
        if row.get('kind', 'requirement') not in ('requirement', 'decision', 'question'):
            raise ValueError(f'需求 {rid} 的 kind 不支持')
        if row.get('kind') == 'decision' or str(row.get('source', '')).startswith('speech:'):
            validate_decision_source(hub, row)
        seen.add(rid)
        rows.append(row)
    return rows


def validate_decision_source(hub, row):
    # A source link is evidence provenance, not host-authenticated authority.
    # It prevents a plain --kind decision / arbitrary reason from authorizing
    # scope loss. Same-account editing remains outside this trust boundary.
    from speech_land import _history_index
    source = row.get('source')
    if not isinstance(source, str) or not source.startswith('speech:'):
        raise ValueError('决定必须用 --source speech:<来源事件摘要> 关联 OWNER-SPEECH.md 的完整原话')
    speech = _inside_no_links(hub.parent, 'OWNER-SPEECH.md')
    history = _history_index(read_text_utf8(speech, '原话来源'))
    want = hashlib.sha256(row['verbatim_intent'].encode('utf-8')).hexdigest()
    if history.get(source[len('speech:'):]) != want:
        raise ValueError('决定没有匹配的完整用户原话来源，不能自行盖章')


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _paths(product, files):
    if not isinstance(files, list) or not files or len(set(files)) != len(files):
        raise ValueError('files 必须是非空、不重复的产品相对文件路径')
    out = {}
    for name in files:
        if not _text(name) or Path(name).is_absolute() or ':' in name or '\\' in name:
            raise ValueError('files 只接受普通产品相对路径，使用 / 分隔')
        if any(p.rstrip(' .').casefold() in ('', '.hub', '.git', 'temp') or p in ('.', '..')
               for p in name.split('/')):
            raise ValueError('files 不得指向账本、Git、TEMP 或父目录')
        path = _inside_no_links(product, name)
        if path.exists() and not path.is_file():
            raise ValueError('files 必须逐个列出文件，不能以目录代替依赖清单')
        out[name] = sha256_file(path) if path.is_file() else None
    return out


def _validate_item(item, contract, source_rows, product):
    fields = {'id', 'outcome', 'sources', 'phase', 'files', 'consumer', 'depends_on',
              'evidence', 'assignee', 'change_source', 'change_note'}
    if not isinstance(item, dict) or set(item) - fields:
        raise ValueError('责任有未知字段；完成状态不得手填')
    if not all(_text(item.get(k)) for k in ('id', 'outcome', 'phase', 'consumer')):
        raise ValueError('责任缺少 id、outcome、phase 或 consumer')
    if item['phase'] not in {p['id'] for p in contract['phases']}:
        raise ValueError(f"责任 {item['id']} 的阶段不在当前合同中")
    sources = {r['requirement_id']: r for r in source_rows}
    refs = item.get('sources')
    if not isinstance(refs, list) or not refs:
        raise ValueError('责任必须引用非空的原话片段 sources')
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != {'requirement_id', 'quote'}:
            raise ValueError('sources 需要 requirement_id 和 quote')
        source = sources.get(ref['requirement_id'])
        if not source or not _text(ref['quote']) or ref['quote'] not in source['verbatim_intent']:
            raise ValueError('责任引用了不存在的原话或原话没有的片段')
    _paths(product, item.get('files'))
    deps = item.get('depends_on')
    if (not isinstance(deps, list) or any(not _text(x) for x in deps)
            or len(set(deps)) != len(deps) or item['id'] in deps):
        raise ValueError('depends_on 必须是不重复、非自身的责任 ID 数组')
    evidence = item.get('evidence')
    if not isinstance(evidence, list) or not evidence:
        raise ValueError('责任必须声明非空 evidence 策略')
    seen = set()
    for rule in evidence:
        if not isinstance(rule, dict):
            raise ValueError('evidence 每项必须是对象')
        kind = rule.get('kind')
        if kind == 'probe':
            if set(rule) != {'kind', 'check', 'assertions'} or not _text(rule['check']):
                raise ValueError('probe 策略只接受 kind、check、assertions')
            names = rule['assertions']
            if (not isinstance(names, list) or not names or any(not _text(x) for x in names)
                    or len(set(names)) != len(names)):
                raise ValueError('probe 必须声明非空且不重复的具名断言')
            phase = next(p for p in contract['phases'] if p['id'] == item['phase'])
            if rule['check'] not in phase_physical_checks(product, contract, phase):
                raise ValueError('责任的 check 必须属于其到期阶段')
        elif kind in ('acceptance', 'review'):
            if set(rule) != {'kind'}:
                raise ValueError('acceptance/review 策略只接受 kind，来源另行登记')
        else:
            raise ValueError('证据类型只接受 probe、acceptance、review')
        key = digest(rule)
        if key in seen:
            raise ValueError('证据策略不能重复')
        seen.add(key)


def _decision(rows, rid):
    row = next((r for r in rows if r['requirement_id'] == rid), None)
    if not row or row.get('kind') != 'decision':
        raise ValueError('范围/证据策略变化必须引用已保留的用户决定原话（require --kind decision）')
    return row


def work_state(ledger):
    items, retired, stack, attestations = {}, {}, [], []
    for event in ledger:
        kind = event.get('kind')
        if kind == 'work_define':
            for item in event['items']:
                items[item['id']] = item
        elif kind == 'work_retire':
            retired[event['item_id']] = event
        elif kind == 'work_enter':
            if event.get('parent') != (stack[-1] if stack else None):
                raise ValueError('工作调用栈的父项不一致')
            stack.append(event['item_id'])
        elif kind == 'work_leave':
            if not stack or stack[-1] != event['item_id']:
                raise ValueError('工作返回与直接调用方不一致')
            stack.pop()
        elif kind == 'work_attest':
            attestations.append(event)
    return items, retired, stack, attestations


def validate_plan(items, retired, contract, rows, product):
    for key, item in items.items():
        _validate_item(item, contract, rows, product)
        if 'change_source' in item:
            _decision(rows, item['change_source'])
        if key in retired:
            decision = _decision(rows, retired[key].get('source'))
            if retired[key].get('source_sha') != digest(decision):
                raise ValueError('撤回决定原话发生变化，旧撤回不再有效')
    visiting, visited = set(), set()
    for key in items:
        if key in retired or key in visited:
            continue
        pending = [(key, False)]
        while pending:
            node, exiting = pending.pop()
            if exiting:
                visiting.remove(node)
                visited.add(node)
                continue
            if node not in items or node in retired:
                raise ValueError(f'依赖 {node} 不存在或已撤回；先重新接好承担者')
            if node in visiting:
                raise ValueError('责任依赖形成循环')
            if node in visited:
                continue
            visiting.add(node)
            pending.append((node, True))
            pending.extend((dep, False) for dep in items[node]['depends_on'])


def all_bindings(product, contract, items, rows):
    """Hash each declared dependency once; no recursion or exponential DAG walk."""
    sources = {r['requirement_id']: r for r in rows}
    bound, hashes, file_hashes = {}, {}, {}
    fp = contract_fingerprint(contract)
    for start in items:
        pending = [(start, False)]
        while pending:
            key, exiting = pending.pop()
            if key in bound:
                continue
            item = items[key]
            if not exiting:
                pending.append((key, True))
                pending.extend((dep, False) for dep in item['depends_on'] if dep not in bound)
                continue
            for name in item['files']:
                if name not in file_hashes:
                    file_hashes.update(_paths(product, [name]))
            value = {'definition_sha': digest(item), 'sources_sha': digest([
                sources[r['requirement_id']] for r in item['sources']]),
                'files': {name: file_hashes[name] for name in item['files']}, 'fp': fp}
            if item.get('change_source'):
                value['change_source_sha'] = digest(_decision(rows, item['change_source']))
            if item['depends_on']:
                value['dependencies'] = {dep: hashes[dep] for dep in item['depends_on']}
            bound[key], hashes[key] = value, digest(value)
    return bound


def item_binding(product, contract, item, rows, items=None):
    items = items if items is not None else work_state(read_ledger(product / '.hub'))[0]
    return all_bindings(product, contract, items, rows)[item['id']]


def probe_work_bindings(product, hub, contract, check, phase, ledger=None):
    rows = requirements(hub)
    items, retired, _, _ = work_state(read_ledger(hub) if ledger is None else ledger)
    validate_plan(items, retired, contract, rows, product)
    order = {p['id']: n for n, p in enumerate(contract['phases'])}
    bindings = all_bindings(product, contract, items, rows)
    return {key: bindings[key]
            for key, item in items.items() if key not in retired and order[item['phase']] <= order[phase] and any(
                rule['kind'] == 'probe' and rule['check'] == check for rule in item['evidence'])}


def work_view(product, hub, contract, *, phase=None, ledger=None):
    ledger = read_ledger(hub) if ledger is None else ledger
    rows = requirements(hub)
    items, retired, stack, attestations = work_state(ledger)
    validate_plan(items, retired, contract, rows, product)
    phases = contract['phases']
    order = {p['id']: n for n, p in enumerate(phases)}
    if phase is not None and phase not in order:
        raise ValueError('工作视图的阶段不在合同中')
    cutoff = order[phase] if phase else len(phases)
    covered = {s['requirement_id'] for item in items.values() for s in item['sources']}
    gaps = [f"未分解原话：{r['requirement_id']}" for r in rows
            if r.get('kind', 'requirement') == 'requirement' and r['requirement_id'] not in covered]
    speech_path = _inside_no_links(product, 'OWNER-SPEECH.md')
    if speech_path.is_file():
        from speech_land import _history_index
        speech_events = _history_index(read_text_utf8(speech_path, '原话来源'))
        mapped_events = {r.get('source') for r in rows}
        gaps.extend('原话来源尚未归类：speech:' + key for key in speech_events
                    if 'speech:' + key not in mapped_events)
    if not rows:
        gaps.append('缺少用户原话来源；先捕获需求，不要从成功声明补造原话')
    if not items:
        gaps.append('缺少累积责任计划；使用 state work --define，不能以 checklist 的 verified 替代')
    current, _ = candidate_pointers(ledger)
    live = current and _candidate_live(product, current)[0] == 'ok'
    receipts = {}
    if live:
        for p in phases:
            for check, event in physical_receipts_for(product, hub, contract, p, ledger, current['sha256']).items():
                receipts[(p['id'], check)] = event
    results = {}
    bindings = all_bindings(product, contract, items, rows)
    def assess(key):
        if key in results:
            return results[key]
        item = items[key]
        if key in retired:
            result = {'id': key, 'outcome': item['outcome'], 'phase': item['phase'],
                      'status': 'withdrawn', 'source': retired[key]['source'], 'gaps': []}
            results[key] = result
            return result
        binding = bindings[key]
        missing = []
        refs = []
        if any(v is None for v in binding['files'].values()):
            missing.append('落地文件尚未齐备')
        for rule in item['evidence']:
            if rule['kind'] == 'probe':
                latest = next((event for event in reversed(ledger)
                    if event.get('kind') == PHYSICAL_RECEIPT_EVENT
                    and event.get('check_id') == rule['check']
                    and event.get('cand_sha') == (current or {}).get('sha256')
                    and event.get('product_root') == str(product.resolve())
                    and order.get(event.get('phase_id'), -1) >= order[item['phase']]), None)
                receipt = receipts.get((latest.get('phase_id'), rule['check'])) if latest else None
                if receipt and receipt['n'] != latest['n']:
                    receipt = None
                label = rule['check'] + ':' + ','.join(rule['assertions'])
                if not receipt or receipt.get('work_bindings', {}).get(key) != binding:
                    missing.append(label + ' 缺少当前责任/文件的实际收据')
                    continue
                observed = receipt.get('observed', {}).get('assertions', [])
                passed = {a['id'] for a in observed if isinstance(a, dict) and a.get('passed') is True}
                absent = set(rule['assertions']) - passed
                if absent:
                    missing.append('未通过具名断言：' + ','.join(sorted(absent)))
                else:
                    refs.append(receipt['n'])
            else:
                matched = None
                for event in reversed(attestations):
                    if event.get('item_id') != key or event.get('evidence_kind') != rule['kind']:
                        continue
                    try:
                        source = _decision(rows, event.get('source'))
                        artifact = _paths(product, [event['artifact']])
                        valid = (event.get('binding') == binding and event.get('artifact_hashes') == artifact
                                 and all(artifact.values()) and event.get('source_sha') == digest(source)
                                 and event.get('cand_sha') == (current or {}).get('sha256')
                                 and (not current or live)
                                 and event.get('epoch') == phase_epoch(contract, ledger, item['phase']))
                        if valid:
                            matched = event['n']
                    except (ValueError, KeyError):
                        pass
                    break
                if matched is None:
                    missing.append('缺少当前对象的' + ('用户体验验收来源' if rule['kind'] == 'acceptance' else '独立评估来源'))
                else:
                    refs.append(matched)
        for dep in item['depends_on']:
            if results[dep]['status'] != 'satisfied':
                missing.append('前置责任尚未完成：' + dep)
        result = {'id': key, 'outcome': item['outcome'], 'phase': item['phase'],
                  'consumer': item['consumer'], 'depends_on': item['depends_on'],
                  'sources': item['sources'], 'status': 'pending' if missing else 'satisfied',
                  'gaps': missing, 'receipt_refs': sorted(set(refs))}
        results[key] = result
        return result
    # all_bindings preserves topological insertion order, so assess never recurses.
    for key in bindings:
        result = assess(key)
        if order[items[key]['phase']] <= cutoff and result['status'] == 'pending':
            gaps.append(key + '：' + '；'.join(result['gaps']))
    if phase is None and stack:
        gaps.append('还有未返回的工作：' + ' → '.join(stack))
    return {'version': 1, 'scope': phase or 'delivery', 'complete': not gaps,
            'items': list(results.values()), 'gaps': gaps, 'active_stack': stack,
            'boundary': '声明关系与观察的控制核；不证明语义完整、真实用户身份或操作系统隔离'}


def engineering_next(contract, view, phase=None, *, memory_gap=False, blocked=False,
                     candidate_issue=False, identity_issue=False, view_error=None):
    """Context for the agent's next judgment, never a thinking score or gate.

    Known gaps constrain action; they cannot infer the actual business cause.
    A dependency-ready item is only a suggested focus, not a scheduler decision.
    """
    order = {p['id']: n for n, p in enumerate(contract['phases'])}
    cutoff = order.get(phase, len(order))
    view = view or {}
    rows = {r['id']: r for r in view.get('items', [])}
    stack = view.get('active_stack', [])
    due = [r for r in rows.values() if order.get(r['phase'], len(order)) <= cutoff
           and r['status'] == 'pending']
    active = rows.get(stack[-1]) if stack else None
    active_in_scope = active and order.get(active['phase'], len(order)) <= cutoff
    focus = active if active_in_scope else None
    if not stack:
        focus = next((r for r in due if all(rows.get(d, {}).get('status') == 'satisfied'
                     for d in r.get('depends_on', []))), None)
    if focus is None and due and not stack:
        focus = due[0]
    parent = stack[-2] if len(stack) > 1 else '总目标'
    action_kind = 'investigate' if focus else 'reconcile'
    if identity_issue:
        action_kind, action = 'identity', '先从现场路径与 Git 核实用户所指项目；身份冲突解决前不施工。'
    elif view_error:
        action_kind, action = 'recover_state', '先保留当前账本并核对损坏/冲突的来源，恢复可核验事实；不能按新项目重建责任来掩盖旧账错误。'
    elif candidate_issue:
        action_kind, action = 'candidate', '先核对候选变化的出处和影响，保留已有改动；确认当前实物后登记或恢复，不靠改哈希跳过调查。'
    elif blocked:
        action_kind, action = 'blocked', '先核对阻塞所缺的事实或授权；可独立调查的继续，依赖阻塞条件的动作保持停止，有新证据后按原流程恢复。'
    elif memory_gap:
        action_kind, action = 'recover', '先从原话、Git、源码与现有实物恢复使用过程和旧能力；只把确实无法恢复的业务取舍问用户。'
    elif stack and not active_in_scope:
        action_kind, action = 'scope', '当前调用指向本阶段范围外的责任，先核对阶段与调用位置；不要提前完成未来工作，也不要越过未返回调用另开施工。'
    elif active and active['status'] == 'satisfied':
        action_kind, action = 'return', '当前专项已有声明证据；先让调用方实际接收并核对交付结果，再按 work --leave 返回直接调用方，继续原未完动作。'
    elif not rows:
        action_kind, action = 'prepare', '先从用户实际使用结果倒推必要条件，查证会决定路线的未知，再把安排写入已有方案和责任；不要先填表假装需求已想清。'
    elif focus and any(rows.get(d, {}).get('status') != 'satisfied' for d in focus.get('depends_on', [])):
        pending = [d for d in focus['depends_on'] if rows.get(d, {}).get('status') != 'satisfied']
        if any(order.get(rows.get(d, {}).get('phase'), len(order)) > cutoff for d in pending):
            action_kind, action = 'scope', '当前责任依赖尚未到期的工作，先核对依赖与阶段安排；不要为补当前缺口提前完成未来阶段。'
        else:
            action_kind, action = 'dependencies', ('当前工作先核对前置 ' + '、'.join(pending)
                + ' 的实际缺口，必要时进入专项取得输入，再回当前调用验证使用结果；不要把未证前提当成已可依赖。')
    elif focus:
        action = (f"先推演「{focus['outcome']}」如何由「{focus.get('consumer', '实际使用者')}」真正使用，"
                  '找出会改变路线的关键未知并选择最小调查或实验；据结果调整当前项目，再实现一段完整使用过程。')
    else:
        action = '先对照原始目的复核当前使用过程及未覆盖条件；已验证且前提未变的部分复用，补必要工程工作后再展示需要用户判断的体验。'
    return {'kind': action_kind, 'focus': ({k: focus.get(k) for k in
            ('id', 'outcome', 'consumer', 'depends_on', 'gaps')} if focus else None),
            'return_to': parent, 'action': action, 'view_error': view_error,
            'boundary': '导航只提供当前事实与判断时机；不证明已经思考全面，不改变责任、收据或授权。'}


def work_gaps(product, hub, contract, phase=None, *, mandatory=False):
    ledger = read_ledger(hub)
    enabled = mandatory or contract.get('schema_version', 1) >= 3 or any(
        e.get('kind') == 'work_define' for e in ledger)
    if not enabled:
        return None  # explicitly retain old intermediate protocol, never final delivery
    try:
        return work_view(product, hub, contract, phase=phase, ledger=ledger)['gaps']
    except (ValueError, TypeError, KeyError) as error:
        return [f'责任账无法核验：{error}']


def cmd_work(args):
    # Local import avoids a CLI/core cycle. Identity checks remain the same.
    from hub_cmds import _need_contract, _guard_identity, load_contract
    hub, contract = load_contract(args.product)
    _need_contract(args.product, contract)
    _guard_identity(args.product, contract)
    product = Path(args.product).resolve()
    try:
        with _file_lock(hub / 'work-transaction', stale=120):
            ledger = read_ledger(hub)
            rows = requirements(hub)
            items, retired, stack, _ = work_state(ledger)
            if args.define:
                payload = read_json(Path(args.define))
                if (not isinstance(payload, dict) or set(payload) != {'version', 'items'}
                        or type(payload['version']) is not int or payload['version'] != 1
                        or not isinstance(payload['items'], list) or not payload['items']):
                    raise ValueError('责任计划要求 version=1 和非空 items')
                updates, ids = {}, set()
                for item in payload['items']:
                    _validate_item(item, contract, rows, product)
                    key = item['id']
                    if key in ids or key in retired:
                        raise ValueError('本次责任 ID 重复或已撤回；新责任使用新 ID 并保留来源')
                    if key in items and item != items[key]:
                        if item.get('change_source'):
                            _decision(rows, item['change_source'])
                        elif not _text(item.get('change_note')):
                            raise ValueError('工程调整要说明 change_note；业务撤回必须另有用户决定来源')
                        old = items[key]
                        if not {digest(r) for r in old['evidence']} <= {digest(r) for r in item['evidence']}:
                            raise ValueError('不得把原证据策略删减/降为评估文字；业务范围确实变更应有来源地撤回并新建责任')
                        if not {digest(s) for s in old['sources']} <= {digest(s) for s in item['sources']}:
                            raise ValueError('修改责任不得丢失原话来源；合并/拆分先新增承接责任再按决定撤回旧项')
                    ids.add(key)
                    updates[key] = item
                merged = dict(items, **updates)
                validate_plan(merged, retired, contract, rows, product)
                append_ledger(hub, {'kind': 'work_define', 'items': list(updates.values())})
                print('已累积责任；旧项保留，完成状态由证据推导。')
                return
            if args.withdraw:
                if args.withdraw not in items or args.withdraw in retired:
                    raise ValueError('只能撤回仍有效的责任')
                source = _decision(rows, args.source)
                if args.withdraw in stack:
                    raise ValueError('先从当前工作返回，不能撤回仍在调用栈里的工作')
                event = {'kind': 'work_retire', 'item_id': args.withdraw,
                         'source': args.source, 'source_sha': digest(source)}
                validate_plan(items, dict(retired, **{args.withdraw: event}), contract, rows, product)
                append_ledger(hub, event)
                print('已按决定来源撤回；它不是实现完成，原话与旧责任继续保留。')
                return
            if args.attest:
                item = items.get(args.attest)
                if not item or args.attest in retired:
                    raise ValueError('评估对象不存在或已撤回')
                if args.kind not in ('review', 'acceptance') or {'kind': args.kind} not in item['evidence']:
                    raise ValueError('此责任没有声明该评估策略')
                source = _decision(rows, args.source)
                artifact = _paths(product, [args.artifact])
                if not all(artifact.values()) or not _text(args.actor):
                    raise ValueError('评估需要已有证据文件和实际评估者身份')
                if args.kind == 'review' and args.actor == item.get('assignee', 'implementer'):
                    raise ValueError('实现者不能为自己登记独立评估')
                current, _ = candidate_pointers(ledger)
                append_ledger(hub, {'kind': 'work_attest', 'item_id': args.attest,
                    'evidence_kind': args.kind, 'source': args.source, 'source_sha': digest(source),
                    'actor': args.actor, 'artifact': args.artifact, 'artifact_hashes': artifact,
                    'binding': item_binding(product, contract, item, rows),
                    'cand_sha': (current or {}).get('sha256'),
                    'epoch': phase_epoch(contract, ledger, item['phase'])})
                print('已登记评估来源；这不是物理运行观察，也不自动替代探针。')
                return
            if args.enter:
                if args.enter not in items or args.enter in retired or args.enter in stack:
                    raise ValueError('只能进入有效且不在调用栈中的责任')
                append_ledger(hub, {'kind': 'work_enter', 'item_id': args.enter,
                                    'parent': stack[-1] if stack else None})
                print('当前工作：' + ' → '.join([*stack, args.enter]))
                return
            view = work_view(product, hub, contract, phase=args.phase, ledger=ledger)
            if args.leave:
                if not stack:
                    raise ValueError('没有需要返回的工作')
                current_item = next(r for r in view['items'] if r['id'] == stack[-1])
                if current_item['status'] != 'satisfied' and not args.pause:
                    raise ValueError('当前责任仍未完成；阻塞转交可用 --pause，未完成项会继续保留')
                append_ledger(hub, {'kind': 'work_leave', 'item_id': stack[-1], 'paused': args.pause})
                print('返回：' + (stack[-2] if len(stack) > 1 else '总目标；继续核对所有剩余责任'))
                return
        if args.json:
            print(json.dumps(view, ensure_ascii=False, indent=2))
        else:
            print('责任检查：' + ('当前范围证据齐备' if view['complete'] else '仍有未完成责任'))
            for row in view['items']:
                print(f"  {row['id']} [{row['status']}] {row['outcome']}")
            for gap in view['gaps']:
                print('  - ' + gap)
        if args.check and not view['complete']:
            raise SystemExit(3)
    except (ValueError, TypeError, KeyError) as error:
        die(f'责任账拒绝：{error}', 3)
