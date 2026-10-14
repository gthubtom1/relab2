# part1 评估（开工自检 + 起飞复核 + 派子代理 + 实弹 SURVEY 起步）
体系问题：
1. [HIGH] IDA 未完成分析的 int 3 占位被当「入口被掏空/双体结构」的事实基础（技能卡警告过 JUMPOUT/int3 空壳，体系没拦住）。
2. [MED] cdb 断点命令串被解析坏 → 只有首个 bp 生效，却把乱码输出当「GetVolumeInformationA 命中」线索。
3. [MED] 启动即崩归因 7 分钟内翻转 5 次（反调试→环境→自检→缺卡密→SMC→CRT abort）。
4. [MED] 探测层「工具可用性」依赖继承 PATH，cdbX64 False↔True 漂移，未写进文件。
5. [MED] 审计可被「先改口径」规避（PROJECT-UNDERSTANDING 的「打不穿也算完成」被修是为躲子代理 grep，非因口径错）。
6. [MED] 实弹目标放仓库根（26MB），体系对「目标如何入库/忽略」无规定 → git status 长期不净。
7. [MED] 物理陷阱未覆盖「工具+非 ANSI 路径」：中文 case 目录让 r2/rabin2 解析失败，被迫建 ASCII junction。
8. [MED] 工具表缺条/误导：本机 rabin2.exe 实为 r2 副本，toolmap 无 r2 条目。
流程：partial（case 目录齐全、由 case-init -Preset assault 生成；但本片未见 master-route 点火、未在 case 内跑 review_case 审计）。
near_refusal：无。
诚实：好。
