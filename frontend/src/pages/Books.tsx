/**
 * 作品库 / 作品设置页：
 * 工作台已经迁移到独立的 /workspace，这里只负责作品资产管理与基础配置。
 */
import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, BookOpen, LibraryBig, Plus, Settings2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { BookCreateModal } from '@/components/BookCreateModal'
import { ErrorMessage, LoadingSpinner } from '@/components/Feedback'
import { useActiveBook, resolveActiveBookId } from '@/contexts/ActiveBookContext'
import { formatLanguageLabel, formatStylePresetLabel, formatNamingPolicyLabel } from '@/lib/display-labels'
import { createBook, fetchBooks, saveCreationIntent, updateBook } from '@/services/books'
import type { BookCreateWizardRequest, BookItem, BookUpsertRequest } from '@/types'

const STYLE_PRESETS: Array<{ value: string; label: string; prompt: string }> = [
  {
    value: 'webnovel_cn',
    label: '网文通俗风（节奏快）',
    prompt: '文风要求：节奏明快、冲突清晰、段落短促，结尾保留强钩子。',
  },
  {
    value: 'literary_cn',
    label: '文学细腻风（描写强）',
    prompt: '文风要求：注重意象与情绪层次，语言克制，细节具有审美密度。',
  },
  {
    value: 'neutral_cn',
    label: '中性叙事风（稳健）',
    prompt: '文风要求：叙事清晰稳定，信息组织明确，避免过度修辞。',
  },
]

