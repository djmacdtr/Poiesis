/**
 * 路线总览条：
 * 这一层只负责展示路线级状态和最关键动作，不再把阶段卡、修复区、说明文案混在同一块里。
 */
import { cn } from '@/lib/utils'

export type RoadmapViewMode = 'stages' | 'repair'

interface RoadmapControlPanelProps {
  roadmapFeedback: string
  onRoadmapFeedbackChange: (value: string) => void
  totalChapterCount: number
  expandedArcCount: number
  totalArcCount: number
  fatalCount: number
  warningCount: number
  pendingRepairCount: number
  isLocked: boolean
  canGenerateStoryArcs: boolean
  canLockRoadmap: boolean
  isGeneratingStoryArcs: boolean
  isLockingRoadmap: boolean
  isPlanningRepairs: boolean
  isReverifying: boolean
  viewMode: RoadmapViewMode
  onViewModeChange: (mode: RoadmapViewMode) => void
  onGenerateStoryArcs: () => void
  onPlanRepairs: () => void
  onReverify: () => void
  onConfirmRoadmap: () => void
  lockReasons: string[]
}

function statToneClassName(kind: 'neutral' | 'danger' | 'warning' | 'repair'): string {
  if (kind === 'danger') return 'border-rose-200 bg-rose-50 text-rose-700'
  if (kind === 'warning') return 'border-amber-200 bg-amber-50 text-amber-700'
  if (kind === 'repair') return 'border-indigo-200 bg-indigo-50 text-indigo-700'
  return 'border-stone-200 bg-stone-50 text-stone-800'
}

export function RoadmapControlPanel({
  roadmapFeedback,
  onRoadmapFeedbackChange,
  totalChapterCount,
  expandedArcCount,
  totalArcCount,
  fatalCount,
  warningCount,
  pendingRepairCount,
  isLocked,
  canGenerateStoryArcs,
  canLockRoadmap,
  isGeneratingStoryArcs,
  isLockingRoadmap,
  isPlanningRepairs,
  isReverifying,
  viewMode,
  onViewModeChange,
  onGenerateStoryArcs,
  onPlanRepairs,
  onReverify,
  onConfirmRoadmap,
  lockReasons,
}: RoadmapControlPanelProps) {
  return (
    <section className="rounded-[24px] border border-stone-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-semibold text-stone-900">章节路线控制台</h3>
            <span
              className={cn(
                'rounded-full px-2.5 py-1 text-xs font-medium',
                isLocked ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700',
              )}
            >
              {isLocked ? '整书蓝图已锁定' : '章节路线待锁定'}
            </span>
          </div>
          <p className="mt-2 text-sm leading-6 text-stone-600">
            主区只保留当前最重要的路线任务。阶段生成、闭环修复和章节细修被拆成明确的工作流，不再互相争抢注意力。
          </p>
        </div>
        <div className="inline-flex rounded-2xl border border-stone-200 bg-stone-50 p-1">
          <button
            type="button"
            onClick={() => onViewModeChange('stages')}
            className={cn(
              'rounded-xl px-3 py-2 text-xs font-medium transition-colors',
              viewMode === 'stages' ? 'bg-white text-stone-900 shadow-sm' : 'text-stone-500 hover:text-stone-800',
            )}
          >
            阶段视图
          </button>
          <button
            type="button"
            onClick={() => onViewModeChange('repair')}
            className={cn(
              'rounded-xl px-3 py-2 text-xs font-medium transition-colors',
              viewMode === 'repair' ? 'bg-white text-stone-900 shadow-sm' : 'text-stone-500 hover:text-stone-800',
            )}
          >
            修复视图
          </button>
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <div className={cn('rounded-2xl border px-4 py-3', statToneClassName('neutral'))}>
          <p className="text-xs font-medium text-stone-500">整书规划</p>
          <p className="mt-2 text-lg font-semibold">{totalChapterCount} 章</p>
        </div>
        <div className={cn('rounded-2xl border px-4 py-3', statToneClassName('neutral'))}>
          <p className="text-xs font-medium text-stone-500">阶段完成</p>
          <p className="mt-2 text-lg font-semibold">
            {expandedArcCount}/{totalArcCount} 幕
          </p>
        </div>
        <div className={cn('rounded-2xl border px-4 py-3', statToneClassName('danger'))}>
          <p className="text-xs font-medium">严重问题</p>
          <p className="mt-2 text-lg font-semibold">{fatalCount}</p>
        </div>
        <div className={cn('rounded-2xl border px-4 py-3', statToneClassName('warning'))}>
          <p className="text-xs font-medium">提醒</p>
          <p className="mt-2 text-lg font-semibold">{warningCount}</p>
        </div>
        <div className={cn('rounded-2xl border px-4 py-3', statToneClassName('repair'))}>
          <p className="text-xs font-medium">待确认修复</p>
          <p className="mt-2 text-lg font-semibold">{pendingRepairCount}</p>
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-end">
        <div className="space-y-2">
          <label className="block text-xs font-medium text-stone-600">路线层微调要求</label>
          <textarea
            value={roadmapFeedback}
            onChange={(event) => onRoadmapFeedbackChange(event.target.value)}
            rows={2}
            placeholder="例如：前 3 章更猛，中段压抑感更强，阶段结尾形成明确反转。"
            className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
          />
        </div>
        <div className="flex flex-wrap gap-2 xl:justify-end">
          <button
            type="button"
            onClick={onGenerateStoryArcs}
            disabled={!canGenerateStoryArcs || isGeneratingStoryArcs || isLocked}
            className="rounded-xl bg-emerald-600 px-3.5 py-2.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {isGeneratingStoryArcs ? '生成中…' : totalArcCount > 0 ? '重生成阶段骨架' : '生成阶段骨架'}
          </button>
          <button
            type="button"
            onClick={onReverify}
            disabled={isReverifying}
            className="rounded-xl border border-stone-300 px-3.5 py-2.5 text-sm font-medium text-stone-700 hover:bg-stone-100 disabled:opacity-50"
          >
            {isReverifying ? '复验中…' : '重新复验'}
          </button>
          <button
            type="button"
            onClick={onPlanRepairs}
            disabled={isPlanningRepairs}
            className="rounded-xl border border-indigo-300 bg-indigo-50 px-3.5 py-2.5 text-sm font-medium text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
          >
            {isPlanningRepairs ? '生成中…' : '生成修复方案'}
          </button>
          <button
            type="button"
            onClick={onConfirmRoadmap}
            disabled={!canLockRoadmap}
            className="rounded-xl bg-stone-900 px-3.5 py-2.5 text-sm font-medium text-white hover:bg-stone-800 disabled:opacity-50"
          >
            {isLockingRoadmap ? '锁定中…' : isLocked ? '整书蓝图已锁定' : '锁定整书蓝图'}
          </button>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3 text-sm text-stone-600">
        <p className="font-medium text-stone-800">
          {canLockRoadmap ? '当前路线已经达到锁定条件。' : '当前路线仍不建议锁定整书蓝图。'}
        </p>
        {!canLockRoadmap && lockReasons.length > 0 ? (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-xs">
            {lockReasons.slice(0, 4).map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        ) : null}
      </div>
    </section>
  )
}
