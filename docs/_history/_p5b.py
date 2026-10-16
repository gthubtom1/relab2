# -*- coding: utf-8 -*-
"""P5: README 规模表去掉手写数字（与 scale 行重复 → 会腐烂）。

问题（外部审查实证）：check-readme-scale.py 只核对 HTML 注释里的字段，
README 展示表格里的 `57 顶层 + 6 嵌套` 是手写的第二份数字 —— 改回
`50 / 42 / ~2500 / ~25 MB` 门仍会 PASS。
修法：表格只写"口径说明"，数字一律来自上方 scale 行（唯一数字源）。
"""
import io

P = 'README.md'
NL = '\r\n'
raw = io.open(P, encoding='utf-8-sig', newline='').read()

OLD = NL.join([
    "| \u9879 | \u6570\u91cf |",
    "|---|---|",
    "| \u6280\u80fd\u6a21\u5757 | 57 \u9876\u5c42 + 6 \u5d4c\u5957\uff08\u89c1\u4e0a\u65b9 scale \u884c\uff09 |",
    "| \u884c\u4e3a\u5361\u7247 | 10\uff08base 5 + guest 1 + hub 4\uff0c\u89c1\u4e0a\u65b9 scale \u884c\uff09 |",
    "| \u672c\u4ed3\u5e93 | 3083 \u4e2a\u8ddf\u8e2a\u6587\u4ef6 / 43.0 MB\uff08\u89c1\u4e0a\u65b9 scale \u884c\uff09 |",
    "| \u5de5\u5177\u6839 `D:\\Tools` | \u672c\u673a\u5b9e\u6d4b 10.23 GB\uff08\u5546\u4e1a\u5de5\u5177\uff0c\u4fbf\u643a\u7248\uff0c**\u4e0d\u968f\u672c\u4ed3\u5e93\u5206\u53d1**\uff09 |",
])
NEW = NL.join([
    "| \u9879 | \u53e3\u5f84\uff08\u6570\u5b57\u7edf\u4e00\u89c1\u4e0a\u65b9 scale \u884c\uff0c\u672c\u8868\u4e0d\u91cd\u590d\uff09 |",
    "|---|---|",
    "| \u6280\u80fd\u6a21\u5757 | \u9876\u5c42\u6280\u80fd + \u5d4c\u5957\u6280\u80fd\uff08skills_top + skills_nested\uff09 |",
    "| \u884c\u4e3a\u5361\u7247 | base + guest + hub \u4e09\u4e2a\u6c60\u5b50\uff08cards_active\uff09 |",
    "| \u672c\u4ed3\u5e93 | \u8ddf\u8e2a\u6587\u4ef6\u6570 + \u4f53\u79ef\uff08tracked_files / tracked_mb\uff09 |",
    "| \u5de5\u5177\u6839 `D:\\Tools` | \u5546\u4e1a\u5de5\u5177\uff0c\u4fbf\u643a\u7248\uff0c**\u4e0d\u968f\u672c\u4ed3\u5e93\u5206\u53d1**\uff08\u4f53\u79ef\u56fa\u7136\u968f\u673a\uff0c\u4e0d\u5f52\u5165 scale \u884c\uff09 |",
])
assert OLD in raw, 'README table anchor missing'
raw = raw.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8', newline='').write(raw)
print('README table de-duplicated')

# 同时让门也核对「表格里不得再出现手写 scale 数字」
GP = 'skillpack/skills/tests/check-readme-scale.py'
g = io.open(GP, encoding='utf-8-sig', newline='').read()
if 'TABLE_DUP' not in g:
    anchor = "def main(argv=None) -> int:"
    add = '''TABLE_DUP = [
    r"\\|\\s*\u6280\u80fd\u6a21\u5757\\s*\\|\\s*\\d+",
    r"\\|\\s*\u884c\u4e3a\u5361\u7247\\s*\\|\\s*\\d+",
    r"\\|\\s*\u672c\u4ed3\u5e93\\s*\\|\\s*\\d+",
]


def check_table_dup():
    """README \u5c55\u793a\u8868\u91cc\u4e0d\u5f97\u518d\u51fa\u73b0\u624b\u5199\u7684 scale \u6570\u5b57\uff08\u7b2c\u4e8c\u4efd\u6570\u5b57\u6e90\uff09\u3002"""
    text = _read(README_PATH)
    bad = []
    for pat in TABLE_DUP:
        for m in re.finditer(pat, text):
            bad.append("README \u8868\u683c\u91cc\u7684\u624b\u5199\u6570\u5b57\uff08\u4e0e scale \u884c\u91cd\u590d\uff0c\u4f1a\u8150\u70c2\uff09\uff1a%r"
                       % m.group(0)[:60])
    return bad


'''
    g = g.replace(anchor, add + anchor, 1)
    g = g.replace("    errs, n = check()",
                  "    errs, n = check()\n    errs += check_table_dup()", 1)
    io.open(GP, 'w', encoding='utf-8', newline='').write(g)
    print('gate now also checks the table')
else:
    print('gate already has table check')
