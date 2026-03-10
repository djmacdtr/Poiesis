/**
 * 场景化运行详情页。
 * 页面层只负责数据查询、选择状态和布局编排，
 * 具体展示逻辑下沉到 scene-detail 组件与 helper。
 */
import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { ChapterStatusCard } from '@/components/scene-detail/ChapterStatusCard'
import { PatchDiffCard } from '@/components/scene-detail/PatchDiffCard'
import { RawJsonDetails } from '@/components/scene-detail/RawJsonDetails'
import { ReviewTimeline } from '@/components/scene-detail/ReviewTimeline'
import { SceneChangeSetPanel } from '@/components/scene-detail/SceneChangeSetPanel'
import { SceneIssueList } from '@/components/scene-detail/SceneIssueList'
import { ScenePlanCard } from '@/components/scene-detail/ScenePlanCard'
import { SceneTextCard } from '@/components/scene-detail/SceneTextCard'
import { StatusPill } from '@/components/scene-detail/StatusPill'
import { sceneStatusLabel } from '@/lib/scene-detail'
import { chapterStatusLabel, cn, formatDateTime } from '@/lib/utils'
import { fetchSceneChapterDetail, fetchSceneDetail, fetchSceneRunDetail, publishChapter } from '@/services/run'

const runStatusLabel: Record<string, string> = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  interrupted: '已中断',
}

const runStatusTone: Record<string, 'neutral' | 'success' | 'warning' | 'danger' | 'info'> = {
  pending: 'warning',
  running: 'info',
  completed: 'success',
  failed: 'danger',
  interrupted: 'warning',
}

const chapterStatusTone: Record<string, 'neutral' | 'success' | 'warning' | 'danger' | 'info'> = {
  draft: 'neutral',
  needs_review: 'warning',
  ready_to_publish: 'success',
  published: 'info',
}

const sceneStatusTone: Record<string, 'neutral' | 'success' | 'warning' | 'danger' | 'info'> = {
  pending: 'warning',
  running: 'info',
  completed: 'success',
  needs_review: 'warning',
  failed: 'danger',
  approved: 'info',
}

