/**
 * 创作工作台主入口：
 * 与作品库页解耦后，这里只负责“选择当前作品 + 加载蓝图工作台”。
 */
import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { BookOpenText, Sparkles } from 'lucide-react'
import { BookBlueprintWorkspace } from '@/components/BookBlueprintWorkspace'
import { ErrorMessage, LoadingSpinner } from '@/components/Feedback'
import { useActiveBook, resolveActiveBookId } from '@/contexts/ActiveBookContext'
import { formatLanguageLabel, formatStylePresetLabel } from '@/lib/display-labels'
import { fetchBookBlueprint, fetchBooks } from '@/services/books'
import type { BookItem } from '@/types'

export default function WorkspacePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { activeBookId, setActiveBookId } = useActiveBook()

  const { data: books = [], isLoading: booksLoading, error: booksError } = useQuery<BookItem[]>({
    queryKey: ['books'],
    queryFn: fetchBooks,
    staleTime: 30_000,
  })

  const resolvedBookId = resolveActiveBookId(activeBookId, books)

  const {
    data: blueprint,
    isLoading: blueprintLoading,
    error: blueprintError,
  } = useQuery({
    queryKey: ['bookBlueprint', resolvedBookId],
    queryFn: () => fetchBookBlueprint(resolvedBookId),
    enabled: books.length > 0 && resolvedBookId > 0,
  })

  useEffect(() => {
    /**
     * 工作台页采用“query 参数优先，其次回退到全局当前作品”的策略：
     * 1. 允许从作品库通过 `/workspace?book=...` 精确跳转；
     * 2. 没有 query 时，继续沿用左侧导航共享的当前作品；
     * 3. 最终结果会同步回 query，保证刷新后地址仍能表达当前上下文。
     */
    if (books.length === 0) {
      return
    }
    const fromQuery = Number(searchParams.get('book') || '')
    const targetBookId =
      Number.isFinite(fromQuery) && fromQuery > 0 ? resolveActiveBookId(fromQuery, books) : resolvedBookId

    if (targetBookId !== activeBookId) {
      setActiveBookId(targetBookId)
      return
    }
    if (searchParams.get('book') !== String(targetBookId)) {
      setSearchParams({ book: String(targetBookId) }, { replace: true })
    }
  }, [activeBookId, books, resolvedBookId, searchParams, setActiveBookId, setSearchParams])

  if (booksLoading) {
    return <LoadingSpinner text="加载作品工作台中…" />
  }
  if (booksError) {
    return <ErrorMessage message={(booksError as Error).message} />
  }
  if (books.length === 0) {
    return (
      <section className="rounded-3xl border border-stone-200 bg-white p-8 shadow-sm">
        <div className="flex items-start gap-4">
          <div className="rounded-2xl bg-emerald-50 p-3 text-emerald-600">
            <Sparkles className="h-6 w-6" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-stone-900">还没有可用作品</h2>
            <p className="mt-2 text-sm leading-6 text-stone-600">
              先到“作品库”创建一本作品，再回到这里进入蓝图驱动写作工作台。
            </p>
          </div>
        </div>
      </section>
    )
  }
  if (blueprintLoading) {
    return <LoadingSpinner text="加载创作蓝图中…" />
  }
  if (blueprintError) {
    return <ErrorMessage message={(blueprintError as Error).message} />
  }

  const activeBook = books.find((item) => item.id === resolvedBookId) ?? books[0]!

  return (
    <div className="space-y-5">
      <section className="rounded-[28px] border border-stone-200 bg-white px-6 py-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
              <BookOpenText className="h-3.5 w-3.5" />
              蓝图驱动写作主工作台
            </div>
            <h2 className="mt-3 text-2xl font-semibold text-stone-900">围绕当前作品逐层推进整书蓝图</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-stone-600">
              这里承接创作意图、候选方向、世界观、人物、关系图谱、章节路线与连续性校对。
              页面外的“章节总览”和“设定总览”仅作为资产页，不再承担主流程。
            </p>
          </div>
          <div className="min-w-[280px] rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3">
            <label className="block text-xs font-medium uppercase tracking-[0.18em] text-stone-500">
              当前作品
            </label>
            <select
              value={resolvedBookId}
              onChange={(event) => {
                const nextBookId = Number(event.target.value)
                setActiveBookId(nextBookId)
                setSearchParams({ book: String(nextBookId) }, { replace: true })
              }}
              className="mt-2 w-full rounded-xl border border-stone-300 bg-white px-3 py-2.5 text-sm text-stone-800"
            >
              {books.map((book) => (
                <option key={book.id} value={book.id}>
                  {book.name}（{formatLanguageLabel(book.language)} / {formatStylePresetLabel(book.style_preset)}）
                </option>
              ))}
            </select>
            <p className="mt-2 text-xs text-stone-500">
              当前书名：{activeBook.name} · 文风：{formatStylePresetLabel(activeBook.style_preset)}
            </p>
          </div>
        </div>
      </section>

      <BookBlueprintWorkspace bookId={resolvedBookId} blueprint={blueprint} activeBook={activeBook} />
    </div>
  )
}
