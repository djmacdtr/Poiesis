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
