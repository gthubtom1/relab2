"""按浏览器真实顺序走一遍新页面要用的每个东西。
不是「接口能通」，是「页面点得动」：静态、首页、六类接口、卡片建删、保险箱查询。

鉴权是会话 Cookie 那一套（进页面拿 Cookie，后面接口带它）：
地址里不带 ?t=，令牌也不在正文里。
"""
import json
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar

port = sys.argv[1]
b = 'http://127.0.0.1:' + port
fails = []


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name, extra)
    if not cond:
        fails.append(name)


jar = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = [("Referer", b + "/")]


def req(path, data=None, authed=True):
    body = json.dumps(data).encode('utf-8') if data is not None else None
    if not authed:
        # 裸请求：不用 cookie jar，模拟没进过页面的调用方
        r = urllib.request.Request(b + path, data=body,
                                   method='POST' if data is not None else 'GET')
        if data is not None:
            r.add_header('Content-Type', 'application/json; charset=utf-8')
        try:
            with urllib.request.urlopen(r, timeout=15) as res:
                return res.status, res.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
    r = urllib.request.Request(b + path, data=body,
                               method='POST' if data is not None else 'GET')
    if data is not None:
        r.add_header('Content-Type', 'application/json; charset=utf-8')
    try:
        with opener.open(r, timeout=15) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


for asset, least in (('/app.js', 4000), ('/style.css', 4000)):
    code, body = req(asset)
    check('无凭证拿 %s' % asset, code == 200 and len(body) > least, 'http=%s %dB' % (code, len(body)))

code, body = req('/')
check('首页无凭证 200（它只负责发会话 Cookie）', code == 200 and b'app.js' in body, 'http=%s' % code)
check('拿到了会话 Cookie', bool(jar), 'cookie %d 个' % len(jar))

code, _ = req('/api/status', authed=False)
check('/api/status 无凭证 403', code == 403, 'http=%s' % code)

code, body = req('/api/status')
st = json.loads(body)
check('/api/status', code == 200 and st.get('ok'), '就绪=%s 卡片=%d' % (st['package']['ready'], len(st.get('cards', []))))
check('打包器带文件数', st['package'].get('file_count') == 91, str(st['package'].get('file_count')))

code, body = req('/api/hosts')
hosts = json.loads(body)['hosts']
usable = [h for h in hosts if h['exists'] and not h.get('fixture')]
check('/api/hosts 扫到宿主', code == 200 and len(usable) >= 1, '总 %d 家，能装 %d 家' % (len(hosts), len(usable)))
check('宿主行带版本字段', all('version' in h for h in hosts))

code, body = req('/api/cards')
check('/api/cards', code == 200 and isinstance(json.loads(body)['cards'], list))

code, body = req('/api/safebox?host_id=' + usable[0]['id'])
check('/api/safebox 列表', code == 200 and 'snapshots' in json.loads(body))

# 卡片建 → 查 → 删（真走一遍页面里的新建）
code, body = req('/api/cards', {'name': '页面自检卡', 'hosts': 'probe',
                                'content': '只谈工程。', 'kind': 'base'})
check('建底模卡', code == 200 and json.loads(body)['ok'], body[:120].decode('utf-8', 'replace'))
code, body = req('/api/cards', {'name': '页面自检指引', 'hosts': 'probe',
                                'content': '根：D:\\某包\n1 先读总控', 'kind': 'guest'})
check('建指引卡', code == 200 and json.loads(body).get('kind') == 'guest')
code, body = req('/api/cards')
kinds = sorted(c['kind'] for c in json.loads(body)['cards'] if c['id'].startswith('页面自检'))
check('两种卡都在表里', kinds == ['base', 'guest'], str(kinds))
for cid in ('页面自检卡', '页面自检指引'):
    code, body = req('/api/cards/delete', {'id': cid})
    check('删卡 %s' % cid, code == 200 and json.loads(body)['ok'])

print('判定：', '全绿' if not fails else '红：%s' % fails)
sys.exit(0 if not fails else 1)