function ChapterPlanSummary({ chapterDetail }: { chapterDetail: NonNullable<Awaited<ReturnType<typeof fetchSceneChapterDetail>>> }) {
  const plan = chapterDetail.trace.chapter_plan

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-stone-700">章节规划摘要</h3>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-xl bg-stone-50 p-3">
          <p className="text-xs font-medium text-stone-500">章节标题</p>
          <p className="mt-1 text-sm text-stone-700">{plan.title || `第 ${plan.chapter_number} 章`}</p>
        </div>
        <div className="rounded-xl bg-stone-50 p-3">
          <p className="text-xs font-medium text-stone-500">章节目标</p>
          <p className="mt-1 text-sm text-stone-700">{plan.goal || '—'}</p>
        </div>
        <div className="rounded-xl bg-stone-50 p-3">
          <p className="text-xs font-medium text-stone-500">章节钩子</p>
          <p className="mt-1 text-sm text-stone-700">{plan.hook || '—'}</p>
        </div>
        <div className="rounded-xl bg-stone-50 p-3">
          <p className="text-xs font-medium text-stone-500">目标场景数</p>
          <p className="mt-1 text-sm text-stone-700">{plan.scene_count_target || 0}</p>
        </div>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-xl bg-stone-50 p-3">
          <p className="text-xs font-medium text-stone-500">必须保留</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {plan.must_preserve.length > 0 ? (
              plan.must_preserve.map((item) => (
                <span key={item} className="rounded-full bg-white px-2 py-1 text-xs text-stone-600">
                  {item}
                </span>
              ))
            ) : (
              <span className="text-xs text-stone-400">没有指定保留事项</span>
            )}
          </div>
        </div>
        <div className="rounded-xl bg-stone-50 p-3">
          <p className="text-xs font-medium text-stone-500">必须推进的剧情线索</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {plan.must_progress_loops.length > 0 ? (
              plan.must_progress_loops.map((item) => (
                <span key={item} className="rounded-full bg-white px-2 py-1 text-xs text-stone-600">
                  {item}
                </span>
              ))
            ) : (
              <span className="text-xs text-stone-400">没有指定剧情线索</span>
            )}
          </div>
        </div>
      </div>
      {plan.notes.length > 0 && (
        <div className="mt-4 rounded-xl bg-stone-50 p-3">
          <p className="text-xs font-medium text-stone-500">附加说明</p>
          <ul className="mt-2 space-y-1 text-sm text-stone-700">
            {plan.notes.map((item) => (
              <li key={item}>- {item}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

export default function SceneRunDetail() {
  const queryClient = useQueryClient()
  const { runId = '' } = useParams()
  const numericRunId = Number(runId)
  const [selectedChapter, setSelectedChapter] = useState<number | null>(null)
  const [selectedScene, setSelectedScene] = useState<number | null>(null)

  const { data: runDetail } = useQuery({
    queryKey: ['sceneRunDetail', numericRunId],
    queryFn: () => fetchSceneRunDetail(numericRunId),
    enabled: Number.isFinite(numericRunId),
  })

  const chapterNumber = useMemo(() => {
    if (selectedChapter != null) return selectedChapter
    return runDetail?.chapters?.[0]?.chapter_number ?? null
  }, [runDetail, selectedChapter])

  const { data: chapterDetail } = useQuery({
    queryKey: ['sceneChapterDetail', numericRunId, chapterNumber],
    queryFn: () => fetchSceneChapterDetail(numericRunId, chapterNumber!),
    enabled: Number.isFinite(numericRunId) && chapterNumber != null,
  })

  const sceneNumber = useMemo(() => {
    if (selectedScene != null) return selectedScene
    return chapterDetail?.trace?.scenes?.[0]?.scene_number ?? null
  }, [chapterDetail, selectedScene])

  const { data: sceneDetail } = useQuery({
    queryKey: ['sceneDetail', numericRunId, chapterNumber, sceneNumber],
    queryFn: () => fetchSceneDetail(numericRunId, chapterNumber!, sceneNumber!),
    enabled: Number.isFinite(numericRunId) && chapterNumber != null && sceneNumber != null,
  })

  const selectedChapterSummary = useMemo(
    () => runDetail?.chapters.find((item) => item.chapter_number === chapterNumber),
    [chapterNumber, runDetail],
  )

  const publishMutation = useMutation({
    mutationFn: () => publishChapter(numericRunId, chapterNumber!),
    onSuccess: async () => {
      toast.success('章节已发布')
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['sceneRunDetail', numericRunId] }),
        queryClient.invalidateQueries({ queryKey: ['sceneChapterDetail', numericRunId, chapterNumber] }),
        queryClient.invalidateQueries({ queryKey: ['chapters'] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] }),
      ])
    },
    onError: (error: Error) => {
      toast.error(error.message)
    },
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-stone-900">任务 #{runId}</h2>
          <p className="mt-1 text-sm text-stone-500">章节、场景和审阅风险都在这条链路里收口。</p>
        </div>
        <Link to="/runs" className="rounded-lg border border-stone-300 px-3 py-1.5 text-sm text-stone-700">
          返回运行面板
        </Link>
      </div>

      {runDetail && (
        <section className="rounded-2xl border border-stone-200 bg-white p-5">
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill
              label={runStatusLabel[runDetail.run.status] ?? runDetail.run.status}
              tone={runStatusTone[runDetail.run.status] ?? 'neutral'}
            />
            {selectedChapterSummary && (
              <StatusPill
                label={`第 ${selectedChapterSummary.chapter_number} 章 · ${chapterStatusLabel[selectedChapterSummary.status] ?? selectedChapterSummary.status}`}
                tone={chapterStatusTone[selectedChapterSummary.status] ?? 'neutral'}
              />
            )}
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <div className="rounded-xl bg-stone-50 p-3">
              <p className="text-xs font-medium text-stone-500">任务编号</p>
              <p className="mt-1 text-sm text-stone-700">{runDetail.run.task_id}</p>
            </div>
            <div className="rounded-xl bg-stone-50 p-3">
              <p className="text-xs font-medium text-stone-500">书籍 ID</p>
              <p className="mt-1 text-sm text-stone-700">{runDetail.run.book_id}</p>
            </div>
            <div className="rounded-xl bg-stone-50 p-3">
              <p className="text-xs font-medium text-stone-500">创建时间</p>
              <p className="mt-1 text-sm text-stone-700">{formatDateTime(runDetail.run.created_at)}</p>
            </div>
            <div className="rounded-xl bg-stone-50 p-3">
              <p className="text-xs font-medium text-stone-500">最近更新时间</p>
              <p className="mt-1 text-sm text-stone-700">{formatDateTime(runDetail.run.updated_at)}</p>
            </div>
          </div>
          {selectedChapterSummary && (
            <div className="mt-4 rounded-xl bg-stone-50 p-3 text-sm text-stone-700">
              <p className="font-medium text-stone-800">当前章节摘要</p>
              <p className="mt-1 leading-6">
                {selectedChapterSummary.blockers.length > 0
                  ? selectedChapterSummary.blockers.join('；')
                  : selectedChapterSummary.can_publish
                    ? '当前章节已满足发布条件，可以直接发布。'
                    : '当前章节暂无额外阻塞项。'}
              </p>
            </div>
          )}
        </section>
      )}

      {runDetail && (
        <section className="grid gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
          <div className="space-y-4">
            <div className="rounded-2xl border border-stone-200 bg-white p-4">
              <h3 className="text-sm font-semibold text-stone-700">章节导航</h3>
              <div className="mt-3 space-y-2">
                {runDetail.chapters.map((chapter) => (
                  <button
                    key={chapter.chapter_number}
                    onClick={() => {
                      setSelectedChapter(chapter.chapter_number)
                      setSelectedScene(null)
                    }}
                    className={cn(
                      'w-full rounded-xl border px-3 py-3 text-left transition-colors',
                      chapter.chapter_number === chapterNumber
                        ? 'border-stone-900 bg-stone-900 text-white'
                        : 'border-stone-200 bg-white hover:bg-stone-50',
                    )}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm font-medium">第 {chapter.chapter_number} 章</span>
                      <StatusPill
                        label={chapterStatusLabel[chapter.status] ?? chapter.status}
                        tone={chapterStatusTone[chapter.status] ?? 'neutral'}
                        className={chapter.chapter_number === chapterNumber ? 'bg-white/15 text-white' : ''}
                      />
                    </div>
                    <p className={cn('mt-2 text-xs leading-5', chapter.chapter_number === chapterNumber ? 'text-stone-300' : 'text-stone-500')}>
                      {chapter.blockers.length > 0
                        ? chapter.blockers[0]
                        : chapter.can_publish
                          ? '已达到可发布状态'
                          : '暂无阻塞项'}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            {chapterDetail && (
              <div className="rounded-2xl border border-stone-200 bg-white p-4">
                <h3 className="text-sm font-semibold text-stone-700">场景导航</h3>
                {chapterDetail.trace.scenes.length === 0 ? (
                  <p className="mt-3 text-sm text-stone-400">当前章节还没有场景记录。</p>
                ) : (
                  <div className="mt-3 space-y-2">
                    {chapterDetail.trace.scenes.map((scene) => (
                      <button
                        key={scene.scene_number}
                        onClick={() => setSelectedScene(scene.scene_number)}
                        className={cn(
                          'w-full rounded-xl border px-3 py-3 text-left transition-colors',
                          scene.scene_number === sceneNumber
                            ? 'border-stone-900 bg-stone-900 text-white'
                            : 'border-stone-200 bg-white hover:bg-stone-50',
                        )}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <span className="text-sm font-medium">场景 {scene.scene_number}</span>
                          <StatusPill
                            label={sceneStatusLabel[scene.status] ?? scene.status}
                            tone={sceneStatusTone[scene.status] ?? 'neutral'}
                            className={scene.scene_number === sceneNumber ? 'bg-white/15 text-white' : ''}
                          />
                        </div>
                        <p className={cn('mt-1 text-xs', scene.scene_number === sceneNumber ? 'text-stone-300' : 'text-stone-500')}>
                          {scene.scene_plan.title || '未命名场景'}
                        </p>
                        <p className={cn('mt-1 text-xs', scene.scene_number === sceneNumber ? 'text-stone-300' : 'text-stone-400')}>
                          {scene.verifier_issues.length > 0
                            ? `当前有 ${scene.verifier_issues.length} 个问题`
                            : scene.review_required
                              ? '等待人工处理'
                              : '当前场景已通过'}
                        </p>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="space-y-4">
            {chapterDetail && (
              <>
                <ChapterStatusCard
                  publish={chapterDetail.publish}
                  isPublishing={publishMutation.isPending}
                  onPublish={() => publishMutation.mutate()}
                />
                <ChapterPlanSummary chapterDetail={chapterDetail} />
                <SceneTextCard title="章节正文预览" text={chapterDetail.trace.assembled_text} />
              </>
            )}

            {sceneDetail && (
              <>
                <ScenePlanCard plan={sceneDetail.scene.scene_plan} />
                <SceneTextCard
                  title="场景正文"
                  text={sceneDetail.scene.final_text || sceneDetail.scene.draft?.content || ''}
                  draftText={sceneDetail.scene.draft?.content}
                />
                <SceneIssueList issues={sceneDetail.scene.verifier_issues} />
                <SceneChangeSetPanel changeset={sceneDetail.scene.changeset} />
                <ReviewTimeline review={sceneDetail.review} events={sceneDetail.review_events} />
                <PatchDiffCard patches={sceneDetail.patches} />
                <RawJsonDetails
                  title="查看原始数据"
                  value={{
                    chapter: chapterDetail,
                    scene: sceneDetail,
                  }}
                />
              </>
            )}

            {!sceneDetail && chapterDetail && (
              <section className="rounded-2xl border border-stone-200 bg-white p-6 text-sm text-stone-400">
                当前章节没有可展示的场景详情。
              </section>
            )}
          </div>
        </section>
      )}
    </div>
  )
}