export default function BooksPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { activeBookId, setActiveBookId } = useActiveBook()

  const [bookName, setBookName] = useState('')
  const [bookLanguage, setBookLanguage] = useState('zh-CN')
  const [bookStylePreset, setBookStylePreset] = useState('literary_cn')
  const [bookStylePrompt, setBookStylePrompt] = useState('')
  const [bookNamingPolicy, setBookNamingPolicy] = useState('localized_zh')
  const [bookIsDefault, setBookIsDefault] = useState(false)
  const [createModalOpen, setCreateModalOpen] = useState(false)

  const { data: books = [], isLoading, error } = useQuery<BookItem[]>({
    queryKey: ['books'],
    queryFn: fetchBooks,
    staleTime: 30_000,
  })

  const selectedBookId = resolveActiveBookId(activeBookId, books)
  const selectedBook = useMemo(
    () => books.find((book) => book.id === selectedBookId) ?? null,
    [books, selectedBookId],
  )

  const createMutation = useMutation({
    mutationFn: async (payload: BookCreateWizardRequest) => {
      const created = await createBook(payload.book)
      await saveCreationIntent(created.id, payload.intent)
      return created
    },
    onSuccess: async (created) => {
      setActiveBookId(created.id)
      setCreateModalOpen(false)
      await queryClient.invalidateQueries({ queryKey: ['books'] })
      toast.success('作品已创建')
      navigate(`/workspace?book=${created.id}`)
    },
    onError: (err: Error) => toast.error(`创建失败：${err.message}`),
  })

  const updateMutation = useMutation({
    mutationFn: (params: { id: number; payload: BookUpsertRequest }) => updateBook(params.id, params.payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['books'] })
      toast.success('作品设置已更新')
    },
    onError: (err: Error) => toast.error(`更新失败：${err.message}`),
  })

  useEffect(() => {
    /**
     * 作品库页不再拥有自己的“选书真源”。
     * 它只消费全局当前作品，并在书籍列表变化后把表单同步到当前书上。
     * 这样从左侧导航切书、从工作台跳回作品库时，表单会自动跟随同一本书。
     */
    if (books.length === 0) {
      return
    }
    if (selectedBookId !== activeBookId) {
      setActiveBookId(selectedBookId)
      return
    }
    if (!selectedBook) {
      return
    }
    setBookName(selectedBook.name)
    setBookLanguage(selectedBook.language)
    setBookStylePreset(selectedBook.style_preset)
    setBookStylePrompt(selectedBook.style_prompt)
    setBookNamingPolicy(selectedBook.naming_policy)
    setBookIsDefault(selectedBook.is_default)
  }, [activeBookId, books, selectedBook, selectedBookId, setActiveBookId])

  const buildUpdatePayload = (): BookUpsertRequest => ({
    name: bookName.trim() || '未命名小说',
    language: bookLanguage,
    style_preset: bookStylePreset,
    style_prompt: bookStylePrompt,
    naming_policy: bookNamingPolicy,
    is_default: bookIsDefault,
  })

  if (isLoading) return <LoadingSpinner text="加载作品库中…" />
  if (error) return <ErrorMessage message={(error as Error).message} />

  return (
    <div className="space-y-6">
      <section className="rounded-[28px] border border-stone-200 bg-white px-6 py-5 shadow-sm">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700">
              <LibraryBig className="h-3.5 w-3.5" />
              作品库与基础配置
            </div>
            <h2 className="mt-3 text-2xl font-semibold text-stone-900">先整理作品资产，再进入创作工作台</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-stone-600">
              这里不再承载整书蓝图主流程，只负责切换作品、维护语言与文风、以及新建项目。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => selectedBook && navigate(`/workspace?book=${selectedBook.id}`)}
              disabled={!selectedBook}
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              进入当前工作台
              <ArrowRight className="h-4 w-4" />
            </button>
            <button
              onClick={() => setCreateModalOpen(true)}
              disabled={createMutation.isPending}
              className="inline-flex items-center gap-2 rounded-xl border border-stone-300 bg-white px-4 py-2.5 text-sm font-medium text-stone-700 hover:bg-stone-50 disabled:opacity-50"
            >
              <Plus className="h-4 w-4" />
              新建作品
            </button>
          </div>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
        <section className="rounded-[28px] border border-stone-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-stone-500" />
            <h3 className="text-base font-semibold text-stone-900">作品列表</h3>
          </div>
          <div className="mt-4 space-y-3">
            {books.map((book) => {
              const isActive = book.id === selectedBookId
              return (
                <button
                  key={book.id}
                  type="button"
                  onClick={() => setActiveBookId(book.id)}
                  className={`w-full rounded-2xl border px-4 py-4 text-left transition-colors ${
                    isActive
                      ? 'border-emerald-200 bg-emerald-50/80'
                      : 'border-stone-200 bg-stone-50 hover:bg-stone-100'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-stone-900">{book.name}</p>
                      <p className="mt-1 text-xs text-stone-500">
                        {formatLanguageLabel(book.language)} · {formatStylePresetLabel(book.style_preset)}
                      </p>
                    </div>
                    {book.is_default ? (
                      <span className="rounded-full bg-white px-2 py-1 text-[11px] font-medium text-emerald-700">
                        默认
                      </span>
                    ) : null}
                  </div>
                </button>
              )
            })}
          </div>
        </section>

        <section className="rounded-[28px] border border-stone-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2">
            <Settings2 className="h-5 w-5 text-stone-500" />
            <div>
              <h3 className="text-base font-semibold text-stone-900">作品设置</h3>
              <p className="mt-1 text-sm text-stone-500">这些基础配置会影响后续蓝图生成与命名策略。</p>
            </div>
          </div>

          {!selectedBook ? (
            <div className="mt-6 rounded-2xl border border-dashed border-stone-300 px-4 py-8 text-sm text-stone-500">
              当前还没有可编辑作品，请先新建。
            </div>
          ) : (
            <div className="mt-5 space-y-5">
              <div>
                <label className="mb-1 block text-xs font-medium text-stone-500">书名</label>
                <input
                  value={bookName}
                  onChange={(event) => setBookName(event.target.value)}
                  className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
                />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs font-medium text-stone-500">语言</label>
                  <select
                    value={bookLanguage}
                    onChange={(event) => setBookLanguage(event.target.value)}
                    className="w-full rounded-xl border border-stone-300 bg-white px-3 py-2.5 text-sm"
                  >
                    <option value="zh-CN">中文</option>
                    <option value="en-US">英文</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-stone-500">专名策略</label>
                  <select
                    value={bookNamingPolicy}
                    onChange={(event) => setBookNamingPolicy(event.target.value)}
                    className="w-full rounded-xl border border-stone-300 bg-white px-3 py-2.5 text-sm"
                  >
                    <option value="localized_zh">中文化（音译/意译）</option>
                    <option value="preserve_original">保留原名</option>
                    <option value="hybrid">混合策略</option>
                  </select>
                  <p className="mt-1 text-xs text-stone-400">当前显示：{formatNamingPolicyLabel(bookNamingPolicy)}</p>
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-stone-500">文风预设</label>
                <select
                  value={bookStylePreset}
                  onChange={(event) => {
                    const preset = event.target.value
                    setBookStylePreset(preset)
                    const hit = STYLE_PRESETS.find((item) => item.value === preset)
                    if (hit) {
                      setBookStylePrompt(hit.prompt)
                    }
                  }}
                  className="w-full rounded-xl border border-stone-300 bg-white px-3 py-2.5 text-sm"
                >
                  {STYLE_PRESETS.map((preset) => (
                    <option key={preset.value} value={preset.value}>
                      {preset.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-stone-500">自定义文风描述</label>
                <textarea
                  value={bookStylePrompt}
                  onChange={(event) => setBookStylePrompt(event.target.value)}
                  rows={5}
                  className="w-full rounded-xl border border-stone-300 px-3 py-2.5 text-sm"
                  placeholder="例如：多用短句推进冲突，减少解释性旁白，结尾保留强钩子。"
                />
              </div>

              <label className="inline-flex items-center gap-2 text-sm text-stone-700">
                <input
                  type="checkbox"
                  checked={bookIsDefault}
                  onChange={(event) => setBookIsDefault(event.target.checked)}
                  className="rounded border-stone-300"
                />
                设为默认作品
              </label>

              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => updateMutation.mutate({ id: selectedBook.id, payload: buildUpdatePayload() })}
                  disabled={updateMutation.isPending}
                  className="rounded-xl bg-stone-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-stone-800 disabled:opacity-50"
                >
                  {updateMutation.isPending ? '保存中…' : '保存作品设置'}
                </button>
                <button
                  onClick={() => navigate(`/workspace?book=${selectedBook.id}`)}
                  className="rounded-xl border border-stone-300 bg-white px-4 py-2.5 text-sm font-medium text-stone-700 hover:bg-stone-50"
                >
                  去工作台继续蓝图
                </button>
              </div>
            </div>
          )}
        </section>
      </div>

      <BookCreateModal
        open={createModalOpen}
        loading={createMutation.isPending}
        initialValues={{
          language: bookLanguage,
          style_preset: bookStylePreset,
          style_prompt: bookStylePrompt,
          naming_policy: bookNamingPolicy,
          is_default: false,
        }}
        onCancel={() => setCreateModalOpen(false)}
        onConfirm={(payload) => createMutation.mutate(payload)}
      />
    </div>
  )
}
