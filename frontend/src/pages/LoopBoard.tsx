/**
 * Loop Board：查看 open / resolved / overdue 线索。
 */
import { useQuery } from '@tanstack/react-query'
import { fetchLoops } from '@/services/run'

export default function LoopBoard() {
  const { data } = useQuery({
    queryKey: ['loopBoard'],
    queryFn: () => fetchLoops(1),
    refetchInterval: 5000,
  })

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-stone-900">Loop Board</h2>
        <p className="mt-1 text-sm text-stone-500">展示当前故事承诺的推进状态，而不是旧式 foreshadowing 列表。</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {(data?.items ?? []).map((loop) => (
          <article key={loop.loop_id} className="rounded-2xl border border-stone-200 bg-white p-5">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-stone-900">{loop.title}</h3>
              <span className="rounded-full bg-stone-100 px-2 py-0.5 text-xs text-stone-600">{loop.status}</span>
            </div>
            <div className="mt-3 space-y-2 text-xs text-stone-500">
              <p>Loop ID: {loop.loop_id}</p>
              <p>Introduced: {loop.introduced_in_scene || '-'}</p>
              <p>Last Updated: {loop.last_updated_scene || '-'}</p>
              <p>Due Window: {loop.due_window || '-'}</p>
              <p>Priority: {loop.priority}</p>
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}
