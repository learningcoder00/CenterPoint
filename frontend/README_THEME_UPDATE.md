# 前端界面改动说明

## 0411

### 主要调整
- 新增全局主题切换，支持黑夜模式和白天模式。
- 主题选择会写入 `localStorage`，下次打开页面时自动恢复上次使用的模式。
- 优化右上角主题切换按钮样式，使其更简洁。
- 修复白天模式下多个区域显示不清的问题，包括：
  - `Clips` 卡片悬停播放时右下角帧数提示
  - 单个 `clip` 预览弹窗底部播放栏
  - `保存 tags` 按钮
  - 底部悬浮批量操作条
- 新增并完善 Windows 下的前端脚本：
  - `start_frontend.cmd`
  - `build_frontend.cmd`
  - `start_backend.cmd`

### Clips 页样式优化
- 重做 `Clips` 页主卡片样式，提升视觉层次。
- 强化卡片 hover 效果、选中态、徽标和信息区块样式。
- 优化图片预览区和卡片底部标签区的展示。
- 去掉图片预览区重复显示的 `clip id`，只保留 `CLIP PREVIEW` 说明。
- 优化顶部 Hero 区、搜索区和批量操作按钮区的整体排版。

### 当天涉及文件
- `src/App.vue`
- `src/assets/main.css`
- `src/components/PreviewModal.vue`
- `src/views/ClipsView.vue`
- `src/components/ClipCard.vue`
- `start_frontend.cmd`
- `build_frontend.cmd`
- `start_backend.cmd`

## 0412

### 搜索功能增强
- 在 `Clips` 页搜索区新增轻量版“搜索范围”切换：
  - `全部`
  - `clip id`
  - `start token`
  - `tag`
- 搜索输入框会根据当前搜索范围切换占位提示文本。
- 搜索结果数量提示与搜索区联动显示。
- 调整搜索范围按钮的位置，从标题旁边移到输入框下方，使布局更清爽。

### 搜索命中高亮
- 为搜索结果增加字段级命中反馈。
- 命中 `clip id` 时，高亮标题。
- 命中 `start token` 时，高亮对应信息卡片。
- 命中 `tag` 时，只高亮单独命中的标签本身。
- 将结果筛选逻辑与高亮逻辑拆分，避免模糊匹配过宽导致错误高亮。
- 额外尝试了一版“命中统一红色”的实验样式，方便比较搜索反馈的可见度。

### 当天涉及文件
- `src/views/ClipsView.vue`
- `src/components/ClipCard.vue`
- `src/router.js`
- `README_THEME_UPDATE.md`

## 0413

### 新页面接入
- 接入 `wang` 新增的 `AIOptimizationView.vue` 页面，并正式挂到当前前端导航中。
- 顶部导航新增 `AI Optimization` 入口，和现有 `Clips`、`Results` 页面并列展示。
- 保留后端新增的 AI 优化接口能力，同时把页面结构重写进当前前端体系。

### 统一样式
- 将 `AIOptimizationView.vue` 从旧版独立样式改造成和现有页面一致的视觉语言。
- 新页面统一使用当前项目的 `hero`、`stats`、`controls`、`card`、`badge` 等样式体系。
- 重新设计 AI 页面布局：
  - 顶部为和 `Clips` / `Results` 一致的 Hero 区
  - 中间为请求提交区与最新响应区双栏布局
  - 底部为优化建议历史卡片列表
- 统一表单、按钮、搜索框、删除按钮、展开按钮的视觉风格，保证和现有前端主题一致。

### 交互与结构整理
- 将 AI 相关请求从页面内联 `fetch` 抽离到 `src/api.js`，和原有接口封装方式保持一致。
- 保留从 `Results` 页点击 `AI优化` 后通过 `jobId` 自动带入的交互。
- 支持按 `job id` 或问题描述搜索历史优化建议。
- 保留优化建议的删除、展开 / 收起、刷新列表等功能。

### 当天涉及文件
- `src/App.vue`
- `src/api.js`
- `src/views/AIOptimizationView.vue`
- `README_THEME_UPDATE.md`

## 最终涉及文件汇总
- `src/App.vue`
- `src/api.js`
- `src/assets/main.css`
- `src/router.js`
- `src/views/AIOptimizationView.vue`
- `src/views/ClipsView.vue`
- `src/views/ResultsView.vue`
- `src/components/ClipCard.vue`
- `src/components/PreviewModal.vue`

## Windows 脚本说明
- `start_frontend.cmd`：启动前端开发服务器，用于本地实时预览 Vue 页面。
- `build_frontend.cmd`：打包前端代码，生成给后端读取的 `dist` 静态文件。
- `start_backend.cmd`：启动 Java 后端服务，并通过后端地址访问页面和接口数据。
