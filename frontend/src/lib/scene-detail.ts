/**
 * Scene 详情页展示辅助函数。
 * 这一层负责把后端结构化数据转换成更适合页面展示的中文视图模型。
 */
import type {
  PublishBlockers,
  ReviewEvent,
  SceneChangeSet,
  SceneIssue,
  ScenePatchRecord,
} from '@/types'

export const sceneStatusLabel: Record<string, string> = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  needs_review: '待审阅',
  failed: '失败',
  approved: '已通过',
}

export const reviewActionLabel: Record<string, string> = {
  approve: '人工通过',
  retry: '重新生成',
  patch: '人工修补',
  rewrite: '重写',
  reject: '驳回',
}

export const reviewEventStatusLabel: Record<string, string> = {
  succeeded: '执行成功',
  failed: '执行失败',
}

export const issueSeverityLabel: Record<string, string> = {
  fatal: '严重问题',
  warning: '提醒',
  info: '信息',
}

export const issueSeverityTone: Record<string, string> = {
  fatal: 'border-red-200 bg-red-50 text-red-700',
  warning: 'border-amber-200 bg-amber-50 text-amber-700',
  info: 'border-sky-200 bg-sky-50 text-sky-700',
}

export interface IssueGroup {
  severity: 'fatal' | 'warning' | 'info'
  label: string
  items: SceneIssue[]
}

export interface ChangeSection {
  key: string
  title: string
  items: Array<Record<string, unknown>>
  emptyText: string
}

export interface ReviewTimelineItem {
  id: number
  title: string
  statusLabel: string
  statusTone: string
  operator: string
  timestamp: string
  summary: string
}

export function groupIssues(issues: SceneIssue[]): IssueGroup[] {
  const order: Array<'fatal' | 'warning' | 'info'> = ['fatal', 'warning', 'info']
  return order
    .map((severity) => ({
      severity,
      label: issueSeverityLabel[severity],
      items: issues.filter((item) => item.severity === severity),
    }))
    .filter((group) => group.items.length > 0)
}

export function buildChangeSections(changeset: SceneChangeSet): ChangeSection[] {
  return [
    {
      key: 'characters',
      title: '角色变化',
      items: changeset.characters,
      emptyText: '当前场景没有提取到角色变化。',
    },
    {
      key: 'world_rules',
      title: '世界规则变化',
      items: changeset.world_rules,
      emptyText: '当前场景没有引入新的世界规则变化。',
    },
    {
      key: 'timeline_events',
      title: '时间线事件',
      items: changeset.timeline_events,
      emptyText: '当前场景没有提取到时间线事件。',
    },
    {
      key: 'loop_updates',
      title: '剧情线索推进',
      items: changeset.loop_updates,
      emptyText: '当前场景没有推进剧情线索。',
    },
    {
      key: 'uncertain_claims',
      title: '不确定事实',
      items: changeset.uncertain_claims,
      emptyText: '当前场景没有标记不确定事实。',
    },
  ]
}

export function buildReviewTimeline(events: ReviewEvent[]): ReviewTimelineItem[] {
  return events.map((event) => {
    const resultSummary = String(event.result_payload?.result_summary || event.result_payload?.review_reason || '')
    return {
      id: event.id,
      title: reviewActionLabel[event.action] ?? event.action,
      statusLabel: reviewEventStatusLabel[event.status] ?? event.status,
      statusTone: event.status === 'failed' ? 'bg-red-50 text-red-700' : 'bg-emerald-50 text-emerald-700',
      operator: event.operator || '系统',
      timestamp: event.created_at,
      summary: resultSummary || '本次动作没有附加结果摘要。',
    }
  })
}

export function summarizePatchResult(patch: ScenePatchRecord): string {
  if (patch.applied_successfully) return '修补后已通过校验。'
  if (patch.verifier_issues.length === 0) return '修补已记录，但没有新的校验结果。'
  return `修补后仍有 ${patch.verifier_issues.length} 个问题。`
}

export function describePublishState(publish: PublishBlockers): string {
  if (publish.can_publish) return '当前章节已满足发布条件。'
  if (publish.blockers.length > 0) return publish.blockers.join('；')
  return '当前章节尚未满足发布条件。'
}
