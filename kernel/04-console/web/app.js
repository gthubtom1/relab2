'use strict';

// 工作台：左边点一家，中间勾几样，底部按下去。右边看要写什么和结果。
//
// 这轮的硬规矩（都对着主人提的那五条）：
//   1) 槽位标题行不是开关 —— 只有那颗 .switch 能开关。整行可点就是误击的来源。
//   2)「＋新建」只有一处：贴着它管的那一段标题。列表末尾不再重复摆一个，
//      两处入口同时在页面上等于没有入口。
//   3) 卡片整行列出：名字 / 预览 / 在不在用 / 能按什么，一行看全。
//   4) 弹层的种类写在 DOM 的 data-kind 上，点哪个按钮进来就只能存哪种，
//      没有「上一次开的是另一种」这种共享状态。
//   5) 每次按下去都有回音：按压、成功闪一下、toast、aria-live。

window.addEventListener('error', function (ev) {
  try {
    const box = document.getElementById('out');
    if (box) {
      box.className = 'bad';
      box.textContent = '页面脚本出错（把它发给工程师）：\n'
        + (ev.message || '未知错误') + '\n' + (ev.filename || '') + ':' + (ev.lineno || '');
    }
  } catch (e) { /* 连错误栏都没了，只能认了 */ }
});

const TOKEN = new URLSearchParams(location.search).get('t') || '';

function $(id) { return document.getElementById(id); }

const STATE = {
  hosts: [],
  cards: [],
  selected: '',
  locks: {},
  on: { hub: true, base: false, guest: false },
  pick: { hub: '', base: '', guest: '' },
  showAll: false,
  busy: false,
  deep: false,
  scan: null,
  seq: 0,
};

const KIND = {
  base: { name: '底模卡', slot: '第 2 段（原文之后）', verb: '新建底模卡' },
  guest: { name: '客套指引卡', slot: '第 3 段（末尾、标记块之前）', verb: '新建指引卡' },
  hub: { name: '中枢内核卡', slot: '第 4 段（最后定论）', verb: '新建中枢卡' },
};

// ---------------------------------------------------------------- 回音

let toastTimer = 0;

function toast(text, kind) {
  const el = $('live-toast');
  el.textContent = text;
  el.className = kind ? ('toast-' + kind) : '';
  el.hidden = false;
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(function () { el.hidden = true; }, 4200);
}

function setBusy(on) {
  STATE.busy = Boolean(on);
  document.body.classList.toggle('is-busy', Boolean(on));
  $('busy-bar').hidden = !on;
  const kill = $('btn-kill-host');
  if (kill && !kill.hidden) kill.disabled = Boolean(on);
}

// 旧控制台那套：按下立刻有反馈，成事后闪一下绿框。
document.addEventListener('pointerdown', function (ev) {
  const btn = ev.target && ev.target.closest ? ev.target.closest('button') : null;
  if (!btn || btn.disabled) return;
  btn.classList.add('is-tap');
}, true);

document.addEventListener('pointerup', function () {
  document.querySelectorAll('button.is-tap').forEach(function (b) { b.classList.remove('is-tap'); });
}, true);

function flash(btn, ok) {
  if (!btn) return;
  if (!ok) return;
  btn.classList.add('is-done');
  window.setTimeout(function () { btn.classList.remove('is-done'); }, 700);
}

// 任何一次动作都写一句话到提示条。aria-live 已经挂在节点上了。
function say(lines, kind) {
  const out = $('out');
  out.className = kind || '';
  out.textContent = (Array.isArray(lines) ? lines : [lines]).join('\n');
}

function note(t) { $('action-note').textContent = t; }

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

function btn(id, label, title, onClick) {
  const b = el('button', 'btn-ghost', label);
  b.id = id;
  b.type = 'button';
  if (title) b.title = title;
  b.onclick = onClick;
  return b;
}

// ---------------------------------------------------------------- 网络

async function api(path, options) {
  const opts = Object.assign({ method: 'GET' }, options || {});
  opts.headers = Object.assign({ 'X-Token': TOKEN }, (options && options.headers) || {});
  if (opts.body) { opts.headers['Content-Type'] = 'application/json; charset=utf-8'; }
  const res = await fetch(path, opts);
  const text = await res.text();
  let data = null;
  try { data = JSON.parse(text); } catch (err) { data = null; }
  if (!data) { throw new Error('本机服务回了看不懂的内容。'); }
  if (res.status >= 400 || data.ok === false) {
    throw new Error(data.error || data.say || ('没成（' + res.status + '）'));
  }
  return data;
}

function post(path, payload) {
  return api(path, { method: 'POST', body: JSON.stringify(payload) });
}

function anyModalOpen() {
  return ['card-modal', 'view-modal', 'host-modal'].some(function (id) {
    return !$(id).classList.contains('hidden');
  });
}

// ---------------------------------------------------------------- 名单

// 这两件事是正交的，别让一个词扛两件事：
//   agentState —— 这家智能体在不在你电脑上（能被扫出来 = 家目录和入口文件都在）
//   hubState   —— 中枢写进这家了没有，写进去了哪几段
// 以前这两件事挤在一个「未装」里，主人会读成「这家没装」。不许再那样写。
function agentState(h) {
  return h.exists ? { key: 'in', text: '在' } : { key: 'none', text: '没这家' };
}

function hubState(h) {
  if (!h.exists) return { key: 'none', text: '没这家' };
  // 「已进」的判据是入口文件里真读到那几段，不是 hub/ 目录在不在。
  // 有人手删了入口文件里的块，hub/ 还照样在——这时候必须说没进。
  if (h.installed && h.entry_ok) return { key: 'on', text: '中枢已进' };
  if (h.installed && !h.entry_ok) {
    return { key: 'warn', text: '入口未进' };
  }
  if (h.legacy) return { key: 'legacy', text: '只剩旧版' };
  return { key: 'idle', text: '中枢没进' };
}

function rankOf(h) {
  if (!h.exists) return 3;
  if (h.running) return 1;
  if (h.installed) return 0;
  if (h.legacy) return 2.5;
  return 2;
}

