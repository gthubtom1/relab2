"""一键自测：把验收 1-5 跑一遍，把真实输出打在屏幕上。

    python selftest.py                 用 TEMP 里的假打包器（默认，03-bundle 没就绪也能跑）
    python selftest.py --bundle real   用真的 03-bundle 联调（装卸都发生在 TEMP 里）

只在 04-console/TEMP 里造假家目录与假打包器，绝不碰真实 %USERPROFILE% 里的智能体。
服务进程用完就杀，不留常驻。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bundle_locator  # noqa: E402
import hosts as hosts_mod  # noqa: E402
import server as console  # noqa: E402

TEMP = HERE / "TEMP"
FAKE_BUNDLE = TEMP / "fake-bundle"
EMPTY_BUNDLE = TEMP / "empty-bundle"
BUNDLE = HERE.parent / "03-bundle"          # 真打包器（验收 9 直接调它）
FIXTURE_HOME = TEMP / "fixture-home"
FIXTURE_ENTRY = FIXTURE_HOME / "AGENTS.md"

# real = 仓库里真的 03-bundle（默认）；fake = TEMP 里的接线替身。
# 默认必须是 real：替身是 06:56 写的接线壳，它把标记块接在文末，而真打包器 18:43
# 改成了「标记块在前、原文在中、指引在后」。拿替身跑字节级判据，测的是已经不存在的产品。
# 两种跑法宿主家目录都在 TEMP/fixture-home，真家目录一个字节不碰。
BUNDLE_KIND = "real"

BANNED = ["技能", "副插件", "卡带", "AI 接口", "适配", "github", "http", "packs", "user-skills"]


def line(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


SESSION = {"cookie": ""}


def _auth_headers(token: str | None) -> dict:
    """令牌已经不发在命令行行了：走浏览器那条路——先开一次页面拿会话 Cookie。

    token=None 表示「什么都不带」，用来验真正那道门。
    """
    if token is None:
        return {}
    if token:
        return {"X-Token": token}
    if SESSION["cookie"]:
        return {"Cookie": SESSION["cookie"]}
    return {}


def open_page(base: str) -> None:
    """像浏览器那样先 GET 一次页面外壳，服务端会下发会话 Cookie。"""
    req = urllib.request.Request(base + "/", headers={"Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=30) as res:
        res.read()
        raw = res.headers.get("Set-Cookie") or ""
    SESSION["cookie"] = raw.split(";")[0].strip()


def get(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers=_auth_headers(token))
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"http_status": exc.code, "body": exc.read().decode("utf-8", "replace")}


def post(url: str, token: str, payload: dict) -> dict:
    raw = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=raw, method="POST",
        headers=dict(_auth_headers(token),
                     **{"Content-Type": "application/json; charset=utf-8"}),
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"http_status": exc.code, **json.loads(exc.read().decode("utf-8", "replace"))}


def reset_fixture() -> bytes:
    if FIXTURE_HOME.exists():
        shutil.rmtree(FIXTURE_HOME)
    FIXTURE_HOME.mkdir(parents=True)
    FIXTURE_ENTRY.write_text(
        "# 假宿主的原文\n\n这一行是自测前就有的。装完、卸完之后必须逐字节一模一样。\n",
        encoding="utf-8",
    )
    return FIXTURE_ENTRY.read_bytes()


# 与 03-bundle/_bundle_lib.py 同一对标记。这里独立实现，不 import 打包器：
# 控制台的耦合面只有子进程命令行这一条。判据必须自成一体。
M_BEGIN = "# >>> hubcore hub >>>"
M_END = "# <<< hubcore hub <<<"


def strip_our_block(text: str) -> str:
    """摘掉「中枢自己写的」那块标记块，其余原样返回。找不到就原样返回。"""
    b = text.find(M_BEGIN)
    if b < 0:
        return text
    e = text.find(M_END, b)
    if e < 0:
        return text
    e += len(M_END)
    if text[e:e + 1] == "\n":
        e += 1
    return text[:b] + text[e:]


def check_bundler_guard() -> None:
    line("A. 打包器没就绪时，载入必须明确报错（不是静默成功）")
    EMPTY_BUNDLE.mkdir(parents=True, exist_ok=True)
    os.environ["HUBCONSOLE_TEST_HOME"] = str(FIXTURE_HOME)
    before = os.environ.get("HUBCONSOLE_BUNDLE_DIR")
    os.environ["HUBCONSOLE_BUNDLE_DIR"] = str(EMPTY_BUNDLE)
    try:
        print("readiness() =", json.dumps(bundle_locator.readiness(), ensure_ascii=False))
        result = console.do_load("fixture")
        print("do_load('fixture') =", json.dumps(result, ensure_ascii=False, indent=1))
        print("判定：", "通过" if (not result["ok"] and "打包器未就绪" in result["error"]) else "不通过")
    finally:
        if before is None:
            os.environ.pop("HUBCONSOLE_BUNDLE_DIR", None)
        else:
            os.environ["HUBCONSOLE_BUNDLE_DIR"] = before
        os.environ.pop("HUBCONSOLE_TEST_HOME", None)


def start_child() -> tuple[subprocess.Popen, int, str, list[str]]:
    env = dict(os.environ)
    if BUNDLE_KIND == "fake":
        env["HUBCONSOLE_BUNDLE_DIR"] = str(FAKE_BUNDLE)
    else:
        env.pop("HUBCONSOLE_BUNDLE_DIR", None)
    env["HUBCONSOLE_TEST_HOME"] = str(FIXTURE_HOME)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-u", str(HERE / "run.py"), "--no-open"],
        cwd=str(HERE), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace",
    )
    # 打包器的输出是继承终端的，会灌进这根管道。必须一直抽干，
    # 否则输出超过管道缓冲就把子进程卡死，自测自己先挂。
    stream: list[str] = []

    def drain():
        for row in iter(proc.stdout.readline, ""):
            stream.append(row.rstrip())

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()

    port = 0
    token = ""
    scanned = 0
    deadline = time.time() + 30
    while time.time() < deadline:
        # 必须扫整条流。只看最后一行会漏：读线程可能比主线程快，
        # 主线程醒来时前三行已经齐了。
        while scanned < len(stream):
            line_out = stream[scanned]
            scanned += 1
            hit = re.search(r"127\.0\.0\.1:(\d+)", line_out)
            if hit:
                port = int(hit.group(1))
            hit = re.search(r"令牌：(\S+)", line_out)
            if hit:
                token = hit.group(1)
        if port:
            break
        if proc.poll() is not None and not stream:
            break
        time.sleep(0.05)
    return proc, port, token, stream


def main(argv: list[str] | None = None) -> int:
    global BUNDLE_KIND
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--bundle" in argv:
        BUNDLE_KIND = argv[argv.index("--bundle") + 1]
    if BUNDLE_KIND not in ("fake", "real"):
        print("--bundle 只能是 fake 或 real")
        return 2
    if BUNDLE_KIND == "fake":
        print("注意：fake 是接线替身，只证明命令接上了；写入顺序和字节语义不代表产品。")
    print(f"打包器来源：{BUNDLE_KIND}（宿主家目录一律在 TEMP/fixture-home，真家目录不碰）")
    reset_fixture()
    failures: list[str] = []

    check_bundler_guard()

    line("B. 起服务：python run.py --no-open")
    proc, port, token, stream = start_child()
    for item in list(stream):
        print(item)
    if not port:
        print("不通过：没拿到端口")
        proc.kill()
        return 1
    base = f"http://127.0.0.1:{port}"
    time.sleep(0.4)
    # 页面地址不再带令牌（主人要的就是这个）：先把页面开一次，拿到会话 Cookie。
    try:
        open_page(base)
    except urllib.error.HTTPError as exc:
        print("不通过：首页打不开", exc)
        proc.kill()
        return 1
    print("会话 Cookie：", SESSION["cookie"].split("=", 1)[0] if SESSION["cookie"] else "（没拿到）")

    try:
        line("验收 1：/api/status")
        status = get(base + "/api/status", token)
        slim = {k: v for k, v in status.items() if k != "token"}
        print(json.dumps(slim, ensure_ascii=False, indent=1))
        print("带会话 Cookie 过得去：", status.get("ok") is True)

        line("验收 1 续：没有凭证必须被拒（远程网页就是被这一条挡住）")
        for probe, label in (("wrong-token", "错令牌"), (None, "什么都不带")):
            got = get(base + "/api/status", probe)
            print(f"{label} ->", got)
            if got.get("http_status") != 403:
                failures.append(f"验收 1：{label} 没被拒 -> {got}")
        if status.get("ok") is not True:
            failures.append("验收 1：带会话 Cookie 拿不到状态")

        line("验收 2：/api/hosts 在这台机器上扫到什么")
        listed = get(base + "/api/hosts", token)
        rows = listed["hosts"]
        for row in rows:
            print("{id:<10} 家目录在={e:<5} 入口={n:<28} 已装={i:<5} 运行中={r} pids={p}".format(
                id=row["id"], e=row["exists"], n=row["entry"],
                i=row["installed"], r=row["running"], p=row.get("pids", [])))
        present = [row for row in rows if row["exists"] and not row.get("fixture")]
        print(f"真实存在的家目录：{len(present)} 个 -> {[r['id'] for r in present]}")
        # 这台机器上装了几个智能体宿主，是**事实**，不是判据。
        # 原实现写死「不足 3 个就判红」—— 那让这条断言在任何少于 3 个宿主的机器上
        # **永远红着**，于是所有人学会忽略它，等于没有这道门（2026-10-09 修）。
        # 真正要验的不变量：扫描结果与注册表自洽、每行字段齐全。
        REQUIRED_FIELDS = {"id", "exists", "entry", "installed", "running"}
        missing_fields = [r.get("id", "?") for r in rows if not REQUIRED_FIELDS <= set(r)]
        registry_ids = {h["id"] for h in (status.get("hosts") or [])}
        unknown_ids = [r["id"] for r in rows if registry_ids and r["id"] not in registry_ids]
        if not rows:
            failures.append("验收 2：一个宿主都没扫到（扫描逻辑坏了）")
        if len(present) < 1:
            failures.append("验收 2：一个真实存在的家目录都没扫到")
        if missing_fields:
            failures.append("验收 2：这些宿主行缺字段：%s" % missing_fields)
        if unknown_ids:
            failures.append("验收 2：扫出注册表里没有的宿主：%s" % unknown_ids)
        ok2 = bool(rows) and len(present) >= 1 and not missing_fields and not unknown_ids
        print("判定：", "通过" if ok2 else "不通过")

        line(f"验收 3：端到端装 / 卸（打包器={BUNDLE_KIND}，宿主家目录在 TEMP，真家目录一个字节没动）")
        print("宿主家目录：", FIXTURE_HOME)
        original = FIXTURE_ENTRY.read_bytes()
        print("装之前 AGENTS.md 指纹：", hashlib.sha256(original).hexdigest()[:16])
        print()
        print("--- POST /api/load {host_id: fixture}")
        load = post(base + "/api/load", token, {"host_id": "fixture"})
        print(json.dumps(load, ensure_ascii=False, indent=1))
        after_bytes = FIXTURE_ENTRY.read_bytes()
        after_load = after_bytes.decode("utf-8")
        hub_dir = FIXTURE_HOME / "hub"
        print("装完家目录内容：", sorted(p.name for p in hub_dir.iterdir()) if hub_dir.is_dir() else "（没有 hub/，装没成）")
        print("AGENTS.md 现在是这样：")
        for row_text in after_load.splitlines():
            print("   |", row_text)
        # 判据：把中枢自己那块标记块摘掉，剩下的必须跟装之前逐字节相同。
        # 标记块刻意写在**最末**（insert_marker 返回 原文+底模+指引+标记块），
        # 所以不能用「原文还在开头」来判——那是只对前置/追加式成立的错判据。
        stripped_after = strip_our_block(after_load)
        original_text = original.decode("utf-8")
        origin_intact = (stripped_after == original_text)
        # 标记块必须永远是最后一段：它是「和任何底模兼容」的实现方式——
        # 主人换底模/换指引卡都不会动到它，它就永远在最后一段做最终裁决。
        block_last = after_load.rstrip("\r\n").endswith(M_END)
        # 逐字节**前缀**比对：装后的文件 = 装前的字节 + 标记块字节，一字节不差。
        # （顺序改了就从「尾巴比对」翻成「前缀比对」，字节层面的卡不变。）
        head_intact = (after_bytes[:len(original)] == original)
        print("标记块在文件最末：", block_last)
        print("摘掉标记块后与装前逐字节相同：", origin_intact)
        print("原文那段前缀字节与装前完全一致（%d 字节）：" % len(original), head_intact)
        if not load.get("ok"):
            failures.append("验收 3：装没成")
        if not origin_intact:
            failures.append("验收 3：装的时候动了宿主原文（摘掉标记块后对不上）")
        if not block_last:
            failures.append("验收 3：标记块不在文件最末（它必须是最后一段定论）")
        if not head_intact:
            failures.append("验收 3：标记块之前的宿主原文字节被改了")

        line("验收 3 续：运行中的宿主，载入必须被拒")
        running = [row["id"] for row in rows if row["running"]]
        print("当前被判定为运行中的：", running)
        for host_id in running[:1]:
            blocked = post(base + "/api/load", token, {"host_id": host_id})
            print(f"POST /api/load {host_id} ->", json.dumps(blocked, ensure_ascii=False, indent=1))
            if blocked.get("ok") or "运行中" not in str(blocked.get("error", "")):
                failures.append(f"验收 3：{host_id} 在跑却没被拦住")

        line("验收 3 续：POST /api/hosts/kill 强制关闭接口安全验证")
        kill_bad = post(base + "/api/hosts/kill", token, {"id": "nonexistent_host_12345"})
        print("kill 不存在的宿主 ->", json.dumps(kill_bad, ensure_ascii=False))
        if kill_bad.get("ok"):
            failures.append("验收 3 续：kill 不存在的宿主返回了成功")
        kill_fixture = post(base + "/api/hosts/kill", token, {"id": "fixture"})
        print("kill fixture（无运行进程） ->", json.dumps(kill_fixture, ensure_ascii=False))
        if not kill_fixture.get("ok") or kill_fixture.get("killed") != []:
            failures.append("验收 3 续：kill 空闲宿主未返回 ok 或 killed 列表非空")

        line("验收 3 续：POST /api/unload {host_id: fixture}")
        drop = post(base + "/api/unload", token, {"host_id": "fixture"})
        print(json.dumps(drop, ensure_ascii=False, indent=1))
        final = FIXTURE_ENTRY.read_bytes()
        print("卸完 AGENTS.md 指纹：", hashlib.sha256(final).hexdigest()[:16])
        print("卸完家目录还剩：", sorted(p.name for p in FIXTURE_HOME.iterdir()))
        print("hub/ 还在吗：", (FIXTURE_HOME / "hub").exists())
        if final != original:
            failures.append("验收 3：卸完 AGENTS.md 没有逐字节还原")
        print("判定：", "通过" if final == original else "不通过")

        line("验收 3o：覆盖模式 —— 宿主原文整段丢弃（原字节进备份），卸回时逐字节还原")
        ow1 = post(base + "/api/load", token, {"host_id": "fixture", "replace_origin": True})
        print("第一次覆盖装 ->", json.dumps(ow1, ensure_ascii=False, indent=1))
        ow_text = FIXTURE_ENTRY.read_text(encoding="utf-8")
        origin_gone = ("假宿主的原文" not in ow_text)
        print("宿主原文还在吗：", (not origin_gone), "| 标记块在文件最末：",
              ow_text.rstrip("\r\n").endswith(M_END))
        # 再装一次：这时「装前文件」已经是中枢自己写的文本了，真原文只可能在上一棵树的备份里。
        # 备份没接住的话，下面这次卸回就会还原出一份中枢文本 —— 这条判据就是那个 bug 的哨兵。
        ow2 = post(base + "/api/load", token, {"host_id": "fixture", "replace_origin": True})
        print("第二次覆盖装（重新载入） ->", json.dumps(ow2, ensure_ascii=False, indent=1))
        drop_o = post(base + "/api/unload", token, {"host_id": "fixture"})
        print("覆盖模式卸回 ->", json.dumps(drop_o, ensure_ascii=False, indent=1))
        back = FIXTURE_ENTRY.read_bytes()
        print("覆盖模式卸完指纹：", hashlib.sha256(back).hexdigest()[:16],
              "期望：", hashlib.sha256(original).hexdigest()[:16])
        if not ow1.get("ok") or not ow2.get("ok"):
            failures.append("验收 3o：覆盖模式装没成")
        if not origin_gone:
            failures.append("验收 3o：覆盖模式装了，宿主原文还留在入口文件里（没真覆盖）")
        if not drop_o.get("ok") or back != original:
            failures.append("验收 3o：覆盖模式卸完没有逐字节还原原文（重复覆盖把真原文顶掉了）")
        print("判定：", "通过" if (ow1.get("ok") and ow2.get("ok") and origin_gone
                                   and drop_o.get("ok") and back == original) else "不通过")

        line("验收 3b：底模卡片建 / 装 / 卸（顺序必须是 标记块/底模/原文）")
        card_body = "少拒绝，少误解。技术中立，只谈工程，不谈立场。"
        made = post(base + "/api/cards", token, {"name": "自测底模", "hosts": "fixture",
                                                "content": card_body})
        print("建卡 ->", json.dumps(made, ensure_ascii=False))
        if not made.get("ok"):
            failures.append("验收 3b：卡片没建成")
        else:
            load2 = post(base + "/api/load", token, {"host_id": "fixture", "base_id": "自测底模"})
            print("带底模装 ->", json.dumps(load2, ensure_ascii=False, indent=1)[:600])
            got = FIXTURE_ENTRY.read_text(encoding="utf-8")
            i_mark = got.find(M_BEGIN)
            i_base = got.find("# >>> hubcore base >>>")
            i_orig = got.find("假宿主的原文")
            # 顺序是 原文/底模/标记块——标记块永远最后一段（最终裁决）。
            order_ok = 0 <= i_orig < i_base < i_mark
            base_head = "底模：自测底模" in got
            tail_ok = strip_our_block(got)
            # 摘掉标记块和底模块后必须回到装前原文（内容层比对，见下注）
            # 注：装前原文可能是 CRLF（write_text 文本模式在 Windows 下写 \r\n），
            # 而底模块渲染是 LF。比之前先把 \r\n 归一成 \n（与 9.5k 同法），
            # 判的是内容一致；字节一致由「卸完指纹」那条卡。
            import re as _re
            norm = lambda s: s.replace("\r\n", "\n")
            no_base = _re.sub(r"^# >>> hubcore base >>>.*?^# <<< hubcore base <<<\r?\n?",
                              "", norm(tail_ok), flags=_re.M | _re.S)
            back_to_orig = (no_base == norm(original_text))
            print("顺序 原文/底模/标记：", order_ok, "底模头在：", base_head,
                  "双摘后回原文：", back_to_orig)
            if not load2.get("ok"):
                failures.append("验收 3b：带底模没装上")
            if not order_ok:
                failures.append("验收 3b：顺序不是 原文/底模/标记块")
            if not back_to_orig:
                failures.append("验收 3b：双摘后对不上装前原文")
            # CRLF 底模：主人粘进来的东西几乎都是 CRLF，存卡再装必须一个字都不改。
            # 这条真出过事：write_text 在 Windows 上把 \n 翻成 \r\n，正文里原有的
            # \r\n 变成 \r\r\n，**每个空行多一个换行**——「原样存、一个字不改」当场不成立。
            # 判据用主人粘进来的原始字节（\r\n）而不是归一后的文本。
            crlf_body = "第一行。\r\n\r\n第二段。\r\n\r\n第三段。"
            made_c = post(base + "/api/cards", token, {"name": "自测CRLF底模", "hosts": "fixture",
                                                      "content": crlf_body})
            post(base + "/api/load", token, {"host_id": "fixture", "base_id": "自测CRLF底模"})
            got_c = FIXTURE_ENTRY.read_text(encoding="utf-8")
            # 只在**底模块自己那一段**里查空行，不能对整份文件查：
            # 规则全文里有 `---` 分隔线，它前后天然就是连续空行，
            # 对整份文件查会把标记块自己的排版误判成「底模空行被翻倍」。
            # 2026-09-28 标记块从 11 句短句换成全文内联，这个误判才暴露出来。
            i_b = got_c.find("# >>> hubcore base >>>")
            i_be = got_c.find("# <<< hubcore base <<<")
            base_seg = got_c[i_b:i_be] if 0 <= i_b < i_be else ""
            blank_doubled = "\n\n\n" in base_seg or "\r\n\r\n\r\n" in base_seg
            kept = crlf_body.replace("\r\n", "\n") in got_c.replace("\r\n", "\n")
            print("CRLF 底模：内容在位 %s，空行没被翻倍 %s" % (kept, not blank_doubled))
            if not kept:
                failures.append("验收 3b：CRLF 底模存完再装，内容变了")
            if blank_doubled:
                failures.append("验收 3b：CRLF 底模存完空行被翻倍（写盘把 \\n 又翻成了 \\r\\n）")
            post(base + "/api/unload", token, {"host_id": "fixture"})
            post(base + "/api/cards/delete", token, {"id": "自测CRLF底模"})
            post(base + "/api/load", token, {"host_id": "fixture", "base_id": "自测底模"})
            drop2 = post(base + "/api/unload", token, {"host_id": "fixture"})
            final2 = FIXTURE_ENTRY.read_bytes()
            print("卸完指纹一致：", final2 == original)
            if not drop2.get("ok") or final2 != original:
                failures.append("验收 3b：带底模卸完没还原")
            gone = post(base + "/api/cards/delete", token, {"id": "自测底模"})
            print("删卡 ->", json.dumps(gone, ensure_ascii=False))
            if not gone.get("ok"):
                failures.append("验收 3b：卡片没删掉")

        line("验收 3c：指引卡成品原样粘（顺序 标记/底模/原文/指引，三摘还原）")
        guest_text = ("技能包根：D:\\假包\\reverse-skill\n"
                      "触发词：逆向 破解 脱壳\n"
                      "0. 先读包根 routing\n1. 定入口\n2. 动手")
        made_g = post(base + "/api/cards", token, {"name": "自测指引", "hosts": "fixture",
                                                  "content": guest_text, "kind": "guest"})
        print("建指引卡 ->", json.dumps(made_g, ensure_ascii=False))
        if not made_g.get("ok") or made_g.get("kind") != "guest":
            failures.append("验收 3c：指引卡没建成")
        else:
            made_b = post(base + "/api/cards", token, {"name": "自测底模2", "hosts": "",
                                                      "content": card_body})
            load3 = post(base + "/api/load", token, {"host_id": "fixture",
                                                    "base_id": "自测底模2",
                                                    "guest_id": "自测指引"})
            got3 = FIXTURE_ENTRY.read_text(encoding="utf-8")
            i1 = got3.find(M_BEGIN)
            i2 = got3.find("# >>> hubcore base >>>")
            i3 = got3.find("假宿主的原文")
            i4 = got3.find("# >>> hubcore guest >>>")
            order3 = 0 <= i3 < i2 < i4 < i1
            verbatim = guest_text in got3
            print("四段顺序 原文/底模/指引/标记：", order3, "成品原样：", verbatim)
            if not load3.get("ok"):
                failures.append("验收 3c：三件套没装上")
            if not order3:
                failures.append("验收 3c：顺序不是 原文/底模/指引/标记块")
            if not verbatim:
                failures.append("验收 3c：指引成品被改了")
            drop3 = post(base + "/api/unload", token, {"host_id": "fixture"})
            final3 = FIXTURE_ENTRY.read_bytes()
            if not drop3.get("ok") or final3 != original:
                failures.append("验收 3c：三摘后没还原")
            print("三摘后指纹一致：", final3 == original)
            post(base + "/api/cards/delete", token, {"id": "自测指引"})
            post(base + "/api/cards/delete", token, {"id": "自测底模2"})

        line("验收 3d：卡片池分家 —— 挪出 hub/base/guest 子夹就不读，挪回来又能用")
        made_p = post(base + "/api/cards", token, {"name": "池子试验卡", "hosts": "fixture",
                                                   "content": "池子试验正文。"})
        pool_file = HERE / "cards" / "base" / "池子试验卡.md"
        park = HERE / "cards" / "_park" / "池子试验卡.md"
        park.parent.mkdir(parents=True, exist_ok=True)
        print("新卡落在 base/ 子夹：", pool_file.is_file())
        if not made_p.get("ok") or not pool_file.is_file():
            failures.append("验收 3d：新卡没落到 base/ 子夹")
        listed = [c["id"] for c in get(base + "/api/cards", token)["cards"]]
        print("在池子里被列出来：", "池子试验卡" in listed)
        if "池子试验卡" not in listed:
            failures.append("验收 3d：池子里的卡没被列出来")
        pool_file.replace(park)
        listed2 = [c["id"] for c in get(base + "/api/cards", token)["cards"]]
        blocked_p = post(base + "/api/load", token, {"host_id": "fixture", "base_id": "池子试验卡"})
        print("挪出子夹后：还列出来？", "池子试验卡" in listed2,
              "| 载入被拒？", (not blocked_p.get("ok")) and "base/" in str(blocked_p.get("error")))
        if "池子试验卡" in listed2:
            failures.append("验收 3d：挪出子夹的卡还留在列表里（等于没停用）")
        if blocked_p.get("ok") or "base/" not in str(blocked_p.get("error")):
            failures.append("验收 3d：挪出子夹的卡还能装上去")
        park.replace(pool_file)
        listed3 = [c["id"] for c in get(base + "/api/cards", token)["cards"]]
        print("挪回来：", "池子试验卡" in listed3)
        if "池子试验卡" not in listed3:
            failures.append("验收 3d：挪回来的卡没恢复")
        gone_p = post(base + "/api/cards/delete", token, {"id": "池子试验卡", "kind": "base"})
        left = [c["id"] for c in get(base + "/api/cards", token)["cards"]]
        print("删卡 ->", json.dumps(gone_p, ensure_ascii=False), "| 还剩这张？", "池子试验卡" in left)
        if not gone_p.get("ok") or "池子试验卡" in left:
            failures.append("验收 3d：试验卡没删干净")
        print("判定：", "通过" if (gone_p.get("ok") and "池子试验卡" not in left) else "不通过")

        line("验收 3e：中枢内核卡 = 标记块正文（换卡重装不叠块，卸回逐字节还原）")
        hub_card = HERE / "cards" / "hub" / "01-敏捷逆向攻坚.md"
        hub_text = "\n".join(hub_card.read_text(encoding="utf-8").splitlines()[3:]).strip("\n")
        hub_first = hub_text.splitlines()[0]
        load_h1 = post(base + "/api/load", token, {"host_id": "fixture", "hub_id": "01-敏捷逆向攻坚",
                                                  "replace_origin": True})
        got_h = FIXTURE_ENTRY.read_text(encoding="utf-8")
        print("装完：ok=%s | 块数=%d | 卡正文在=%s | 标记块在最末=%s"
              % (load_h1.get("ok"), got_h.count(M_BEGIN), hub_first in got_h,
                 got_h.rstrip("\r\n").endswith(M_END)))
        if not load_h1.get("ok") or got_h.count(M_BEGIN) != 1 or hub_first not in got_h:
            failures.append("验收 3e：中枢卡没写进标记块（或叠了块）")
        load_h2 = post(base + "/api/load", token, {"host_id": "fixture", "hub_id": "03-协议与自动化中枢",
                                                  "replace_origin": True})
        got_h2 = FIXTURE_ENTRY.read_text(encoding="utf-8")
        print("换一张卡重装：ok=%s | 块数=%d（必须是 1）" % (load_h2.get("ok"), got_h2.count(M_BEGIN)))
        if not load_h2.get("ok") or got_h2.count(M_BEGIN) != 1:
            failures.append("验收 3e：换卡重装叠块了（旧块没被认出来）")
        drop_h = post(base + "/api/unload", token, {"host_id": "fixture"})
        final_h = FIXTURE_ENTRY.read_bytes()
        print("卸回：ok=%s | 逐字节还原=%s | 文件里还剩几个 hubcore 字样=%d"
              % (drop_h.get("ok"), final_h == original,
                 FIXTURE_ENTRY.read_text(encoding="utf-8").count("hubcore")))
        if not drop_h.get("ok") or final_h != original:
            failures.append("验收 3e：装了中枢内核卡之后卸不干净（卸回认不出自己写的块）")
        print("判定：", "通过" if (load_h1.get("ok") and load_h2.get("ok")
                                   and got_h2.count(M_BEGIN) == 1 and final_h == original
                                   and drop_h.get("ok")) else "不通过")

        line("验收 3g：node 承载的宿主（pi / claude / gemini…）不许被包内那份探针拒装")
        argv_probe = bundle_locator._argv_install(Path("C:/tmp/x"), allow_running=True)
        has_flag = "--allow-running" in argv_probe
        print("交给打包器的命令行带 --allow-running：", has_flag)
        if not has_flag:
            failures.append("验收 3g：控制台没把「已确认空闲」传下去（node 宿主会被包内探针拒装）")
        node_home = Path(os.environ.get("USERPROFILE") or Path.home()) / ".pi" / "agent"
        if node_home.is_dir():
            def _dry(extra):
                return subprocess.run([sys.executable, "-B", str(BUNDLE / "install.py"),
                                       "--source", str(BUNDLE / "dist" / "hubcore"),
                                       "--host-home", str(node_home), "--dry-run"] + extra,
                                      capture_output=True, text=True,
                                      encoding="utf-8", errors="replace", timeout=120)
            r_with = _dry(["--allow-running"])
            out_with = (r_with.stdout or "") + (r_with.stderr or "")
            ok_with = r_with.returncode == 0 and "读不出这家是否正在跑" not in out_with
            print("带 --allow-running 试运行：rc=%d | 没被拒=%s" % (r_with.returncode, ok_with))
            if not ok_with:
                failures.append("验收 3g：包内探针把空闲的 node 宿主拒了（rc=%d）" % r_with.returncode)
            r_without = _dry([])
            out_without = (r_without.stdout or "") + (r_without.stderr or "")
            print("不带 --allow-running：rc=%d | %s" % (
                r_without.returncode,
                "按设计拒绝（本包探针认不出 node 宿主）" if "读不出这家是否正在跑" in out_without
                else "这台机器上探针认得出来，不算红"))
        else:
            print("本机没有 .pi/agent 这个家，跳过真跑那一半（上面那条命令行判据仍算数）")

        line("验收 3h：直写模式（选中的几层拼一份 → 整份替换；卸回 = 按保险箱换回来）")
        dhome = TEMP / "direct-home"
        if dhome.exists():
            shutil.rmtree(dhome)
        dhome.mkdir(parents=True)
        dentry = dhome / "AGENTS.md"
        dentry.write_text("# 直写试验原文\n\n这一行要能退回来。\n", encoding="utf-8")
        dbefore = dentry.read_bytes()
        add9 = post(base + "/api/hosts/add", token, {"name": "直写试验家", "home": str(dhome)})
        hid9 = add9.get("id") or ""
        if not add9.get("ok"):
            failures.append("验收 3h：加不进这家")
        else:
            d1 = post(base + "/api/load", token, {"host_id": hid9, "mode": "direct",
                                                 "hub_id": "01-敏捷逆向攻坚"})
            dt = dentry.read_text(encoding="utf-8")
            steps9 = [s.get("name") for s in (d1.get("steps") or [])]
            print("直写：ok=%s | 卡正文在=%s | 没有我们的标记行=%s | 原文清空=%s | %d 字节"
                  % (d1.get("ok"), "# [内核执行协议 · 敏捷逆向攻坚]" in dt,
                     M_BEGIN not in dt, "直写试验原文" not in dt, len(dt.encode("utf-8"))))
            print("步骤：", steps9)
            if not d1.get("ok") or "# [内核执行协议 · 敏捷逆向攻坚]" not in dt:
                failures.append("验收 3h：直写没写进去")
            if M_BEGIN in dt:
                failures.append("验收 3h：直写还留了我们的标记行（本该是一份干净文本）")
            if "直写试验原文" in dt:
                failures.append("验收 3h：直写没把原来的清掉")
            if "定位打包器" in steps9:
                failures.append("验收 3h：直写还去叫打包器了")
            d2 = post(base + "/api/unload", token, {"host_id": hid9, "mode": "direct"})
            back9 = dentry.read_bytes() == dbefore
            print("卸回（按保险箱换回来）：ok=%s | 逐字节还原=%s" % (d2.get("ok"), back9))
            if not d2.get("ok") or not back9:
                failures.append("验收 3h：直写模式退不回原文")
            post(base + "/api/hosts/remove", token, {"id": hid9})
            shutil.rmtree(dhome, ignore_errors=True)

        line("验收 8：保险箱（拍 → 装 → 比对 → 恢复）—— 这一条以前一条测试都没有")
        box = TEMP / "safebox-e2e-home"
        if box.exists():
            shutil.rmtree(box)
        box.mkdir(parents=True)
        box_entry = box / "AGENTS.md"
        box_entry.write_text("# 自测假家原文\n\n这一行装前装后都要一样。\n", encoding="utf-8")
        before8 = box_entry.read_bytes()
        added8 = post(base + "/api/hosts/add", token, {"name": "保险箱试验家", "home": str(box)})
        print("手加这家 ->", json.dumps(added8, ensure_ascii=False))
        hid8 = added8.get("id") or ""
        if not added8.get("ok"):
            failures.append("验收 8：加不进这家")
        else:
            snap8 = post(base + "/api/safebox", token, {"host_id": hid8, "action": "snapshot"})
            print("锁定保险箱 ->", json.dumps(snap8, ensure_ascii=False)[:300])
            if not snap8.get("ok"):
                failures.append("验收 8：保险箱没拍成")
            # 保险箱落在 %LOCALAPPDATA%，按宿主 id 分目录，**跨测试运行会留下上一轮的快照**，
            # 所以只能比"载入前 vs 载入后"的差，不能断言绝对张数。
            # 列表是 GET 接口，用 post() 调会 400 拿到空列表（这个坑踩过一次）。
            tags_before = [s.get("tag") for s in
                           (get(base + "/api/safebox?host_id=" + hid8, token)
                            .get("snapshots") or [])]
            load8 = post(base + "/api/load", token, {"host_id": hid8})
            print("装 ->", json.dumps(load8, ensure_ascii=False)[:400])
            steps8 = [s.get("name") for s in (load8.get("steps") or [])]
            print("装的步骤：", steps8)
            if "保险箱" not in steps8:
                failures.append("验收 8：载入前没自动拍保险箱（没拍就不该写）")
            if not load8.get("ok"):
                failures.append("验收 8：没装上")
            # 已经有保险箱就不许覆盖：主人手里那一版是基准，
            # 每次载入自动重拍等于把基准换成"这次之前的样子"，第一次之后基准就永远丢了。
            tags_after = [s.get("tag") for s in
                          (get(base + "/api/safebox?host_id=" + hid8, token)
                           .get("snapshots") or [])]
            print("载入前 %d 版 -> 载入后 %d 版" % (len(tags_before), len(tags_after)))
            if tags_after != tags_before:
                failures.append("验收 8：已有保险箱时载入又拍了一张（%s -> %s）"
                                % (tags_before, tags_after))
            if snap8.get("tag") not in tags_after:
                failures.append("验收 8：载入把主人按下的那一版保险箱覆盖了（tag %s 不在了）"
                                % snap8.get("tag"))
            cmp8 = post(base + "/api/safebox", token, {"host_id": hid8, "action": "verify"})
            print("比对 ->", json.dumps(cmp8, ensure_ascii=False)[:300])
            if cmp8.get("http_status") == 400:
                failures.append("验收 8：比对发现差异被回成 400（页面会当成失败，主人看不到清单）")
            if cmp8.get("same") is not False or not cmp8.get("diffs"):
                failures.append("验收 8：装完比对没说不一样，也说不出是哪几个文件")
            box_entry.write_text(box_entry.read_text(encoding="utf-8") + "\n我自己又加的一行。\n",
                                 encoding="utf-8")
            cmp8b = post(base + "/api/safebox", token, {"host_id": hid8, "action": "verify"})
            print("主人再改一笔后比对 ->", json.dumps(cmp8b, ensure_ascii=False)[:300])
            res8 = post(base + "/api/safebox", token, {"host_id": hid8, "action": "restore"})
            print("按保险箱恢复 ->", json.dumps(res8, ensure_ascii=False)[:300])
            back = box_entry.read_bytes() == before8
            print("入口文件逐字节回到装前：", back)
            if not res8.get("ok") or not back:
                failures.append("验收 8：按保险箱恢复没还原")
            cmp8c = post(base + "/api/safebox", token, {"host_id": hid8, "action": "verify"})
            print("恢复后再比对 ->", json.dumps(cmp8c, ensure_ascii=False)[:300])
            # 中枢自己装的 hub/ 不归保险箱管，那一处差异不算还原失败。
            if res8.get("ok") and not back:
                failures.append("验收 8：恢复后还是不一样")

            line("验收 8b：保险箱就是一份 .bak —— 落在盘上、再锁就覆盖、恢复时用掉")
            box_root = (Path(os.environ.get("LOCALAPPDATA")
                             or str(Path.home() / "AppData" / "Local"))
                        / "HubCoreConsole" / "safebox" / hid8)
            # 上面那次「恢复」已经把备份用掉了（新的规矩：恢复＝把 bak 换回 md），
            # 所以这里重新锁一份，再看盘上是不是只有一份。
            post(base + "/api/safebox", token, {"host_id": hid8, "action": "snapshot"})
            baks = sorted(p.name for p in box_root.glob("*.bak"))
            print("重新锁一份，盘上的 .bak：", baks)
            if len(baks) != 1:
                failures.append("验收 8b：锁一次之后盘上的 .bak 不是 1 份（%d 份）" % len(baks))
            else:
                first = box_root / baks[0]
                if first.read_bytes() != before8:
                    failures.append("验收 8b：.bak 跟锁定时那份入口文件不是逐字节一样")
            for _ in range(5):
                post(base + "/api/safebox", token, {"host_id": hid8, "action": "snapshot"})
            left = sorted(p.name for p in box_root.glob("*.bak"))
            print("连按 5 次锁定后还剩 %d 份：%s" % (len(left), left))
            if len(left) != 1:
                failures.append("验收 8b：再锁没有覆盖旧的（剩 %d 份）" % len(left))
            else:
                fresh = (box_root / left[0])
                same_bytes = fresh.read_bytes() == box_entry.read_bytes()
                print("新的那一份 = 现在这份入口文件：", same_bytes)
                if not same_bytes:
                    failures.append("验收 8b：覆盖后的 .bak 不是当前入口文件")
            gone_note = post(base + "/api/safebox", token, {"host_id": hid8, "action": "restore"})
            used_up = not list(box_root.glob("*.bak"))
            again = post(base + "/api/safebox", token, {"host_id": hid8, "action": "restore"})
            print("恢复一次：ok=%s | .bak 被用掉=%s | 再恢复=%s（应该不成，因为没备份了）"
                  % (gone_note.get("ok"), used_up, again.get("ok")))
            if not gone_note.get("ok") or not used_up:
                failures.append("验收 8b：恢复没把 .bak 用掉（按设计要一次性）")
            if again.get("ok"):
                failures.append("验收 8b：备份用掉之后还能恢复（不该能）")

            post(base + "/api/hosts/remove", token, {"id": hid8})
            shutil.rmtree(box, ignore_errors=True)

        line("验收 9：CRLF 入口文件（主人用 Windows 编辑器存过）+ 卡片含定界行，两条都要挡住")
        crlf_home = TEMP / "crlf-home"
        if crlf_home.exists():
            shutil.rmtree(crlf_home)
        crlf_home.mkdir(parents=True)
        crlf_entry = crlf_home / "AGENTS.md"
        crlf_text = "# CRLF 假家\r\n\r\n这一行装前装后都要一样。\r\n"
        crlf_entry.write_bytes(b"\xef\xbb\xbf" + crlf_text.encode("utf-8"))
        crlf_card = TEMP / "crlf-card.md"
        crlf_card.write_text("# base: 底模-crlf\n# kind: base\n\n先看证据再下结论。\n", encoding="utf-8")
        r9 = subprocess.run(
            [sys.executable, "-B", str(BUNDLE / "install.py"), "--source",
             str(BUNDLE / "dist" / "hubcore"), "--host-home", str(crlf_home),
             "--base", str(crlf_card)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        print("CRLF 家装上 rc =", r9.returncode)
        crlf_after_install = crlf_entry.read_bytes()
        print("装完：BOM 还在 →", crlf_after_install.startswith(b"\xef\xbb\xbf"),
              "| 标记块在 →", b"# >>> hubcore hub >>>" in crlf_after_install,
              "| 原文在 →", crlf_text.strip().encode("utf-8") in crlf_after_install)
        if r9.returncode:
            failures.append("验收 9：CRLF 家装不上")
        if not crlf_after_install.startswith(b"\xef\xbb\xbf"):
            failures.append("验收 9：装完 BOM 掉了（改了主人的编码）")
        if b"# >>> hubcore hub >>>" not in crlf_after_install:
            failures.append("验收 9：装完 CRLF 文件里没有标记块")
        # 模拟主人在 CRLF 文件里自己加一行（真实编辑器保存就是这个效果）
        crlf_entry.write_bytes(crlf_after_install + "\r\n我自己又加的一行。\r\n".encode("utf-8"))
        r9b = subprocess.run(
            [sys.executable, "-B", str(BUNDLE / "uninstall.py"), "--host-home",
             str(crlf_home), "--yes"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        crlf_left = crlf_entry.read_bytes()
        print("卸回 rc =", r9b.returncode)
        print("卸完：标记块还在 →", b"# >>> hubcore hub >>>" in crlf_left,
              "| 底模还在 →", "先看证据再下结论".encode("utf-8") in crlf_left)
        print("       主人自己那行还在 →", "我自己又加的一行".encode("utf-8") in crlf_left,
              "| BOM 还在 →", crlf_left.startswith(b"\xef\xbb\xbf"))
        if b"# >>> hubcore hub >>>" in crlf_left:
            failures.append("验收 9：CRLF 文件卸回后标记块还在（装得上卸不掉）")
        if "先看证据再下结论".encode("utf-8") in crlf_left:
            failures.append("验收 9：CRLF 文件卸回后底模块还在")
        if "我自己又加的一行".encode("utf-8") not in crlf_left:
            failures.append("验收 9：卸回落主人自己写的那行被动了")
        if not crlf_left.startswith(b"\xef\xbb\xbf"):
            failures.append("验收 9：卸回后 BOM 掉了")
        # 卡片正文里混进定界行必须拒装（否则卸回只摘半块，卡片尾巴留在主人原文里）
        bad_card = TEMP / "bad-delim-card.md"
        bad_card.write_text("# base: 带定界行\n# kind: base\n\n"
                           "正常一行\n# <<< hubcore guest <<<\n再一行\n", encoding="utf-8")
        r9c = subprocess.run(
            [sys.executable, "-B", str(BUNDLE / "install.py"), "--source",
             str(BUNDLE / "dist" / "hubcore"), "--host-home", str(crlf_home),
             "--base", str(bad_card)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        bad_said = ((r9c.stdout or "") + (r9c.stderr or ""))
        print("带定界行的卡装上去 rc =", r9c.returncode, "| 拒的理由：",
              ("定界行" in bad_said))
        if r9c.returncode == 0 or "定界行" not in bad_said:
            failures.append("验收 9：卡片正文含定界行竟然装上去了")
        shutil.rmtree(crlf_home, ignore_errors=True)

        # 验收 9b：**结尾没有换行**的入口文件，装完再卸完必须逐字节回到装前。
        # 这不是边角，是很常见的文件形态。装的时候要给原文补一个分隔换行
        # （不补，标记块首行会粘在主人最后一行上，按行锚点摘不干净），
        # 那个换行是我们加的 —— 卸的时候必须认出来还原。
        # 认不出来就有两个后果：多一个字节；更糟的是这一个字节差被当成
        # 「主人自己改过」，于是走「只摘块不覆盖」，把换行永久留在主人文件里还报告成正常。
        line("验收 9b：结尾没有换行的入口文件，装完再卸完逐字节回到装前")
        nonl_home = TEMP / "nonl-home"
        if nonl_home.exists():
            shutil.rmtree(nonl_home)
        nonl_home.mkdir(parents=True)
        nonl_entry = nonl_home / "AGENTS.md"
        # 故意不以换行收尾（最后一行就是最后一行）
        nonl_before = "# 我的规则\n\n这一段没有结尾换行。".encode("utf-8")
        nonl_entry.write_bytes(nonl_before)
        r9d = subprocess.run(
            [sys.executable, "-B", str(BUNDLE / "install.py"), "--source",
             str(BUNDLE / "dist" / "hubcore"), "--host-home", str(nonl_home)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        nonl_installed = nonl_entry.read_bytes()
        print("无结尾换行家装上 rc =", r9d.returncode,
              "| 标记块在 →", b"# >>> hubcore hub >>>" in nonl_installed,
              "| 原文在 →", "这一段没有结尾换行。".encode("utf-8") in nonl_installed)
        if r9d.returncode:
            failures.append("验收 9b：无结尾换行家装不上")
        if b"# >>> hubcore hub >>>" not in nonl_installed:
            failures.append("验收 9b：装完文件里没有标记块")
        # 主人在装完到卸回之间**一个字都没改** —— 这时候必须整份还原，不能只摘块
        r9e = subprocess.run(
            [sys.executable, "-B", str(BUNDLE / "uninstall.py"), "--host-home",
             str(nonl_home), "--yes"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        nonl_left = nonl_entry.read_bytes()
        said = (r9e.stdout or "") + (r9e.stderr or "")
        print("卸回 rc =", r9e.returncode,
              "| 装前 %d 字节 → 卸后 %d 字节" % (len(nonl_before), len(nonl_left)),
              "| 逐字节相同 →", nonl_left == nonl_before)
        if nonl_left != nonl_before:
            failures.append("验收 9b：装完再卸完没有逐字节回到装前（多 %+d 字节）"
                            % (len(nonl_left) - len(nonl_before)))
        if "主人自己改过" in said or "属正常" in said:
            failures.append("验收 9b：我们自己补的换行被误报成「主人自己改过」")
        shutil.rmtree(nonl_home, ignore_errors=True)

        line("验收 4：前端 HTML/JS 里不许出现的字样")
        targets = [HERE / "web" / "index.html", HERE / "web" / "app.js", HERE / "web" / "style.css"]
        for target in targets:
            body = target.read_text(encoding="utf-8")
            hits = [word for word in BANNED if word in body]
            print(f"{target.name:<12} 命中：{hits if hits else '无'}")
            if hits:
                failures.append(f"验收 4：{target.name} 出现 {hits}")
        page_res = urllib.request.urlopen(
            urllib.request.Request(base + "/", headers=dict(_auth_headers(token))), timeout=10
        )
        page_body = page_res.read().decode("utf-8")
        print("首页正文长度：", len(page_body), "字符")
        page_hits = [word for word in BANNED if word in page_body]
        print("服务端发出来的首页命中：", page_hits if page_hits else "无")
        if page_hits:
            failures.append(f"验收 4：首页出现 {page_hits}")

        line("验收 5：服务只绑回环")
        print("绑定地址：", console.BIND_HOST, "端口：", port)
        print("回环可连：", console.is_loopback_bind(port))
        net = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
        lines = [ln for ln in (net.stdout or "").splitlines()
                 if f":{port}" in ln and "LISTENING" in ln.upper()]
        bad: list[str] = []
        for ln in lines:
            print("netstat:", ln.strip())
            local = ln.split()[1] if len(ln.split()) > 1 else ""
            if not (local.startswith("127.0.0.1:") or local.startswith("[::1]:")):
                bad.append(local)
        if bad:
            failures.append(f"验收 5：不是回环绑定 {bad}")
        print("判定：", "通过" if lines and not bad else "不通过")

        line("验收 6：浏览器真实链路（不带任何凭证开页面拿 Cookie，再调接口）")
        for asset in ("/app.js", "/style.css"):
            try:
                with urllib.request.urlopen(base + asset, timeout=10) as res:
                    body = res.read()
                print(f"{asset} 无凭证 -> {res.status}，{len(body)} 字节")
                if res.status != 200 or len(body) < 500:
                    failures.append(f"验收 6：{asset} 浏览器拿不到，页面裸奔")
            except urllib.error.HTTPError as exc:
                print(f"{asset} 无凭证 -> {exc.code}（页面会裸奔）")
                failures.append(f"验收 6：{asset} 无凭证被拒，页面裸奔")
        # 页面外壳必须对环回来客开着（不然页面永远起不来，令牌从哪来），
        # 真正上锁的是 /api/。
        try:
            with urllib.request.urlopen(base + "/", timeout=10) as res:
                res.read()
                print("首页无凭证 ->", res.status, "（应该 200：它只负责发会话 Cookie）")
                if res.status != 200:
                    failures.append("验收 6：首页无凭证打不开")
        except urllib.error.HTTPError as exc:
            print("首页无凭证 ->", exc.code)
            failures.append("验收 6：首页无凭证不是 200")
        for api in ("/api/status", "/api/hosts"):
            try:
                urllib.request.urlopen(base + api, timeout=10).read()
                print(f"{api} 无凭证 -> 200（不该放行）")
                failures.append(f"验收 6：{api} 无凭证被放行")
            except urllib.error.HTTPError as exc:
                print(f"{api} 无凭证 -> {exc.code}")
                if exc.code != 403:
                    failures.append(f"验收 6：{api} 无凭证不是 403")

        line("验收 7：页面骨架与脚本对得上（id 全都存在，不然页面变死）")
        html = (HERE / "web" / "index.html").read_text(encoding="utf-8")
        js = (HERE / "web" / "app.js").read_text(encoding="utf-8")
        have = set(re.findall(r'id="([^"]+)"', html))
        want = set(re.findall(r"\$\('([^']+)'\)", js))
        want |= set(re.findall(r"getElementById\('([^']+)'\)", js))
        missing = sorted(want - have - {"tiles-base", "tiles-guest"})
        print("页面 %d 个 id，脚本引用 %d 个；缺 %s" % (len(have), len(want), missing or "无"))
        if missing:
            failures.append("验收 7：脚本引用的 id 页面上没有 -> 加载即抛错，页面变死：%s" % missing)
        for tag in ("script", "style", "switch", "tile"):
            if tag == "script" and "<script src=\"app.js\">" not in html:
                failures.append("验收 7：页面没挂 app.js")
        if "window.addEventListener('error'" not in js:
            failures.append("验收 7：脚本没有兜错，出错会静悄悄变死页")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    line("打包器原样输出（stdio 继承终端，控制台没吞掉）")
    for item in list(stream):
        print("  " + item)

    line("总判")
    if failures:
        for item in failures:
            print("不通过：", item)
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
