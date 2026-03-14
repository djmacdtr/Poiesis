/**
 * 生成评测面板：
 * 把 generation_evals 从“后端埋点”提升为工作台里的可读视图。
 *
 * 这一层的职责不是替代问题队列或执行结果，而是回答更长期的问题：
 * 1. 最近的生成/修复到底有没有真的减少问题；
 * 2. 哪类任务最容易“执行成功但问题没解掉”；
 * 3. 当前模型/提示词版本的胜率是否在变好。
 */
import { useState } from 'react'
import type { GenerationEvalRecord } from '@/types'
import {
  formatCreativeIssueTypeLabel,
  formatCreativeSourceLayerLabel,
  formatExecutionReadinessLabel,
  formatGenerationEvalAcceptedByLabel,
  formatGenerationEvalTaskTypeLabel,
  formatJudgeModeLabel,
} from '@/lib/display-labels'

interface GenerationEvalBoardProps {
  items: GenerationEvalRecord[]
}

type EvalTaskFilter = 'all' | GenerationEvalRecord['task_type']
type EvalTimeWindow = 'all' | '7d' | '30d' | '90d'

function sumJudgeScores(scores: Array<{ score: number }>): number {
  return scores.reduce((total, item) => total + item.score, 0)
}

function formatTimestamp(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value || '未记录'
  }
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function GenerationEvalBoard({ items }: GenerationEvalBoardProps) {
  /**
   * 评测面板默认先看全量，但允许作者快速收窄到某一种任务类型。
   * 这样我们既能看整体趋势，也能快速回答“单章重写到底有没有变好”。
   */
  const [taskFilter, setTaskFilter] = useState<EvalTaskFilter>('all')
  const [timeWindow, setTimeWindow] = useState<EvalTimeWindow>('all')
  const [modelFilter, setModelFilter] = useState<string>('all')
  const [promptFilter, setPromptFilter] = useState<string>('all')
  const now = Date.now()
  const modelOptions = Array.from(new Set(items.map((item) => item.source_model.trim()).filter(Boolean))).sort()
  const promptOptions = Array.from(new Set(items.map((item) => item.prompt_version.trim()).filter(Boolean))).sort()

  /**
   * 筛选顺序固定为“时间窗口 -> 任务类型 -> 模型 -> 提示词版本”：
   * - 先按时间收窄，避免历史评测把最近趋势冲淡；
   * - 再按任务、模型、提示词逐层细分，方便定位到底是哪一环出了问题。
   */
  const filteredItems = items.filter((item) => {
    if (timeWindow !== 'all') {
      const createdAt = new Date(item.created_at).getTime()
      const windowDays = timeWindow === '7d' ? 7 : timeWindow === '30d' ? 30 : 90
      if (!Number.isNaN(createdAt) && now - createdAt > windowDays * 24 * 60 * 60 * 1000) {
        return false
      }
    }
    if (taskFilter !== 'all' && item.task_type !== taskFilter) {
      return false
    }
    if (modelFilter !== 'all' && item.source_model !== modelFilter) {
      return false
    }
    if (promptFilter !== 'all' && item.prompt_version !== promptFilter) {
      return false
    }
    return true
  })
  const totalCount = filteredItems.length
  const cleanPassCount = filteredItems.filter((item) => item.residual_issue_count === 0).length
  const avgResolved =
    totalCount > 0
      ? filteredItems.reduce((total, item) => total + item.resolved_issue_count, 0) / totalCount
      : 0
  const avgIntroduced =
    totalCount > 0
      ? filteredItems.reduce((total, item) => total + item.introduced_issue_count, 0) / totalCount
      : 0

  const taskGroups = Object.values(
    items.reduce<Record<string, { taskType: string; count: number; cleanPassCount: number }>>((acc, item) => {
      const current = acc[item.task_type] ?? {
        taskType: item.task_type,
        count: 0,
        cleanPassCount: 0,
      }
      current.count += 1
      if (item.residual_issue_count === 0) {
        current.cleanPassCount += 1
      }
      acc[item.task_type] = current
      return acc
    }, {}),
  ).sort((left, right) => right.count - left.count)

  const issueTypeGroups = Object.values(
    filteredItems.reduce<
      Record<
        string,
        {
          issueType: string
          count: number
          cleanPassCount: number
          residualCount: number
          introducedCount: number
        }
      >
    >((acc, item) => {
      const issueTypes = item.before_issue_types.length > 0 ? item.before_issue_types : item.after_issue_types
      for (const issueType of issueTypes) {
        const current = acc[issueType] ?? {
          issueType,
          count: 0,
          cleanPassCount: 0,
          residualCount: 0,
          introducedCount: 0,
        }
        current.count += 1
        if (item.residual_issue_count === 0) {
          current.cleanPassCount += 1
        }
        current.residualCount += item.residual_issue_count
        current.introducedCount += item.introduced_issue_count
        acc[issueType] = current
      }
      return acc
    }, {}),
  ).sort((left, right) => right.count - left.count)

  const recentItems = [...filteredItems]
    .sort((left, right) => right.created_at.localeCompare(left.created_at))
    .slice(0, 8)
  const filterOptions: Array<{ key: EvalTaskFilter; label: string; count: number }> = [
    { key: 'all', label: '全部任务', count: items.length },
    ...taskGroups.map((group) => ({
      key: group.taskType as EvalTaskFilter,
      label: formatGenerationEvalTaskTypeLabel(group.taskType),
      count: group.count,
    })),
  ]

  return (
    <section className="space-y-4 rounded-[28px] border border-stone-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h4 className="text-base font-semibold text-stone-900">生成评测面板</h4>
          <p className="mt-1 text-sm leading-6 text-stone-600">
            这里汇总最近的生成、重写与修复评测记录。它不直接决定当前要点哪张问题卡，而是帮助我们判断“哪类策略真的有效、哪类只是执行了但没修好”。
          </p>
        </div>
        <span className="rounded-full bg-sky-50 px-3 py-1 text-xs font-medium text-sky-700">
          最近 {recentItems.length} 条
        </span>
      </div>

      <div className="flex flex-wrap gap-2">
        {filterOptions.map((option) => (
          <button
            key={option.key}
            type="button"
            onClick={() => setTaskFilter(option.key)}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
              taskFilter === option.key
                ? 'border-stone-900 bg-stone-900 text-white'
                : 'border-stone-200 bg-white text-stone-600 hover:border-stone-300'
            }`}
          >
            {option.label} · {option.count}
          </button>
        ))}
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <label className="rounded-2xl border border-stone-200 bg-stone-50 px-3 py-3 text-xs text-stone-600">
          <span className="mb-2 block font-medium text-stone-700">时间窗口</span>
          <select
            value={timeWindow}
            onChange={(event) => setTimeWindow(event.target.value as EvalTimeWindow)}
            className="w-full rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm text-stone-700"
          >
            <option value="all">全部时间</option>
            <option value="7d">最近 7 天</option>
            <option value="30d">最近 30 天</option>
            <option value="90d">最近 90 天</option>
          </select>
        </label>
        <label className="rounded-2xl border border-stone-200 bg-stone-50 px-3 py-3 text-xs text-stone-600">
          <span className="mb-2 block font-medium text-stone-700">模型</span>
          <select
            value={modelFilter}
            onChange={(event) => setModelFilter(event.target.value)}
            className="w-full rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm text-stone-700"
          >
            <option value="all">全部模型</option>
            {modelOptions.map((modelName) => (
              <option key={modelName} value={modelName}>
                {modelName}
              </option>
            ))}
          </select>
        </label>
        <label className="rounded-2xl border border-stone-200 bg-stone-50 px-3 py-3 text-xs text-stone-600">
          <span className="mb-2 block font-medium text-stone-700">提示词版本</span>
          <select
            value={promptFilter}
            onChange={(event) => setPromptFilter(event.target.value)}
            className="w-full rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm text-stone-700"
          >
            <option value="all">全部提示词</option>
            {promptOptions.map((promptVersion) => (
              <option key={promptVersion} value={promptVersion}>
                {promptVersion}
              </option>
            ))}
          </select>
        </label>
      </div>

      {items.length > 0 ? (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3">
              <p className="text-xs font-medium text-stone-500">当前筛选评测数</p>
              <p className="mt-2 text-lg font-semibold text-stone-900">{totalCount}</p>
            </div>
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3">
              <p className="text-xs font-medium text-emerald-600">完全清除率</p>
              <p className="mt-2 text-lg font-semibold text-emerald-800">
                {totalCount > 0 ? `${Math.round((cleanPassCount / totalCount) * 100)}%` : '0%'}
              </p>
            </div>
            <div className="rounded-2xl border border-indigo-200 bg-indigo-50 px-4 py-3">
              <p className="text-xs font-medium text-indigo-600">平均清除问题</p>
              <p className="mt-2 text-lg font-semibold text-indigo-800">{avgResolved.toFixed(1)} 项</p>
            </div>
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
              <p className="text-xs font-medium text-amber-600">平均新增问题</p>
              <p className="mt-2 text-lg font-semibold text-amber-800">{avgIntroduced.toFixed(1)} 项</p>
            </div>
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
            <section className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
              <h5 className="text-sm font-semibold text-stone-900">按任务类型统计</h5>
              <div className="mt-3 space-y-2">
                {taskGroups.map((group) => (
                  <div key={group.taskType} className="rounded-xl bg-white px-3 py-3 text-sm text-stone-700">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-medium text-stone-900">{formatGenerationEvalTaskTypeLabel(group.taskType)}</p>
                      <span className="text-xs text-stone-500">{group.count} 次</span>
                    </div>
                    <p className="mt-1 text-xs text-stone-500">
                      完全清除率：
                      {group.count > 0 ? ` ${Math.round((group.cleanPassCount / group.count) * 100)}%` : ' 0%'}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            <div className="space-y-4">
              <section className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <h5 className="text-sm font-semibold text-stone-900">按问题类型统计</h5>
                <div className="mt-3 space-y-2">
                  {issueTypeGroups.length > 0 ? (
                    issueTypeGroups.slice(0, 8).map((group) => (
                      <div key={group.issueType} className="rounded-xl bg-white px-3 py-3 text-sm text-stone-700">
                        <div className="flex items-center justify-between gap-3">
                          <p className="font-medium text-stone-900">{formatCreativeIssueTypeLabel(group.issueType)}</p>
                          <span className="text-xs text-stone-500">{group.count} 次</span>
                        </div>
                        <div className="mt-2 flex flex-wrap gap-3 text-xs text-stone-500">
                          <span>
                            完全清除率：
                            {group.count > 0 ? ` ${Math.round((group.cleanPassCount / group.count) * 100)}%` : ' 0%'}
                          </span>
                          <span>累计残留：{group.residualCount}</span>
                          <span>累计新增：{group.introducedCount}</span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-xl bg-white px-3 py-4 text-sm text-stone-500">
                      当前筛选条件下还没有可统计的问题类型。
                    </div>
                  )}
                </div>
              </section>

              <section className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <h5 className="text-sm font-semibold text-stone-900">最近评测记录</h5>
                <div className="mt-3 space-y-3">
                  {recentItems.map((item) => (
                    <div key={item.eval_id} className="rounded-2xl bg-white px-4 py-4 text-sm text-stone-700">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="font-medium text-stone-900">
                            {formatGenerationEvalTaskTypeLabel(item.task_type)} · {formatCreativeSourceLayerLabel(item.layer)}
                          </p>
                          <p className="mt-1 text-xs text-stone-500">
                            {formatTimestamp(item.created_at)} · {item.source_model || '未记录模型'} · {item.prompt_version || '未记录提示词'}
                          </p>
                        </div>
                        <span className="rounded-full bg-stone-100 px-3 py-1 text-xs font-medium text-stone-700">
                          {formatGenerationEvalAcceptedByLabel(item.accepted_by)}
                        </span>
                      </div>
                      <div className="mt-3 grid gap-2 md:grid-cols-4">
                        <div className="rounded-xl bg-stone-50 px-3 py-2 text-xs text-stone-600">
                          候选数：{item.candidate_count}
                        </div>
                        <div className="rounded-xl bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
                          已清除：{item.resolved_issue_count}
                        </div>
                        <div className="rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700">
                          残留：{item.residual_issue_count}
                        </div>
                        <div className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">
                          新增：{item.introduced_issue_count}
                        </div>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2 text-xs text-stone-500">
                        <span>
                          评审：{formatJudgeModeLabel(String(item.context_payload.judge_mode ?? '').trim() || 'none')}
                        </span>
                        <span>
                          执行状态：
                          {formatExecutionReadinessLabel(String(item.context_payload.execution_readiness ?? '').trim() || 'executable')}
                        </span>
                      </div>
                      {item.after_issue_types.length > 0 ? (
                        <p className="mt-3 text-xs leading-5 text-stone-600">
                          复验后问题：{item.after_issue_types.map((issueType) => formatCreativeIssueTypeLabel(issueType)).join('、')}
                        </p>
                      ) : (
                        <p className="mt-3 text-xs leading-5 text-emerald-700">复验后没有残留问题。</p>
                      )}
                      {item.judge_scores.length > 0 ? (
                        <p className="mt-2 text-xs leading-5 text-stone-500">
                          Judge 综合分：{sumJudgeScores(item.judge_scores).toFixed(1)}
                        </p>
                      ) : null}
                    </div>
                  ))}
                </div>
              </section>
            </div>
          </div>
        </>
      ) : (
        <div className="rounded-2xl border border-dashed border-stone-300 bg-stone-50 px-4 py-8 text-sm text-stone-500">
          当前还没有生成评测记录。等你开始生成章节、重写单章或执行修复提案后，这里会逐步沉淀出“哪类策略最有效”的真实数据。
        </div>
      )}
    </section>
  )
}
