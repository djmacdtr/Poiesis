/**
 * Staging 候选审批页：审批或拒绝待处理的世界设定变更
 */
import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Check, X } from 'lucide-react'
import { toast } from 'sonner'
import { fetchStaging, approveStaging, rejectStaging } from '@/services/world'
import { fetchBooks } from '@/services/books'
import { LoadingSpinner, ErrorMessage, EmptyState } from '@/components/Feedback'
import { PromptModal } from '@/components/PromptModal'
import { formatDate, stagingStatusLabel } from '@/lib/utils'
import { cn } from '@/lib/utils'
import type { BookItem, StagingFilter } from '@/types'

/** 过滤选项 */
const filterOptions: { value: StagingFilter; label: string }[] = [
  { value: 'pending', label: '待审批' },
  { value: 'approved', label: '已通过' },
  { value: 'rejected', label: '已拒绝' },
  { value: 'all', label: '全部' },
]

/** 状态颜色 */
const statusColor: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-700',
  approved: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
}
const ACTIVE_BOOK_ID_KEY = 'poiesis.activeBookId'

export default function Staging() {
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [filter, setFilter] = useState<StagingFilter>('pending')
  const [activeBookId, setActiveBookId] = useState<number>(() => {
    const fromQuery = Number(searchParams.get('book') || '')
    if (Number.isFinite(fromQuery) && fromQuery > 0) return fromQuery
    if (typeof window === 'undefined') return 1
    const raw = window.localStorage.getItem(ACTIVE_BOOK_ID_KEY)
    return raw ? Number(raw) || 1 : 1
  })
  /** 拒绝对话框状态 */
  const [rejectId, setRejectId] = useState<number | null>(null)
  const [rejectReason, setRejectReason] = useState('')

  const { data: books = [] } = useQuery<BookItem[]>({
    queryKey: ['books'],
    queryFn: fetchBooks,
    staleTime: 30_000,
  })

  const { data, isLoading, error } = useQuery({
    queryKey: ['staging', filter, activeBookId],
    queryFn: () => fetchStaging(filter, activeBookId),
  })

  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(ACTIVE_BOOK_ID_KEY, String(activeBookId))
    setSearchParams({ book: String(activeBookId) }, { replace: true })
  }, [activeBookId, setSearchParams])

  useEffect(() => {
    if (books.length === 0) return
    const exists = books.some((item) => item.id === activeBookId)
    if (exists) return
    const next = books.find((item) => item.is_default)?.id ?? books[0].id
    setActiveBookId(next)
  }, [activeBookId, books])

  const approveMutation = useMutation({
    mutationFn: (id: number) => approveStaging(id),
    onSuccess: () => {
      toast.success('已审批通过')
      void queryClient.invalidateQueries({ queryKey: ['staging'] })
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) => rejectStaging(id, reason),
    onSuccess: () => {
      toast.success('已拒绝该变更')
      setRejectId(null)
      setRejectReason('')
      void queryClient.invalidateQueries({ queryKey: ['staging'] })
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const handleRejectSubmit = () => {
    if (!rejectId) return
    if (!rejectReason.trim()) {
      toast.error('请输入拒绝原因')
      return
    }
    rejectMutation.mutate({ id: rejectId, reason: rejectReason })
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-gray-800">候选审批（Staging）</h2>
        <select
          value={activeBookId}
          onChange={(e) => setActiveBookId(Number(e.target.value))}
          className="min-w-56 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 bg-white"
        >
          {books.map((book) => (
            <option key={book.id} value={book.id}>
              {book.name}（{book.language} / {book.style_preset}）
            </option>
          ))}
        </select>
      </div>

      {/* 过滤标签 */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit">
        {filterOptions.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setFilter(opt.value)}
            className={cn(
              'px-4 py-1.5 text-sm rounded-md font-medium transition-colors',
              filter === opt.value
                ? 'bg-white text-indigo-600 shadow-sm'
                : 'text-gray-600 hover:text-gray-900',
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* 内容区 */}
      {isLoading && <LoadingSpinner text="加载候选变更…" />}
      {error && <ErrorMessage message={(error as Error).message} />}
      {!isLoading && !error && (!data || data.length === 0) && (
        <EmptyState text="该状态下暂无候选变更" />
      )}

      {data && data.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
          {data.map((item) => (
            <div key={item.id} className="px-5 py-4 space-y-3">
              {/* 头部 */}
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-800">{item.entity_type}</span>
                    <span className="text-xs font-mono text-gray-400">{item.entity_key}</span>
                    <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">{item.change_type}</span>
                  </div>
                  <p className="text-xs text-gray-400">
                    {item.source_chapter != null && `来源：第 ${item.source_chapter} 章 · `}
                    {formatDate(item.created_at)}
                  </p>
                </div>

                <span className={cn('text-xs font-medium px-2 py-0.5 rounded-full shrink-0', statusColor[item.status] ?? 'bg-gray-100 text-gray-600')}>
                  {stagingStatusLabel[item.status] ?? item.status}
                </span>
              </div>

              {/* 提议数据预览 */}
              <pre className="bg-gray-50 rounded-lg p-3 text-xs text-gray-600 overflow-x-auto max-h-32 overflow-y-auto">
                {JSON.stringify(item.proposed_data, null, 2)}
              </pre>

              {/* 拒绝原因 */}
              {item.rejection_reason && (
                <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg">
                  拒绝原因：{item.rejection_reason}
                </p>
              )}

              {/* 操作按钮（仅 pending 状态可操作） */}
              {item.status === 'pending' && (
                <div className="flex gap-2">
                  <button
                    onClick={() => approveMutation.mutate(item.id)}
                    disabled={approveMutation.isPending}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white text-xs rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
                  >
                    <Check className="w-3.5 h-3.5" />
                    通过
                  </button>
                  <button
                    onClick={() => { setRejectId(item.id); setRejectReason('') }}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-red-50 text-red-600 text-xs rounded-lg hover:bg-red-100 transition-colors"
                  >
                    <X className="w-3.5 h-3.5" />
                    拒绝
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <PromptModal
        open={rejectId !== null}
        title="拒绝候选变更"
        description="请输入拒绝原因，便于后续追溯该变更为何未通过。"
        value={rejectReason}
        placeholder="请输入拒绝原因（必填）"
        confirmText="确认拒绝"
        cancelText="取消"
        loading={rejectMutation.isPending}
        onChange={setRejectReason}
        onConfirm={handleRejectSubmit}
        onCancel={() => {
          setRejectId(null)
          setRejectReason('')
        }}
      />
    </div>
  )
}
