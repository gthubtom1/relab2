"""静态一致性检查：app.js 里引用的每个 id，index.html 里必须存在。

页面「点不动、一家也扫不到」最常见的原因就是这一条：
脚本加载时 $('xxx') 拿到 null，后面一行就抛，整段脚本死掉，
页面剩下纯静态的骨架——看着像示例，其实 JS 已经断了。

    python 04-console/TEMP/check_ids.py
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / '04-console'
html = (HERE / "web" / "index.html").read_text(encoding="utf-8")
js = (HERE / "web" / "app.js").read_text(encoding="utf-8")

have = set(re.findall(r'id="([^"]+)"', html))
want = set(re.findall(r"\$\('([^']+)'\)", js))
want |= set(re.findall(r"getElementById\('([^']+)'\)", js))
# 动态拼出来的 id（tiles-base / tiles-guest / 别的模板）单独放行
dynamic = {"tiles-base", "tiles-guest"}

missing = sorted(want - have - dynamic)
print("html 里 %d 个 id，脚本引用 %d 个" % (len(have), len(want)))
if missing:
    print("脚本要但页面没有（会当场抛错，页面变死）：")
    for m in missing:
        print("   ", m)
else:
    print("脚本引用的 id 全在页面上")

# 反向：页面上有、脚本从不引用的交互元素（多半是漏绑事件）
ids_for_buttons = set(re.findall(r'<(?:button|input|select|textarea)[^>]*id="([^"]+)"', html))
unused = sorted(ids_for_buttons - want)
print("页面有、脚本没引用：", unused if unused else "无")

sys.exit(1 if missing else 0)