function renderHosts() {
  const box = $('hosts');
  box.innerHTML = '';
  const real = STATE.hosts.filter(function (h) { return h.exists; });
  const scanned = real.filter(function (h) { return h.scanned; }).length;
  const custom = real.filter(function (h) { return h.custom; }).length;

  const bits = [];
  if (real.length) {
    // 两件事分开报：机器上有几家智能体 · 中枢写进几家。
    const inHub = real.filter(function (h) { return h.installed; }).length;
    const legacy = real.filter(function (h) { return h.legacy && !h.installed; }).length;
    bits.push('机器上有 ' + real.length + ' 家智能体');
    bits.push('中枢已进 ' + inHub + ' 家');
    if (legacy) bits.push(legacy + ' 家只剩旧版 hub-lean');
    if (scanned) bits.push(scanned + ' 家是扫出来的');
    if (custom) bits.push(custom + ' 家是你手加的');
    if (STATE.showAll) bits.push('另有 ' + (STATE.hosts.length - real.length) + ' 家在名单里但本机没装');
  } else {
    bits.push('一家都没扫到。点「深扫全盘」把整台盘兜一遍，还是没有就点「＋ 加一家」自己填家目录。');
  }
  $('hosts-hint').textContent = bits.join(' · ');

  if (!STATE.hosts.length) { box.appendChild(el('p', 'side-hint', '还没扫。')); return; }
  STATE.hosts.slice().sort(function (a, b) {
    return rankOf(a) - rankOf(b) || String(a.name).localeCompare(String(b.name));
  }).forEach(function (h) {
    const ag = agentState(h);
    const hub = hubState(h);
    const sel = STATE.selected === h.id;
    const row = el('button', 'seat st-' + ag.key + (sel ? ' sel' : '')
                    + (hub.key === 'on' ? ' st-on' : '')
                    + (hub.key === 'warn' ? ' st-warn' : '')
                    + (hub.key === 'legacy' ? ' st-legacy' : ''));
    row.type = 'button';
    row.appendChild(el('i', 'dot'));
    const body = el('span', 'seat-body');
    body.appendChild(el('span', 'seat-name', h.name));
    // 第二行把两件事分开写：怎么认到它的 + 它在哪。路径太长就省略，不换行。
    body.appendChild(el('span', 'seat-why',
      (h.why ? h.why + ' · ' : '') + h.home
      + (h.entry_exists ? '' : '（入口 ' + h.entry + ' 还没有）')));
    row.appendChild(body);
    row.appendChild(el('span', 'pill st-' + hub.key, hub.text));
    row.title = (ag.key === 'in' ? '智能体在 · ' : '智能体没装 · ')
      + '中枢：' + hub.text + '\n' + h.home + '（入口 ' + h.entry + '）';
    row.onclick = function () { selectHost(h.id); };
    box.appendChild(row);
  });

  renderScanReport(STATE.scan || (STATE.status && STATE.status.scan) || {});
}

function renderScanReport(scan) {
  const detail = $('scan-detail');
  if (!scan || !scan.roots || !scan.roots.length) { detail.hidden = true; return; }
  // 扫到/漏扫是主人最关心的事，收在折叠里等于没说 —— 默认展开。
  detail.hidden = false;
  detail.open = true;
  const box = $('scan-report');
  box.innerHTML = '';
  const add = function (label, value) {
    const line = el('div');
    line.appendChild(el('b', null, label + '：'));
    line.appendChild(document.createTextNode(value));
    box.appendChild(line);
  };
  // 要紧的先写：扫到几家、深扫滤掉多少。这两条主人一眼就要看见，别排在下面等滚动。
  add('扫到', (scan.found || []).length
      ? ((scan.found || []).length + ' 家 · ' + scan.found.join('、'))
      : '名单之外没有额外的');
  if (scan.deep) {
    add('深扫滤掉', (scan.filtered || 0) + ' 个不像家目录的（临时目录、测试夹、仓库子目录）');
  }
  add('看了这几个位置', scan.roots.join(' / '));
  add('手加的', String(scan.custom || 0) + ' 家');
  add('被你点名不列的', String(scan.ignored || 0) + ' 家');
  // 「别列这家」以前是单向门：点错一次就再也看不到这家。
  // 每一条都给一个能点的退路。
  (scan.ignored_homes || []).forEach(function (home) {
    const line = el('div', 'scan-ignored');
    line.appendChild(el('span', null, home + '：'));
    const undo = el('button', 'btn-ghost', '恢复显示');
    undo.onclick = function () {
      post('/api/hosts/unignore', { home: home }).then(function () {
        toast('✓ 以后会列 ' + home);
        return api('/api/scan').then(function (d) {
          STATE.scan = d.scan;
          renderScanReport(d.scan);
          return refresh();
        });
      }).catch(function (e) { toast('✗ ' + e.message, 'bad'); });
    };
    line.appendChild(undo);
    box.appendChild(line);
  });
  if (!scan.everything) {
    add('深扫能力', '这台机器没装 Everything，深扫只能扫到上面那几个位置。手填家目录照样管用。');
  }
  if ((scan.skipped || []).length) {
    add('没列出来的点目录', scan.skipped.join('、'));
  }
}

function selectedHost() {
  return STATE.hosts.filter(function (h) { return h.id === STATE.selected; })[0] || null;
}

// ---------------------------------------------------------------- 主板

