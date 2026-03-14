/**
 * 阶段工作台：
 * 把当前可行动阶段、后续阻塞阶段、已完成阶段明确分组，
 * 避免所有阶段在同一层级平铺后让作者失去“现在先做哪一幕”的焦点。
 */
import type { StoryArcPlan } from '@/types'
import { cn } from '@/lib/utils'

interface ArcIssueStat {
  arcNumber: number
  fatalCount: number
  warningCount: number
}

interface RoadmapArcBoardProps {
  currentArc: StoryArcPlan | null
  blockedArcs: StoryArcPlan[]
  completedArcs: StoryArcPlan[]
  activeArcNumber: number | null
  issueStats: ArcIssueStat[]
  feedbackByArcNumber: Record<number, string>
  pendingArcNumber: number | null
  isExpanding: boolean
  isRegenerating: boolean
  onToggleArc: (arcNumber: number) => void
  onExpandArc: (arcNumber: number) => void
  onRegenerateArc: (arcNumber: number) => void
  onArcFeedbackChange: (arcNumber: number, value: string) => void
  onFocusArc: (arcNumber: number) => void
}

function issueTone(fatalCount: number, warningCount: number, active: boolean): string {
  if (fatalCount > 0) return active ? 'border-rose-300 bg-rose-50/80 ring-2 ring-rose-100' : 'border-rose-200 bg-rose-50/50'
  if (warningCount > 0) return active ? 'border-amber-300 bg-amber-50/80 ring-2 ring-amber-100' : 'border-amber-200 bg-amber-50/50'
  return active ? 'border-emerald-300 bg-white ring-2 ring-emerald-100' : 'border-stone-200 bg-stone-50/80'
}

function findIssueStat(issueStats: ArcIssueStat[], arcNumber: number): ArcIssueStat {
  return issueStats.find((item) => item.arcNumber === arcNumber) ?? { arcNumber, fatalCount: 0, warningCount: 0 }
}

function renderMetaChip(label: string) {
  return <span className="rounded-full bg-white px-2 py-1 text-xs text-stone-600">{label}</span>
}

