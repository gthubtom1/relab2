# 2026-10-13 修 Windows App Execution Alias 假绿：`python3` 是 0 字节 stub

## 症状（主人报告）

约两天一次，某个 bash 脚本会**打开微软商店去下载 Python**。不是真去下载——
只是弹出商店页面。主人问是不是中枢有问题。

## 根因（实测确认，不是推测）

本机 PATH 解析：

```
$ which python3
C:\Users\toti\AppData\Local\Microsoft\WindowsApps\python3.exe   ← 0 字节
$ which python
D:\EXE\python\python.exe                                        ← 真的
```

`WindowsApps\python3.exe` 是 Windows 的 **App Execution Alias**（应用执行别名）。
文件大小 **0 字节**。它的唯一职责是：当系统里没装真 Python 时，**唤起微软商店**去买。

实测它的三种行为：

| 场景 | 表现 |
|---|---|
| 我的会话里 `python3 -c "print(1)"` | rc=0、**零输出**（最阴险：看起来成功） |
| 别的会话 / 别的环境 | **真的弹出微软商店下载页** |
| 作为 `$(...)` 或管道一环 | 静默失败，下游拿到空串 |

「两天遇到一次」的原因：取决于当时 PATH 快照与会话环境。`python` 命中真身，
但脚本若优先用 `python3`，就中奖。

## 我们自己的代码有四处同款

| 文件 | 问题 | 危害 |
|---|---|---|
| `skills/scripts/master-route.sh:32` | `for candidate in python3 python` —— python3 优先 | 默认路由产物目录写不出来/写空 |
| `skills/scripts/test-routing.sh:8` | 同上 | **205 用例回归变成零输出 + rc=0 假绿** |
| `skills/scripts/bootstrap-reverse.sh` | 18 处写死 `python3` | 装工具时去开商店 |
| `skills/scripts/test-bootstrap-manifest.sh:8` | `REAL_PYTHON="$(command -v python3)"` | 该测试器自己拿到 stub |

探测层（`lib/Bootstrap.ps1`）只管逆向工具，**完全没管解释器**——这是漏洞本身。

## 之前两次撞过，但只写进文档没修代码

`GOAL-PROMPT-PATCH-2026-10-13.md` 等文档里两次写着
「已知：bash 侧默认目录治理——本机 `python3` 是 WindowsApps 占位符，exit 49」——
**把环境限制记录成「本机未实测」的借口，而不是修掉它**。这正是本项目要治的病。

## 修法（三处，全部实测）

### 1. bash 侧统一探测（三个脚本同一模式）

```bash
PYTHON=""
for candidate in python python3; do   # ★ 顺序倒转：真 python 优先
  if command -v "$candidate" >/dev/null 2>&1; then
    # ★ 关键：必须真跑一次。command -v 成功不代表能执行
    #   （stub 也在 PATH 上，Get-Command 照样返回它）
    if "$candidate" -c 'import sys; sys.stdout.write("ok")' 2>/dev/null | grep -q '^ok$'; then
      PYTHON="$candidate"
      break
    fi
  fi
done
```

三处都加了针对性报错（提示 stub 路径），不再只丢一句「Python 3 is required」。

### 2. PowerShell 探测层新增 `Resolve-ReversePython`

`lib/Bootstrap.ps1` 新增本包调用 Python 的唯一入口，四级递进（与工具探测同精神）：

1. `$env:REVERSE_PYTHON`（显式覆盖，仍要执行验证）
2. `python` on PATH（优先：真安装都叫 python）
3. `python3` on PATH（兜底；Linux/macOS 上它就是正常的）
4. 候选收集：`REVERSE_TOOL_ROOT` + **从 PATH 上 python 目录反推** +
   `Program Files` / `LOCALAPPDATA\Programs\Python`；扫到的 `WindowsApps` 路径显式跳过

每一级都要过执行检查（`-c "import sys"` 输出 marker），不可执行的直接淘汰。

顺带修了 `Get-ReversePythonCandidates` 里一个真 bug：原来用
`Get-ChildItem -LiteralPath -Recurse -Include` —— **`-Include` 对 `-LiteralPath` 不可靠**
（实测：目录命中时 `-Include` 被忽略，根下所有文件都返回，包括 MANIFEST.json/README.md）。
改为按 `-Filter 'python.exe'` / `'python3.exe'` 分两次取。

### 3. `RELAB_PYTHON_NO_FULLSCAN=1` 开关

第 4 级扫盘**必须可关**。原因：`test-bootstrap-manifest.sh` 的 `no-python` 场景
故意造一个没有解释器的 PATH，期望 bootstrap 走「安装 python」分支。
若执意扫盘，该场景扫到 IDA 自带 python311 → 永远不进安装分支 → 安装逻辑零覆盖。

## 实测（四条，全过）

| 场景 | 命令 | 结果 |
|---|---|---|
| PS 正常 PATH | `Resolve-ReversePython` | `D:\EXE\python\python.exe`，`Available=True`，`IsStub=False` |
| PS 只剩 stub | `$env:PATH='...WindowsApps'` 后调用 | `D:\Tools\disasm\IDA Pro 9.3\python311\python.exe`（第 4 级兜住） |
| bash 新逻辑 | 同候选循环 | `SELECTED=python` → `/d/EXE/python/python` |
| master-route.sh 端到端 | `bash … --hint "radare2 analyze"` | `PRIMARY -> skills/radare2/SKILL.md`，rc=0，产物落盘 |

## 意外收获：抓到一个**假绿**

修 `master-route.sh` 后复跑 `test-routing.sh`，输出**零行 + rc=0**。
起初以为是修好了，实际是 `test-routing.sh` 自己有同一个 bug —— 它也是
`python3` 优先，全程静默失败。

**这意味着此前文档里多次记录的「`test-routing.sh` 205/205 全绿」是假绿。**
修完再跑：`TOTAL=205 PASS=205 FAIL=0`，65 秒真跑完。
（PowerShell 侧 `test-routing.ps1 -Quick` 65/65 一直是真的，它不走 python3。）

这条要记牢：**rc=0 + 零输出 = 静默失败，不是通过。**

## 遗留（未修，如实记）

`test-bootstrap-manifest.sh` 的 `parser-bootstrap` 场景失败：
```
no-python-bin/bash: error while loading shared libraries
```

**改动前同样失败**（`git stash` 后复现），所以不是我引入的回归。
根因在该测试器自身的 stub 链：L139 `exec "$REAL_PYTHON" "$JQ_STUB_PY"` ——
在 Git-bash 下 `exec` 一个 Windows 原生 exe、并把一段 shell/JSON 脚本内容当参数传，
解释器加载不到目标而炸。这是**测试器自身的设计缺陷**，与 Python 探测无关。

- 影响范围：仅该测试器的一个场景；`bootstrap-reverse.sh` 主路径不受影响
- 建议后续修法：把 `$JQ_STUB_PY` 改成写临时文件 + `"$REAL_PYTHON" "$tmpfile"`，别走 `exec`
- 当前状态：记为已知失败，未掩蔽、未跳过