// 中枢写进这家什么：逐段给答案，在不在 + 在的话是哪张卡。
// 底模/指引的名字来自装的时候写的 install-manifest.json，不是猜的。
function renderSegs(h) {
  const box = $('hero-seg');
  const row = $('seg-row');
  row.innerHTML = '';
  if (!h) { box.hidden = true; return; }
  box.hidden = false;
  // 每一段的「在不在」都以入口文件的实测为准，manifest 只是交叉参考。
  const segs = [
    { name: '中枢标记块', in: !!h.has_marker, detail: h.has_marker ? '在入口文件里' : '没进' },
    { name: '底模', in: !!h.has_base, detail: h.base_name ? '「' + h.base_name + '」' : (h.has_base ? '在' : '没进') },
    { name: '客套指引', in: !!h.has_guest, detail: h.guest_name ? '「' + h.guest_name + '」' : (h.has_guest ? '在' : '没进') },
  ];
  if (h.base_drift) segs[1].detail += '（你改过这张卡，智能体里还是旧的）';
  if (h.guest_drift) segs[2].detail += '（你改过这张卡，智能体里还是旧的）';
  segs.forEach(function (s) {
    const chip = el('span', 'seg' + (s.in ? ' on' : ''));
    chip.appendChild(el('b', null, s.name));
    chip.appendChild(el('span', null, s.detail));
    row.appendChild(chip);
  });
  const notes = [];
  if (h.installed) {
    notes.push('中枢文件 ' + h.core_kb + ' KB · ' + h.file_count + ' 个文件，在 ' + h.home + '\\hub。'
      + (h.entry_ok ? '入口文件实测：' + h.entry_note + '。' : '⚠ ' + h.entry_note + '。')
      + '宿主原文一个字没动。');
  } else {
    notes.push('还没往这家写过。选好左边那几样，按底部的「载入」。');
  }
  if (h.legacy) {
    notes.push('⚠ 旧版中枢（hub-lean/，' + h.legacy_files + ' 个文件）还留在这儿。'
      + '那是上一版写的，这一版不认它、也不会去动它 —— 要清得用旧版自己的卸载方式。');
  }
  $('seg-note').textContent = notes.join(' ');
}

function renderHero() {
  const h = selectedHost();
  const kill = $('btn-kill-host');
  const hide = $('btn-hide-host');
  const drop = $('btn-drop-host');
  if (!h) {
    $('hero-title').textContent = '先在左边点一家智能体';
    $('hero-recipe').textContent = '选中之后这里显示它的家目录、入口文件和运行状态。';
    ['home', 'entry', 'run', 'hub'].forEach(function (k) { $('hero-' + k).textContent = '—'; });
    if (kill) kill.hidden = true;
    hide.hidden = true;
    drop.hidden = true;
    renderSegs(null);
    return;
  }
  const ag = agentState(h);
  const hub = hubState(h);
  $('hero-title').textContent = h.name;
  $('hero-recipe').textContent = hub.key === 'warn'
    ? '⚠ ' + hub.text + ' —— 智能体这一轮可能读不到中枢规则。点「卸回」再「载入」一次。'
    : (h.installed ? '已经装着中枢。改完卡片再按载入：先摘旧的三段，再插新的。'
                   : '勾好中间那几样，按底部的载入。');
  $('hero-home').textContent = h.home;
  $('hero-entry').textContent = h.entry + (h.entry_exists ? '' : '（还没有）');
  $('hero-run').textContent = (ag.key === 'in' ? '智能体在' : '智能体没装')
    + (h.running ? ' · 运行中' : (h.exists ? ' · 空闲' : ''))
    + (h.auto ? ' · ' + (h.why || '只按文件认') : '')
    + ((h.pids && h.pids.length) ? ' · PID ' + h.pids.join('、') : '');
  $('hero-hub').textContent = hub.text
    + (h.installed ? '（' + h.core_kb + ' KB / ' + h.file_count + ' 个文件'
       + (h.installed_at ? '，' + h.installed_at.slice(0, 10) : '') + '）' : '')
    + (h.legacy && !h.installed ? ' · 旧版 hub-lean/ 还在' : '');
  $('hero-hub').className = h.installed ? 'ok' : (h.legacy ? 'warn' : '');
  if (kill) {
    const pidsCount = (h.pids && h.pids.length) || 0;
    if (h.running && pidsCount > 0) {
      kill.hidden = false;
      kill.textContent = '强制关闭 (' + pidsCount + ')';
      kill.title = '强制终止后台运行中的 ' + pidsCount + ' 个进程 (PID: ' + h.pids.join('、') + ')';
      kill.disabled = STATE.busy;
    } else {
      kill.hidden = true;
    }
  }
  hide.hidden = false;
  drop.hidden = !h.custom;
  // 「别列这家」只对扫出来的/内置的那几家管用：手加的那家在 custom-hosts.json 里，
  // 扫描根本不看它——对它显示这个按钮就是骗人。主人想删手加的，有「从名单拿掉」。
  if (h.custom) { hide.hidden = true; }
  renderSegs(h);
}

function cardsOf(kind) {
  return STATE.cards.filter(function (c) { return (c.kind || 'base') === kind; });
}

function mountedName(kind) {
  const h = selectedHost();
  if (!h || !h.installed) return '';
  return kind === 'base' ? (h.base_name || '') : (kind === 'guest' ? (h.guest_name || '') : (h.hub_name || ''));
}

// 这一行是在宿主上已经装着的，还是这次要装上去的。
function cardTag(kind, card) {
  const mounted = mountedName(kind);
  const drift = (selectedHost() || {})[kind + '_drift'] || '';
  // Windows 文件名不区分大小写：装的是「Foo」而卡叫「foo」时也算同一张。
  const same = function (a, b) {
    return !!a && !!b && String(a).toLowerCase() === String(b).toLowerCase();
  };
  if (mounted && same(mounted, card.id)) {
    if (drift) return { text: '正在用（你改过，没重装）', cls: 'tag-warn' };
    return { text: '正在用', cls: 'tag-ok' };
  }
  if (STATE.on[kind] && STATE.pick[kind] === card.id) return { text: '这次会装', cls: 'tag-soft' };
  return { text: '没挂上', cls: 'tag-mute' };
}

