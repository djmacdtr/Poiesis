/**
 * 审阅队列页：处理进入人工队列的场景。
 *
 * 这里和 /workspace 共用同一套“当前作品”上下文：
 * - query 参数可以精确跳到某一本书的审阅队列；
 * - 没有 query 时回退到左侧导航共享的当前作品；
 * - 最终结果同步回 query，避免工作台和审阅页各自停在不同作品上。
 */
import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { ErrorMessage, LoadingSpinner } from '@/components/Feedback'
import { useActiveBook, resolveActiveBookId } from '@/contexts/ActiveBookContext'
import { formatReviewStatusLabel, formatSceneStatusLabel } from '@/lib/display-labels'
import { fetchBooks } from '@/services/books'
import { approveReview, fetchReviewQueue, patchReview, retryReview } from '@/services/run'
import type { BookItem, ReviewQueueItem } from '@/types'

const reviewActionLabel: Record<'approve' | 'retry' | 'patch', string> = {
  approve: '通过',
  retry: '重试',
  patch: '修补',
}

export default function ReviewQueue() {
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const { activeBookId, setActiveBookId } = useActiveBook()
  const [patchMap, setPatchMap] = useState<Record<number, string>>({})

  const { data: books = [], isLoading: booksLoading, error: booksError } = useQuery<BookItem[]>({
    queryKey: ['books'],
    queryFn: fetchBooks,
    staleTime: 30_000,
  })

  const resolvedBookId = resolveActiveBookId(activeBookId, books)

  const { data, isLoading, error } = useQuery({
    queryKey: ['reviewQueue', resolvedBookId],
    queryFn: () => fetchReviewQueue(resolvedBookId),
    enabled: books.length > 0,
    refetchInterval: 4000,
  })

  useEffect(() => {
    if (books.length === 0) {
      return
    }
    const fromQuery = Number(searchParams.get('book') || '')
    const targetBookId =
      Number.isFinite(fromQuery) && fromQuery > 0 ? resolveActiveBookId(fromQuery, books) : resolvedBookId

    if (targetBookId !== activeBookId) {
      setActiveBookId(targetBookId)
      return
    }
    if (searchParams.get('book') !== String(targetBookId)) {
      setSearchParams({ book: String(targetBookId) }, { replace: true })
    }
  }, [activeBookId, books, resolvedBookId, searchParams, setActiveBookId, setSearchParams])

  if (booksLoading) {
    return <LoadingSpinner text="加载审阅队列中…" />
  }
  if (booksError) {
    return <ErrorMessage message={(booksError as Error).message} />
  }
  if (isLoading) {
    return <LoadingSpinner text="读取当前作品审阅项中…" />
  }
  if (error) {
    return <ErrorMessage message={(error as Error).message} />
  }

  const activeBook = books.find((item) => item.id === resolvedBookId) ?? null

  const handleAction = async (review: ReviewQueueItem, action: 'approve' | 'retry' | 'patch') => {
    try {
      if (review.status !== 'pending') {
        toast.warning('该审阅项已处理，不能重复执行动作')
        return
      }
      if (action === 'patch' && !(patchMap[review.id] || '').trim()) {
        toast.warning('请先填写修补要求')
        return
      }
      if (action === 'approve') await approveReview(review.id)
      if (action === 'retry') await retryReview(review.id)
      if (action === 'patch') await patchReview(review.id, patchMap[review.id] || '')
      toast.success(`已执行${reviewActionLabel[action]}`)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['reviewQueue', resolvedBookId] }),
        queryClient.invalidateQueries({ queryKey: ['sceneRunDetail', review.run_id] }),
        queryClient.invalidateQueries({ queryKey: ['sceneChapterDetail', review.run_id, review.chapter_number] }),
        queryClient.invalidateQueries({ queryKey: ['sceneDetail', review.run_id, review.chapter_number, review.scene_number] }),
        queryClient.invalidateQueries({ queryKey: ['chapters'] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] }),
        queryClient.invalidateQueries({ queryKey: ['bookBlueprint', resolvedBookId] }),
      ])
    } catch (error) {
      toast.error((error as Error).message)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-stone-900">审阅队列</h2>
        <p className="mt-1 text-sm text-stone-500">
          当前作品：{activeBook?.name || '未命名作品'}。默认自动通过，但存在严重问题的场景会进入这里等待处理。
        </p>
      </div>
      <div className="space-y-4">
        {(data?.items ?? []).map((item) => (
          <section key={item.id} className="rounded-2xl border border-stone-200 bg-white p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-stone-900">
                  任务 #{item.run_id} / 第 {item.chapter_number} 章 / 场景 {item.scene_number}
                </p>
                <p className="mt-1 text-xs text-stone-500">{item.reason || '无说明'}</p>
                <p className="mt-1 text-xs text-stone-400">
                  场景状态：{formatSceneStatusLabel(item.scene_status)} · 历史动作：{item.event_count} 次
                </p>
                {item.latest_result_summary && (
                  <p className="mt-1 text-xs text-stone-400">最近结果：{item.latest_result_summary}</p>
                )}
              </div>
              <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs text-amber-700">
                {formatReviewStatusLabel(item.status)}
              </span>
            </div>
            <textarea
              value={patchMap[item.id] ?? item.patch_text}
              onChange={(event) => setPatchMap((prev) => ({ ...prev, [item.id]: event.target.value }))}
              placeholder="需要的话可以直接提交修补文本。"
              className="mt-4 min-h-28 w-full rounded-xl border border-stone-300 px-3 py-2 text-sm"
            />
            <div className="mt-4 flex gap-2">
              <button
                onClick={() => handleAction(item, 'approve')}
                disabled={item.status !== 'pending'}
                className="rounded-lg bg-stone-900 px-3 py-1.5 text-xs text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                通过
              </button>
              <button
                onClick={() => handleAction(item, 'retry')}
                disabled={item.status !== 'pending'}
                className="rounded-lg border border-stone-300 px-3 py-1.5 text-xs text-stone-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                重试
              </button>
              <button
                onClick={() => handleAction(item, 'patch')}
                disabled={item.status !== 'pending'}
                className="rounded-lg border border-stone-300 px-3 py-1.5 text-xs text-stone-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                修补
              </button>
            </div>
          </section>
        ))}
        {(data?.items?.length ?? 0) === 0 && (
          <div className="rounded-2xl border border-stone-200 bg-white p-5 text-sm text-stone-500">
            当前没有待处理的审阅项。
          </div>
        )}
      </div>
    </div>
  )
}