export function RoadmapArcBoard({
  currentArc,
  blockedArcs,
  completedArcs,
  activeArcNumber,
  issueStats,
  feedbackByArcNumber,
  pendingArcNumber,
  isExpanding,
  isRegenerating,
  onToggleArc,
  onExpandArc,
  onRegenerateArc,
  onArcFeedbackChange,
  onFocusArc,
}: RoadmapArcBoardProps) {
  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-stone-900">阶段工作台</h4>
          <p className="mt-1 text-xs text-stone-500">只突出当前最早可行动阶段。后续阶段保持可见，但默认退到阻塞摘要层级。</p>
        </div>
      </div>

      {currentArc ? (
        (() => {
          const { fatalCount, warningCount } = findIssueStat(issueStats, currentArc.arc_number)
          const isPending = pendingArcNumber === currentArc.arc_number
          const isActive = activeArcNumber === currentArc.arc_number
          return (
            <article className={cn('rounded-[24px] border p-5 shadow-sm', issueTone(fatalCount, warningCount, true))}>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-emerald-600 px-2.5 py-1 text-xs font-semibold text-white">当前阶段</span>
                    <h5 className="text-lg font-semibold text-stone-900">
                      第 {currentArc.arc_number} 幕 · {currentArc.title}
                    </h5>
                  </div>
                  <p className="mt-2 max-w-3xl text-sm leading-6 text-stone-600">
                    {currentArc.purpose || '当前阶段还没有填写目标说明。'}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {renderMetaChip(`第 ${currentArc.start_chapter}-${currentArc.end_chapter} 章`)}
                  {renderMetaChip(`已生成 ${currentArc.generated_chapter_count}/${currentArc.chapter_target_count} 章`)}
                  {renderMetaChip(`严重问题 ${fatalCount}`)}
                  {renderMetaChip(`提醒 ${warningCount}`)}
                </div>
              </div>

              <div className="mt-4 grid gap-3 lg:grid-cols-3">
                <div className="rounded-2xl border border-stone-200 bg-white px-4 py-3">
                  <p className="text-xs font-medium text-stone-500">主线推进</p>
                  <p className="mt-2 text-sm leading-6 text-stone-700">
                    {currentArc.main_progress.length > 0 ? currentArc.main_progress.join('；') : '未填写'}
                  </p>
                </div>
                <div className="rounded-2xl border border-stone-200 bg-white px-4 py-3">
                  <p className="text-xs font-medium text-stone-500">关系推进</p>
                  <p className="mt-2 text-sm leading-6 text-stone-700">
                    {currentArc.relationship_progress.length > 0 ? currentArc.relationship_progress.join('；') : '未填写'}
                  </p>
                </div>
                <div className="rounded-2xl border border-stone-200 bg-white px-4 py-3">
                  <p className="text-xs font-medium text-stone-500">阶段高潮</p>
                  <p className="mt-2 text-sm leading-6 text-stone-700">{currentArc.arc_climax || '未填写'}</p>
                </div>
              </div>

              <div className="mt-4 space-y-2">
                <label className="block text-xs font-medium text-stone-600">编辑阶段说明 / 重生成要求</label>
                <textarea
                  value={feedbackByArcNumber[currentArc.arc_number] ?? ''}
                  onChange={(event) => onArcFeedbackChange(currentArc.arc_number, event.target.value)}
                  rows={2}
                  placeholder="例如：让本阶段更早出现局势升级，并在结尾形成明确反转。"
                  className="w-full rounded-xl border border-stone-300 bg-white px-3 py-2.5 text-sm"
                />
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => onExpandArc(currentArc.arc_number)}
                  disabled={
                    isPending ||
                    isExpanding ||
                    !currentArc.can_generate_next_chapter ||
                    currentArc.status === 'completed' ||
                    currentArc.status === 'confirmed'
                  }
                  className="rounded-xl bg-emerald-600 px-3.5 py-2.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                >
                  {isPending
                    ? '生成中…'
                    : currentArc.status === 'completed' || currentArc.status === 'confirmed'
                      ? '本阶段已完成'
                      : currentArc.next_chapter_number
                        ? `生成第 ${currentArc.next_chapter_number} 章`
                        : '生成下一章'}
                </button>
                <button
                  type="button"
                  onClick={() => onToggleArc(currentArc.arc_number)}
                  disabled={!currentArc.has_chapters}
                  className="rounded-xl border border-stone-300 px-3.5 py-2.5 text-sm font-medium text-stone-700 hover:bg-stone-100 disabled:opacity-50"
                >
                  {!currentArc.has_chapters ? '尚未生成章节' : isActive ? '收起本阶段章节' : '查看本阶段章节'}
                </button>
                <button
                  type="button"
                  onClick={() => onRegenerateArc(currentArc.arc_number)}
                  disabled={isPending || isRegenerating}
                  className="rounded-xl bg-amber-600 px-3.5 py-2.5 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
                >
                  {isPending ? '重生成中…' : '重生成本阶段骨架'}
                </button>
              </div>
            </article>
          )
        })()
      ) : (
        <div className="rounded-[24px] border border-dashed border-stone-300 bg-stone-50 px-5 py-6 text-sm text-stone-500">
          当前还没有可行动阶段。请先生成阶段骨架，或检查前序阶段是否已经完成。
        </div>
      )}

      {blockedArcs.length > 0 ? (
        <section className="rounded-[24px] border border-stone-200 bg-white p-4 shadow-sm">
          <h5 className="text-sm font-semibold text-stone-900">后续阻塞阶段</h5>
          <div className="mt-3 space-y-2">
            {blockedArcs.map((arc) => {
              const { fatalCount, warningCount } = findIssueStat(issueStats, arc.arc_number)
              return (
                <button
                  key={arc.arc_number}
                  type="button"
                  onClick={() => onFocusArc(arc.arc_number)}
                  className="flex w-full items-center justify-between gap-3 rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3 text-left hover:bg-white"
                >
                  <div>
                    <p className="text-sm font-semibold text-stone-900">
                      第 {arc.arc_number} 幕 · {arc.title}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-stone-500">
                      需先完成第 {arc.blocking_arc_number} 幕 · 第 {arc.start_chapter}-{arc.end_chapter} 章
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {renderMetaChip(`严重 ${fatalCount}`)}
                    {renderMetaChip(`提醒 ${warningCount}`)}
                  </div>
                </button>
              )
            })}
          </div>
        </section>
      ) : null}

      {completedArcs.length > 0 ? (
        <details className="rounded-[24px] border border-stone-200 bg-white p-4 shadow-sm">
          <summary className="cursor-pointer text-sm font-semibold text-stone-900">历史阶段</summary>
          <div className="mt-3 space-y-2">
            {completedArcs.map((arc) => (
              <button
                key={arc.arc_number}
                type="button"
                onClick={() => onFocusArc(arc.arc_number)}
                className="flex w-full items-center justify-between gap-3 rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3 text-left hover:bg-white"
              >
                <div>
                  <p className="text-sm font-semibold text-stone-900">
                    第 {arc.arc_number} 幕 · {arc.title}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-stone-500">
                    已完成 {arc.generated_chapter_count}/{arc.chapter_target_count} 章
                  </p>
                </div>
                <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-700">
                  已完成
                </span>
              </button>
            ))}
          </div>
        </details>
      ) : null}
    </section>
  )
}
