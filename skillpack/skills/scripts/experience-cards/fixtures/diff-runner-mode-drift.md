# fixture：diff-runner 对照里的「模式漂移」

## 现象（两次独立复现）

同一个 `sha256sum`（Git 自带 GNU 版，`C:\Program Files\Git\usr\bin\sha256sum.exe`），
同一条命令、同一个文件，**输出分隔符随调用环境变化**：

```
$ sha256sum baseline/sample-input.txt                     # git-bash 直连终端
f510729...   baseline/sample-input.txt                    # 两个空格（文本模式）

$ powershell -NoProfile -Command 'sha256sum baseline/sample-input.txt'
f510729... *baseline/sample-input.txt                     # 星号（二进制模式）
```

`sha256sum --help` 写：`-t, --text  read in text mode (default)` —— 默认是文本模式，
但当 stdout 被重定向/管道接管时，GNU coreutils 会切到二进制模式并打 `*` 标记。

## 为什么对「同输入双程序对照」是致命的

diff-runner 的第一版把两个命令都交给 PowerShell（`powershell -NoProfile -Command`）执行，
于是基线侧带 `*`、新实现侧（Python，永远两空格）不带。草稿五列表里两列肉眼看着"差不多"，
判定人如果只看摘要值一致就打「一致」，就把一个**环境造成的伪差异**记成了真差异；
反过来，如果为了消掉 `*` 去改新实现，就是把环境行为固化进了交付物 —— 两边都错。

## 修法（实测有效）

在**驱动命令里显式固定模式**，而不是在新实现里模仿：

```
- baseline_command: `bash -lc "sha256sum -t {input}"`   # -t 固定文本模式
```

`-t` 之后两个程序输出逐字节相同（phase 7 的 rebuild-sha256sum case 五行为面全绿即此）。

## 更一般的判据

对照驱动必须满足：**两边命令在同一 shell 语义下执行，且把一切「随环境变化」的契约项
在命令里固定住**（模式、编码、locale、行尾）。固定不了的（时间戳、随机数、PID）标
`NONDETERMINISTIC` 由人定容差。绝不允许「改新实现去贴合某次基线输出」。
