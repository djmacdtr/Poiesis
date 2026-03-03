/**
 * 字数趋势折线图组件（使用 recharts）
 */
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import type { WordCountDataPoint } from '@/types'

interface WordTrendChartProps {
  data: WordCountDataPoint[]
}

export function WordTrendChart({ data }: WordTrendChartProps) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis
          dataKey="chapter"
          tickFormatter={(v: number) => `第${v}章`}
          tick={{ fontSize: 12, fill: '#6b7280' }}
        />
        <YAxis tick={{ fontSize: 12, fill: '#6b7280' }} />
        <Tooltip
          formatter={(value) => [`${value ?? 0} 字`, '字数']}
          labelFormatter={(label) => `第 ${label} 章`}
        />
        <Line
          type="monotone"
          dataKey="words"
          stroke="#6366f1"
          strokeWidth={2}
          dot={{ r: 3, fill: '#6366f1' }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
