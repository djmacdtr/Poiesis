/**
 * 工作台右侧摘要栏：
 * 固定承接“当前步骤摘要 + 上下文 inspector”，让中间主区保持专注，
 * 同时避免把连续性、校验问题、对象细节都堆回主区。
 */
import type { ReactNode } from 'react'

interface WorkspaceSummaryRailProps {
  title: string
  description: string
  children: ReactNode
}

export function WorkspaceSummaryRail({ title, description, children }: WorkspaceSummaryRailProps) {
  return (
    <aside className="space-y-4">
      <section className="rounded-[24px] border border-stone-200 bg-white px-4 py-3 shadow-sm">
        <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-stone-400">Inspector</p>
        <h3 className="mt-2 text-sm font-semibold text-stone-900">{title}</h3>
        <p className="mt-1 text-xs leading-5 text-stone-600">{description}</p>
      </section>
      <div className="space-y-4">{children}</div>
    </aside>
  )
}
