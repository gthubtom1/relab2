"""读 build_hubcore 的 MANIFEST，把 11 个后置补丁的落地情况打出来。只读。

用法：
  python show_patches.py MANIFEST.json        # 默认就是同目录的 MANIFEST.json
  python show_patches.py --help

退出码：0 = 全部 ok；3 = 有失败或缺脚本。
"""
import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser(
        description="读 build_hubcore 的 MANIFEST，逐条打印后置补丁的落地情况（只读）。")
    ap.add_argument("manifest", nargs="?", default=str(HERE / "MANIFEST.json"),
                    help="MANIFEST.json 路径（默认同目录那一份）")
    a = ap.parse_args()
    path = pathlib.Path(a.manifest)
    if not path.is_file():
        print(f"找不到 {path}。先跑 build_hubcore.py 生成 MANIFEST，或把路径传对。",
              file=sys.stderr)
        return 2
    m = json.loads(path.read_text(encoding="utf-8"))
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
    return 0 if bad == 0 and missing == 0 and ok == len(patches) else 3


if __name__ == "__main__":
    sys.exit(main())
