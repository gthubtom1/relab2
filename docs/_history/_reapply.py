# -*- coding: utf-8 -*-
"""在已恢复的 relab2.ps1（HEAD + BOM/CRLF）上重新应用两块：
  P12  WARN 文案带后果说明
  P7   漂移门委派给 check-card-drift.py（单块替换，不碰别处）
保持 BOM + CRLF。
"""
import io

P = 'relab2.ps1'
NL = '\r\n'

t = io.open(P, encoding='utf-8-sig', newline='').read()

# ---------------- P12 ----------------
OLD12 = "    else { Add-Result 'REVERSE_SKILL_ROOT' 'WARN' '\u672a\u8bbe\u7f6e\uff08\u8dd1 setup \u6216 relab2-root.ps1\uff09' }"
NEW12 = ("    else { Add-Result 'REVERSE_SKILL_ROOT' 'WARN' "
         "'\u672a\u8bbe\u7f6e\uff08\u8dd1 setup \u6216 relab2-root.ps1\uff09\u2014\u2014\u6b64\u65f6\u5361\u7247\u5151\u5e95\u503c\u4e3a "
         "C:\\relab2\uff1b\u82e5\u672c\u673a\u4e0d\u5728\u90a3\u4e2a\u8def\u5f84\u4e0b\uff0c\u6a21\u578b\u4f1a\u7528\u9519\u8335\u6811' }")
assert OLD12 in t, 'P12 anchor missing'
t = t.replace(OLD12, NEW12, 1)
print('P12 reapplied')

# ---------------- P7 ----------------
OLD7 = NL.join([
    "    # 7b \u2605 \u88c5\u673a\u5361 vs \u4ed3\u5e93\u5361\u7684\u6f02\u79fb",
])
i = t.find(OLD7)
assert i >= 0, 'P7 anchor missing'
# \u627e\u5230\u8be5\u5757\u7ed3\u675f\uff1a'    else { Add-Result \'\u88c5\u673a\u5361\u6f02\u79fb\' \'OK\''
END = "        Add-Result '\u88c5\u673a\u5361\u6f02\u79fb' 'OK' '\u5bbf\u4e3b\u5165\u53e3\u6587\u4ef6\u4e0e\u4ed3\u5e93\u5361\u9010\u884c\u4e00\u81f4'"
j = t.find(END, i)
assert j >= 0, 'P7 end anchor missing'
j_end = t.find('\n', t.find('}', j)) + 1

NEW7 = NL.join([
    "    # 7b \u2605 \u88c5\u673a\u5361 vs \u4ed3\u5e93\u5361\u7684\u6f02\u79fb\u3002",
    "    #   2026-10-15 \u5ba1\u8ba1\u5b9e\u6d4b\uff1a\u5bbf\u4e3b PERSONALITY.md \u6bd4\u4ed3\u5e93\u5361\u65e7 6 \u884c\uff0c\u800c\u6b64\u524d\u6ca1\u4efb\u4f55\u95e8\u7981\u5728\u770b\u3002",
    "    # \u2605 P7\uff082026-10-15\uff09\uff1a\u6539\u7531\u72ec\u7acb Python \u811a\u672c\u505a\uff0c\u76f4\u63a5 import hosts.py \u7684 HOSTS\u3002",
    "    #   \u4e0d\u518d\u5728 relab2.ps1 \u91cc\u590d\u5236\u4e00\u4efd\u5bbf\u4e3b\u8868\uff08PS \u526a\u7247\u628a omp \u7684 entry_base \u89e3\u6210\u7a7a\u7ffb\u8fc7\u8f66\uff09\u3002",
    "    $py = $null",
    "    foreach ($cand in @((Get-Command python -ErrorAction SilentlyContinue).Source,",
    "                        (Get-Command py -ErrorAction SilentlyContinue).Source)) {",
    "        if ($cand) { $py = $cand; break }",
    "    }",
    "    if ($py) {",
    "        $o = & $py (Join-Path $RepoRoot 'skillpack\\skills\\scripts\\check-card-drift.py') -Json 2>&1",
    "        $rc = $LASTEXITCODE",
    "        if ($rc -eq 0) {",
    "            Add-Result '\u88c5\u673a\u5361\u6f02\u79fb' 'OK' '\u5df2\u88c5\u5bbf\u4e3b\u5165\u53e3\u6587\u4ef6\u4e0e\u4ed3\u5e93\u5361\u9010\u884c\u4e00\u81f4'",
    "        }",
    "        elseif ($rc -eq 10) {",
    "            $o | Select-Object -Last 12 | ForEach-Object { Write-Host ('      ' + $_) -ForegroundColor Yellow }",
    "            Add-Result '\u88c5\u673a\u5361\u6f02\u79fb' 'WARN' '\u90e8\u5206\u5bbf\u4e3b\u5165\u53e3\u6587\u4ef6\u4e0e\u4ed3\u5e93\u5361\u4e0d\u4e00\u81f4\uff08\u539f\u56de\u4e0a\u65b9\u884c\uff09'",
    "        }",
    "        else {",
    "            $o | Select-Object -Last 8 | ForEach-Object { Write-Host ('      ' + $_) -ForegroundColor Red }",
    "            Add-Result '\u88c5\u673a\u5361\u6f02\u79fb' 'WARN' \"\u6f02\u79fb\u68c0\u67e5\u672c\u8eab\u8dd1\u5931\u8d25\uff08rc=$rc\uff09\"",
    "        }",
    "    }",
    "    else {",
    "        Add-Result '\u88c5\u673a\u5361\u6f02\u79fb' 'WARN' 'PATH \u91cc\u6ca1\u6709 python\uff0c\u8df3\u8fc7'",
    "    }",
    "",
])
t = t[:i] + NEW7 + t[j_end:]
out = ('\ufeff' + t).encode('utf-8')
out = out.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
io.open(P, 'wb').write(out)
print('P7 reapplied; bytes', len(out))
