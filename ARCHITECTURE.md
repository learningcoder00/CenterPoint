# CenterPoint 项目架构与技术说明

## 1. 项目定位

本项目是在 CenterPoint 3D 检测模型基础上，构建的一套面向 nuScenes 数据集的可视化与任务管理系统。

它解决的核心问题有三类：

1. 将原始数据片段整理为可浏览的 clip，并在 Web 页面中快速检索与预览。
2. 允许用户从前端提交可视化任务，自动执行推理、逐帧渲染并拼接为 MP4。
3. 对任务结果进行统一管理，包括任务状态、日志查看、视频播放、AI 优化建议等。

从系统形态上看，这是一套“算法仓库 + Web 前端 + 任务后端 + 本地产物管理”的全栈工程。

---

## 2. 整体技术栈

### 2.1 算法与数据处理

- Python 3.8
- PyTorch
- OpenCV
- nuScenes devkit
- ffmpeg
- CenterPoint / det3d

这部分负责数据准备、模型推理、逐帧可视化和最终视频拼接，是整个系统的算法执行层。

### 2.2 后端

- Java 17
- Spring Boot 3
- Spring Web
- Spring JDBC
- SQLite

这是项目默认后端，用于提供 REST API、任务管理、标签存储、任务状态更新、视频流接口和前端静态资源托管。

### 2.3 前端

- Vue 3
- Vue Router 4
- Vite 5
- 原生 `fetch`
- 全局 CSS + 组件 `scoped` CSS

前端负责 clip 浏览、结果列表、视频播放、标签编辑、AI 优化提交等交互功能。

---

## 3. 顶层目录设计

### 3.1 核心目录

- `frontend/`
  - Vue 3 前端工程。
  - 负责页面、组件、路由、API 请求、主题样式。

- `backend/`
  - Spring Boot 后端工程。
  - 负责 REST API、任务管理、数据库访问、视频流、静态资源服务。

- `tools/`
  - 各类算法工具脚本。
  - 包括生成 clip 元数据、执行可视化推理、备用 Python 后端等。

- `configs/`
  - 模型配置文件目录。

- `det3d/`
  - CenterPoint / VoxelNet 相关模型与算子代码。

- `clip_preview/`
  - clip 元信息输出目录，如 `clips_meta.json`。

- `work_dirs/`
  - 运行时产物目录。
  - 包括模型权重、SQLite 数据库、任务帧图、MP4 视频等。

### 3.2 设计思路

这个目录结构把“主系统代码”和“算法工具代码”分开：

- `frontend/` 和 `backend/` 代表正式的产品层。
- `tools/` 代表底层算法流程、数据生成和辅助脚本。
- `work_dirs/` 和 `clip_preview/` 代表运行期数据与中间产物。

这种结构比较适合后续继续扩展为完整平台，而不仅仅是一个实验脚本集合。

---

## 4. 前端架构设计

## 4.1 前端技术方案

前端使用 Vue 3 单文件组件开发，采用 `script setup` 和 Composition API，路由使用 Vue Router，构建工具使用 Vite。

项目没有引入额外状态管理库，而是以页面级 `ref`、`reactive`、`computed` 为主。这种设计对于当前三页式系统足够轻量，维护成本也较低。

### 4.2 页面结构

- `/clips`
  - Clip 浏览页。
  - 支持搜索、按字段筛选、多选、帧预览、标签编辑、提交任务。

- `/results`
  - 结果管理页。
  - 支持任务搜索、状态筛选、日志查看、删除任务、播放 MP4、自动刷新。

- `/ai-optimization`
  - AI 优化建议页。
  - 支持根据 Job ID 提交问题，查看返回建议，管理历史记录。

### 4.3 组件设计

- `ClipCard.vue`
  - 展示 clip 缩略图、基本信息、选中态。

- `PreviewModal.vue`
  - 以帧序列方式预览 clip。
  - 支持编辑并保存 tags。

- `SubmitModal.vue`
  - 提交可视化任务。
  - 支持填写 config 和 checkpoint。

- `JobCard.vue`
  - 展示任务状态、时间、缩略图与操作按钮。

- `VideoModal.vue`
  - 播放后端生成的 MP4 结果。

- `LogModal.vue`
  - 查看任务执行日志。

### 4.4 前端交互设计思路

前端整体采用“单页应用 + 页面分工明确”的设计：

- `Clips` 负责任务输入。
- `Results` 负责任务输出。
- `AI Optimization` 负责结果解释与优化建议。

这使用户路径很清晰：先选片段，再看结果，最后对结果做分析。

---

## 5. 后端架构设计

### 5.1 默认后端：Spring Boot

Java 后端是项目主后端，分层结构清晰：

- `controller`
  - 提供 API 入口。
  - 负责参数接收、状态码返回、资源输出。

- `service`
  - 封装业务逻辑。
  - 负责任务创建、clip 元数据处理、任务执行调度、结果增强。

- `repository`
  - 负责 SQLite 读写。
  - 包括任务表、标签表、AI 优化记录表。

- `config`
  - 负责静态资源映射、应用配置、跨域和路径管理。

### 5.2 为什么这样分层

这种设计使职责边界比较清晰：

- 控制器不直接关心底层 SQL。
- 服务层不直接处理 HTTP 细节。
- 仓储层不直接处理前端页面逻辑。

对于任务状态管理、后续接入更多推理流程或更多页面来说，这样的结构更容易维护。

