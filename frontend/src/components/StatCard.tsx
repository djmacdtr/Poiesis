/**
 * 统计卡片组件
 */
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface StatCardProps {
  /** 卡片标题 */
  title: string
  /** 主要数值 */
  value: string | number
  /** 描述文字 */
  description?: string
  /** 图标 */
  icon?: ReactNode
  /** 额外样式 */
  className?: string
}

export function StatCard({ title, value, description, icon, className }: StatCardProps) {
  return (
    <div className={cn('bg-white rounded-xl border border-gray-200 p-5 flex gap-4', className)}>
      {icon && (
        <div className="shrink-0 w-10 h-10 bg-indigo-50 rounded-lg flex items-center justify-center text-indigo-600">
          {icon}
        </div>
      )}
      <div className="min-w-0">
        <p className="text-sm text-gray-500 truncate">{title}</p>
        <p className="text-2xl font-bold text-gray-900 mt-0.5">{value}</p>
        {description && <p className="text-xs text-gray-400 mt-1">{description}</p>}
      </div>
    </div>
  )
}
