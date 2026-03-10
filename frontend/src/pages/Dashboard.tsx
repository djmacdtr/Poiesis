/**
 * 仪表盘页：展示写作进度概览、字数趋势图
 */
import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import {
  BookOpen,
  FileText,
  GitPullRequest,
  Users,
  Orbit,
} from 'lucide-react'
import { StatCard } from '@/components/StatCard'
import { WordTrendChart } from '@/components/WordTrendChart'
import { LoadingSpinner, ErrorMessage } from '@/components/Feedback'
import { fetchDashboardStats, fetchWordCountTrend } from '@/services/stats'
import { fetchBooks } from '@/services/books'
import { formatWordCount } from '@/lib/utils'
import type { BookItem } from '@/types'

const ACTIVE_BOOK_ID_KEY = 'poiesis.activeBookId'

export default function Dashboard() {
  const [activeBookId, setActiveBookId] = useState<number>(() => {
    if (typeof window === 'undefined') return 1
    const raw = window.localStorage.getItem(ACTIVE_BOOK_ID_KEY)
    return raw ? Number(raw) || 1 : 1
  })

  const { data: books = [] } = useQuery<BookItem[]>({
    queryKey: ['books'],
    queryFn: fetchBooks,
    staleTime: 30_000,
  })

  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
  } = useQuery({
    queryKey: ['dashboard-stats', activeBookId],
    queryFn: () => fetchDashboardStats(activeBookId),
    refetchInterval: 30_000,
  })

  const {
    data: trend,
    isLoading: trendLoading,
  } = useQuery({
    queryKey: ['word-trend', activeBookId],
    queryFn: () => fetchWordCountTrend(activeBookId),
    refetchInterval: 30_000,
  })

  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(ACTIVE_BOOK_ID_KEY, String(activeBookId))
  }, [activeBookId])

  useEffect(() => {
    if (books.length === 0) return
    const exists = books.some((item) => item.id === activeBookId)
    if (exists) return
    const next = books.find((item) => item.is_default)?.id ?? books[0].id
    setActiveBookId(next)
  }, [activeBookId, books])

  if (statsLoading) return <LoadingSpinner text="加载统计数据…" />
  if (statsError) return <ErrorMessage message={(statsError as Error).message} />

  const formatLanguage = (language: string) => {
    if (language === 'zh-CN') return '中文'
    if (language === 'en-US') return '英文'
    return language
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-gray-800">总览</h2>
        <select
          value={activeBookId}
          onChange={(e) => setActiveBookId(Number(e.target.value))}
          className="min-w-56 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 bg-white"
        >
          {books.map((book) => (
            <option key={book.id} value={book.id}>
              {book.name}（{formatLanguage(book.language)} / {book.style_preset}）
            </option>
          ))}
        </select>
      </div>

      {/* 统计卡片网格 */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard
          title="总章节数"
          value={stats?.totalChapters ?? 0}
          description={`已完成 ${stats?.completedChapters ?? 0} 章`}
          icon={<BookOpen className="w-5 h-5" />}
        />
        <StatCard
          title="总字数"
          value={formatWordCount(stats?.totalWords ?? 0)}
          icon={<FileText className="w-5 h-5" />}
        />
        <StatCard
          title="待处理审阅"
          value={stats?.pendingReviewCount ?? 0}
          description="需要人工接管的场景"
          icon={<GitPullRequest className="w-5 h-5" />}
        />
        <StatCard
          title="已注册角色"
          value={stats?.characterCount ?? 0}
          icon={<Users className="w-5 h-5" />}
        />
        <StatCard
          title="活跃剧情线索"
          value={stats?.activeLoopCount ?? 0}
          icon={<Orbit className="w-5 h-5" />}
        />
        <StatCard
          title="可发布章节"
          value={stats?.readyToPublishCount ?? 0}
          description="已完成审阅，可手动发布"
          icon={<BookOpen className="w-5 h-5" />}
        />
      </div>

      {/* 字数趋势图 */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">各章字数趋势</h3>
        {trendLoading ? (
          <LoadingSpinner text="加载图表…" />
        ) : (
          <WordTrendChart data={trend ?? []} />
        )}
      </div>
    </div>
  )
}
