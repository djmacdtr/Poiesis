/**
 * 蓝图工作台：在同一页面里逐层生成、编辑并确认整书蓝图。
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { RelationshipGraphPanel } from '@/components/relationship-graph/RelationshipGraphPanel'
import { RelationshipGraphWorkspaceEditor } from '@/components/relationship-graph/RelationshipGraphWorkspaceEditor'
import {
  type WorkspaceSectionKey,
  type WorkspaceSidebarItem,
  WorkspaceSidebar,
} from '@/components/workspace/WorkspaceSidebar'
import { WorkspaceInspectorRail } from '@/components/workspace/WorkspaceInspectorRail'
import { RoadmapArcBoard } from '@/components/workspace/RoadmapArcBoard'
import { RoadmapChapterList } from '@/components/workspace/RoadmapChapterList'
import { RoadmapControlPanel, type RoadmapViewMode } from '@/components/workspace/RoadmapControlPanel'
import {
  CreativeRepairBoard,
  type CreativeIssueSourceFilter,
} from '@/components/workspace/CreativeRepairBoard'
import {
  RoadmapInspectorPanel,
  type RoadmapInspectorState,
} from '@/components/workspace/RoadmapInspectorPanel'
import {
  formatBlueprintStatusLabel,
  formatBlueprintStepLabel,
  formatContinuityEventKindLabel,
  formatContinuityLoopLabel,
  formatCreativeSourceLayerLabel,
  formatLanguageLabel,
  formatLoopStatusLabel,
  formatNamingPolicyLabel,
  formatStylePresetLabel,
  parseTaskStatusValue,
  formatTaskStatusLabel,
} from '@/lib/display-labels'
import {
  buildLocalContinuityState,
  buildLocalRoadmapIssues,
  deriveStoryArcsFromRoadmapDraft,
  summarizeRoadmapLockState,
} from '@/lib/roadmap-workspace'
import {
  buildCharacterNodesFromBlueprint,
  buildRelationshipGraphViewModel,
  normalizeCharacterNodeId,
} from '@/lib/relationship-graph'
import {
  acceptRegeneratedConceptVariant,
  applyCreativeRepairProposal,
  confirmRelationshipGraph,
  confirmRelationshipPending,
  confirmCharacterBlueprint,
  confirmRoadmap,
  confirmWorldBlueprint,
  confirmRelationshipReplan,
  createRelationshipReplan,
  generateCharacterBlueprint,
  generateConceptVariants,
  generateStoryArcs,
  generateWorldBlueprint,
  expandStoryArc,
  planCreativeRepairs,
  regenerateArcChapter,
  regenerateStoryArc,
  regenerateConceptVariant,
  rejectRelationshipPending,
  reverifyCreativeIssues,
  replanBlueprint,
  rollbackCreativeRepairRun,
  saveCreationIntent,
  selectConceptVariant,
  upsertRelationshipEdge,
} from '@/services/books'
import type {
  BlueprintContinuityState,
  BookItem,
  BookBlueprint,
  ChapterRoadmapItem,
  CharacterNode,
  CharacterBlueprint,
  ConceptVariantRegenerationResult,
  CreativeIssue,
  CreativeRepairProposal,
  CreativeRepairRun,
  PlannedLoopItem,
  PlannedRelationshipBeat,
  PlannedTaskItem,
  CreationIntent,
  FactionBlueprint,
  ImmutableRuleBlueprint,
  LocationBlueprint,
  RelationshipBlueprintEdge,
  RelationshipConflictReport,
  RelationshipGraphSelection,
  RelationshipPendingItem,
  RelationshipReplanResponse,
  TabooRuleBlueprint,
  WorldBlueprint,
} from '@/types'

interface BookBlueprintWorkspaceProps {
  bookId: number
  blueprint: BookBlueprint | undefined
  activeBook?: BookItem | null
}

/**
 * 后端 current_step 仍然是蓝图工作流的真实阶段标记，
 * 但页内导航的颗粒度比它更细，因此这里做一次映射：
 * - 后端负责“当前在 intent / world / roadmap 哪一层”；
 * - 前端负责“这一层在工作台里对应哪个可见分区”。
 */
function mapBlueprintStepToWorkspaceSection(step?: string | null): WorkspaceSectionKey {
  if (step === 'concept' || step === 'concept_variants') return 'concept'
  if (step === 'world') return 'world'
  if (step === 'characters') return 'characters'
  if (step === 'relationships') return 'relationships'
  if (step === 'roadmap' || step === 'story_arcs') return 'roadmap'
  if (step === 'continuity') return 'continuity'
  return 'intent'
}

function parseTags(value: string): string[] {
  return value
    .split(/[,，、；;\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function joinTags(values: string[]): string {
  return values.join('，')
}

function serializeChapterTasks(tasks: PlannedTaskItem[]): string {
  /**
   * 任务编辑区改成“摘要优先、中文状态优先”的序列化顺序：
   * - 用户首先看到的是任务内容，而不是内部 task_id；
   * - 原始 task_id 仍然保留在最后一列，便于需要时人工排查；
   * - 旧格式依然由 parseChapterTasks 兼容，避免已经输入过的内容瞬间失效。
   */
  return tasks
    .map((task) =>
      [
        task.summary,
        formatTaskStatusLabel(task.status),
        task.related_characters.join(','),
        task.due_end_chapter ?? '',
        task.task_id,
      ].join('|'),
    )
    .join('\n')
}

function parseChapterTasks(value: string): PlannedTaskItem[] {
  return value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      /**
       * 兼容两种编辑格式：
       * 1. 旧格式：task_id|status|summary|人物A,人物B|最迟章号
       * 2. 新格式：summary|状态|人物A,人物B|最迟章号|task_id
       *
       * 新格式面向作者阅读更友好，旧格式仍然允许继续解析，避免打断已存在草稿。
       */
      const parts = line.split(/[|｜]/).map((item) => item.trim())
      /**
       * 旧格式的最后一列是“最迟章号”，通常为空或纯数字；
       * 新格式的最后一列是“任务标识”，通常是 verify-bloodline 这类内部键。
       * 因此这里用最后一列是否为数字来区分两种输入。
       */
      const looksLikeOldFormat =
        parts.length >= 5 && ((parts[4] ?? '') === '' || Number.isFinite(Number(parts[4])))

      const [first = '', second = '', third = '', fourth = '', fifth = ''] = parts
      const taskId = looksLikeOldFormat ? first : fifth
      const status = looksLikeOldFormat ? second : second
      const summary = looksLikeOldFormat ? third : first
      const relatedCharacters = looksLikeOldFormat ? fourth : third
      const dueEnd = looksLikeOldFormat ? fifth : fourth
      return {
        task_id: taskId.trim() || `manual-task-${index + 1}`,
        status: parseTaskStatusValue(status),
        summary: summary.trim(),
        related_characters: parseTags(relatedCharacters),
        due_end_chapter:
          dueEnd.trim() && Number.isFinite(Number(dueEnd.trim())) ? Number(dueEnd.trim()) : null,
      }
    })
    .filter((task) => task.summary)
}

function serializeRelationshipBeats(beats: PlannedRelationshipBeat[]): string {
  return beats.map((beat) => `${beat.source_character}->${beat.target_character}|${beat.summary}`).join('\n')
}

function parseRelationshipBeats(value: string): PlannedRelationshipBeat[] {
  return value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [pair = '', summary = ''] = line.split('|')
      const [sourceCharacter = '', targetCharacter = ''] = pair.split('->')
      return {
        source_character: sourceCharacter.trim(),
        target_character: targetCharacter.trim(),
        summary: summary.trim(),
      }
    })
    .filter((beat) => beat.source_character && beat.target_character && beat.summary)
}

function defaultPlannedLoop(chapterNumber: number, dueEndChapter: number, index: number): PlannedLoopItem {
  /**
   * 新增伏笔时直接给出完整结构，而不是再回到过去那种“只写一句文本”的松散模式：
   * - title / summary / due_end_chapter 直接占位，提醒维护者和作者这是必填约束；
   * - due_end_chapter 默认落在当前阶段结束章，鼓励先给出清晰回收边界，再决定是否跨幕延长。
   */
  return {
    loop_id: `manual-loop-${chapterNumber}-${Date.now()}-${index + 1}`,
    title: '',
    summary: '',
    status: 'open',
    priority: 1,
    due_start_chapter: chapterNumber,
    due_end_chapter: dueEndChapter,
    related_characters: [],
    resolution_requirements: [],
  }
}

