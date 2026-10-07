"""读 build_hubcore 的 MANIFEST，把 11 个后置补丁的落地情况打出来。只读。"""
import json
import pathlib
import sys

m = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
patches = m.get("post_patches", [])
print(f"后置补丁共 {len(patches)} 条")
ok = bad = missing = 0
for p in patches:
    st = p.get("status")
    if st == "ok":
        ok += 1
    elif str(st).startswith("缺"):
        missing += 1
    else:
        bad += 1
    line = (p.get("out") or "").replace("\n", " ")[:110]
    print(f"  [{st:>6}] rc={p.get('rc')}  {p['target']}")
    if line:
        print(f"            {line}")
print(f"\n成功 {ok} / 失败 {bad} / 缺脚本 {missing}")
sys.exit(0 if bad == 0 and missing == 0 and ok == len(patches) else 3)
