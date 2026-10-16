# -*- coding: utf-8 -*-
"""P3: 让 check-prompt-budget 与 register-skills 用同一口径（递归），并加一道门禁。"""
import io
NL='\r\n'
P='skillpack/skills/scripts/check-prompt-budget.py'
t=io.open(P,encoding='utf-8-sig',newline='').read()
old = "        return sorted(glob.glob(os.path.join(SKILLS_ROOT, '*/SKILL.md')))"
new = ("        # \u2605 2026-10-15 \u5ba1\u8ba1 P3\uff1a\u4ee5\u524d\u53ea\u770b\u4e00\u5c42\uff0c\u5d4c\u5957\u6280\u80fd\uff08community/* \u7b49 6 \u4e2a\uff09"
       "\u4e0d\u88ab\u7edf\u8ba1\u3002\n"
       "        #   register-skills.ps1 \u5df2\u6539\u6210\u9012\u5f52\u679a\u4e3e\uff0c\u8fd9\u91cc\u5fc5\u987b\u540c\u53e3\u5f84\uff0c\u5426\u5219"
       "\u201c\u5df2\u7ba1\u7684\u6280\u80fd\u201d\u548c\u201c\u88ab\u9884\u7b97\u7684\u6280\u80fd\u201d\u4e24\u5957\u6570\u3002\n"
       "        return sorted(glob.glob(os.path.join(SKILLS_ROOT, '**', 'SKILL.md'), recursive=True))")
assert old in t, "anchor not found"
t=t.replace(old,new,1)
io.open(P,'w',encoding='utf-8',newline='').write(t)
print("check-prompt-budget aligned")
