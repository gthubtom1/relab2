# -*- coding: utf-8 -*-
"""P9 follow-up (external review): the dynamic audit only ran 2 of the 9 watched
scripts, and the static check let any source through if it merely mentioned the
forbidden directory name.

Fix 1: run every watched script the machine can actually execute
        (python ones via this interpreter, .ps1 via pwsh when available),
        instead of a hand-picked pair.
Fix 2: keep the static "mentions the name" rule (it is a cheap necessary
        condition), but the *proof* is now the dynamic run; when a watched
        script could not be run we say so loudly instead of implying coverage.
"""
import io

P = 'skillpack/skills/tests/verify-no-forbidden-reads.py'
NL = '\r\n'
raw = io.open(P, encoding='utf-8-sig', newline='').read()

OLD = '''    python = sys.executable
    targets = [
        [python, os.path.join(SKILLS_ROOT, "scripts", "verify-doc-links.py"), "--json"],
        [python, os.path.join(SKILLS_ROOT, "tests", "verify-project-requirements.py")],
    ]
    ran = 0
    for argv in targets:
        name = os.path.basename(argv[1])
        try:
            subprocess.run(argv, capture_output=True, timeout=timeout, env=env, cwd=SKILLS_ROOT)
            ran += 1
        except (OSError, subprocess.TimeoutExpired) as exc:
            errs.append(f"{name}: \u52a8\u6001\u8dd1\u4e0d\u8d77\u6765\uff08{type(exc).__name__}\uff09\u2014\u2014 \u672c\u6b21\u53ea\u8bc1\u660e\u4e86\u9759\u6001\uff0c\u6ca1\u8bc1\u660e\u8fd0\u884c\u671f")'''

NEW = '''    python = sys.executable
    pwsh = None
    for cand in ("pwsh", "powershell"):
        found = None
        try:
            import shutil as _sh
            found = _sh.which(cand)
        except Exception:
            found = None
        if found:
            pwsh = found
            break

    # \u2605 2026-10-15 \u5916\u90e8\u5ba1\u8ba1\u8ffd\u95ee\uff1a\u4ee5\u524d\u8fd9\u91cc\u53ea\u624b\u6319\u4e24\u4e2a\u811a\u672c\u8dd1\uff0c\u800c WATCHED_SCRIPTS \u6709 9 \u4e2a\u2014\u2014
    #   \u201c\u5176\u4f59\u7684\u95e8\u7981\u53ef\u80fd\u9759\u9ed8\u8bfb\u7981\u533a\u5374\u4e0d\u7ea2\u201d\u3002\u73b0\u5728\u5168\u90e8\u8dd1\uff1apy \u7528\u5f53\u524d\u89e3\u91ca\u5668\uff0c
    #   .ps1 \u8dd1 pwsh\uff08\u6ca1\u6709\u5c31\u660e\u8bf4\u201c\u672a\u8986\u76d6\u201d\uff0c\u4e0d\u4f2a\u88c5\u8986\u76d6\u8fc7\uff09\u3002
    targets = []
    for rel in WATCHED_SCRIPTS:
        ap = os.path.join(MANIFEST_ROOT, rel.replace("/", os.sep))
        if not os.path.isfile(ap):
            continue                      # \u9759\u6001\u68c0\u67e5\u5df2\u7ecf\u62a5\u8fc7\u201c\u5269\u4f59\u540d\u5355\u8fc7\u671f\u201d
        if rel.endswith(".py"):
            argv = [python, ap]
            if rel.endswith("verify-project-requirements.py"):
                argv.append("--selftest")
            elif rel.endswith("verify-doc-links.py"):
                argv.append("--json")
            targets.append((rel, argv))
        elif rel.endswith(".ps1"):
            if pwsh:
                targets.append((rel, [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ap]))
            else:
                errs.append(f"{rel}: \u672c\u673a\u6ca1\u6709 pwsh/powershell\uff0c\u8be5\u811a\u672c\u672a\u88ab\u52a8\u6001\u8986\u76d6"
                            f"\uff08\u9759\u6001\u68c0\u67e5\u4ecd\u6709\u6548\uff0c\u4f46\u8fd9\u4e00\u6761\u672a\u83b7\u8fd0\u884c\u671f\u8bc1\u636e\uff09")
    ran = 0
    for rel, argv in targets:
        name = os.path.basename(argv[1])
        try:
            subprocess.run(argv, capture_output=True, timeout=timeout, env=env, cwd=SKILLS_ROOT)
            ran += 1
        except (OSError, subprocess.TimeoutExpired) as exc:
            errs.append(f"{name}: \u52a8\u6001\u8dd1\u4e0d\u8d77\u6765\uff08{type(exc).__name__}\uff09\u2014\u2014 \u672c\u6b21\u53ea\u8bc1\u660e\u4e86\u9759\u6001\uff0c\u6ca1\u8bc1\u660e\u8fd0\u884c\u671f")'''

assert OLD in raw, "dynamic_check anchor not found"
raw = raw.replace(OLD, NEW, 1)

# run summary 也要说明覆盖了几个
old_sum = '    print(f"[\u52a8\u6001] \u8dd1\u4e86 {ran} \u4e2a\u95e8\u7981\uff0c\u8bb0\u5f55 {total} \u6b21 open()\uff0c\u7981\u8bfb\u547d\u4e2d {len(hits)} \u6b21")'
new_sum = ('    print(f"[\u52a8\u6001] \u8dd1\u4e86 {ran}/{len(targets)} \u4e2a WATCHED \u811a\u672c\uff0c\u8bb0\u5f55 {total} \u6b21 open()\uff0c'
           '\u7981\u8bfb\u547d\u4e2d {len(hits)} \u6b21")')
assert old_sum in raw, "summary anchor not found"
raw = raw.replace(old_sum, new_sum, 1)

io.open(P, 'w', encoding='utf-8', newline='').write(raw)
print("dynamic coverage widened")
