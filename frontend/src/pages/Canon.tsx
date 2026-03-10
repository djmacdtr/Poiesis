/**
 * 世界设定 Canon 页：展示角色、世界规则、时间线、伏笔
 */
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { fetchCanon } from '@/services/world'
import { fetchBooks } from '@/services/books'
import { LoadingSpinner, ErrorMessage, EmptyState } from '@/components/Feedback'
import { formatDate, foreshadowingStatusLabel } from '@/lib/utils'
import { cn } from '@/lib/utils'
import type { BookItem, CanonData } from '@/types'

/** 标签页配置 */
const tabs = [
  { key: 'characters', label: '角色' },
  { key: 'world_rules', label: '世界规则' },
  { key: 'timeline', label: '时间线' },
  { key: 'foreshadowing', label: '伏笔' },
] as const

type TabKey = (typeof tabs)[number]['key']

/** 伏笔状态颜色 */
const foreshadowingColor: Record<string, string> = {
  pending: 'bg-amber-100 text-amber-700',
  active: 'bg-blue-100 text-blue-700',
  resolved: 'bg-green-100 text-green-700',
  dropped: 'bg-gray-100 text-gray-500',
}
const ACTIVE_BOOK_ID_KEY = 'poiesis.activeBookId'

export default function Canon() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState<TabKey>('characters')
  const [activeBookId, setActiveBookId] = useState<number>(() => {
    const fromQuery = Number(searchParams.get('book') || '')
    if (Number.isFinite(fromQuery) && fromQuery > 0) return fromQuery
    if (typeof window === 'undefined') return 1
    const raw = window.localStorage.getItem(ACTIVE_BOOK_ID_KEY)
    return raw ? Number(raw) || 1 : 1
  })

  const { data: books = [] } = useQuery<BookItem[]>({
    queryKey: ['books'],
    queryFn: fetchBooks,
    staleTime: 30_000,
  })

  const { data, isLoading, error } = useQuery<CanonData>({
    queryKey: ['canon', activeBookId],
    queryFn: () => fetchCanon(activeBookId),
  })

  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(ACTIVE_BOOK_ID_KEY, String(activeBookId))
    setSearchParams({ book: String(activeBookId) }, { replace: true })
  }, [activeBookId, setSearchParams])

  useEffect(() => {
    if (books.length === 0) return
    const exists = books.some((item) => item.id === activeBookId)
    if (exists) return
    const next = books.find((item) => item.is_default)?.id ?? books[0].id
    setActiveBookId(next)
  }, [activeBookId, books])

  if (isLoading) return <LoadingSpinner text="加载世界设定…" />
  if (error) return <ErrorMessage message={(error as Error).message} />

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-gray-800">世界设定（Canon）</h2>
        <select
          value={activeBookId}
          onChange={(e) => setActiveBookId(Number(e.target.value))}
          className="min-w-56 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 bg-white"
        >
          {books.map((book) => (
            <option key={book.id} value={book.id}>
              {book.name}（{book.language} / {book.style_preset}）
            </option>
          ))}
        </select>
      </div>

      <section className="grid gap-4 md:grid-cols-4">
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <p className="text-xs font-medium text-gray-500">最近已发布章节</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900">
            {data?.story_state.last_published_chapter ?? 0}
          </p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <p className="text-xs font-medium text-gray-500">当前活动章节</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900">
            {data?.story_state.active_chapter ?? 1}
          </p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <p className="text-xs font-medium text-gray-500">未闭合线索</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900">
            {data?.story_state.open_loop_count ?? 0}
          </p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <p className="text-xs font-medium text-gray-500">已逾期线索</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900">
            {data?.story_state.overdue_loop_count ?? 0}
          </p>
        </div>
      </section>

      {(data?.story_state.recent_scene_refs?.length ?? 0) > 0 && (
        <section className="rounded-xl border border-gray-200 bg-white p-4">
          <h3 className="text-sm font-semibold text-gray-800">最近发布章节涉及场景</h3>
          <div className="mt-3 flex flex-wrap gap-2">
            {(data?.story_state.recent_scene_refs ?? []).map((item) => (
              <span key={item} className="rounded-full bg-gray-100 px-2.5 py-1 text-xs text-gray-600">
                {item}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* 标签页导航 */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'px-4 py-1.5 text-sm rounded-md font-medium transition-colors',
              activeTab === tab.key
                ? 'bg-white text-indigo-600 shadow-sm'
                : 'text-gray-600 hover:text-gray-900',
            )}
          >
            {tab.label}
            {data && (
              <span className="ml-1.5 text-xs text-gray-400">
                ({data[tab.key].length})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* 标签页内容 */}
      <div>
        {/* 角色列表 */}
        {activeTab === 'characters' && (
          <div>
            {!data?.characters.length ? (
              <EmptyState text="暂无角色" />
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                {data.characters.map((char) => (
                  <div key={char.id} className="bg-white rounded-xl border border-gray-200 p-4 space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-semibold text-gray-900">{char.name}</h3>
                      <span className="text-xs text-gray-400 shrink-0">{char.status}</span>
                    </div>
                    <p className="text-sm text-gray-600">{char.description}</p>
                    {char.core_motivation && (
                      <p className="text-xs text-indigo-600 bg-indigo-50 px-2 py-1 rounded">
                        核心动机：{char.core_motivation}
                      </p>
                    )}
                    <p className="text-xs text-gray-400">{formatDate(char.created_at)}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 世界规则列表 */}
        {activeTab === 'world_rules' && (
          <div>
            {!data?.world_rules.length ? (
              <EmptyState text="暂无世界规则" />
            ) : (
              <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
                {data.world_rules.map((rule) => (
                  <div key={rule.id} className="px-5 py-4 space-y-1">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-medium text-gray-800">世界规则</p>
                      <div className="flex items-center gap-2">
                        <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">{rule.category}</span>
                        {rule.is_immutable && (
                          <span className="text-xs bg-red-100 text-red-600 px-1.5 py-0.5 rounded">不可变</span>
                        )}
                      </div>
                    </div>
                    <p className="text-xs text-gray-400">规则标识：{rule.rule_key}</p>
                    <div className="flex items-center gap-2">
                      {rule.is_immutable && (
                        <span className="text-xs text-red-500">核心设定，生成过程中不允许改写</span>
                      )}
                    </div>
                    <p className="text-sm text-gray-700">{rule.description}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 时间线 */}
        {activeTab === 'timeline' && (
          <div>
            {!data?.timeline.length ? (
              <EmptyState text="暂无时间线事件" />
            ) : (
              <div className="space-y-3">
                {data.timeline
                  .slice()
                  .sort((a, b) => a.chapter_number - b.chapter_number)
                  .map((event) => (
                    <div key={event.id} className="flex gap-4">
                      {/* 时间轴线 */}
                      <div className="flex flex-col items-center">
                        <div className="w-2.5 h-2.5 rounded-full bg-indigo-400 shrink-0 mt-1.5" />
                        <div className="w-0.5 flex-1 bg-gray-200 mt-1" />
                      </div>
                      <div className="bg-white rounded-xl border border-gray-200 p-4 flex-1 mb-1 space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-indigo-500 font-medium">第 {event.chapter_number} 章</span>
                          {event.timestamp_in_world && (
                            <span className="text-xs text-gray-400">{event.timestamp_in_world}</span>
                          )}
                        </div>
                        <p className="text-sm text-gray-700">{event.description}</p>
                        {event.characters_involved.length > 0 && (
                          <div className="flex flex-wrap gap-1">
                            {event.characters_involved.map((c) => (
                              <span key={c} className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                                {c}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
              </div>
            )}
          </div>
        )}

        {/* 伏笔 */}
        {activeTab === 'foreshadowing' && (
          <div>
            {!data?.foreshadowing.length ? (
              <EmptyState text="暂无伏笔记录" />
            ) : (
              <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
                {data.foreshadowing.map((item) => (
                  <div key={item.id} className="px-5 py-4 space-y-1.5">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-medium text-gray-800">伏笔记录</p>
                      <span className={cn('text-xs px-1.5 py-0.5 rounded', foreshadowingColor[item.status] ?? 'bg-gray-100 text-gray-500')}>
                        {foreshadowingStatusLabel[item.status] ?? item.status}
                      </span>
                    </div>
                    <p className="text-sm text-gray-700">{item.description}</p>
                    <p className="text-xs text-gray-400">
                      标识：{item.hint_key}
                    </p>
                    <p className="text-xs text-gray-400">
                      引入于第 {item.introduced_in_chapter} 章
                      {item.resolved_in_chapter != null && `，解决于第 ${item.resolved_in_chapter} 章`}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
