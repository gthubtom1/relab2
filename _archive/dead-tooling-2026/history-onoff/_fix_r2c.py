# -*- coding: utf-8 -*-
"""P4: make check_r2 call the single production judge (_r2_sentence_judge)
so the gate and the control group can never drift apart again."""
import io

P = 'skillpack/skills/tests/verify-project-requirements.py'
raw = io.open(P, encoding='utf-8-sig', newline='').read()

OLD = '''    errs = []
    for p in _skill_files():
        txt = _read(p)
        name = os.path.basename(os.path.dirname(p))
        for m in re.finditer(r"[^\\n]*", txt):
            line = m.group(0)
            if not line.strip():
                continue
            for sent in _sentences(line):
                # \u6574\u53e5\u5c31\u662f\u53cd\u62d2\u7b54\u786e\u8ba4 \u2192 \u8fd9\u4e00\u53e5\u653e\u884c
                if any(re.search(w, sent) for w in REBUTTAL_FULL):
                    continue
                # \u65e7\u7684\u884c\u5185\u767d\u540d\u5355\u4f5c\u4e3a\u5151\u5e52\u7f6e\uff1a\u6574\u884c\u5168\u90e8\u53ea\u542b\u53cd\u62d2\u7b54\u8bed\u4e49\u65f6\u624d\u8df3\u8fc7\u6574\u884c
                if all(any(re.search(w, s) for w in REBUTTAL_WHITELIST)
                       for s in _sentences(line)) and _sentences(line):
                    continue
                for pat, why in STOPGATE_PATTERNS:
                    if re.search(pat, sent):
                        ln = txt[:m.start()].count("\\n") + 1
                        errs.append(f"\u94c1\u5f8b\u2461 {name}/SKILL.md:{ln} {why}\uff1a{sent.strip()[:70]!r}")
                        break
    return errs'''

NEW = '''    errs = []
    for p in _skill_files():
        txt = _read(p)
        name = os.path.basename(os.path.dirname(p))
        for m in re.finditer(r"[^\\n]*", txt):
            line = m.group(0)
            if not line.strip():
                continue
            if not _r2_sentence_judge(line):
                continue
            # \u62a5\u9519\u65f6\u628a\u5177\u4f53\u547d\u4e2d\u7684\u90a3\u4e00\u53e5\u6253\u51fa\u6765\uff08\u4e0d\u6253\u6574\u884c\uff0c\u907f\u514d\u628a\u5408\u89c4\u53e5\u4e00\u5e26\u62a5\u4e0a\uff09
            for sent in _sentences(line):
                for pat, why in STOPGATE_PATTERNS:
                    if re.search(pat, sent):
                        ln = txt[:m.start()].count("\\n") + 1
                        errs.append(f"\u94c1\u5f8b\u2461 {name}/SKILL.md:{ln} {why}\uff1a{sent.strip()[:70]!r}")
                        break
                else:
                    continue
                break
    return errs'''

assert OLD in raw, "check_r2 body anchor not found"
raw = raw.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8', newline='').write(raw)
print("check_r2 now delegates to _r2_sentence_judge")
