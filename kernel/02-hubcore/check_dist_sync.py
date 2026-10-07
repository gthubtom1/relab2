"""产物新鲜度检查：dist/ 是不是当前源码构建出来的？

第一版做错了什么（留给以后看）：拿**变换前**的源码去比**变换后**的产物。
可打包器本来就要改写一批东西（`.agents/skills/X/SKILL.md` → `workflows/X.md`、
`hub-lean` → `hubcore`、`<hub>/` 占位符展开、行尾 CRLF），所以重打之后它**还是红的**。
一个接进心跳的检查天天喊狼来了，最后一定被无视；被无视之后，
它本来能抓到的真故障也一起丢掉。**报错了还给错修法，比不报更坏。**

现在改成：拿**当前源码重新构建一份新的**，和现有 `dist/` 逐文件比 sha。
所有变换都由构造保证，判据只剩一件事——dist 是不是当前源码的产物。

退出码 0 = 新鲜；3 = 过期或多了不该有的东西。
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEV = HERE.parent
BUNDLE = DEV / "03-bundle"
DIST = BUNDLE / "dist" / "hubcore"
PACK = BUNDLE / "pack.py"
# 打包工具不该进包。装出去的系统不需要重新验证自己是从哪构建的。
TOOLS_MUST_NOT_SHIP = ("pack.py", "install.py", "verify.py", "_bundle_lib.py",
                       "bundle-meta.json", "hosts.py", "_scratch.py")


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _files(root: Path) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        # Compare RELATIVE parts only. Testing `s in p.parts` on the absolute path
        # meant any ancestor directory named "state" excluded the entire tree, so a
        # stale file under state/ could never be reported (DESIGN-RULES rule 12:
        # blind spots must not be silent).
        rel_parts = p.relative_to(root).parts
        if any(s in rel_parts for s in ("__pycache__", ".state")):
            continue
        out[p.relative_to(root).as_posix()] = _sha(p)
    return out


def main() -> int:
    if not DIST.is_dir():
        print(json.dumps({"ok": False, "why": f"没有产物目录：{DIST}"},
                         ensure_ascii=False, indent=2))
        return 3
    if not PACK.is_file():
        print(json.dumps({"ok": False, "why": f"没有打包器：{PACK}"},
                         ensure_ascii=False, indent=2))
        return 3

    tmp = Path(tempfile.mkdtemp(prefix="ctxiso-fresh-"))
    fresh_root = tmp / "hubcore"
    try:
        proc = subprocess.run(
            [sys.executable, str(PACK), "--out", str(fresh_root), "--allow-out-anywhere"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300, cwd=str(BUNDLE))
        if proc.returncode != 0:
            print(json.dumps({"ok": False, "why": "重新构建失败，产物新鲜度无从判断",
                              "rc": proc.returncode,
                              "tail": (proc.stdout or "") + (proc.stderr or "")[-800:]},
                             ensure_ascii=False, indent=2))
            return 3
        fresh, dist = _files(fresh_root), _files(DIST)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    drift = sorted(k for k in fresh.keys() & dist.keys() if fresh[k] != dist[k])
    missing = sorted(fresh.keys() - dist.keys())      # 该有却没有 = 忘了重打
    extra = sorted(dist.keys() - fresh.keys())        # dist 里多出来的
    smuggled = [n for n in TOOLS_MUST_NOT_SHIP if (DIST / n).is_file()]
    # `extra` counts files left in dist/ that the current source no longer produces.
    # It used to be computed and printed but excluded from `ok`, so a stale leftover
    # still returned exit 0 while the docstring promised 3 for "多了不该有的东西".
    ok = not (drift or missing or extra or smuggled)

    out = {
        "ok": ok,
        "checked": len(fresh),
        "identical": len(fresh) - len(drift) - len(missing),
        "drift": drift[:40],
        "missing_in_dist": missing[:40],
        "extra_in_dist": extra[:40],
        "build_tools_in_dist": smuggled,
        "verdict": (
            "产物是当前源码构建出来的" if ok else
            ("打包工具混进了产物：%s" % "、".join(smuggled) if smuggled else
             f"产物过期：{len(missing)} 个文件该有却没有、{len(drift)} 个内容不同。"
             f"重跑 `python {PACK}` 之后再装。")),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
