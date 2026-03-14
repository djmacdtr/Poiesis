/**
 * 工作台右侧控制栏：
 * 这里不再承担“长说明 + 全局摘要 + 多种对象表单混搭”的角色，
 * 而是统一作为 inspector 壳层，固定放全局状态摘要，再放当前选中对象的详情。
 */
import type { ReactNode } from 'react'
import { WorkspaceSummaryRail } from '@/components/workspace/WorkspaceSummaryRail'

interface WorkspaceInspectorRailProps {
  title: string
  description: string
  statusLabel: string
  revisionLabel: string
  fatalCount: number
  warningCount: number
  children: ReactNode
}

export function WorkspaceInspectorRail({
  title,
  description,
  statusLabel,
  revisionLabel,
  fatalCount,
  warningCount,
  children,
}: WorkspaceInspectorRailProps) {
  return (
    <WorkspaceSummaryRail title={title} description={description}>
      <section className="rounded-[24px] border border-stone-200 bg-white p-4 shadow-sm">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3">
            <p className="text-xs font-medium text-stone-500">当前状态</p>
            <p className="mt-2 text-sm font-semibold text-stone-900">{statusLabel}</p>
          </div>
          <div className="rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3">
            <p className="text-xs font-medium text-stone-500">生效版本</p>
            <p className="mt-2 text-sm font-semibold text-stone-900">{revisionLabel}</p>
          </div>
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3">
            <p className="text-xs font-medium text-rose-500">严重问题</p>
            <p className="mt-2 text-sm font-semibold text-rose-700">{fatalCount}</p>
          </div>
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
            <p className="text-xs font-medium text-amber-600">提醒</p>
            <p className="mt-2 text-sm font-semibold text-amber-700">{warningCount}</p>
          </div>
        </div>
      </section>
      {children}
    </WorkspaceSummaryRail>
  )
}
