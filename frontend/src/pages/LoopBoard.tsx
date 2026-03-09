/**
 * 剧情线索面板：查看进行中、已解决和已逾期的线索。
 */
import { useQuery } from '@tanstack/react-query'
import { fetchLoops } from '@/services/run'

const loopStatusLabel: Record<string, string> = {
  open: '开启',
  hinted: '埋线',
  escalated: '升级',
  resolved: '已解决',
  dropped: '已放弃',
  overdue: '已逾期',
}

export default function LoopBoard() {
  const { data } = useQuery({
    queryKey: ['loopBoard'],
    queryFn: () => fetchLoops(1),
    refetchInterval: 5000,
  })

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-stone-900">剧情线索面板</h2>
        <p className="mt-1 text-sm text-stone-500">展示当前故事承诺的推进状态，而不是旧式 foreshadowing 列表。</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {(data?.items ?? []).map((loop) => (
          <article key={loop.loop_id} className="rounded-2xl border border-stone-200 bg-white p-5">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-stone-900">{loop.title}</h3>
              <span className="rounded-full bg-stone-100 px-2 py-0.5 text-xs text-stone-600">
                {loopStatusLabel[loop.status] ?? loop.status}
              </span>
            </div>
            <div className="mt-3 space-y-2 text-xs text-stone-500">
              <p>线索 ID：{loop.loop_id}</p>
              <p>首次出现：{loop.introduced_in_scene || '-'}</p>
              <p>最近推进：{loop.last_updated_scene || '-'}</p>
              <p>回收窗口：{loop.due_window || '-'}</p>
              <p>优先级：{loop.priority}</p>
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}
