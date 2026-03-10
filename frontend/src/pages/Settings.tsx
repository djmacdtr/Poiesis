/**
 * 系统设置页：配置模型密钥、嵌入方式，并提示用户前往蓝图工作台。
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Settings, CheckCircle, XCircle, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { getSystemConfig, saveSystemConfig } from '@/services/systemConfig'
import type { SystemConfigRequest } from '@/services/systemConfig'
import { LoadingSpinner, ErrorMessage } from '@/components/Feedback'
import { ConfirmModal } from '@/components/ConfirmModal'
import { Link } from 'react-router-dom'

type LLMProvider = 'openai' | 'anthropic' | 'siliconflow'

const MODEL_OPTIONS: Record<LLMProvider, string[]> = {
  openai: ['gpt-4o', 'gpt-4.1', 'gpt-4o-mini'],
  anthropic: ['claude-3-7-sonnet-latest', 'claude-3-5-sonnet-20241022'],
  siliconflow: ['Qwen/Qwen2.5-72B-Instruct', 'deepseek-ai/DeepSeek-V3'],
}

function isProvider(value: string): value is LLMProvider {
  return value === 'openai' || value === 'anthropic' || value === 'siliconflow'
}

function getFirstModel(provider: LLMProvider): string {
  return MODEL_OPTIONS[provider][0]
}

function getEmbeddingProviderLabel(provider: string | null | undefined): string {
  if (provider === 'remote') return '远程模式'
  if (provider === 'local') return '本地模式'
  return '未设置'
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
  // 读取当前配置状态
  const {
    data: configStatus,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['systemConfig'],
    queryFn: getSystemConfig,
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

  if (isLoading) return <LoadingSpinner text="加载配置中…" />
  if (error) return <ErrorMessage message={(error as Error).message} />

  return (
    <div className="space-y-6 max-w-2xl">
      <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
        <Settings className="w-5 h-5" />
        系统设置
      </h2>

      {/* 模型密钥配置卡片 */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <h3 className="text-sm font-semibold text-gray-700">模型密钥配置</h3>

        {/* 当前状态 */}
        <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              {configStatus?.has_openai_api_key ? (
                <CheckCircle className="w-4 h-4 text-green-500" />
              ) : (
                <XCircle className="w-4 h-4 text-gray-400" />
              )}
              <span className="text-gray-600">OpenAI 密钥</span>
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
              <span className="text-gray-600">Anthropic 密钥</span>
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
              <span className="text-gray-600">SiliconFlow 密钥</span>
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
              OpenAI API 密钥
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
              Anthropic API 密钥
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
              SiliconFlow API 密钥
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
              嵌入方式
            </label>
            <select
              id="embedding-provider"
              value={embeddingProvider}
              onChange={(e) => setEmbeddingProvider(e.target.value as 'local' | 'remote' | '')}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 bg-white"
            >
              <option value="">— 不修改（已保存：{getEmbeddingProviderLabel(configStatus?.embedding_provider)}）</option>
              <option value="local">本地模式（轻量离线）</option>
              <option value="remote">远程模式（依赖嵌入服务）</option>
            </select>
            <p className="mt-1 text-xs text-gray-500">
              当前生效：{configStatus?.embedding_provider_effective === 'remote' ? '远程模式' : '本地模式'}
            </p>
            {configStatus?.embedding_service_health && (
              <p className={`mt-1 text-xs ${configStatus.embedding_service_health.reachable ? 'text-green-600' : 'text-amber-600'}`}>
                远程嵌入服务状态：{configStatus.embedding_service_health.reachable ? '可达' : '不可达'}
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
            <p className="text-sm font-semibold text-gray-700">写作模型</p>
            <p className="text-xs text-gray-500">
              当前生效：{configStatus?.llm_provider_effective} / {configStatus?.llm_model_effective}
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="llm-provider">
              写作提供商
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
              写作模型
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
            <p className="mt-1 text-xs text-gray-500">支持手动输入任意模型名称。</p>
          </div>

          <div className="space-y-1">
            <p className="text-sm font-semibold text-gray-700">规划模型</p>
            <p className="text-xs text-gray-500">
              当前生效：{configStatus?.planner_llm_provider_effective} / {configStatus?.planner_llm_model_effective}
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="planner-provider">
              规划提供商
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
              规划模型
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
            <p className="mt-1 text-xs text-gray-500">支持手动输入任意模型名称。</p>
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
            清空模型配置并回退默认文件
          </button>
        </div>
      </div>

      <ConfirmModal
        open={confirmClearModelOpen}
        title="确认清空模型配置"
        description="将清空写作模型与规划模型的数据库配置，后续新任务会回退到 config.yaml 默认模型。"
        confirmText="确认清空"
        cancelText="取消"
        danger
        loading={saveMutation.isPending}
        onConfirm={handleClearModelConfig}
        onCancel={() => setConfirmClearModelOpen(false)}
      />

      {/* 蓝图工作台引导卡片 */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
        <h3 className="text-sm font-semibold text-gray-700">作品与蓝图工作台</h3>
        <p className="text-sm text-gray-500">
          新书的世界观、人物和章节路线都应通过蓝图工作台逐层生成并锁定。
          <span className="text-amber-600 ml-1">请统一在作品与蓝图管理中完成作品初始化。</span>
        </p>
        <Link
          to="/books"
          className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white text-sm rounded-lg hover:bg-emerald-700 transition-colors"
        >
          <Sparkles className="w-4 h-4" />
          前往作品与蓝图管理
        </Link>
      </div>
    </div>
  )
}