function parseOptionalChapterNumber(value: string): number | null {
  const normalized = value.trim()
  if (!normalized) {
    return null
  }
  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : null
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

function serializeBlueprintValue<T>(value: T): string {
  return JSON.stringify(value ?? null)
}

function serializeRelationshipEdge(edge: RelationshipBlueprintEdge): string {
  return JSON.stringify({
    source_character_id: edge.source_character_id,
    target_character_id: edge.target_character_id,
    relation_type: edge.relation_type,
    polarity: edge.polarity,
    intensity: edge.intensity,
    visibility: edge.visibility,
    stability: edge.stability,
    summary: edge.summary,
    hidden_truth: edge.hidden_truth,
    non_breakable_without_reveal: edge.non_breakable_without_reveal,
  })
}

function buildSavedRelationshipEdgeMap(edges: RelationshipBlueprintEdge[]): Record<string, RelationshipBlueprintEdge> {
  return Object.fromEntries(edges.map((edge) => [edge.edge_id, { ...edge }]))
}

function serializeCharacterDraft(character: CharacterBlueprint): string {
  return JSON.stringify({
    name: character.name,
    role: character.role,
    public_persona: character.public_persona,
    core_motivation: character.core_motivation,
    fatal_flaw: character.fatal_flaw,
    non_negotiable_traits: character.non_negotiable_traits,
    relationship_constraints: character.relationship_constraints,
    arc_outline: character.arc_outline,
  })
}

function buildSavedCharacterMap(characters: CharacterBlueprint[]): Record<number, CharacterBlueprint> {
  return Object.fromEntries(characters.map((character, index) => [index, { ...character }]))
}

export function BookBlueprintWorkspace({ bookId, blueprint, activeBook = null }: BookBlueprintWorkspaceProps) {
  const queryClient = useQueryClient()
  /**
   * activeSection 是页内导航状态，不是后端状态真源。
   * 初次进入或切书时，会用 current_step 做默认落点；之后一旦用户手动切换，
   * 我们就尊重当前视图，不再每次后端刷新都强制把用户拉回某个步骤。
   */
  const [activeSection, setActiveSection] = useState<WorkspaceSectionKey>('overview')
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
  const [savedCharacterById, setSavedCharacterById] = useState<Record<number, CharacterBlueprint>>({})
  const [editingCharacterIds, setEditingCharacterIds] = useState<Record<number, boolean>>({})
  const [savedRelationshipEdgeById, setSavedRelationshipEdgeById] = useState<Record<string, RelationshipBlueprintEdge>>({})
  const [editingRelationshipIds, setEditingRelationshipIds] = useState<Record<string, boolean>>({})
  const [roadmapDraft, setRoadmapDraft] = useState<ChapterRoadmapItem[]>([])
  const [relationshipConflict, setRelationshipConflict] = useState<RelationshipConflictReport | null>(null)
  const [relationshipDesiredChange, setRelationshipDesiredChange] = useState('')
  const [relationshipReplan, setRelationshipReplan] = useState<RelationshipReplanResponse | null>(null)
  const [graphSelection, setGraphSelection] = useState<RelationshipGraphSelection>(null)
  const [roadmapError, setRoadmapError] = useState('')
  const [replanStart, setReplanStart] = useState(1)
  const [replanReason, setReplanReason] = useState('')
  const [replanGuidance, setReplanGuidance] = useState('')
  const [pendingVariantId, setPendingVariantId] = useState<number | null>(null)
  const [pendingRoadmapArcNumber, setPendingRoadmapArcNumber] = useState<number | null>(null)
  const [pendingRoadmapChapterNumber, setPendingRoadmapChapterNumber] = useState<number | null>(null)
  const [roadmapArcFeedbackByNumber, setRoadmapArcFeedbackByNumber] = useState<Record<number, string>>({})
  const [activeRoadmapArcNumber, setActiveRoadmapArcNumber] = useState<number | null>(null)
  /**
   * 章节细修被迁到右侧上下文栏后，需要单独维护“当前选中的章节”。
   * 主区只负责阶段卡与章节摘要，右栏再根据这个选中值决定显示哪张表单。
   */
  const [selectedRoadmapChapterNumber, setSelectedRoadmapChapterNumber] = useState<number | null>(null)
  const [highlightedRoadmapChapterNumber, setHighlightedRoadmapChapterNumber] = useState<number | null>(null)
  /**
   * 路线页被拆成“阶段视图 / 修复视图”后，需要单独记录当前主视图。
   * 这里仍然只影响前端展示，不改变后端蓝图状态机。
   */
  const [roadmapViewMode, setRoadmapViewMode] = useState<RoadmapViewMode>('stages')
  /**
   * 修复控制面中的选中态统一放在工作台壳层：
   * - 主区三列卡片可以互相联动；
   * - 右栏 inspector 可以根据同一个选中值展示详细差异或日志；
   * - 刷新后若对象已不存在，会在下方 effect 中自动清空。
   */
  const [creativeIssueSourceFilter, setCreativeIssueSourceFilter] =
    useState<CreativeIssueSourceFilter>('all')
  const [selectedCreativeIssueId, setSelectedCreativeIssueId] = useState<string | null>(null)
  const [selectedCreativeRepairProposalId, setSelectedCreativeRepairProposalId] = useState<string | null>(null)
  const [selectedCreativeRepairRunId, setSelectedCreativeRepairRunId] = useState<string | null>(null)
  const [regenerationProposalByVariantId, setRegenerationProposalByVariantId] = useState<
    Record<number, ConceptVariantRegenerationResult>
  >({})
  const characterCardRefs = useRef<Record<string, HTMLElement | null>>({})
  const relationshipCardRefs = useRef<Record<string, HTMLElement | null>>({})
  const pendingSectionRef = useRef<HTMLDivElement | null>(null)
  const conflictSectionRef = useRef<HTMLDivElement | null>(null)

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
    const nextCharacterDraft = blueprint?.character_draft ?? blueprint?.character_confirmed ?? []
    setCharacterDraft(nextCharacterDraft)
    setSavedCharacterById(buildSavedCharacterMap(nextCharacterDraft))
    setEditingCharacterIds(Object.fromEntries(nextCharacterDraft.map((_, index) => [index, false])))
    const nextRelationshipGraph = blueprint?.relationship_graph_draft ?? blueprint?.relationship_graph_confirmed ?? []
    setRelationshipGraphDraft(nextRelationshipGraph)
    setSavedRelationshipEdgeById(buildSavedRelationshipEdgeMap(nextRelationshipGraph))
    setEditingRelationshipIds(Object.fromEntries(nextRelationshipGraph.map((edge) => [edge.edge_id, false])))
    setRelationshipPending(blueprint?.relationship_pending ?? [])
    setRelationshipNodes(buildCharacterNodesFromBlueprint(blueprint?.character_draft ?? blueprint?.character_confirmed ?? []))
    setRoadmapDraft(blueprint?.roadmap_draft ?? blueprint?.roadmap_confirmed ?? [])
    const lockedRoadmap = blueprint?.roadmap_confirmed ?? []
    const lastChapter = lockedRoadmap.length > 0 ? lockedRoadmap[lockedRoadmap.length - 1]!.chapter_number : 1
    setReplanStart(Math.max(1, Math.min(replanStart, lastChapter)))
    setRegenerationProposalByVariantId((prev) => {
      const validIds = new Set((blueprint?.concept_variants ?? []).map((item) => item.id).filter(Boolean) as number[])
      return Object.fromEntries(Object.entries(prev).filter(([key]) => validIds.has(Number(key))))
    })
  }, [blueprint])

  useEffect(() => {
    const arcs = blueprint?.story_arcs_confirmed?.length
      ? blueprint.story_arcs_confirmed
      : blueprint?.story_arcs_draft ?? []
    if (arcs.length === 0) {
      setActiveRoadmapArcNumber(null)
      return
    }
    setActiveRoadmapArcNumber((current) =>
      current && arcs.some((item) => item.arc_number === current) ? current : arcs[0]!.arc_number,
    )
  }, [blueprint?.story_arcs_confirmed, blueprint?.story_arcs_draft])

  useEffect(() => {
    /**
     * 只在默认 overview 状态下，才用后端 current_step 帮用户落到更合适的分区。
     * 如果用户已经主动切换到某个步骤，就不再打断他的阅读/编辑上下文。
     */
    setActiveSection((current) =>
      current === 'overview' ? mapBlueprintStepToWorkspaceSection(blueprint?.current_step) : current,
    )
  }, [blueprint?.current_step, bookId])

  useEffect(() => {
    if (!highlightedRoadmapChapterNumber) {
      return
    }
    const timer = window.setTimeout(() => {
      setHighlightedRoadmapChapterNumber(null)
    }, 1800)
    return () => window.clearTimeout(timer)
  }, [highlightedRoadmapChapterNumber])

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
    onSuccess: async (payload, variables) => {
      setRelationshipGraphDraft(payload.edges)
      setSavedRelationshipEdgeById(buildSavedRelationshipEdgeMap(payload.edges))
      setEditingRelationshipIds((prev) => ({
        ...prev,
        ...Object.fromEntries(payload.edges.map((edge) => [edge.edge_id, false])),
        [variables.edge_id]: false,
      }))
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
        if (raw?.edge_id) {
          setGraphSelection({ kind: 'edge', id: raw.edge_id as string })
        }
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
      setSavedRelationshipEdgeById(buildSavedRelationshipEdgeMap(payload.edges))
      setEditingRelationshipIds(Object.fromEntries(payload.edges.map((edge) => [edge.edge_id, false])))
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
      setSavedRelationshipEdgeById(buildSavedRelationshipEdgeMap(payload.edges))
      setEditingRelationshipIds(Object.fromEntries(payload.edges.map((edge) => [edge.edge_id, false])))
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
      setSavedRelationshipEdgeById(buildSavedRelationshipEdgeMap(payload.edges))
      setEditingRelationshipIds(Object.fromEntries(payload.edges.map((edge) => [edge.edge_id, false])))
      setRelationshipPending(payload.pending)
      setRelationshipConflict(null)
      setRelationshipReplan(null)
      setRelationshipDesiredChange('')
      toast.success('关系重规划已确认，将作用于未来章节')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const generateStoryArcsMutation = useMutation({
    mutationFn: () => generateStoryArcs(bookId, { feedback: roadmapFeedback }),
    onSuccess: async (payload) => {
      setRoadmapDraft(payload.roadmap_draft)
      setRoadmapError('')
      toast.success('阶段骨架已生成，请按阶段顺序逐章生成')
      await refreshBlueprint()
    },
    onError: (error: Error) => {
      setRoadmapError(error.message)
      toast.error(error.message)
    },
  })

  const expandStoryArcMutation = useMutation({
    mutationFn: ({ arcNumber, feedback }: { arcNumber: number; feedback: string }) =>
      expandStoryArc(bookId, arcNumber, { feedback }),
    onMutate: ({ arcNumber }) => {
      setPendingRoadmapArcNumber(arcNumber)
    },
    onSuccess: async (payload, variables) => {
      setRoadmapDraft(payload.roadmap_draft)
      setRoadmapError('')
      setRoadmapArcFeedbackByNumber((prev) => ({
        ...prev,
        [variables.arcNumber]: '',
      }))
      setActiveRoadmapArcNumber(variables.arcNumber)
      const arc = payload.story_arcs_confirmed.length
        ? payload.story_arcs_confirmed.find((item) => item.arc_number === variables.arcNumber)
        : payload.story_arcs_draft.find((item) => item.arc_number === variables.arcNumber)
      toast.success(
        arc?.next_chapter_number === null
          ? `第 ${variables.arcNumber} 幕已完成全部章节生成`
          : `第 ${variables.arcNumber} 幕已生成下一章`,
      )
      await refreshBlueprint()
    },
    onError: (error: Error) => {
      setRoadmapError(error.message)
      toast.error(error.message)
    },
    onSettled: () => {
      setPendingRoadmapArcNumber(null)
    },
  })

  const regenerateArcChapterMutation = useMutation({
    mutationFn: ({ arcNumber, chapterNumber, feedback }: { arcNumber: number; chapterNumber: number; feedback: string }) =>
      regenerateArcChapter(bookId, arcNumber, chapterNumber, { feedback }),
    onMutate: ({ chapterNumber }) => {
      setPendingRoadmapChapterNumber(chapterNumber)
    },
    onSuccess: async (payload, variables) => {
      setRoadmapDraft(payload.roadmap_draft)
      setRoadmapError('')
      setActiveRoadmapArcNumber(variables.arcNumber)
      toast.success(`第 ${variables.chapterNumber} 章已重生成`)
      await refreshBlueprint()
    },
    onError: (error: Error) => {
      setRoadmapError(error.message)
      toast.error(error.message)
    },
    onSettled: () => {
      setPendingRoadmapChapterNumber(null)
    },
  })

  const regenerateStoryArcMutation = useMutation({
    mutationFn: ({ arcNumber, feedback }: { arcNumber: number; feedback: string }) =>
      regenerateStoryArc(bookId, arcNumber, { feedback }),
    onMutate: ({ arcNumber }) => {
      setPendingRoadmapArcNumber(arcNumber)
    },
    onSuccess: async (payload, variables) => {
      setRoadmapDraft(payload.roadmap_draft)
      setRoadmapError('')
      setRoadmapArcFeedbackByNumber((prev) => ({
        ...prev,
        [variables.arcNumber]: '',
      }))
      setActiveRoadmapArcNumber(variables.arcNumber)
      toast.success(`第 ${variables.arcNumber} 幕阶段骨架已重生成`)
      await refreshBlueprint()
    },
    onError: (error: Error) => {
      setRoadmapError(error.message)
      toast.error(error.message)
    },
    onSettled: () => {
      setPendingRoadmapArcNumber(null)
    },
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

  const planCreativeRepairsMutation = useMutation({
    mutationFn: (issueIds: string[] = []) => planCreativeRepairs(bookId, issueIds),
    onSuccess: async () => {
      toast.success('已生成修复提案，请先预览差异再决定是否执行')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const applyCreativeRepairProposalMutation = useMutation({
    mutationFn: (proposalId: string) => applyCreativeRepairProposal(bookId, proposalId),
    onSuccess: async () => {
      toast.success('修复提案已执行，并已自动复验当前章节路线')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const rollbackCreativeRepairRunMutation = useMutation({
    mutationFn: (runId: string) => rollbackCreativeRepairRun(bookId, runId),
    onSuccess: async () => {
      toast.success('已回滚到修复前快照')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const reverifyCreativeIssuesMutation = useMutation({
    mutationFn: () => reverifyCreativeIssues(bookId),
    onSuccess: async () => {
      toast.success('已重新复验当前章节路线')
      await refreshBlueprint()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const selectedVariantId = blueprint?.selected_variant_id
  const canGenerateCharacters = Boolean(blueprint?.world_confirmed)
  const canGenerateStoryArcs = Boolean(blueprint?.world_confirmed && blueprint?.character_confirmed.length)
  const revisions = blueprint?.revisions ?? []
  const roadmapToShow = blueprint?.roadmap_confirmed.length ? blueprint.roadmap_confirmed : roadmapDraft
  const expandedArcNumbers = blueprint?.expanded_arc_numbers ?? []
  const baseStoryArcsToShow = blueprint?.story_arcs_confirmed.length
    ? blueprint.story_arcs_confirmed
    : blueprint?.story_arcs_draft ?? []
  const roadmapDraftDirty =
    serializeBlueprintValue(roadmapDraft) !==
    serializeBlueprintValue(blueprint?.roadmap_confirmed.length ? blueprint?.roadmap_confirmed : blueprint?.roadmap_draft ?? [])
  const localStoryArcsToShow = useMemo(
    () => deriveStoryArcsFromRoadmapDraft(roadmapToShow, baseStoryArcsToShow, expandedArcNumbers),
    [baseStoryArcsToShow, expandedArcNumbers, roadmapToShow],
  )
  const storyArcsToShow = localStoryArcsToShow.length > 0 ? localStoryArcsToShow : baseStoryArcsToShow
  const localRoadmapIssues = useMemo(
    () => buildLocalRoadmapIssues(storyArcsToShow, roadmapToShow, expandedArcNumbers),
    [expandedArcNumbers, roadmapToShow, storyArcsToShow],
  )
  const localContinuityState = useMemo(
    () => buildLocalContinuityState(roadmapToShow),
    [roadmapToShow],
  )
  const continuityState: BlueprintContinuityState =
    roadmapDraftDirty || !blueprint?.continuity_state ? localContinuityState : blueprint.continuity_state
  const roadmapIssues = roadmapDraftDirty ? localRoadmapIssues : blueprint?.roadmap_validation_issues ?? []
  /**
   * 闭环控制面默认只消费后端已持久化的工作态：
   * - issue / proposal / run 都需要和数据库快照保持一致，才能支持 apply / rollback；
   * - 如果用户本地正在编辑但尚未写回，我们先提示“请先保存或确认当前修改”，
   *   避免拿一份未持久化的前端草稿去执行后端提案，造成状态分裂。
   */
  const creativeIssues: CreativeIssue[] = roadmapDraftDirty ? [] : blueprint?.creative_issues ?? []
  const creativeRepairProposals: CreativeRepairProposal[] = roadmapDraftDirty
    ? []
    : blueprint?.creative_repair_proposals ?? []
  const creativeRepairRuns: CreativeRepairRun[] = roadmapDraftDirty ? [] : blueprint?.creative_repair_runs ?? []
  const roadmapLockState = useMemo(
    () => summarizeRoadmapLockState(storyArcsToShow, expandedArcNumbers, roadmapIssues, roadmapToShow),
    [expandedArcNumbers, roadmapIssues, roadmapToShow, storyArcsToShow],
  )
  const intentIsSaved = serializeBlueprintValue(intentDraft) === serializeBlueprintValue(blueprint?.intent ?? defaultIntent())
  const worldIsConfirmed =
    Boolean(blueprint?.world_confirmed) &&
    worldDraft !== null &&
    serializeBlueprintValue(worldDraft) === serializeBlueprintValue(blueprint?.world_confirmed ?? null)
  const characterIsConfirmed =
    (blueprint?.character_confirmed?.length ?? 0) > 0 &&
    serializeBlueprintValue(characterDraft) === serializeBlueprintValue(blueprint?.character_confirmed ?? [])
  const relationshipGraphIsConfirmed =
    (blueprint?.relationship_graph_confirmed?.length ?? 0) > 0 &&
    serializeBlueprintValue(relationshipGraphDraft) === serializeBlueprintValue(blueprint?.relationship_graph_confirmed ?? [])
  const roadmapIsLocked =
    (blueprint?.roadmap_confirmed?.length ?? 0) > 0 &&
    storyArcsToShow.length > 0 &&
    serializeBlueprintValue(roadmapDraft) === serializeBlueprintValue(blueprint?.roadmap_confirmed ?? [])
  const totalFatalRoadmapIssues = roadmapIssues.filter((item) => item.severity === 'fatal').length
  const totalWarningRoadmapIssues = roadmapIssues.filter((item) => item.severity === 'warning').length
  const canLockRoadmap =
    storyArcsToShow.length > 0 &&
    !confirmRoadmapMutation.isPending &&
    !roadmapIsLocked &&
    roadmapLockState.canLock &&
    !generateStoryArcsMutation.isPending &&
    !expandStoryArcMutation.isPending &&
    !regenerateArcChapterMutation.isPending &&
    !regenerateStoryArcMutation.isPending
  const activeRevisionLabel = useMemo(() => {
    const active = revisions.find((item) => item.is_active)
    return active ? `v${active.revision_number}` : '未锁定'
  }, [revisions])
  /**
   * 左侧步骤导航的状态全部在这里集中推导，避免每个子区块自己判断“完成/警告/阻塞”。
   * 这样后续如果要新增步骤或修改门禁语义，只需要改这里的一处映射。
   */
  const workspaceSidebarItems = useMemo<WorkspaceSidebarItem[]>(
    () => [
      {
        key: 'overview',
        label: '总览',
        description: '查看整书蓝图状态、问题和下一步建议。',
        statusLabel: blueprint?.status === 'locked' ? '已锁定' : '工作中',
        tone: roadmapIsLocked ? 'ready' : totalFatalRoadmapIssues > 0 ? 'danger' : 'pending',
      },
      {
        key: 'intent',
        label: '创作意图',
        description: '定义题材、主题、主角提示与禁用元素。',
        statusLabel: intentIsSaved ? '已保存' : '待保存',
        tone: intentIsSaved ? 'ready' : 'pending',
        dirty: !intentIsSaved,
      },
      {
        key: 'concept',
        label: '候选方向',
        description: '选定整书方向，再进入世界观与人物细化。',
        statusLabel: selectedVariantId ? '已选定' : '待选择',
        tone: selectedVariantId ? 'ready' : 'pending',
      },
      {
        key: 'world',
        label: '世界观',
        description: '固定世界硬规则、力量体系与势力结构。',
        statusLabel: worldIsConfirmed ? '已确认' : '待确认',
        tone: worldIsConfirmed ? 'ready' : 'pending',
      },
      {
        key: 'characters',
        label: '人物',
        description: '聚焦角色动机、缺口与角色弧线。',
        statusLabel: characterDraft.length > 0 ? `${characterDraft.length} 人` : '未生成',
        tone: characterIsConfirmed ? 'ready' : characterDraft.length > 0 ? 'warning' : 'pending',
        dirty: !characterIsConfirmed && characterDraft.length > 0,
      },
      {
        key: 'relationships',
        label: '关系图谱',
        description: '图谱画布优先，处理待确认关系与冲突重规划。',
        statusLabel:
          relationshipConflict !== null
            ? '有冲突'
            : relationshipPending.length > 0
              ? `${relationshipPending.length} 待确认`
              : relationshipGraphIsConfirmed
                ? '已确认'
                : '待确认',
        tone: relationshipConflict ? 'danger' : relationshipPending.length > 0 ? 'warning' : relationshipGraphIsConfirmed ? 'ready' : 'pending',
      },
      {
        key: 'roadmap',
        label: '章节路线',
        description: '按阶段顺序逐章生成，并在右栏细修当前章节。',
        statusLabel: storyArcsToShow.length > 0 ? `${expandedArcNumbers.length}/${storyArcsToShow.length} 幕完成` : '未生成',
        tone: totalFatalRoadmapIssues > 0 ? 'danger' : totalWarningRoadmapIssues > 0 ? 'warning' : roadmapIsLocked ? 'ready' : 'pending',
      },
      {
        key: 'continuity',
        label: '连续性',
        description: '检查任务、伏笔、关系和世界更新是否承接顺畅。',
        statusLabel:
          continuityState.open_tasks.length > 0 || continuityState.active_loops.length > 0
            ? `${continuityState.open_tasks.length + continuityState.active_loops.length} 项待跟进`
            : '状态清晰',
        tone: totalFatalRoadmapIssues > 0 ? 'danger' : continuityState.open_tasks.length > 0 ? 'warning' : 'ready',
      },
      {
        key: 'settings',
        label: '作品设置',
        description: '查看当前作品的语言、文风与命名策略。',
        statusLabel: activeBook ? '可查看' : '无作品',
        tone: activeBook ? 'ready' : 'pending',
      },
    ],
    [
      activeBook,
      blueprint?.status,
      characterDraft.length,
      characterIsConfirmed,
      continuityState.active_loops.length,
      continuityState.open_tasks.length,
      expandedArcNumbers.length,
      intentIsSaved,
      relationshipConflict,
      relationshipGraphIsConfirmed,
      relationshipPending.length,
      roadmapIsLocked,
      selectedVariantId,
      storyArcsToShow.length,
      totalFatalRoadmapIssues,
      totalWarningRoadmapIssues,
      worldIsConfirmed,
    ],
  )
  const relationshipGraphView = useMemo(
    () =>
      buildRelationshipGraphViewModel({
        nodes: relationshipNodes,
        edges: relationshipGraphDraft,
        pending: relationshipPending,
        selection: graphSelection,
        conflict: relationshipConflict,
        replanEdgeId: relationshipReplan?.proposal.future_edge.edge_id ?? null,
      }),
    [graphSelection, relationshipConflict, relationshipGraphDraft, relationshipNodes, relationshipPending, relationshipReplan],
  )
  const selectedCharacterIndex = useMemo(() => {
    if (graphSelection?.kind !== 'node') {
      return -1
    }
    return characterDraft.findIndex(
      (character, index) =>
        normalizeCharacterNodeId(character.name || `角色${index + 1}`) === graphSelection.id,
    )
  }, [characterDraft, graphSelection])
  const selectedEdgeIndex = useMemo(() => {
    if (graphSelection?.kind !== 'edge') {
      return -1
    }
    return relationshipGraphDraft.findIndex((edge) => edge.edge_id === graphSelection.id)
  }, [graphSelection, relationshipGraphDraft])
  const selectedCharacter = selectedCharacterIndex >= 0 ? characterDraft[selectedCharacterIndex]! : null
  const selectedEdge = selectedEdgeIndex >= 0 ? relationshipGraphDraft[selectedEdgeIndex]! : null
  const characterDirtyById = useMemo(
    () =>
      Object.fromEntries(
        characterDraft.map((character, index) => [
          index,
          savedCharacterById[index]
            ? serializeCharacterDraft(savedCharacterById[index]!) !== serializeCharacterDraft(character)
            : true,
        ]),
      ),
    [characterDraft, savedCharacterById],
  )
  const relationshipDirtyById = useMemo(
    () =>
      Object.fromEntries(
        relationshipGraphDraft.map((edge) => [
          edge.edge_id,
          savedRelationshipEdgeById[edge.edge_id]
            ? serializeRelationshipEdge(savedRelationshipEdgeById[edge.edge_id]!) !== serializeRelationshipEdge(edge)
            : true,
        ]),
      ),
    [relationshipGraphDraft, savedRelationshipEdgeById],
  )
  const roadmapIssuesByArc = useMemo(
    () =>
      storyArcsToShow.map((arc) => ({
        arcNumber: arc.arc_number,
        fatalCount: roadmapIssues.filter(
          (issue) =>
            issue.severity === 'fatal' &&
            ((issue.arc_number ?? null) === arc.arc_number ||
              (issue.chapter_number !== null &&
                issue.chapter_number >= arc.start_chapter &&
                issue.chapter_number <= arc.end_chapter)),
        ).length,
        warningCount: roadmapIssues.filter(
          (issue) =>
            issue.severity === 'warning' &&
            ((issue.arc_number ?? null) === arc.arc_number ||
              (issue.chapter_number !== null &&
                issue.chapter_number >= arc.start_chapter &&
                issue.chapter_number <= arc.end_chapter)),
        ).length,
      })),
    [roadmapIssues, storyArcsToShow],
  )
  const visibleRoadmapChapters = useMemo(() => {
    if (!activeRoadmapArcNumber) {
      return []
    }
    const activeArc = storyArcsToShow.find((item) => item.arc_number === activeRoadmapArcNumber)
    if (!activeArc) {
      return []
    }
    return roadmapToShow.filter(
      (item) => item.chapter_number >= activeArc.start_chapter && item.chapter_number <= activeArc.end_chapter,
    )
  }, [activeRoadmapArcNumber, roadmapToShow, storyArcsToShow])
  const activeRoadmapArc = useMemo(
    () => storyArcsToShow.find((item) => item.arc_number === activeRoadmapArcNumber) ?? null,
    [activeRoadmapArcNumber, storyArcsToShow],
  )
  const selectedRoadmapChapter = useMemo(
    () => visibleRoadmapChapters.find((item) => item.chapter_number === selectedRoadmapChapterNumber) ?? null,
    [selectedRoadmapChapterNumber, visibleRoadmapChapters],
  )
  const selectedRoadmapChapterIssues = useMemo(
    () =>
      selectedRoadmapChapter
        ? roadmapIssues.filter((issue) => issue.chapter_number === selectedRoadmapChapter.chapter_number)
        : [],
    [roadmapIssues, selectedRoadmapChapter],
  )
  const pendingCreativeRepairCount = useMemo(
    () => creativeRepairProposals.filter((item) => item.status === 'awaiting_approval').length,
    [creativeRepairProposals],
  )
  /**
   * 路线主区的核心规则是“只突出当前最早可行动阶段”：
   * - 优先找后端明确标记 can_generate_next_chapter 的阶段；
   * - 如果当前没有明确的可行动阶段，则回退到用户已经展开查看的阶段；
   * - 这样主区始终有一个清晰焦点，不会再把所有阶段平铺成同一层级。
   */
  const currentActionableArc = useMemo(
    () =>
      storyArcsToShow.find((item) => item.can_generate_next_chapter) ??
      activeRoadmapArc ??
      storyArcsToShow[0] ??
      null,
    [activeRoadmapArc, storyArcsToShow],
  )
  const blockedRoadmapArcs = useMemo(
    () =>
      storyArcsToShow.filter(
        (item) =>
          item.arc_number !== currentActionableArc?.arc_number &&
          item.status !== 'completed' &&
          item.status !== 'confirmed',
      ),
    [currentActionableArc?.arc_number, storyArcsToShow],
  )
  const completedRoadmapArcs = useMemo(
    () => storyArcsToShow.filter((item) => item.status === 'completed' || item.status === 'confirmed'),
    [storyArcsToShow],
  )
  const currentArcChapters = useMemo(() => {
    if (!currentActionableArc) {
      return []
    }
    return roadmapToShow.filter(
      (item) =>
        item.chapter_number >= currentActionableArc.start_chapter &&
        item.chapter_number <= currentActionableArc.end_chapter,
    )
  }, [currentActionableArc, roadmapToShow])
  const archivedArcChapters = useMemo(
    () =>
      storyArcsToShow
        .filter((arc) => arc.arc_number !== currentActionableArc?.arc_number)
        .map((arc) => ({
          arc,
          chapters: roadmapToShow.filter(
            (item) => item.chapter_number >= arc.start_chapter && item.chapter_number <= arc.end_chapter,
          ),
        }))
        .filter((item) => item.chapters.length > 0),
    [currentActionableArc?.arc_number, roadmapToShow, storyArcsToShow],
  )
  const selectedCreativeIssue = useMemo(
    () => creativeIssues.find((item) => item.issue_id === selectedCreativeIssueId) ?? null,
    [creativeIssues, selectedCreativeIssueId],
  )
  const selectedCreativeRepairProposal = useMemo(
    () => creativeRepairProposals.find((item) => item.proposal_id === selectedCreativeRepairProposalId) ?? null,
    [creativeRepairProposals, selectedCreativeRepairProposalId],
  )
  const selectedCreativeRepairRun = useMemo(
    () => creativeRepairRuns.find((item) => item.run_id === selectedCreativeRepairRunId) ?? null,
    [creativeRepairRuns, selectedCreativeRepairRunId],
  )
  /**
   * 来源筛选本质上是在切换“当前控制面工作层”。
   * 非 roadmap 层还没有 proposal / run 执行链，因此切过去时要主动清掉这些 roadmap 选中态，
   * 否则右栏会停在旧提案详情，和当前筛选来源产生语义分裂。
   */
  const handleCreativeIssueSourceFilterChange = (filter: CreativeIssueSourceFilter) => {
    setCreativeIssueSourceFilter(filter)
    if (filter === 'all' || filter === 'roadmap') {
      return
    }
    setSelectedCreativeRepairProposalId(null)
    setSelectedCreativeRepairRunId(null)
    setSelectedRoadmapChapterNumber(null)
    setSelectedCreativeIssueId((current) => {
      if (!current) {
        return null
      }
      const matchedIssue = creativeIssues.find((item) => item.issue_id === current) ?? null
      return matchedIssue?.source_layer === filter ? current : null
    })
  }
  /**
   * 右栏 inspector 的显示规则统一折叠到一个视图层状态对象里：
   * - 同一时刻只允许出现一个主对象；
   * - 章节、问题、提案、执行结果的优先级固定，避免 JSX 条件分支互相覆盖；
   * - 后续 scene / review / canon 接入时，也能沿用同一套“选中对象 -> inspector 模式”。
   */
  const roadmapInspectorState = useMemo<RoadmapInspectorState>(() => {
    if (selectedCreativeRepairProposal) {
      return {
        mode: 'proposal',
        issue: null,
        proposal: selectedCreativeRepairProposal,
        run: null,
        chapter: null,
      }
    }
    if (selectedCreativeRepairRun) {
      return {
        mode: 'run',
        issue: null,
        proposal: null,
        run: selectedCreativeRepairRun,
        chapter: null,
      }
    }
    if (selectedCreativeIssue) {
      return {
        mode: 'issue',
        issue: selectedCreativeIssue,
        proposal: null,
        run: null,
        chapter: null,
      }
    }
    if (selectedRoadmapChapter) {
      return {
        mode: 'chapter',
        issue: null,
        proposal: null,
        run: null,
        chapter: selectedRoadmapChapter,
      }
    }
    return {
      mode: 'summary',
      issue: null,
      proposal: null,
      run: null,
      chapter: null,
    }
  }, [
    selectedCreativeIssue,
    selectedCreativeRepairProposal,
    selectedCreativeRepairRun,
    selectedRoadmapChapter,
  ])
  const chapterActionArc = activeRoadmapArc ?? currentActionableArc
  const lastGeneratedVisibleRoadmapChapterNumber = chapterActionArc?.generated_chapter_count
    ? chapterActionArc.start_chapter + chapterActionArc.generated_chapter_count - 1
    : null
  const canRegenerateFocusedRoadmapChapter =
    selectedRoadmapChapter !== null &&
    lastGeneratedVisibleRoadmapChapterNumber !== null &&
    selectedRoadmapChapter.chapter_number === lastGeneratedVisibleRoadmapChapterNumber

  useEffect(() => {
    if (visibleRoadmapChapters.length === 0) {
      setSelectedRoadmapChapterNumber(null)
      return
    }
    setSelectedRoadmapChapterNumber((current) =>
      current && visibleRoadmapChapters.some((item) => item.chapter_number === current)
        ? current
        : visibleRoadmapChapters[0]!.chapter_number,
    )
  }, [visibleRoadmapChapters])

  useEffect(() => {
    if (!graphSelection) {
      return
    }
    if (graphSelection.kind === 'node') {
      const exists = relationshipGraphView.nodes.some((item) => item.id === graphSelection.id)
      if (!exists) {
        setGraphSelection(null)
      }
      return
    }
    const exists = relationshipGraphView.edges.some((item) => item.id === graphSelection.id)
    if (!exists) {
      setGraphSelection(null)
    }
  }, [graphSelection, relationshipGraphView])

  useEffect(() => {
    /**
     * 路线页默认策略：
     * - 一旦出现 fatal 或待确认修复提案，优先切到“修复视图”，
     *   让作者先处理真正阻塞后续生成的问题；
     * - 没有高优先级修复压力时，再回到“阶段视图”。
     */
    if (activeSection !== 'roadmap') {
      return
    }
    if (totalFatalRoadmapIssues > 0 || pendingCreativeRepairCount > 0) {
      setRoadmapViewMode('repair')
      return
    }
    setRoadmapViewMode((current) => current)
  }, [activeSection, pendingCreativeRepairCount, totalFatalRoadmapIssues])

  useEffect(() => {
    if (selectedCreativeIssueId && !creativeIssues.some((item) => item.issue_id === selectedCreativeIssueId)) {
      setSelectedCreativeIssueId(null)
    }
  }, [creativeIssues, selectedCreativeIssueId])

  useEffect(() => {
    if (
      selectedCreativeRepairProposalId &&
      !creativeRepairProposals.some((item) => item.proposal_id === selectedCreativeRepairProposalId)
    ) {
      setSelectedCreativeRepairProposalId(null)
    }
  }, [creativeRepairProposals, selectedCreativeRepairProposalId])

  useEffect(() => {
    if (selectedCreativeRepairRunId && !creativeRepairRuns.some((item) => item.run_id === selectedCreativeRepairRunId)) {
      setSelectedCreativeRepairRunId(null)
    }
  }, [creativeRepairRuns, selectedCreativeRepairRunId])

  const jumpToCharacterForm = (nodeId: string) => {
    setGraphSelection({ kind: 'node', id: nodeId })
    characterCardRefs.current[nodeId]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  const jumpToRelationshipForm = (edgeId: string) => {
    setGraphSelection({ kind: 'edge', id: edgeId })
    relationshipCardRefs.current[edgeId]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  const jumpToPendingQueue = () => {
    pendingSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  const jumpToConflictArea = () => {
    conflictSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  const focusRoadmapChapter = (chapterNumber: number, arcNumber?: number | null) => {
    if (arcNumber) {
      setActiveRoadmapArcNumber(arcNumber)
    }
    setSelectedRoadmapChapterNumber(chapterNumber)
    setHighlightedRoadmapChapterNumber(chapterNumber)
  }

  const toggleRoadmapArc = (arcNumber: number) => {
    setActiveRoadmapArcNumber((current) => (current === arcNumber ? null : arcNumber))
  }

  const jumpToRoadmapArc = (arcNumber: number) => {
    setActiveRoadmapArcNumber(arcNumber)
    setSelectedRoadmapChapterNumber(null)
  }

  const handleStoryArcExpand = (arcNumber: number) => {
    const feedback = roadmapArcFeedbackByNumber[arcNumber] ?? ''
    expandStoryArcMutation.mutate({ arcNumber, feedback })
  }

  const handleRoadmapArcRegenerate = (arcNumber: number) => {
    const feedback = roadmapArcFeedbackByNumber[arcNumber] ?? ''
    regenerateStoryArcMutation.mutate({ arcNumber, feedback })
  }

  const handleRoadmapChapterRegenerate = (arcNumber: number, chapterNumber: number) => {
    const feedback = roadmapArcFeedbackByNumber[arcNumber] ?? ''
    regenerateArcChapterMutation.mutate({ arcNumber, chapterNumber, feedback })
  }

  /**
   * 章节细修统一通过章节号回写到 roadmap 草稿。
   * 右侧上下文栏与主区章节列表都会复用这套更新入口，避免两边各自维护一套 patch 逻辑。
   */
  const updateRoadmapChapterByNumber = (
    chapterNumber: number,
    updater: (item: ChapterRoadmapItem) => ChapterRoadmapItem,
  ) => {
    setRoadmapDraft((prev) =>
      prev.map((item) => (item.chapter_number === chapterNumber ? updater(item) : item)),
    )
  }

  /**
   * 伏笔改成结构化卡片后，右栏需要支持局部更新、追加和删除。
   * 这里把所有操作都收敛到同一层，保证章节草稿仍然只通过 chapter_number 回写。
   */
  const updateRoadmapLoopByIndex = (
    chapterNumber: number,
    loopIndex: number,
    updater: (loop: PlannedLoopItem) => PlannedLoopItem,
  ) => {
    updateRoadmapChapterByNumber(chapterNumber, (item) => ({
      ...item,
      planned_loops: item.planned_loops.map((loop, index) => (index === loopIndex ? updater(loop) : loop)),
    }))
  }

  const addRoadmapLoop = (chapterNumber: number, dueEndChapter: number) => {
    updateRoadmapChapterByNumber(chapterNumber, (item) => ({
      ...item,
      planned_loops: [...item.planned_loops, defaultPlannedLoop(chapterNumber, dueEndChapter, item.planned_loops.length)],
    }))
  }

  const removeRoadmapLoop = (chapterNumber: number, loopIndex: number) => {
    updateRoadmapChapterByNumber(chapterNumber, (item) => ({
      ...item,
      planned_loops: item.planned_loops.filter((_, index) => index !== loopIndex),
    }))
  }

  const updateSelectedCharacter = (patch: Partial<CharacterBlueprint>) => {
    if (selectedCharacterIndex < 0) {
      return
    }
    setCharacterDraft((prev) =>
      prev.map((item, index) => (index === selectedCharacterIndex ? { ...item, ...patch } : item)),
    )
    if (typeof patch.name === 'string') {
      setGraphSelection({
        kind: 'node',
        id: normalizeCharacterNodeId(patch.name || `角色${selectedCharacterIndex + 1}`),
      })
    }
  }

  const commitSelectedCharacterDraft = () => {
    if (!selectedCharacter || selectedCharacterIndex < 0) {
      return
    }
    setSavedCharacterById((prev) => ({ ...prev, [selectedCharacterIndex]: { ...selectedCharacter } }))
    setEditingCharacterIds((prev) => ({ ...prev, [selectedCharacterIndex]: false }))
    toast.success('人物修改已写入当前草稿，请在完成后确认人物蓝图')
  }

  const startEditingCharacter = (characterIndex: number) => {
    setEditingCharacterIds((prev) => ({ ...prev, [characterIndex]: true }))
  }

  const cancelEditingCharacter = (characterIndex: number) => {
    const savedCharacter = savedCharacterById[characterIndex]
    if (savedCharacter) {
      setCharacterDraft((prev) =>
        prev.map((item, index) => (index === characterIndex ? { ...savedCharacter } : item)),
      )
      setEditingCharacterIds((prev) => ({ ...prev, [characterIndex]: false }))
      return
    }
    setCharacterDraft((prev) => prev.filter((_, index) => index !== characterIndex))
    setEditingCharacterIds((prev) => {
      const next = { ...prev }
      delete next[characterIndex]
      return next
    })
    if (graphSelection?.kind === 'node' && selectedCharacter) {
      const selectedNodeId = normalizeCharacterNodeId(selectedCharacter.name || `角色${characterIndex + 1}`)
      if (graphSelection.id === selectedNodeId) {
        setGraphSelection(null)
      }
    }
  }

  const updateSelectedEdge = (patch: Partial<RelationshipBlueprintEdge>) => {
    if (selectedEdgeIndex < 0) {
      return
    }
    setRelationshipGraphDraft((prev) =>
      prev.map((item, index) => (index === selectedEdgeIndex ? { ...item, ...patch } : item)),
    )
  }

  const saveSelectedEdge = () => {
    if (!selectedEdge) {
      return
    }
    upsertRelationshipEdgeMutation.mutate(selectedEdge)
  }

  const deleteSelectedEdge = () => {
    if (!selectedEdge) {
      return
    }
    setRelationshipGraphDraft((prev) => prev.filter((item) => item.edge_id !== selectedEdge.edge_id))
    setEditingRelationshipIds((prev) => {
      const next = { ...prev }
      delete next[selectedEdge.edge_id]
      return next
    })
    setGraphSelection(null)
  }

  const startEditingEdge = (edgeId: string) => {
    setEditingRelationshipIds((prev) => ({ ...prev, [edgeId]: true }))
  }

  const cancelEditingEdge = (edgeId: string) => {
    const savedEdge = savedRelationshipEdgeById[edgeId]
    if (savedEdge) {
      setRelationshipGraphDraft((prev) => prev.map((item) => (item.edge_id === edgeId ? { ...savedEdge } : item)))
    } else {
      setRelationshipGraphDraft((prev) => prev.filter((item) => item.edge_id !== edgeId))
      if (graphSelection?.kind === 'edge' && graphSelection.id === edgeId) {
        setGraphSelection(null)
      }
    }
    setRelationshipConflict((prev) => (prev?.edge_id === edgeId ? null : prev))
    setEditingRelationshipIds((prev) => {
      if (savedEdge) {
        return { ...prev, [edgeId]: false }
      }
      const next = { ...prev }
      delete next[edgeId]
      return next
    })
  }

  const summaryRailTitle =
    activeSection === 'overview'
      ? '整书蓝图总览'
      : activeSection === 'intent'
        ? '创作意图摘要'
        : activeSection === 'concept'
          ? '方向决策摘要'
          : activeSection === 'world'
            ? '世界观摘要'
            : activeSection === 'characters'
              ? '人物摘要'
              : activeSection === 'relationships'
                ? '关系图谱摘要'
                : activeSection === 'roadmap'
                  ? roadmapInspectorState.mode === 'proposal'
                    ? '修复提案详情'
                    : roadmapInspectorState.mode === 'run'
                      ? '执行结果详情'
                      : roadmapInspectorState.mode === 'issue'
                        ? '问题详情'
                        : roadmapInspectorState.mode === 'chapter' && roadmapInspectorState.chapter
                          ? `第 ${roadmapInspectorState.chapter.chapter_number} 章细修`
                          : creativeIssueSourceFilter === 'review'
                            ? '审阅接入摘要'
                            : creativeIssueSourceFilter === 'scene'
                              ? '场景接入预留'
                              : creativeIssueSourceFilter === 'canon'
                                ? '设定同步预留'
                                : currentActionableArc
                            ? `第 ${currentActionableArc.arc_number} 幕检查`
                            : '章节路线摘要'
                  : activeSection === 'continuity'
                    ? '连续性摘要'
                    : '作品设置摘要'
  const summaryRailDescription =
    activeSection === 'roadmap' && roadmapInspectorState.mode === 'proposal'
      ? '当前查看的是修复提案细节。右栏会展示差异摘要、后置条件与执行风险，方便作者在确认前先做一轮人工审阅。'
      : activeSection === 'roadmap' && roadmapInspectorState.mode === 'run'
        ? '当前查看的是最近一次修复执行结果。右栏会保留日志与快照信息，帮助判断是否需要回滚。'
        : activeSection === 'roadmap' && roadmapInspectorState.mode === 'issue'
          ? `当前查看的是${formatCreativeSourceLayerLabel(roadmapInspectorState.issue?.source_layer)}问题详情。可以先理解影响范围，再决定是接受修复提案还是手动编辑。`
          : activeSection === 'roadmap' && roadmapInspectorState.mode === 'chapter'
            ? '章节细修被移到右侧 inspector，主区只保留阶段工作台与章节列表，避免长表单把整页压垮。'
            : activeSection === 'roadmap' && creativeIssueSourceFilter === 'review'
              ? '审阅队列先以只读形式进入工作台。这里用于集中查看待处理 scene，真正的通过、重试、修补动作仍在审阅页执行。'
              : activeSection === 'roadmap' && creativeIssueSourceFilter === 'scene'
                ? 'scene verifier 原始问题目前还没有稳定持久化真源，因此这一层暂时只保留接入预留，不直接伪造问题卡。'
                : activeSection === 'roadmap' && creativeIssueSourceFilter === 'canon'
                  ? '设定同步代理尚未启用。等 canon_sync agent 真正落地后，这里才会展示可执行的跨层同步提案。'
            : activeSection === 'roadmap'
              ? '未选中章节时，右栏默认显示当前阶段摘要与连续性压力点，帮助作者决定下一步先修哪里。'
      : activeSection === 'relationships'
        ? '关系图谱以画布为中心，具体人物或关系边的细节放在这里查看与编辑。'
        : activeSection === 'continuity'
          ? '这里汇总当前路线的任务、伏笔、关系与世界更新，作为下一章生成前的校对基线。'
          : '右侧摘要栏固定承接当前步骤的状态、风险与对象详情，减少主区信息噪音。'

  return (
    <div className="grid gap-5 xl:grid-cols-[260px_minmax(0,1fr)_340px]">
      <div className="xl:sticky xl:top-6 xl:self-start">
        <WorkspaceSidebar items={workspaceSidebarItems} activeKey={activeSection} onChange={setActiveSection} />
      </div>

      <div className="space-y-6 min-w-0">
        {activeSection === 'overview' ? (
          <section className="rounded-[28px] border border-stone-200 bg-white p-6 shadow-sm">
            {/* 总览页承接原先散落在多个卡片顶部的全局状态，作为进入任一步骤前的统一入口。 */}
            <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                  当前作品总览
                </div>
                <h3 className="mt-3 text-xl font-semibold text-stone-900">
                  {activeBook?.name ?? '当前作品'} · 蓝图状态 {formatBlueprintStatusLabel(blueprint?.status)}
                </h3>
                <p className="mt-2 text-sm leading-6 text-stone-600">
                  当前步骤：{formatBlueprintStepLabel(blueprint?.current_step)} · 生效版本：{activeRevisionLabel}。
                  左侧导航已经按蓝图层次拆开，主区聚焦单一步骤，右侧固定承接摘要与上下文细节。
                </p>
              </div>
              <div className="grid min-w-[260px] gap-3 rounded-3xl border border-stone-200 bg-stone-50 p-4 text-sm text-stone-600">
                <div>
                  <p className="text-xs font-medium text-stone-500">已确认层</p>
                  <p className="mt-1 font-medium text-stone-800">
                    {[worldIsConfirmed ? '世界观' : '', characterIsConfirmed ? '人物' : '', relationshipGraphIsConfirmed ? '关系' : '', roadmapIsLocked ? '路线' : '']
                      .filter(Boolean)
                      .join(' / ') || '尚未确认'}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-medium text-stone-500">当前风险</p>
                  <p className="mt-1 font-medium text-stone-800">
                    {totalFatalRoadmapIssues > 0
                      ? `${totalFatalRoadmapIssues} 个严重问题`
                      : totalWarningRoadmapIssues > 0
                        ? `${totalWarningRoadmapIssues} 个提醒`
                        : '无明显结构问题'}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-medium text-stone-500">下一步建议</p>
                  <p className="mt-1 font-medium text-stone-800">
                    {workspaceSidebarItems.find((item) => item.tone === 'pending' || item.tone === 'warning' || item.tone === 'danger')?.label ?? '继续细化当前工作台'}
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <p className="text-xs font-medium text-stone-500">候选方向</p>
                <p className="mt-2 text-2xl font-semibold text-stone-900">{blueprint?.concept_variants.length ?? 0}</p>
              </div>
              <div className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <p className="text-xs font-medium text-stone-500">人物数量</p>
                <p className="mt-2 text-2xl font-semibold text-stone-900">{characterDraft.length}</p>
              </div>
              <div className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <p className="text-xs font-medium text-stone-500">阶段进度</p>
                <p className="mt-2 text-2xl font-semibold text-stone-900">
                  {expandedArcNumbers.length}/{storyArcsToShow.length || 0}
                </p>
              </div>
              <div className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <p className="text-xs font-medium text-stone-500">连续性待跟进</p>
                <p className="mt-2 text-2xl font-semibold text-stone-900">
                  {continuityState.open_tasks.length + continuityState.active_loops.length}
                </p>
              </div>
            </div>

            <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {workspaceSidebarItems
                .filter((item) => item.key !== 'overview')
                .map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => setActiveSection(item.key)}
                    className="rounded-2xl border border-stone-200 bg-white px-4 py-4 text-left transition-colors hover:bg-stone-50"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-stone-900">{item.label}</p>
                      <span className="rounded-full bg-stone-100 px-2 py-1 text-[11px] text-stone-600">
                        {item.statusLabel}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-stone-500">{item.description}</p>
                  </button>
                ))}
            </div>
          </section>
        ) : null}

        {activeSection === 'intent' ? (
      <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
        {/* 创作意图保持独立步骤，避免和候选方向、世界观混在一页导致“还没保存就继续往后走”。 */}
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-stone-800">创作蓝图工作台</h3>
            <p className="mt-1 text-sm text-stone-500">
              当前状态：{formatBlueprintStatusLabel(blueprint?.status)} · 当前步骤：{formatBlueprintStepLabel(blueprint?.current_step)} · 生效版本：{activeRevisionLabel}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full px-2 py-1 text-xs font-medium ${
                intentIsSaved ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
              }`}
            >
              {intentIsSaved ? '创作意图已保存' : '创作意图待保存'}
            </span>
            {revisions.length > 0 && (
              <div className="rounded-xl bg-stone-50 px-3 py-2 text-xs text-stone-600">
                已有 {revisions.length} 个蓝图版本
              </div>
            )}
          </div>
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
            disabled={saveIntentMutation.isPending || intentIsSaved}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {saveIntentMutation.isPending ? '保存中…' : intentIsSaved ? '已保存创作意图' : '保存创作意图'}
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

        ) : null}

        {activeSection === 'concept' ? (
      <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
        {/* 候选方向单独成页，强调“先定整书方向，再细化世界观和人物”。 */}
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

        ) : null}

        {activeSection === 'world' ? (
      <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
        {/* 世界观仍沿用原有编辑表单，但通过页内分步把视觉噪音从主工作台里抽离。 */}
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-stone-800">世界观蓝图</h3>
            <p className="mt-1 text-sm text-stone-500">先锁定世界硬规则，再让人物和章节路线在这套约束内展开。</p>
          </div>
          <span
            className={`rounded-full px-2 py-1 text-xs font-medium ${
              worldIsConfirmed ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
            }`}
          >
            {worldIsConfirmed ? '已确认' : '待确认'}
          </span>
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
            disabled={!selectedVariantId || generateWorldMutation.isPending || worldIsConfirmed}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {generateWorldMutation.isPending ? '生成中…' : worldIsConfirmed ? '世界观草稿已锁定' : '生成世界观草稿'}
          </button>
          <button
            onClick={() => confirmWorldMutation.mutate()}
            disabled={!worldDraft || confirmWorldMutation.isPending || worldIsConfirmed}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {confirmWorldMutation.isPending ? '确认中…' : worldIsConfirmed ? '世界观已确认' : '确认世界观'}
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

        ) : null}

        {activeSection === 'characters' || activeSection === 'relationships' ? (
      <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
        {/* 人物与关系图谱共用同一套状态，但在 IA 上拆成两个入口：
            - 人物步骤偏角色本身；
            - 关系步骤偏图谱画布、待确认项和冲突处理。 */}
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-stone-800">
              {activeSection === 'relationships' ? '关系图谱工作区' : '人物蓝图'}
            </h3>
            <p className="mt-1 text-sm text-stone-500">
              {activeSection === 'relationships'
                ? '关系图谱以画布和冲突处理为中心，人物摘要与关系详情放到右侧上下文栏。'
                : '角色核心动机、不可突变特质和关系约束会作为后续正文的强校验来源。'}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span
              className={`rounded-full px-2 py-1 text-xs font-medium ${
                characterIsConfirmed ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
              }`}
            >
              {characterIsConfirmed ? '人物已确认' : '人物待确认'}
            </span>
            <span
              className={`rounded-full px-2 py-1 text-xs font-medium ${
                relationshipGraphIsConfirmed ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
              }`}
            >
              {relationshipGraphIsConfirmed ? '关系图谱已确认' : '关系图谱待确认'}
            </span>
          </div>
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
            disabled={!canGenerateCharacters || generateCharacterMutation.isPending || characterIsConfirmed}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {generateCharacterMutation.isPending ? '生成中…' : characterIsConfirmed ? '人物蓝图已锁定' : '生成人物蓝图'}
          </button>
          <button
            onClick={() => confirmCharacterMutation.mutate()}
            disabled={characterDraft.length === 0 || confirmCharacterMutation.isPending || characterIsConfirmed}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {confirmCharacterMutation.isPending ? '确认中…' : characterIsConfirmed ? '人物蓝图已确认' : '确认人物蓝图'}
          </button>
          <button
            onClick={() => confirmRelationshipGraphMutation.mutate()}
            disabled={
              relationshipGraphDraft.length === 0 || confirmRelationshipGraphMutation.isPending || relationshipGraphIsConfirmed
            }
            className="rounded-lg bg-stone-700 px-4 py-2 text-sm text-white hover:bg-stone-800 disabled:opacity-50"
          >
            {confirmRelationshipGraphMutation.isPending
              ? '确认中…'
              : relationshipGraphIsConfirmed
                ? '关系图谱已确认'
                : '单独确认关系图谱'}
          </button>
        </div>
        {roadmapError ? (
          <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {roadmapError}
          </p>
        ) : null}
        {activeSection !== 'relationships' ? (
        <div className="space-y-3">
          {characterDraft.map((character, index) => (
            <article
              key={`${character.name}-${index}`}
              ref={(node) => {
                characterCardRefs.current[normalizeCharacterNodeId(character.name || `角色${index + 1}`)] = node
              }}
              onClick={() => setGraphSelection({ kind: 'node', id: normalizeCharacterNodeId(character.name || `角色${index + 1}`) })}
              className={`rounded-xl border p-4 space-y-3 transition-all ${
                graphSelection?.kind === 'node' &&
                graphSelection.id === normalizeCharacterNodeId(character.name || `角色${index + 1}`)
                  ? 'border-indigo-300 ring-2 ring-indigo-100'
                  : 'border-stone-200'
              }`}
            >
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
        ) : null}
        {activeSection !== 'characters' ? (
        <div className="rounded-2xl border border-stone-200 p-4 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h4 className="text-sm font-semibold text-stone-800">人物关系图谱</h4>
              <p className="mt-1 text-xs text-stone-500">这里锁定核心人物关系边。已发布事实冲突时，系统会要求进入关系重规划流程。</p>
            </div>
            <button
              type="button"
              onClick={() =>
                setRelationshipGraphDraft((prev) => {
                  const nextEdge = {
                    edge_id: `rel-${prev.length + 1}`,
                    source_character_id: relationshipNodes[0]?.character_id ?? '',
                    target_character_id: relationshipNodes[1]?.character_id ?? relationshipNodes[0]?.character_id ?? '',
                    relation_type: '',
                    polarity: '复杂' as const,
                    intensity: 3,
                    visibility: '半公开' as const,
                    stability: '稳定' as const,
                    summary: '',
                    hidden_truth: '',
                    non_breakable_without_reveal: false,
                  }
                  setGraphSelection({ kind: 'edge', id: nextEdge.edge_id })
                  setEditingRelationshipIds((editPrev) => ({ ...editPrev, [nextEdge.edge_id]: true }))
                  return [...prev, nextEdge]
                })
              }
              className="rounded-lg border border-dashed border-stone-300 px-3 py-2 text-sm text-stone-600 hover:bg-stone-50"
            >
              新增关系边
            </button>
          </div>

          <RelationshipGraphPanel
            nodes={relationshipGraphView.nodes}
            edges={relationshipGraphView.edges}
            selection={graphSelection}
            onSelectionChange={setGraphSelection}
            onJumpToNodeForm={jumpToCharacterForm}
            onJumpToEdgeForm={jumpToRelationshipForm}
            onJumpToPending={jumpToPendingQueue}
            onJumpToConflict={jumpToConflictArea}
            sidebar={
              activeSection === 'relationships' ? (
                <div className="rounded-2xl border border-dashed border-stone-300 bg-white px-4 py-6 text-sm text-stone-500">
                  关系细节已迁到右侧上下文栏。点击图谱中的人物节点或关系边，即可在右侧查看和编辑。
                </div>
              ) : undefined
            }
            fullscreenSidebar={
              <RelationshipGraphWorkspaceEditor
                selectedCharacter={selectedCharacter}
                selectedEdge={selectedEdge}
                relationshipNodes={relationshipNodes}
                relationshipConflict={relationshipConflict}
                onCharacterChange={updateSelectedCharacter}
                onCommitCharacter={commitSelectedCharacterDraft}
                onEdgeChange={updateSelectedEdge}
                onSaveEdge={saveSelectedEdge}
                onDeleteEdge={deleteSelectedEdge}
                isCharacterEditing={
                  selectedCharacter ? (editingCharacterIds[selectedCharacterIndex] ?? !savedCharacterById[selectedCharacterIndex]) : false
                }
                isCharacterDirty={selectedCharacter ? (characterDirtyById[selectedCharacterIndex] ?? true) : false}
                onStartCharacterEdit={() => selectedCharacterIndex >= 0 && startEditingCharacter(selectedCharacterIndex)}
                onCancelCharacterEdit={() => selectedCharacterIndex >= 0 && cancelEditingCharacter(selectedCharacterIndex)}
                isEditing={
                  selectedEdge ? (editingRelationshipIds[selectedEdge.edge_id] ?? !savedRelationshipEdgeById[selectedEdge.edge_id]) : false
                }
                isDirty={selectedEdge ? (relationshipDirtyById[selectedEdge.edge_id] ?? true) : false}
                onStartEdit={() => selectedEdge && startEditingEdge(selectedEdge.edge_id)}
                onCancelEdit={() => selectedEdge && cancelEditingEdge(selectedEdge.edge_id)}
                onJumpToPending={jumpToPendingQueue}
                onJumpToConflict={jumpToConflictArea}
                isSavingEdge={upsertRelationshipEdgeMutation.isPending}
              />
            }
          />

          {relationshipGraphDraft.length === 0 ? (
            <div className="rounded-xl border border-dashed border-stone-300 px-4 py-6 text-sm text-stone-500">
              还没有关系边。生成人物蓝图后，系统会先给出一版关系草稿；你也可以手动新增。
            </div>
          ) : (
            <div className="space-y-3">
              {relationshipGraphDraft.map((edge, index) => {
                const isPersisted = Boolean(savedRelationshipEdgeById[edge.edge_id])
                const isEditing = editingRelationshipIds[edge.edge_id] ?? !isPersisted
                const isDirty = relationshipDirtyById[edge.edge_id] ?? true
                const isSelected = graphSelection?.kind === 'edge' && graphSelection.id === edge.edge_id

                return (
                  <div
                    key={edge.edge_id}
                    ref={(node) => {
                      relationshipCardRefs.current[edge.edge_id] = node
                    }}
                    onClick={() => setGraphSelection({ kind: 'edge', id: edge.edge_id })}
                    className={`rounded-xl border p-3 space-y-2 transition-all ${
                      relationshipConflict?.edge_id === edge.edge_id
                        ? 'border-red-300 bg-red-50/40'
                        : isSelected
                          ? 'border-indigo-300 ring-2 ring-indigo-100'
                          : 'border-stone-200'
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        {relationshipConflict?.edge_id === edge.edge_id ? (
                          <span className="rounded-full bg-red-100 px-2 py-1 font-medium text-red-700">冲突待处理</span>
                        ) : isEditing ? (
                          <span className="rounded-full bg-amber-100 px-2 py-1 font-medium text-amber-700">编辑中</span>
                        ) : (
                          <span className="rounded-full bg-emerald-100 px-2 py-1 font-medium text-emerald-700">已保存</span>
                        )}
                        {isPersisted && !isEditing && (
                          <span className="text-stone-500">
                            当前关系已落到草稿图谱，如需修改请先点击“编辑”。
                          </span>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {!isEditing ? (
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation()
                              startEditingEdge(edge.edge_id)
                            }}
                            className="rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-700 hover:bg-stone-50"
                          >
                            编辑
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation()
                              cancelEditingEdge(edge.edge_id)
                            }}
                            className="rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-600 hover:bg-stone-50"
                          >
                            取消
                          </button>
                        )}
                      </div>
                    </div>
                    <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-4">
                      <select
                        value={edge.source_character_id}
                        disabled={!isEditing}
                        onChange={(e) =>
                          setRelationshipGraphDraft((prev) =>
                            prev.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, source_character_id: e.target.value } : item,
                            ),
                          )
                        }
                        onFocus={() => setGraphSelection({ kind: 'edge', id: edge.edge_id })}
                        className="rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white disabled:bg-stone-50 disabled:text-stone-500"
                      >
                        {relationshipNodes.map((node) => (
                          <option key={node.character_id} value={node.character_id}>
                            {node.name}
                          </option>
                        ))}
                      </select>
                      <select
                        value={edge.target_character_id}
                        disabled={!isEditing}
                        onChange={(e) =>
                          setRelationshipGraphDraft((prev) =>
                            prev.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, target_character_id: e.target.value } : item,
                            ),
                          )
                        }
                        onFocus={() => setGraphSelection({ kind: 'edge', id: edge.edge_id })}
                        className="rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white disabled:bg-stone-50 disabled:text-stone-500"
                      >
                        {relationshipNodes.map((node) => (
                          <option key={node.character_id} value={node.character_id}>
                            {node.name}
                          </option>
                        ))}
                      </select>
                      <input
                        value={edge.relation_type}
                        disabled={!isEditing}
                        onChange={(e) =>
                          setRelationshipGraphDraft((prev) =>
                            prev.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, relation_type: e.target.value } : item,
                            ),
                          )
                        }
                        onFocus={() => setGraphSelection({ kind: 'edge', id: edge.edge_id })}
                        className="rounded-lg border border-stone-300 px-3 py-2 text-sm disabled:bg-stone-50 disabled:text-stone-500"
                        placeholder="关系类型"
                      />
                      <select
                        value={edge.polarity}
                        disabled={!isEditing}
                        onChange={(e) =>
                          setRelationshipGraphDraft((prev) =>
                            prev.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, polarity: e.target.value as RelationshipBlueprintEdge['polarity'] } : item,
                            ),
                          )
                        }
                        onFocus={() => setGraphSelection({ kind: 'edge', id: edge.edge_id })}
                        className="rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white disabled:bg-stone-50 disabled:text-stone-500"
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
                        disabled={!isEditing}
                        onChange={(e) =>
                          setRelationshipGraphDraft((prev) =>
                            prev.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, visibility: e.target.value as RelationshipBlueprintEdge['visibility'] } : item,
                            ),
                          )
                        }
                        onFocus={() => setGraphSelection({ kind: 'edge', id: edge.edge_id })}
                        className="rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white disabled:bg-stone-50 disabled:text-stone-500"
                      >
                        <option value="公开">公开</option>
                        <option value="半公开">半公开</option>
                        <option value="隐藏">隐藏</option>
                        <option value="误导性表象">误导性表象</option>
                      </select>
                      <select
                        value={edge.stability}
                        disabled={!isEditing}
                        onChange={(e) =>
                          setRelationshipGraphDraft((prev) =>
                            prev.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, stability: e.target.value as RelationshipBlueprintEdge['stability'] } : item,
                            ),
                          )
                        }
                        onFocus={() => setGraphSelection({ kind: 'edge', id: edge.edge_id })}
                        className="rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white disabled:bg-stone-50 disabled:text-stone-500"
                      >
                        <option value="稳定">稳定</option>
                        <option value="脆弱">脆弱</option>
                        <option value="正在转变">正在转变</option>
                      </select>
                      <input
                        value={String(edge.intensity)}
                        disabled={!isEditing}
                        onChange={(e) =>
                          setRelationshipGraphDraft((prev) =>
                            prev.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, intensity: parseNumber(e.target.value) } : item,
                            ),
                          )
                        }
                        onFocus={() => setGraphSelection({ kind: 'edge', id: edge.edge_id })}
                        className="rounded-lg border border-stone-300 px-3 py-2 text-sm disabled:bg-stone-50 disabled:text-stone-500"
                        placeholder="强度 1-5"
                      />
                    </div>
                    <textarea
                      value={edge.summary}
                      disabled={!isEditing}
                      onChange={(e) =>
                        setRelationshipGraphDraft((prev) =>
                          prev.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, summary: e.target.value } : item,
                          ),
                        )
                      }
                      onFocus={() => setGraphSelection({ kind: 'edge', id: edge.edge_id })}
                      rows={2}
                      className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm disabled:bg-stone-50 disabled:text-stone-500"
                      placeholder="关系摘要"
                    />
                    <textarea
                      value={edge.hidden_truth}
                      disabled={!isEditing}
                      onChange={(e) =>
                        setRelationshipGraphDraft((prev) =>
                          prev.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, hidden_truth: e.target.value } : item,
                          ),
                        )
                      }
                      onFocus={() => setGraphSelection({ kind: 'edge', id: edge.edge_id })}
                      rows={2}
                      className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm disabled:bg-stone-50 disabled:text-stone-500"
                      placeholder="隐藏真相 / 关系底牌"
                    />
                    <label className="flex items-center gap-2 text-xs text-stone-600">
                      <input
                        type="checkbox"
                        checked={edge.non_breakable_without_reveal}
                        disabled={!isEditing}
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
                        disabled={!isEditing || !isDirty || upsertRelationshipEdgeMutation.isPending}
                        className="rounded-lg bg-stone-800 px-3 py-2 text-sm text-white hover:bg-stone-900 disabled:opacity-50"
                      >
                        {upsertRelationshipEdgeMutation.isPending && isSelected
                          ? '保存中…'
                          : !isEditing
                            ? '已保存'
                            : isDirty
                              ? '保存这条关系'
                              : '已保存'}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setRelationshipGraphDraft((prev) => prev.filter((_, itemIndex) => itemIndex !== index))
                          setSavedRelationshipEdgeById((prev) => {
                            const next = { ...prev }
                            delete next[edge.edge_id]
                            return next
                          })
                          setEditingRelationshipIds((prev) => {
                            const next = { ...prev }
                            delete next[edge.edge_id]
                            return next
                          })
                          setRelationshipConflict((prev) => (prev?.edge_id === edge.edge_id ? null : prev))
                          if (isSelected) {
                            setGraphSelection(null)
                          }
                        }}
                        className="rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-600 hover:bg-stone-50"
                      >
                        删除
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {relationshipPending.length > 0 && (
            <div ref={pendingSectionRef} className="rounded-xl border border-amber-200 bg-amber-50/50 p-4 space-y-3">
              <h5 className="text-sm font-semibold text-amber-900">待确认人物 / 关系</h5>
              {relationshipPending.map((item) => (
                <div
                  key={item.id ?? `${item.item_type}-${item.summary}`}
                  onClick={() => {
                    if (item.item_type === 'character' && item.character) {
                      setGraphSelection({ kind: 'node', id: item.character.character_id })
                    }
                    if (item.item_type === 'relationship' && item.relationship) {
                      setGraphSelection({ kind: 'edge', id: item.relationship.edge_id })
                    }
                  }}
                  className="rounded-lg bg-white p-3 text-sm text-stone-700"
                >
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
            <div ref={conflictSectionRef} className="rounded-xl border border-red-200 bg-red-50/60 p-4 space-y-3">
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
        ) : null}
      </section>

        ) : null}

        {activeSection === 'roadmap' ? (
          <section className="space-y-4">
            <RoadmapControlPanel
              roadmapFeedback={roadmapFeedback}
              onRoadmapFeedbackChange={setRoadmapFeedback}
              totalChapterCount={storyArcsToShow.length > 0 ? Math.max(...storyArcsToShow.map((item) => item.end_chapter)) : 0}
              expandedArcCount={expandedArcNumbers.length}
              totalArcCount={storyArcsToShow.length}
              fatalCount={totalFatalRoadmapIssues}
              warningCount={totalWarningRoadmapIssues}
              pendingRepairCount={pendingCreativeRepairCount}
              isLocked={roadmapIsLocked}
              canGenerateStoryArcs={canGenerateStoryArcs}
              canLockRoadmap={canLockRoadmap}
              isGeneratingStoryArcs={generateStoryArcsMutation.isPending}
              isLockingRoadmap={confirmRoadmapMutation.isPending}
              isPlanningRepairs={planCreativeRepairsMutation.isPending}
              isReverifying={reverifyCreativeIssuesMutation.isPending}
              viewMode={roadmapViewMode}
              onViewModeChange={setRoadmapViewMode}
              onGenerateStoryArcs={() => generateStoryArcsMutation.mutate()}
              onPlanRepairs={() => planCreativeRepairsMutation.mutate([])}
              onReverify={() => reverifyCreativeIssuesMutation.mutate()}
              onConfirmRoadmap={() => confirmRoadmapMutation.mutate()}
              lockReasons={roadmapLockState.reasons}
            />

            {roadmapError ? (
              <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                {roadmapError}
              </div>
            ) : null}

            {storyArcsToShow.length === 0 ? (
              <div className="rounded-[24px] border border-dashed border-stone-300 bg-white px-5 py-8 text-sm text-stone-500 shadow-sm">
                还没有阶段骨架。请先确认世界观与人物蓝图，再生成整书阶段结构。
              </div>
            ) : roadmapViewMode === 'repair' ? (
              <CreativeRepairBoard
                issues={creativeIssues}
                proposals={creativeRepairProposals}
                runs={creativeRepairRuns}
                roadmapDraftDirty={roadmapDraftDirty}
                isPlanningRepairs={planCreativeRepairsMutation.isPending}
                isApplyingProposal={applyCreativeRepairProposalMutation.isPending}
                isRollingBackRun={rollbackCreativeRepairRunMutation.isPending}
                onPlanAll={() => planCreativeRepairsMutation.mutate([])}
                onPlanIssue={(issueId) => planCreativeRepairsMutation.mutate([issueId])}
                onApplyProposal={(proposalId) => applyCreativeRepairProposalMutation.mutate(proposalId)}
                onRollbackRun={(runId) => rollbackCreativeRepairRunMutation.mutate(runId)}
                onFocusChapter={focusRoadmapChapter}
                onFocusArc={jumpToRoadmapArc}
                onSelectIssue={(issueId) => {
                  const matchedIssue = creativeIssues.find((item) => item.issue_id === issueId) ?? null
                  if (matchedIssue) {
                    setCreativeIssueSourceFilter(
                      ['roadmap', 'scene', 'review', 'canon'].includes(matchedIssue.source_layer)
                        ? (matchedIssue.source_layer as CreativeIssueSourceFilter)
                        : 'all',
                    )
                  }
                  setSelectedCreativeIssueId(issueId)
                  setSelectedCreativeRepairProposalId(null)
                  setSelectedCreativeRepairRunId(null)
                  setSelectedRoadmapChapterNumber(null)
                }}
                onSelectProposal={(proposalId) => {
                  setCreativeIssueSourceFilter('roadmap')
                  setSelectedCreativeRepairProposalId(proposalId)
                  setSelectedCreativeIssueId(null)
                  setSelectedCreativeRepairRunId(null)
                  setSelectedRoadmapChapterNumber(null)
                }}
                onSelectRun={(runId) => {
                  setCreativeIssueSourceFilter('roadmap')
                  setSelectedCreativeRepairRunId(runId)
                  setSelectedCreativeIssueId(null)
                  setSelectedCreativeRepairProposalId(null)
                  setSelectedRoadmapChapterNumber(null)
                }}
                selectedIssueId={selectedCreativeIssueId}
                selectedProposalId={selectedCreativeRepairProposalId}
                selectedRunId={selectedCreativeRepairRunId}
                sourceFilter={creativeIssueSourceFilter}
                onSourceFilterChange={handleCreativeIssueSourceFilterChange}
                reviewQueueHref={`/reviews?book=${bookId}`}
              />
            ) : (
              <>
                <RoadmapArcBoard
                  currentArc={currentActionableArc}
                  blockedArcs={blockedRoadmapArcs}
                  completedArcs={completedRoadmapArcs}
                  activeArcNumber={activeRoadmapArcNumber}
                  issueStats={roadmapIssuesByArc}
                  feedbackByArcNumber={roadmapArcFeedbackByNumber}
                  pendingArcNumber={pendingRoadmapArcNumber}
                  isExpanding={expandStoryArcMutation.isPending}
                  isRegenerating={regenerateStoryArcMutation.isPending}
                  onToggleArc={toggleRoadmapArc}
                  onExpandArc={handleStoryArcExpand}
                  onRegenerateArc={handleRoadmapArcRegenerate}
                  onArcFeedbackChange={(arcNumber, value) =>
                    setRoadmapArcFeedbackByNumber((prev) => ({ ...prev, [arcNumber]: value }))
                  }
                  onFocusArc={(arcNumber) => {
                    setActiveRoadmapArcNumber(arcNumber)
                    setSelectedRoadmapChapterNumber(null)
                  }}
                />
                <RoadmapChapterList
                  currentArc={currentActionableArc}
                  currentArcChapters={currentArcChapters}
                  archivedArcChapters={archivedArcChapters}
                  selectedChapterNumber={selectedRoadmapChapterNumber}
                  highlightedChapterNumber={highlightedRoadmapChapterNumber}
                  lastGeneratedChapterNumber={lastGeneratedVisibleRoadmapChapterNumber}
                  activeArc={chapterActionArc}
                  roadmapIssues={roadmapIssues}
                  pendingChapterNumber={pendingRoadmapChapterNumber}
                  onSelectChapter={(chapterNumber) => {
                    setCreativeIssueSourceFilter('roadmap')
                    setSelectedRoadmapChapterNumber(chapterNumber)
                    setHighlightedRoadmapChapterNumber(chapterNumber)
                    setSelectedCreativeIssueId(null)
                    setSelectedCreativeRepairProposalId(null)
                    setSelectedCreativeRepairRunId(null)
                  }}
                  onRegenerateChapter={handleRoadmapChapterRegenerate}
                />
              </>
            )}
          </section>
        ) : null}
        {activeSection === 'continuity' ? (
          <section className="rounded-[28px] border border-stone-200 bg-white p-6 shadow-sm">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-xl font-semibold text-stone-900">连续性校对台</h3>
                <p className="mt-2 text-sm leading-6 text-stone-600">
                  这里把章节路线中已经回填的任务、伏笔、关键事件、关系推进与世界更新拉平展示，
                  让下一章生成前的检查更像“工作台”而不是零散表单附属区。
                </p>
              </div>
              <span className="rounded-full bg-sky-50 px-3 py-1 text-xs font-medium text-sky-700">
                最近计划到第 {continuityState.last_planned_chapter} 章
              </span>
            </div>

            <div className="mt-6 grid gap-4 xl:grid-cols-2">
              <div className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <h4 className="text-sm font-semibold text-stone-900">未完成任务</h4>
                <div className="mt-3 space-y-2">
                  {continuityState.open_tasks.length > 0 ? (
                    continuityState.open_tasks.map((task) => (
                      <div key={task.task_id} className="rounded-xl bg-white px-3 py-3 text-sm text-stone-700">
                        <p className="font-medium text-stone-900">{task.summary}</p>
                        <p className="mt-1 text-xs text-stone-500">
                          状态：{formatTaskStatusLabel(task.status)} · 关联人物：{task.related_characters.join('、') || '未标注'} · 最迟第{' '}
                          {task.due_end_chapter ?? '未标注'} 章
                        </p>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-stone-500">当前没有未完成任务。</p>
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <h4 className="text-sm font-semibold text-stone-900">活跃伏笔</h4>
                <div className="mt-3 space-y-2">
                  {continuityState.active_loops.length > 0 ? (
                    continuityState.active_loops.map((loop) => (
                      <div key={`${loop.loop_id}-${loop.label}`} className="rounded-xl bg-white px-3 py-3 text-sm text-stone-700">
                        <p className="font-medium text-stone-900">{formatContinuityLoopLabel(loop)}</p>
                        {loop.summary && loop.summary.trim() && loop.summary.trim() !== formatContinuityLoopLabel(loop) ? (
                          <p className="mt-1 text-sm text-stone-700">{loop.summary.trim()}</p>
                        ) : null}
                        <p className="mt-1 text-xs text-stone-500">
                          状态：{formatLoopStatusLabel(loop.status)} ·
                          {typeof (loop.due_end_chapter ?? loop.payoff_due_chapter) === 'number'
                            ? ` 最迟第 ${loop.due_end_chapter ?? loop.payoff_due_chapter} 章兑现`
                            : ' 尚未设置最迟兑现章'}
                        </p>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-stone-500">当前没有活跃伏笔。</p>
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <h4 className="text-sm font-semibold text-stone-900">最近事件</h4>
                <div className="mt-3 space-y-2">
                  {continuityState.recent_events.length > 0 ? (
                    continuityState.recent_events.map((event, index) => (
                      <div key={`${event.chapter_number}-${event.kind}-${index}`} className="rounded-xl bg-white px-3 py-3 text-sm text-stone-700">
                        <p className="font-medium text-stone-900">
                          第 {event.chapter_number} 章 · {formatContinuityEventKindLabel(event.kind)}
                        </p>
                        <p className="mt-1 text-sm text-stone-700">{event.summary}</p>
                        <p className="mt-1 text-xs text-stone-500">
                          阶段：{event.story_stage || '未标注'} · 时间锚点：{event.timeline_anchor || '未标注'}
                        </p>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-stone-500">当前没有最近事件。</p>
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <h4 className="text-sm font-semibold text-stone-900">关系与世界更新</h4>
                <div className="mt-3 space-y-4">
                  <div>
                    <p className="text-xs font-medium uppercase tracking-[0.18em] text-stone-400">关系状态</p>
                    <div className="mt-2 space-y-2">
                      {continuityState.relationship_states.length > 0 ? (
                        continuityState.relationship_states.map((item, index) => (
                          <div
                            key={`${item.source_character}-${item.target_character}-${index}`}
                            className="rounded-xl bg-white px-3 py-3 text-sm text-stone-700"
                          >
                            <p className="font-medium text-stone-900">
                              {item.source_character} → {item.target_character}
                            </p>
                            <p className="mt-1 text-sm text-stone-700">{item.latest_summary}</p>
                            <p className="mt-1 text-xs text-stone-500">
                              来源章节：第 {item.source_chapter ?? '未标注'} 章
                            </p>
                          </div>
                        ))
                      ) : (
                        <p className="text-sm text-stone-500">当前没有已回填关系推进。</p>
                      )}
                    </div>
                  </div>
                  <div>
                    <p className="text-xs font-medium uppercase tracking-[0.18em] text-stone-400">世界更新</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {continuityState.world_updates.length > 0 ? (
                        continuityState.world_updates.map((item) => (
                          <span key={item} className="rounded-full bg-white px-3 py-1.5 text-xs text-stone-700">
                            {item}
                          </span>
                        ))
                      ) : (
                        <p className="text-sm text-stone-500">当前没有新的世界更新。</p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>
        ) : null}

        {activeSection === 'settings' ? (
          <section className="rounded-[28px] border border-stone-200 bg-white p-6 shadow-sm">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-xl font-semibold text-stone-900">作品设置入口</h3>
                <p className="mt-2 text-sm leading-6 text-stone-600">
                  作品基础配置已经从主工作流剥离到独立的“作品库”页面，避免首屏继续被大面积基础表单占住。
                </p>
              </div>
              <Link
                to={`/books`}
                className="rounded-xl border border-stone-300 bg-white px-4 py-2.5 text-sm font-medium text-stone-700 hover:bg-stone-50"
              >
                前往作品库编辑
              </Link>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-2">
              <div className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <p className="text-xs font-medium text-stone-500">书名</p>
                <p className="mt-2 text-lg font-semibold text-stone-900">{activeBook?.name ?? '未选择作品'}</p>
              </div>
              <div className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <p className="text-xs font-medium text-stone-500">语言 / 专名策略</p>
                <p className="mt-2 text-lg font-semibold text-stone-900">
                  {formatLanguageLabel(activeBook?.language)} / {formatNamingPolicyLabel(activeBook?.naming_policy)}
                </p>
              </div>
              <div className="rounded-2xl border border-stone-200 bg-stone-50 p-4 md:col-span-2">
                <p className="text-xs font-medium text-stone-500">文风配置</p>
                <p className="mt-2 text-sm text-stone-700">
                  预设：{formatStylePresetLabel(activeBook?.style_preset)}
                </p>
                <p className="mt-2 text-sm leading-6 text-stone-600">{activeBook?.style_prompt || '当前没有自定义文风说明。'}</p>
              </div>
            </div>
          </section>
        ) : null}

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

      <div className="xl:sticky xl:top-6 xl:self-start">
        <WorkspaceInspectorRail
          title={summaryRailTitle}
          description={summaryRailDescription}
          statusLabel={formatBlueprintStatusLabel(blueprint?.status)}
          revisionLabel={activeRevisionLabel}
          fatalCount={totalFatalRoadmapIssues}
          warningCount={totalWarningRoadmapIssues}
        >
          {/* 全局状态卡已经上移到 WorkspaceInspectorRail 壳层，这里不再重复渲染第二份。 */}

          {activeSection === 'roadmap' ? (
            <RoadmapInspectorPanel
              state={roadmapInspectorState}
              currentActionableArc={currentActionableArc}
              chapterActionArc={chapterActionArc}
              continuityState={continuityState}
              selectedRoadmapChapterIssues={selectedRoadmapChapterIssues}
              pendingRoadmapChapterNumber={pendingRoadmapChapterNumber}
              canRegenerateFocusedRoadmapChapter={canRegenerateFocusedRoadmapChapter}
              joinTags={joinTags}
              parseTags={parseTags}
              serializeChapterTasks={serializeChapterTasks}
              parseChapterTasks={parseChapterTasks}
              serializeRelationshipBeats={serializeRelationshipBeats}
              parseRelationshipBeats={parseRelationshipBeats}
              parseOptionalChapterNumber={parseOptionalChapterNumber}
              updateRoadmapChapterByNumber={updateRoadmapChapterByNumber}
              updateRoadmapLoopByIndex={updateRoadmapLoopByIndex}
              addRoadmapLoop={addRoadmapLoop}
            removeRoadmapLoop={removeRoadmapLoop}
            onRegenerateChapter={handleRoadmapChapterRegenerate}
            reviewQueueHref={`/reviews?book=${bookId}`}
          />
          ) : null}

          {activeSection !== 'roadmap' && roadmapIssues.length > 0 ? (
            <section className="rounded-[28px] border border-stone-200 bg-white p-5 shadow-sm">
              <h4 className="text-sm font-semibold text-stone-900">优先处理问题</h4>
              <div className="mt-3 space-y-2">
                {roadmapIssues.slice(0, 4).map((issue, index) => (
                  <div
                    key={`${issue.type}-${issue.chapter_number ?? index}`}
                    className={`rounded-2xl px-3 py-3 text-sm ${
                      issue.severity === 'fatal' ? 'bg-rose-50 text-rose-700' : 'bg-amber-50 text-amber-700'
                    }`}
                  >
                    <p className="font-medium">
                      {issue.chapter_number ? `第 ${issue.chapter_number} 章` : issue.arc_number ? `第 ${issue.arc_number} 幕` : '路线问题'}
                    </p>
                    <p className="mt-1 leading-6">{issue.message}</p>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {activeSection === 'characters' || activeSection === 'relationships' ? (
            <>
              {/* 关系图谱的对象级编辑统一放到右栏：
                  - 主区可以持续保留图谱画布；
                  - 右栏根据当前选中的节点/边切换表单；
                  - 全屏图谱和常规图谱都复用同一套 editor 逻辑。 */}
              <RelationshipGraphWorkspaceEditor
                selectedCharacter={selectedCharacter}
                selectedEdge={selectedEdge}
                relationshipNodes={relationshipNodes}
                relationshipConflict={relationshipConflict}
                onCharacterChange={updateSelectedCharacter}
                onCommitCharacter={commitSelectedCharacterDraft}
                onEdgeChange={updateSelectedEdge}
                onSaveEdge={saveSelectedEdge}
                onDeleteEdge={deleteSelectedEdge}
                isCharacterEditing={
                  selectedCharacter ? (editingCharacterIds[selectedCharacterIndex] ?? !savedCharacterById[selectedCharacterIndex]) : false
                }
                isCharacterDirty={selectedCharacter ? (characterDirtyById[selectedCharacterIndex] ?? true) : false}
                onStartCharacterEdit={() => selectedCharacterIndex >= 0 && startEditingCharacter(selectedCharacterIndex)}
                onCancelCharacterEdit={() => selectedCharacterIndex >= 0 && cancelEditingCharacter(selectedCharacterIndex)}
                isEditing={
                  selectedEdge ? (editingRelationshipIds[selectedEdge.edge_id] ?? !savedRelationshipEdgeById[selectedEdge.edge_id]) : false
                }
                isDirty={selectedEdge ? (relationshipDirtyById[selectedEdge.edge_id] ?? true) : false}
                onStartEdit={() => selectedEdge && startEditingEdge(selectedEdge.edge_id)}
                onCancelEdit={() => selectedEdge && cancelEditingEdge(selectedEdge.edge_id)}
                onJumpToPending={jumpToPendingQueue}
                onJumpToConflict={jumpToConflictArea}
                isSavingEdge={upsertRelationshipEdgeMutation.isPending}
              />
            </>
          ) : null}

          {activeSection === 'continuity' ? (
            <section className="rounded-[28px] border border-stone-200 bg-white p-5 shadow-sm">
              <h4 className="text-sm font-semibold text-stone-900">连续性检查清单</h4>
              <ul className="mt-3 space-y-2 text-sm text-stone-600">
                <li>先看未完成任务和活跃伏笔，再决定下一章应承接哪些问题。</li>
                <li>如果关系或世界更新过多，先回到相关步骤确认是否需要补强蓝图。</li>
                <li>若连续性告警升到 fatal，优先处理阶段结构或最后一章重生成。</li>
              </ul>
            </section>
          ) : null}
        </WorkspaceInspectorRail>
      </div>
    </div>
  )
}