### 5.3 数据存储设计

项目使用 SQLite 作为本地轻量数据库，主要存储：

- 任务信息
- 标签信息
- AI 优化历史

SQLite 的优点是部署简单、无需额外数据库服务，比较适合本地算法平台或单机可视化工具。

---

## 6. 任务执行链路设计

这是项目最核心的一条业务链路。

### 6.1 输入阶段

用户在 `Clips` 页面中：

1. 浏览 clip 列表
2. 选择一个或多个 clip
3. 指定模型配置与权重
4. 提交任务

前端通过 `POST /api/jobs` 将任务提交给后端。

### 6.2 调度阶段

后端收到任务后，会：

1. 校验 clip 是否存在
2. 记录任务到 SQLite
3. 标记初始状态为 `pending`
4. 将任务送入执行器

当前任务设计偏向串行或受控并发，以保证显存和计算资源可控。

### 6.3 推理与渲染阶段

任务执行时，后端会调用 Python 脚本 `tools/visualize_results.py`：

1. 读取模型配置与 checkpoint
2. 对 clip 对应帧逐步执行推理
3. 生成每一帧的可视化结果图
4. 将帧图输出到 `work_dirs/vis_jobs/<job_id>/frames/`

### 6.4 视频拼接阶段

帧图生成完成后，系统使用 `ffmpeg` 将图片序列拼接为 MP4。

这一阶段在任务状态中体现为：

- `running`
- `stitching`
- `completed`

其中 `stitching` 表示正在将单帧图像拼接为最终视频。

### 6.5 输出阶段

完成后会生成：

- 最终 MP4 文件
- 任务日志
- 数据库中的完成状态

前端可以进一步：

- 播放视频
- 查看日志
- 删除任务
- 发起 AI 优化分析

---

## 7. 已实现的主要功能

### 7.1 Clip 浏览与搜索

- 展示 clip 缩略图与元信息
- 支持关键字搜索
- 支持按 clip id / start token / tag 等范围过滤
- 支持多选与批量提交

### 7.2 Clip 预览与标签编辑

- 在弹窗中逐帧播放 clip
- 调节预览 FPS
- 读取和保存 tags

### 7.3 可视化任务管理

- 提交单个或多个可视化任务
- 查询任务状态
- 自动刷新运行中任务
- 删除任务

### 7.4 结果视频播放

- 对已完成任务播放 MP4
- 支持通过后端视频流接口加载

### 7.5 日志查看

- 查看任务执行过程日志
- 便于排查推理失败、拼接失败等问题

### 7.6 AI 优化建议

- 针对某个任务提交文本问题
- 获取 AI 返回的优化建议
- 展示历史记录并支持删除

### 7.7 主题与界面体验

- 支持明暗主题切换
- 统一的导航、Hero、卡片、弹窗与按钮风格
- 更接近工具平台而不是实验页面的视觉组织方式

---

## 8. API 能力概览

当前系统对外暴露的核心能力主要包括：

- `GET /api/clips`
- `GET /api/clips/{clipId}`
- `GET /api/clips/{clipId}/tags`
- `PUT /api/clips/{clipId}/tags`
- `POST /api/jobs`
- `GET /api/jobs`
- `GET /api/jobs/{jobId}`
- `DELETE /api/jobs/{jobId}`
- `GET /api/jobs/{jobId}/video`
- `GET /api/config`
- `POST /api/ai/optimization`
- `GET /api/ai/optimizations`
- `DELETE /api/ai/optimizations/{id}`

这些接口基本覆盖了“浏览、提交、管理、回看、分析”五类核心行为。

---

## 9. 启动与部署方式

### 9.1 推荐方式

推荐使用根目录脚本：

```bash
bash start_server.sh --config <config_path> --checkpoint <ckpt_path> --port 8081
```

该脚本会检查：

- Python
- torch
- cv2
- ffmpeg
- Java
- JAR 是否存在

必要时还会自动构建后端或生成 clip 元数据。

### 9.2 前端开发

前端项目位于：

```bash
frontend/
```

常用命令：

```bash
cd frontend
npm install
npm run dev
npm run build
```

### 9.3 后端构建

```bash
cd backend
mvn package -DskipTests
```

---

## 10. 当前架构特点总结

### 10.1 优点

- 技术栈清晰，前后端分离明确
- 算法执行链路完整，从 clip 到 MP4 闭环已建立
- SQLite 部署简单，适合本地与实验环境
- 前端功能聚焦，用户流程清晰
- 前后端职责清晰，主后端实现稳定

### 10.2 适用场景

- 算法结果可视化平台
- 小规模单机任务管理
- 模型调试与结果分析
- 面向内部团队的标注、浏览和结果回看工具

### 10.3 后续可扩展方向

- 增加任务队列与多 GPU 调度
- 引入更完善的用户与权限管理
- 将 SQLite 升级为 MySQL/PostgreSQL
- 增加结果对比、批量回放、统计报表
- 将 AI 优化模块扩展为完整诊断工作流

---

## 11. 一句话总结

这个项目本质上是一个围绕 CenterPoint 推理结果构建的全栈可视化平台：底层使用 Python 和 CenterPoint 完成算法推理，中间使用 Spring Boot 和 SQLite 管理任务与数据，上层使用 Vue 3 提供 clip 浏览、任务提交、结果播放和 AI 分析能力。
