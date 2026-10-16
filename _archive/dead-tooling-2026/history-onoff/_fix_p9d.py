# -*- coding: utf-8 -*-
"""P9: 静态判据从「提到禁读名就算排除」改成「必须真的排除」。

外部审查构造出的假绿：
    # NOTE: we must never read _归档-禁读-历史文档/ (forbidden dir)
    import os
    def scan():
        for dp, dns, fs in os.walk(REPO_ROOT):     # 没有任何排除
            ...

`_reaches_forbidden` 旧逻辑第一行就是 `if FORBIDDEN_DIRNAME in src: return False`
——只要源码里出现过这个名字（哪怕只是在注释里声明"我不读它"）就整段放行。
于是一份 actually 会读禁读区的脚本被判为安全，而这正是缩动态集后唯一还看着它的东西。

新判据：看到禁读名之后，还要确认它是被用于**排除**（而不是提及）。
认可的排除写法（任一位于同一源码内）：
  · dirs[:] = [d for d in dirs if ... FORBIDDEN ...]
  · startswith(FORBIDDEN_READ_PREFIX...) / .startswith("_归档-禁读-历史文档")
  · != FORBIDDEN_DIRNAME  / not in (...)
  · 显式的 skip 名单里含该名字的字符串常量
"""
import io

P = 'skillpack/skills/tests/verify-no-forbidden-reads.py'
NL = '\r\n'
t = io.open(P, encoding='utf-8-sig', newline='').read()

OLD = '''def _reaches_forbidden(src):
    """\u8fd9\u6bb5\u6e90\u7801\u7684\u904d\u5386\uff0c\u80fd\u4e0d\u80fd\u5230\u8fbe\u4ed3\u6839\u7684\u7981\u8bfb\u76ee\u5f55\uff1f"""
    if FORBIDDEN_DIRNAME in src:
        return False  # \u5df2\u6392\u9664
    walks = ("os.walk" in src) or ("ls-files" in src) or ("Get-ChildItem" in src)
    if not walks:
        return False  # \u4e0d\u904d\u5386
    # \u904d\u5386\u6839\u9489\u5728\u5b50\u6811\u91cc\uff08\u4e14\u6ca1\u6709\u518d\u4ece\u4ed3\u6839\u8d1f\u8d70\u4e00\u6b21\uff09\u2192\u591f\u4e0d\u5230\u4ed3\u6839\u7684\u7981\u8bfb\u76ee\u5f55
    walks_repo_root = ("os.walk(ROOT" in src) or ("os.walk(REPO_ROOT" in src) or ("ls-files" in src)
    if walks_repo_root:
        return True
    pinned = [
        DQ + "skills" + DQ,
        SQ + "skills" + SQ,
        "skills/",
        "skills" + BS + BS,
    ]
    return not any(tok in src for tok in pinned)'''

NEW = '''# \u8ba4\u53ef\u7684\u201c\u771f\u6392\u9664\u201d\u5199\u6cd5\uff08\u770b\u5230\u7981\u8bfb\u540d\u5b57\u4e4b\u540e\uff0c\u8fd8\u5f97\u770b\u5230\u5b83\u88ab\u7528\u5728\u6392\u9664\u4e0a\uff09
_EXCLUDE_HINTS = (
    "dirs[:]",
    "dirs[:] =",
    "startswith(FORBIDDEN",
    "startswith(_",
    "!= FORBIDDEN",
    "not in",
    "SKIPPED_PREFIXES",
    "FORBIDDEN_READ_PREFIXES",
    "FORBIDDEN_READ_PREFIX",
    "-Exclude",
    "--exclude",
    "Where-Object",
    "-notlike",
    "-notmatch",
)


def _actually_excludes(src: str) -> bool:
    """\u8fd9\u6bb5\u6e90\u7801\u662f\u5426\u771f\u7684\u628a\u7981\u8bfb\u76ee\u5f55\u6392\u9664\u6389\uff08\u800c\u4e0d\u662f\u53ea\u5728\u6ce8\u91ca\u91cc\u63d0\u5230\u5b83\uff09\u3002"""
    for ln in src.splitlines():
        s = ln.strip()
        if s.startswith("#"):
            continue                      # \u6ce8\u91ca\u91cc\u63d0\u4e0d\u7b97
        if FORBIDDEN_DIRNAME not in s and "FORBIDDEN" not in s:
            continue
        if any(h in s for h in _EXCLUDE_HINTS):
            return True
    return False


def _reaches_forbidden(src):
    """\u8fd9\u6bb5\u6e90\u7801\u7684\u904d\u5386\uff0c\u80fd\u4e0d\u80fd\u5230\u8fbe\u4ed3\u6839\u7684\u7981\u8bfb\u76ee\u5f55\uff1f

    \u2605 2026-10-15 \u5916\u90e8\u5ba1\u8ba1\u8ffd\u95ee\uff1a\u65e7\u7248\u7b2c\u4e00\u884c\u5c31\u662f
    `if FORBIDDEN_DIRNAME in src: return False` \u2014\u2014\u53ea\u8981\u6e90\u7801\u91cc\u51fa\u73b0\u8fc7\u8fd9\u4e2a\u540d\u5b57
    \uff08\u5305\u62ec\u53ea\u5728\u6ce8\u91ca\u91cc\u5199\u300c\u6211\u4e0d\u8bfb\u5b83\u300d\uff09\u5c31\u6574\u6bb5\u653e\u884c\u3002
    \u73b0\u5728\u8981\u6c42\u201c\u771f\u6392\u9664\u201d\uff1a\u540d\u5b57\u5f97\u51fa\u73b0\u5728\u4e00\u6761\u975e\u6ce8\u91ca\u4e14\u542b\u6392\u9664\u5199\u6cd5\u7684\u4ee3\u7801\u91cc\u3002
    """
    walks = ("os.walk" in src) or ("ls-files" in src) or ("Get-ChildItem" in src)
    if not walks:
        return False  # \u4e0d\u904d\u5386
    if _actually_excludes(src):
        return False  # \u5df2\u7ecf\u771f\u6392\u9664
    # \u904d\u5386\u6839\u9489\u5728\u5b50\u6811\u91cc\uff08\u4e14\u6ca1\u6709\u518d\u4ece\u4ed3\u6839\u8d70\u4e00\u6b21\uff09\u2192\u591f\u4e0d\u5230\u4ed3\u6839\u7684\u7981\u8bfb\u76ee\u5f55
    walks_repo_root = ("os.walk(ROOT" in src) or ("os.walk(REPO_ROOT" in src) or ("ls-files" in src)
    if walks_repo_root:
        return True
    pinned = [
        DQ + "skills" + DQ,
        SQ + "skills" + SQ,
        "skills/",
        "skills" + BS + BS,
    ]
    return not any(tok in src for tok in pinned)'''

assert OLD in t, "old _reaches_forbidden not found"
t = t.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8', newline='').write(t)
print("static judgement hardened")
