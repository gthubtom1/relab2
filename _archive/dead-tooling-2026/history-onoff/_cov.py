# -*- coding: utf-8 -*-
"""给 HELP_POSITIVE_CASES 补 11 个能力的样本，并在 selftest_help 里断言全覆盖。"""
import io
NL = '\r\n'
P = 'skillpack/skills/scripts/capability-index.py'
t = io.open(P, encoding='utf-8-sig', newline='').read()

NEW_CASES = '''    # \u2014\u2014 2026-10-15 \u5916\u90e8\u5ba1\u8ba1\u8ffd\u95ee\uff1a\u5269\u4f59 11 \u4e2a\u80fd\u529b\u7684\u6b63\u5411\u6837\u672c\uff08\u4e0d\u8865\u5c31\u4e0d\u77e5\u9053\u5b83\u4eec\u4ec0\u4e48\u65f6\u5019\u518d\u5757\u6389\uff09
    "MyBinDiff": ("MyBinDiff 1.0 - Compare two builds and migrate function names "
                  "from the old version to the new one.", "binary-diff"),
    "MyCapa": ("MyCapa 1.0 - Identify attack capabilities in a binary and map them "
               "to ATT&CK techniques.", "capability-map"),
    "MyCloudAudit": ("MyCloudAudit 1.0 - Audit kubernetes RBAC and detect IAM role "
                     "misconfigurations.", "cloud"),
    "MyObjdump": ("MyObjdump 1.0 - Disassemble an ELF object file and inspect "
                  "its sections and symbols.", "disasm-cli"),
    "MyFwEmu": ("MyFwEmu 1.0 - Boot and emulate router firmware with full-system "
                "emulation (QEMU).", "firmware-emulate"),
    "MyHwProbe": ("MyHwProbe 1.0 - Read NOR flash over SPI and talk to the UART "
                  "serial console via JTAG.", "hardware"),
    "MyHttp": ("MyHttp 1.0 - Send and replay an HTTP request; a small API client "
               "for debugging endpoints.", "http-client"),
    "MyKd": ("MyKd 1.0 - Kernel-mode debugger: analyse a kernel crash dump with "
             "WinDbg-style commands.", "kernel-debug"),
    "MyMobileHook": ("MyMobileHook 1.0 - Frida hook of an android app; bypass SSL "
                     "pinning and root detection.", "mobile-runtime"),
    "MySandbox": ("MySandbox 1.0 - Detonate a malware sample in an isolated "
                  "sandbox and record its behaviour.", "sandbox"),
    "MySdr": ("MySdr 1.0 - Software defined radio: capture IQ with a HackRF and "
              "demodulate with GNU Radio.", "sdr"),
'''

# 插到 HELP_POSITIVE_CASES 字典的闭合括号前：
# 找 "MyTriage" 那一行（现有最后一条语义组），在它之后插入
anchor = '    "MyTriage": ('
i = t.index(anchor)
# 走到该条目的结尾行（以 '),'结尾）
j = t.index('),\n', i) + 3
t = t[:j] + NEW_CASES + t[j:]

# selftest_help 里加全覆盖断言
old_ret = '''    if fails:
        print("capability-index help \u5151\u5e95\u81ea\u68c0: FAIL")'''
new_ret = '''    # \u5168\u8986\u76d6\u65ad\u8a00\uff1a\u6bcf\u4e2a\u80fd\u529b\u81f3\u5c11 2 \u6761 help \u6b63\u5219\uff0c\u4e14\u90fd\u6709\u6b63\u5411\u6837\u672c\u3002
    #   \u8fd9\u4e00\u6761\u5c31\u662f\u9632\u300c\u67d0\u4e2a\u80fd\u529b\u7684 help \u8def\u5f84\u4e0d\u77e5\u4e0d\u89c9\u5757\u6389\u300d\u2014\u2014
    #   2026-10-15 \u4e4b\u524d 17/4/33 \u4e2a\u80fd\u529b\u6ca1\u6709\u5151\u5e95\u6b63\u5219\uff0c\u800c\u6beb\u65e0\u95e8\u7981\u62a5\u9519\u3002
    from collections import Counter as _C
    per = _C(c for _, c in HELP_HINTS)
    for cap in CAPABILITIES:
        if per.get(cap, 0) < 2:
            fails.append(f"\u80fd\u529b {cap} \u53ea\u6709 {per.get(cap, 0)} \u6761 help \u6b63\u5219\uff08<\u22652 \u65f6\u8be5\u8def\u5f84\u7ed3\u6784\u4e0a\u6c38\u8fdc\u547d\u4e2d\uff09")
    sampled = {w for _t, w in HELP_POSITIVE_CASES.values()}
    for cap in CAPABILITIES:
        if cap not in sampled:
            fails.append(f"\u80fd\u529b {cap} \u6ca1\u6709\u6b63\u5411\u6837\u672c\uff08\u5757\u6389\u4e86\u4e5f\u6ca1\u4eba\u77e5\u9053\uff09")
    if fails:
        print("capability-index help \u5151\u5e95\u81ea\u68c0: FAIL")'''
assert old_ret in t, "selftest tail anchor not found"
t = t.replace(old_ret, new_ret, 1)

io.open(P, 'w', encoding='utf-8', newline='').write(t)
print("cases + coverage assertion added")