function renderCards(kind) {
  const box = $('tiles-' + kind);
  box.innerHTML = '';
  const list = cardsOf(kind);
  if (!list.length) {
    box.appendChild(el('div', 'card-empty', '还没有' + KIND[kind].name + '。点上面标题里那个「＋ 新建」写一张。'));
  }
  list.forEach(function (c) {
    const picked = STATE.pick[kind] === c.id;
    const row = el('div', 'card-row' + (picked ? ' picked' : '') + (STATE.on[kind] ? '' : ' dim'));
    row.onclick = function () { useCard(kind, c.id); };

    const left = el('div');
    left.appendChild(el('span', 'card-id', c.id));
    left.appendChild(el('span', 'card-kind', kind === 'base' ? '底模' : (kind === 'guest' ? '指引' : '中枢')));
    if (c.declared && c.declared !== c.kind) {
      const warn = el('span', 'card-kind', '⚠ 卡头写的是' + c.declared);
      warn.title = '把卡文件挪到 ' + c.declared + '/ 子夹，或者把卡头那行改成 ' + c.kind
        + '，不然按「载入」会被打包器拦下。';
      left.appendChild(warn);
    }
    row.appendChild(left);
    row.appendChild(el('span', 'card-preview', c.preview || '（正文第一行是空的）'));

    const ops = el('div', 'card-ops');
    const tag = cardTag(kind, c);
    ops.appendChild(el('span', 'tag ' + tag.cls, tag.text));
    ops.appendChild(btn('use-' + kind + '-' + c.id, picked ? '取消选用' : '用这张',
                        '同一时刻只用一张。点一下换一张。', function (ev) { ev.stopPropagation(); useCard(kind, c.id); }));
    ops.appendChild(btn('view-' + kind + '-' + c.id, '看', '看这张卡的全文。', function (ev) { ev.stopPropagation(); viewCard(kind, c.id); }));
    ops.appendChild(btn('edit-' + kind + '-' + c.id, '改', '改这张卡。种类不变，改的还是' + KIND[kind].name + '。', function (ev) { ev.stopPropagation(); openCard(kind, 'edit', c.id); }));
    const del = btn('del-' + kind + '-' + c.id, '删', '删掉这张卡（已经装进宿主的不受影响）。', function (ev) {
      ev.stopPropagation();
      if (!window.confirm('删掉卡片「' + c.id + '」？\n已经装进宿主的那一份不会被这次删除动到；'
          + '但下次按「载入」时如果没勾它，那一段会被摘掉。')) return;
      post('/api/cards/delete', { id: c.id, kind: kind }).then(function () {
        if (STATE.pick[kind] === c.id) STATE.pick[kind] = '';
        toast('删掉了 ' + c.id);
        return refresh();
      }).catch(function (e) { toast(e.message, 'bad'); say([e.message], 'bad'); });
    });
    del.className = 'btn-ghost btn-danger';
    ops.appendChild(del);
    row.appendChild(ops);
    box.appendChild(row);
  });
}

function useCard(kind, id) {
  if (STATE.pick[kind] === id) {
    STATE.pick[kind] = '';
    toast('取消选用 ' + id);
  } else {
    STATE.pick[kind] = id;
    STATE.on[kind] = true;
    toast('这次用 ' + id + '（' + KIND[kind].slot + '）', 'good');
  }
  renderSlots(); renderPlan();
  // 选卡不等于开段：只有那颗开关能开关（这个文件顶上第 1 条纪律）。
  note(KIND[kind].name + '：' + (STATE.pick[kind] ? '用 ' + STATE.pick[kind] : '这次不写')
       + (STATE.pick[kind] && !STATE.on[kind] ? '（开关还关着，不会写进去）' : ''));
}

function renderSlots() {
  renderCards('hub');
  renderCards('base');
  renderCards('guest');
  ['hub', 'base', 'guest'].forEach(function (k) {
    $('sw-' + k).setAttribute('aria-pressed', STATE.on[k] ? 'true' : 'false');
    const slot = $('slot-' + k);
    if (slot) { slot.className = 'slot slot-' + k + ' ' + (STATE.on[k] ? 'on' : 'off'); }
  });
  $('hub-tag').textContent = STATE.on.hub ? '12 块底线 · 约 23.6 KB' : '关着，不写这一段';
  ['base', 'guest'].forEach(function (k) {
    $('sw-' + k).title = (KIND[k].name + '：开/关') + (STATE.on[k] ? '（现在开着）' : '（现在关着）');
    $((k === 'base' ? 'base' : 'guest') + '-tag').textContent = STATE.on[k]
      ? (STATE.pick[k] ? ('用 ' + STATE.pick[k]) : '开着，但还没点卡片')
      : '关着';
  });

  const h = selectedHost();
  // 「正在跑」「运行态读不到」「这家根本没装」——这三种都不该让载入亮着。
  // 页面上的灰不是门禁，门禁在服务端；这里只是别让主人白等一次失败。
  const blocked = !h || !h.exists || h.running || h.running_known === false || STATE.busy;
  const load = $('btn-load');
  load.disabled = blocked;
  if (!load.dataset.icon) load.dataset.icon = load.innerHTML;   // 保住对勾图标
  load.innerHTML = load.dataset.icon + (h && h.installed ? '重新载入' : '载入');
  load.title = !h ? '先选一家智能体'
    : (!h.exists ? '这家没装过，没有家目录可写'
      : (h.running ? '这家正在跑，先关掉'
        : (h.running_known === false ? '读不出这家在不在跑，先关掉它再写'
          : '把勾好的几段写进它家入口文件')));
  $('btn-unload').disabled = !h || !h.installed || h.running || h.running_known === false || STATE.busy;
  ['btn-lock', 'btn-verify'].forEach(function (id) {
    $(id).disabled = !h || STATE.busy;
  });
  $('btn-restore').disabled = !h || h.running || h.running_known === false || STATE.busy;
}

// ---------------------------------------------------------------- 检视

