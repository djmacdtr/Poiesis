/**
 * 场景化运行面板：启动任务、查看进度、跳转详情。
 */
import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { formatDateTime } from '@/lib/utils'
import { fetchBooks } from '@/services/books'
import { fetchSceneRuns, startSceneRun } from '@/services/run'
import type { BookItem, SceneRunSummary } from '@/types'

const runStatusLabel: Record<string, string> = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  interrupted: '已中断',
}

function formatLanguage(language: string): string {
  if (language === 'zh-CN') return '中文'
  if (language === 'en-US') return '英文'
  return language
}

export default function RunBoard() {
  const queryClient = useQueryClient()
  const [bookId, setBookId] = useState(1)
  const [chapterCount, setChapterCount] = useState(1)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const { data: books = [] } = useQuery<BookItem[]>({
    queryKey: ['books'],
    queryFn: fetchBooks,
  })

  const { data: runs = [] } = useQuery<SceneRunSummary[]>({
    queryKey: ['sceneRuns'],
    queryFn: fetchSceneRuns,
    refetchInterval: 3000,
  })

  const handleStart = async () => {
    setIsSubmitting(true)
    try {
      await startSceneRun(chapterCount, bookId)
      toast.success('场景化运行任务已启动')
      await queryClient.invalidateQueries({ queryKey: ['sceneRuns'] })
    } catch (error) {
      toast.error((error as Error).message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-stone-200 bg-white p-6 shadow-sm">
        <h2 className="text-xl font-semibold text-stone-900">运行面板</h2>
        <p className="mt-1 text-sm text-stone-500">新的主链以场景为一等实体，章节只作为聚合与发布层。</p>
        <div className="mt-5 grid gap-4 md:grid-cols-[1fr_160px_160px_auto]">
          <select
            value={bookId}
            onChange={(event) => setBookId(Number(event.target.value))}
            className="rounded-xl border border-stone-300 px-3 py-2 text-sm"
          >
            {books.map((book) => (
              <option key={book.id} value={book.id}>
                {book.name} / {formatLanguage(book.language)}
              </option>
            ))}
          </select>
          <input
            type="number"
            min={1}
            max={20}
            value={chapterCount}
            onChange={(event) => setChapterCount(Number(event.target.value))}
            className="rounded-xl border border-stone-300 px-3 py-2 text-sm"
          />
          <div className="rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-stone-600">
            默认自动通过，异常进入审阅
          </div>
          <button
            onClick={handleStart}
            disabled={isSubmitting}
            className="rounded-xl bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800 disabled:opacity-50"
          >
            {isSubmitting ? '启动中…' : '启动任务'}
          </button>
        </div>
      </section>

      <section className="rounded-2xl border border-stone-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-stone-700">运行列表</h3>
          <span className="text-xs text-stone-500">会持续刷新状态</span>
        </div>
        <div className="mt-4 space-y-3">
          {runs.length === 0 && <p className="text-sm text-stone-500">当前还没有运行任务。</p>}
          {runs.map((run) => (
            <article key={run.id} className="rounded-xl border border-stone-200 p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-stone-900">任务 #{run.id}</p>
                  <p className="mt-1 text-xs text-stone-500">{run.task_id}</p>
                </div>
                <span className="rounded-full bg-stone-100 px-2.5 py-1 text-xs text-stone-700">
                  {runStatusLabel[run.status] ?? run.status}
                </span>
              </div>
              <div className="mt-3 grid gap-2 text-sm text-stone-600 md:grid-cols-3">
                <span>书籍：{run.book_id}</span>
                <span>
                  进度：{run.current_chapter}/{run.total_chapters}
                </span>
                <span>更新时间：{formatDateTime(run.updated_at)}</span>
              </div>
              {run.error_message && (
                <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{run.error_message}</p>
              )}
              <div className="mt-4 flex gap-2">
                <Link
                  to={`/runs/${run.id}`}
                  className="rounded-lg border border-stone-300 px-3 py-1.5 text-xs text-stone-700 hover:bg-stone-50"
                >
                  查看运行详情
                </Link>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}
