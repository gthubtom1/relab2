---
name: Strix•httpx 用法
description: Strix httpx 探测命令手册,覆盖探针参数、输出格式与自动化安全用法;触发名:strix-httpx
license: "review-required"
compatibility: "Requires the canonical reverse-skill case/scope contract; source tools are optional."
allowed-tools: Read Write Edit Glob Grep Bash
metadata:
  integrated: "true"
  integration-source: "ctf-super-hub"
  source-path: "strix-httpx/SKILL.md"
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

# httpx CLI Playbook

Official docs:
- https://docs.projectdiscovery.io/opensource/httpx/usage
- https://docs.projectdiscovery.io/opensource/httpx/running
- https://github.com/projectdiscovery/httpx

Canonical syntax:
`httpx [flags]`

High-signal flags:
- `-u, -target <url>` single target
- `-l, -list <file>` target list
- `-nf, -no-fallback` probe both HTTP and HTTPS
- `-nfs, -no-fallback-scheme` do not auto-switch schemes
- `-sc` status code
- `-title` page title
- `-server, -web-server` server header
- `-td, -tech-detect` technology detection
- `-fr, -follow-redirects` follow redirects
- `-mc <codes>` / `-fc <codes>` match or filter status codes
- `-path <path_or_file>` probe specific paths
- `-p, -ports <ports>` probe custom ports
- `-proxy, -http-proxy <url>` proxy target requests
- `-tlsi, -tls-impersonate` experimental TLS impersonation
- `-j, -json` JSONL output
- `-sr, -store-response` store request/response artifacts
- `-srd, -store-response-dir <dir>` custom directory for stored artifacts
- `-silent` compact output
- `-rl <n>` requests/second cap
- `-t <n>` threads
- `-timeout <seconds>` request timeout
- `-retries <n>` retry attempts
- `-o <file>` output file

Agent-safe baseline for automation:
`httpx -l hosts.txt -sc -title -server -td -fr -timeout 10 -retries 1 -rl 50 -t 25 -silent -j -o httpx.jsonl`

Common patterns:
- Quick live+fingerprint check:
  `httpx -l hosts.txt -sc -title -server -td -silent -o httpx.txt`
- Probe known admin paths:
  `httpx -l hosts.txt -path /,/login,/admin -sc -title -silent -j -o httpx_paths.jsonl`
- Probe both schemes explicitly:
  `httpx -l hosts.txt -nf -sc -title -silent`
- Vhost detection pass:
  `httpx -l hosts.txt -vhost -sc -title -silent -j -o httpx_vhost.jsonl`
- Proxy-instrumented probing:
  `httpx -l hosts.txt -sc -title -proxy http://127.0.0.1:48080 -silent -j -o httpx_proxy.jsonl`
- Response-storage pass for downstream content parsing:
  `httpx -l hosts.txt -fr -sr -srd recon/httpx_store -sc -title -server -cl -ct -location -probe -silent`

Critical correctness rules:
- For machine parsing, prefer `-j -o <file>`.
- Keep `-rl` and `-t` explicit for reproducible throughput.
- Use `-nf` when you need dual-scheme probing from host-only input.
- When using `-path` or `-ports`, keep scope tight to avoid accidental scan inflation.
- Use `-sr -srd <dir>` when later steps need raw response artifacts (JS/route extraction, grepping, replay).

Usage rules:
- Use `-silent` for pipeline-friendly output.
- Use `-mc/-fc` when downstream steps depend on specific response classes.
- Prefer `-proxy` flag over global proxy env vars when only httpx traffic should be proxied.
- Do not use `-h`/`--help` for routine runs unless absolutely necessary.

Failure recovery:
- If too many timeouts occur, reduce `-rl/-t` and/or increase `-timeout`.
- If output is noisy, add `-fc` filters or `-fd` duplicate filtering.
- If HTTPS-only probing misses HTTP services, rerun with `-nf` (and avoid `-nfs`).

If uncertain, query web_search with:
`site:docs.projectdiscovery.io httpx <flag> usage`
