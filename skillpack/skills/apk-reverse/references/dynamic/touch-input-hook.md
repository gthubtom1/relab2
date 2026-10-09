# 触摸输入 Hook 与注入分析

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/06-dynamic/03-touch-input-hook.md`
> **什么时候用**：屏幕上出现非人为的点击/滑动，或触摸事件处理速度异常，需要检测和分析触摸事件流。

## 适用信号

- 屏幕上出现非人为的点击/滑动
- 触摸事件处理速度异常快（毫秒级瞄准切换）
- `/dev/input/event*` 或 InputReader 有异常活动

## Android 触摸体系层级

```
屏幕硬件
→ Linux kernel /dev/input/eventX（原始事件）
→ InputReader（framework native）
→ InputDispatcher → ViewRootImpl（Java 分发）
→ Activity.dispatchTouchEvent（应用层）
```

**注入可发生在任意一层，特征不同**：越靠下越难在应用层察觉。

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$adb = (Resolve-ReverseToolSpec -Name 'adb').Command
& $adb shell getevent -lp        # 列出所有输入设备
& $adb shell getevent             # 实时事件流
& $adb shell dumpsys input
```

## 步骤

### 1. 检测 /dev/input 注入

```powershell
& $adb shell getevent -lp
```

异常信号：事件间隔 < 10ms（超人手速）；坐标精准落在 UI 按钮中心。

```c
/* 注入端代码形态：直接向 /dev/input/eventX 写事件 */
int fd = open("/dev/input/event5", O_RDWR);
struct input_event ev[3];
ev[0].type = EV_ABS; ev[0].code = ABS_MT_POSITION_X; ev[0].value = x;
ev[1].type = EV_SYN; ev[1].code = SYN_MT_REPORT;     ev[1].value = 0;
ev[2].type = EV_SYN; ev[2].code = SYN_REPORT;        ev[2].value = 0;
write(fd, ev, sizeof(ev));
/* 检测: lsof | grep "/dev/input/event" */
```

### 2. 检测谁持有 event 设备

```powershell
& $adb shell "ls -l /proc/*/fd 2>/dev/null | grep input/event"
```

`/proc/<pid>/fd` 的符号链接指向 `/dev/input/eventX`，持有者就是注入源。

### 3. Frida Hook Java 层注入接口

```javascript
Java.perform(function () {
    var InputManager = Java.use("android.hardware.input.InputManager");
    InputManager.injectInputEvent.implementation = function (event, mode) {
        var motion = Java.cast(event, Java.use("android.view.MotionEvent"));
        console.log("[injectInput] mode=" + mode +
                    " x=" + motion.getX() + " y=" + motion.getY());
        return true;
    };
});
```

### 4. Hook onTouchEvent 分析触摸模式

```javascript
Java.perform(function () {
    var View = Java.use("android.view.View");
    View.onTouchEvent.implementation = function (event) {
        var a = event.getActionMasked();
        console.log("[touch] action=" + a +
                    " x=" + event.getX() + " y=" + event.getY() +
                    " t=" + event.getEventTime());
        return this.onTouchEvent(event);
    };
});
```

### 5. 离线判断是否机器操作

```python
def is_synthetic(events):
    """events: [(t_ms, x, y, action), ...]"""
    moves = [(t, x, y) for t, x, y, a in events
             if a == 2]                    # ACTION_MOVE
    if len(moves) < 4:
        return False
    intervals = [moves[i+1][0] - moves[i][0] for i in range(len(moves)-1)]
    dists = [((moves[i+1][1]-moves[i][1])**2 +
              (moves[i+1][2]-moves[i][2])**2) ** 0.5
             for i in range(len(moves)-1)]
    # 机器：采样间隔极均匀、步长极平滑；人：抖动多、偶发停顿
    import statistics
    return (statistics.pstdev(intervals) < 5 and
            statistics.pstdev(dists) < 3)
```

**这三个指标都是「统计特征」，不能单独作为判定依据** —— 要结合事件来源（是否来自 `injectInputEvent` 而非真实 input 设备）。

本机用构造的合成事件序列验证过这个判据（**注意：合成数据只能证明判据本身可计算，不能证明它在真人输入上同样可靠**）：

```
human -> False (应为 False)
bot   -> True (应为 True)
```

## 判据

| 观察 | 结论 |
|---|---|
| `/proc/*/fd` 里有进程持有 `/dev/input/eventX` | 存在内核层注入 |
| `[injectInput] mode=... x=... y=...` | Java 层注入，调用栈可追到注入者 |
| 触摸间隔标准差极小且步长平滑 | 疑似机器操作（需结合来源确认） |
| `dumpsys input` 显示注入源与预期不符 | 异常注入 |

**外部可观测的判据**：`/proc/<pid>/fd` 的**持有者 pid** 或 `injectInputEvent` 的**调用堆栈** —— 统计特征只能作为旁证。

## 坑

- **`getevent` 需要 root 或 shell 权限**，普通应用读不了。
- **`/proc/*/fd` 遍历在 Android 10+ 有 SELinux 限制**，可能只能看到自己的进程。
- **`InputManager.injectInputEvent` 是隐藏 API**，`Java.use` 在部分版本会被隐藏 API 限制拦下。
- **`MotionEvent.getX()` 是相对当前 View 的坐标**，跨 View 要用 `getRawX()`。
- **`onTouchEvent` hook 会覆盖所有 View**，日志量极大，必须按包名过滤或采样。
- **统计特征容易被高刷设备的正常插值干扰**，机器/人类判定要看多维度。
- **本机无 Android 设备**：全部 dumpsys/hook 部分**需真机/模拟器，本机未验证**。

## 相关

- `overlay-rendering-hook.md` —— overlay 常与触摸注入联动
- `../native/so-structure-audit.md` —— 确认 so 里是否有 input 相关代码
