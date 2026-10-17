# 工具与测试进程的生命周期规矩

> 起因（主人指出）：之前靶机程序**同时跑起 10 个**；工具用完了还开着。
> 根因不是"忘了关"，是**没有机制**——每个测试各自 `Start-Process`，没有全局登记、没有并发上限、没有统一收尸点。

## 规矩（三条，任何测试都必须遵守）

### 1. 所有子进程走 `proc_guard`

```python
import proc_guard
r = proc_guard.run([exe], timeout=8, group="<组名>", limit=1)
# r = {rc, stdout, stderr, timed_out, elapsed, pid}
```

**禁止**直接 `subprocess.Popen` / `Start-Process` 跑测试样本。

`proc_guard.run` 保证：
- 启动即登记（`.procs.json`，带 pid / group / 启动时间 / argv）
- **并发上限**：同 group 默认 1；超限先杀最老的
- **硬超时**：到点 terminate，2s 宽限后 `taskkill /T /F`（连子进程树）
- **无条件收尸**：`finally` 里一定 kill，正常退出也收

### 2. 长驻 GUI 工具必须有开有关

x64dbg / IDA / Ghidra / dnSpy / jadx-gui / Wireshark 这类，**不许开了就不管**。

```bash
# 关掉本 registry 登记过的工具进程（安全）
python proc_guard.py --sweep-tools

# 按进程名关掉所有（更彻底，可能误杀你自己开着的）
python proc_guard.py --sweep-tools-all
```

### 3. 每轮结束做一次全扫

```bash
python proc_guard.py --sweep  C:\relab2\work\_benchmark\samples   # 清测试样本
python proc_guard.py --sweep-tools                                # 清工具
python proc_guard.py --reap                                       # 清死条目
python proc_guard.py --list                                       # 确认 registry 为空
```

## 自测抓到的三个真 bug（已修）

| # | bug | 现象 | 修法 |
|---|---|---|---|
| 1 | registry 并发写竞态 | 5 线程同时写同一个 `.tmp` → `PermissionError`，登记丢失 → 进程泄漏 | 加 `_FileLock`（`O_CREAT\|O_EXCL` + 重试 + 陈旧锁回收）+ 每进程独立 `.tmp.<pid>` |
| 2 | check-then-spawn 竞态 | 只锁 registry 写、不锁检查→启动，5 线程同时通过检查 → **并发上限完全失效**（5 个全在跑） | 把 `_enforce_limit` 与 `Popen` 放进**同一把锁**；锁做成可重入 |
| 3 | 只在 `poll() is None` 时才 kill | `taskkill /T` 还要收孙子进程；registry 写失败时也漏杀 | `finally` 里**无条件** `_kill(pid)`（带 `/T`） |

## 验收（实测）

```
5 个并发任务，limit=1，timeout=2s
  wall=2.45s（串行，不是 5×2s 也不是 5 个并行）
  task2 elapsed=2.09s（跑满超时），其余 0.14–0.28s（被预抢占）
  errors=0
  --sweep → swept 0   ← 无残留
```

## 为什么不用 `subprocess.run(timeout=...)`

`subprocess.run` 超时只 `kill()` 直接子进程，**孙子进程会留下**。
靶机程序常自己 `CreateProcess`（或调试器拉目标），必须 `taskkill /T`。

## 文件

| 文件 | 作用 |
|---|---|
| `proc_guard.py` | 生命周期守护（run / list / reap / sweep / sweep-tools） |
| `.procs.json` | 进程登记表（自动维护；崩了也能被 `--sweep` 兜住） |
| `gui_check.ps1` | GUI 驱动，收尾改 `taskkill /T /F` |
