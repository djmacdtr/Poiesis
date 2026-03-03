# Poiesis 前端控制台

基于 React + TypeScript + Vite 构建的 AI 小说写作控制台。

## 技术栈

- **框架**：React 19 + TypeScript（strict 模式）
- **构建**：Vite 7 + TailwindCSS 4
- **路由**：React Router v7
- **数据请求**：TanStack React Query v5
- **图表**：Recharts
- **图标**：Lucide React
- **通知**：Sonner

## 快速开始

```bash
# 安装依赖（已完成）
npm install

# 配置环境变量
cp .env.example .env.local
# 编辑 .env.local，设置后端地址：
# VITE_API_BASE_URL=http://localhost:8000

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

## 页面说明

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | 仪表盘 | 写作进度概览、字数趋势图 |
| `/run` | 运行控制 | 启动写作任务、实时查看进度 |
| `/chapters` | 章节列表 | 所有章节的标题、字数、状态 |
| `/chapters/:id` | 章节详情 | 正文内容、写作计划 |
| `/canon` | 世界设定 | 角色、规则、时间线、伏笔 |
| `/staging` | 候选审批 | 审批或拒绝 AI 提出的设定变更 |
| `/stats` | 统计分析 | 字数柱状图、章节状态分布 |

## 目录结构

```
src/
├─ pages/          # 页面组件
├─ components/     # 通用组件
├─ services/       # API 服务层
├─ types/          # TypeScript 类型定义
├─ lib/            # 工具函数
└─ main.tsx        # 入口
```