// 打包器每次写入前都会先把旧的三段摘干净，再插回这次勾的。
// 所以「已装但这次没勾」= 会被摘掉。主人有权在按下去之前看见这件事。
function pendingRemovals(h) {
  const out = [];
  if (!h || !h.installed) return out;
  if (!STATE.on.hub) out.push('中枢标记块（这次不写它）');
  ['base', 'guest'].forEach(function (k) {
    const mounted = k === 'base' ? h.base_name : h.guest_name;
    if (!mounted) return;
    if (!STATE.on[k] || !STATE.pick[k]) out.push(KIND[k].name + '「' + mounted + '」（这次不写它）');
    else if (STATE.pick[k] !== mounted) out.push(KIND[k].name + '「' + mounted + '」换成「' + STATE.pick[k] + '」');
  });
  return out;
}

function renderPlan() {
  const box = $('plan');
  box.innerHTML = '';
  const h = selectedHost();
  if (!h) { box.appendChild(el('li', null, '先选一家智能体')); return; }
  const pkg = (STATE.status && STATE.status.package) || {};
  const rows = [];
  if (STATE.on.base) rows.push(STATE.pick.base ? ('宿主原文之后：底模「' + STATE.pick.base + '」') : '底模开关开着，但还没点卡片');
  if (STATE.on.guest) rows.push(STATE.pick.guest ? ('再往后：客套指引「' + STATE.pick.guest + '」') : '指引开关开着，但还没点卡片');
  rows.push('直写：选中的几层按顺序拼成一份，整份替换入口文件（原来那份进保险箱，随时能退）');
  if (STATE.on.hub) rows.push('最后一段：中枢标记块（12 块底线，永远最终裁决）');
  if (!STATE.on.hub && !STATE.on.base && !STATE.on.guest) rows.push('三段都没勾，没东西可写');
  if (h.installed) {
    const gone = pendingRemovals(h);
    rows.push('先摘掉旧的三段，再插新的');
    if (gone.length) rows.push('这次会动：' + gone.join('；'));
  } else if (pkg.ready) {
    rows.push('顺便写 hub/：' + (pkg.file_count || 0) + ' 个文件，' + (pkg.total_kb || 0) + ' KB');
  } else {
    rows.push('打包器未就绪：' + ((pkg.missing || []).join('、') || '看终端'));
  }
  rows.forEach(function (t) { box.appendChild(el('li', null, t)); });
}

function renderLocks() {
  const h = selectedHost();
  const box = $('lock-detail');
  box.innerHTML = '';
  if (!h) { $('lock-state').textContent = '还没选'; return; }
  const snaps = (STATE.locks[h.id] || {}).snapshots || [];
  if (!snaps.length) {
    $('lock-state').textContent = '还没锁过';
    box.appendChild(el('li', null, '锁一次 = 记下它现在的样子，以后能比、能退。'));
    return;
  }
  const last = snaps[snaps.length - 1];
  $('lock-state').textContent = '锁了 ' + snaps.length + ' 次，最近 ' + last.tag;
  box.appendChild(el('li', null, '锁的是入口文件那一份，逐字节存成 .bak。'));
  box.appendChild(el('li', null, '最多留 3 份；要换基准就再按一次「锁定」。'));
}

// ---------------------------------------------------------------- 动作

// 选中一家时，把「它现在装着哪几张卡」从装好的记录里读回来。
// 不这么做：刷新一次页面后开关全回默认，主人按一次「重新载入」，
// 打包器会先把旧三段摘干净再只插回勾过的——底模和指引就被静默删掉了。
function adoptInstalled(h) {
  if (!h) return;
  STATE.pick = { hub: '', base: '', guest: '' };
  ['hub', 'base', 'guest'].forEach(function (k) {
    const name = k === 'base' ? h.base_name : (k === 'guest' ? h.guest_name : (h.hub_name || ''));
    if (k === 'hub') {
      STATE.on.hub = Boolean(h.installed);
      if (name && cardsOf('hub').some(function (c) { return c.id === name; })) {
        STATE.pick.hub = name;
      }
      return;
    }
    if (!h.installed || !name) { STATE.on[k] = false; return; }
    const exists = cardsOf(k).some(function (c) { return c.id === name; });
    STATE.on[k] = exists;
    STATE.pick[k] = exists ? name : '';
  });
}

function selectHost(id) {
  STATE.selected = id;
  renderHosts(); renderHero(); renderSlots(); renderPlan(); renderLocks();
  const h = selectedHost();
  adoptInstalled(h);
  renderSlots(); renderPlan();
  if (h && h.installed && (h.base_name || h.guest_name)) {
    const gone = [];
    if (h.base_name && !STATE.pick.base) gone.push('底模「' + h.base_name + '」');
    if (h.guest_name && !STATE.pick.guest) gone.push('指引「' + h.guest_name + '」');
    if (gone.length) {
      say(['这家现在装着：' + gone.join('、') + '，但这几张卡已经不在卡片区了。',
           '按「载入」不会把它们摘掉（这次不勾就不动它们）；真要清掉就点「卸回」。'], 'warn');
    }
  }
  note(h ? ((h.installed ? '已选 ' + h.name + '（装着 v' + (h.version || '?') + '）' : '已选 ' + h.name + '（未装）')) : '');
  api('/api/safebox?host_id=' + encodeURIComponent(id)).then(function (lk) {
    STATE.locks[id] = lk;
    renderLocks();
  }).catch(function () {});
}

