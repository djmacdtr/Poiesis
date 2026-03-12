/**
 * 全局类型定义
 * 对应后端 SQLite 数据库表结构及 API 响应格式
 */

// ──────────────────────────────────────────────
// 章节相关
// ──────────────────────────────────────────────

/** 章节状态 */
export type ChapterStatus = 'draft' | 'completed' | 'needs_review' | 'ready_to_publish' | 'published'

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
export interface StoryStateSummary {
  last_published_chapter: number
  published_chapters: number[]
  active_chapter: number
  recent_scene_refs: string[]
  open_loop_count: number
  resolved_loop_count: number
  overdue_loop_count: number
  chapter_summary: Record<string, unknown>
  published_at: string
}

/** Canon 数据整体响应 */
export interface CanonData {
  world_rules: WorldRule[]
  characters: Character[]
  timeline: TimelineEvent[]
  foreshadowing: Foreshadowing[]
  story_state: StoryStateSummary
  world_blueprint_summary?: WorldBlueprint | null
  relationship_graph?: RelationshipBlueprintEdge[]
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
    can_publish: boolean
    blockers: string[]
  }>
}

export interface PublishBlockers {
  chapter_status: 'draft' | 'needs_review' | 'ready_to_publish' | 'published'
  can_publish: boolean
  blockers: string[]
}

export interface ChapterDetailResponse {
  trace: ChapterTraceDetail
  output?: ChapterOutput | null
  publish: PublishBlockers
}

export interface ReviewEvent {
  id: number
  review_id: number
  action: 'approve' | 'retry' | 'rewrite' | 'patch' | 'reject'
  status: 'succeeded' | 'failed'
  operator: string
  input_payload: Record<string, unknown>
  result_payload: Record<string, unknown>
  created_at: string
}

export interface ScenePatchRecord {
  id: number
  run_id: number
  chapter_number: number
  scene_number: number
  patch_text: string
  before_text: string
  after_text: string
  verifier_issues: SceneIssue[]
  applied_successfully: boolean
  created_at: string
}

export interface SceneDetailResponse {
  scene: SceneTrace
  review?: ReviewQueueItem | null
  review_events: ReviewEvent[]
  patches: ScenePatchRecord[]
  publish_blockers: PublishBlockers
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
  scene_status: string
  latest_result_summary: string
  event_count: number
  resolved_scene_status: string
  result_summary: string
  closed_at?: string | null
  created_at: string
  updated_at: string
}

