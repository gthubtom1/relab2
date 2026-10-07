# community-raw —— 第三方社区技能源（vendored，原样保留）

> **本目录是外部内容，不是本项目维护的部分。**

## 规矩

1. **不改原文。** 这些是上游仓库的快照，改正文会让它们与上游脱节，失去合并的价值。
2. **不引用它们里的路径和文件。** 它们是为各自的原始项目写的，里面提到的
   `tool-index.md`、`refresh-tool-index.ps1`、`registry.py` 等，**在本项目都不存在**。
3. **读方法论，不读工具路径。** 这些源里关于「用什么工具、路径在哪」的部分已过时；
   本项目的工具定位一律走 `skillpack/skills/TOOLS.md` + `(Get-Command <id>).Source`。

## 为什么留在这里

里面的**逆向/渗透/交付方法论**仍有参考价值 —— 战术清单、失败阶梯、checklist 设计。
需要时读，需要用就重新验证，不要照抄它的执行脚本。

## 已知会误导的地方

本目录里有 456 处提到 `tool-index.md` / `tool-index.json` / `refresh-tool-index`。
这些文件在本项目**已全部废止并移除**（备份见 `_archive/dead-tooling-2026/`）。

替代口径：

| 旧文档写的 | 现在怎么做 |
|---|---|
| 读 `tool-index.md` 拿工具路径 | `(Get-Command <工具id> -ErrorAction SilentlyContinue).Source` |
| 跑 `refresh-tool-index.ps1` 刷新 | 不需要刷新。工具定位是运行时探测，不落盘、不缓存 |
| 查 `registry.py resolve <id>` | 本项目没有 registry 层；现查现用 |
| 工具根 `C:\HACKER` / `D:\HACKER` | 无固定工具根。绿色软件约定落 `D:\Tools\<名>\`，但**仍要现查** |

## 子目录

| 目录 | 源 | 规模 |
|---|---|---|
| `ai-fullstack/` | 全栈工程 workflow 集 | 643 文件 |
| `apk-reverse-source/` | APK 逆向 skill 源 | 114 文件 |
| `ctf-super-hub/` | CTF 技能整合包 | 164 文件 |
| `hack-skills/` | 安全专题技能集 | 166 文件 |