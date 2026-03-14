/**
 * 闭环修复控制面：
 * 把问题、提案、执行结果拆成三列顺序信息流，让作者先识别问题，再看系统建议，最后看执行结果。
 */
import { Link } from 'react-router-dom'
import type { CreativeIssue, CreativeRepairProposal, CreativeRepairRun } from '@/types'
import {
  formatCreativeIssueStatusLabel,
  formatCreativeRepairabilityLabel,
  formatCreativeRiskLabel,
  formatCreativeRunStatusLabel,
  formatCreativeSourceLayerLabel,
  formatCreativeStrategyLabel,
} from '@/lib/display-labels'

export type CreativeIssueSourceFilter = 'all' | 'roadmap' | 'scene' | 'review' | 'canon'

interface CreativeRepairBoardProps {
  issues: CreativeIssue[]
  proposals: CreativeRepairProposal[]
  runs: CreativeRepairRun[]
  roadmapDraftDirty: boolean
  isPlanningRepairs: boolean
  isApplyingProposal: boolean
  isRollingBackRun: boolean
  onPlanAll: () => void
  onPlanIssue: (issueId: string) => void
  onApplyProposal: (proposalId: string) => void
  onRollbackRun: (runId: string) => void
  onFocusChapter: (chapterNumber: number, arcNumber: number | null) => void
  onFocusArc: (arcNumber: number) => void
  onSelectIssue: (issueId: string) => void
  onSelectProposal: (proposalId: string) => void
  onSelectRun: (runId: string) => void
  selectedIssueId: string | null
  selectedProposalId: string | null
  selectedRunId: string | null
  sourceFilter: CreativeIssueSourceFilter
  onSourceFilterChange: (filter: CreativeIssueSourceFilter) => void
  reviewQueueHref: string
}

function issueCardTone(issue: CreativeIssue): string {
  return issue.severity === 'fatal'
    ? 'border-rose-200 bg-rose-50 text-rose-700'
    : 'border-amber-200 bg-amber-50 text-amber-700'
}

function previewValue(value: unknown): string {
  if (Array.isArray(value)) return value.join('；') || '空'
  if (value === null || value === undefined || value === '') return '空'
  return String(value)
}

function emptyIssueHint(sourceFilter: CreativeIssueSourceFilter): string {
  if (sourceFilter === 'scene') {
    return 'scene verifier 原始问题目前还没有稳定的持久化真源，因此这一层暂时只保留接入预留。'
  }
  if (sourceFilter === 'canon') {
    return '设定同步代理尚未启用。当前只保留来源层入口，不生成伪造问题或执行动作。'
  }
  if (sourceFilter === 'review') {
    return '当前作品没有待处理的审阅项。'
  }
  return '当前筛选条件下没有待处理问题。'
}

