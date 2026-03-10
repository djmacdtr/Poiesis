/**
 * 通用状态徽章。
 */
import { cn } from '@/lib/utils'

interface StatusPillProps {
  label: string
  tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'info'
  className?: string
}

const toneMap: Record<NonNullable<StatusPillProps['tone']>, string> = {
  neutral: 'bg-stone-100 text-stone-700',
  success: 'bg-emerald-100 text-emerald-700',
  warning: 'bg-amber-100 text-amber-700',
  danger: 'bg-red-100 text-red-700',
  info: 'bg-sky-100 text-sky-700',
}

export function StatusPill({ label, tone = 'neutral', className }: StatusPillProps) {
  return (
    <span className={cn('rounded-full px-2.5 py-1 text-xs font-medium', toneMap[tone], className)}>
      {label}
    </span>
  )
}
