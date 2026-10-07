---
name: "CTF•新手入口"
description: "面向中文用户和新手的统一入口，保持原有两种模式：1) 自动分流，2) 先头脑风暴再分流。分流目标既可以是 ctf-*，也可以在 Web/接口/漏洞验证阶段增强到 strix-*；适合不知道该用哪个 skill、想先理清题意、又不想自己先判断何时该切到工具链或漏洞专项的场景;触发名:ctf-beginner-hub"
argument-hint: "[auto|brainstorm] [challenge-file-or-url-or-description]"
metadata:
  user-invocable: "false"
  integrated: "true"
  integration-source: "ctf-super-hub"
  source-path: "ctf-beginner-hub/SKILL.md"
  maturity: "partial"
  integration-risk: "medium"
  allowed-context: "offline-ctf,authorized-lab"
license: "review-required"
compatibility: "Requires the canonical reverse-skill case/scope contract; source tools are optional."
allowed-tools: Read Write Edit Glob Grep Bash
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

# CTF 新手入口

这是给 **不会选 skill 的新手** 用的统一入口。

它保持和你之前一样的两种模式，只是在需要时把 Strix 当成增强层接进去。

## 两种模式

### 模式 1：自动分流（默认推荐）

适合：
- 已经拿到题面、附件、URL、IP、端口、源码、二进制
- 不想自己判断分类

流程：
1. 先判断更像哪一类题
2. 再决定是走 `ctf-*` 还是增强到 `strix-*`
3. 给你最小化下一步

### 模式 2：先头脑风暴，再分流

适合：
- 看不懂题面
- 不知道第一步做什么
- 想先理清目标、材料、卡点

流程：
1. 先澄清题目到底给了什么
2. 再判断走 `ctf-*` 还是增强到 `strix-*`
3. 再给你最小化下一步

## 什么情况下还是走原来的 `ctf-*`

- Reverse / Pwn / Crypto / Forensics / OSINT / Malware / Misc / AI/ML
- 还停留在 CTF 大类判断阶段
- 还没有进入具体 Web 测试动作阶段

## 什么情况下增强到 `strix-*`

当题目已经明显进入下面这些动作时：
- 要探测 URL / 状态码 / 标题 / 路由
- 要爬路径、跑字典、跑模板扫描
- 要验证 SQLi / XSS / SSRF / RCE / JWT / IDOR / 上传 / 文件包含

### 新手默认增强顺序

#### 先用工具类
- `strix-httpx`
- `strix-katana`
- `strix-ffuf`
- `strix-nuclei`
- `strix-sqlmap`

#### 再用漏洞专项
- `strix-sql-injection`
- `strix-xss`
- `strix-ssrf`
- `strix-rce`
- `strix-authentication-jwt`
- `strix-idor`
- `strix-information-disclosure`
- `strix-insecure-file-uploads`
- `strix-open-redirect`
- `strix-csrf`
- `strix-business-logic`
- `strix-broken-function-level-authorization`
- `strix-path-traversal-lfi-rfi`

## 新手友好输出规范

1. 这题现在更像什么
2. 为什么先走这个 skill
3. 先做哪 1~3 步
4. 每一步是在干什么
5. 如果没结果，下一步切到哪个 skill
6. 术语用一句人话解释

## 推荐默认策略

如果用户没有指定：
- **已有附件 / URL / 服务** -> 先走自动分流
- **只有模糊题面 / 明显很迷茫** -> 先走头脑风暴
- **已经确定是 Web / 接口题并进入验证阶段** -> 允许增强到 `strix-*`

## 结束条件

当主 skill 被确定后：
- 进入对应 `ctf-*` 深挖
- 或增强到对应 `strix-*`
- 题做完后转 `ctf-writeup`
