/**
 * 工作台左侧步骤导航：
 * 这里只承载页内 IA，不处理业务逻辑，所有状态来源都由外层工作台统一下发。
 */
import { cn } from '@/lib/utils'

export type WorkspaceSectionKey =
  | 'overview'
  | 'intent'
  | 'concept'
  | 'world'
  | 'characters'
  | 'relationships'
  | 'roadmap'
  | 'continuity'
  | 'settings'

export interface WorkspaceSidebarItem {
  key: WorkspaceSectionKey
  label: string
  description: string
  statusLabel: string
  tone: 'ready' | 'pending' | 'warning' | 'danger'
  dirty?: boolean
  blocked?: boolean
}

interface WorkspaceSidebarProps {
  items: WorkspaceSidebarItem[]
  activeKey: WorkspaceSectionKey
  onChange: (nextKey: WorkspaceSectionKey) => void
}

const toneClassName: Record<WorkspaceSidebarItem['tone'], string> = {
  ready: 'bg-emerald-50 text-emerald-700',
  pending: 'bg-stone-100 text-stone-600',
  warning: 'bg-amber-50 text-amber-700',
  danger: 'bg-rose-50 text-rose-700',
}

export function WorkspaceSidebar({ items, activeKey, onChange }: WorkspaceSidebarProps) {
  return (
    <aside className="rounded-[28px] border border-stone-200 bg-white p-4 shadow-sm">
      <div className="border-b border-stone-200 px-2 pb-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-stone-400">工作台导航</p>
        <p className="mt-2 text-sm leading-6 text-stone-600">
          用固定步骤把蓝图工作流拆开，避免世界观、人物、路线和连续性同时挤在一页里。
        </p>
      </div>

      <div className="mt-4 space-y-2">
        {items.map((item) => {
          const isActive = item.key === activeKey
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => onChange(item.key)}
              className={cn(
                'w-full rounded-2xl border px-4 py-3 text-left transition-all',
                isActive
                  ? 'border-emerald-200 bg-emerald-50/80 shadow-sm'
                  : 'border-transparent bg-stone-50 hover:border-stone-200 hover:bg-white',
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-stone-900">{item.label}</p>
                  <p className="mt-1 text-xs leading-5 text-stone-500">{item.description}</p>
                </div>
                <span className={cn('shrink-0 rounded-full px-2 py-1 text-[11px] font-medium', toneClassName[item.tone])}>
                  {item.statusLabel}
                </span>
              </div>
              {(item.dirty || item.blocked) && (
                <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                  {item.dirty ? (
                    <span className="rounded-full bg-white px-2 py-1 text-amber-700">有未保存修改</span>
                  ) : null}
                  {item.blocked ? (
                    <span className="rounded-full bg-white px-2 py-1 text-stone-600">受前序阶段阻塞</span>
                  ) : null}
                </div>
              )}
            </button>
          )
        })}
      </div>
    </aside>
  )
}

