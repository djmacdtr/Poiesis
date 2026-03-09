/**
 * 书籍管理页：按书配置语言、文风与命名策略
 */
import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BookOpen, Plus } from 'lucide-react'
import { toast } from 'sonner'
import { createBook, fetchBooks, updateBook } from '@/services/books'
import type { BookItem, BookUpsertRequest } from '@/types'
import { LoadingSpinner, ErrorMessage } from '@/components/Feedback'
import { BookCreateModal } from '@/components/BookCreateModal'

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

function getLanguageLabel(language: string): string {
  if (language === 'zh-CN') return '中文'
  if (language === 'en-US') return '英文'
  return language
}

function getStylePresetLabel(stylePreset: string): string {
  return STYLE_PRESETS.find((item) => item.value === stylePreset)?.label ?? stylePreset
}

export default function BooksPage() {
  const queryClient = useQueryClient()

  const [activeBookId, setActiveBookId] = useState<number>(1)
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

  const createMutation = useMutation({
    mutationFn: (payload: BookUpsertRequest) => createBook(payload),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ['books'] })
      setActiveBookId(created.id)
      setCreateModalOpen(false)
      toast.success('书籍创建成功')
    },
    onError: (err: Error) => toast.error(`创建失败：${err.message}`),
  })

  const updateMutation = useMutation({
    mutationFn: (params: { id: number; payload: BookUpsertRequest }) => updateBook(params.id, params.payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['books'] })
      toast.success('书籍配置已更新')
    },
    onError: (err: Error) => toast.error(`更新失败：${err.message}`),
  })

  useEffect(() => {
    if (books.length === 0) return
    const selected = books.find((b) => b.id === activeBookId)
    const current = selected ?? books.find((b) => b.is_default) ?? books[0]
    if (!selected) setActiveBookId(current.id)
    setBookName(current.name)
    setBookLanguage(current.language)
    setBookStylePreset(current.style_preset)
    setBookStylePrompt(current.style_prompt)
    setBookNamingPolicy(current.naming_policy)
    setBookIsDefault(current.is_default)
  }, [activeBookId, books])

  const buildUpdatePayload = (): BookUpsertRequest => ({
    name: bookName.trim() || '未命名小说',
    language: bookLanguage,
    style_preset: bookStylePreset,
    style_prompt: bookStylePrompt,
    naming_policy: bookNamingPolicy,
    is_default: bookIsDefault,
  })

  if (isLoading) return <LoadingSpinner text="加载书籍配置中…" />
  if (error) return <ErrorMessage message={(error as Error).message} />

  return (
    <div className="space-y-6 max-w-3xl">
      <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
        <BookOpen className="w-5 h-5" />
        书籍管理
      </h2>

      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="book-select-page">
            选择书籍
          </label>
          <select
            id="book-select-page"
            value={activeBookId}
            onChange={(e) => setActiveBookId(Number(e.target.value))}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 bg-white"
          >
            {books.map((book) => (
              <option key={book.id} value={book.id}>
                {book.name}（{getLanguageLabel(book.language)} / {getStylePresetLabel(book.style_preset)}{book.is_default ? ' / 默认' : ''}）
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="book-name-page">
            书名
          </label>
          <input
            id="book-name-page"
            type="text"
            value={bookName}
            onChange={(e) => setBookName(e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="book-language-page">
              语言
            </label>
            <select
              id="book-language-page"
              value={bookLanguage}
              onChange={(e) => setBookLanguage(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 bg-white"
            >
              <option value="zh-CN">中文</option>
              <option value="en-US">英文</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="book-naming-policy-page">
              专名策略
            </label>
            <select
              id="book-naming-policy-page"
              value={bookNamingPolicy}
              onChange={(e) => setBookNamingPolicy(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 bg-white"
            >
              <option value="localized_zh">中文化（音译/意译）</option>
              <option value="preserve_original">保留原名</option>
              <option value="hybrid">混合策略</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="book-style-preset-page">
            文风预设
          </label>
          <select
            id="book-style-preset-page"
            value={bookStylePreset}
            onChange={(e) => {
              const preset = e.target.value
              setBookStylePreset(preset)
              const hit = STYLE_PRESETS.find((item) => item.value === preset)
              if (hit) setBookStylePrompt(hit.prompt)
            }}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 bg-white"
          >
            {STYLE_PRESETS.map((preset) => (
              <option key={preset.value} value={preset.value}>
                {preset.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="book-style-prompt-page">
            自定义文风描述
          </label>
          <textarea
            id="book-style-prompt-page"
            value={bookStylePrompt}
            onChange={(e) => setBookStylePrompt(e.target.value)}
            rows={4}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            placeholder="例如：多用短句推进冲突，减少解释性旁白，结尾留悬念。"
          />
        </div>

        <label className="inline-flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={bookIsDefault}
            onChange={(e) => setBookIsDefault(e.target.checked)}
            className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
          />
          设为默认书籍
        </label>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => updateMutation.mutate({ id: activeBookId, payload: buildUpdatePayload() })}
            disabled={updateMutation.isPending || books.length === 0}
            className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {updateMutation.isPending ? '保存中…' : '保存当前书籍'}
          </button>

          <button
            onClick={() => setCreateModalOpen(true)}
            disabled={createMutation.isPending}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-emerald-600 text-white text-sm rounded-lg hover:bg-emerald-700 disabled:opacity-50 transition-colors"
          >
            <Plus className="w-4 h-4" />
            新建书籍
          </button>
        </div>
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
