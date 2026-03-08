/**
 * 系统设置页：配置 API Key、Embedding Provider，以及初始化世界
 */
import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Settings, CheckCircle, XCircle, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'
import { getSystemConfig, saveSystemConfig, initWorld } from '@/services/systemConfig'
import { createBook, fetchBooks, updateBook } from '@/services/books'
import type { SystemConfigRequest } from '@/services/systemConfig'
import type { BookItem, BookUpsertRequest } from '@/types'
import { LoadingSpinner, ErrorMessage } from '@/components/Feedback'
import { ConfirmModal } from '@/components/ConfirmModal'

type LLMProvider = 'openai' | 'anthropic' | 'siliconflow'

const MODEL_OPTIONS: Record<LLMProvider, string[]> = {
  openai: ['gpt-4o', 'gpt-4.1', 'gpt-4o-mini'],
  anthropic: ['claude-3-7-sonnet-latest', 'claude-3-5-sonnet-20241022'],
  siliconflow: ['Qwen/Qwen2.5-72B-Instruct', 'deepseek-ai/DeepSeek-V3'],
}

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

function isProvider(value: string): value is LLMProvider {
  return value === 'openai' || value === 'anthropic' || value === 'siliconflow'
}

function getFirstModel(provider: LLMProvider): string {
  return MODEL_OPTIONS[provider][0]
}

