#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 grok/cursor jsonl 抽出主人原话，追加进 OWNER-SPEECH.md。不写进功能表。不是运行核。"""
import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from hub_io import _file_lock, _inside_no_links

QUERY_RE = re.compile(r"<user_query>\s*(.*?)\s*</user_query>", re.S)
SKIP_TYPES = {"assistant", "system", "tool", "function", "tool_result", "tool_call", "system_reminder"}
SKIP_PREFIX = ("<user_info>", "<git_status>", "<rules>", "<system-reminder>",
               "This session is being continued", "<always_applied")


def _text_of(content):
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        bits = []
        for part in content:
            if isinstance(part, str):
                bits.append(part)
            elif isinstance(part, dict):
                bits.append(str(part.get("text") or part.get("content") or ""))
        return "\n".join(x for x in bits if x).strip()
    if isinstance(content, dict):
        return str(content.get("text") or content.get("content") or "").strip()
    return str(content).strip()


def _from_obj(obj):
    if not isinstance(obj, dict):
        return []
    msg = obj.get("message") if isinstance(obj.get("message"), dict) else {}
    roles = {str(role).lower() for role in (obj.get("type"), obj.get("role"), msg.get("role")) if role}
    if roles & SKIP_TYPES or not roles & {"user", "user_query"}:
        return []
    if obj.get("synthetic_reason") == "system_reminder":
        return []
    blob = _text_of(obj.get("content") or obj.get("text") or obj.get("user_query"))
    if isinstance(msg, dict):
        mrole = (msg.get("role") or "").lower()
        if mrole in SKIP_TYPES:
            return []
        blob = blob or _text_of(msg.get("content") or msg.get("text"))
    tagged = [m.strip() for m in QUERY_RE.findall(blob or "") if m.strip()]
    if tagged:
        return tagged
    t = (blob or "").strip()
    if not t:
        return []
    if t.startswith(SKIP_PREFIX):
        return []
    return [t]


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON 字段重复：{key}")
        result[key] = value
    return result


def _history_index(existing):
    seen = {}
    lines = existing.split("\n")
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.startswith("<!-- hub-speech "):
            index += 1
            continue
        match = re.fullmatch(r"<!-- hub-speech ([a-f0-9]{64}) ([a-f0-9]{64}) -->", line)
        if not match:
            raise ValueError("原话流水来源标记损坏，请先恢复完整记录")
        key, digest = match.groups()
        index += 1
        if index >= len(lines) or lines[index] != "- 主人原话：":
            raise ValueError("原话流水缺少正文，不能把半条记录当作已经导入")
        index += 1
        body = []
        while index < len(lines) and lines[index].startswith("  "):
            body.append(lines[index][2:])
            index += 1
        if (index >= len(lines) or lines[index] != f"<!-- /hub-speech {key} -->"
                or _digest("\n".join(body)) != digest or key in seen):
            raise ValueError("原话流水正文、结束标记或来源摘要不一致，请先恢复完整记录")
        seen[key] = digest
        index += 1
    return seen


def _iter_jsonl(path, source_id=None):
    events = []
    raw = Path(path).read_text(encoding="utf-8-sig")
    source = source_id or os.path.normcase(str(Path(path).resolve()))
    for number, line in enumerate(raw.split("\n"), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line, object_pairs_hook=_unique_object)
        except ValueError as exc:
            raise ValueError(f"{path.name}:{number} JSON 损坏：{exc}") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"{path.name}:{number} 记录必须是对象")
        message = obj.get("message") if isinstance(obj.get("message"), dict) else {}
        native_id = obj.get("uuid") or obj.get("id") or obj.get("message_id") or message.get("id") or message.get("uuid")
        identity = ["id", str(native_id)] if native_id else ["line", number]
        for part, value in enumerate(_from_obj(obj)):
            value = value.replace("\r\n", "\n").replace("\r", "\n")
            key = _digest(json.dumps([source, identity, part], ensure_ascii=False))
            events.append((key, _digest(value), value))
    return events


def main():
    ap = argparse.ArgumentParser(description="抽出主人原话追加到 OWNER-SPEECH.md，禁止压进功能表")
    ap.add_argument("--product", required=True)
    ap.add_argument("--from", dest="src", required=True, help="jsonl 文件或目录")
    ap.add_argument("--source-id", help="稳定会话标识；单文件换路径导入时使用同一个标识")
    args = ap.parse_args()
    from hub_cmds import _is_hub_tree, _HUB_NOT_PRODUCT
    if _is_hub_tree(args.product):
        print(_HUB_NOT_PRODUCT, file=sys.stderr)
        return 2
    src = Path(args.src)
    files = []
    if src.is_dir():
        files = sorted(src.rglob("*.jsonl"))
    elif src.is_file():
        files = [src]
    else:
        print("找不到对话文件。", file=sys.stderr)
        return 2
    if args.source_id and len(files) != 1:
        print("--source-id 只用于单个会话文件。", file=sys.stderr)
        return 2
    root = Path(args.product).resolve()
    try:
        # Parse the whole import before appending anything. A bad source must
        # not silently delete an instruction or leave a partial batch behind.
        events = [event for f in files for event in _iter_jsonl(f, args.source_id)]
        if not events:
            print("没有抽出主人原话。没有改功能表。")
            return 1
        dest = _inside_no_links(root, "OWNER-SPEECH.md")
        with _file_lock(dest):
            old_bytes = dest.read_bytes() if dest.exists() else b""
            existing = old_bytes.decode("utf-8-sig")
            seen = _history_index(existing)
            got = []
            for key, digest, value in events:
                if key in seen:
                    if seen[key] != digest:
                        raise ValueError("同一来源事件的原话被改写；请核对导出来源，不能覆盖历史。")
                    continue
                seen[key] = digest
                got.append((key, digest, value))
            if not got:
                print("这些来源事件已经记录，本次没有重复追加。")
                return 0
            block = ["\n" if existing else "# 主人原话流水\n\n只追加。不许压成功能表。\n\n---\n"]
            for key, digest, value in got:
                block.extend([f"<!-- hub-speech {key} {digest} -->", "- 主人原话："])
                block.extend(f"  {line}" for line in value.split("\n"))
                block.append(f"<!-- /hub-speech {key} -->")
                block.append("")
            # Build a complete replacement in disposable space. os.replace is
            # on the same volume; a failed write cannot leave a half event.
            scratch = _inside_no_links(root, "TEMP")
            scratch.mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="speech-", dir=scratch) as tmp:
                pending = Path(tmp) / "OWNER-SPEECH.md"
                pending.write_bytes(old_bytes + ("\n".join(block).rstrip() + "\n").encode("utf-8"))
                os.replace(pending, dest)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"拒绝导入：{exc}", file=sys.stderr)
        return 2
    print(f"已追加 {len(got)} 条主人原话到 OWNER-SPEECH.md。没有写入 FEATURES.md。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
