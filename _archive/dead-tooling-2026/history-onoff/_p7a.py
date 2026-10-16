# -*- coding: utf-8 -*-
"""P7: 装机卡漂移门从「只查 .omp/agent」扩到 hosts.py 里全部已装宿主。

旧代码把宿主目录写死成 `~/.omp/agent`（relab2.ps1:210），只比 PERSONALITY.md /
RULES.md。主人明确要「今天 omp，明天 Claude Code / Cursor / Codex / Gemini CLI」，
换了宿主这道门就形同不存在，而它正是修「仓库改好了、机器上还是旧的」那件事的。

做法：从 kernel/03-bundle/hosts.py 的 HOSTS 表生成宿主清单，
对每个「家目录真实存在」的宿主比对其入口文件（含 entry_base）与
kernel/04-console/cards/base|guest 里的仓库卡。
"""
import io
import re

HOSTS_PY = 'kernel/03-bundle/hosts.py'
PS = 'relab2.ps1'

# 解析 HostSpec("id", "display", "rel", "entry", ..., entry_base="X")
ROW = re.compile(
    r'HostSpec\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"'
    r'(?P<rest>.*?)\)\s*,?', re.S)

rows = []
t = io.open(HOSTS_PY, encoding='utf-8-sig').read()
start = t.index('HOSTS = (')
end = t.index('BY_ID', start)
for m in ROW.finditer(t[start:end]):
    hid, disp, rel, entry = m.group(1), m.group(2), m.group(3), m.group(4)
    rest = m.group('rest')
    eb = re.search(r'entry_base\s*=\s*"([^"]+)"', rest)
    rows.append((hid, rel, entry, eb.group(1) if eb else ''))
if len(rows) < 10:
    raise SystemExit('parsed only %d hosts' % len(rows))
print('parsed hosts:', len(rows))

# 生成 PowerShell 的宿主表字面量
ps_rows = []
for hid, rel, entry, eb in rows:
    ps_rows.append(
        "    @{ id = '%s'; rel = '%s'; entry = '%s'; entry_base = '%s' }"
        % (hid, rel.replace("'", "''"), entry.replace("'", "''"),
           eb.replace("'", "''")))
PS_TABLE = "    @(\n" + "\n".join(ps_rows) + "\n    )"

raw = io.open(PS, encoding='utf-8-sig', newline='').read()
NL = '\r\n'

OLD = NL.join([
    "    $hostAgentDir = Join-Path $env:USERPROFILE '.omp\\agent'",
    "    $cardDirs = @((Join-Path $RepoRoot 'kernel\\04-console\\cards\\base'),",
    "                  (Join-Path $RepoRoot 'kernel\\04-console\\cards\\guest'))",
])
NEW = NL.join([
    "    # \u2605 P7\uff082026-10-15\uff09\uff1a\u6cbb\u75db\u65b0\u7684\u6f02\u79fb\u95e8\u3002\u65e7\u4ee3\u7801\u628a\u5bbf\u4e3b\u5199\u6b7b\u6210 .omp/agent\uff0c",
    "    #   \u6362 Claude Code / Cursor / Codex \u5c31\u5f62\u540c\u4e0d\u5b58\u5728\u3002",
    "    #   \u73b0\u5728\u6309 hosts.py \u7684 HOSTS \u8868\u904d\u5386\uff0c\u53ea\u770b\u5bbf\u4e3b\u5bb6\u76ee\u5f55\u771f\u5b9e\u5b58\u5728\u7684\u3002",
    "    $hostTable = @(",
])
# 我们把 $hostTable 直接展开成生成的表
NEW = NL.join([
    "    # \u2605 P7\uff082026-10-15\uff09\uff1a\u6cbb\u75db\u65b0\u7684\u6f02\u79fb\u95e8\u3002",
    "    #   \u65e7\u4ee3\u7801\u628a\u5bbf\u4e3b\u5199\u6b7b\u6210 .omp/agent\uff0c\u6362 Claude Code / Cursor / Codex \u5c31\u5f62\u540c\u4e0d\u5b58\u5728\u3002",
    "    $hostTable =",
    PS_TABLE,
    "    $cardDirs = @((Join-Path $RepoRoot 'kernel\\04-console\\cards\\base'),",
    "                  (Join-Path $RepoRoot 'kernel\\04-console\\cards\\guest'))",
])
assert OLD in raw, 'P7 anchor missing'
raw = raw.replace(OLD, NEW, 1)
io.open(PS, 'w', encoding='utf-8', newline='').write(raw)
print('hostTable wired')
