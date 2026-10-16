# -*- coding: utf-8 -*-
"""P3 收尾：Doctor 预期集限定到 manifest 登记的根，且有问题时 exit 非零。

两个已实证的缺陷：
  1) 预期集用 `$targets`（含一次性 -ProjectRoot 目标）→ 删 1 条报 63 个 MISSING，
     把"未登记的宿主"也算进预期，数字不可信。
  2) `-Doctor` 即使 $dangling.Count -gt 0 也固定 exit 0 → CI/doctor 门看不到它变红。
"""
import io

P = 'skillpack/skills/scripts/register-skills.ps1'
NL = '\r\n'
raw = io.open(P, encoding='utf-8-sig', newline='').read()

# ---- 1) 预期集改用在 manifest 里出现过的根 + 已装宿主 ----
OLD_EXP = NL.join([
    "    foreach ($t in $targets) {",
    "        if (-not $t.installed) { continue }",
    "        foreach ($d in $skillDirs) {",
    "            $lp = Join-Path $t.path $d.Id",
    "            $st = $null",
    "            if (-not (Test-Path -LiteralPath $lp)) {",
    "                $st = 'MISSING(\u9884\u671f\u7684 link \u4e0d\u5b58\u5728)'",
    "            }",
])
NEW_EXP = NL.join([
    "    # \u2605 P3\uff1a\u9884\u671f\u96c6\u5408\u53ea\u8986\u76d6**manifest \u91cc\u767b\u8bb0\u8fc7\u7684\u6839**\u3002",
    "    #   \u7528 $targets \u4f1a\u628a\u4e00\u6b21\u6027 -ProjectRoot \u76ee\u6807\u4e5f\u7b97\u8fdb\u53bb\uff1a\u5220 1 \u6761\u5374\u62a5 63 \u4e2a",
    "    #   MISSING\uff08\u5b9e\u6d4b\u53d1\u751f\u8fc7\uff09\uff0c\u6570\u5b57\u4e0d\u53ef\u4fe1\u3002",
    "    $expectedRoots = @($recorded | ForEach-Object {",
    "        $pp = Split-Path -Parent $_.path",
    "        if ($pp) { $pp }",
    "    } | Select-Object -Unique)",
    "    foreach ($er in $expectedRoots) {",
    "        foreach ($d in $skillDirs) {",
    "            $lp = Join-Path $er $d.Id",
    "            $st = $null",
    "            if (-not (Test-Path -LiteralPath $lp)) {",
    "                $st = 'MISSING(\u9884\u671f\u7684 link \u4e0d\u5b58\u5728)'",
    "            }",
])
assert OLD_EXP in raw, 'expected-set anchor missing'
raw = raw.replace(OLD_EXP, NEW_EXP, 1)

# 该块尾部的 $rows.Add 也要改成 $er 对应的 agent
OLD_ADD = NL.join([
    "            if ($st) {",
    "                $rows.Add([pscustomobject]@{ agent = $t.agent; path = $lp; state = $st })",
    "            }",
    "        }",
    "    }",
    "    $dangling = @($rows | Where-Object { $_.state -ne 'OK' })",
])
NEW_ADD = NL.join([
    "            if ($st) {",
    "                $ag = 'unknown'",
    "                foreach ($tt in $targets) {",
    "                    if ((& $norm $tt.path) -eq (& $norm $er)) { $ag = $tt.agent }",
    "                }",
    "                foreach ($e2 in $recorded) {",
    "                    if ((& $norm (Split-Path -Parent $e2.path)) -eq (& $norm $er)) { $ag = $e2.agent }",
    "                }",
    "                $rows.Add([pscustomobject]@{ agent = $ag; path = $lp; state = $st })",
    "            }",
    "        }",
    "    }",
    "    $dangling = @($rows | Where-Object { $_.state -ne 'OK' })",
    "    # \u2605 P3\uff1a\u6709\u95ee\u9898\u5c31 Exit \u975e\u96f6\u2014\u2014\u65e7\u4ee3\u7801\u56fa\u5b9a Exit 0\uff0c\u95e8\u7981\u770b\u4e0d\u89c1\u3002",
    "    if (-not $Json -and $dangling.Count -gt 0) {",
    "        Write-Host ('\u53d1\u73b0 {0} \u5904\u95ee\u9898\uff08\u4e0a\u65b9\u5217\u8868\uff09' -f $dangling.Count) -ForegroundColor Red",
    "    }",
])
assert OLD_ADD in raw, 'rows.Add anchor missing'
raw = raw.replace(OLD_ADD, NEW_ADD, 1)

io.open(P, 'w', encoding='utf-8', newline='').write(raw)
print('Doctor expected-set + exit code fixed')
