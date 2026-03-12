/**
 * 蓝图工作台：在同一页面里逐层生成、编辑并确认整书蓝图。
 */
import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  acceptRegeneratedConceptVariant,
  confirmRelationshipGraph,
  confirmRelationshipPending,
  confirmCharacterBlueprint,
  confirmRoadmap,
  confirmWorldBlueprint,
  confirmRelationshipReplan,
  createRelationshipReplan,
  generateCharacterBlueprint,
  generateConceptVariants,
  generateRoadmap,
  generateWorldBlueprint,
  regenerateConceptVariant,
  rejectRelationshipPending,
  replanBlueprint,
  saveCreationIntent,
  selectConceptVariant,
  upsertRelationshipEdge,
} from '@/services/books'
import type {
  BookBlueprint,
  ChapterRoadmapItem,
  CharacterNode,
  CharacterBlueprint,
  ConceptVariantRegenerationResult,
  CreationIntent,
  FactionBlueprint,
  ImmutableRuleBlueprint,
  LocationBlueprint,
  RelationshipBlueprintEdge,
  RelationshipConflictReport,
  RelationshipPendingItem,
  RelationshipReplanResponse,
  TabooRuleBlueprint,
  WorldBlueprint,
} from '@/types'

interface BookBlueprintWorkspaceProps {
  bookId: number
  blueprint: BookBlueprint | undefined
}

