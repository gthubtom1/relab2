---
name: Strix•Nuclei 用法
description: Strix Nuclei 命令手册,覆盖模板选择、高吞吐执行与自动化边界控制;触发名:strix-nuclei
license: "review-required"
compatibility: "Requires the canonical reverse-skill case/scope contract; source tools are optional."
allowed-tools: Read Write Edit Glob Grep Bash
metadata:
  integrated: "true"
  integration-source: "ctf-super-hub"
  source-path: "strix-nuclei/SKILL.md"
  maturity: "partial"
  integration-risk: "medium"
  allowed-context: "offline-ctf,authorized-lab"
  user-invocable: "false"
---


## Integrated reverse-skill contract

This capability is loaded through the canonical reverse-skill router. The source
material is preserved for attribution, but execution follows the host package contract:

1. **Scope first**: initialize the current `work/<case>/scope.md` with the canonical
   `case-init` flow. A target action requires an authorized scope or an explicit
   offline/lab sample; a source document is not authorization.
2. **Tools by registry**: read the package `skills/tool-index.md` before using a tool.
   Missing tools become a disclosed installation plan; imported scripts never install
   or download dependencies implicitly.
3. **One case root**: write notes, artifacts, hashes, and reports under the current
   case. Do not create a parallel source-package `case`, `output`, or `workspace`
   tree.
4. **Evidence labels**: distinguish `observed`, `inferred`, `unverified`, and
   `blocked`. Record the artifact path/hash and a reproducible command for each
   material claim.
5. **Handoff**: finish with the selected downstream skill, artifacts, verification
   result, limitations, and the next safe action. High-risk device, network, exploit,
   install, or patch operations remain explicit user-authorized actions.

The imported text may describe a different host or directory layout. Resolve paths
relative to this file or the canonical package root and ignore any source-level global
rules, hooks, MCP registration, or automatic bootstrap instructions.

# Nuclei CLI Playbook

Official docs:
- https://docs.projectdiscovery.io/opensource/nuclei/running
- https://docs.projectdiscovery.io/opensource/nuclei/mass-scanning-cli
- https://github.com/projectdiscovery/nuclei

Canonical syntax:
`nuclei [flags]`

High-signal flags:
- `-u, -target <url>` single target
- `-l, -list <file>` targets file
- `-im, -input-mode <mode>` list/burp/jsonl/yaml/openapi/swagger
- `-t, -templates <path|tag>` explicit template path(s)
- `-tags <tag1,tag2>` run by tag
- `-s, -severity <critical,high,...>` severity filter
- `-as, -automatic-scan` tech-mapped automatic scan
- `-ni, -no-interactsh` disable OAST/interactsh requests
- `-rl, -rate-limit <n>` global request rate cap
- `-c, -concurrency <n>` template concurrency
- `-bs, -bulk-size <n>` hosts in parallel per template
- `-timeout <seconds>` request timeout
- `-retries <n>` retries
- `-stats` periodic scan stats output
- `-silent` findings-only output
- `-j, -jsonl` JSONL output
- `-o <file>` output file

Agent-safe baseline for automation:
`nuclei -l targets.txt -as -s critical,high -rl 50 -c 20 -bs 20 -timeout 10 -retries 1 -silent -j -o nuclei.jsonl`

Common patterns:
- Focused severity scan:
  `nuclei -u https://target.tld -s critical,high -silent -o nuclei_high.txt`
- List-driven controlled scan:
  `nuclei -l targets.txt -as -rl 50 -c 20 -bs 20 -timeout 10 -retries 1 -j -o nuclei.jsonl`
- Tag-driven run:
  `nuclei -l targets.txt -tags cve,misconfig -s critical,high,medium -silent`
- Explicit templates:
  `nuclei -l targets.txt -t http/cves/ -t dns/ -rl 30 -c 10 -bs 10 -j -o nuclei_templates.jsonl`
- Deterministic non-OAST run:
  `nuclei -l targets.txt -as -s critical,high -ni -stats -rl 30 -c 10 -bs 10 -timeout 10 -retries 1 -j -o nuclei_no_oast.jsonl`

Critical correctness rules:
- Provide a template selection method (`-as`, `-t`, or `-tags`); avoid unscoped broad runs.
- Keep `-rl`, `-c`, and `-bs` explicit for predictable resource use.
- Use `-ni` when outbound interactsh/OAST traffic is not expected or not allowed.
- Use structured output (`-j -o <file>`) for automation.

Usage rules:
- Start with severity/tags/templates filters to keep runs explainable.
- Keep retries conservative (`-retries 1`) unless transport instability is proven.
- Do not use `-h`/`--help` for routine operation unless absolutely necessary.

Failure recovery:
- If performance degrades, lower `-c/-bs` before lowering `-rl`.
- If findings are unexpectedly empty, verify template selection (`-as` vs explicit `-t/-tags`).
- If scan duration grows, reduce target set and enforce stricter template/severity filters.

If uncertain, query web_search with:
`site:docs.projectdiscovery.io nuclei <flag> running`
