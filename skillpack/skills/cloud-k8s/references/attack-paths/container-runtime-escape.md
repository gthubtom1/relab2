# 容器运行时逃逸打点

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/ctf-website/techniques/10-cloud/container-runtime-escape.md`（GPL-3.0）。原 frontmatter 的 `mcp_tools` 映射已剔除——本技能包未挂载 `run_ctf_tool` / `http_probe`，改用本地工具链。
> **能力域**：本文为技术能力说明，按项目 `scope.md` 直接套用。
> **什么时候用**：命中「container / Docker / containerd / runc」这类信号时，把本文当打点清单读；命中即进「步骤」，命中不了就换主题。

## 适用信号

- container
- Docker
- containerd
- runc
- privileged
- hostPath
- docker.sock
- capabilities
- seccomp
- AppArmor

## 前置

- 授权：目标在 scope 内（`case-init.ps1` 已 grant），测试时段与限速已约定。
- 工具定位走探测层，别猜路径：

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name '<toolid>'   # 例：sqlmap / httpx / ffuf / curl / python
& $r.Command <参数>                                # 永远用完整路径，不依赖 cwd
```

- Python 解释器用探测层的 `python`。
- 本文脚本默认只读、只打点；扩大范围前先回到 scope 确认。

## 步骤

本文正文按下列小节顺序推进，**每一步的完整命令与脚本在「技术正文」对应小节里**（这类文档以代码体 + 表格为主，按小节读比按 bullet 读快）：

1. 容器环境基线
2. 快速打点脚本
3. 关键入口
4. Docker Socket — 如果 socket 可写，等价于拿到 Docker API。下一跳看能否创建容器、挂载 /、读写宿主机路径。
5. Privileged / hostPath / hostPID
6. runc/containerd CVE 判定 — 版本命中只是线索，真正决定路径的是启动参数、runtime 配置、内核、LSM 和可达文件描述符。

## 判据

判据必须是外部可观测的（状态码、响应字段、差分、落盘文件），不是「命令有输出」。

- **输入信号** — `/proc/1/cgroup` 出现 `docker`、`kubepods`、`containerd`
- **输入信号** — `/var/run/docker.sock` 可读写
- **输入信号** — `CapEff` 包含 `CAP_SYS_ADMIN`、`CAP_SYS_PTRACE`
- **输入信号** — `/host`、`/mnt/host` 或 `/var/lib/kubelet` 被挂载
- **输入信号** — `securityContext.privileged=true` 或 `hostPID=true`

## 坑

- 探针命令在**未本机验证**时不要当成既定事实跑；先用探测层确认 `Available=True`。
- 噪声排除：先固定 baseline（同 URL 同 token 跑 3 次），再只改一个变量做差分。
- 不要把「状态码 200」当命中——WAF/缓存/软 404 都返回 200，命中判据要落到具体业务字段。

## 相关

- 见本技能 `../../SKILL.md` 的 references 索引。

## 技术正文

> 以下为原库正文（保留全部技术细节与脚本），仅移除原 `MCP 工具映射` 章节并重写跨文档链接。

## 场景

拿到容器内 shell 后，先判断它是普通 Docker、Kubernetes Pod、CI runner 容器，还是已经挂了宿主机资源。核心不是背 CVE，而是快速回答三件事：有没有宿主机控制面、有没有危险 capability、有没有 host mount。

## 输入信号

- `/proc/1/cgroup` 出现 `docker`、`kubepods`、`containerd`
- `/var/run/docker.sock` 可读写
- `CapEff` 包含 `CAP_SYS_ADMIN`、`CAP_SYS_PTRACE`
- `/host`、`/mnt/host` 或 `/var/lib/kubelet` 被挂载
- `securityContext.privileged=true` 或 `hostPID=true`

## 容器环境基线

```bash
echo "[cgroup]"
cat /proc/1/cgroup 2>/dev/null

echo "[capabilities]"
grep -E 'Cap(Prm|Eff|Bnd)|Seccomp' /proc/self/status

echo "[mounts]"
grep -E 'docker|containerd|kubelet|/host|/var/run/docker.sock' /proc/self/mountinfo

echo "[profile]"
cat /proc/self/attr/current 2>/dev/null || true
ls -l /var/run/docker.sock 2>/dev/null || true
```

## 快速打点脚本

```python
# container_escape_paths.py - 容器逃逸入口打点
from pathlib import Path

def read(path):
    try:
        return Path(path).read_text(errors="replace")
    except OSError:
        return ""

signals = []
status = read("/proc/self/status")
mounts = read("/proc/self/mountinfo")
cgroup = read("/proc/1/cgroup")

if "docker" in cgroup or "kubepods" in cgroup or "containerd" in cgroup:
    signals.append("running-inside-container")
if "0000003fffffffff" in status or "CapEff:\t0000003fffffffff" in status:
    signals.append("broad-capabilities")
if "Seccomp:\t0" in status:
    signals.append("seccomp-disabled")
if "/var/run/docker.sock" in mounts or Path("/var/run/docker.sock").exists():
    signals.append("docker-socket-mounted")
if "/var/lib/kubelet" in mounts or "/host" in mounts:
    signals.append("host-path-mounted")

print({"signals": signals, "next": "docker.sock/hostPath/capability" if len(signals) >= 3 else "version-and-mount-check"})
```

## 关键入口

### Docker Socket

```bash
curl --unix-socket /var/run/docker.sock http://localhost/version
curl --unix-socket /var/run/docker.sock http://localhost/containers/json
```

如果 socket 可写，等价于拿到 Docker API。下一跳看能否创建容器、挂载 `/`、读写宿主机路径。

### Privileged / hostPath / hostPID

```text
privileged=true → capabilities 广、设备访问多
hostPath=/ → 宿主机文件系统直接暴露
hostPID=true → 可观察宿主机进程，结合 nsenter 风险更高
CAP_SYS_ADMIN → mount/ns/cgroup 相关逃逸面显著扩大
```

### runc/containerd CVE 判定

```bash
runc --version 2>/dev/null || true
containerd --version 2>/dev/null || true
crictl version 2>/dev/null || true
```

版本命中只是线索，真正决定路径的是启动参数、runtime 配置、内核、LSM 和可达文件描述符。

## 攻击链

```text
Container shell → docker.sock mounted → Docker API → host filesystem access → Flag
Container shell → privileged + hostPath → chroot/nsenter 验证 → host proof
K8s Pod → hostPID + CAP_SYS_PTRACE → 观察宿主进程 → 凭证线索
CI container → mounted workspace + cloud env → CI secret → cloud IAM
```

## Evidence

记录: `/proc/1/cgroup`、capability 摘要、seccomp/AppArmor 状态、挂载点摘要、Docker API 响应、runtime 版本、可达宿主机路径。