export default function SettingsPage() {
  const queryClient = useQueryClient()

  // 表单状态
  const [openaiKey, setOpenaiKey] = useState('')
  const [anthropicKey, setAnthropicKey] = useState('')
  const [siliconflowKey, setSiliconflowKey] = useState('')
  const [embeddingProvider, setEmbeddingProvider] = useState<'local' | 'remote' | ''>('')
  const [defaultChapterCount, setDefaultChapterCount] = useState<number | ''>('')
  const [llmProvider, setLlmProvider] = useState<LLMProvider | ''>('')
  const [llmModel, setLlmModel] = useState('')
  const [plannerLlmProvider, setPlannerLlmProvider] = useState<LLMProvider | ''>('')
  const [plannerLlmModel, setPlannerLlmModel] = useState('')
  const [confirmClearModelOpen, setConfirmClearModelOpen] = useState(false)
  const [isInitializing, setIsInitializing] = useState(false)
  const [activeBookId, setActiveBookId] = useState<number>(1)
  const [bookName, setBookName] = useState('')
  const [bookLanguage, setBookLanguage] = useState('zh-CN')
  const [bookStylePreset, setBookStylePreset] = useState('literary_cn')
  const [bookStylePrompt, setBookStylePrompt] = useState('')
  const [bookNamingPolicy, setBookNamingPolicy] = useState('localized_zh')
  const [bookIsDefault, setBookIsDefault] = useState(false)

  // 读取当前配置状态
  const {
    data: configStatus,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['systemConfig'],
    queryFn: getSystemConfig,
  })

  const { data: books = [] } = useQuery<BookItem[]>({
    queryKey: ['books'],
    queryFn: fetchBooks,
    staleTime: 30_000,
  })

  // 保存配置 mutation
  const saveMutation = useMutation({
    mutationFn: (data: SystemConfigRequest) => saveSystemConfig(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['systemConfig'] })
      toast.success('配置保存成功')
      // 清空密钥输入框（不在界面上留存）
      setOpenaiKey('')
      setAnthropicKey('')
      setSiliconflowKey('')
    },
    onError: (err: Error) => {
      toast.error(`保存失败：${err.message}`)
    },
  })

  const createBookMutation = useMutation({
    mutationFn: (payload: BookUpsertRequest) => createBook(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['books'] })
      toast.success('书籍创建成功')
    },
    onError: (err: Error) => {
      toast.error(`创建书籍失败：${err.message}`)
    },
  })

  const updateBookMutation = useMutation({
    mutationFn: (params: { id: number; payload: BookUpsertRequest }) => updateBook(params.id, params.payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['books'] })
      toast.success('书籍配置已更新')
    },
    onError: (err: Error) => {
      toast.error(`更新书籍失败：${err.message}`)
    },
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

  const handleSave = (overridePayload?: SystemConfigRequest) => {
    if (overridePayload) {
      saveMutation.mutate(overridePayload)
      return
    }

    const payload: SystemConfigRequest = {}
    if (openaiKey !== '') payload.openai_api_key = openaiKey
    if (anthropicKey !== '') payload.anthropic_api_key = anthropicKey
    if (siliconflowKey !== '') payload.siliconflow_api_key = siliconflowKey
    if (embeddingProvider !== '') payload.embedding_provider = embeddingProvider
    if (defaultChapterCount !== '') payload.default_chapter_count = Number(defaultChapterCount)
    if (llmProvider !== '') payload.llm_provider = llmProvider
    if (llmModel !== '') payload.llm_model = llmModel.trim()
    if (plannerLlmProvider !== '') payload.planner_llm_provider = plannerLlmProvider
    if (plannerLlmModel !== '') payload.planner_llm_model = plannerLlmModel.trim()
    saveMutation.mutate(payload)
  }

  const handleClearModelConfig = () => {
    handleSave({
      llm_provider: '',
      llm_model: '',
      planner_llm_provider: '',
      planner_llm_model: '',
    })
    setConfirmClearModelOpen(false)
  }

  const handleInit = async () => {
    setIsInitializing(true)
    try {
      const res = await initWorld()
      toast.success(res.message ?? '世界初始化完成')
    } catch (err) {
      toast.error((err as Error).message)
    } finally {
      setIsInitializing(false)
    }
  }

  const applyPresetPrompt = (preset: string) => {
    const hit = STYLE_PRESETS.find((item) => item.value === preset)
    if (hit) setBookStylePrompt(hit.prompt)
  }

  const handleCreateBook = () => {
    const payload: BookUpsertRequest = {
      name: bookName.trim() || '新小说',
      language: bookLanguage,
      style_preset: bookStylePreset,
      style_prompt: bookStylePrompt,
      naming_policy: bookNamingPolicy,
      is_default: bookIsDefault,
    }
    createBookMutation.mutate(payload)
  }

  const handleUpdateBook = () => {
    const payload: BookUpsertRequest = {
      name: bookName.trim() || '未命名小说',
      language: bookLanguage,
      style_preset: bookStylePreset,
      style_prompt: bookStylePrompt,
      naming_policy: bookNamingPolicy,
      is_default: bookIsDefault,
    }
    updateBookMutation.mutate({ id: activeBookId, payload })
  }

  if (isLoading) return <LoadingSpinner text="加载配置中…" />
  if (error) return <ErrorMessage message={(error as Error).message} />

  return (
    <div className="space-y-6 max-w-2xl">
      <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
        <Settings className="w-5 h-5" />
        系统设置
      </h2>

      {/* API Key 配置卡片 */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <h3 className="text-sm font-semibold text-gray-700">API Key 配置</h3>

        {/* 当前状态 */}
        <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              {configStatus?.has_openai_api_key ? (
                <CheckCircle className="w-4 h-4 text-green-500" />
              ) : (
                <XCircle className="w-4 h-4 text-gray-400" />
              )}
              <span className="text-gray-600">OpenAI Key</span>
              <span className={`text-xs px-1.5 py-0.5 rounded ${configStatus?.has_openai_api_key ? 'bg-green-50 text-green-700' : 'bg-gray-50 text-gray-400'}`}>
                {configStatus?.has_openai_api_key ? '已配置' : '未配置'}
              </span>
            </div>
            <p className="font-mono text-[11px] text-gray-500">
              {configStatus?.openai_api_key_preview ? `预览：${configStatus.openai_api_key_preview}` : '预览：--'}
            </p>
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              {configStatus?.has_anthropic_api_key ? (
                <CheckCircle className="w-4 h-4 text-green-500" />
              ) : (
                <XCircle className="w-4 h-4 text-gray-400" />
              )}
              <span className="text-gray-600">Anthropic Key</span>
              <span className={`text-xs px-1.5 py-0.5 rounded ${configStatus?.has_anthropic_api_key ? 'bg-green-50 text-green-700' : 'bg-gray-50 text-gray-400'}`}>
                {configStatus?.has_anthropic_api_key ? '已配置' : '未配置'}
              </span>
            </div>
            <p className="font-mono text-[11px] text-gray-500">
              {configStatus?.anthropic_api_key_preview ? `预览：${configStatus.anthropic_api_key_preview}` : '预览：--'}
            </p>
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              {configStatus?.has_siliconflow_api_key ? (
                <CheckCircle className="w-4 h-4 text-green-500" />
              ) : (
                <XCircle className="w-4 h-4 text-gray-400" />
              )}
              <span className="text-gray-600">SiliconFlow Key</span>
              <span className={`text-xs px-1.5 py-0.5 rounded ${configStatus?.has_siliconflow_api_key ? 'bg-green-50 text-green-700' : 'bg-gray-50 text-gray-400'}`}>
                {configStatus?.has_siliconflow_api_key ? '已配置' : '未配置'}
              </span>
            </div>
            <p className="font-mono text-[11px] text-gray-500">
              {configStatus?.siliconflow_api_key_preview ? `预览：${configStatus.siliconflow_api_key_preview}` : '预览：--'}
            </p>
          </div>
        </div>

        <hr className="border-gray-100" />

        {/* 输入表单 */}
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="openai-key">
              OpenAI API Key
              <span className="ml-1 font-normal text-gray-400">（留空则保持不变，输入新值可覆盖）</span>
            </label>
            <input
              id="openai-key"
              type="password"
              placeholder={configStatus?.has_openai_api_key ? '已配置，输入新值可覆盖' : '请输入 sk-...'}
              value={openaiKey}
              onChange={(e) => setOpenaiKey(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              autoComplete="off"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="anthropic-key">
              Anthropic API Key
              <span className="ml-1 font-normal text-gray-400">（留空则保持不变）</span>
            </label>
            <input
              id="anthropic-key"
              type="password"
              placeholder={configStatus?.has_anthropic_api_key ? '已配置，输入新值可覆盖' : '请输入 sk-ant-...'}
              value={anthropicKey}
              onChange={(e) => setAnthropicKey(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              autoComplete="off"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="siliconflow-key">
              SiliconFlow API Key
              <span className="ml-1 font-normal text-gray-400">（留空则保持不变）</span>
            </label>
            <input
              id="siliconflow-key"
              type="password"
              placeholder={configStatus?.has_siliconflow_api_key ? '已配置，输入新值可覆盖' : '请输入 sk-...'}
              value={siliconflowKey}
              onChange={(e) => setSiliconflowKey(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              autoComplete="off"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="embedding-provider">
              Embedding Provider
            </label>
            <select
              id="embedding-provider"
              value={embeddingProvider}
              onChange={(e) => setEmbeddingProvider(e.target.value as 'local' | 'remote' | '')}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 bg-white"
            >
              <option value="">— 不修改（已保存：{configStatus?.embedding_provider ?? '未设置'}）</option>
              <option value="local">local（轻量离线）</option>
              <option value="remote">remote（依赖 embed 服务）</option>
            </select>
            <p className="mt-1 text-xs text-gray-500">
              当前生效：{configStatus?.embedding_provider_effective ?? 'local'}
            </p>
            {configStatus?.embedding_service_health && (
              <p className={`mt-1 text-xs ${configStatus.embedding_service_health.reachable ? 'text-green-600' : 'text-amber-600'}`}>
                remote 健康状态：{configStatus.embedding_service_health.reachable ? '可达' : '不可达'}
                {!configStatus.embedding_service_health.reachable && configStatus.embedding_service_health.error_msg
                  ? `（${configStatus.embedding_service_health.error_msg}）`
                  : ''}
              </p>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="chapter-count">
              默认章节生成数
            </label>
            <input
              id="chapter-count"
              type="number"
              min={1}
              max={100}
              placeholder={configStatus?.default_chapter_count?.toString() ?? '未设置'}
              value={defaultChapterCount}
              onChange={(e) => setDefaultChapterCount(e.target.value ? Number(e.target.value) : '')}
              className="w-32 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>

          <hr className="border-gray-100" />

          <div className="space-y-1">
            <p className="text-sm font-semibold text-gray-700">写作模型（llm）</p>
            <p className="text-xs text-gray-500">
              当前生效：{configStatus?.llm_provider_effective} / {configStatus?.llm_model_effective}
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="llm-provider">
              写作 Provider
            </label>
            <select
              id="llm-provider"
              value={llmProvider}
              onChange={(e) => {
                const value = e.target.value
                if (value === '') {
                  setLlmProvider('')
                  return
                }
                if (isProvider(value)) {
                  setLlmProvider(value)
                  if (llmModel.trim() === '') {
                    setLlmModel(getFirstModel(value))
                  }
                }
              }}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 bg-white"
            >
              <option value="">
                — 不修改（已保存：{configStatus?.llm_provider ?? '未设置'}）
              </option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="siliconflow">SiliconFlow</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="llm-model">
              写作 Model
            </label>
            <input
              id="llm-model"
              type="text"
              list="llm-model-options"
              placeholder={configStatus?.llm_model ?? configStatus?.llm_model_effective ?? '输入或选择模型名'}
              value={llmModel}
              onChange={(e) => setLlmModel(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
            <datalist id="llm-model-options">
              {(llmProvider !== '' ? MODEL_OPTIONS[llmProvider] : MODEL_OPTIONS[configStatus?.llm_provider_effective ?? 'openai']).map((model) => (
                <option key={model} value={model} />
              ))}
            </datalist>
            <p className="mt-1 text-xs text-gray-500">支持手动输入任意模型标识。</p>
          </div>

          <div className="space-y-1">
            <p className="text-sm font-semibold text-gray-700">规划模型（planner_llm）</p>
            <p className="text-xs text-gray-500">
              当前生效：{configStatus?.planner_llm_provider_effective} / {configStatus?.planner_llm_model_effective}
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="planner-provider">
              规划 Provider
            </label>
            <select
              id="planner-provider"
              value={plannerLlmProvider}
              onChange={(e) => {
                const value = e.target.value
                if (value === '') {
                  setPlannerLlmProvider('')
                  return
                }
                if (isProvider(value)) {
                  setPlannerLlmProvider(value)
                  if (plannerLlmModel.trim() === '') {
                    setPlannerLlmModel(getFirstModel(value))
                  }
                }
              }}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 bg-white"
            >
              <option value="">
                — 不修改（已保存：{configStatus?.planner_llm_provider ?? '未设置'}）
              </option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="siliconflow">SiliconFlow</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="planner-model">
              规划 Model
            </label>
            <input
              id="planner-model"
              type="text"
              list="planner-model-options"
              placeholder={configStatus?.planner_llm_model ?? configStatus?.planner_llm_model_effective ?? '输入或选择模型名'}
              value={plannerLlmModel}
              onChange={(e) => setPlannerLlmModel(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
            <datalist id="planner-model-options">
              {(plannerLlmProvider !== ''
                ? MODEL_OPTIONS[plannerLlmProvider]
                : MODEL_OPTIONS[configStatus?.planner_llm_provider_effective ?? 'openai']
              ).map((model) => (
                <option key={model} value={model} />
              ))}
            </datalist>
            <p className="mt-1 text-xs text-gray-500">支持手动输入任意模型标识。</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => handleSave()}
            disabled={saveMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {saveMutation.isPending ? (
              <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
            ) : (
              <Settings className="w-4 h-4" />
            )}
            {saveMutation.isPending ? '保存中…' : '保存配置'}
          </button>

          <button
            onClick={() => setConfirmClearModelOpen(true)}
            disabled={saveMutation.isPending}
            className="px-4 py-2 bg-amber-50 text-amber-700 border border-amber-200 text-sm rounded-lg hover:bg-amber-100 disabled:opacity-50 transition-colors"
          >
            清空模型配置并回退 YAML
          </button>
        </div>
      </div>

      {/* 书籍与文风配置 */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <h3 className="text-sm font-semibold text-gray-700">书籍与文风配置</h3>
        <p className="text-xs text-gray-500">
          每本书独立维护语言、文风与命名策略，运行任务时将自动按书应用。
        </p>

        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="book-select">
            当前书籍
          </label>
          <select
            id="book-select"
            value={activeBookId}
            onChange={(e) => setActiveBookId(Number(e.target.value))}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 bg-white"
          >
            {books.map((book) => (
              <option key={book.id} value={book.id}>
                {book.name}（{book.language} / {book.style_preset}{book.is_default ? ' / 默认' : ''}）
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="book-name">
            书名
          </label>
          <input
            id="book-name"
            type="text"
            value={bookName}
            onChange={(e) => setBookName(e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="book-language">
              语言
            </label>
            <select
              id="book-language"
              value={bookLanguage}
              onChange={(e) => setBookLanguage(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 bg-white"
            >
              <option value="zh-CN">zh-CN（中文）</option>
              <option value="en-US">en-US（英文）</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="book-naming-policy">
              专名策略
            </label>
            <select
              id="book-naming-policy"
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
          <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="book-style-preset">
            文风预设
          </label>
          <select
            id="book-style-preset"
            value={bookStylePreset}
            onChange={(e) => {
              setBookStylePreset(e.target.value)
              applyPresetPrompt(e.target.value)
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
          <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="book-style-prompt">
            自定义文风描述
          </label>
          <textarea
            id="book-style-prompt"
            value={bookStylePrompt}
            onChange={(e) => setBookStylePrompt(e.target.value)}
            rows={4}
            placeholder="可填写你想要的文风关键词、节奏偏好、叙述视角约束等。"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
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

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleUpdateBook}
            disabled={updateBookMutation.isPending || books.length === 0}
            className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {updateBookMutation.isPending ? '保存中…' : '保存当前书籍配置'}
          </button>
          <button
            onClick={handleCreateBook}
            disabled={createBookMutation.isPending}
            className="px-4 py-2 bg-emerald-600 text-white text-sm rounded-lg hover:bg-emerald-700 disabled:opacity-50 transition-colors"
          >
            {createBookMutation.isPending ? '创建中…' : '按当前配置新建书籍'}
          </button>
        </div>
      </div>

      <ConfirmModal
        open={confirmClearModelOpen}
        title="确认清空模型配置"
        description="将清空 llm 与 planner_llm 的数据库配置，后续新任务会回退到 config.yaml 默认模型。"
        confirmText="确认清空"
        cancelText="取消"
        danger
        loading={saveMutation.isPending}
        onConfirm={handleClearModelConfig}
        onCancel={() => setConfirmClearModelOpen(false)}
      />

      {/* 初始化世界卡片 */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
        <h3 className="text-sm font-semibold text-gray-700">初始化世界</h3>
        <p className="text-sm text-gray-500">
          从默认 seed.yaml 初始化世界数据库（角色、规则、时间线）。
          <span className="text-amber-600 ml-1">⚠️ 此操作会重新加载种子数据。</span>
        </p>
        <button
          onClick={handleInit}
          disabled={isInitializing}
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white text-sm rounded-lg hover:bg-emerald-700 disabled:opacity-50 transition-colors"
        >
          {isInitializing ? (
            <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
          ) : (
            <RefreshCw className="w-4 h-4" />
          )}
          {isInitializing ? '初始化中…' : '初始化世界'}
        </button>
      </div>
    </div>
  )
}
