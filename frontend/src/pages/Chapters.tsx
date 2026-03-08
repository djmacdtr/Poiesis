/**
 * 章节列表页：展示所有章节的基本信息
 */
import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { fetchChaptersByBook } from '@/services/chapters'
import { fetchBooks } from '@/services/books'
import { LoadingSpinner, ErrorMessage, EmptyState } from '@/components/Feedback'
import { formatDate, formatWordCount, chapterStatusLabel } from '@/lib/utils'
import { cn } from '@/lib/utils'
import type { BookItem } from '@/types'

const ACTIVE_BOOK_ID_KEY = 'poiesis.activeBookId'

/** 状态徽章颜色 */
const statusColor: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-600',
  completed: 'bg-green-100 text-green-700',
  published: 'bg-indigo-100 text-indigo-700',
}

export default function Chapters() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [activeBookId, setActiveBookId] = useState<number>(() => {
    const fromQuery = Number(searchParams.get('book') || '')
    if (Number.isFinite(fromQuery) && fromQuery > 0) return fromQuery
    if (typeof window === 'undefined') return 1
    const raw = window.localStorage.getItem(ACTIVE_BOOK_ID_KEY)
    return raw ? Number(raw) || 1 : 1
  })

  const { data: books = [] } = useQuery<BookItem[]>({
    queryKey: ['books'],
    queryFn: fetchBooks,
    staleTime: 30_000,
  })

  const { data, isLoading, error } = useQuery({
    queryKey: ['chapters', activeBookId],
    queryFn: () => fetchChaptersByBook(activeBookId),
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

  if (isLoading) return <LoadingSpinner text="加载章节列表…" />
  if (error) return <ErrorMessage message={(error as Error).message} />
  if (!data || data.length === 0) return <EmptyState text="暂无章节，请先运行写作任务" />

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-gray-800">章节列表</h2>
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

      <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
        {data.map((chapter) => (
          <Link
            key={chapter.id}
            to={`/chapters/${chapter.id}?book=${activeBookId}`}
            className="flex items-center gap-4 px-5 py-4 hover:bg-gray-50 transition-colors group"
          >
            {/* 章节序号 */}
            <div className="w-10 h-10 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600 text-sm font-bold shrink-0">
              {chapter.chapter_number}
            </div>

            {/* 标题与元信息 */}
            <div className="flex-1 min-w-0">
              <p className="font-medium text-gray-800 truncate">{chapter.title || `第 ${chapter.chapter_number} 章`}</p>
              <p className="text-xs text-gray-400 mt-0.5">
                {formatWordCount(chapter.word_count)} · 更新于 {formatDate(chapter.updated_at)}
              </p>
            </div>

            {/* 状态徽章 */}
            <span className={cn('text-xs font-medium px-2 py-0.5 rounded-full shrink-0', statusColor[chapter.status] ?? 'bg-gray-100 text-gray-600')}>
              {chapterStatusLabel[chapter.status] ?? chapter.status}
            </span>

            <ChevronRight className="w-4 h-4 text-gray-300 shrink-0 group-hover:text-gray-500 transition-colors" />
          </Link>
        ))}
      </div>
    </div>
  )
}
