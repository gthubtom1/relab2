---
name: Strix•sqlmap 用法
description: Strix sqlmap 命令手册,覆盖目标语法、无交互执行与常见枚举流程;触发名:strix-sqlmap
license: "review-required"
compatibility: "Requires the canonical reverse-skill case/scope contract; source tools are optional."
allowed-tools: Read Write Edit Glob Grep Bash
metadata:
  integrated: "true"
  integration-source: "ctf-super-hub"
  source-path: "strix-sqlmap/SKILL.md"
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

# sqlmap CLI Playbook

Official docs:
- https://github.com/sqlmapproject/sqlmap/wiki/usage
- https://sqlmap.org

Canonical syntax:
`sqlmap -u "<target_url_with_params>" [options]`

High-signal flags:
- `-u, --url <url>` target URL
- `-r <request_file>` raw HTTP request input
- `-p <param>` test specific parameter(s)
- `--batch` non-interactive mode
- `--level <1-5>` test depth
- `--risk <1-3>` payload risk profile
- `--threads <n>` concurrency
- `--technique <letters>` technique selection
- `--forms` parse and test forms from target page
- `--cookie <cookie>` and `--headers <headers>` authenticated context
- `--timeout <seconds>` and `--retries <n>` transport stability
- `--tamper <scripts>` WAF/input-filter evasion
- `--random-agent` randomize user-agent
- `--ignore-proxy` bypass configured proxy
- `--dbs`, `-D <db> --tables`, `-D <db> -T <table> --columns`, `-D <db> -T <table> -C <cols> --dump`
- `--flush-session` clear cached scan state

Agent-safe baseline for automation:
`sqlmap -u "https://target.tld/item?id=1" -p id --batch --level 2 --risk 1 --threads 5 --timeout 10 --retries 1 --random-agent`

Common patterns:
- Baseline injection check:
  `sqlmap -u "https://target.tld/item?id=1" -p id --batch --level 2 --risk 1 --threads 5`
- POST parameter testing:
  `sqlmap -u "https://target.tld/login" --data "user=admin&pass=test" -p pass --batch --level 2 --risk 1`
- Form-driven testing:
  `sqlmap -u "https://target.tld/login" --forms --batch --level 2 --risk 1 --random-agent`
- Enumerate DBs:
  `sqlmap -u "https://target.tld/item?id=1" -p id --batch --dbs`
- Enumerate tables in DB:
  `sqlmap -u "https://target.tld/item?id=1" -p id --batch -D appdb --tables`
- Dump selected columns:
  `sqlmap -u "https://target.tld/item?id=1" -p id --batch -D appdb -T users -C id,email,role --dump`

Critical correctness rules:
- Always include `--batch` in automation to avoid interactive prompts.
- Keep target parameter explicit with `-p` when possible.
- Use `--flush-session` when retesting after request/profile changes.
- Start conservative (`--level 1-2`, `--risk 1`) and escalate only when needed.

Usage rules:
- Keep authenticated context (`--cookie`/`--headers`) aligned with manual validation state.
- Prefer narrow extraction (`-D/-T/-C`) over broad dump-first behavior.
- Do not use `-h`/`--help` during normal execution unless absolutely necessary.

Failure recovery:
- If results conflict with manual testing, rerun with `--flush-session`.
- If blocked by filtering/WAF, reduce `--threads` and test targeted `--tamper` chains.
- If initial detection misses likely injection, increment `--level`/`--risk` gradually.

If uncertain, query web_search with:
`site:github.com/sqlmapproject/sqlmap/wiki/usage sqlmap <flag>`
