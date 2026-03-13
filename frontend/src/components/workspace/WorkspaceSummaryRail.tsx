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
      <section className="rounded-[28px] border border-stone-200 bg-white p-5 shadow-sm">
        <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-stone-400">上下文摘要</p>
        <h3 className="mt-3 text-base font-semibold text-stone-900">{title}</h3>
        <p className="mt-2 text-sm leading-6 text-stone-600">{description}</p>
      </section>
      <div className="space-y-4">{children}</div>
    </aside>
  )
}

