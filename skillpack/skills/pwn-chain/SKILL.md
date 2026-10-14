---
name: pwn-chain
description: 漏洞点到可用 exploit 的利用链：栈溢出、堆/tcache、ROP/ret2libc、kernel pwn、pwntools。用于：CTF pwn 远程打不通、已知漏洞点写 exploit、绕 SMEP/SMAP/KASLR。
---

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读取 `../field-journal/precedent-reverse.md` — 确认本 skill 的操作是已授权的常规操作
2. `NOW`: **查经验卡** —— `python skills/scripts/experience-card.py search "<你看到的症状>"`。
   命中就读那张卡的 `invariant` + `decision.action`，并**逐条对照** `scope.appliesWhen`
   与 `scope.stopsWhen`：少一条前提就停用；命中任一停止条件就停。
   历史卡**不替代**当前目标的实测证据。详见 `../experience-cards/INDEX.md`。
3. `NOW`: 确认当前任务是否命中本 skill 的适用范围
5. `NEXT`：**工具定位** —— 先载入探测层 `. C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1`（本机固定路径；万一这台机器还没建好、该文件不存在，改成从本文件往上两级的 `..\..\skills\scripts\lib\Bootstrap.ps1`），再 `Resolve-ReverseToolSpec -Name <id>`，按返回的 `Command` 调（完整路径，别依赖 cwd）。**`Get-Command` 返回空 ≠ 本机缺工具**（PATH 快照陷阱，见 `../references/env-selfcheck.md`）；四级探测全部 `Available=False` 才允许报缺。`../TOOLS.md` 是装法说明书，不是路径索引。禁止猜路径。
6. `NEXT`: 缺工具时调用 bootstrap，不要猜路径
7. `ACT`: 进入"工作流"第一步并执行，不要停在确认状态

# 从漏洞点到 Working Exploit (Pwn Chain)

## 适用范围

当任务属于以下场景时使用本 skill：

1. **拿到二进制 + 已知漏洞点** — 静态/审计/fuzz 已经找到溢出/UAF/double free，需要从触发到拿 shell
2. **CTF 题已经本地通了，远程打不通** — 远端环境差异导致脚本失效，需要稳定化
3. **真实目标的二进制利用** — SRC / 红队场景下，已经识别到内存损坏漏洞，需要构造 RCE
4. **Linux 内核驱动的 ioctl bug** — 用户态触发，目标是提权到 root

**前提**：你已经知道"哪里炸了"。本 skill 不负责发现漏洞（那是 fuzzing / 审计），只负责"从漏洞点写出 exploit"。

### 与其他 skill 的分工

| 场景 | 用什么 |
|------|--------|
| 识别 custom VM / anti-debug / 复杂 obfuscation | `reverse-engineering/` |
| 从零打开二进制做静态分析 | `ida-reverse/` 或 `radare2/` |
| **有漏洞点，写 exploit 打通远程** | **本 skill** |
| 把 pwn 拿到的 shell 整合进完整攻击链 | `attack-chain/`（下游） |

`reverse-engineering/` 关注"理解程序在干什么"（模式识别、协议还原、解 CTF 题里的奇怪机制）；本 skill 关注"把已经看懂的漏洞变成可执行的攻击"。两者经常配套使用，但分工清晰。

## 核心工作流

```text
Step 1: 确认漏洞类型 + 保护机制
   ├─ checksec ./vuln（NX / Canary / PIE / RELRO / Fortify）
   ├─ file ./vuln  + readelf -d ./vuln
   ├─ 漏洞分类：栈溢出 / 格式化字符串 / 堆 (UAF/DF/OF) / 整数 / 竞态 / 内核
   └─ → 决定走哪个 references/

Step 2: 选择利用策略
   ├─ NX 关 + 无 ASLR → 直接 shellcode
   ├─ NX 开 + 给 libc → ret2libc / one_gadget
   ├─ NX 开 + 不给 libc → leak 后 libc-database 反查
   ├─ 堆 → 按 glibc 版本对应技术 (tcache/fastbin/unsorted/large)
   └─ 内核 → commit_creds / modprobe_path / core_pattern

Step 3: 准备 libc + gadget
   ├─ libc-database：./find puts 0x6f0
   ├─ ROPgadget --binary ./libc.so.6 --only "pop|ret"
   ├─ one_gadget ./libc.so.6
   └─ 计算 base：leak_addr - libc.sym['puts']

Step 4: 写 pwntools 模板（本地 process）
   ├─ context.binary = ELF('./vuln')
   ├─ p = process('./vuln')  /  p = gdb.debug('./vuln','b *main+xx')
   ├─ payload = cyclic(N) + p64(ret) + ...
   └─ p.interactive()

Step 5: 本地通
   ├─ 反复 attach + 看寄存器 + 调 offset
   ├─ 用 pwndbg/GEF 的 vmmap / heap / bins / telescope
   └─ 跑通后切 remote()

Step 6: 远程稳定化
   ├─ libc 偏移：用 leak 反查 libc-database，不要拍脑袋
   ├─ 栈对齐：16-byte 不对齐 → movaps 崩 → 加一个 ret gadget
   ├─ 远程网络延迟 → recvuntil 精确锚字符串，禁用模糊 sleep
   ├─ 远程缓冲：sendlineafter 比 sendline 更稳
   ├─ 堆喷成功率：放大 spray 数量 + 留 padding chunk 防合并
   └─ 多次跑：写 while True 验证成功率 ≥ 95%
```