function act(kind) {
  const h = selectedHost();
  if (!h) { say(['先在左边点一家智能体。'], 'bad'); toast('先在左边点一家智能体。', 'bad'); return; }
  if (STATE.busy) { say(['上一个动作还在跑，等它完。'], 'bad'); toast('上一个动作还在跑，等它完。', 'bad'); return; }
  if (kind === 'unload' && !window.confirm(
      '把 ' + h.name + ' 的入口文件按保险箱那份换回来？\n'
      + '直写模式只有这一条退路：保险箱里那份会覆盖现在这份，备份用掉（要再退就先重新锁定）。')) return;
  if (kind === 'restore' && !window.confirm(
      '按保险箱那版把 ' + h.name + ' 的配置和入口文件还原？\n清单只报不删。')) return;

  const payload = { host_id: h.id };
  let path = '';
  if (kind === 'load') {
    const why = [];
    why.push('· 写法：直写 —— 这一家的入口文件整份换成我们拼的那一份（原来那份进保险箱，随时能退）');
    if (why.length && !window.confirm(
        '写入 ' + h.name + ' 时会动这些：\n\n' + why.join('\n') + '\n\n继续吗？')) return;
    path = '/api/load';
    payload.with_marker = !!STATE.on.hub;
    payload.mode = 'direct';
    payload.replace_origin = true;
    if (STATE.on.base && STATE.pick.base) payload.base_id = STATE.pick.base;
    if (STATE.on.guest && STATE.pick.guest) payload.guest_id = STATE.pick.guest;
    if (STATE.on.hub && STATE.pick.hub) payload.hub_id = STATE.pick.hub;
    if (!STATE.on.hub && !STATE.on.base && !STATE.on.guest) {
      toast('三段都没勾，没东西可写。', 'bad');
      return;
    }
  } else if (kind === 'unload') {
    path = '/api/unload';
    payload.mode = 'direct';
  } else {
    path = '/api/safebox';
    payload.action = kind;
  }
  const label = ({ load: '写进去', unload: '卸回', snapshot: '锁定保险箱',
                   verify: '和保险箱比对', restore: '按保险箱恢复' }[kind] || kind);
  setBusy(true);
  renderSlots();
  say(['在跑…（' + label + '）'], '');
  toast(label + '…');
  note('在跑，别关窗口…');
  post(path, payload).then(function (data) {
    const lines = (data.steps || []).map(function (s) {
      return (s.ok ? '✓ ' : '✗ ') + s.name + (s.detail ? '：' + s.detail : '');
    });
    if (data.say) lines.push(data.say);
    if (data.error) lines.push(data.error);
    if (data.diffs && data.diffs.length) {
      lines.push('');
      data.diffs.forEach(function (d) { lines.push('· ' + d); });
    }
    // 「比对」有差异不是失败：它是在告诉你哪儿不一样。用黄色，不拉红报警。
    const isVerify = kind === 'verify';
    const passed = isVerify ? data.same !== false : data.ok;
    const tone = isVerify ? (passed ? 'good' : 'warn') : (data.ok ? 'good' : 'bad');
    if (!lines.length) lines.push(data.ok ? '成了。' : '没成。');
    say(lines, tone);
    const done = {
      load: data.ok ? '装好了。关掉这个窗口就能去用它。' : '没装成，看右下结果。',
      unload: data.ok ? '卸回了。按「比对」可以确认跟保险箱那一版一致。' : '没卸回，看右下结果。',
      snapshot: data.say || '锁好了。',
      verify: data.same === false ? '不一样，清单在下面。' : (data.say || ''),
      restore: data.say || '',
    }[kind] || '';
    note(done);
    toast((isVerify ? (passed ? '✓ ' : '! ') : (data.ok ? '✓ ' : '✗ ')) + label
          + (done ? '：' + done : ''), tone);
    // 打包器跑完了，交互就该还给人。补一次状态是后台的事，不该把按钮锁住。
    setBusy(false);
    renderSlots();
    flash(btnOf(kind), isVerify ? passed : data.ok);
    return refresh();
  }).catch(function (e) {
    say([e.message], 'bad');
    note('这一步没成：' + e.message);
    toast('✗ ' + label + '：' + e.message, 'bad');
  }).then(function () {
    setBusy(false);
    renderSlots();
  });
}

function btnOf(kind) {
  const map = { load: 'btn-load', unload: 'btn-unload', snapshot: 'btn-lock',
                verify: 'btn-verify', restore: 'btn-restore' };
  return map[kind] ? $(map[kind]) : null;
}

// ---------------------------------------------------------------- 弹层

function openModal(id) { $(id).className = 'modal'; }
function closeModal(id) { $(id).className = 'modal hidden'; }

function openCard(kind, mode, editId) {
  // 种类、模式、正在改哪一张，全都写进 DOM。保存时只读 DOM，不读任何全局变量，
  // 所以「点底模的按钮弹出指引的弹层」这种事在结构上就发生不了。
  const modal = $('card-modal');
  modal.dataset.kind = kind;
  modal.dataset.mode = mode || 'new';
  modal.dataset.edit = editId || '';
  $('card-msg').textContent = '';
  $('card-name').value = editId || '';
  $('card-hosts').value = '';
  $('card-content').value = '';
  if (editId) {
    api('/api/card?kind=' + encodeURIComponent(kind) + '&id=' + encodeURIComponent(editId)
    ).then(function (data) {
      $('card-hosts').value = data.hosts || '';
      $('card-content').value = data.content || '';
      $('card-msg').textContent = '已经把这张卡原来的正文拉出来了。改完按保存。';
    }).catch(function (e) { $('card-msg').textContent = e.message; });
  }
  $('modal-title').textContent = editId
    ? ('改' + KIND[kind].name + '「' + editId + '」')
    : KIND[kind].verb;
  const slotText = {
    hub: '这一步在写「中枢内核卡」：底层执行内核与执行约束，装进去就是标记块的正文（最后一段定论）。原样存，我们一个字都不改。',
    base: '这一步在写「底模卡」：你自己写的一套心智，装进去在第 2 段（宿主原文之后）。原样存，我们一个字都不改。',
    guest: '这一步在写「客套指引卡」：别人的成品提示词，原样粘在第 3 段（末尾、标记块之前）。原样存，我们一个字都不改。',
  };
  $('modal-kind').textContent = slotText[kind] || slotText.base;
  openModal('card-modal');
  $('card-content').focus();
}

function viewCard(kind, id) {
  api('/api/card?kind=' + encodeURIComponent(kind) + '&id=' + encodeURIComponent(id)
  ).then(function (data) {
    const k = KIND[data.kind] || KIND.base;
    $('view-title').textContent = '看' + k.name + '「' + id + '」';
    $('view-kind').textContent = '装在' + k.slot + '。'
      + (data.declared && data.declared !== data.kind
         ? '⚠ 卡头那行写的是 ' + data.declared + '，按载入会被打包器拦下。' : '卡头与池子一致。')
      + '（' + data.bytes + ' 字节）';
    $('view-body').textContent = data.content || '';
    openModal('view-modal');
  }).catch(function (e) { toast(e.message, 'bad'); say([e.message], 'bad'); });
}

