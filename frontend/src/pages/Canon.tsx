/**
 * 世界设定 Canon 页：展示角色、世界规则、时间线、伏笔
 */
import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { RelationshipGraphPanel } from '@/components/relationship-graph/RelationshipGraphPanel'
import { useActiveBook, resolveActiveBookId } from '@/contexts/ActiveBookContext'
import { buildCharacterNodesFromCanon, buildRelationshipGraphViewModel } from '@/lib/relationship-graph'
import { fetchCanon } from '@/services/world'
import { fetchBooks } from '@/services/books'
import { LoadingSpinner, ErrorMessage, EmptyState } from '@/components/Feedback'
import { formatDate, foreshadowingStatusLabel } from '@/lib/utils'
import { cn } from '@/lib/utils'
import type { BookItem, CanonData, RelationshipGraphSelection } from '@/types'

/** 标签页配置 */
const tabs = [
  { key: 'world_blueprint', label: '世界蓝图' },
  { key: 'characters', label: '角色' },
  { key: 'relationship_graph', label: '人物关系' },
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
export default function Canon() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { activeBookId, setActiveBookId } = useActiveBook()
  const [activeTab, setActiveTab] = useState<TabKey>('characters')
  const [graphSelection, setGraphSelection] = useState<RelationshipGraphSelection>(null)

  const { data: books = [] } = useQuery<BookItem[]>({
    queryKey: ['books'],
    queryFn: fetchBooks,
    staleTime: 30_000,
  })

  const { data, isLoading, error } = useQuery<CanonData>({
    queryKey: ['canon', resolveActiveBookId(activeBookId, books)],
    queryFn: () => fetchCanon(resolveActiveBookId(activeBookId, books)),
    enabled: books.length > 0,
  })

  useEffect(() => {
    if (books.length === 0) return
    const fromQuery = Number(searchParams.get('book') || '')
    const targetBookId =
      Number.isFinite(fromQuery) && fromQuery > 0 ? resolveActiveBookId(fromQuery, books) : resolveActiveBookId(activeBookId, books)
    if (targetBookId !== activeBookId) {
      setActiveBookId(targetBookId)
      return
    }
    if (searchParams.get('book') !== String(targetBookId)) {
      setSearchParams({ book: String(targetBookId) }, { replace: true })
    }
  }, [activeBookId, books, searchParams, setActiveBookId, setSearchParams])

  if (isLoading) return <LoadingSpinner text="加载世界设定…" />
  if (error) return <ErrorMessage message={(error as Error).message} />

  const tabCounts: Record<TabKey, number> = {
    world_blueprint: data?.world_blueprint_summary ? 1 : 0,
    characters: data?.characters.length ?? 0,
    relationship_graph: data?.relationship_graph?.length ?? 0,
    world_rules: data?.world_rules.length ?? 0,
    timeline: data?.timeline.length ?? 0,
    foreshadowing: data?.foreshadowing.length ?? 0,
  }
  const relationshipGraphView = useMemo(
    () =>
      buildRelationshipGraphViewModel({
        nodes: buildCharacterNodesFromCanon(data?.characters ?? []),
        edges: data?.relationship_graph ?? [],
        pending: [],
        selection: graphSelection,
        conflict: null,
        replanEdgeId: null,
      }),
    [data?.characters, data?.relationship_graph, graphSelection],
  )

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-gray-800">世界设定（Canon）</h2>
        <p className="text-sm text-gray-500">当前作品由左侧导航统一切换</p>
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
            <span className="ml-1.5 text-xs text-gray-400">({tabCounts[tab.key]})</span>
          </button>
        ))}
      </div>

      {/* 标签页内容 */}
      <div>
        {activeTab === 'world_blueprint' && (
          <div>
            {!data?.world_blueprint_summary ? (
              <EmptyState text="当前还没有可展示的世界蓝图，请先在蓝图工作台确认世界观。" />
            ) : (
              <div className="space-y-4">
                <section className="rounded-xl border border-gray-200 bg-white p-5 space-y-3">
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900">世界总览</h3>
                    <p className="mt-2 text-sm text-gray-700">{data.world_blueprint_summary.setting_summary}</p>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-lg bg-stone-50 p-3">
                      <p className="text-xs font-medium text-stone-500">时代背景</p>
                      <p className="mt-2 text-sm text-stone-700">{data.world_blueprint_summary.era_context || '未填写'}</p>
                    </div>
                    <div className="rounded-lg bg-stone-50 p-3">
                      <p className="text-xs font-medium text-stone-500">社会秩序</p>
                      <p className="mt-2 text-sm text-stone-700">{data.world_blueprint_summary.social_order || '未填写'}</p>
                    </div>
                  </div>
                </section>

                <section className="rounded-xl border border-gray-200 bg-white p-5 space-y-4">
                  <h3 className="text-sm font-semibold text-gray-900">力量体系</h3>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-lg bg-stone-50 p-3">
                      <p className="text-xs font-medium text-stone-500">核心机制</p>
                      <p className="mt-2 text-sm text-stone-700">{data.world_blueprint_summary.power_system.core_mechanics || '未填写'}</p>
                    </div>
                    <div className="rounded-lg bg-stone-50 p-3">
                      <p className="text-xs font-medium text-stone-500">代价</p>
                      <p className="mt-2 text-sm text-stone-700">{data.world_blueprint_summary.power_system.costs.join('；') || '未填写'}</p>
                    </div>
                    <div className="rounded-lg bg-stone-50 p-3">
                      <p className="text-xs font-medium text-stone-500">限制</p>
                      <p className="mt-2 text-sm text-stone-700">{data.world_blueprint_summary.power_system.limitations.join('；') || '未填写'}</p>
                    </div>
                    <div className="rounded-lg bg-stone-50 p-3">
                      <p className="text-xs font-medium text-stone-500">成长路径</p>
                      <p className="mt-2 text-sm text-stone-700">{data.world_blueprint_summary.power_system.advancement_path.join('；') || '未填写'}</p>
                    </div>
                  </div>
                </section>

                <section className="rounded-xl border border-gray-200 bg-white p-5 space-y-4">
                  <h3 className="text-sm font-semibold text-gray-900">势力结构</h3>
                  <div className="grid gap-4 md:grid-cols-2">
                    {data.world_blueprint_summary.factions.map((faction) => (
                      <article key={faction.name} className="rounded-lg border border-gray-200 p-4 space-y-2">
                        <div className="flex items-center justify-between gap-3">
                          <h4 className="text-sm font-semibold text-gray-900">{faction.name}</h4>
                          <span className="text-xs rounded bg-gray-100 px-2 py-0.5 text-gray-500">{faction.position || '未设定位阶'}</span>
                        </div>
                        <p className="text-sm text-gray-700">目标：{faction.goal || '未填写'}</p>
                        <p className="text-xs text-gray-500">公开形象：{faction.public_image || '未填写'}</p>
                        <p className="text-xs text-amber-700">隐藏真相：{faction.hidden_truth || '未填写'}</p>
                        <p className="text-xs text-gray-500">常用手段：{faction.methods.join('；') || '未填写'}</p>
                      </article>
                    ))}
                  </div>
                </section>

                <section className="grid gap-4 lg:grid-cols-2">
                  <div className="rounded-xl border border-gray-200 bg-white p-5 space-y-3">
                    <h3 className="text-sm font-semibold text-gray-900">不可变规则</h3>
                    <div className="space-y-3">
                      {data.world_blueprint_summary.immutable_rules.map((rule) => (
                        <div key={rule.key} className="rounded-lg bg-red-50 p-3 space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="rounded bg-red-100 px-2 py-0.5 text-xs text-red-600">不可变</span>
                            <span className="text-xs text-gray-500">{rule.category}</span>
                          </div>
                          <p className="text-sm font-medium text-gray-900">{rule.key}</p>
                          <p className="text-sm text-gray-700">{rule.description}</p>
                          <p className="text-xs text-gray-500">存在理由：{rule.rationale || '未填写'}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-xl border border-gray-200 bg-white p-5 space-y-3">
                    <h3 className="text-sm font-semibold text-gray-900">禁忌规则</h3>
                    <div className="space-y-3">
                      {data.world_blueprint_summary.taboo_rules.map((rule) => (
                        <div key={rule.key} className="rounded-lg bg-amber-50 p-3 space-y-1">
                          <p className="text-sm font-medium text-gray-900">{rule.key}</p>
                          <p className="text-sm text-gray-700">{rule.description}</p>
                          <p className="text-xs text-amber-700">触犯后果：{rule.consequence || '未填写'}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </section>

                <section className="grid gap-4 lg:grid-cols-2">
                  <div className="rounded-xl border border-gray-200 bg-white p-5">
                    <h3 className="text-sm font-semibold text-gray-900">关键地点</h3>
                    <div className="mt-3 space-y-3">
                      {data.world_blueprint_summary.geography.map((location) => (
                        <div key={location.name} className="rounded-lg bg-stone-50 p-3">
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-sm font-medium text-gray-900">{location.name}</p>
                            <span className="text-xs text-gray-500">{location.role || '未设功能'}</span>
                          </div>
                          <p className="mt-2 text-sm text-gray-700">{location.description || '未填写'}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-xl border border-gray-200 bg-white p-5 space-y-4">
                    <div>
                      <h3 className="text-sm font-semibold text-gray-900">历史伤痕</h3>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {data.world_blueprint_summary.historical_wounds.map((item) => (
                          <span key={item} className="rounded-full bg-rose-50 px-2.5 py-1 text-xs text-rose-700">{item}</span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-gray-900">公开秘密</h3>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {data.world_blueprint_summary.public_secrets.map((item) => (
                          <span key={item} className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs text-indigo-700">{item}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                </section>
              </div>
            )}
          </div>
        )}

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

        {activeTab === 'relationship_graph' && (
          <div>
            {!data?.relationship_graph?.length ? (
              <EmptyState text="当前还没有人物关系图谱，请先在人物蓝图阶段确认关系网。" />
            ) : (
              <div className="space-y-4">
                <RelationshipGraphPanel
                  nodes={relationshipGraphView.nodes}
                  edges={relationshipGraphView.edges}
                  selection={graphSelection}
                  onSelectionChange={setGraphSelection}
                  readOnly
                />
                <div className="grid gap-4 md:grid-cols-2">
                  {data.relationship_graph.map((edge) => (
                    <article key={edge.edge_id} className="rounded-xl border border-gray-200 bg-white p-4 space-y-2">
                      <div className="flex items-center justify-between gap-3">
                        <h3 className="text-sm font-semibold text-gray-900">
                          {edge.source_character_id} → {edge.target_character_id}
                        </h3>
                        <span className="rounded bg-stone-100 px-2 py-0.5 text-xs text-stone-600">{edge.relation_type}</span>
                      </div>
                      <div className="flex flex-wrap gap-2 text-xs">
                        <span className="rounded bg-sky-50 px-2 py-0.5 text-sky-700">倾向：{edge.polarity}</span>
                        <span className="rounded bg-violet-50 px-2 py-0.5 text-violet-700">公开度：{edge.visibility}</span>
                        <span className="rounded bg-amber-50 px-2 py-0.5 text-amber-700">稳定性：{edge.stability}</span>
                        <span className="rounded bg-gray-100 px-2 py-0.5 text-gray-600">强度：{edge.intensity}</span>
                      </div>
                      <p className="text-sm text-gray-700">{edge.summary || '未填写关系摘要'}</p>
                      {edge.hidden_truth && (
                        <p className="text-xs text-amber-700">隐藏真相：{edge.hidden_truth}</p>
                      )}
                      {edge.non_breakable_without_reveal && (
                        <p className="text-xs text-red-600">这条关系需要通过“揭示事件”才能被合法改写。</p>
                      )}
                    </article>
                  ))}
                </div>
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