export function CreativeRepairBoard({
  issues,
  proposals,
  runs,
  roadmapDraftDirty,
  isPlanningRepairs,
  isApplyingProposal,
  isRollingBackRun,
  onPlanAll,
  onPlanIssue,
  onApplyProposal,
  onRollbackRun,
  onFocusChapter,
  onFocusArc,
  onSelectIssue,
  onSelectProposal,
  onSelectRun,
  selectedIssueId,
  selectedProposalId,
  selectedRunId,
  sourceFilter,
  onSourceFilterChange,
  reviewQueueHref,
}: CreativeRepairBoardProps) {
  /**
   * 第二阶段的 scene / review / canon 目前只接到“统一问题队列”这一步，
   * 还没有接入 apply / rollback。因此控制面需要先支持来源筛选，
   * 让作者区分“已可执行的路线问题”和“只读接入的其他层问题”。
   */
  const filteredIssues =
    sourceFilter === 'all' ? issues : issues.filter((item) => item.source_layer === sourceFilter)
  const visibleProposals = sourceFilter === 'all' || sourceFilter === 'roadmap' ? proposals : []
  const visibleRuns = sourceFilter === 'all' || sourceFilter === 'roadmap' ? runs : []
  const recentRuns = visibleRuns.slice(0, 1)
  const archivedRuns = visibleRuns.slice(1)
  const filterOptions: Array<{ key: CreativeIssueSourceFilter; label: string; count: number }> = [
    { key: 'all', label: '全部', count: issues.length },
    {
      key: 'roadmap',
      label: formatCreativeSourceLayerLabel('roadmap'),
      count: issues.filter((item) => item.source_layer === 'roadmap').length,
    },
    {
      key: 'scene',
      label: formatCreativeSourceLayerLabel('scene'),
      count: issues.filter((item) => item.source_layer === 'scene').length,
    },
    {
      key: 'review',
      label: formatCreativeSourceLayerLabel('review'),
      count: issues.filter((item) => item.source_layer === 'review').length,
    },
    {
      key: 'canon',
      label: formatCreativeSourceLayerLabel('canon'),
      count: issues.filter((item) => item.source_layer === 'canon').length,
    },
  ]

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-stone-900">闭环修复控制面</h4>
          <p className="mt-1 text-xs text-stone-500">问题、提案、执行结果被拆开后，作者可以更明确地判断“先修什么、怎么修、修完了没有”。</p>
        </div>
        <button
          type="button"
          onClick={onPlanAll}
          disabled={
            roadmapDraftDirty ||
            !['all', 'roadmap'].includes(sourceFilter) ||
            issues.every((item) => item.source_layer !== 'roadmap') ||
            isPlanningRepairs
          }
          className="rounded-xl bg-stone-900 px-3.5 py-2.5 text-sm font-medium text-white hover:bg-stone-800 disabled:opacity-50"
        >
          {isPlanningRepairs ? '生成中…' : '为当前问题生成修复方案'}
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {filterOptions.map((option) => (
          <button
            key={option.key}
            type="button"
            onClick={() => onSourceFilterChange(option.key)}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
              sourceFilter === option.key
                ? 'border-stone-900 bg-stone-900 text-white'
                : 'border-stone-200 bg-white text-stone-600 hover:border-stone-300'
            }`}
          >
            {option.label} · {option.count}
          </button>
        ))}
      </div>

      {roadmapDraftDirty ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          当前路线草稿仍有本地未确认修改。修复提案必须基于后端持久化状态生成，否则执行结果与页面草稿会发生分裂。
        </div>
      ) : null}

      {sourceFilter !== 'all' && sourceFilter !== 'roadmap' ? (
        <div className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
          当前筛选的是{formatCreativeSourceLayerLabel(sourceFilter)}。这一层已经接入统一问题队列，但暂未接入可执行修复，因此这里只提供只读排查入口。
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)_minmax(0,0.9fr)]">
        <section className="space-y-2">
          <h5 className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">问题队列</h5>
          {filteredIssues.length > 0 ? (
            filteredIssues.map((issue) => {
              const chapterNumber = Number(issue.target_ref.chapter_number ?? 0) || null
              const arcNumber = Number(issue.target_ref.arc_number ?? 0) || null
              return (
                <button
                  key={issue.issue_id}
                  type="button"
                  onClick={() => onSelectIssue(issue.issue_id)}
                  className={`w-full rounded-2xl border px-4 py-3 text-left text-sm transition-all ${issueCardTone(issue)} ${
                    selectedIssueId === issue.issue_id ? 'ring-2 ring-current/20' : ''
                  }`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{issue.severity === 'fatal' ? '严重问题' : '提醒'}</span>
                    <span className="rounded-full border border-current/30 px-2 py-0.5 text-[11px]">
                      {formatCreativeIssueStatusLabel(issue.status)}
                    </span>
                    <span className="rounded-full border border-current/30 px-2 py-0.5 text-[11px]">
                      {formatCreativeSourceLayerLabel(issue.source_layer)}
                    </span>
                    <span className="rounded-full border border-current/30 px-2 py-0.5 text-[11px]">
                      {formatCreativeRepairabilityLabel(issue.repairability)}
                    </span>
                  </div>
                  <p className="mt-2 leading-6">{issue.message}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {issue.suggested_strategy ? (
                      <span className="rounded-full bg-white px-2 py-1 text-[11px] text-stone-600">
                        {formatCreativeStrategyLabel(issue.suggested_strategy)}
                      </span>
                    ) : null}
                    {chapterNumber ? (
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation()
                          onFocusChapter(chapterNumber, arcNumber)
                        }}
                        className="rounded-full bg-white px-2 py-1 text-[11px] text-stone-600"
                      >
                        定位第 {chapterNumber} 章
                      </button>
                    ) : null}
                    {arcNumber ? (
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation()
                          onFocusArc(arcNumber)
                        }}
                        className="rounded-full bg-white px-2 py-1 text-[11px] text-stone-600"
                      >
                        查看第 {arcNumber} 幕
                      </button>
                    ) : null}
                    {issue.repairability !== 'manual' && issue.source_layer === 'roadmap' ? (
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation()
                          onPlanIssue(issue.issue_id)
                        }}
                        disabled={isPlanningRepairs}
                        className="rounded-full bg-white px-2 py-1 text-[11px] font-medium text-stone-800 disabled:opacity-50"
                      >
                        生成修复方案
                      </button>
                    ) : null}
                    {issue.source_layer === 'review' ? (
                      <>
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation()
                            onSelectIssue(issue.issue_id)
                          }}
                          className="rounded-full bg-white px-2 py-1 text-[11px] font-medium text-stone-800"
                        >
                          查看详情
                        </button>
                        <Link
                          to={reviewQueueHref}
                          onClick={(event) => event.stopPropagation()}
                          className="rounded-full bg-white px-2 py-1 text-[11px] font-medium text-stone-800"
                        >
                          前往审阅队列
                        </Link>
                      </>
                    ) : null}
                  </div>
                </button>
              )
            })
          ) : (
            <div className="rounded-2xl border border-dashed border-stone-300 bg-stone-50 px-4 py-6 text-sm text-stone-500">
              {emptyIssueHint(sourceFilter)}
            </div>
          )}
        </section>

        <section className="space-y-2">
          <h5 className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">修复提案</h5>
          {visibleProposals.length > 0 ? (
            visibleProposals.map((proposal) => (
              <button
                key={proposal.proposal_id}
                type="button"
                onClick={() => onSelectProposal(proposal.proposal_id)}
                className={`w-full rounded-2xl border border-stone-200 bg-white px-4 py-3 text-left text-sm transition-all ${
                  selectedProposalId === proposal.proposal_id ? 'ring-2 ring-indigo-100' : 'hover:border-stone-300'
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-medium text-stone-900">{proposal.summary}</p>
                    <div className="mt-1 flex flex-wrap gap-2 text-[11px] text-stone-500">
                      <span>{formatCreativeStrategyLabel(proposal.strategy_type)}</span>
                      <span>{formatCreativeRiskLabel(proposal.risk_level)}</span>
                      <span>{proposal.requires_llm ? '需要模型改写' : '结构补丁'}</span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation()
                      onApplyProposal(proposal.proposal_id)
                    }}
                    disabled={isApplyingProposal || proposal.status !== 'awaiting_approval'}
                    className="rounded-xl bg-emerald-600 px-3 py-2 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                  >
                    {isApplyingProposal ? '执行中…' : '接受并执行'}
                  </button>
                </div>
                {proposal.diff_preview.length > 0 ? (
                  <div className="mt-3 rounded-2xl bg-stone-50 p-3">
                    {proposal.diff_preview.slice(0, 3).map((item, index) => (
                      <div key={`${proposal.proposal_id}-${index}`} className="text-xs text-stone-600">
                        <span className="font-medium text-stone-800">{String(item.field_name ?? item.kind ?? '变更')}</span>
                        {'：'}
                        {previewValue(item.before)} → {previewValue(item.after)}
                      </div>
                    ))}
                  </div>
                ) : null}
              </button>
            ))
          ) : (
            <div className="rounded-2xl border border-dashed border-stone-300 bg-stone-50 px-4 py-6 text-sm text-stone-500">
              当前筛选层还没有修复提案。
            </div>
          )}
        </section>

        <section className="space-y-2">
          <h5 className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">执行结果</h5>
          {recentRuns.length > 0 ? (
            <>
              {recentRuns.map((run) => (
                <button
                  key={run.run_id}
                  type="button"
                  onClick={() => onSelectRun(run.run_id)}
                  className={`w-full rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3 text-left text-sm transition-all ${
                    selectedRunId === run.run_id ? 'ring-2 ring-stone-200' : 'hover:border-stone-300'
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-medium text-stone-900">{formatCreativeRunStatusLabel(run.status)}</p>
                      <p className="mt-1 text-xs text-stone-500">{run.logs[0] ?? '本次执行没有附加日志。'}</p>
                    </div>
                    {run.status === 'succeeded' ? (
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation()
                          onRollbackRun(run.run_id)
                        }}
                        disabled={isRollingBackRun}
                        className="rounded-xl border border-rose-300 px-3 py-2 text-xs text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                      >
                        {isRollingBackRun ? '回滚中…' : '回滚'}
                      </button>
                    ) : null}
                  </div>
                  {run.error_message ? <p className="mt-2 text-xs text-rose-600">{run.error_message}</p> : null}
                </button>
              ))}
              {archivedRuns.length > 0 ? (
                <details className="rounded-2xl border border-stone-200 bg-white p-3">
                  <summary className="cursor-pointer text-xs font-medium text-stone-600">展开历史执行记录</summary>
                  <div className="mt-3 space-y-2">
                    {archivedRuns.map((run) => (
                      <button
                        key={run.run_id}
                        type="button"
                        onClick={() => onSelectRun(run.run_id)}
                        className="w-full rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-left text-xs text-stone-600 hover:bg-white"
                      >
                        {formatCreativeRunStatusLabel(run.status)} · {run.logs[0] ?? '无附加日志'}
                      </button>
                    ))}
                  </div>
                </details>
              ) : null}
            </>
          ) : (
            <div className="rounded-2xl border border-dashed border-stone-300 bg-stone-50 px-4 py-6 text-sm text-stone-500">
              当前还没有执行结果。
            </div>
          )}
        </section>
      </div>
    </section>
  )
}
