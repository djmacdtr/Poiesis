/**
 * 全局类型定义
 * 对应后端 SQLite 数据库表结构及 API 响应格式
 */

// ──────────────────────────────────────────────
// 章节相关
// ──────────────────────────────────────────────

/** 章节状态 */
export type ChapterStatus = 'draft' | 'completed' | 'published'

/** 章节列表项（轻量版，不含正文） */
export interface ChapterSummaryItem {
  id: number
  book_id: number
  chapter_number: number
  title: string
  word_count: number
  status: ChapterStatus
  created_at: string
  updated_at: string
}

/** 章节详情（含正文与计划） */
export interface Chapter extends ChapterSummaryItem {
  content: string
  plan: ChapterPlan | null
}

/** 章节写作计划 */
export interface ChapterPlan {
  outline?: string
  key_events?: string[]
  characters?: string[]
  [key: string]: unknown
}

/** 章节摘要（AI 生成） */
export interface ChapterSummary {
  id: number
  book_id?: number
  chapter_number: number
  summary: string
  key_events: string[]
  characters_featured: string[]
  new_facts_introduced: string[]
  created_at: string
}

// ──────────────────────────────────────────────
// 世界设定 / Canon
// ──────────────────────────────────────────────

/** 世界规则 */
export interface WorldRule {
  id: number
  rule_key: string
  description: string
  is_immutable: boolean
  category: string
  created_at: string
}

/** 角色属性（自由扩展） */
export type CharacterAttributes = Record<string, unknown>

/** 角色 */
export interface Character {
  id: number
  name: string
  description: string
  core_motivation: string
  attributes: CharacterAttributes
  status: string
  created_at: string
  updated_at: string
}

/** 时间线事件 */
export interface TimelineEvent {
  id: number
  event_key: string
  chapter_number: number
  description: string
  characters_involved: string[]
  timestamp_in_world: string
  created_at: string
}

/** 伏笔状态 */
export type ForeshadowingStatus = 'active' | 'resolved' | 'dropped'

/** 伏笔 */
export interface Foreshadowing {
  id: number
  hint_key: string
  description: string
  introduced_in_chapter: number
  resolved_in_chapter: number | null
  status: ForeshadowingStatus
  created_at: string
}

/** Canon 数据整体响应 */
export interface CanonData {
  world_rules: WorldRule[]
  characters: Character[]
  timeline: TimelineEvent[]
  foreshadowing: Foreshadowing[]
}

// ──────────────────────────────────────────────
// Staging（候选变更）
// ──────────────────────────────────────────────

/** 变更状态 */
export type StagingStatus = 'pending' | 'approved' | 'rejected'

/** Staging 变更记录 */
export interface StagingChange {
  id: number
  change_type: string
  entity_type: string
  entity_key: string
  proposed_data: Record<string, unknown>
  status: StagingStatus
  source_chapter: number | null
  rejection_reason: string | null
  created_at: string
}

/** Staging 列表查询参数 */
export type StagingFilter = StagingStatus | 'all'

// ──────────────────────────────────────────────
// 运行任务
// ──────────────────────────────────────────────

/** 运行任务状态 */
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'interrupted'

/** 启动运行响应 */
export interface RunResponse {
  task_id: string
  status: TaskStatus
  message?: string
}

/** 运行任务详情（轮询用） */
export interface TaskDetail {
  task_id: string
  status: TaskStatus
  progress?: number
  current_chapter?: number
  total_chapters?: number
  logs?: string[]
  error?: string
  preview_text?: string
  created_at?: string
  updated_at?: string
}

// ──────────────────────────────────────────────
// 书籍
// ──────────────────────────────────────────────

export interface BookItem {
  id: number
  name: string
  language: string
  style_preset: string
  style_prompt: string
  naming_policy: string
  is_default: boolean
  created_at: string
  updated_at: string
}

export interface BookUpsertRequest {
  name: string
  language: string
  style_preset: string
  style_prompt: string
  naming_policy: string
  is_default: boolean
}

// ──────────────────────────────────────────────
// 统计（前端本地聚合）
// ──────────────────────────────────────────────

/** 仪表盘统计数据 */
export interface DashboardStats {
  /** 总章节数 */
  totalChapters: number
  /** 已完成章节数 */
  completedChapters: number
  /** 总字数 */
  totalWords: number
  /** 待审批变更数 */
  pendingStagingCount: number
  /** 已注册角色数 */
  characterCount: number
  /** 活跃伏笔数 */
  activeForeshadowingCount: number
}

/** 字数趋势数据点 */
export interface WordCountDataPoint {
  chapter: number
  words: number
}
