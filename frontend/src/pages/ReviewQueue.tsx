/**
 * 审阅队列页：处理进入人工队列的场景。
 */
import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { approveReview, fetchReviewQueue, patchReview, retryReview } from '@/services/run'
import type { ReviewQueueItem } from '@/types'

const reviewStatusLabel: Record<string, string> = {
  pending: '待处理',
  completed: '已处理',
}

const reviewActionLabel: Record<'approve' | 'retry' | 'patch', string> = {
  approve: '通过',
  retry: '重试',
  patch: '修补',
}

export default function ReviewQueue() {
  const queryClient = useQueryClient()
  const [patchMap, setPatchMap] = useState<Record<number, string>>({})
  const { data } = useQuery({
    queryKey: ['reviewQueue'],
    queryFn: () => fetchReviewQueue(1),
    refetchInterval: 4000,
  })

  const handleAction = async (review: ReviewQueueItem, action: 'approve' | 'retry' | 'patch') => {
    try {
      if (action === 'approve') await approveReview(review.id)
      if (action === 'retry') await retryReview(review.id)
      if (action === 'patch') await patchReview(review.id, patchMap[review.id] || '')
      toast.success(`已执行${reviewActionLabel[action]}`)
      await queryClient.invalidateQueries({ queryKey: ['reviewQueue'] })
    } catch (error) {
      toast.error((error as Error).message)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-stone-900">审阅队列</h2>
        <p className="mt-1 text-sm text-stone-500">默认自动通过，但存在严重问题的场景会进入这里等待处理。</p>
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
              </div>
              <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs text-amber-700">
                {reviewStatusLabel[item.status] ?? item.status}
              </span>
            </div>
            <textarea
              value={patchMap[item.id] ?? item.patch_text}
              onChange={(event) => setPatchMap((prev) => ({ ...prev, [item.id]: event.target.value }))}
              placeholder="需要的话可以直接提交修补文本。"
              className="mt-4 min-h-28 w-full rounded-xl border border-stone-300 px-3 py-2 text-sm"
            />
            <div className="mt-4 flex gap-2">
              <button onClick={() => handleAction(item, 'approve')} className="rounded-lg bg-stone-900 px-3 py-1.5 text-xs text-white">
                通过
              </button>
              <button onClick={() => handleAction(item, 'retry')} className="rounded-lg border border-stone-300 px-3 py-1.5 text-xs text-stone-700">
                重试
              </button>
              <button onClick={() => handleAction(item, 'patch')} className="rounded-lg border border-stone-300 px-3 py-1.5 text-xs text-stone-700">
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
