/**
 * 统计分析页：章节状态分布、各章字数对比图
 */
import { useQuery } from '@tanstack/react-query'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts'
import { fetchChapters } from '@/services/chapters'
import { LoadingSpinner, ErrorMessage, EmptyState } from '@/components/Feedback'
import { chapterStatusLabel } from '@/lib/utils'

/** 饼图颜色 */
const PIE_COLORS = ['#6366f1', '#22c55e', '#f59e0b', '#ef4444']

export default function Stats() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['chapters'],
    queryFn: fetchChapters,
  })

  if (isLoading) return <LoadingSpinner text="加载统计数据…" />
  if (error) return <ErrorMessage message={(error as Error).message} />
  if (!data || data.length === 0) return <EmptyState text="暂无章节数据" />

  // 字数柱状图数据
  const barData = data
    .slice()
    .sort((a, b) => a.chapter_number - b.chapter_number)
    .map((c) => ({ name: `第${c.chapter_number}章`, words: c.word_count }))

  // 状态饼图数据
  const statusMap = new Map<string, number>()
  for (const chapter of data) {
    statusMap.set(chapter.status, (statusMap.get(chapter.status) ?? 0) + 1)
  }
  const pieData = Array.from(statusMap.entries()).map(([status, count]) => ({
    name: chapterStatusLabel[status] ?? status,
    value: count,
  }))

  // 平均字数
  const avgWords = Math.round(data.reduce((s, c) => s + c.word_count, 0) / data.length)

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-gray-800">统计分析</h2>

      {/* 汇总数字 */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: '总章节数', value: data.length },
          { label: '平均字数', value: `${avgWords}字` },
          { label: '总字数', value: `${data.reduce((s, c) => s + c.word_count, 0).toLocaleString()}字` },
        ].map((item) => (
          <div key={item.label} className="bg-white rounded-xl border border-gray-200 p-4 text-center">
            <p className="text-xs text-gray-500">{item.label}</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">{item.value}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* 各章字数柱状图 */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">各章字数</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={barData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#6b7280' }} />
              <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} />
              <Tooltip formatter={(v) => [`${v ?? 0} 字`, '字数']} />
              <Bar dataKey="words" fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* 章节状态分布饼图 */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">章节状态分布</h3>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={90}
                paddingAngle={3}
                dataKey="value"
                label={({ name, percent }: { name?: string; percent?: number }) =>
                  `${name ?? ''} ${((percent ?? 0) * 100).toFixed(0)}%`
                }
                labelLine={false}
              >
                {pieData.map((_, index) => (
                  <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Legend />
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
