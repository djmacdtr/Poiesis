/**
 * 前端显示文案映射：
 * 这里统一承接后端状态码、语言码、文风预设等“机器值 -> 中文文案”的转换。
 *
 * 设计约束：
 * 1. 后端继续返回稳定的英文/代码态枚举，便于 API 与测试保持一致；
 * 2. 前端界面层不直接暴露这些机器值，统一通过本文件转成中文友好文案；
 * 3. 后续如果新增状态，只需要补这里的映射，不要在页面组件里零散手写。
 */

const LANGUAGE_LABELS: Record<string, string> = {
  'zh-CN': '中文',
  'en-US': '英文',
}

const STYLE_PRESET_LABELS: Record<string, string> = {
  webnovel_cn: '网文通俗风（节奏快）',
  literary_cn: '文学细腻风（描写强）',
  neutral_cn: '中性叙事风（稳健）',
}

const NAMING_POLICY_LABELS: Record<string, string> = {
  localized_zh: '中文化（音译/意译）',
  preserve_original: '保留原名',
  hybrid: '混合策略',
}

/**
 * 蓝图状态与 current_step 都属于后端工作流真源。
 * 这里的中文映射只负责“界面阅读友好”，不改变业务判断语义。
 */
const BLUEPRINT_STATUS_LABELS: Record<string, string> = {
  draft: '草稿中',
  concept_selected: '已选定候选方向',
  world_ready: '世界观待确认',
  world_confirmed: '世界观已确认',
  characters_ready: '人物待确认',
  characters_confirmed: '人物已确认',
  story_arcs_ready: '章节路线规划中',
  locked: '整书蓝图已锁定',
}

const BLUEPRINT_STEP_LABELS: Record<string, string> = {
  intent: '创作意图',
  concept: '候选方向',
  concept_variants: '候选方向',
  world: '世界观',
  characters: '人物蓝图',
  relationships: '关系图谱',
  story_arcs: '章节路线',
  roadmap: '章节路线',
  continuity: '连续性校对',
  locked: '蓝图锁定',
}

const TASK_STATUS_LABELS: Record<string, string> = {
  new: '新建',
  in_progress: '推进中',
  resolved: '已解决',
  failed: '失败',
}

const TASK_STATUS_VALUE_ALIASES: Record<string, 'new' | 'in_progress' | 'resolved' | 'failed'> = {
  new: 'new',
  '新建': 'new',
  in_progress: 'in_progress',
  '进行中': 'in_progress',
  '推进中': 'in_progress',
  resolved: 'resolved',
  '已解决': 'resolved',
  '已完成': 'resolved',
  failed: 'failed',
  '失败': 'failed',
}

const LOOP_STATUS_LABELS: Record<string, string> = {
  open: '未回收',
  progressed: '已推进',
  hinted: '已提示',
  escalated: '已升级',
  resolved: '已回收',
  dropped: '已放弃',
  overdue: '已逾期',
}

const LOOP_STATUS_VALUE_ALIASES: Record<string, 'open' | 'progressed' | 'resolved'> = {
  open: 'open',
  '未回收': 'open',
  progressed: 'progressed',
  '已推进': 'progressed',
  resolved: 'resolved',
  '已回收': 'resolved',
}

/**
 * 连续性事件类型用于“最近事件”时间线。
 * 后端保留稳定的英文 kind，前端统一翻译成面向作者的中文短标签。
 */
const CONTINUITY_EVENT_KIND_LABELS: Record<string, string> = {
  main_progress: '主线推进',
  key_event: '关键事件',
  reveal: '信息揭示',
  world_update: '世界更新',
}

const CREATIVE_ISSUE_STATUS_LABELS: Record<string, string> = {
  open: '待处理',
  planned: '已规划',
  awaiting_approval: '待确认',
  applied: '已执行',
  verified: '已复验',
  escalated: '已升级',
  dismissed: '已忽略',
}

const CREATIVE_REPAIRABILITY_LABELS: Record<string, string> = {
  deterministic: '结构补丁',
  llm: '需要改写',
  manual: '建议手动处理',
}

/**
 * 问题来源层用于告诉作者“这个问题来自哪一层真源”。
 * roadmap 之外的层目前还只接入了检测或只读视图，因此需要单独翻译出来源，
 * 避免作者误以为所有问题都已经支持一键执行修复。
 */
const CREATIVE_SOURCE_LAYER_LABELS: Record<string, string> = {
  blueprint: '蓝图层',
  roadmap: '章节路线',
  scene: '场景生成',
  review: '审阅队列',
  canon: '设定同步',
}

const CREATIVE_STRATEGY_LABELS: Record<string, string> = {
  field_patch: '字段级修补',
  chapter_rewrite: '单章重写',
  arc_rewrite: '阶段重写',
  scene_rewrite: '场景重写',
  canon_sync: '设定同步',
}

const CREATIVE_RISK_LABELS: Record<string, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
}

const CREATIVE_RUN_STATUS_LABELS: Record<string, string> = {
  queued: '排队中',
  running: '执行中',
  succeeded: '执行成功',
  failed: '执行失败',
  rolled_back: '已回滚',
}

