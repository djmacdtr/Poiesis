/**
 * 工作台顶部状态条：
 * 把原先占首屏很高的大说明卡压缩成“当前作品 + 关键状态 + 快捷切书”的窄条，
 * 让作者进入 /workspace 后更快看到真正的主工作区。
 */
import { BookOpenText, GitBranchPlus, ShieldAlert, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'

interface WorkspaceTopStatusBarProps {
  bookOptions: Array<{
    id: number
    name: string
    languageLabel: string
    styleLabel: string
  }>
  activeBookName: string
  activeBookStyleLabel: string
  activeBookId: number
  blueprintStatusLabel: string
  blueprintStepLabel: string
  fatalCount: number
  warningCount: number
  pendingRepairCount: number
  onSelectBook: (bookId: number) => void
}

function statusToneClassName(fatalCount: number, warningCount: number): string {
  if (fatalCount > 0) return 'border-rose-200 bg-rose-50 text-rose-700'
  if (warningCount > 0) return 'border-amber-200 bg-amber-50 text-amber-700'
  return 'border-emerald-200 bg-emerald-50 text-emerald-700'
}

export function WorkspaceTopStatusBar({
  bookOptions,
  activeBookName,
  activeBookStyleLabel,
  activeBookId,
  blueprintStatusLabel,
  blueprintStepLabel,
  fatalCount,
  warningCount,
  pendingRepairCount,
  onSelectBook,
}: WorkspaceTopStatusBarProps) {
  return (
    <section className="rounded-[24px] border border-stone-200 bg-white px-5 py-4 shadow-sm">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <div className="rounded-2xl bg-emerald-50 p-2.5 text-emerald-700">
            <Sparkles className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-semibold text-stone-900">{activeBookName}</p>
              <span className="rounded-full bg-stone-100 px-2 py-1 text-[11px] font-medium text-stone-600">
                {activeBookStyleLabel}
              </span>
            </div>
            <p className="mt-1 text-xs text-stone-500">蓝图驱动写作主工作台</p>
          </div>
        </div>

        <div className="flex flex-1 flex-wrap items-center gap-2 xl:justify-center">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-stone-200 bg-stone-50 px-3 py-1.5 text-xs font-medium text-stone-700">
            <BookOpenText className="h-3.5 w-3.5" />
            当前状态：{blueprintStatusLabel}
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-stone-200 bg-stone-50 px-3 py-1.5 text-xs font-medium text-stone-700">
            <GitBranchPlus className="h-3.5 w-3.5" />
            当前步骤：{blueprintStepLabel}
          </span>
          <span
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium',
              statusToneClassName(fatalCount, warningCount),
            )}
          >
            <ShieldAlert className="h-3.5 w-3.5" />
            {fatalCount > 0 ? `${fatalCount} 个严重问题` : warningCount > 0 ? `${warningCount} 个提醒` : '当前无结构风险'}
          </span>
          {pendingRepairCount > 0 ? (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700">
              待确认修复 {pendingRepairCount}
            </span>
          ) : null}
        </div>

        <div className="min-w-[260px] xl:max-w-[320px] xl:flex-1">
          <label className="block text-[11px] font-semibold uppercase tracking-[0.18em] text-stone-400">
            当前作品
          </label>
          <select
            value={activeBookId}
            onChange={(event) => onSelectBook(Number(event.target.value))}
            className="mt-2 w-full rounded-xl border border-stone-300 bg-stone-50 px-3 py-2.5 text-sm text-stone-800"
          >
            {bookOptions.map((book) => (
              <option key={book.id} value={book.id}>
                {book.name}（{book.languageLabel} / {book.styleLabel}）
              </option>
            ))}
          </select>
        </div>
      </div>
    </section>
  )
}
