/**
 * 章节列表：
 * 当前阶段章节保持主列表展示，其他阶段章节下沉到历史分组，
 * 这样主区不会再同时平铺所有章节卡，作者也更容易把注意力放在当前阶段。
 */
import type { ChapterRoadmapItem, RoadmapValidationIssue, StoryArcPlan } from '@/types'
import { cn } from '@/lib/utils'

interface RoadmapChapterListProps {
  currentArc: StoryArcPlan | null
  currentArcChapters: ChapterRoadmapItem[]
  archivedArcChapters: Array<{
    arc: StoryArcPlan
    chapters: ChapterRoadmapItem[]
  }>
  selectedChapterNumber: number | null
  highlightedChapterNumber: number | null
  lastGeneratedChapterNumber: number | null
  activeArc: StoryArcPlan | null
  roadmapIssues: RoadmapValidationIssue[]
  pendingChapterNumber: number | null
  onSelectChapter: (chapterNumber: number) => void
  onRegenerateChapter: (arcNumber: number, chapterNumber: number) => void
}

function chapterIssueTone(chapterIssues: RoadmapValidationIssue[], selected: boolean): string {
  if (selected) return 'border-indigo-300 bg-white ring-2 ring-indigo-100'
  if (chapterIssues.some((issue) => issue.severity === 'fatal')) return 'border-rose-200 bg-rose-50/40'
  if (chapterIssues.length > 0) return 'border-amber-200 bg-amber-50/40'
  return 'border-stone-200 bg-stone-50/80'
}