const SCENE_STATUS_LABELS: Record<string, string> = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  needs_review: '待审阅',
  approved: '已通过',
  failed: '失败',
}

const REVIEW_STATUS_LABELS: Record<string, string> = {
  pending: '待处理',
  completed: '已处理',
  failed: '执行失败',
}

const GENERATION_EVAL_TASK_TYPE_LABELS: Record<string, string> = {
  next_chapter: '生成下一章',
  rewrite_chapter: '单章重写',
  rewrite_arc: '单幕骨架重写',
  field_patch: '字段级修补',
  scene_retry: '场景重试',
  scene_patch: '场景修补',
}

const GENERATION_EVAL_ACCEPTED_BY_LABELS: Record<string, string> = {
  auto: '系统自动采用',
  user: '用户确认执行',
  review: '审阅确认采用',
}

const CREATIVE_ISSUE_TYPE_LABELS: Record<string, string> = {
  scene_review_pending: '待审阅场景',
  task_status_jump: '任务状态跳变',
  duplicate_task_creation: '重复创建任务',
  invalid_task_payload: '任务结构非法',
  invalid_chapter_dependency: '章节承接关系非法',
  missing_previous_dependency: '缺少上一章承接',
  missing_story_progress: '缺少主线推进',
  missing_key_events: '缺少关键事件',
  missing_task_or_loop_progress: '缺少任务或伏笔推进',
  timeline_not_advanced: '时间线未推进',
  repeated_chapter_function: '章节功能重复',
  chapter_similarity: '章节相似度过高',
  arc_function_monotony: '阶段功能单一',
  arc_story_progress_stagnation: '阶段主线推进停滞',
  arc_missing_climax: '阶段高潮不足',
  loop_missing_title: '伏笔缺少标题',
  loop_missing_summary: '伏笔缺少摘要',
  loop_missing_due_end: '伏笔缺少最迟兑现章',
  loop_due_end_before_intro: '伏笔最迟兑现章早于引入章',
  loop_due_window_invalid: '伏笔兑现窗口非法',
  loop_overdue: '伏笔已逾期未回收',
  loop_still_overdue: '伏笔仍然逾期未回收',
  loop_stagnation: '伏笔长期无推进',
  loop_resolved_without_context: '伏笔回收缺少上下文',
  task_overdue: '任务已逾期未解决',
  task_still_overdue: '任务仍然逾期未解决',
  task_reopened_without_reset: '任务重开时未重置状态',
  relationship_break_without_reveal: '关系断裂缺少揭示',
  relationship_stagnation: '关系推进停滞',
  world_rule_conflict: '世界规则冲突',
}

/**
 * 修复提案 diff 里的字段名本质上是后端稳定键值。
 * 作者界面需要看的是“这次到底改了哪一项”，因此这里统一翻成中文标签，
 * 避免控制面继续把 purpose / due_end_chapter 这类内部字段直接暴露出来。
 */
const CREATIVE_DIFF_FIELD_LABELS: Record<string, string> = {
  title: '标题',
  chapter_function: '章节功能',
  story_progress: '主线推进',
  key_events: '关键事件',
  purpose: '阶段目的',
  main_progress: '主线推进',
  arc_climax: '阶段高潮',
  clear_chapter_numbers: '清空章节',
  status: '状态',
  depends_on_chapters: '承接章节',
  due_end_chapter: '最迟兑现章',
  due_start_chapter: '开始进入章',
  summary: '摘要',
}

export function formatLanguageLabel(language?: string | null): string {
  if (!language) return '未填写'
  return LANGUAGE_LABELS[language] ?? language
}

export function formatStylePresetLabel(stylePreset?: string | null): string {
  if (!stylePreset) return '未填写'
  return STYLE_PRESET_LABELS[stylePreset] ?? stylePreset
}

export function formatNamingPolicyLabel(policy?: string | null): string {
  if (!policy) return '未填写'
  return NAMING_POLICY_LABELS[policy] ?? policy
}

export function formatBlueprintStatusLabel(status?: string | null): string {
  if (!status) return '未初始化'
  return BLUEPRINT_STATUS_LABELS[status] ?? status
}

export function formatBlueprintStepLabel(step?: string | null): string {
  if (!step) return '创作意图'
  return BLUEPRINT_STEP_LABELS[step] ?? step
}

export function formatTaskStatusLabel(status?: string | null): string {
  if (!status) return '未标注'
  return TASK_STATUS_LABELS[status] ?? status
}

/**
 * 任务状态在编辑表单里允许用户输入中文，也允许保留旧格式中的英文机器值。
 * 这里统一把各种输入折叠为前端内部使用的规范状态。
 */
export function parseTaskStatusValue(status?: string | null): 'new' | 'in_progress' | 'resolved' | 'failed' {
  const normalized = (status ?? '').trim()
  if (!normalized) return 'new'
  return TASK_STATUS_VALUE_ALIASES[normalized] ?? 'new'
}

