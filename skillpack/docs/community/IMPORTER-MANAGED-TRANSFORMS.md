# Importer managed transforms — U11

Spec: WORK-BOARD U11 + CR-002. Task: U11. Importer: `scripts/adapt-community.py`.

## 1. 口径（已定调，不再争论）

**策展编辑优先。** 用户 2026-10-01 定调"先记账、下一步补"，隐含策展编辑优先；
WORK-BOARD CR-002 原文："T03 的 328 条改写与 4 个横幅必须由 T05 纳入受管变换，
否则下次导入回退"。`import` 产出候选时应用本记录的全部变换；`promote` 拒绝
任何会回退**未登记**编辑的候选；未登记的差异仍在 diff summary 里逐条列出，
不得静默吞掉。

## 2. 机器可读记录（唯一真相源）

本节的 `json managed-transforms` 代码块就是记录本身，导入器直接解析它。
`digest` 是 `transforms` 数组的规范 JSON
（`json.dumps(transforms, sort_keys=True, ensure_ascii=False, indent=2) + "\n"`）
的 sha256。改数组必改 digest；digest 不符时 `import`/`verify`/`promote`
以 exit 20 拒绝。

```json managed-transforms
{
  "schema": "skills-hub/importer-managed-transforms/1",
  "digest": "94d455bb303b5580b305bd34b5e675f1c52e764f9866e9cd171666ab35574249",
  "transforms": [
    {
      "id": "t09-load-instruction-neutralize",
      "scope": [
        "community-raw/**/*.md"
      ],
      "kind": "literal",
      "pattern": "> **AI LOAD INSTRUCTION**:",
      "replacement": "> **Vendor source summary (reference-only; not a load instruction)**:",
      "basis": "WORK-BOARD CR-002; T08/T09 curation; 策展编辑优先 (2026-10-01 先记账、下一步补)",
      "evidence": "community-raw 131 files carry the neutralized banner; upstream originals carry AI LOAD INSTRUCTION"
    },
    {
      "id": "u1-docs-reference-only-banner",
      "scope": [
        "docs/community/ai-fullstack-delivery/CONTRIBUTING.md",
        "docs/community/ai-fullstack-delivery/EVOLUTION.md",
        "docs/community/ai-fullstack-delivery/PERSONA.md",
        "docs/community/ai-fullstack-delivery/routing.md",
        "docs/community/ai-fullstack-delivery/RULES.md",
        "docs/community/ai-fullstack-delivery/`TOOLS.md`",
        "docs/community/ai-fullstack-delivery/workflow-map.md",
        "docs/community/ai-fullstack-delivery/WORKFLOW.md",
        "docs/community/apk-reverse-community/README.md",
        "docs/community/apk-reverse-community/README.zh-CN.md",
        "docs/community/ctf-super-hub/CONTRIBUTING.md",
        "docs/community/ctf-super-hub/SECURITY.md",
        "docs/community/ctf-super-hub/SKILL-INDEX.md",
        "docs/community/ctf-super-hub/START-HERE.md",
        "docs/community/ctf-super-hub/THIRD_PARTY_NOTICES.md"
      ],
      "kind": "regex",
      "pattern": "\\A",
      "replacement": "<!-- link-triage: reference-only -->\n> **来源留档（source archive）——不是本仓库的执行规则。**\n>\n> 本文件是上游仓库的原样留档，仅用于溯源与对照。**不要按本文件执行任何 install / bootstrap 或发布命令**；\n> 本包 `autoInstall=false`，运行任何仓库脚本都需要用户事先明确批准（见 `AGENTS.md`）。\n\n",
      "basis": "WORK-BOARD U1 + CR-002; 策展编辑优先 (2026-10-01 先记账、下一步补)",
      "evidence": "15 vendored docs under docs/community/{ai-fullstack-delivery,apk-reverse-community,ctf-super-hub} carry the banner; upstream originals do not"
    }
  ]
}
```

