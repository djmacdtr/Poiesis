/**
 * 剧情线索面板：查看进行中、已解决和已逾期的线索。
 */
import { useMemo, useState } from 'react'
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
  const [statusFilter, setStatusFilter] = useState<'all' | string>('all')
  const [priorityFilter, setPriorityFilter] = useState<'all' | string>('all')
  const { data } = useQuery({
    queryKey: ['loopBoard'],
    queryFn: () => fetchLoops(1),
    refetchInterval: 5000,
  })

  const filteredItems = useMemo(() => {
    return (data?.items ?? []).filter((loop) => {
      if (statusFilter !== 'all' && loop.status !== statusFilter) return false
      if (priorityFilter !== 'all' && String(loop.priority) !== priorityFilter) return false
      return true
    })
  }, [data?.items, priorityFilter, statusFilter])

  const groupedItems = useMemo(
    () =>
      ({
        open: filteredItems.filter((item) => item.status === 'open'),
        escalated: filteredItems.filter((item) => item.status === 'escalated' || item.status === 'hinted'),
        overdue: filteredItems.filter((item) => item.status === 'overdue'),
        resolved: filteredItems.filter((item) => item.status === 'resolved'),
        dropped: filteredItems.filter((item) => item.status === 'dropped'),
      }) as const,
    [filteredItems],
  )

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-stone-900">剧情线索面板</h2>
          <p className="mt-1 text-sm text-stone-500">按状态查看当前故事承诺、回收窗口和最近推进位置。</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
          >
            <option value="all">全部状态</option>
            <option value="open">开启</option>
            <option value="hinted">埋线</option>
            <option value="escalated">升级</option>
            <option value="overdue">已逾期</option>
            <option value="resolved">已解决</option>
            <option value="dropped">已放弃</option>
          </select>
          <select
            value={priorityFilter}
            onChange={(event) => setPriorityFilter(event.target.value)}
            className="rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
          >
            <option value="all">全部优先级</option>
            <option value="1">优先级 1</option>
            <option value="2">优先级 2</option>
            <option value="3">优先级 3</option>
          </select>
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {[
          ['open', '进行中'],
          ['escalated', '已升级'],
          ['overdue', '已逾期'],
          ['resolved', '已解决'],
          ['dropped', '已放弃'],
        ].map(([key, label]) => (
          <div key={key} className="rounded-2xl border border-stone-200 bg-white p-4">
            <p className="text-xs font-medium text-stone-500">{label}</p>
            <p className="mt-2 text-2xl font-semibold text-stone-900">
              {groupedItems[key as keyof typeof groupedItems].length}
            </p>
          </div>
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {filteredItems.map((loop) => (
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
              <p>回收章节：{loop.due_end_chapter != null ? `第 ${loop.due_end_chapter} 章` : loop.due_window || '-'}</p>
              <p>优先级：{loop.priority}</p>
              {loop.related_characters.length > 0 && (
                <p>相关角色：{loop.related_characters.join('、')}</p>
              )}
            </div>
          </article>
        ))}
        {filteredItems.length === 0 && (
          <div className="rounded-2xl border border-stone-200 bg-white p-5 text-sm text-stone-500">
            当前筛选条件下没有剧情线索。
          </div>
        )}
      </div>
    </div>
  )
}