function openHostForm() {
  $('host-msg').textContent = '';
  $('host-name').value = '';
  $('host-path').value = '';
  openModal('host-modal');
  $('host-name').focus();
}

$('btn-save-card').onclick = function () {
  // 种类从 DOM 读。按钮点了哪个弹层，这里就存哪种。
  const kind = $('card-modal').dataset.kind === 'guest' ? 'guest' : 'base';
  const name = $('card-name').value.trim();
  if (!name) { $('card-msg').textContent = '先给这张卡起个名。'; return; }
  if (!$('card-content').value.trim()) { $('card-msg').textContent = '正文是空的。'; return; }
  $('card-msg').textContent = '在存…';
  post('/api/cards', {
    name: name,
    hosts: $('card-hosts').value,
    content: $('card-content').value,
    kind: kind,
  }).then(function (data) {
    $('card-name').value = '';
    $('card-hosts').value = '';
    $('card-content').value = '';
    STATE.on[kind] = true;
    STATE.pick[kind] = data.id;
    return refresh().then(function () {
      closeModal('card-modal');
      renderSlots(); renderPlan();
      say(['卡片已保存：' + data.id, '种类：' + KIND[kind].name, '已经帮你勾上、选好了。'], 'good');
      toast('✓ 存好了' + KIND[kind].name + '「' + data.id + '」，这次就用它', 'good');
      note('卡片存好了：' + data.id);
      flash($('new-' + kind), true);
    });
  }).catch(function (e) {
    $('card-msg').textContent = e.message;
    toast('✗ 没存成：' + e.message, 'bad');
  });
};

$('btn-save-host').onclick = function () {
  $('host-msg').textContent = '在加…';
  post('/api/hosts/add', { name: $('host-name').value, home: $('host-path').value })
    .then(function () {
      closeModal('host-modal');
      toast('✓ 加进名单了', 'good');
      return refresh();
    })
    .then(function () {
      $('host-msg').textContent = '';
      flash($('btn-add-host'), true);
    })
    .catch(function (e) {
      $('host-msg').textContent = e.message;
      toast('✗ 没加上：' + e.message, 'bad');
    });
};

$('btn-close-card').onclick = function () { closeModal('card-modal'); };
$('btn-close-view').onclick = function () { closeModal('view-modal'); };
$('btn-close-host').onclick = function () { closeModal('host-modal'); };
['card-modal', 'view-modal', 'host-modal'].forEach(function (id) {
  $(id).onclick = function (ev) { if (ev.target === $(id)) closeModal(id); };
});
document.addEventListener('keydown', function (ev) {
  if (ev.key !== 'Escape') return;
  closeModal('card-modal'); closeModal('view-modal'); closeModal('host-modal');
});

// ---------------------------------------------------------------- 开关

// 只有这颗开关能开关。槽位标题行不再挂任何点击 —— 整行可点必然误触。
// 中枢段没有卡片、没有「＋新建」；底模和指引各有各的。
['hub', 'base', 'guest'].forEach(function (key) {
  $('sw-' + key).onclick = function () { toggle(key); };
  const nb = $('new-' + key);
  if (nb) { nb.onclick = function () { openCard(key, 'new', ''); }; }
});

function toggle(key) {
  STATE.on[key] = !STATE.on[key];
  renderSlots(); renderPlan();
  const label = { hub: '中枢内核', base: '底模', guest: '客套指引' }[key];
  if (['base', 'guest'].indexOf(key) >= 0 && STATE.on[key] && !STATE.pick[key]) {
    // 不再“自动挑最近一张”：那是主人没选过的卡，闷头写进去他不会知道。
    // 只提示该选一张，选没选由他点磁贴上的「用这张」。
    say([label + '开关开了，还没选卡。', '点磁贴上那张的「用这张」，或者点它头上那个「＋ 新建」。'], '');
  }
  const picked = (key === 'hub') ? '' : (STATE.pick[key] ? '，用 ' + STATE.pick[key] : '');
  const text = label + (STATE.on[key] ? '：开' : '：关') + picked;
  note(text);
  toast(text);
  if (key !== 'hub' && STATE.on[key] && !cardsOf(key).length) {
    say([label + '开关开了，但一张卡都没有。', '点它头上那个「＋ 新建」写一张。'], '');
  }
}

// ---------------------------------------------------------------- 名单操作

const btnKill = $('btn-kill-host');
if (btnKill) {
  btnKill.onclick = function () {
    const h = selectedHost();
    if (!h || !h.running) return;
    const pids = h.pids || [];
    const count = pids.length;
    const msg = '确定要强制关闭「' + h.name + '」的后台进程吗？\n'
      + (count ? '共 ' + count + ' 个进程 (PID: ' + pids.join('、') + ')' : '')
      + '\n\n强制关闭后，即可解锁载入/卸回操作。';
    if (!window.confirm(msg)) return;

    setBusy(true);
    btnKill.disabled = true;
    post('/api/hosts/kill', { id: h.id }).then(function (res) {
      const killedCount = (res.killed || []).length;
      toast('✓ 已强制关闭 ' + h.name + ' 的 ' + killedCount + ' 个进程');
      return refresh();
    }).catch(function (e) {
      toast('✗ 强制关闭失败：' + e.message, 'bad');
    }).finally(function () {
      setBusy(false);
    });
  };
}

$('btn-hide-host').onclick = function () {
  const h = selectedHost();
  if (!h) return;
  if (!window.confirm('以后别再列「' + h.name + '」？\n只是不在名单里显示，不会动它的家目录。')) return;
  post('/api/hosts/ignore', { home: h.home }).then(function () {
    toast('✓ 以后不列 ' + h.name);
    return refresh();
  }).catch(function (e) { toast('✗ ' + e.message, 'bad'); });
};

