---
name: injection-checking
description: >-
  Entry P1 category router for injection testing. Use when routing between XSS,
  SQLi, SSRF, XXE, SSTI, command injection, and NoSQL injection workflows based
  on how attacker-controlled input is consumed.
license: "MIT-with-third-party-provenance-review"
compatibility: "Requires the canonical reverse-skill case/scope contract; source tools are optional."
allowed-tools: Read Write Edit Glob Grep Bash
metadata:
  integrated: "true"
  integration-source: "hack-skills"
  source-path: "skills/injection-checking/SKILL.md"
  maturity: "partial"
  integration-risk: "high"
  allowed-context: "authorized-lab,defensive"
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

# Injection Testing Router

This is the routing entry point when input reaches a dangerous interpreter or execution environment.

After confirming this is an injection-class issue, use it to decide whether it is mainly browser context, database, template engine, server-side requests, XML parsing, or system commands.

## When to Use

- Input reaches HTML, JS, SQL, templates, URL fetchers, XML parsers, or shell
- You have not yet decided whether to start with XSS, SQLi, SSRF, XXE, SSTI, CMDi, or NoSQL
- You need to choose the correct deep-topic skill based on input flow

## Skill Map

- [XSS Cross Site Scripting](../xss-cross-site-scripting/SKILL.md)
- [SQLi SQL Injection](../sqli-sql-injection/SKILL.md)
- [SSRF Server Side Request Forgery](../ssrf-server-side-request-forgery/SKILL.md)
- [XXE XML External Entity](../xxe-xml-external-entity/SKILL.md)
- [SSTI Server Side Template Injection](../ssti-server-side-template-injection/SKILL.md)
- [CMDi Command Injection](../cmdi-command-injection/SKILL.md)
- [NoSQL Injection](../nosql-injection/SKILL.md)
- [Deserialization Insecure](../deserialization-insecure/SKILL.md)
- [JNDI Injection](../jndi-injection/SKILL.md)
- [Expression Language Injection](../expression-language-injection/SKILL.md)
- [CRLF Injection](../crlf-injection/SKILL.md)
- [Extra Injection Types (SSI, LDAP, XPath)](./EXTRA_INJECTION_TYPES.md)
- [Request Smuggling](../request-smuggling/SKILL.md)
- [Prototype Pollution](../prototype-pollution/SKILL.md)
- [Type Juggling](../type-juggling/SKILL.md)
- [HTTP Parameter Pollution](../http-parameter-pollution/SKILL.md)
- [XSLT Injection](../xslt-injection/SKILL.md)
- [CSV Formula Injection](../csv-formula-injection/SKILL.md)

## Recommended Flow

1. First identify the final sink of the input
2. Then choose the topic skill that best matches that interpreter
3. Small payload samples and quick triage are merged into each main skill; no extra payload router is needed

## Related Categories

- [file-access-vuln](../file-access-vuln/SKILL.md)