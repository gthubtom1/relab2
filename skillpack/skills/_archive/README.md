# _archive —— 旧架构归档（2026-10-05）

**本目录只放归档说明；被归档的旧架构正文已移出 `skills/` 树，见下表。**

- 归档原因：2026-10-05 架构变更。旧架构 = 宿主 agent 通过跨设备通道遥控虚拟机；新架构 = agent 与工具全部运行在同一隔离环境内，无跨设备控制。
- 现行运行环境：见 `skills/SKILL.md` 的 `EXECUTION ENVIRONMENT` 段与 `skills/tool-index.md`（生成物）。
- 保留原则：卡死教训、命令纪律等仍有效的内容已迁到 `skills/SKILL.md` 的 `COMMAND DISCIPLINE` 段，不在此处重复。

| 归档对象 | 现位置 | 内容 |
|---|---|---|
| 旧 VMware 靶机手册 | `docs/history/vmware-sandbox.md` | 母盘/黄金快照、自动克隆脚本、跨设备控制器、免密远程执行、共享文件夹、Session 0 等旧操作手册（顶部已加「已归档、不再适用」横幅） |
| 本次清理前的文件备份 | `work/cleanup-backups-20261005/`（镜像原路径） | 改前快照，见其中 `README-BACKUPS.md` |
| 更早的旧架构整份备份 | `work/backups-20261005-022834/` | 见其中 `README-ARCHIVED.md` |