export function formatLoopStatusLabel(status?: string | null): string {
  if (!status) return '未标注'
  return LOOP_STATUS_LABELS[status] ?? status
}

/**
 * 伏笔状态编辑器同样允许中文输入和旧英文状态并存。
 * 这里统一折叠成章节草稿内部使用的规范值，避免表单保存后出现多套状态写法。
 */
export function parseLoopStatusValue(status?: string | null): 'open' | 'progressed' | 'resolved' {
  const normalized = (status ?? '').trim()
  if (!normalized) return 'open'
  return LOOP_STATUS_VALUE_ALIASES[normalized] ?? 'open'
}

/**
 * 连续性工作态里的伏笔如果缺少 title / summary，通常只剩下 loop-1 这类内部编号。
 * 对作者界面来说，这种编号没有信息量，因此这里把纯内部编号转成更自然的展示名。
 */
export function formatContinuityLoopLabel(loop: {
  loop_id?: string | null
  label?: string | null
  title?: string | null
  summary?: string | null
}): string {
  const candidates = [loop.label, loop.title, loop.summary]
    .map((item) => item?.trim() ?? '')
    .filter(Boolean)

  if (candidates.length > 0) {
    return candidates[0]!
  }

  const normalizedLoopId = (loop.loop_id ?? '').trim()
  const matchedIndex = /^loop-(\d+)$/i.exec(normalizedLoopId)
  if (matchedIndex) {
    return `伏笔 ${matchedIndex[1]}`
  }
  return normalizedLoopId || '未命名伏笔'
}

export function formatContinuityEventKindLabel(kind?: string | null): string {
  if (!kind) return '未标注事件'
  return CONTINUITY_EVENT_KIND_LABELS[kind] ?? kind
}

export function formatCreativeIssueStatusLabel(status?: string | null): string {
  if (!status) return '待处理'
  return CREATIVE_ISSUE_STATUS_LABELS[status] ?? status
}

export function formatCreativeRepairabilityLabel(repairability?: string | null): string {
  if (!repairability) return '待判断'
  return CREATIVE_REPAIRABILITY_LABELS[repairability] ?? repairability
}

export function formatCreativeSourceLayerLabel(sourceLayer?: string | null): string {
  if (!sourceLayer) return '未标注来源'
  return CREATIVE_SOURCE_LAYER_LABELS[sourceLayer] ?? sourceLayer
}

export function formatCreativeStrategyLabel(strategy?: string | null): string {
  if (!strategy) return '待判断'
  return CREATIVE_STRATEGY_LABELS[strategy] ?? strategy
}

export function formatCreativeRiskLabel(risk?: string | null): string {
  if (!risk) return '未标注风险'
  return CREATIVE_RISK_LABELS[risk] ?? risk
}

export function formatCreativeRunStatusLabel(status?: string | null): string {
  if (!status) return '未执行'
  return CREATIVE_RUN_STATUS_LABELS[status] ?? status
}

export function formatSceneStatusLabel(status?: string | null): string {
  if (!status) return '未标注'
  return SCENE_STATUS_LABELS[status] ?? status
}

export function formatReviewStatusLabel(status?: string | null): string {
  if (!status) return '未标注'
  return REVIEW_STATUS_LABELS[status] ?? status
}

export function formatGenerationEvalTaskTypeLabel(taskType?: string | null): string {
  if (!taskType) return '未标注任务'
  return GENERATION_EVAL_TASK_TYPE_LABELS[taskType] ?? taskType
}

export function formatGenerationEvalAcceptedByLabel(acceptedBy?: string | null): string {
  if (!acceptedBy) return '未标注采用方式'
  return GENERATION_EVAL_ACCEPTED_BY_LABELS[acceptedBy] ?? acceptedBy
}

export function formatCreativeIssueTypeLabel(issueType?: string | null): string {
  if (!issueType) return '未标注问题类型'
  return CREATIVE_ISSUE_TYPE_LABELS[issueType] ?? issueType
}

export function formatCreativeDiffFieldLabel(fieldName?: string | null): string {
  if (!fieldName) return '变更字段'
  return CREATIVE_DIFF_FIELD_LABELS[fieldName] ?? fieldName
}

/**
 * diff 预览里的 before / after 可能还是后端稳定枚举。
 * 这里按字段语义做最小必要的中文化：
 * - status 优先尝试任务状态，再尝试伏笔状态；
 * - 数组继续保持可扫读的中文分隔；
 * - 其他字段维持原值，避免前端擅自改写业务内容。
 */
export function formatCreativeDiffValue(fieldName: string | null | undefined, value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => formatCreativeDiffValue(fieldName, item)).join('；') || '空'
  }
  if (value === null || value === undefined || value === '') {
    return '空'
  }
  if (fieldName === 'status') {
    const raw = String(value)
    const taskLabel = TASK_STATUS_LABELS[raw]
    if (taskLabel) {
      return taskLabel
    }
    const loopLabel = LOOP_STATUS_LABELS[raw]
    if (loopLabel) {
      return loopLabel
    }
  }
  return String(value)
}
