/**
 * 书籍创建弹窗：集中填写必要信息后再提交，避免误创建。
 */
import { useEffect, useState, type FormEvent } from 'react'
import { BookPlus } from 'lucide-react'
import { ModalBase } from '@/components/ModalBase'
import type { BookUpsertRequest } from '@/types'

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

interface BookCreateModalProps {
  open: boolean
  loading?: boolean
  initialValues?: Partial<BookUpsertRequest>
  onCancel: () => void
  onConfirm: (payload: BookUpsertRequest) => void
}

export function BookCreateModal({
  open,
  loading = false,
  initialValues,
  onCancel,
  onConfirm,
}: BookCreateModalProps) {
  const [name, setName] = useState('')
  const [language, setLanguage] = useState('zh-CN')
  const [stylePreset, setStylePreset] = useState('literary_cn')
  const [stylePrompt, setStylePrompt] = useState('')
  const [namingPolicy, setNamingPolicy] = useState('localized_zh')
  const [isDefault, setIsDefault] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setName('')
    setLanguage(initialValues?.language ?? 'zh-CN')
    setStylePreset(initialValues?.style_preset ?? 'literary_cn')
    setStylePrompt(initialValues?.style_prompt ?? '')
    setNamingPolicy(initialValues?.naming_policy ?? 'localized_zh')
    setIsDefault(initialValues?.is_default ?? false)
    setError(null)
  }, [open, initialValues])

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    const trimmedName = name.trim()
    if (trimmedName === '') {
      setError('请填写书名')
      return
    }

    onConfirm({
      name: trimmedName,
      language,
      style_preset: stylePreset,
      style_prompt: stylePrompt,
      naming_policy: namingPolicy,
      is_default: isDefault,
    })
  }

  return (
    <ModalBase open={open} maxWidthClass="max-w-xl">
      <div className="p-6 space-y-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center">
            <BookPlus className="w-5 h-5 text-emerald-600" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-semibold text-gray-800">新建书籍</h3>
            <p className="text-sm text-gray-600">请填写书籍基础信息后再创建。</p>
          </div>
        </div>

        {error && <div className="rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="create-book-name">
              书名
            </label>
            <input
              id="create-book-name"
              type="text"
              value={name}
              onChange={(e) => {
                setName(e.target.value)
                if (error) setError(null)
              }}
              placeholder="例如：玄都夜雨"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="create-book-language">
                语言
              </label>
              <select
                id="create-book-language"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400 bg-white"
              >
                <option value="zh-CN">zh-CN（中文）</option>
                <option value="en-US">en-US（英文）</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="create-book-naming-policy">
                专名策略
              </label>
              <select
                id="create-book-naming-policy"
                value={namingPolicy}
                onChange={(e) => setNamingPolicy(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400 bg-white"
              >
                <option value="localized_zh">中文化（音译/意译）</option>
                <option value="preserve_original">保留原名</option>
                <option value="hybrid">混合策略</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="create-book-style-preset">
              文风预设
            </label>
            <select
              id="create-book-style-preset"
              value={stylePreset}
              onChange={(e) => {
                const preset = e.target.value
                setStylePreset(preset)
                const hit = STYLE_PRESETS.find((item) => item.value === preset)
                if (hit) setStylePrompt(hit.prompt)
              }}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400 bg-white"
            >
              {STYLE_PRESETS.map((preset) => (
                <option key={preset.value} value={preset.value}>
                  {preset.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="create-book-style-prompt">
              自定义文风描述
            </label>
            <textarea
              id="create-book-style-prompt"
              value={stylePrompt}
              onChange={(e) => setStylePrompt(e.target.value)}
              rows={3}
              placeholder="可选：补充更具体的文风偏好。"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400"
            />
          </div>

          <label className="inline-flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={isDefault}
              onChange={(e) => setIsDefault(e.target.checked)}
              className="rounded border-gray-300 text-emerald-600 focus:ring-emerald-500"
            />
            设为默认书籍
          </label>

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onCancel}
              disabled={loading}
              className="px-4 py-2 text-sm text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-50 transition-colors"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm rounded-lg text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 transition-colors"
            >
              {loading ? (
                <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
              ) : (
                <BookPlus className="w-4 h-4" />
              )}
              {loading ? '创建中…' : '确认创建'}
            </button>
          </div>
        </form>
      </div>
    </ModalBase>
  )
}
