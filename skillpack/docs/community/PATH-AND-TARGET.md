# 路径与目标强制（T22，规范 17.16 / 17.17）

守卫：`skills/scripts/verify-path-and-target.py`（只读，标准库，无网络）。
失败关闭：不确定即拒。退出码 0 = ALLOW，20 = DENY，2 = 用法错误。

## 与既有守卫的分工

- `skills/scripts/verify-repository-security.py` 的链接检查只看 git index 里
  mode `120000` 条目的目标字符串；本守卫覆盖**工作树实况**：候选路径的
  realpath containment，以及逐祖先 lstat 的 symlink / junction / reparse
  point / hardlink 判定。两者不重叠，不削弱。
- `scripts/verify-source-attestation.py` 做来源路径规范化（NFC + casefold
  碰撞扫描）与 digest 校验；本守卫复用 NFC+casefold 思想做 case/artifact
  根 containment，并额外做 URL / DNS / redirect / port 目标 allowlist，
  这是 attestation 从不做的事。

## 越界形态与负向 fixture（样本全部掩码断开）

lab 一律在仓库外 `D:/Project/skills-hub/work/T22-lab`；
fixture 见 `tests/security/fixtures/`，驱动见
`tests/security/test-path-and-target.py`。

| fixture | 形态 | 掩码样本 | 拒绝证据 |
|---|---|---|---|
| F1 | `..` 路径穿越 | `..[SEP]..[SEP]Windows[SEP]System32[SEP]calc.exe` | exit 20，traversal rejected |
| F2 | symlink 目标逃逸 | `..[SEP]..[SEP]ev[.]il` | exit 20，symlink-target escapes |
| F3 | junction 逃逸（真实 `mklink /J` 构造） | `link[SEP]secret.txt -> outside` | exit 20，junction/reparse rejected |
| F4 | hardlink 别名（真实 `os.link`，nlink=2） | `hard.bin nlink=2` | exit 20，hardlink rejected |
| F5 | UNC / 设备命名空间 | `[UNC-PREFIX]srv[.]example[SEP]share` | exit 20，UNC/device rejected |
| F6 | 盘符越界 | `C[DRIVE]Windows[SEP]System32` | exit 20，drive-letter escape |
| F7 | 大小写伪装保留名 | `case[SEP]CoN.txt` | exit 20，reserved name rejected |
| F8 | DNS rebinding（离线双轮应答） | `svc[.]example 10.0.0.1 -> 10.0.0.2` | DENY，answer changed |
| F9 | 重定向跳出 allowlist（离线链） | `allowed[.]example/a -> ev[.]il.example/b` | exit 20，redirect hop escapes |
| F10 | 端口/协议超 scope | `allowed[.]example:8443` | exit 20，port not in allowlist |

正向对照：`work\scope.md` 类良性相对路径 exit 0 ALLOW。

## 本平台诚实登记（未验证项）

1. **live symlink 文件**：本机无提权，`os.symlink` 报 WinError 1314。
   替代覆盖：F2 字符串形态门（同一 `parse_symlink_target_shape`
   分支）已验证；F3 junction 覆盖了 reparse 实况分支。仍属**未验证**。
2. **真实 DNS 解析**：不得联网，无离线 DNS 环境。替代覆盖：F8 把两轮应答
   直接喂给 `check_dns_binding`，同一比较分支已验证。仍属**未验证**。
3. **真实重定向抓取**：不得联网。替代覆盖：F9 离线链走同一
   `check_redirect_chain` 分支已验证。仍属**未验证**。
4. **NTFS 8.3 短名**：本卷 `dir /x` 无短名列（短名生成已禁用），短名绕过
   在本机不可构造；守卫对候选路径做 NFC 规范化后比较，短名若存在会被
   realpath 展开后 containment 拦截。属**未验证**。

## 运行

```powershell
$env:PYTHONIOENCODING='utf-8'
& (Resolve-ReverseToolSpec -Name 'pyre').Command kills\scripts\verify-path-and-target.py
& (Resolve-ReverseToolSpec -Name 'pyre').Command ests\security\test-path-and-target.py
```