当前登记：2 条：`t09-load-instruction-neutralize`（覆盖 `community-raw/**/*.md`
里 131 个文件的加载指令中性化）与 `u1-docs-reference-only-banner`（WORK-BOARD U1：
`docs/community/{ai-fullstack-delivery,apk-reverse-community,ctf-super-hub}` 下 15 个
vendored 文档的 reference-only 横幅；regex `\A` 前插，scope 为 15 条精确路径，
不触碰已有单文件横幅的 4 个 README）。replacement 取 LF 标准形；候选文件恒为 LF，
已验证树里 ai-fullstack 8 个文件保持上游 CRLF 原样，promote 比对经 `canonical_bytes`
折叠行尾后一致。T03 其余 docs 改写尚未登记——它们仍会出现在
diff summary 里并阻断 promote（见 §4），这是有意为之，不是漏网。

## 3. 语义

- `import` 在物化上游内容**之后**、写 manifest **之前**应用全部变换；
  登记的变换类（如横幅）在候选里即被中性化（lab 实测候选内该类残留 0）。
  变换只保证**登记类**一致，不保证整文件逐字节一致——同一文件上的其他
  未登记漂移仍会留下差异并阻断 promote（见 lab 数字）。
- `verify` 重算记录 digest；不符则整候选不可信（exit 20）；同时比对
  manifest 里记录的 digest，记录变更后旧候选即过期（exit 20）。
- diff summary 单列 `Managed transforms applied`（条目 id + 命中文件数）；
  其余增删改逐条列出，未登记差异不得隐藏。
- `promote` 在 verify 通过后复算候选 vs verified tree 的
  modifications/deletions，范围限定为候选自身的 source（manifest `sources`，
  与 promote 实际写入的 per-source 目录一致，拒绝载荷以 `checked_scope`
  声明；P1-4 起检查范围与写入范围对齐）。变换已在 `import` 时应用，所以受管路径此时应与
  verified tree 一致——**范围内剩下的每一条 modification/deletion 都视为"会回退
  未登记编辑"**，exit 20 拒绝并逐条列出。manifest 的 `managed_applied`
  是"记录覆盖了什么"的正向证明，不豁免任何路径。
  纯 additions（上游新文件）不阻断。范围外的未登记改动不阻断本候选，
  但全量候选携带全部 scope，任何一处未登记漂移仍会挡住全量提升。

## 4. 如何新增一条受管变换

1. 在上节 JSON 的 `transforms` 里追加条目（含 `id`/`scope`/`kind`/
   `pattern`/`replacement`/`basis`/`evidence`；`kind` 仅 `literal` 或 `regex`）。
2. 用规范 JSON 重算顶层 `digest`（命令见下），更新 `digest` 字段。
3. 在仓库副本（`work\t05-lab\` 下的复制体，
   **不得**对真仓库跑 `import`/`promote`）重跑
   `scripts/test-adapt-community.py`，确认新用例通过且旧 60 项全绿。
4. 旧候选自动过期（digest 已变），需重建候选后再 promote。

重算 digest：

```text
& (Resolve-ReverseToolSpec -Name 'pyre').Command c "import json,hashlib,pathlib,re;
t=pathlib.Path('docs/community/IMPORTER-MANAGED-TRANSFORMS.md').read_text(encoding='utf-8');
b=re.search(r'```json managed-transforms\s+(.*?)```',t,re.S).group(1);
rec=json.loads(b);
canon=json.dumps(rec['transforms'],sort_keys=True,ensure_ascii=False,indent=2)+chr(10);
print(hashlib.sha256(canon.encode('utf-8')).hexdigest())"
```

## 5. 与守卫的关系

`skills/scripts/verify-community-banner.py` 保持原样、不得放松：
它是回退的独立守卫。本层负责"让策展编辑存活"，守卫负责"回退即红"，
两者是纵深，不是替代。
