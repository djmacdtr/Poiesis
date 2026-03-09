/**
 * 场景化运行详情页。
 */
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { fetchSceneChapterDetail, fetchSceneDetail, fetchSceneRunDetail } from '@/services/run'

const traceStatusLabel: Record<string, string> = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  needs_review: '待审阅',
  failed: '失败',
  approved: '已通过',
}

const chapterStatusLabel: Record<string, string> = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
}

function JsonPanel({ value }: { value: unknown }) {
  return (
    <pre className="overflow-x-auto rounded-xl border border-stone-200 bg-stone-50 p-3 text-xs text-stone-700">
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

export default function SceneRunDetail() {
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
        <section className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
          <div className="space-y-4">
            <div className="rounded-2xl border border-stone-200 bg-white p-4">
              <h3 className="text-sm font-semibold text-stone-700">章节列表</h3>
              <div className="mt-3 space-y-2">
                {runDetail.chapters.map((chapter) => (
                  <button
                    key={chapter.chapter_number}
                    onClick={() => {
                      setSelectedChapter(chapter.chapter_number)
                      setSelectedScene(null)
                    }}
                    className="w-full rounded-xl border border-stone-200 px-3 py-2 text-left hover:bg-stone-50"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-stone-800">第 {chapter.chapter_number} 章</span>
                      <span className="text-xs text-stone-500">
                        {chapterStatusLabel[chapter.status] ?? chapter.status}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-stone-500">
                      {chapter.review_required ? '包含待审场景' : '已自动通过'}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            {chapterDetail && (
              <div className="rounded-2xl border border-stone-200 bg-white p-4">
                <h3 className="text-sm font-semibold text-stone-700">场景列表</h3>
                <div className="mt-3 space-y-2">
                  {chapterDetail.trace.scenes.map((scene) => (
                    <button
                      key={scene.scene_number}
                      onClick={() => setSelectedScene(scene.scene_number)}
                      className="w-full rounded-xl border border-stone-200 px-3 py-2 text-left hover:bg-stone-50"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-stone-800">场景 {scene.scene_number}</span>
                        <span className="text-xs text-stone-500">
                          {traceStatusLabel[scene.status] ?? scene.status}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-stone-500">{scene.scene_plan.title}</p>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="space-y-4">
            {chapterDetail && (
              <>
                <section className="rounded-2xl border border-stone-200 bg-white p-4">
                  <h3 className="text-sm font-semibold text-stone-700">章节规划</h3>
                  <JsonPanel value={chapterDetail.trace.chapter_plan} />
                </section>
                <section className="rounded-2xl border border-stone-200 bg-white p-4">
                  <h3 className="text-sm font-semibold text-stone-700">章节正文</h3>
                  <div className="max-h-80 overflow-y-auto whitespace-pre-wrap rounded-xl bg-stone-50 p-3 text-sm leading-6 text-stone-700">
                    {chapterDetail.trace.assembled_text || '暂无正文'}
                  </div>
                </section>
              </>
            )}

            {sceneDetail && (
              <>
                <section className="rounded-2xl border border-stone-200 bg-white p-4">
                  <h3 className="text-sm font-semibold text-stone-700">场景规划</h3>
                  <JsonPanel value={sceneDetail.scene.scene_plan} />
                </section>
                <section className="rounded-2xl border border-stone-200 bg-white p-4">
                  <h3 className="text-sm font-semibold text-stone-700">场景正文</h3>
                  <div className="max-h-72 overflow-y-auto whitespace-pre-wrap rounded-xl bg-stone-50 p-3 text-sm leading-6 text-stone-700">
                    {sceneDetail.scene.final_text || sceneDetail.scene.draft?.content || '暂无正文'}
                  </div>
                </section>
                <section className="rounded-2xl border border-stone-200 bg-white p-4">
                  <h3 className="text-sm font-semibold text-stone-700">问题 / 变更 / 修补</h3>
                  <JsonPanel
                    value={{
                      issues: sceneDetail.scene.verifier_issues,
                      changeset: sceneDetail.scene.changeset,
                      patches: sceneDetail.patches,
                    }}
                  />
                </section>
              </>
            )}
          </div>
        </section>
      )}
    </div>
  )
}