function parseTags(value: string): string[] {
  return value
    .split(/[,，、\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function joinTags(values: string[]): string {
  return values.join('，')
}

function defaultIntent(): CreationIntent {
  return {
    genre: '',
    themes: [],
    tone: '',
    protagonist_prompt: '',
    conflict_prompt: '',
    ending_preference: '',
    forbidden_elements: [],
    length_preference: '12',
    target_experience: '',
    variant_preference: '',
  }
}

function defaultWorldBlueprint(): WorldBlueprint {
  return {
    setting_summary: '',
    era_context: '',
    social_order: '',
    historical_wounds: [],
    public_secrets: [],
    geography: [],
    power_system: {
      core_mechanics: '',
      costs: [],
      limitations: [],
      advancement_path: [],
      symbols: [],
    },
    factions: [],
    immutable_rules: [],
    taboo_rules: [],
  }
}

function defaultLocation(): LocationBlueprint {
  return { name: '', role: '', description: '' }
}

function defaultFaction(): FactionBlueprint {
  return { name: '', position: '', goal: '', methods: [], public_image: '', hidden_truth: '' }
}

function defaultImmutableRule(): ImmutableRuleBlueprint {
  return { key: '', description: '', category: 'world', rationale: '', is_immutable: true }
}

function defaultTabooRule(): TabooRuleBlueprint {
  return { key: '', description: '', consequence: '', is_immutable: true }
}

function parseNumber(value: string, fallback = 3): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

export function BookBlueprintWorkspace({ bookId, blueprint }: BookBlueprintWorkspaceProps) {
  const queryClient = useQueryClient()
  const [intentDraft, setIntentDraft] = useState<CreationIntent>(defaultIntent)
  const [themesText, setThemesText] = useState('')
  const [forbiddenText, setForbiddenText] = useState('')
  const [worldFeedback, setWorldFeedback] = useState('')
  const [characterFeedback, setCharacterFeedback] = useState('')
  const [roadmapFeedback, setRoadmapFeedback] = useState('')
  const [worldDraft, setWorldDraft] = useState<WorldBlueprint | null>(null)
  const [characterDraft, setCharacterDraft] = useState<CharacterBlueprint[]>([])
  const [relationshipGraphDraft, setRelationshipGraphDraft] = useState<RelationshipBlueprintEdge[]>([])
  const [relationshipPending, setRelationshipPending] = useState<RelationshipPendingItem[]>([])
  const [relationshipNodes, setRelationshipNodes] = useState<CharacterNode[]>([])
  const [roadmapDraft, setRoadmapDraft] = useState<ChapterRoadmapItem[]>([])
  const [relationshipConflict, setRelationshipConflict] = useState<RelationshipConflictReport | null>(null)
  const [relationshipDesiredChange, setRelationshipDesiredChange] = useState('')
  const [relationshipReplan, setRelationshipReplan] = useState<RelationshipReplanResponse | null>(null)
  const [replanStart, setReplanStart] = useState(1)
  const [replanReason, setReplanReason] = useState('')
  const [replanGuidance, setReplanGuidance] = useState('')
  const [pendingVariantId, setPendingVariantId] = useState<number | null>(null)
  const [regenerationProposalByVariantId, setRegenerationProposalByVariantId] = useState<
    Record<number, ConceptVariantRegenerationResult>
  >({})

  const refreshBlueprint = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['books'] }),
      queryClient.invalidateQueries({ queryKey: ['bookBlueprint', bookId] }),
      queryClient.invalidateQueries({ queryKey: ['canon', bookId] }),
      queryClient.invalidateQueries({ queryKey: ['loopBoard'] }),
    ])
  }

  useEffect(() => {
    const nextIntent = blueprint?.intent ?? defaultIntent()
    setIntentDraft(nextIntent)
    setThemesText(joinTags(nextIntent.themes))
    setForbiddenText(joinTags(nextIntent.forbidden_elements))
    setWorldDraft(blueprint?.world_draft ?? blueprint?.world_confirmed ?? defaultWorldBlueprint())
    setCharacterDraft(blueprint?.character_draft ?? blueprint?.character_confirmed ?? [])
    setRelationshipGraphDraft(blueprint?.relationship_graph_draft ?? blueprint?.relationship_graph_confirmed ?? [])
    setRelationshipPending(blueprint?.relationship_pending ?? [])
    setRelationshipNodes(
      (blueprint?.character_draft ?? blueprint?.character_confirmed ?? []).map((character) => ({
        character_id: character.name.trim().replace(/\s+/g, '_'),
        name: character.name,
        role: character.role,
        public_persona: character.public_persona,
        core_motivation: character.core_motivation,
        fatal_flaw: character.fatal_flaw,
        non_negotiable_traits: character.non_negotiable_traits,
        arc_outline: character.arc_outline,
        faction_affiliation: '',
        status: 'active',
      })),
    )
    setRoadmapDraft(blueprint?.roadmap_draft ?? blueprint?.roadmap_confirmed ?? [])
    const lockedRoadmap = blueprint?.roadmap_confirmed ?? []
    const lastChapter = lockedRoadmap.length > 0 ? lockedRoadmap[lockedRoadmap.length - 1]!.chapter_number : 1
    setReplanStart(Math.max(1, Math.min(replanStart, lastChapter)))
    setRegenerationProposalByVariantId((prev) => {
      const validIds = new Set((blueprint?.concept_variants ?? []).map((item) => item.id).filter(Boolean) as number[])
      return Object.fromEntries(Object.entries(prev).filter(([key]) => validIds.has(Number(key))))
    })
  }, [blueprint])

  const saveIntentMutation = useMutation({
    mutationFn: () =>
      saveCreationIntent(bookId, {
        ...intentDraft,
        themes: parseTags(themesText),
        forbidden_elements: parseTags(forbiddenText),
      }),
    onSuccess: async () => {
      toast.success('创作意图已保存')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const generateConceptMutation = useMutation({
    mutationFn: () => generateConceptVariants(bookId),
    onSuccess: async () => {
      toast.success('已生成 3 版候选方向')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const selectVariantMutation = useMutation({
    mutationFn: (variantId: number) => selectConceptVariant(bookId, variantId),
    onSuccess: async () => {
      toast.success('已选定候选方向，进入世界观阶段')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const regenerateVariantMutation = useMutation({
    mutationFn: (variantId: number) => regenerateConceptVariant(bookId, variantId),
    onMutate: async (variantId: number) => {
      setPendingVariantId(variantId)
    },
    onSuccess: async (payload) => {
      if (payload.status === 'applied') {
        setRegenerationProposalByVariantId((prev) => {
          const next = { ...prev }
          delete next[payload.target_variant_id]
          return next
        })
        toast.success('已自动替换为差异更明显的新版本')
        await refreshBlueprint()
        return
      }
      setRegenerationProposalByVariantId((prev) => ({
        ...prev,
        [payload.target_variant_id]: payload,
      }))
      toast.warning('新提案仍与其他候选较接近，请人工决定是否替换')
    },
    onError: (error: Error) => toast.error(error.message),
    onSettled: () => {
      setPendingVariantId(null)
    },
  })

  const acceptRegeneratedVariantMutation = useMutation({
    mutationFn: ({ variantId, payload }: { variantId: number; payload: ConceptVariantRegenerationResult }) => {
      if (!payload.proposed_variant) {
        throw new Error('当前没有可接受的重生成提案')
      }
      return acceptRegeneratedConceptVariant(bookId, variantId, payload.proposed_variant)
    },
    onSuccess: async (_, variables) => {
      setRegenerationProposalByVariantId((prev) => {
        const next = { ...prev }
        delete next[variables.variantId]
        return next
      })
      toast.success('已接受新的候选提案')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const generateWorldMutation = useMutation({
    mutationFn: () => generateWorldBlueprint(bookId, { feedback: worldFeedback }),
    onSuccess: async (payload) => {
      setWorldDraft(payload.world_draft)
      toast.success('世界观草稿已生成')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const confirmWorldMutation = useMutation({
    mutationFn: () => confirmWorldBlueprint(bookId, worldDraft),
    onSuccess: async () => {
      toast.success('世界观已确认')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const generateCharacterMutation = useMutation({
    mutationFn: () => generateCharacterBlueprint(bookId, { feedback: characterFeedback }),
    onSuccess: async (payload) => {
      setCharacterDraft(payload.character_draft)
      toast.success('人物蓝图草稿已生成')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const confirmCharacterMutation = useMutation({
    mutationFn: () => confirmCharacterBlueprint(bookId, characterDraft, relationshipGraphDraft),
    onSuccess: async () => {
      toast.success('人物蓝图已确认')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const confirmRelationshipGraphMutation = useMutation({
    mutationFn: () => confirmRelationshipGraph(bookId, relationshipGraphDraft),
    onSuccess: async () => {
      toast.success('人物关系图谱已确认')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const upsertRelationshipEdgeMutation = useMutation({
    mutationFn: (edge: RelationshipBlueprintEdge) => upsertRelationshipEdge(bookId, edge),
    onSuccess: async (payload) => {
      setRelationshipGraphDraft(payload.edges)
      setRelationshipPending(payload.pending)
      setRelationshipConflict(null)
      toast.success('关系边已保存')
      await refreshBlueprint()
    },
    onError: (error: Error & { cause?: unknown }) => {
      const detail = (error as unknown as { message?: string }).message || '关系边保存失败'
      try {
        const raw = JSON.parse(detail)
        setRelationshipConflict(raw as RelationshipConflictReport)
        toast.error('当前修改与已发布事实冲突，请走关系重规划')
        return
      } catch {
        // ignore
      }
      toast.error(detail)
    },
  })

  const confirmRelationshipPendingMutation = useMutation({
    mutationFn: (itemId: number) => confirmRelationshipPending(bookId, itemId),
    onSuccess: async (payload) => {
      setRelationshipGraphDraft(payload.edges)
      setRelationshipPending(payload.pending)
      toast.success('待确认项已纳入正式关系图谱')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const rejectRelationshipPendingMutation = useMutation({
    mutationFn: (itemId: number) => rejectRelationshipPending(bookId, itemId),
    onSuccess: async (payload) => {
      setRelationshipGraphDraft(payload.edges)
      setRelationshipPending(payload.pending)
      toast.success('已拒绝待确认项')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const createRelationshipReplanMutation = useMutation({
    mutationFn: () => {
      if (!relationshipConflict) {
        throw new Error('当前没有可重规划的关系冲突')
      }
      return createRelationshipReplan(bookId, {
        edge_id: relationshipConflict.edge_id,
        reason: '编辑关系图谱时命中已发布事实冲突',
        desired_change: relationshipDesiredChange,
      })
    },
    onSuccess: (payload) => {
      setRelationshipReplan(payload)
      toast.success('已生成关系重规划提案')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const confirmRelationshipReplanMutation = useMutation({
    mutationFn: () => {
      if (!relationshipReplan) {
        throw new Error('当前没有可确认的关系重规划提案')
      }
      return confirmRelationshipReplan(bookId, relationshipReplan.request_id, relationshipReplan.proposal.proposal_id)
    },
    onSuccess: async (payload) => {
      setRelationshipGraphDraft(payload.edges)
      setRelationshipPending(payload.pending)
      setRelationshipConflict(null)
      setRelationshipReplan(null)
      setRelationshipDesiredChange('')
      toast.success('关系重规划已确认，将作用于未来章节')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const generateRoadmapMutation = useMutation({
    mutationFn: () => generateRoadmap(bookId, { feedback: roadmapFeedback }),
    onSuccess: async (payload) => {
      setRoadmapDraft(payload.roadmap_draft)
      toast.success('章节路线草稿已生成')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const confirmRoadmapMutation = useMutation({
    mutationFn: () => confirmRoadmap(bookId, roadmapDraft),
    onSuccess: async () => {
      toast.success('整书蓝图已锁定，可以开始正文写作')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const replanMutation = useMutation({
    mutationFn: () =>
      replanBlueprint(bookId, {
        starting_chapter: replanStart,
        reason: replanReason,
        guidance: replanGuidance,
      }),
    onSuccess: async (payload) => {
      setRoadmapDraft(payload.roadmap_confirmed)
      toast.success('未来章节已生成新蓝图版本')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const selectedVariantId = blueprint?.selected_variant_id
  const canGenerateCharacters = Boolean(blueprint?.world_confirmed)
  const canGenerateRoadmap = Boolean(blueprint?.world_confirmed && blueprint?.character_confirmed.length)
  const revisions = blueprint?.revisions ?? []
  const roadmapToShow = blueprint?.roadmap_confirmed.length ? blueprint.roadmap_confirmed : roadmapDraft
  const activeRevisionLabel = useMemo(() => {
    const active = revisions.find((item) => item.is_active)
    return active ? `v${active.revision_number}` : '未锁定'
  }, [revisions])

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-stone-800">创作蓝图工作台</h3>
            <p className="mt-1 text-sm text-stone-500">
              当前状态：{blueprint?.status ?? '未初始化'} · 当前步骤：{blueprint?.current_step ?? 'intent'} · 生效版本：{activeRevisionLabel}
            </p>
          </div>
          {revisions.length > 0 && (
            <div className="rounded-xl bg-stone-50 px-3 py-2 text-xs text-stone-600">
              已有 {revisions.length} 个蓝图版本
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-stone-500 mb-1">题材</label>
            <input
              value={intentDraft.genre}
              onChange={(e) => setIntentDraft((prev) => ({ ...prev, genre: e.target.value }))}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-stone-500 mb-1">整体基调</label>
            <input
              value={intentDraft.tone}
              onChange={(e) => setIntentDraft((prev) => ({ ...prev, tone: e.target.value }))}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
            />
          </div>
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-stone-500 mb-1">主题关键词</label>
            <input
              value={themesText}
              onChange={(e) => setThemesText(e.target.value)}
              placeholder="多个关键词用逗号分隔"
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
            />
          </div>
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-stone-500 mb-1">目标体验</label>
            <input
              value={intentDraft.target_experience}
              onChange={(e) => setIntentDraft((prev) => ({ ...prev, target_experience: e.target.value }))}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
            />
          </div>
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-stone-500 mb-1">主角提示</label>
            <textarea
              value={intentDraft.protagonist_prompt}
              onChange={(e) => setIntentDraft((prev) => ({ ...prev, protagonist_prompt: e.target.value }))}
              rows={3}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
            />
          </div>
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-stone-500 mb-1">核心冲突</label>
            <textarea
              value={intentDraft.conflict_prompt}
              onChange={(e) => setIntentDraft((prev) => ({ ...prev, conflict_prompt: e.target.value }))}
              rows={3}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-stone-500 mb-1">结局倾向</label>
            <input
              value={intentDraft.ending_preference}
              onChange={(e) => setIntentDraft((prev) => ({ ...prev, ending_preference: e.target.value }))}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-stone-500 mb-1">候选分歧偏好</label>
            <select
              value={intentDraft.variant_preference}
              onChange={(e) => setIntentDraft((prev) => ({ ...prev, variant_preference: e.target.value }))}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white"
            >
              <option value="">默认分歧策略</option>
              <option value="人物差异优先">人物差异优先</option>
              <option value="世界差异优先">世界差异优先</option>
              <option value="结局差异优先">结局差异优先</option>
              <option value="尽量风格拉开">尽量风格拉开</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-stone-500 mb-1">禁用元素</label>
            <input
              value={forbiddenText}
              onChange={(e) => setForbiddenText(e.target.value)}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => saveIntentMutation.mutate()}
            disabled={saveIntentMutation.isPending}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {saveIntentMutation.isPending ? '保存中…' : '保存创作意图'}
          </button>
          <button
            onClick={() => generateConceptMutation.mutate()}
            disabled={generateConceptMutation.isPending}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {generateConceptMutation.isPending ? '生成中…' : '生成 3 版候选方向'}
          </button>
        </div>
      </section>

      <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
        <div>
          <h3 className="text-base font-semibold text-stone-800">候选方向</h3>
          <p className="mt-1 text-sm text-stone-500">先选定一条整书方向，再进入世界观、人物和章节路线细化。</p>
        </div>
        <div className="grid gap-3 lg:grid-cols-3">
          {(blueprint?.concept_variants ?? []).map((variant) => (
            <article
              key={variant.id ?? variant.variant_no}
              className={`rounded-xl border p-4 ${
                selectedVariantId === variant.id ? 'border-emerald-500 bg-emerald-50/60' : 'border-stone-200'
              }`}
            >
              {(() => {
                const variantId = variant.id ?? variant.variant_no
                const proposal = regenerationProposalByVariantId[variantId]
                const isPendingCurrent = pendingVariantId === variant.id && regenerateVariantMutation.isPending
                const hasPendingProposal = Boolean(proposal?.proposed_variant)
                return (
                  <>
              <div className="flex items-center justify-between gap-3">
                <h4 className="text-sm font-semibold text-stone-800">方向 {variant.variant_no}</h4>
                {selectedVariantId === variant.id && <span className="text-xs text-emerald-700">已选中</span>}
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-stone-600">
                <div className="rounded-lg bg-stone-50 px-2 py-2">
                  <span className="text-stone-400">主驱动</span>
                  <p className="mt-1 font-medium text-stone-700">{variant.core_driver || '未标注'}</p>
                </div>
                <div className="rounded-lg bg-stone-50 px-2 py-2">
                  <span className="text-stone-400">策略</span>
                  <p className="mt-1 font-medium text-stone-700">{variant.variant_strategy || '未标注'}</p>
                </div>
                <div className="rounded-lg bg-stone-50 px-2 py-2">
                  <span className="text-stone-400">冲突源</span>
                  <p className="mt-1 font-medium text-stone-700">{variant.conflict_source || '未标注'}</p>
                </div>
                <div className="rounded-lg bg-stone-50 px-2 py-2">
                  <span className="text-stone-400">世界结构</span>
                  <p className="mt-1 font-medium text-stone-700">{variant.world_structure || '未标注'}</p>
                </div>
                <div className="rounded-lg bg-stone-50 px-2 py-2">
                  <span className="text-stone-400">主角弧线</span>
                  <p className="mt-1 font-medium text-stone-700">{variant.protagonist_arc_mode || '未标注'}</p>
                </div>
                <div className="rounded-lg bg-stone-50 px-2 py-2">
                  <span className="text-stone-400">气质</span>
                  <p className="mt-1 font-medium text-stone-700">{variant.tone_signature || '未标注'}</p>
                </div>
              </div>
              <p className="mt-3 text-sm font-medium text-stone-800">{variant.hook}</p>
              <p className="mt-2 text-sm text-stone-600">{variant.world_pitch}</p>
              <p className="mt-2 text-sm text-stone-600">{variant.main_arc_pitch}</p>
              <p className="mt-2 text-sm text-stone-500">结局倾向：{variant.ending_pitch}</p>
              {variant.diversity_note && (
                <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
                  {variant.diversity_note}
                </p>
              )}
              {hasPendingProposal && proposal.proposed_variant && (
                <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50/70 p-3 space-y-3">
                  <div>
                    <p className="text-sm font-semibold text-amber-900">重生成提案待确认</p>
                    <p className="mt-1 text-xs text-amber-800">
                      已回炉 {proposal.attempt_count} 轮，但仍与方向 {proposal.similarity_report?.compared_variant_no ?? '其他版本'}
                      存在较高相似度。
                    </p>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs text-amber-900">
                    <div>
                      <span className="text-amber-700">相似字段</span>
                      <p className="mt-1">{proposal.similarity_report?.repeated_fields.join('、') || '无'}</p>
                    </div>
                    <div>
                      <span className="text-amber-700">重复段落</span>
                      <p className="mt-1">{proposal.similarity_report?.repeated_sections.join('、') || '无'}</p>
                    </div>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-amber-800">建议差异方向</p>
                    <ul className="mt-1 space-y-1 text-xs text-amber-900">
                      {(proposal.similarity_report?.guidance ?? []).map((item) => (
                        <li key={item}>- {item}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="space-y-2 rounded-lg bg-white/80 p-3 text-sm text-stone-700">
                    <p className="font-medium text-stone-800">{proposal.proposed_variant.hook}</p>
                    <p>{proposal.proposed_variant.world_pitch}</p>
                    <p>{proposal.proposed_variant.main_arc_pitch}</p>
                    <p className="text-xs text-stone-500">结局倾向：{proposal.proposed_variant.ending_pitch}</p>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <button
                      onClick={() =>
                        variant.id &&
                        acceptRegeneratedVariantMutation.mutate({ variantId: variant.id, payload: proposal })
                      }
                      disabled={acceptRegeneratedVariantMutation.isPending}
                      className="rounded-lg bg-amber-600 px-3 py-2 text-sm text-white hover:bg-amber-700 disabled:opacity-50"
                    >
                      接受替换
                    </button>
                    <button
                      onClick={() =>
                        setRegenerationProposalByVariantId((prev) => {
                          const next = { ...prev }
                          delete next[variantId]
                          return next
                        })
                      }
                      disabled={acceptRegeneratedVariantMutation.isPending}
                      className="rounded-lg border border-amber-300 px-3 py-2 text-sm text-amber-900 hover:bg-amber-100 disabled:opacity-50"
                    >
                      保留原版
                    </button>
                  </div>
                </div>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                {variant.differentiators.map((item) => (
                  <span key={item} className="rounded-full bg-white px-2 py-1 text-xs text-stone-600">
                    {item}
                  </span>
                ))}
              </div>
              <div className="mt-4 grid gap-2">
                <button
                  onClick={() => variant.id && selectVariantMutation.mutate(variant.id)}
                  disabled={!variant.id || selectVariantMutation.isPending || pendingVariantId !== null}
                  className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-700 hover:bg-white disabled:opacity-50"
                >
                  选择这一版
                </button>
                <button
                  onClick={() => variant.id && regenerateVariantMutation.mutate(variant.id)}
                  disabled={
                    !variant.id ||
                    Boolean(selectedVariantId) ||
                    pendingVariantId !== null ||
                    selectVariantMutation.isPending ||
                    acceptRegeneratedVariantMutation.isPending
                  }
                  className="w-full rounded-lg bg-stone-100 px-3 py-2 text-sm text-stone-700 hover:bg-stone-200 disabled:opacity-50"
                >
                  {isPendingCurrent ? '重生成中…' : '仅重生成这一版'}
                </button>
              </div>
                  </>
                )
              })()}
            </article>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
        <div>
          <h3 className="text-base font-semibold text-stone-800">世界观蓝图</h3>
          <p className="mt-1 text-sm text-stone-500">先锁定世界硬规则，再让人物和章节路线在这套约束内展开。</p>
        </div>
        <textarea
          value={worldFeedback}
          onChange={(e) => setWorldFeedback(e.target.value)}
          rows={2}
          placeholder="可选：补充本层微调要求，例如“更偏江湖感，不要过强神怪设定”。"
          className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => generateWorldMutation.mutate()}
            disabled={!selectedVariantId || generateWorldMutation.isPending}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {generateWorldMutation.isPending ? '生成中…' : '生成世界观草稿'}
          </button>
          <button
            onClick={() => confirmWorldMutation.mutate()}
            disabled={!worldDraft || confirmWorldMutation.isPending}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {confirmWorldMutation.isPending ? '确认中…' : '确认世界观'}
          </button>
        </div>
        {worldDraft && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-stone-500 mb-1">世界概述</label>
              <textarea
                value={worldDraft.setting_summary}
                onChange={(e) => setWorldDraft({ ...worldDraft, setting_summary: e.target.value })}
                rows={4}
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label className="block text-xs font-medium text-stone-500 mb-1">时代背景</label>
                <textarea
                  value={worldDraft.era_context}
                  onChange={(e) => setWorldDraft({ ...worldDraft, era_context: e.target.value })}
                  rows={3}
                  className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-stone-500 mb-1">社会秩序</label>
                <textarea
                  value={worldDraft.social_order}
                  onChange={(e) => setWorldDraft({ ...worldDraft, social_order: e.target.value })}
                  rows={3}
                  className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                />
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label className="block text-xs font-medium text-stone-500 mb-1">历史伤痕</label>
                <textarea
                  value={joinTags(worldDraft.historical_wounds)}
                  onChange={(e) => setWorldDraft({ ...worldDraft, historical_wounds: parseTags(e.target.value) })}
                  rows={3}
                  className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-stone-500 mb-1">公开秘密</label>
                <textarea
                  value={joinTags(worldDraft.public_secrets)}
                  onChange={(e) => setWorldDraft({ ...worldDraft, public_secrets: parseTags(e.target.value) })}
                  rows={3}
                  className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                />
              </div>
            </div>
            <div className="rounded-xl border border-stone-200 p-4 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-stone-800">力量体系</p>
                <button
                  type="button"
                  onClick={() =>
                    setWorldDraft({
                      ...worldDraft,
                      power_system: {
                        ...worldDraft.power_system,
                        costs: worldDraft.power_system.costs.length ? worldDraft.power_system.costs : [''],
                        limitations: worldDraft.power_system.limitations.length ? worldDraft.power_system.limitations : [''],
                        advancement_path: worldDraft.power_system.advancement_path.length ? worldDraft.power_system.advancement_path : [''],
                        symbols: worldDraft.power_system.symbols.length ? worldDraft.power_system.symbols : [''],
                      },
                    })
                  }
                  className="text-xs text-stone-500 hover:text-stone-700"
                >
                  初始化细项
                </button>
              </div>
              <textarea
                value={worldDraft.power_system.core_mechanics}
                onChange={(e) =>
                  setWorldDraft({
                    ...worldDraft,
                    power_system: { ...worldDraft.power_system, core_mechanics: e.target.value },
                  })
                }
                rows={3}
                placeholder="核心机制"
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <label className="block text-xs font-medium text-stone-500 mb-1">代价</label>
                  <textarea
                    value={joinTags(worldDraft.power_system.costs)}
                    onChange={(e) =>
                      setWorldDraft({
                        ...worldDraft,
                        power_system: { ...worldDraft.power_system, costs: parseTags(e.target.value) },
                      })
                    }
                    rows={3}
                    className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-500 mb-1">限制</label>
                  <textarea
                    value={joinTags(worldDraft.power_system.limitations)}
                    onChange={(e) =>
                      setWorldDraft({
                        ...worldDraft,
                        power_system: { ...worldDraft.power_system, limitations: parseTags(e.target.value) },
                      })
                    }
                    rows={3}
                    className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-500 mb-1">成长路径</label>
                  <textarea
                    value={joinTags(worldDraft.power_system.advancement_path)}
                    onChange={(e) =>
                      setWorldDraft({
                        ...worldDraft,
                        power_system: { ...worldDraft.power_system, advancement_path: parseTags(e.target.value) },
                      })
                    }
                    rows={3}
                    className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-500 mb-1">象征特征</label>
                  <textarea
                    value={joinTags(worldDraft.power_system.symbols)}
                    onChange={(e) =>
                      setWorldDraft({
                        ...worldDraft,
                        power_system: { ...worldDraft.power_system, symbols: parseTags(e.target.value) },
                      })
                    }
                    rows={3}
                    className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                  />
                </div>
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-xs font-medium text-stone-500">不可变规则</p>
              {worldDraft.immutable_rules.map((rule, index) => (
                <div key={`${rule.key}-${index}`} className="grid gap-2 md:grid-cols-[140px_minmax(0,1fr)_120px_minmax(0,1fr)]">
                  <input
                    value={rule.key}
                    onChange={(e) =>
                      setWorldDraft({
                        ...worldDraft,
                        immutable_rules: worldDraft.immutable_rules.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, key: e.target.value } : item,
                        ),
                      })
                    }
                    className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                  />
                  <input
                    value={rule.description}
                    onChange={(e) =>
                      setWorldDraft({
                        ...worldDraft,
                        immutable_rules: worldDraft.immutable_rules.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, description: e.target.value } : item,
                        ),
                      })
                    }
                    className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                  />
                  <input
                    value={rule.category ?? ''}
                    onChange={(e) =>
                      setWorldDraft({
                        ...worldDraft,
                        immutable_rules: worldDraft.immutable_rules.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, category: e.target.value } : item,
                        ),
                      })
                    }
                    className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                  />
                  <input
                    value={rule.rationale ?? ''}
                    onChange={(e) =>
                      setWorldDraft({
                        ...worldDraft,
                        immutable_rules: worldDraft.immutable_rules.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, rationale: e.target.value } : item,
                        ),
                      })
                    }
                    className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                    placeholder="规则缘由"
                  />
                </div>
              ))}
              <button
                type="button"
                onClick={() =>
                  setWorldDraft({
                    ...worldDraft,
                    immutable_rules: [...worldDraft.immutable_rules, defaultImmutableRule()],
                  })
                }
                className="rounded-lg border border-dashed border-stone-300 px-3 py-2 text-sm text-stone-600 hover:bg-stone-50"
              >
                新增不可变规则
              </button>
            </div>
            <div className="space-y-2">
              <p className="text-xs font-medium text-stone-500">禁忌规则</p>
              {worldDraft.taboo_rules.map((rule, index) => (
                <div key={`${rule.key}-${index}`} className="grid gap-2 md:grid-cols-[140px_minmax(0,1fr)_minmax(0,1fr)]">
                  <input
                    value={rule.key}
                    onChange={(e) =>
                      setWorldDraft({
                        ...worldDraft,
                        taboo_rules: worldDraft.taboo_rules.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, key: e.target.value } : item,
                        ),
                      })
                    }
                    className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                  />
                  <input
                    value={rule.description}
                    onChange={(e) =>
                      setWorldDraft({
                        ...worldDraft,
                        taboo_rules: worldDraft.taboo_rules.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, description: e.target.value } : item,
                        ),
                      })
                    }
                    className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                  />
                  <input
                    value={rule.consequence}
                    onChange={(e) =>
                      setWorldDraft({
                        ...worldDraft,
                        taboo_rules: worldDraft.taboo_rules.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, consequence: e.target.value } : item,
                        ),
                      })
                    }
                    className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                    placeholder="触犯后果"
                  />
                </div>
              ))}
              <button
                type="button"
                onClick={() =>
                  setWorldDraft({
                    ...worldDraft,
                    taboo_rules: [...worldDraft.taboo_rules, defaultTabooRule()],
                  })
                }
                className="rounded-lg border border-dashed border-stone-300 px-3 py-2 text-sm text-stone-600 hover:bg-stone-50"
              >
                新增禁忌规则
              </button>
            </div>
            <div className="space-y-2">
              <p className="text-xs font-medium text-stone-500">关键地点</p>
              {worldDraft.geography.map((location, index) => (
                <div key={`${location.name}-${index}`} className="grid gap-2 md:grid-cols-[160px_160px_minmax(0,1fr)]">
                  <input
                    value={location.name}
                    onChange={(e) =>
                      setWorldDraft({
                        ...worldDraft,
                        geography: worldDraft.geography.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, name: e.target.value } : item,
                        ),
                      })
                    }
                    className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                    placeholder="地点名"
                  />
                  <input
                    value={location.role}
                    onChange={(e) =>
                      setWorldDraft({
                        ...worldDraft,
                        geography: worldDraft.geography.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, role: e.target.value } : item,
                        ),
                      })
                    }
                    className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                    placeholder="地点作用"
                  />
                  <input
                    value={location.description}
                    onChange={(e) =>
                      setWorldDraft({
                        ...worldDraft,
                        geography: worldDraft.geography.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, description: e.target.value } : item,
                        ),
                      })
                    }
                    className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                    placeholder="地点描述"
                  />
                </div>
              ))}
              <button
                type="button"
                onClick={() => setWorldDraft({ ...worldDraft, geography: [...worldDraft.geography, defaultLocation()] })}
                className="rounded-lg border border-dashed border-stone-300 px-3 py-2 text-sm text-stone-600 hover:bg-stone-50"
              >
                新增地点
              </button>
            </div>
            <div className="space-y-2">
              <p className="text-xs font-medium text-stone-500">势力结构</p>
              {worldDraft.factions.map((faction, index) => (
                <div key={`${faction.name}-${index}`} className="rounded-xl border border-stone-200 p-3 space-y-2">
                  <div className="grid gap-2 md:grid-cols-3">
                    <input
                      value={faction.name}
                      onChange={(e) =>
                        setWorldDraft({
                          ...worldDraft,
                          factions: worldDraft.factions.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, name: e.target.value } : item,
                          ),
                        })
                      }
                      className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                      placeholder="势力名"
                    />
                    <input
                      value={faction.position}
                      onChange={(e) =>
                        setWorldDraft({
                          ...worldDraft,
                          factions: worldDraft.factions.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, position: e.target.value } : item,
                          ),
                        })
                      }
                      className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                      placeholder="势力定位"
                    />
                    <input
                      value={faction.goal}
                      onChange={(e) =>
                        setWorldDraft({
                          ...worldDraft,
                          factions: worldDraft.factions.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, goal: e.target.value } : item,
                          ),
                        })
                      }
                      className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                      placeholder="势力目标"
                    />
                  </div>
                  <textarea
                    value={joinTags(faction.methods)}
                    onChange={(e) =>
                      setWorldDraft({
                        ...worldDraft,
                        factions: worldDraft.factions.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, methods: parseTags(e.target.value) } : item,
                        ),
                      })
                    }
                    rows={2}
                    className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                    placeholder="手段 / 作风"
                  />
                  <div className="grid gap-2 md:grid-cols-2">
                    <input
                      value={faction.public_image}
                      onChange={(e) =>
                        setWorldDraft({
                          ...worldDraft,
                          factions: worldDraft.factions.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, public_image: e.target.value } : item,
                          ),
                        })
                      }
                      className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                      placeholder="公开形象"
                    />
                    <input
                      value={faction.hidden_truth}
                      onChange={(e) =>
                        setWorldDraft({
                          ...worldDraft,
                          factions: worldDraft.factions.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, hidden_truth: e.target.value } : item,
                          ),
                        })
                      }
                      className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                      placeholder="隐藏真相"
                    />
                  </div>
                </div>
              ))}
              <button
                type="button"
                onClick={() => setWorldDraft({ ...worldDraft, factions: [...worldDraft.factions, defaultFaction()] })}
                className="rounded-lg border border-dashed border-stone-300 px-3 py-2 text-sm text-stone-600 hover:bg-stone-50"
              >
                新增势力
              </button>
            </div>
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
        <div>
          <h3 className="text-base font-semibold text-stone-800">人物蓝图</h3>
          <p className="mt-1 text-sm text-stone-500">角色核心动机、不可突变特质和关系约束会作为后续正文的强校验来源。</p>
        </div>
        <textarea
          value={characterFeedback}
          onChange={(e) => setCharacterFeedback(e.target.value)}
          rows={2}
          placeholder="可选：补充本层微调要求，例如“主角不要太正统，要更复杂一些”。"
          className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => generateCharacterMutation.mutate()}
            disabled={!canGenerateCharacters || generateCharacterMutation.isPending}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {generateCharacterMutation.isPending ? '生成中…' : '生成人物蓝图'}
          </button>
          <button
            onClick={() => confirmCharacterMutation.mutate()}
            disabled={characterDraft.length === 0 || confirmCharacterMutation.isPending}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {confirmCharacterMutation.isPending ? '确认中…' : '确认人物蓝图'}
          </button>
          <button
            onClick={() => confirmRelationshipGraphMutation.mutate()}
            disabled={relationshipGraphDraft.length === 0 || confirmRelationshipGraphMutation.isPending}
            className="rounded-lg bg-stone-700 px-4 py-2 text-sm text-white hover:bg-stone-800 disabled:opacity-50"
          >
            {confirmRelationshipGraphMutation.isPending ? '确认中…' : '单独确认关系图谱'}
          </button>
        </div>
        <div className="space-y-3">
          {characterDraft.map((character, index) => (
            <article key={`${character.name}-${index}`} className="rounded-xl border border-stone-200 p-4 space-y-3">
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <label className="block text-xs font-medium text-stone-500 mb-1">姓名</label>
                  <input
                    value={character.name}
                    onChange={(e) =>
                      setCharacterDraft((prev) =>
                        prev.map((item, itemIndex) => (itemIndex === index ? { ...item, name: e.target.value } : item)),
                      )
                    }
                    className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-500 mb-1">定位</label>
                  <input
                    value={character.role}
                    onChange={(e) =>
                      setCharacterDraft((prev) =>
                        prev.map((item, itemIndex) => (itemIndex === index ? { ...item, role: e.target.value } : item)),
                      )
                    }
                    className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <textarea
                value={character.public_persona}
                onChange={(e) =>
                  setCharacterDraft((prev) =>
                    prev.map((item, itemIndex) =>
                      itemIndex === index ? { ...item, public_persona: e.target.value } : item,
                    ),
                  )
                }
                rows={2}
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
              <input
                value={character.core_motivation}
                onChange={(e) =>
                  setCharacterDraft((prev) =>
                    prev.map((item, itemIndex) =>
                      itemIndex === index ? { ...item, core_motivation: e.target.value } : item,
                    ),
                  )
                }
                placeholder="核心动机"
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
              <input
                value={character.fatal_flaw}
                onChange={(e) =>
                  setCharacterDraft((prev) =>
                    prev.map((item, itemIndex) => (itemIndex === index ? { ...item, fatal_flaw: e.target.value } : item)),
                  )
                }
                placeholder="致命缺口"
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
            </article>
          ))}
        </div>
        <div className="rounded-2xl border border-stone-200 p-4 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h4 className="text-sm font-semibold text-stone-800">人物关系图谱</h4>
              <p className="mt-1 text-xs text-stone-500">这里锁定核心人物关系边。已发布事实冲突时，系统会要求进入关系重规划流程。</p>
            </div>
            <button
              type="button"
              onClick={() =>
                setRelationshipGraphDraft((prev) => [
                  ...prev,
                  {
                    edge_id: `rel-${prev.length + 1}`,
                    source_character_id: relationshipNodes[0]?.character_id ?? '',
                    target_character_id: relationshipNodes[1]?.character_id ?? relationshipNodes[0]?.character_id ?? '',
                    relation_type: '',
                    polarity: '复杂',
                    intensity: 3,
                    visibility: '半公开',
                    stability: '稳定',
                    summary: '',
                    hidden_truth: '',
                    non_breakable_without_reveal: false,
                  },
                ])
              }
              className="rounded-lg border border-dashed border-stone-300 px-3 py-2 text-sm text-stone-600 hover:bg-stone-50"
            >
              新增关系边
            </button>
          </div>

          {relationshipGraphDraft.length === 0 ? (
            <div className="rounded-xl border border-dashed border-stone-300 px-4 py-6 text-sm text-stone-500">
              还没有关系边。生成人物蓝图后，系统会先给出一版关系草稿；你也可以手动新增。
            </div>
          ) : (
            <div className="space-y-3">
              {relationshipGraphDraft.map((edge, index) => (
                <div key={edge.edge_id} className="rounded-xl border border-stone-200 p-3 space-y-2">
                  <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-4">
                    <select
                      value={edge.source_character_id}
                      onChange={(e) =>
                        setRelationshipGraphDraft((prev) =>
                          prev.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, source_character_id: e.target.value } : item,
                          ),
                        )
                      }
                      className="rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white"
                    >
                      {relationshipNodes.map((node) => (
                        <option key={node.character_id} value={node.character_id}>
                          {node.name}
                        </option>
                      ))}
                    </select>
                    <select
                      value={edge.target_character_id}
                      onChange={(e) =>
                        setRelationshipGraphDraft((prev) =>
                          prev.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, target_character_id: e.target.value } : item,
                          ),
                        )
                      }
                      className="rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white"
                    >
                      {relationshipNodes.map((node) => (
                        <option key={node.character_id} value={node.character_id}>
                          {node.name}
                        </option>
                      ))}
                    </select>
                    <input
                      value={edge.relation_type}
                      onChange={(e) =>
                        setRelationshipGraphDraft((prev) =>
                          prev.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, relation_type: e.target.value } : item,
                          ),
                        )
                      }
                      className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                      placeholder="关系类型"
                    />
                    <select
                      value={edge.polarity}
                      onChange={(e) =>
                        setRelationshipGraphDraft((prev) =>
                          prev.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, polarity: e.target.value as RelationshipBlueprintEdge['polarity'] } : item,
                          ),
                        )
                      }
                      className="rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white"
                    >
                      <option value="正向">正向</option>
                      <option value="负向">负向</option>
                      <option value="复杂">复杂</option>
                      <option value="伪装">伪装</option>
                    </select>
                  </div>
                  <div className="grid gap-2 md:grid-cols-3">
                    <select
                      value={edge.visibility}
                      onChange={(e) =>
                        setRelationshipGraphDraft((prev) =>
                          prev.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, visibility: e.target.value as RelationshipBlueprintEdge['visibility'] } : item,
                          ),
                        )
                      }
                      className="rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white"
                    >
                      <option value="公开">公开</option>
                      <option value="半公开">半公开</option>
                      <option value="隐藏">隐藏</option>
                      <option value="误导性表象">误导性表象</option>
                    </select>
                    <select
                      value={edge.stability}
                      onChange={(e) =>
                        setRelationshipGraphDraft((prev) =>
                          prev.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, stability: e.target.value as RelationshipBlueprintEdge['stability'] } : item,
                          ),
                        )
                      }
                      className="rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white"
                    >
                      <option value="稳定">稳定</option>
                      <option value="脆弱">脆弱</option>
                      <option value="正在转变">正在转变</option>
                    </select>
                    <input
                      value={String(edge.intensity)}
                      onChange={(e) =>
                        setRelationshipGraphDraft((prev) =>
                          prev.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, intensity: parseNumber(e.target.value) } : item,
                          ),
                        )
                      }
                      className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                      placeholder="强度 1-5"
                    />
                  </div>
                  <textarea
                    value={edge.summary}
                    onChange={(e) =>
                      setRelationshipGraphDraft((prev) =>
                        prev.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, summary: e.target.value } : item,
                        ),
                      )
                    }
                    rows={2}
                    className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                    placeholder="关系摘要"
                  />
                  <textarea
                    value={edge.hidden_truth}
                    onChange={(e) =>
                      setRelationshipGraphDraft((prev) =>
                        prev.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, hidden_truth: e.target.value } : item,
                        ),
                      )
                    }
                    rows={2}
                    className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                    placeholder="隐藏真相 / 关系底牌"
                  />
                  <label className="flex items-center gap-2 text-xs text-stone-600">
                    <input
                      type="checkbox"
                      checked={edge.non_breakable_without_reveal}
                      onChange={(e) =>
                        setRelationshipGraphDraft((prev) =>
                          prev.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, non_breakable_without_reveal: e.target.checked } : item,
                          ),
                        )
                      }
                    />
                    必须通过“揭示事件”才能合法改写
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => upsertRelationshipEdgeMutation.mutate(edge)}
                      disabled={upsertRelationshipEdgeMutation.isPending}
                      className="rounded-lg bg-stone-800 px-3 py-2 text-sm text-white hover:bg-stone-900 disabled:opacity-50"
                    >
                      保存这条关系
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        setRelationshipGraphDraft((prev) => prev.filter((_, itemIndex) => itemIndex !== index))
                      }
                      className="rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-600 hover:bg-stone-50"
                    >
                      删除
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {relationshipPending.length > 0 && (
            <div className="rounded-xl border border-amber-200 bg-amber-50/50 p-4 space-y-3">
              <h5 className="text-sm font-semibold text-amber-900">待确认人物 / 关系</h5>
              {relationshipPending.map((item) => (
                <div key={item.id ?? `${item.item_type}-${item.summary}`} className="rounded-lg bg-white p-3 text-sm text-stone-700">
                  <p className="font-medium">{item.summary || (item.item_type === 'character' ? item.character?.name : item.relationship?.summary)}</p>
                  <p className="mt-1 text-xs text-stone-500">
                    来源：第 {item.source_chapter ?? 0} 章 · {item.source_scene_ref || '未标注场景'}
                  </p>
                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      onClick={() => item.id && confirmRelationshipPendingMutation.mutate(item.id)}
                      className="rounded-lg bg-amber-600 px-3 py-1.5 text-xs text-white hover:bg-amber-700"
                    >
                      确认纳入
                    </button>
                    <button
                      type="button"
                      onClick={() => item.id && rejectRelationshipPendingMutation.mutate(item.id)}
                      className="rounded-lg border border-amber-300 px-3 py-1.5 text-xs text-amber-700 hover:bg-amber-100"
                    >
                      拒绝
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {relationshipConflict && (
            <div className="rounded-xl border border-red-200 bg-red-50/60 p-4 space-y-3">
              <h5 className="text-sm font-semibold text-red-900">关系冲突：不可直接改写已发布事实</h5>
              <p className="text-sm text-red-800">{relationshipConflict.conflict_summary}</p>
              <p className="text-xs text-red-700">
                冲突来源：第 {relationshipConflict.source_chapter} 章 {relationshipConflict.source_scene_ref || ''}
              </p>
              <p className="text-xs text-red-700">已发布事实：{relationshipConflict.immutable_fact}</p>
              <textarea
                value={relationshipDesiredChange}
                onChange={(e) => setRelationshipDesiredChange(e.target.value)}
                rows={2}
                placeholder="填写你希望未来把这段关系改成什么样"
                className="w-full rounded-lg border border-red-200 bg-white px-3 py-2 text-sm"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => createRelationshipReplanMutation.mutate()}
                  className="rounded-lg bg-red-600 px-3 py-2 text-sm text-white hover:bg-red-700"
                >
                  生成关系重规划提案
                </button>
                <button
                  type="button"
                  onClick={() => setRelationshipConflict(null)}
                  className="rounded-lg border border-red-300 px-3 py-2 text-sm text-red-700 hover:bg-red-100"
                >
                  暂不处理
                </button>
              </div>
            </div>
          )}

          {relationshipReplan && (
            <div className="rounded-xl border border-indigo-200 bg-indigo-50/60 p-4 space-y-3">
              <h5 className="text-sm font-semibold text-indigo-900">关系重规划提案</h5>
              <p className="text-sm text-indigo-800">策略：{relationshipReplan.proposal.strategy}</p>
              <p className="text-sm text-indigo-800">改动摘要：{relationshipReplan.proposal.change_summary}</p>
              <p className="text-xs text-indigo-700">
                影响未来章节：{relationshipReplan.proposal.affected_future_chapters.join('、') || '未标注'}
              </p>
              <ul className="list-disc pl-5 text-xs text-indigo-700 space-y-1">
                {relationshipReplan.proposal.required_reveals.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => confirmRelationshipReplanMutation.mutate()}
                  className="rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-700"
                >
                  确认采用这份提案
                </button>
                <button
                  type="button"
                  onClick={() => setRelationshipReplan(null)}
                  className="rounded-lg border border-indigo-300 px-3 py-2 text-sm text-indigo-700 hover:bg-indigo-100"
                >
                  暂不采用
                </button>
              </div>
            </div>
          )}
        </div>
      </section>

      <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
        <div>
          <h3 className="text-base font-semibold text-stone-800">章节路线</h3>
          <p className="mt-1 text-sm text-stone-500">锁定整书章节走向后，后续 scene 写作会在该路线内做受控扩写。</p>
        </div>
        <textarea
          value={roadmapFeedback}
          onChange={(e) => setRoadmapFeedback(e.target.value)}
          rows={2}
          placeholder="可选：补充本层微调要求，例如“前 3 章开局更猛，中段节奏更压抑”。"
          className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => generateRoadmapMutation.mutate()}
            disabled={!canGenerateRoadmap || generateRoadmapMutation.isPending}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {generateRoadmapMutation.isPending ? '生成中…' : '生成章节路线'}
          </button>
          <button
            onClick={() => confirmRoadmapMutation.mutate()}
            disabled={roadmapDraft.length === 0 || confirmRoadmapMutation.isPending}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {confirmRoadmapMutation.isPending ? '锁定中…' : '锁定整书蓝图'}
          </button>
        </div>
        <div className="space-y-3">
          {roadmapDraft.map((item, index) => (
            <article key={item.chapter_number} className="rounded-xl border border-stone-200 p-4 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <h4 className="text-sm font-semibold text-stone-800">第 {item.chapter_number} 章</h4>
                <span className="text-xs text-stone-500">
                  计划线索 {item.planned_loops.length} 条
                </span>
              </div>
              <input
                value={item.title}
                onChange={(e) =>
                  setRoadmapDraft((prev) =>
                    prev.map((row, rowIndex) => (rowIndex === index ? { ...row, title: e.target.value } : row)),
                  )
                }
                placeholder="章节标题"
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
              <textarea
                value={item.goal}
                onChange={(e) =>
                  setRoadmapDraft((prev) =>
                    prev.map((row, rowIndex) => (rowIndex === index ? { ...row, goal: e.target.value } : row)),
                  )
                }
                rows={2}
                placeholder="章节目标"
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
              <textarea
                value={item.core_conflict}
                onChange={(e) =>
                  setRoadmapDraft((prev) =>
                    prev.map((row, rowIndex) =>
                      rowIndex === index ? { ...row, core_conflict: e.target.value } : row,
                    ),
                  )
                }
                rows={2}
                placeholder="核心冲突"
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
              <input
                value={item.turning_point}
                onChange={(e) =>
                  setRoadmapDraft((prev) =>
                    prev.map((row, rowIndex) =>
                      rowIndex === index ? { ...row, turning_point: e.target.value } : row,
                    ),
                  )
                }
                placeholder="关键转折"
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
              <input
                value={item.closure_function}
                onChange={(e) =>
                  setRoadmapDraft((prev) =>
                    prev.map((row, rowIndex) =>
                      rowIndex === index ? { ...row, closure_function: e.target.value } : row,
                    ),
                  )
                }
                placeholder="结尾功能"
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
              <div className="grid gap-3 md:grid-cols-2">
                <textarea
                  value={joinTags(item.character_progress)}
                  onChange={(e) =>
                    setRoadmapDraft((prev) =>
                      prev.map((row, rowIndex) =>
                        rowIndex === index ? { ...row, character_progress: parseTags(e.target.value) } : row,
                      ),
                    )
                  }
                  rows={2}
                  placeholder="人物推进，多项可用逗号分隔"
                  className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                />
                <textarea
                  value={joinTags(item.relationship_progress)}
                  onChange={(e) =>
                    setRoadmapDraft((prev) =>
                      prev.map((row, rowIndex) =>
                        rowIndex === index ? { ...row, relationship_progress: parseTags(e.target.value) } : row,
                      ),
                    )
                  }
                  rows={2}
                  placeholder="关系推进，多项可用逗号分隔"
                  className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                />
              </div>
              <div className="grid gap-2 md:grid-cols-2">
                <div className="rounded-lg bg-stone-50 px-3 py-2 text-xs text-stone-600">
                  人物推进：{item.character_progress.length > 0 ? item.character_progress.join('；') : '未指定'}
                </div>
                <div className="rounded-lg bg-stone-50 px-3 py-2 text-xs text-stone-600">
                  关系推进：{item.relationship_progress.length > 0 ? item.relationship_progress.join('；') : '未指定'}
                </div>
              </div>
            </article>
          ))}
          {roadmapToShow.length === 0 && (
            <div className="rounded-xl border border-dashed border-stone-300 px-4 py-6 text-sm text-stone-500">
              还没有章节路线。请先确认世界观和人物蓝图，再生成整书章节走向。
            </div>
          )}
        </div>
      </section>

      {blueprint?.status === 'locked' && (
        <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
          <div>
            <h3 className="text-base font-semibold text-stone-800">未来章节重规划</h3>
            <p className="mt-1 text-sm text-stone-500">只允许重规划未来未发布章节，不会改写已发布内容及其核心事实。</p>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <div>
              <label className="block text-xs font-medium text-stone-500 mb-1">起始章节</label>
              <input
                type="number"
                min={1}
                value={replanStart}
                onChange={(e) => setReplanStart(Number(e.target.value))}
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs font-medium text-stone-500 mb-1">重规划原因</label>
              <input
                value={replanReason}
                onChange={(e) => setReplanReason(e.target.value)}
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
            </div>
          </div>
          <textarea
            value={replanGuidance}
            onChange={(e) => setReplanGuidance(e.target.value)}
            rows={3}
            placeholder="例如：保留主线复仇，但让中段感情线更痛，增加误会与错位。"
            className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
          />
          <button
            onClick={() => replanMutation.mutate()}
            disabled={replanMutation.isPending}
            className="rounded-lg bg-amber-600 px-4 py-2 text-sm text-white hover:bg-amber-700 disabled:opacity-50"
          >
            {replanMutation.isPending ? '重规划中…' : '生成新蓝图版本'}
          </button>
          <div className="rounded-xl bg-stone-50 p-3 text-sm text-stone-600">
            版本历史：
            {revisions.length > 0 ? (
              <ul className="mt-2 space-y-1">
                {revisions.map((item) => (
                  <li key={item.id}>
                    v{item.revision_number}
                    {item.is_active ? '（当前生效）' : ''}
                    ：{item.change_reason || '未填写原因'}
                  </li>
                ))}
              </ul>
            ) : (
              <span className="ml-2">暂无版本记录</span>
            )}
          </div>
        </section>
      )}
    </div>
  )
}
