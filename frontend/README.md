# Poiesis Frontend Console / 前端控制台

Poiesis 前端当前已经完全围绕新的 `Scene 工作台（Scene Workspace）` 架构构建，不再兼容旧的 Run 页面和 Staging 审批页。

## Tech Stack / 技术栈

- React 19
- TypeScript
- Vite 7
- TailwindCSS 4
- React Router
- TanStack React Query
- Recharts
- Lucide React
- Sonner

## Quick Start / 快速开始

```bash
npm install
cp .env.example .env.local
npm run dev
```

`.env.local` 示例：

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

生产构建：

```bash
npm run build
```

## Pages / 当前页面

| 路径 | 页面 | 说明 |
|---|---|---|
| `/` | 仪表盘 | 章节、字数、review、loop 总览 |
| `/runs` | Run Board（运行面板） | 启动新的 scene run，查看运行列表 |
| `/runs/:runId` | Scene Run Detail（运行详情） | 查看 run / chapter / scene 明细 |
| `/reviews` | Review Queue（审阅队列） | 处理异常 scene |
| `/loops` | Loop Board（剧情线索面板） | 查看 open / resolved / overdue loops |
| `/chapters` | 章节列表 | 已发布章节列表 |
| `/chapters/:id` | 章节详情 | 章节正文与计划信息 |
| `/canon` | Canon Explorer（世界设定浏览） | 世界规则、角色、时间线、伏笔展示 |
| `/books` | 书籍管理 | 多书配置 |
| `/settings` | 系统设置 | provider、model、API Key 等配置 |

## Directory Structure / 目录结构

```text
src/
├─ pages/
├─ components/
├─ services/
├─ types/
├─ lib/
└─ main.tsx
```

## Notes / 重要说明

- 旧 `Run.tsx`、`RunDetail.tsx`、`Staging.tsx`、`Stats.tsx` 已移除
- 运行相关请求只走 `/api/runs`、`/api/reviews`、`/api/loops`、`/api/canon`
- 仪表盘统计已切到 `review + loop` 指标，不再展示旧 staging（候选变更）指标