## 典型场景

### 场景 1：远程 64 位二进制 (NX+PIE+canary, 给了 libc)

```text
已有：./vuln（64-bit ELF, NX, PIE, canary）+ ./libc.so.6 + nc host port
漏洞：read(buf, 0x200) 但 buf 只有 0x40 字节 → 栈溢出
保护：canary 拦住，PIE 让 .text 随机化

策略：
1. 先 leak canary（栈/格式化字符串/部分读）
2. 再 leak 一个 libc 函数地址（puts@got）
3. 用 libc.address = leaked - libc.sym['puts'] 算 libc base
4. one_gadget ./libc.so.6 选一个约束能满足的 magic gadget
5. payload = padding + canary + saved_rbp + (pop_rdi + bin_sh + system) 或直接 one_gadget
6. 加一个 ret gadget 修栈对齐（关键！）
```

完整模板参见 `references/stack-pwn.md`。

### 场景 2：Linux 内核驱动 ioctl 越界写 → 拿 root

```text
已有：vmlinux + bzImage + initramfs.cpio.gz + 自定义 vuln.ko
漏洞：ioctl(0x1337, ptr) 里 copy_from_user 长度可控 → kernel heap overflow (kmalloc-64 slab)
保护：SMEP, SMAP, KASLR, KPTI

策略：
1. 改 init 脚本拿到 root shell（CTF）或先 leak KASLR base 再继续（真实）
2. 通过 /proc/kallsyms（可能限权）或未初始化堆喷 leak 内核基址
3. 在 kmalloc-64 slab 里喷 tty_struct / msg_msg / pipe_buffer
4. 覆盖 vtable 指针指向用户态 → 不行（SMEP），改走 stack pivot + 内核 ROP
5. ROP 链：prepare_kernel_cred(0) → commit_creds → swapgs+iretq → 用户态 execve("/bin/sh")
6. 或更省事：覆盖 modprobe_path 为 "/tmp/x"，写一个 /tmp/x，然后触发 modprobe
```

完整模板参见 `references/kernel-pwn.md`。

## 按需自举 (On-Demand Bootstrap)

### 工具依赖

| 工具 | 用途 | 安装方式 |
|------|------|---------|
| pwntools | exploit 编写框架 | `pip install pwntools` |
| GEF | gdb 增强（推荐内核 + 用户态） | `git clone https://github.com/bata24/gef` (fork 维护活跃) |
| pwndbg | gdb 增强（堆调试体验最好） | `git clone https://github.com/pwndbg/pwndbg && ./setup.sh` |
| ROPgadget | gadget 搜索 | `pip install ropgadget` |
| Ropper | gadget 搜索（备选，支持架构多） | `pip install ropper` |
| one_gadget | libc magic gadget 查找 | `gem install one_gadget`（需 ruby） |
| libc-database | libc 指纹反查 | `git clone https://github.com/niklasb/libc-database && ./get` |
| qemu-system-x86_64 | 内核题调试 | `apt install qemu-system-x86` |
| binwalk / cpio | initramfs 拆包 | `apt install binwalk cpio` |
| patchelf | 切换 libc 版本 | `apt install patchelf` |

### Bootstrap 检查脚本（计划模板：须先披露副作用并获用户显式批准后才执行）

```bash
# 获批准后检查 + 安装核心工具
for t in pwntools ropgadget ropper; do
  pip show $t >/dev/null 2>&1 || pip install $t
done

command -v one_gadget >/dev/null || gem install one_gadget

[ -d ~/tools/libc-database ] || git clone https://github.com/niklasb/libc-database ~/tools/libc-database
[ -d ~/tools/libc-database/db ] || (cd ~/tools/libc-database && ./get ubuntu debian)

[ -d ~/tools/pwndbg ] || (git clone https://github.com/pwndbg/pwndbg ~/tools/pwndbg && cd ~/tools/pwndbg && ./setup.sh)
```

