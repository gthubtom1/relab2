# -*- coding: utf-8 -*-
"""P6 收尾：把 KNOWN-BOUNDARIES 的不可复算数字改为引用可执行脚本。"""
import io

DOC = 'docs/KNOWN-BOUNDARIES.md'
NL = '\r\n'
raw = io.open(DOC, encoding='utf-8-sig', newline='').read()

OLD_PREFIX = "| 3 | **\u8def\u7531\u57fa\u51c8 227 \u6761\u91cc 223 \u6761\uff0898.24%\uff09\u7684\u95ee\u53e5\u5c31\u662f\u88ab\u6d4b\u5173\u952e\u8bcd\u62fc\u7684**"
i = raw.find(OLD_PREFIX)
if i < 0:
    raise SystemExit('KNOWN-BOUNDARIES row 3 anchor not found')
j = raw.find('\n', i)

NEW = ("| 3 | **\u8def\u7531\u57fa\u51c8\u91cc\u5927\u91cf\u95ee\u53e5\u7531\u88ab\u6d4b\u8def\u7531\u81ea\u5df1\u7684\u5173\u952e\u8bcd\u62fc\u6210** \u2014\u2014 "
       "\u81ea\u5df1\u51fa\u9898\u81ea\u5df1\u8003\uff08\u539f\u6765\u5199\u7684\u300c223/227 = 98.24%\u300d\u7ed9\u4e0d\u51fa\u7b97\u6cd5\uff0c"
       "\u672c\u8f6e\u72ec\u7acb\u5ba1\u67e5\u7528\u4e24\u79cd\u53ef\u590d\u73b0\u5b9a\u4e49\u5206\u522b\u5f97 **25.11% / 62.8%**\uff0c"
       "\u6570\u5b57\u4e0d\u53ef\u590d\u73b0\u5c31\u4e0d\u5f53\u8bc1\u636e\uff09 | \u5ba1\u8ba1\u72ec\u7acb\u590d\u7b97 + "
       "`python skillpack/skills/scripts/route-benchmark-tautology.py` | **\u5df2\u6539\u4e3a\u53ef\u590d\u7b97**\uff1a"
       "\u5224\u636e\u56fa\u5316\u8fdb\u811a\u672c docstring\uff08hint \u7684 token \u226590% \u843d\u5728\u9884\u671f\u8def\u7531\u7684 must/mustAll "
       "\u8bcd\u9879\u8868\u91cc \u21d2 \u81ea\u8bc1\uff09\uff0c\u6587\u6863\u91cc\u4e0d\u518d\u5199\u6b7b\u6570\u5b57\uff1b"
       "\u66ff\u6362\u6210\u771f\u5b9e\u8bed\u6599\u4ecd\u672a\u505a\uff08\u4e3b\u4eba\u539f\u8bdd\u5c31\u662f\u73b0\u6210\u8bed\u6599\uff0c\u89c1 `lcs-core/01`\uff09。")
raw = raw[:i] + NEW + raw[j:]
io.open(DOC, 'w', encoding='utf-8', newline='').write(raw)
print('KNOWN-BOUNDARIES row 3 now cites a reproducible script')