$('btn-drop-host').onclick = function () {
  const h = selectedHost();
  if (!h || !h.custom) return;
  if (!window.confirm('把「' + h.name + '」从名单拿掉？\n只改名单，不动它的家目录。')) return;
  post('/api/hosts/remove', { id: h.id }).then(function () {
    STATE.selected = '';
    toast('✓ 拿掉了 ' + h.name);
    return refresh();
  }).catch(function (e) { toast('✗ ' + e.message, 'bad'); });
};

$('btn-add-host').onclick = openHostForm;

$('btn-deep').onclick = function () {
  const b = $('btn-deep');
  b.disabled = true;
  b.textContent = '深扫中…';
  note('正在把整台盘按入口文件名兜一遍，可能要几秒。');
  toast('深扫中…');
  // 不把 STATE.deep 挂上：深浅结果进的是同一份缓存（hosts.py discover_extra 末尾），
  // 挂上去会让首页每 5 秒重跑一次全盘扫描。深扫是一次性动作。
  api('/api/scan?deep=1').then(function (data) {
    STATE.scan = data.scan;
    renderScanReport(data.scan);
    const n = (data.scan.found || []).length;
    toast(n ? ('✓ 深扫完，名单之外多认出 ' + n + ' 家')
            : ('✓ 深扫完，滤掉的 ' + (data.scan.filtered || 0) + ' 个都不是家目录'), 'good');
    return refresh();
  }).catch(function (e) {
    toast('✗ 深扫没成：' + e.message, 'bad');
    note('深扫没成：' + e.message);
    return null;
  }).then(function () {
    b.disabled = false;
    b.textContent = '深扫全盘';
  });
};

// ---------------------------------------------------------------- 主循环

// 「刷新」和「重扫」以前是同一个函数：点了像有反应，其实什么也没多做。
// 分工：刷新 = 重读一遍状态；重扫 = 真的按入口文件重扫一遍，并把扫到/跳过什么说清楚。
$('btn-refresh').onclick = function () { note('重读状态…'); refresh(); };
$('btn-scan').onclick = function () {
  const b = $('btn-scan');
  b.disabled = true;
  note('按入口文件重扫家目录…');
  toast('重扫中…');
  api('/api/scan').then(function (data) {
    STATE.scan = data.scan;
    renderScanReport(data.scan);
    const n = (data.scan.found || []).length;
    toast(n ? ('✓ 重扫完，名单之外有 ' + n + ' 家') : '✓ 重扫完，没多认出来', 'good');
    return refresh();
  }).catch(function (e) {
    toast('✗ 重扫没成：' + e.message, 'bad');
  }).then(function () { b.disabled = false; });
};
$('show-all').onchange = function () { STATE.showAll = $('show-all').checked; refresh(); };
$('btn-load').onclick = function () { act('load'); };
$('btn-unload').onclick = function () { act('unload'); };
$('btn-lock').onclick = function () { act('snapshot'); };
$('btn-verify').onclick = function () { act('verify'); };
$('btn-restore').onclick = function () { act('restore'); };

function refresh() {
  // 状态不带 deep：深扫结果自己从 /api/scan 拿，不跟着轮询走。
  // 名单带 deep：深扫新认出来的家，得马上出现在左边。
  const qs = function (extra) { return (extra ? '?' : '') + extra; };
  const deep = STATE.deep ? 'deep=1' : '';
  const hostQs = [STATE.showAll ? 'all=1' : '', deep].filter(Boolean).join('&');
  // 竞态守卫：先发的慢响应不许盖掉后发的新结果。
  const seq = ++STATE.seq;
  const stale = function () { return seq !== STATE.seq; };
  return api('/api/status').then(function (st) {
    if (stale()) return null;
    STATE.status = st;
    STATE.cards = st.cards || [];
    return api('/api/hosts' + qs(hostQs));
  }).then(function (h) {
    if (stale() || !h) return null;
    STATE.hosts = h.hosts || [];
    if (!selectedHost()) {
      const first = STATE.hosts.filter(function (x) { return x.exists; })[0];
      STATE.selected = first ? first.id : '';
    }
    const counts = (STATE.status && STATE.status.counts) || {};
    const pkg = (STATE.status && STATE.status.package) || {};
    $('top-state').textContent = !pkg.ready ? '打包器未就绪'
      : (STATE.status.process_probe_known === false ? '运行态读不到' : '打包器就绪');
    $('top-state').className = 'chip' + (pkg.ready ? '' : ' chip-bad');
    $('top-counts').textContent = '机器上 ' + (counts.hosts_present || 0) + ' 家 · 中枢已进 '
      + (counts.hosts_installed || 0) + ' 家 · 常驻 ' + (counts.core_kb || 0) + ' KB · 卡片 '
      + STATE.cards.length + ' 张'
      + (STATE.status.cards_parked ? '（池子外停用 ' + STATE.status.cards_parked + ' 张）' : '')
      + (counts.hosts_custom ? '（手加 ' + counts.hosts_custom + ' 家）' : '');
    renderHosts(); renderHero(); renderSlots(); renderPlan(); renderLocks();
    const sel = selectedHost();
    if (sel) {
      return api('/api/safebox?host_id=' + encodeURIComponent(sel.id)).then(function (lk) {
        if (stale()) return null;
        STATE.locks[sel.id] = lk;
        renderLocks();
        return null;
      });
    }
    return null;
  }).catch(function (e) {
    if (stale()) return null;   // 旧请求的失败也不该去改顶栏
    $('top-state').textContent = '连不上本机服务';
    $('top-state').className = 'chip chip-bad';
    say(['连不上本机服务：' + e.message,
         '把地址栏里那串 ?t=… 一起带上，或点终端里打出来的那一行地址。'], 'bad');
    return null;
  });
}

refresh();
window.setInterval(function () {
  // 弹层开着不刷：不然主人正在写的东西会被后台重画掉。
  if (!STATE.busy && !anyModalOpen()) refresh();
}, 5000);
