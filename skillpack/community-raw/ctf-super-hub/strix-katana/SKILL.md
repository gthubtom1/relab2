---
name: Strix•Katana 用法
description: Strix Katana 爬虫命令手册,覆盖深度、JS 抓取与稳定并发控制;触发名:strix-katana
license: "review-required"
compatibility: "Requires the canonical reverse-skill case/scope contract; source tools are optional."
allowed-tools: Read Write Edit Glob Grep Bash
metadata:
  integrated: "true"
  integration-source: "ctf-super-hub"
  source-path: "strix-katana/SKILL.md"
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

# Katana CLI Playbook

Official docs:
- https://docs.projectdiscovery.io/opensource/katana/usage
- https://docs.projectdiscovery.io/opensource/katana/running
- https://github.com/projectdiscovery/katana

Canonical syntax:
`katana [flags]`

High-signal flags:
- `-u, -list <url|file>` target URL(s)
- `-d, -depth <n>` crawl depth
- `-jc, -js-crawl` parse JavaScript-discovered endpoints
- `-jsl, -jsluice` deeper JS parsing (memory intensive)
- `-kf, -known-files <all|robotstxt|sitemapxml>` known-file crawling mode
- `-proxy <http|socks5 proxy>` explicit proxy setting
- `-c, -concurrency <n>` concurrent fetchers
- `-p, -parallelism <n>` concurrent input targets
- `-rl, -rate-limit <n>` request rate limit
- `-timeout <seconds>` request timeout
- `-retry <n>` retry count
- `-ef, -extension-filter <list>` extension exclusions
- `-tlsi, -tls-impersonate` experimental JA3/TLS impersonation
- `-hl, -headless` enable hybrid headless crawling
- `-sc, -system-chrome` use local Chrome for headless mode
- `-ho, -headless-options <csv>` extra Chrome options (for example proxy-server)
- `-nos, -no-sandbox` run Chrome headless with no-sandbox
- `-noi, -no-incognito` disable incognito in headless mode
- `-cdd, -chrome-data-dir <dir>` persist browser profile/session
- `-xhr, -xhr-extraction` include XHR endpoints in JSONL output
- `-silent`, `-j, -jsonl`, `-o <file>` output controls

Agent-safe baseline for automation:
`mkdir -p crawl && katana -u https://target.tld -d 3 -jc -kf robotstxt -c 10 -p 10 -rl 50 -timeout 10 -retry 1 -ef png,jpg,jpeg,gif,svg,css,woff,woff2,ttf,eot,map -silent -j -o crawl/katana.jsonl`

Common patterns:
- Fast crawl baseline:
  `katana -u https://target.tld -d 3 -jc -silent`
- Deeper JS-aware crawl:
  `katana -u https://target.tld -d 5 -jc -jsl -kf all -c 10 -p 10 -rl 50 -o katana_urls.txt`
- Multi-target run with JSONL output:
  `katana -list urls.txt -d 3 -jc -silent -j -o katana.jsonl`
- Headless crawl with local Chrome:
  `katana -u https://target.tld -hl -sc -nos -xhr -j -o crawl/katana_headless.jsonl`
- Headless crawl through proxy:
  `katana -u https://target.tld -hl -sc -ho proxy-server=http://127.0.0.1:48080 -j -o crawl/katana_proxy.jsonl`

Critical correctness rules:
- `-kf` must be followed by one of `all`, `robotstxt`, or `sitemapxml`.
- Use documented `-hl` for headless mode.
- `-proxy` expects a single proxy URL string (for example `http://127.0.0.1:8080`).
- `-ho` expects comma-separated Chrome options (example: `-ho --disable-gpu,proxy-server=http://127.0.0.1:8080`).
- For `-kf`, keep depth at least `-d 3` so known files are fully covered.
- If writing to a file, ensure parent directory exists before `-o`.

Usage rules:
- Keep `-d`, `-c`, `-p`, and `-rl` explicit for reproducible runs.
- Use `-ef` early to reduce static-file noise before fuzzing.
- Prefer `-proxy` over environment proxy variables when proxying only Katana traffic.
- Use `-hc` only for one-time diagnostics, not routine crawling loops.
- Do not use `-h`/`--help` for routine runs unless absolutely necessary.

Failure recovery:
- If crawl runs too long, lower `-d` and optionally add `-ct`.
- If memory spikes, disable `-jsl` and lower `-c/-p`.
- If headless fails with Chrome errors, drop `-sc` or install system Chrome.
- If output is noisy, tighten scope and add `-ef` filters.

If uncertain, query web_search with:
`site:docs.projectdiscovery.io katana <flag> usage`