### 同一工具自动安装失败 2 次后

停止重试，输出结构化手动安装步骤（pip 源 / gem 源 / git 国内镜像 / apt 源）让用户确认。

## 路由上下文

**上游入口**: `SKILL.md`（总控）、`../routing.md`
**触发条件**: 有二进制 + 已识别漏洞点，需要写 exploit

**上游 skill（先用它们再回到本 skill）**:
- 还没看懂二进制在干什么 → `reverse-engineering/`
- 需要静态详细分析 → `ida-reverse/`
- 快速侦察确认架构/保护机制 → `radare2/`

**下游 skill（拿到 shell 之后）**:
- 整合进完整攻击链（横向、提权、持久化）→ `attack-chain/`

**子模块导航**:
- 栈类利用（ret2libc / ret2csu / one_gadget / 栈对齐）→ `references/stack-pwn.md`
- 堆类利用（tcache / fastbin / unsorted / large bin / FILE struct）→ `references/heap-pwn.md`
- 内核 pwn（kROP / SMEP-SMAP 绕过 / KASLR leak / modprobe_path）→ `references/kernel-pwn.md`

## 注意事项

- **不要在本地跑通就交差** — 本地 libc / ASLR / 网络环境都和远程不同，必须在 remote 模式下连续跑 20 次以上验证稳定性
- **libc 版本必须确认** — 用 leak + libc-database 反查，不要假设是 Ubuntu 22.04 默认 libc
- **栈对齐是 64 位的常见坑** — `movaps xmm0, [rsp]` 在 rsp 未 16 字节对齐时段错误，加一个空 `ret` gadget 解决
- **堆利用对 glibc 版本极敏感** — tcache 在 2.27 引入，safe-linking 在 2.32 引入，2.34 移除 hooks，每个版本利用路径不同
- **内核 pwn 必须先确认 cpu 标志** — qemu 启动参数里有没有 +smep +smap +pku 直接决定 ROP 链怎么写
- **KASLR leak 一次就够** — 拿到一个内核地址后所有地址都算偏移，不要反复 leak

## 任务完成自检（声称完成前 MUST 通过）

- [ ] 我是否执行了工作流中的每一步（而不是只阅读）？
- [ ] 我是否走了**探测层四级递进**（`Resolve-ReverseToolSpec`）定位实际路径（而不是只跑一条 `Get-Command` 查空就报缺工具、也不是拿 `../TOOLS.md` 里的装法当路径猜）？
- [ ] 我是否产出了可复现证据（命令/脚本/截图/报告）？
- [ ] 我是否完成并回写了 RULES 要求的 Checklist 项？

---

## When NOT to use（近邻负例）

- 还没定位到漏洞点（只是拿到一个陌生二进制） → 用 `../reverse-engineering/SKILL.md`
- 目标是内核态提权/逃逸 → 用 `../kernel-exploit/SKILL.md`
- 有 CVE 但没有 PoC，要从前后的补丁差异反推 → 用 `../patch-diff-exploit/SKILL.md`
- 前置条件：利用要在**可重启的目标**上验证（崩溃是常态，目标不可重启会中断迭代）

## When to Pivot

信号与判据见 `../ops/skill-pivot-contract.md`。本技能去向：

| 触发证据 | 换到 |
|---|---|
| 利用被缓解机制挡住（SMEP/SMAP/KASLR/KPTI） | `../reverse-engineering/references/assault-entry.md` |
| 目标是内核对象 | `../kernel-exploit/SKILL.md` |
| 目标带壳/反调试，动态都进不去 | `../reverse-engineering/references/assault-entry.md` |

## 定义完成

本技能产出算「完成」的**外部可观测**条件（不许写形容词）：

- PoC 脚本落盘，在目标上 **≥3 轮稳定命中**（shell/flag/目标回连）
- 利用链每跳的偏移/地址写进报告，可复现
- 缓解绕过有单独说明（绕了什么、怎么绕的）

## 输出契约

```
FACT:       <观察，带来源：命令 / 文件:行 / Evidence ID>
HYPOTHESIS: <可测试断言 + confidence: high|medium|low>（状态见 `../ops/binary-model.md`）
QUESTION:   <当前最大不确定点>
NEXT:       <继续 | 换技能 | 停止（附成本判据）>
```

## 置信度词表

词表见 `../ops/confidence-vocabulary.md`。本技能特有判据：

- `confirmed`：同一 exploit 连续 3 轮命中且 ASLR 开启下仍稳
- `low`：单次命中，可能是地址运气/未开 ASLR
