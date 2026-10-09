# Overlay 渲染与 ImGui 检测

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/06-dynamic/02-overlay-rendering-hook.md`
> **什么时候用**：应用运行时出现未知悬浮窗/覆盖层，需要检测其存在、分析渲染管线、判断图形后端（OpenGL ES / Vulkan）。

## 适用信号

- 应用运行时出现未知悬浮窗或覆盖层
- `dumpsys window windows` 显示额外的 `TYPE_APPLICATION_OVERLAY` 窗口
- 持续高帧率刷新导致性能异常
- 屏幕上有非应用本身的 UI 元素

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$adb = (Resolve-ReverseToolSpec -Name 'adb').Command
& $adb devices
& $adb shell dumpsys window windows | Select-String 'TYPE_APPLICATION_OVERLAY|Window\{'
```

## 步骤

### 1. 确认窗口存在

```powershell
& $adb shell dumpsys window windows | Select-String -Context 2,6 'TYPE_APPLICATION_OVERLAY'
& $adb shell dumpsys SurfaceFlinger --list
```

### 2. Native Overlay 创建路径

```cpp
#include <android/native_window.h>

/* 通过 native surface 创建独立窗口 */
ANativeWindow *window = ANativeWindowCreator::Create(
    "overlay_name",             /* 窗口标题（检测线索） */
    screen_width, screen_height,
    permeate_record             /* 触摸穿透配置 */
);
ANativeWindow_setBuffersGeometry(window, width, height, AHARDWAREBUFFER_FORMAT_R8G8B8A8_UNORM);
```

**窗口标题字符串是最好的抓手** —— 在 so 的 `.rodata` 里搜窗口标题即可定位创建点。

### 3. 图形后端选择

```cpp
enum { OPENGL_ES = 1, VULKAN = 2 };

GraphicsInterface *getGraphicsInterface(int mode) {
    if (mode == VULKAN && hasVulkan()) return new VulkanGraphics();
    return new OpenGLESGraphics();          /* 回退 */
}
/* Vulkan: VkInstance → VkSurfaceKHR → VkSwapchainKHR */
/* OpenGLES: EGLDisplay → EGLSurface → EGLContext */
```

### 4. ImGui 注入循环

```cpp
while (running) {
    graphics->NewFrame();        /* eglMakeCurrent / vkBeginCommandBuffer */
    ImGui::NewFrame();
    Layout_tick_UI(&running);    /* 业务: 绘制菜单/数据显示 */
    ImGui::Render();
    graphics->EndFrame();       /* eglSwapBuffers / vkQueueSubmit */
}
```

### 5. Frida 渲染管线打点

```javascript
// OpenGL ES: hook eglSwapBuffers 确认帧刷新
var eglSwap = Module.findExportByName("libEGL.so", "eglSwapBuffers");
if (eglSwap) Interceptor.attach(eglSwap, {
    onEnter: function () { console.log("[eglSwap] frame"); }
});

// Vulkan: hook vkQueuePresentKHR
var vkPresent = Module.findExportByName("libvulkan.so", "vkQueuePresentKHR");
if (vkPresent) Interceptor.attach(vkPresent, {
    onEnter: function (args) { console.log("[vkPresent] queue=" + args[0]); }
});

// 窗口创建点：hook ANativeWindow_createSurface / ANativeWindow_createFromSurface
["ANativeWindow_createSurface", "ANativeWindow_createFromSurface"].forEach(function (n) {
    var p = Module.findExportByName(null, n);
    if (!p) return;
    Interceptor.attach(p, { onEnter: function () { console.log("[win] " + n); } });
});
```

**帧率异常检测**：`eglSwapBuffers` 每秒调用次数显著高于应用自身逻辑需要的帧率，就是有额外渲染循环。

## 判据

| 观察 | 结论 |
|---|---|
| `dumpsys window` 有 `TYPE_APPLICATION_OVERLAY` 且 owner 不是目标 | 存在外部 overlay |
| `eglSwapBuffers` 帧频远高于应用内容需要 | 有独立渲染循环 |
| `[win] ANativeWindow_createSurface` 在目标 so 里命中 | Overlay 在目标进程内创建 |
| `dumpsys SurfaceFlinger --list` 出现陌生 layer | overlay 的合成层 |

**外部可观测的判据**：`dumpsys SurfaceFlinger --list` 里多出的 layer 名 + `eglSwapBuffers` 的**调用频率计数**，不是「看到有透明层就觉得可疑」。

## 坑

- **`eglSwapBuffers` 在任何 GL 应用都会调用**，必须看**调用频率**和**调用者地址**（`this.returnAddress`）才能区分是应用自己的还是 overlay 的。
- **`libEGL.so` / `libvulkan.so` 是系统库**，在 so 的导入表里可能看不到；用 `Module.findExportByName` 按系统库名找。
- **Vulkan 的 present 点可能不是 `vkQueuePresentKHR`**（老版本用 `vkQueueQueuePresentKHR`），两个都要试。
- **overlay 窗口名可能被混淆**，搜不到名字不代表没有，按 `ANativeWindow_*` 调用点反查更可靠。
- **`dumpsys SurfaceFlinger` 在新版本 Android 输出格式变了**，layer 名解析要按实际输出调整。
- **本机无 Android 设备**：全部 dumpsys/hook 部分**需真机/模拟器，本机未验证**。

## 相关

- `touch-input-hook.md` —— overlay 常与触摸注入联动
- `../native/so-structure-audit.md` —— 在 so 里找 overlay 依赖
