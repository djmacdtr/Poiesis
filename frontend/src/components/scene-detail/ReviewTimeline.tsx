/**
 * 审阅动作时间线。
 */
import type { ReviewEvent, ReviewQueueItem } from '@/types'
import { buildReviewTimeline, sceneStatusLabel } from '@/lib/scene-detail'
import { formatDateTime } from '@/lib/utils'
import { StatusPill } from './StatusPill'

interface ReviewTimelineProps {
  review?: ReviewQueueItem | null
  events: ReviewEvent[]
}

export function ReviewTimeline({ review, events }: ReviewTimelineProps) {
  const timeline = buildReviewTimeline(events)

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-stone-700">审阅历史</h3>
        {review && (
          <StatusPill
            label={review.status === 'pending' ? '待处理' : review.status === 'completed' ? '已处理' : '执行失败'}
            tone={review.status === 'pending' ? 'warning' : review.status === 'completed' ? 'success' : 'danger'}
          />
        )}
      </div>

      {review ? (
        <div className="mt-4 rounded-xl bg-stone-50 p-3 text-sm text-stone-700">
          <p>当前场景状态：{sceneStatusLabel[review.scene_status] ?? review.scene_status}</p>
          <p className="mt-1">进入审阅原因：{review.reason || '无'}</p>
          <p className="mt-1">最近结果：{review.result_summary || review.latest_result_summary || '尚无结果摘要'}</p>
        </div>
      ) : (
        <p className="mt-4 text-sm text-stone-400">当前场景没有进入过审阅队列。</p>
      )}

      {timeline.length > 0 ? (
        <div className="mt-4 space-y-3">
          {timeline.map((event) => (
            <div key={event.id} className="rounded-xl border border-stone-200 p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-stone-800">{event.title}</p>
                  <p className="mt-1 text-xs text-stone-400">
                    {event.operator} · {formatDateTime(event.timestamp)}
                  </p>
                </div>
                <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${event.statusTone}`}>
                  {event.statusLabel}
                </span>
              </div>
              <p className="mt-2 text-sm leading-6 text-stone-600">{event.summary}</p>
            </div>
          ))}
        </div>
      ) : review ? (
        <p className="mt-4 text-sm text-stone-400">当前审阅项还没有动作历史。</p>
      ) : null}
    </section>
  )
}
