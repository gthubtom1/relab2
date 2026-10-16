# -*- coding: utf-8 -*-
"""P3 step2 收尾：manifest / -Doctor / -Revert 适配「逐技能 link」。

隔离宿主已验证：63 条 link、6 个嵌套指向正确、无别处指向。
剩下三处仍按旧的「整树 junction」语义，必须一起改，否则：
  · manifest 只记 $t.path（现在是实体容器，不是 link）→ 新 link 全漏登
  · -Doctor 只核对整树 → 悬空/错指的 link 查不出来
  · -Revert 只删整树 → 63 条 link 永远摘不掉，换机后成孤儿
"""
import io

P = 'skillpack/skills/scripts/register-skills.ps1'
NL = '\r\n'
raw = io.open(P, encoding='utf-8-sig', newline='').read()

# ---------------- manifest：记录每条 link ----------------
OLD_MF = NL.join([
    "if (-not \$WhatIf -and -not \$Revert) {",
    "    \$entries = @()",
    "    foreach (\$t in \$targets) {",
    "        if (-not \$t.installed) { continue }",
    "        if (-not (Test-Path -LiteralPath \$t.path)) { continue }",
    "        \$tgt = Get-LinkTarget -p \$t.path",
    "        if (-not \$tgt) { continue }",
    "        if ((\& \$norm \$tgt) -ne \$mine) { continue }",
    "        \$entries += [pscustomobject]@{ agent = \$t.agent; scope = \$t.scope; path = \$t.path; target = \$skills }",
    "    }",
])
NEW_MF = NL.join([
    "if (-not \$WhatIf -and -not \$Revert) {",
    "    # \u2605 P3 step2\uff1a\u4e00\u4e2a\u6280\u80fd\u4e00\u6761 link\uff0cmanifest \u4e5f\u6309\u6761\u8bb0\u3002",
    "    #   \u65e7\u5199\u6cd5\u53ea\u8bb0 \$t.path\uff08\u90a3\u662f\u5b9e\u4f53\u5bb9\u5668\u800c\u975e link\uff09\uff0c\u5bfc\u81f4 63 \u6761 link \u5168\u90e3\u767b\u3002",
    "    \$entries = @()",
    "    foreach (\$t in \$targets) {",
    "        if (-not \$t.installed) { continue }",
    "        foreach (\$d in \$skillDirs) {",
    "            \$lp = Join-Path \$t.path \$d.Id",
    "            if (-not (Test-Path -LiteralPath \$lp)) { continue }",
    "            \$tgt = Get-LinkTarget -p \$lp",
    "            if (-not \$tgt) { continue }",
    "            if ((\& \$norm \$tgt) -ne (\& \$norm \$d.Directory)) { continue }",
    "            \$entries += [pscustomobject]@{ agent = \$t.agent; scope = \$t.scope",
    "                                             path = \$lp; target = \$d.Directory",
    "                                             skillId = \$d.Id; nested = [bool]\$d.Nested }",
    "        }",
    "    }",
])
assert OLD_MF in raw, 'manifest anchor missing'
raw = raw.replace(OLD_MF, NEW_MF, 1)
print('manifest now records every link')

# ---------------- Doctor：逐条核对 ----------------
OLD_DR = NL.join([
    "    \$rows = New-Object System.Collections.Generic.List[object]",
    "    \$recorded = @()",
    "    if (Test-Path -LiteralPath \$manifestPath) {",
    "        try {",
    "            \$mf = Get-Content -LiteralPath \$manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json",
    "            \$recorded = @(\$mf.entries)",
    "        } catch { Write-Host (\"WARN: \u6e05\u5355\u89e3\u6790\u5931\u8d25 {0}\" -f \$manifestPath) -ForegroundColor Yellow }",
    "    }",
    "    foreach (\$e in \$recorded) {",
    "        \$st = 'OK'",
    "        if (-not (Test-Path -LiteralPath \$e.path)) { \$st = 'DANGLING(\u8def\u5f84\u4e0d\u5b58\u5728)' }",
    "        else {",
    "            \$t = Get-LinkTarget -p \$e.path",
    "            if (-not \$t) { \$st = 'NOT_A_LINK(\u88ab\u5b9e\u4f53\u76ee\u5f55\u9876\u66ff)' }",
    "            elseif ((\& \$norm \$t) -ne \$mine) { \$st = ('MISMATCH(\u6307\u5411 {0})' -f \$t) }",
    "        }",
    "        \$rows.Add([pscustomobject]@{ agent = \$e.agent; path = \$e.path; state = \$st })",
    "    }",
])
NEW_DR = NL.join([
    "    \$rows = New-Object System.Collections.Generic.List[object]",
    "    \$recorded = @()",
    "    if (Test-Path -LiteralPath \$manifestPath) {",
    "        try {",
    "            \$mf = Get-Content -LiteralPath \$manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json",
    "            \$recorded = @(\$mf.entries)",
    "        } catch { Write-Host (\"WARN: \u6e05\u5355\u89e3\u6790\u5931\u8d25 {0}\" -f \$manifestPath) -ForegroundColor Yellow }",
    "    }",
    "    # \u2605 P3 step2\uff1a\u9010\u6761\u6838\u5bf9\u3002target \u6bd4\u7684\u4e0d\u518d\u662f\u6280\u80fd\u6839\uff0c\u800c\u662f\u8be5\u6280\u80fd\u81ea\u5df1\u7684\u76ee\u5f55\u3002",
    "    foreach (\$e in \$recorded) {",
    "        \$st = 'OK'",
    "        \$want = if (\$e.PSObject.Properties['target']) { \$e.target } else { \$skills }",
    "        if (-not (Test-Path -LiteralPath \$e.path)) { \$st = 'DANGLING(\u8def\u5f84\u4e0d\u5b58\u5728)' }",
    "        else {",
    "            \$t = Get-LinkTarget -p \$e.path",
    "            if (-not \$t) { \$st = 'NOT_A_LINK(\u88ab\u5b9e\u4f53\u76ee\u5f55\u9876\u66ff)' }",
    "            elseif ((\& \$norm \$t) -ne (\& \$norm \$want)) { \$st = ('MISMATCH(\u6307\u5411 {0})' -f \$t) }",
    "        }",
    "        \$rows.Add([pscustomobject]@{ agent = \$e.agent; path = \$e.path; state = \$st })",
    "    }",
])
assert OLD_DR in raw, 'Doctor anchor missing'
raw = raw.replace(OLD_DR, NEW_DR, 1)
print('Doctor now checks per-link targets')

io.open(P, 'w', encoding='utf-8', newline='').write(raw)
print('steps done')
