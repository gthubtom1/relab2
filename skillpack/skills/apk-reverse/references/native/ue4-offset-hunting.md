# UE4 引擎游戏偏移发现

> **来源**：改编自 `LING71671/open-reverselab` 的 `kb/apk-reverse/techniques/02-native/03-ue4-offset-hunting.md`
> **什么时候用**：目标手游是 Unreal Engine，核心逻辑在 `libUE4.so`，要找 Character/Actor 的关键属性偏移。

## 适用信号

- `lib/arm64-v8a/libUE4.so` 存在（通常 100MB+）
- 符号被 strip 但类名仍在 `FName` 池中
- 游戏画面为 3D 射击/动作类
- 包体大 + 使用 OBB

## UE4 类继承链速查（FPS/TPS 通用）

```
UObject
├── AActor
│   ├── APawn
│   │   └── ACharacter
│   │       ├── ASTExtraCharacter（FPS 类游戏通用）
│   │       └── ASTExtraBaseCharacter
│   └── AWeapon
│       ├── ASTExtraWeapon
│       └── ASTExtraShootWeapon
├── UActorComponent
│   ├── UPrimitiveComponent
│   │   ├── USkeletalMeshComponent  (骨骼)
│   │   └── UStaticMeshComponent
│   └── UWeaponManagerComponent
└── UPlayerState
    └── AUAEPlayerState
```

## 前置

```powershell
. 'C:\relab2\skillpack\skills\scripts\lib\Bootstrap.ps1'
$r = Resolve-ReverseToolSpec -Name 'python'
& $r.Command 'C:\relab2\skillpack\skills\apk-reverse\scripts\so-structure-audit.py' libUE4.so --jni
```

先跑 `so-structure-audit.md` 确认 ABI 和是否加固。UE4 的 so 极大，体检输出很长，可用 `--max-sections 20` 截断。

## 步骤

### 方法 1：静态分析 UE4 SDK dump

在目标进程内跑 UE4Dumper → dump `GNames`/`GObjects` → 生成 SDK，得到所有类的完整偏移定义：

```cpp
class ASTExtraCharacter : public ACharacter {
public:
    float Health;       // 0x0E78
    float HealthMax;    // 0x0E7C
    int8_t TeamID;      // 0x0E20
    bool bIsAI;         // 0x0E21
    FString PlayerName; // 0x0D50
};
```

**需真机/模拟器，本机未验证**（UE4Dumper 是外部工具，不在本技能包内）。

### 方法 2：FName 池字符串搜索

```powershell
$py = (Resolve-ReverseToolSpec -Name 'python').Command
& $py 'C:\relab2\skillpack\skills\apk-reverse\scripts\so-structure-audit.py' `
    libUE4.so --strings 6 --grep Health
```

每个 `FName` 在池中有索引，通过 `GNames` 表解析。

### 方法 3：运行时特征法

```c
// 已知: 血量初始值通常是 100 或 100.0
// 搜索策略: 在 libUE4.so 某偏移范围扫描 float=100.0
// 验证: 受到伤害后该值下降 → 确认是 Health
```

### 方法 4：指针链定位（最实战）

```cpp
// UE4 Actor 链: RootComponent → RelativeLocation → X/Y/Z
uintptr_t Actor          = readPtr(actorList + i * 8);
uintptr_t RootComponent  = readPtr(Actor + 0x190);      // AActor::RootComponent
uintptr_t RelLoc         = RootComponent + 0x1A0;      // USceneComponent::RelativeLocation
float x = readFloat(RelLoc), y = readFloat(RelLoc + 4), z = readFloat(RelLoc + 8);

// 武器链
uintptr_t WeaponManager  = readPtr(Actor + 0x0B68);     // WeaponManagerComponent
uintptr_t CurWeapon      = readPtr(WeaponManager + 0x218);
float bulletSpeed        = readFloat(readPtr(CurWeapon + 0x190) + 0x7C0);
```

**这里的偏移是示例数值，必须在你自己的样本上验证**（UE4 版本和游戏改动都会让它失效）。

### 方法 5：Frida 动态遍历 Actor 列表

```javascript
var libbase = Module.findBaseAddress("libUE4.so");
var GWorld = libbase.add(GWORLD_OFF);

function readPtr(a)  { return Memory.readPointer(a); }
function readFloat(a){ return Memory.readFloat(a); }

var PersistentLevel = readPtr(readPtr(GWorld) + 0x30);
var Actors         = readPtr(PersistentLevel + 0x98);
var ActorCount     = Memory.readInt(PersistentLevel + 0xA0);

for (var i = 0; i < ActorCount; i++) {
    var Actor = readPtr(Actors.add(i * 8));
    if (Actor.isNull()) continue;                  // 已销毁对象是 nullptr
    var Root = readPtr(Actor.add(0x190));
    if (Root.isNull()) continue;
    console.log("[Actor " + i + "] X=" + readFloat(Root.add(0x1A0)) +
                " Y=" + readFloat(Root.add(0x1A4)) +
                " Z=" + readFloat(Root.add(0x1A8)));
}
```

## 常见误判

- **UE4 版本不同**，`GWorld`/`GObject`/`GNames` 偏移不同 → 先用 UE4Dumper 确认
- **ActorList 中大量 nullptr** → 引擎特性，已销毁对象不实时清理
- **FName 字典在 strip 后不可读** → dump runtime 字符串
- **属性偏移在不同子类中不同** → 注意继承层级和虚函数表位移
- **`GWorld` 偏移是「全局变量的地址」，不是全局变量的值** → 是 `libUE4.so + OFFSET` 处的指针，再解引用才是 `UWorld*`

## 判据

| 观察 | 结论 |
|---|---|
| `strings` 命中 `Health`/`TeamID` 等类名 | FName 池可读，可做 SDK dump |
| 遍历 ActorList 得到合理数量且坐标随移动变化 | `GWorld`/Actor 偏移正确 |
| 读到全 0 或野指针 | 该跳偏移错误 |
| `readFloat(RelLoc)` 得到合理坐标 | `RootComponent` + `RelativeLocation` 偏移正确 |

**外部可观测的判据**：坐标随角色移动而**变化**，且数值在地图范围内 —— 不是「读出了非零浮点数」就算对。

## 坑

- **`GWorld`/`GNames` 偏移随 UE4 版本变化**，不要跨版本复用。
- **ActorList 里 nullptr 是常态**，必须判空再解引用，否则 Frida 脚本会崩。
- **`RelativeLocation` 是 `FVector`（3×float，12 字节）**，偏移 +0/+4/+8，别按 16 字节对齐取。
- **本机无 Android 设备**：方法 1、5 **需真机/模拟器，本机未验证**；方法 2 的字符串搜索可用本机脚本跑（前提是已有 libUE4.so 样本）。
- **`libUE4.so` 可能 150MB+**，`so-structure-audit.py` 全量 strings 会很慢，用 `--grep` 收窄。

## 相关

- `so-structure-audit.md` —— SO 体检基线
- `il2cpp-offset-discovery.md` —— Unity 侧的偏移发现
- `../dynamic/memory-rw-hook.md` —— 跨进程内存读写
