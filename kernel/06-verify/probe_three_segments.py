"""三段可选：开着中枢 vs 关掉中枢，验字节与拆卸。"""
import shutil
import subprocess
import sys
from pathlib import Path

PY = sys.executable
# ★ 2026-10-16 修：根按**入口文件的位置**定，不看当前工作目录。
#   原来写的是 Path('.').resolve() —— 从 06-verify/ 里跑没事，换成从仓库根跑就会去写
#   kernel/06-verify/04-console/TEMP/probe-base.md（目录不存在 → FileNotFoundError）。
ROOT = Path(__file__).resolve().parents[1]      # kernel/
TEMP = ROOT / '04-console' / 'TEMP'
TEMP.mkdir(parents=True, exist_ok=True)        # 头一次跑时它还不存在
CARD = TEMP / 'probe-base.md'
CARD.write_text('# base: 试探底模\n# kind: base\n# hosts: probe\n\n少谈立场，只谈工程。\n', encoding='utf-8')
GUEST = TEMP / 'probe-guest.md'
GUEST.write_text('# base: 试探指引\n# kind: guest\n# hosts: probe\n\n根：D:\\某包\n1 先读总控\n2 再定入口\n', encoding='utf-8')


def run(argv):
    return subprocess.run([PY] + [str(a) for a in argv], capture_output=True,
                          text=True, encoding='utf-8', errors='replace')


def fresh(name, text='# 原文\n\n这一段是宿主自己的。\n'):
    d = TEMP / ('probe-' + name)
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    (d / 'AGENTS.md').write_text(text, encoding='utf-8', newline='')
    return d


src = ROOT / '03-bundle' / 'dist' / 'hubcore'
fails = []


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name, extra)
    if not cond:
        fails.append(name)


# A. 三样都开
d = fresh('all')
before = (d / 'AGENTS.md').read_bytes()
r = run([ROOT / '03-bundle' / 'install.py', '--source', src, '--host-home', d,
         '--base', CARD, '--guest', GUEST])
check('A 装入 rc=0', r.returncode == 0, r.stderr[-200:] if r.returncode else '')
txt = (d / 'AGENTS.md').read_text(encoding='utf-8')
# 顺序是刻意的：标记块永远写最后（原文 / 底模 / 指引 / 标记块）——它是最后一段定论。
order = [txt.find('这一段是宿主自己的'), txt.find('# >>> hubcore base >>>'),
         txt.find('# >>> hubcore guest >>>'), txt.find('# >>> hubcore hub >>>')]
check('A 顺序 原文/底模/指引/标记块（标记块永远最后）',
      order == sorted(order) and all(i >= 0 for i in order), str(order))
r = run([ROOT / '03-bundle' / 'uninstall.py', '--host-home', d, '--yes'])
after = (d / 'AGENTS.md').read_bytes()
check('A 卸完逐字节还原', after == before, 'rc=%d' % r.returncode)

# B. 关掉中枢，只写底模 + 指引
d = fresh('nomarker')
before = (d / 'AGENTS.md').read_bytes()
r = run([ROOT / '03-bundle' / 'install.py', '--source', src, '--host-home', d,
         '--base', CARD, '--guest', GUEST, '--no-marker'])
check('B 装入 rc=0', r.returncode == 0, r.stderr[-200:] if r.returncode else '')
txt = (d / 'AGENTS.md').read_text(encoding='utf-8')
check('B 没有中枢标记块', '# >>> hubcore hub >>>' not in txt)
check('B 有底模与指引', '# >>> hubcore base >>>' in txt and '# >>> hubcore guest >>>' in txt)
r = run([ROOT / '03-bundle' / 'uninstall.py', '--host-home', d, '--yes'])
after = (d / 'AGENTS.md').read_bytes()
check('B 卸完逐字节还原', after == before, 'rc=%d' % r.returncode)
check('B 卸完没有残留块', '# >>> hubcore' not in (d / 'AGENTS.md').read_text(encoding='utf-8'))

# C. 只开中枢
d = fresh('hubonly')
before = (d / 'AGENTS.md').read_bytes()
r = run([ROOT / '03-bundle' / 'install.py', '--source', src, '--host-home', d])
check('C 只装中枢 rc=0', r.returncode == 0)
txt = (d / 'AGENTS.md').read_text(encoding='utf-8')
check('C 只有标记块', '# >>> hubcore hub >>>' in txt and '# >>> hubcore base >>>' not in txt)
run([ROOT / '03-bundle' / 'uninstall.py', '--host-home', d, '--yes'])
check('C 卸完逐字节还原', (d / 'AGENTS.md').read_bytes() == before)

# D. 覆盖模式：宿主原文整段丢弃；连装两次再卸回，必须还是原文（上一棵树的备份得接住）
d = fresh('replace')
before = (d / 'AGENTS.md').read_bytes()
r1 = run([ROOT / '03-bundle' / 'install.py', '--source', src, '--host-home', d, '--replace-origin'])
check('D 覆盖装 rc=0', r1.returncode == 0, r1.stderr[-200:] if r1.returncode else '')
txt = (d / 'AGENTS.md').read_text(encoding='utf-8')
check('D 原文没留在文件里', '这一段是宿主自己的' not in txt)
r2 = run([ROOT / '03-bundle' / 'install.py', '--source', src, '--host-home', d, '--replace-origin'])
check('D 再覆盖装一次 rc=0', r2.returncode == 0, r2.stderr[-200:] if r2.returncode else '')
run([ROOT / '03-bundle' / 'uninstall.py', '--host-home', d, '--yes'])
check('D 卸完逐字节还原原文', (d / 'AGENTS.md').read_bytes() == before)

for name in ('all', 'nomarker', 'hubonly', 'replace'):
    shutil.rmtree(TEMP / ('probe-' + name), ignore_errors=True)
for p in (CARD, GUEST):
    p.unlink(missing_ok=True)

print('判定：', '全绿' if not fails else '红：%s' % fails)
sys.exit(0 if not fails else 1)
