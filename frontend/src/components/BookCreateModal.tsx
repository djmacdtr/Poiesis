/**
 * 作品创建弹窗：先收集基础信息和创作意图，再进入蓝图工作台。
 */
import { useEffect, useState, type FormEvent } from 'react'
import { BookPlus, Lightbulb } from 'lucide-react'
import { ModalBase } from '@/components/ModalBase'
import type { BookCreateWizardRequest, BookUpsertRequest, CreationIntent } from '@/types'

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
  onConfirm: (payload: BookCreateWizardRequest) => void
}

function parseTags(value: string): string[] {
  return value
    .split(/[,，、\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
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
  const [genre, setGenre] = useState('')
  const [themes, setThemes] = useState('')
  const [tone, setTone] = useState('')
  const [targetExperience, setTargetExperience] = useState('')
  const [protagonistPrompt, setProtagonistPrompt] = useState('')
  const [conflictPrompt, setConflictPrompt] = useState('')
  const [endingPreference, setEndingPreference] = useState('')
  const [forbiddenElements, setForbiddenElements] = useState('')
  const [lengthPreference, setLengthPreference] = useState('12')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setName('')
    setLanguage(initialValues?.language ?? 'zh-CN')
    setStylePreset(initialValues?.style_preset ?? 'literary_cn')
    setStylePrompt(initialValues?.style_prompt ?? '')
    setNamingPolicy(initialValues?.naming_policy ?? 'localized_zh')
    setIsDefault(initialValues?.is_default ?? false)
    setGenre('')
    setThemes('')
    setTone('')
    setTargetExperience('')
    setProtagonistPrompt('')
    setConflictPrompt('')
    setEndingPreference('')
    setForbiddenElements('')
    setLengthPreference('12')
    setError(null)
  }, [open, initialValues])

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    const trimmedName = name.trim()
    if (trimmedName === '') {
      setError('请填写作品名称')
      return
    }
    if (!genre.trim() || !conflictPrompt.trim()) {
      setError('请至少填写题材和核心冲突，便于系统生成创作方向')
      return
    }

    const book: BookUpsertRequest = {
      name: trimmedName,
      language,
      style_preset: stylePreset,
      style_prompt: stylePrompt,
      naming_policy: namingPolicy,
      is_default: isDefault,
    }
    const intent: CreationIntent = {
      genre: genre.trim(),
      themes: parseTags(themes),
      tone: tone.trim(),
      protagonist_prompt: protagonistPrompt.trim(),
      conflict_prompt: conflictPrompt.trim(),
      ending_preference: endingPreference.trim(),
      forbidden_elements: parseTags(forbiddenElements),
      length_preference: lengthPreference.trim(),
      target_experience: targetExperience.trim(),
    }
    onConfirm({ book, intent })
  }

  return (
    <ModalBase open={open} maxWidthClass="max-w-3xl">
      <div className="p-6 space-y-5">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center">
            <BookPlus className="w-5 h-5 text-emerald-600" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-semibold text-gray-800">新建作品与创作蓝图</h3>
            <p className="text-sm text-gray-600">先填写基础信息和创作意图，创建后进入蓝图工作台逐层确认。</p>
          </div>
        </div>

        {error && <div className="rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}

        <form onSubmit={handleSubmit} className="space-y-5">
          <section className="space-y-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
              <BookPlus className="w-4 h-4 text-emerald-600" />
              作品基础信息
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="sm:col-span-2">
                <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="create-book-name">
                  作品名称
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
                  <option value="zh-CN">中文</option>
                  <option value="en-US">英文</option>
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
                <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="create-book-length">
                  预估章数
                </label>
                <input
                  id="create-book-length"
                  type="text"
                  value={lengthPreference}
                  onChange={(e) => setLengthPreference(e.target.value)}
                  placeholder="例如：12"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400"
                />
              </div>
              <div className="sm:col-span-2">
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
            </div>
            <label className="inline-flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={isDefault}
                onChange={(e) => setIsDefault(e.target.checked)}
                className="rounded border-gray-300 text-emerald-600 focus:ring-emerald-500"
              />
              设为默认作品
            </label>
          </section>

          <section className="space-y-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
              <Lightbulb className="w-4 h-4 text-amber-500" />
              创作意图
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">题材</label>
                <input
                  type="text"
                  value={genre}
                  onChange={(e) => setGenre(e.target.value)}
                  placeholder="例如：武侠 / 仙侠 / 黑暗奇幻"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">整体基调</label>
                <input
                  type="text"
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  placeholder="例如：压抑、热血、悲怆、诡谲"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-xs font-medium text-gray-500 mb-1">主题关键词</label>
                <input
                  type="text"
                  value={themes}
                  onChange={(e) => setThemes(e.target.value)}
                  placeholder="多个关键词用逗号分隔，例如：成长、复仇、宿命、背叛"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-xs font-medium text-gray-500 mb-1">目标体验</label>
                <input
                  type="text"
                  value={targetExperience}
                  onChange={(e) => setTargetExperience(e.target.value)}
                  placeholder="例如：起伏跌宕、战斗精彩、带有悲剧感情线"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-xs font-medium text-gray-500 mb-1">主角关键词</label>
                <textarea
                  value={protagonistPrompt}
                  onChange={(e) => setProtagonistPrompt(e.target.value)}
                  rows={3}
                  placeholder="例如：少年剑客，天赋卓绝但身世悲惨，外冷内热。"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-xs font-medium text-gray-500 mb-1">核心冲突</label>
                <textarea
                  value={conflictPrompt}
                  onChange={(e) => setConflictPrompt(e.target.value)}
                  rows={3}
                  placeholder="例如：主角要查明灭门真相，却不断发现真相会毁掉他最在意的人。"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">结局倾向</label>
                <input
                  type="text"
                  value={endingPreference}
                  onChange={(e) => setEndingPreference(e.target.value)}
                  placeholder="例如：高代价圆满 / 悲剧式完成"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">禁用元素</label>
                <input
                  type="text"
                  value={forbiddenElements}
                  onChange={(e) => setForbiddenElements(e.target.value)}
                  placeholder="例如：系统流、穿越、无敌开局"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400"
                />
              </div>
            </div>
          </section>

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
              {loading ? '创建中…' : '创建作品并进入蓝图'}
            </button>
          </div>
        </form>
      </div>
    </ModalBase>
  )
}

