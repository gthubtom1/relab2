import io
NL='\r\n'
P='skillpack/skills/scripts/capability-index.py'
lines=io.open(P,encoding='utf-8-sig',newline='').read().split(NL)
# 1) 删掉上一轮插错位置的块（从"全覆盖断言（外部审查追问）"到"extra = sampled"之后一行）
start=None
for k,l in enumerate(lines):
    if 'fails.append(f"\u80fd\u529b {cap} \u53ea\u6709 {per.get(cap, 0)} \u6761 help \u6b63\u5219"' in l:
        start=k; break
if start is None:
    raise SystemExit("misplaced block not found")
# 往上吞到注释头
b=start
while b>0 and (lines[b-1].strip().startswith('#') or lines[b-1].strip().startswith('from collections') or lines[b-1].strip().startswith('sampled =') or lines[b-1].strip().startswith('per =')):
    b-=1
e=start
while e+1<len(lines) and not lines[e+1].strip()=='' and 'UnboundLocalError' not in lines[e+1]:
    e+=1
# 结束条件：遇到 '    if fails:' 或函数结束
for k in range(start, len(lines)):
    if lines[k].strip()=='if fails:' or lines[k].startswith('def '):
        e=k; break
print("removing lines", b, "to", e-1)
print("  first:", repr(lines[b])[:60], "| last:", repr(lines[e-1])[:60])
del lines[b:e]
# 2) 在 selftest_help 的 'fails: list[str] = []' 之后插回
i=next(k for k,l in enumerate(lines) if l.startswith('def selftest_help'))
j=next(k for k in range(i,len(lines)) if lines[k].strip()=='fails: list[str] = []')
add = [
 '',
 '    # \u5168\u8986\u76d6\u65ad\u8a00\uff08\u5916\u90e8\u5ba1\u8ba1\u8ffd\u95ee\uff09\uff1a',
 '    #   \u00b7 \u6bcf\u4e2a\u80fd\u529b\u81f3\u5c11 2 \u6761 help \u6b63\u5219\uff08<2 \u65f6 classify_by_help \u7684 >=2 \u9608\u503c\u7ed3\u6784\u4e0a\u6c38\u8fdc\u547d\u4e2d\uff09\uff1b',
 '    #   \u00b7 \u6bcf\u4e2a\u80fd\u529b\u90fd\u6709\u6b63\u5411\u6837\u672c\uff08\u5757\u6389\u4e86\u4e5f\u6ca1\u4eba\u77e5\u9053\uff09\u3002',
 '    #   2026-10-15 \u4e4b\u524d 17/4 \u4e2a\u80fd\u529b\u6ca1\u6709\u5151\u5e95\u6b63\u5219\uff0c\u800c\u6beb\u65e0\u95e8\u7981\u62a5\u9519\u3002',
 '    from collections import Counter as _C',
 '    per = _C(c for _, c in HELP_HINTS)',
 '    sampled = set(w for _t, w in HELP_POSITIVE_CASES.values())',
 '    for cap in CAPABILITIES:',
 '        if per.get(cap, 0) < 2:',
 '            fails.append(f"\u80fd\u529b {cap} \u53ea\u6709 {per.get(cap, 0)} \u6761 help \u6b63\u5219"',
 '                         f"\uff08<2 \u65f6\u8be5\u8def\u5f84\u7ed3\u6784\u4e0a\u6c38\u8fdc\u547d\u4e2d\uff09")',
 '        if cap not in sampled:',
 '            fails.append(f"\u80fd\u529b {cap} \u6ca1\u6709\u6b63\u5411\u6837\u672c\uff08\u5757\u6389\u4e86\u4e5f\u6ca1\u4eba\u77e5\u9053\uff09")',
 '    extra = sampled - set(CAPABILITIES)',
 '    if extra:',
 '        fails.append(f"\u6837\u672c\u6307\u5411\u4e0d\u5b58\u5728\u7684\u80fd\u529b\uff1a{sorted(extra)}")',
]
lines[j+1:j+1]=add
io.open(P,'w',encoding='utf-8',newline='').write(NL.join(lines))
print("re-inserted after fails definition")
