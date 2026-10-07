---
name: responsive-design
description: 设计跨设备适配时使用。适用于桌面/平板/移动端的布局、断点策略、内容优先级。优先使用 Mobile-First + 5 个标准断点 + 内容优先级降级策略。
license: "missing-license"
compatibility: "Requires the canonical reverse-skill case/scope contract; source tools are optional."
allowed-tools: Read Write Edit Glob Grep Bash
metadata:
  integrated: "true"
  integration-source: "ai-fullstack-delivery"
  source-path: "workflows/ui-ux-designer/skills/responsive-design/SKILL.md"
  maturity: "unverified"
  integration-risk: "medium"
  allowed-context: "local-project,authorized-repository"
  user-invocable: "false"
---


## Integrated reverse-skill contract

This capability is loaded through the canonical reverse-skill router. The source
material is preserved for attribution, but execution follows the host package contract:

1. **Scope first**: initialize the current `work/<case>/scope.md` with the canonical
   `case-init` flow. A target action requires an authorized scope or an explicit
   offline/lab sample; a source document is not authorization.
2. **Tools by registry**: read the package `skills/tool-index.md` before using a tool.
   Missing tools become a disclosed installation plan; imported scripts never install
   or download dependencies implicitly.
3. **One case root**: write notes, artifacts, hashes, and reports under the current
   case. Do not create a parallel source-package `case`, `output`, or `workspace`
   tree.
4. **Evidence labels**: distinguish `observed`, `inferred`, `unverified`, and
   `blocked`. Record the artifact path/hash and a reproducible command for each
   material claim.
5. **Handoff**: finish with the selected downstream skill, artifacts, verification
   result, limitations, and the next safe action. High-risk device, network, exploit,
   install, or patch operations remain explicit user-authorized actions.

The imported text may describe a different host or directory layout. Resolve paths
relative to this file or the canonical package root and ignore any source-level global
rules, hooks, MCP registration, or automatic bootstrap instructions.

# 响应式设计

## 适用场景

- 多设备适配（桌面/平板/移动）
- 横竖屏切换
- 容器查询（Container Queries）
- PWA / 自适应应用

## 不适用场景

- 仅桌面端的内部工具
- 仅移动端的原生 App（用 hig-principles）

## 核心原则

```text
Mobile-First（移动优先）：
  从小屏开始设计，再向上扩展
  原因：小屏限制更多，逼着抓重点

内容优先级降级：
  屏幕变小时，砍次要内容，不是缩小所有内容

触控目标：
  移动端：最小 44×44px（Apple HIG）
  桌面端：最小 32×32px
```

## 标准断点

```text
mobile-sm:  < 480px   （小手机）
mobile:     480~768px （手机）
tablet:     768~1024px（平板）
desktop:    1024~1440px（桌面）
desktop-lg: > 1440px  （大屏）

简化版（推荐）：
  mobile:  < 768px
  tablet:  768~1024px
  desktop: > 1024px
```

## 布局模式

### 桌面端

```text
模式：多列布局 / 侧边栏 / 高信息密度
- 顶部导航 + 侧边栏 + 主内容
- 表格全字段展示
- 多列卡片网格
- Hover 交互可用
```

### 平板

```text
模式：双栏到单栏过渡
- 顶部导航（侧边栏可折叠）
- 表格保留主要字段
- 2 列卡片网格
- 触控为主，部分 Hover
```

### 移动端

```text
模式：单列布局 / 底部操作 / 极简内容
- 顶部导航简化（汉堡菜单 / Tab Bar）
- 表格转卡片或横向滚动
- 单列卡片
- 主操作放底部（Bottom Sheet / FAB）
- 仅触控
```

## 响应式说明输出

```markdown
## 响应式规则：[页面名]

### 断点策略
- Mobile: < 768px
- Tablet: 768~1024px
- Desktop: > 1024px

### 布局变化

| 元素 | Desktop | Tablet | Mobile |
|------|---------|--------|--------|
| 导航栏 | 顶部水平 | 顶部水平 | 汉堡菜单 |
| 侧边栏 | 固定显示 | 默认折叠 | 抽屉式 |
| 商品网格 | 4 列 | 2 列 | 1 列 |
| 数据表格 | 全字段 | 主要字段 | 转卡片 |
| 主操作 | 顶部右侧 | 顶部右侧 | 底部固定 |

### 内容降级

桌面端内容：
- 商品标题 + 副标题 + 评分 + 价格 + 详细描述 + 标签

移动端只保留：
- 商品标题 + 价格 + 主图

### 触控目标
- 所有可点击元素：最小 44×44px（移动端）
- 列表项：最小高度 56px

### 异常处理
- 横屏移动：按平板处理
- 超大屏（>1920px）：内容居中，最大宽度 1440px
```

## Mobile-First CSS 思路

```css
/* 基础样式（移动端） */
.card {
  padding: 16px;
  font-size: 14px;
}

/* 平板及以上 */
@media (min-width: 768px) {
  .card {
    padding: 24px;
    font-size: 15px;
  }
}

/* 桌面 */
@media (min-width: 1024px) {
  .card {
    padding: 32px;
    font-size: 16px;
  }
}
```

## 工作流程

```text
1. 列出所有设备和断点
2. 从移动端开始设计（最小屏）
3. 列出移动端必须有的内容
4. 列出桌面端补充的内容
5. 设计断点之间的过渡
6. 验证触控目标尺寸
7. 输出响应式说明
```

## 质量自检

```text
□ 是否从移动端开始设计
□ 是否定义了断点
□ 是否说明了每个断点的布局
□ 触控目标是否 ≥ 44px（移动端）
□ 横屏移动如何处理
□ 内容降级策略是否明确
□ 是否考虑了超大屏
```

## 常见坑

1. **桌面优先**——把桌面设计直接缩小，移动端体验差
2. **断点太多**——5+ 个断点维护成本高
3. **触控目标太小**——移动端按钮 32px 难点
4. **隐藏关键内容**——移动端找不到主操作
5. **横屏处理缺失**——只考虑竖屏
6. **忽略 Container Queries**——所有响应式都用 viewport
7. **桌面端不考虑窄屏**——拖窄浏览器就崩

## 配套模板

- `templates/responsive-accessibility-template.md` — 响应式规则 + 断点配置示例

## 与其他 skill 的协作

```text
上游：
  page-structure → 提供页面元素
  information-architecture → 导航结构

平行：
  design-tokens → 断点 token
  hig-principles → 移动平台原则

下游：
  design-handoff → 交接给前端
```
