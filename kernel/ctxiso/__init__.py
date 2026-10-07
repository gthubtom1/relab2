"""ctxiso —— 中枢上下文隔离与本地文档按需读取侧车。

边界（硬约束，不靠自觉靠结构）：
1. 本包**只读**中枢原有的一切：.hub/、hub/、OWNER-SPEECH.md、CHANGES.md …
   打开方式一律 "rb" / "r"，没有任何写句柄指向产品目录。
2. 本包**不重算业务真相**。阶段、停点、门禁的权威仍是 `state status`；
   本包只负责把"要不要看那么多"这件事接管过来。
3. 本包所有状态写在 work/context-isolation/state/ 下，不写进 .hub/。
   （装进宿主后这个目录是包内 `state/`；出货副本由打包器改写，本行是它的适配锚点——
     改这一行会让 pack.py 拒绝打包，那是刻意的：锚点失配宁可停下，也不悄悄出错版本。）
4. Skill 系统完全排除：本包不读、不写、不索引任何 skills 目录。
5. **不在自己目录里写字节码。** 装进宿主后 `hub/ctxiso/__pycache__/*.pyc`
   会把构建机的绝对路径（含开发目录名）固化进出货文件——实测扫出 68 处外部路径命中，
   全部来自 .pyc。这一条从源头堵：导入本包时不生成 .pyc。
"""

import sys

sys.dont_write_bytecode = True

__all__ = ["paths", "config", "store", "archive", "pack", "compact", "observe", "guard"]
__version__ = "0.1.0"