function renderChapterCard(
  item: ChapterRoadmapItem,
  {
    chapterIssues,
    selectedChapterNumber,
    highlightedChapterNumber,
    lastGeneratedChapterNumber,
    activeArc,
    pendingChapterNumber,
    onSelectChapter,
    onRegenerateChapter,
  }: {
    chapterIssues: RoadmapValidationIssue[]
    selectedChapterNumber: number | null
    highlightedChapterNumber: number | null
    lastGeneratedChapterNumber: number | null
    activeArc: StoryArcPlan | null
    pendingChapterNumber: number | null
    onSelectChapter: (chapterNumber: number) => void
    onRegenerateChapter: (arcNumber: number, chapterNumber: number) => void
  },
) {
  const isSelected = selectedChapterNumber === item.chapter_number
  const canRegenerate = lastGeneratedChapterNumber !== null && item.chapter_number === lastGeneratedChapterNumber && activeArc
  return (
    <article
      key={item.chapter_number}
      className={cn(
        'rounded-2xl border p-4 transition-all',
        chapterIssueTone(chapterIssues, isSelected),
        highlightedChapterNumber === item.chapter_number ? 'ring-2 ring-sky-200' : '',
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h5 className="text-sm font-semibold text-stone-900">
            第 {item.chapter_number} 章 · {item.title || '未命名章节'}
          </h5>
          <p className="mt-1 text-xs text-stone-500">
            {item.story_stage || '未标注阶段'} · {item.timeline_anchor || '未标注时间锚点'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {chapterIssues.length > 0 ? (
            <span
              className={cn(
                'rounded-full px-2 py-1 font-medium',
                chapterIssues.some((issue) => issue.severity === 'fatal')
                  ? 'bg-rose-100 text-rose-700'
                  : 'bg-amber-100 text-amber-700',
              )}
            >
              {chapterIssues.some((issue) => issue.severity === 'fatal') ? '需重做' : '需优化'}
            </span>
          ) : null}
          <span className="rounded-full bg-white px-2 py-1 text-stone-600">伏笔 {item.planned_loops.length}</span>
        </div>
      </div>

      <p className="mt-3 text-sm leading-6 text-stone-700">{item.story_progress || item.goal || '当前还没有填写章节摘要。'}</p>

      <div className="mt-3 grid gap-2 text-xs text-stone-600 sm:grid-cols-2">
        <div className="rounded-xl bg-white px-3 py-2">关键事件：{item.key_events.join('；') || '未指定'}</div>
        <div className="rounded-xl bg-white px-3 py-2">人物推进：{item.character_progress.join('；') || '未指定'}</div>
        <div className="rounded-xl bg-white px-3 py-2">关系推进：{item.relationship_progress.join('；') || '未指定'}</div>
        <div className="rounded-xl bg-white px-3 py-2">世界更新：{item.world_updates.join('；') || '未指定'}</div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onSelectChapter(item.chapter_number)}
          className="rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm text-stone-700 hover:bg-stone-100"
        >
          {isSelected ? '正在右栏编辑' : '在右栏编辑'}
        </button>
        {canRegenerate ? (
          <button
            type="button"
            onClick={() => onRegenerateChapter(activeArc.arc_number, item.chapter_number)}
            disabled={pendingChapterNumber === item.chapter_number}
            className="rounded-xl bg-amber-600 px-3 py-2 text-sm text-white hover:bg-amber-700 disabled:opacity-50"
          >
            {pendingChapterNumber === item.chapter_number ? '重生成中…' : '重生成本章'}
          </button>
        ) : null}
      </div>
    </article>
  )
}

export function RoadmapChapterList({
  currentArc,
  currentArcChapters,
  archivedArcChapters,
  selectedChapterNumber,
  highlightedChapterNumber,
  lastGeneratedChapterNumber,
  activeArc,
  roadmapIssues,
  pendingChapterNumber,
  onSelectChapter,
  onRegenerateChapter,
}: RoadmapChapterListProps) {
  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-stone-900">章节列表</h4>
          <p className="mt-1 text-xs text-stone-500">当前阶段章节保留在主区，历史阶段章节下沉到折叠组，避免整页被长列表淹没。</p>
        </div>
        {currentArc ? (
          <span className="rounded-full bg-indigo-100 px-2.5 py-1 text-xs font-medium text-indigo-700">
            当前聚焦：第 {currentArc.arc_number} 幕
          </span>
        ) : null}
      </div>

      {currentArcChapters.length > 0 ? (
        <div className="grid gap-3 xl:grid-cols-2">
          {currentArcChapters.map((item) =>
            renderChapterCard(item, {
              chapterIssues: roadmapIssues.filter((issue) => issue.chapter_number === item.chapter_number),
              selectedChapterNumber,
              highlightedChapterNumber,
              lastGeneratedChapterNumber,
              activeArc,
              pendingChapterNumber,
              onSelectChapter,
              onRegenerateChapter,
            }),
          )}
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-stone-300 bg-stone-50 px-4 py-6 text-sm text-stone-500">
          {currentArc ? '请先为当前阶段生成下一章，再进入章节细修。' : '当前还没有可查看的章节。'}
        </div>
      )}

      {archivedArcChapters.length > 0 ? (
        <details className="rounded-[24px] border border-stone-200 bg-white p-4 shadow-sm">
          <summary className="cursor-pointer text-sm font-semibold text-stone-900">其他阶段章节</summary>
          <div className="mt-4 space-y-4">
            {archivedArcChapters.map(({ arc, chapters }) => (
              <section key={arc.arc_number} className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h5 className="text-sm font-semibold text-stone-800">
                    第 {arc.arc_number} 幕 · {arc.title}
                  </h5>
                  <span className="rounded-full bg-stone-100 px-2 py-1 text-xs text-stone-600">
                    {chapters.length} 章
                  </span>
                </div>
                <div className="grid gap-3 xl:grid-cols-2">
                  {chapters.map((item) =>
                    renderChapterCard(item, {
                      chapterIssues: roadmapIssues.filter((issue) => issue.chapter_number === item.chapter_number),
                      selectedChapterNumber,
                      highlightedChapterNumber,
                      lastGeneratedChapterNumber,
                      activeArc,
                      pendingChapterNumber,
                      onSelectChapter,
                      onRegenerateChapter,
                    }),
                  )}
                </div>
              </section>
            ))}
          </div>
        </details>
      ) : null}
    </section>
  )
}
