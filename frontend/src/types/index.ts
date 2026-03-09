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
// Scene 工作台
// ──────────────────────────────────────────────

export interface RunResponse {
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'interrupted'
}

export interface ScenePlan {
  chapter_number: number
  scene_number: number
  title: string
  goal: string
  conflict: string
  turning_point: string
  location: string
  pov_character: string
  required_loops: string[]
  continuity_requirements: string[]
}

export interface SceneDraft {
  chapter_number: number
  scene_number: number
  title: string
  content: string
  retrieval_context: Record<string, unknown>
}

export interface SceneChangeSet {
  characters: Array<Record<string, unknown>>
  world_rules: Array<Record<string, unknown>>
  timeline_events: Array<Record<string, unknown>>
  loop_updates: Array<Record<string, unknown>>
  uncertain_claims: Array<Record<string, unknown>>
  raw_changes: Array<Record<string, unknown>>
}

export interface SceneIssue {
  severity: 'fatal' | 'warning' | 'info'
  type: string
  reason: string
  repair_hint: string
  location: string
}

export interface SceneTrace {
  run_id: number
  chapter_number: number
  scene_number: number
  status: 'pending' | 'running' | 'completed' | 'needs_review' | 'failed' | 'approved'
  scene_plan: ScenePlan
  draft?: SceneDraft | null
  final_text: string
  changeset: SceneChangeSet
  verifier_issues: SceneIssue[]
  review_required: boolean
  review_reason: string
  review_status: string
  metrics: Record<string, unknown>
  error_message?: string | null
}

export interface StoryPlan {
  book_id: number
  focus: string
  active_themes: string[]
  active_loops: string[]
  narrative_pressure: string
}

export interface SceneChapterPlan {
  chapter_number: number
  title: string
  goal: string
  hook: string
  must_preserve: string[]
  must_progress_loops: string[]
  scene_count_target: number
  notes: string[]
  source_plan: Record<string, unknown>
}

export interface ChapterTraceDetail {
  run_id: number
  chapter_number: number
  status: string
  story_plan: StoryPlan
  chapter_plan: SceneChapterPlan
  scenes: SceneTrace[]
  assembled_text: string
  summary: Record<string, unknown>
  metrics: Record<string, unknown>
  review_required: boolean
  error_message?: string | null
}

export interface ChapterOutput {
  run_id: number
  chapter_number: number
  title: string
  content: string
  summary: Record<string, unknown>
  scene_count: number
  status: string
}

export interface SceneRunSummary {
  id: number
  task_id: string
  book_id: number
  status: string
  current_chapter: number
  total_chapters: number
  created_at: string
  updated_at: string
  error_message?: string | null
}

export interface SceneRunDetail {
  run: SceneRunSummary
  chapters: Array<{
    chapter_number: number
    status: string
    summary: Record<string, unknown>
    metrics: Record<string, unknown>
    review_required: boolean
  }>
}

export interface ChapterDetailResponse {
  trace: ChapterTraceDetail
  output?: ChapterOutput | null
}

export interface SceneDetailResponse {
  scene: SceneTrace
  patches: Array<Record<string, unknown>>
}

export interface ReviewQueueItem {
  id: number
  run_id: number
  chapter_number: number
  scene_number: number
  action: string
  status: string
  reason: string
  patch_text: string
  created_at: string
  updated_at: string
}

export interface LoopState {
  loop_id: string
  title: string
  status: 'open' | 'hinted' | 'escalated' | 'resolved' | 'dropped' | 'overdue'
  introduced_in_scene: string
  due_window: string
  priority: number
  related_characters: string[]
  resolution_requirements: string[]
  last_updated_scene: string
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
  /** 待处理 review 数 */
  pendingReviewCount: number
  /** 已注册角色数 */
  characterCount: number
  /** 活跃 loop 数 */
  activeLoopCount: number
}

/** 字数趋势数据点 */
export interface WordCountDataPoint {
  chapter: number
  words: number
}
