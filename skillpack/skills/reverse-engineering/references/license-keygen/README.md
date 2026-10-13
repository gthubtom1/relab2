# 许可证机制逆向 —— 七篇总入口

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/pe-reverse/techniques/10-license-keygen/`（7 篇，已适配本机工具链）
>
> **什么时候用**：你要分析一个软件的许可证校验机制，**不确定该用哪条技术路线时**。
> 先读 01 分类，再按分类进入 02~07，最后所有路线都在 05 汇合验收。

## 适用信号

- 有激活窗口、注册码输入框、license 文件、注册表授权键，或试用到期提示。
- **不知道该直接写 keygen，还是必须换路径** —— 这是本目录存在的理由。
- 已写出 keygen 但不确定算法是否真的被目标接受（去 05）。

> **能力域**：本目录是 keygen / 授权恢复的**技术能力**。本地样本 / lab 目标按项目 `scope.md` 直接执行；
> 先做机制分类（A/B/C/D），再选武器。

## 步骤

```
1. 读 01 做机制分类（A 本地算法 / B 签名链 / C 自引用 / D 云端）
   —— 先做断网实验，这一步决定后面所有工作是否有意义
2. 读 02 定位校验函数（确认是 1 个还是 2 个 → 2 个则是 C 类）
3. 按分类进入：
     A → 03 还原算法写 keygen
     B → 04 公钥替换 / 逻辑 patch
     C → 07 迭代收敛（先试 20 分钟，失败再回 03）
     D → 06 hook / 状态伪造 / 试用重置（无 keygen 可行）
4. 全部路线都在 05 做 L1~L5 五级验收
5. 记录证据：常量表、地址、判据输出、before/after 差异
```

## 七篇的关系与顺序

```
                    [01] 机制分类
                          │  ← 先做这一步。分类决定后面走哪条路，省掉大量无用功
        ┌─────────────────┼─────────────────┬──────────────────┐
        ▼                 ▼                 ▼                  ▼
    [02] 定位         [02] 定位         [02] 定位           [02] 定位
    校验函数           校验函数           校验函数             校验函数
        │                 │                 │                  │
   A 本地算法        B 签名链         C 自引用            D 云端
        ▼                 ▼                 ▼                  ▼
    [03] 算法        [04] 公钥替换     [07] 迭代收敛        [06] hook 替代
      还原            + patch           抓取回填          状态伪造/试用重置
        │                                (先试收敛，           (无 keygen 可行)
        │                                 不行再回到 [03])
        └────────► [05] 实机验证闭环 ◄─────┘
                    (所有路线的共同出口)
```

## 按顺序读

| # | 文件 | 什么时候读 |
|---|---|---|
| 01 | `license-keygen-01-mechanism-classification.md` | **第一篇，无条件先读**。分类 A/B/C/D，决定后面怎么走 |
| 02 | `license-keygen-02-validation-function-location.md` | 已判为本地校验（A/B/C）后，找校验函数 |
| 03 | `license-keygen-03-key-algorithm-recovery.md` | 已定位校验函数，且确定是 A 类 → 还原算法写 keygen |
| 04 | `license-keygen-04-signature-chain-pubkey-swap.md` | 已判为 B 类（签名链）→ 公钥替换 / 逻辑 patch |
| 05 | `license-keygen-05-keygen-verification-loop.md` | **所有路线的共同出口**。算法还原后的实机验收 |
| 06 | `license-keygen-06-cloud-license-hook.md` | 已判为 D 类（云端校验）→ keygen 不可行，走 hook / 状态伪造 |
| 07 | `license-keygen-07-self-ref-convergence.md` | 已判为 C 类（自引用）→ 迭代收敛捷径 |

## 坑：三条最容易走的弯路

1. **跳过 01 直接写 keygen**。90% 的时间浪费在还原一个根本不存在的本地公式上。
   先分类能省掉几小时到几天。

2. **停在 03 不做 05**。keygen 的 `--verify` 自洽断言通过**只证明算法复现自洽**，
   不证明目标接受。真正的验收是进程内替换 + 重启保持（05 的 L3/L5）。

3. **把 D 类（云端）当 A 类硬啃**。云端校验时客户端**没有可复刻的公式**，
   私钥不在客户端。硬啃的结果是还原出一个「永远返回 false 的本地检查」。
   **先做断网实验**（01 的判定树）确认是本地还是云端。

## 共用的工具前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r2   = (Resolve-ReverseToolSpec -Name 'r2').Command
$cdb  = (Resolve-ReverseToolSpec -Name 'cdbX64').Command
$floss = (Resolve-ReverseToolSpec -Name 'floss').Command
$py   = 'D:\EXE\python\python.exe'
$frida = 'D:\EXE\python\Scripts\frida.exe'    # 05/06/07 的进程内操作
$pm   = 'D:\Tools\Sysinternals\Procmon64.exe'
```

★ **cdb 断点一律用 `ntdll!NtXxx`**，不要用 `kernel32!X`（PDB 里只有 `*Stub` 别名，断不上，
见 `../debugger-breakpoints.md`）。

★ **`frida` 在本机可用**（`D:\EXE\python\Scripts\frida.exe` + Python `frida` 包），
但 05/06/07 里的 Frida 脚本**未在本机实跑验证**，判据标为「命令形态已验证，参数需按样本调整」。

## 证据链的通用要求

无论走哪条路，结论必须落在**程序真实运行上下文**上：

| 层级 | 证据 | 谁提供 |
|---|---|---|
| L1 | keygen 自洽断言 | 03 |
| L2 | 官方 key 回归（必须 VALID） | 03 |
| L3 | **进程内替换后校验函数返回 TRUE** | **05（核心）** |
| L4 | 内存标志位监听 | 05 |
| L5 | 重启后保持 | 05 |

**停在 L1/L2 不算完成。** 详见 `license-keygen-05-keygen-verification-loop.md`。


## ROUTE 状态硬判据（分类先行，不是忠告）

进入本目录任何 01–07 工序之前，分类结论必须已经落进滚动报告 `assault.md` 的 `## routes` 表：

- 断网实验结果（仍能激活 / 失败）→ 该行的**证据**列，原样写现象，不许写结论词
- A / B / C / D 分类结论 → 该行的 **L4 分流**标注
- 分类不确定时 → `confidence: low`，按 ROUTE 出口条件**先做小范围验证再进 EXECUTE**

**分类未落表就进 02–07 = ROUTE 状态出口条件未满足**——这是判据，不是建议。
（出处：`assault-entry.md` ROUTE 段引用的同一分类；本目录 01 的判定树是执行手段。）

## 出口（结论回填）

回填位置：滚动报告 `assault.md`（`-Preset assault` 生成）的对应表。

- 分类结论（01–07 哪一类 / 哪几类混合）→ `## routes` 的 L4 分流证据
- 断网实验现象 → `## findings`（类型 `vuln` 或 `proto`，视结论）
- 校验链关键函数地址 → `## functions`（状态「已分析」+ 证据）
- 分类不明确的疑点 → `## unknowns`

判定：**先分类后动手**。把 D 类（云端）当 A 类（本地算法）硬啃是已知最大时间黑洞。

## 相关

- `../code-patching.md` — 04 的公钥替换 / 逻辑 patch 的字节级细节
- `../debugger-breakpoints.md` — 02 的动态定位手段
- `../dynamic-api-resolution.md` — 校验函数被动态解析时的处理
- `../procmon-patterns.md` — 01 里「是否云端校验」的判定手段
- `../../SKILL.md` — 逆向技能包总体流程