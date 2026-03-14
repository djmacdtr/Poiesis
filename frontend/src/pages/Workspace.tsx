/**
 * 创作工作台主入口：
 * 与作品库页解耦后，这里只负责“选择当前作品 + 加载蓝图工作台”。
 */
import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { BookBlueprintWorkspace } from '@/components/BookBlueprintWorkspace'
import { ErrorMessage, LoadingSpinner } from '@/components/Feedback'
import { WorkspaceTopStatusBar } from '@/components/workspace/WorkspaceTopStatusBar'
import { useActiveBook, resolveActiveBookId } from '@/contexts/ActiveBookContext'
import { formatBlueprintStatusLabel, formatBlueprintStepLabel, formatLanguageLabel, formatStylePresetLabel } from '@/lib/display-labels'
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
  if (!blueprint) {
    return <LoadingSpinner text="整理当前作品工作台中…" />
  }

  const activeBook = books.find((item) => item.id === resolvedBookId) ?? books[0]!
  const fatalCount = blueprint.roadmap_validation_issues.filter((item) => item.severity === 'fatal').length
  const warningCount = blueprint.roadmap_validation_issues.filter((item) => item.severity === 'warning').length
  const pendingRepairCount = blueprint.creative_repair_proposals.filter((item) => item.status === 'awaiting_approval').length

  return (
    <div className="space-y-5">
      <WorkspaceTopStatusBar
        bookOptions={books.map((book) => ({
          id: book.id,
          name: book.name,
          languageLabel: formatLanguageLabel(book.language),
          styleLabel: formatStylePresetLabel(book.style_preset),
        }))}
        activeBookName={activeBook.name}
        activeBookStyleLabel={formatStylePresetLabel(activeBook.style_preset)}
        activeBookId={resolvedBookId}
        blueprintStatusLabel={formatBlueprintStatusLabel(blueprint.status)}
        blueprintStepLabel={formatBlueprintStepLabel(blueprint.current_step)}
        fatalCount={fatalCount}
        warningCount={warningCount}
        pendingRepairCount={pendingRepairCount}
        onSelectBook={(nextBookId) => {
          setActiveBookId(nextBookId)
          setSearchParams({ book: String(nextBookId) }, { replace: true })
        }}
      />

      <BookBlueprintWorkspace bookId={resolvedBookId} blueprint={blueprint} activeBook={activeBook} />
    </div>
  )
}