export interface LoopState {
  loop_id: string
  title: string
  status: 'open' | 'hinted' | 'escalated' | 'resolved' | 'dropped' | 'overdue'
  introduced_in_scene: string
  due_start_chapter: number | null
  due_end_chapter: number | null
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

export interface CreationIntent {
  genre: string
  themes: string[]
  tone: string
  protagonist_prompt: string
  conflict_prompt: string
  ending_preference: string
  forbidden_elements: string[]
  length_preference: string
  target_experience: string
  variant_preference: string
}

export interface ConceptVariant {
  id?: number | null
  variant_no: number
  hook: string
  world_pitch: string
  main_arc_pitch: string
  ending_pitch: string
  variant_strategy: string
  core_driver: string
  conflict_source: string
  world_structure: string
  protagonist_arc_mode: string
  tone_signature: string
  differentiators: string[]
  diversity_note: string
  selected: boolean
}

export interface VariantSimilarityIssue {
  compared_variant_no: number
  text_similarity: number
  structure_overlap: number
  repeated_keywords: string[]
  repeated_sections: string[]
  repeated_fields: string[]
  guidance: string[]
}

export interface VariantRegenerationAttempt {
  attempt_no: number
  status: 'retrying' | 'applied' | 'needs_confirmation'
  warnings: string[]
  similarity_issue: VariantSimilarityIssue | null
}

export interface ConceptVariantRegenerationResult {
  status: 'applied' | 'needs_confirmation'
  target_variant_id: number
  attempt_count: number
  warnings: string[]
  applied_variant: ConceptVariant | null
  proposed_variant: ConceptVariant | null
  similarity_report: VariantSimilarityIssue | null
  attempts: VariantRegenerationAttempt[]
  blueprint: BookBlueprint
}

export interface WorldBlueprint {
  setting_summary: string
  era_context: string
  social_order: string
  historical_wounds: string[]
  public_secrets: string[]
  geography: LocationBlueprint[]
  power_system: PowerSystemBlueprint
  factions: FactionBlueprint[]
  immutable_rules: ImmutableRuleBlueprint[]
  taboo_rules: TabooRuleBlueprint[]
}

export interface LocationBlueprint {
  name: string
  role: string
  description: string
}

export interface PowerSystemBlueprint {
  core_mechanics: string
  costs: string[]
  limitations: string[]
  advancement_path: string[]
  symbols: string[]
}

export interface FactionBlueprint {
  name: string
  position: string
  goal: string
  methods: string[]
  public_image: string
  hidden_truth: string
}

export interface ImmutableRuleBlueprint {
  key: string
  description: string
  category: string
  rationale: string
  is_immutable: boolean
}

export interface TabooRuleBlueprint {
  key: string
  description: string
  consequence: string
  is_immutable: boolean
}

export interface CharacterBlueprint {
  name: string
  role: string
  public_persona: string
  core_motivation: string
  fatal_flaw: string
  non_negotiable_traits: string[]
  relationship_constraints: string[]
  arc_outline: string[]
}

export interface CharacterNode {
  character_id: string
  name: string
  role: string
  public_persona: string
  core_motivation: string
  fatal_flaw: string
  non_negotiable_traits: string[]
  arc_outline: string[]
  faction_affiliation: string
  status: string
}

export interface RelationshipBlueprintEdge {
  edge_id: string
  source_character_id: string
  target_character_id: string
  relation_type: string
  polarity: '正向' | '负向' | '复杂' | '伪装'
  intensity: number
  visibility: '公开' | '半公开' | '隐藏' | '误导性表象'
  stability: '稳定' | '脆弱' | '正在转变'
  summary: string
  hidden_truth: string
  non_breakable_without_reveal: boolean
}

export interface RelationshipPendingItem {
  id?: number | null
  item_type: 'character' | 'relationship'
  status: 'pending' | 'confirmed' | 'rejected'
  source_chapter: number | null
  source_scene_ref: string
  summary: string
  character?: CharacterNode | null
  relationship?: RelationshipBlueprintEdge | null
}

export interface RelationshipConflictReport {
  edge_id: string
  source_chapter: number
  source_scene_ref: string
  conflict_summary: string
  immutable_fact: string
  recommended_paths: string[]
}

export interface RelationshipRetconProposal {
  proposal_id: string
  edge_id: string
  request_reason: string
  change_summary: string
  strategy: '未来关系重规划' | '关系反转提案' | '表象关系与真相关系分层'
  affected_future_chapters: number[]
  future_edge: RelationshipBlueprintEdge
  required_reveals: string[]
}

export interface ChapterRoadmapItem {
  chapter_number: number
  title: string
  goal: string
  core_conflict: string
  turning_point: string
  character_progress: string[]
  relationship_progress: string[]
  planned_loops: Array<Record<string, unknown>>
  closure_function: string
}

export interface BlueprintRevision {
  id: number
  revision_number: number
  is_active: boolean
  change_reason: string
  change_summary: string
  affected_range: number[]
  created_at: string
}

export interface BookBlueprint {
  book_id: number
  status: string
  current_step: string
  active_revision_id: number | null
  selected_variant_id: number | null
  intent: CreationIntent | null
  concept_variants: ConceptVariant[]
  selected_variant: ConceptVariant | null
  world_draft: WorldBlueprint | null
  world_confirmed: WorldBlueprint | null
  character_draft: CharacterBlueprint[]
  character_confirmed: CharacterBlueprint[]
  relationship_graph_draft: RelationshipBlueprintEdge[]
  relationship_graph_confirmed: RelationshipBlueprintEdge[]
  relationship_pending: RelationshipPendingItem[]
  roadmap_draft: ChapterRoadmapItem[]
  roadmap_confirmed: ChapterRoadmapItem[]
  revisions: BlueprintRevision[]
}

export interface RelationshipGraphResponse {
  nodes: CharacterNode[]
  edges: RelationshipBlueprintEdge[]
  pending: RelationshipPendingItem[]
}

export interface RelationshipReplanResponse {
  request_id: number
  request: Record<string, unknown>
  proposal: RelationshipRetconProposal
}

export interface BlueprintGenerateRequest {
  feedback: string
}

export interface BlueprintReplanRequest {
  starting_chapter: number
  reason: string
  guidance: string
}

export interface BookCreateWizardRequest {
  book: BookUpsertRequest
  intent: CreationIntent
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
  /** 可发布章节数 */
  readyToPublishCount: number
}

/** 字数趋势数据点 */
export interface WordCountDataPoint {
  chapter: number
  words: number
}
