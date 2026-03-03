/**
 * 仪表盘页：展示写作进度概览、字数趋势图
 */
import { useQuery } from '@tanstack/react-query'
import {
  BookOpen,
  FileText,
  GitPullRequest,
  Users,
  Bookmark,
} from 'lucide-react'
import { StatCard } from '@/components/StatCard'
import { WordTrendChart } from '@/components/WordTrendChart'
import { LoadingSpinner, ErrorMessage } from '@/components/Feedback'
import { fetchDashboardStats, fetchWordCountTrend } from '@/services/stats'
import { formatWordCount } from '@/lib/utils'

export default function Dashboard() {
  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
  } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: fetchDashboardStats,
    refetchInterval: 30_000,
  })

  const {
    data: trend,
    isLoading: trendLoading,
  } = useQuery({
    queryKey: ['word-trend'],
    queryFn: fetchWordCountTrend,
    refetchInterval: 30_000,
  })

  if (statsLoading) return <LoadingSpinner text="加载统计数据…" />
  if (statsError) return <ErrorMessage message={(statsError as Error).message} />

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-gray-800">总览</h2>

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
          title="待审批变更"
          value={stats?.pendingStagingCount ?? 0}
          description="Staging 候选"
          icon={<GitPullRequest className="w-5 h-5" />}
        />
        <StatCard
          title="已注册角色"
          value={stats?.characterCount ?? 0}
          icon={<Users className="w-5 h-5" />}
        />
        <StatCard
          title="活跃伏笔"
          value={stats?.activeForeshadowingCount ?? 0}
          icon={<Bookmark className="w-5 h-5" />}
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
