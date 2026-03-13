/**
 * 蓝图工作台：在同一页面里逐层生成、编辑并确认整书蓝图。
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { RelationshipGraphPanel } from '@/components/relationship-graph/RelationshipGraphPanel'
import { RelationshipGraphWorkspaceEditor } from '@/components/relationship-graph/RelationshipGraphWorkspaceEditor'
import {
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
  regenerateStoryArc,
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
  RelationshipGraphSelection,
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
    .split(/[,，、；;\n]/)
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
  const [roadmapArcFeedbackByNumber, setRoadmapArcFeedbackByNumber] = useState<Record<number, string>>({})
  const [activeRoadmapArcNumber, setActiveRoadmapArcNumber] = useState<number | null>(null)
  const [highlightedRoadmapChapterNumber, setHighlightedRoadmapChapterNumber] = useState<number | null>(null)
  const [regenerationProposalByVariantId, setRegenerationProposalByVariantId] = useState<
    Record<number, ConceptVariantRegenerationResult>
  >({})
  const characterCardRefs = useRef<Record<string, HTMLElement | null>>({})
  const relationshipCardRefs = useRef<Record<string, HTMLElement | null>>({})
  const roadmapChapterRefs = useRef<Record<number, HTMLElement | null>>({})
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
      toast.success('阶段骨架已生成，请按阶段逐个展开章节')
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
      toast.success(`第 ${variables.arcNumber} 幕章节已展开`)
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
  const roadmapIssues = roadmapDraftDirty ? localRoadmapIssues : blueprint?.roadmap_validation_issues ?? []
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
    !regenerateStoryArcMutation.isPending
  const activeRevisionLabel = useMemo(() => {
    const active = revisions.find((item) => item.is_active)
    return active ? `v${active.revision_number}` : '未锁定'
  }, [revisions])
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
    setHighlightedRoadmapChapterNumber(chapterNumber)
    requestAnimationFrame(() => {
      roadmapChapterRefs.current[chapterNumber]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    })
  }

  const toggleRoadmapArc = (arcNumber: number) => {
    setActiveRoadmapArcNumber((current) => (current === arcNumber ? null : arcNumber))
  }

  const jumpToRoadmapArc = (arcNumber: number) => {
    setActiveRoadmapArcNumber(arcNumber)
  }

  const handleStoryArcExpand = (arcNumber: number) => {
    const feedback = roadmapArcFeedbackByNumber[arcNumber] ?? ''
    expandStoryArcMutation.mutate({ arcNumber, feedback })
  }

  const handleRoadmapArcRegenerate = (arcNumber: number) => {
    const feedback = roadmapArcFeedbackByNumber[arcNumber] ?? ''
    regenerateStoryArcMutation.mutate({ arcNumber, feedback })
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

      <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-stone-800">人物蓝图</h3>
            <p className="mt-1 text-sm text-stone-500">角色核心动机、不可突变特质和关系约束会作为后续正文的强校验来源。</p>
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
      </section>

      <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-stone-800">章节路线</h3>
            <p className="mt-1 text-sm text-stone-500">先生成阶段骨架，再逐幕展开章节。结构问题优先按阶段处理，章节卡片只负责细修。</p>
          </div>
          <span
            className={`rounded-full px-2 py-1 text-xs font-medium ${
              roadmapIsLocked ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
            }`}
          >
            {roadmapIsLocked ? '整书蓝图已锁定' : '章节路线待锁定'}
          </span>
        </div>
        <textarea
          value={roadmapFeedback}
          onChange={(e) => setRoadmapFeedback(e.target.value)}
          rows={2}
          placeholder="可选：补充本层微调要求，例如“前 3 章开局更猛，中段节奏更压抑”。"
          className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
        {roadmapError ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {roadmapError}
          </div>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => generateStoryArcsMutation.mutate()}
            disabled={!canGenerateStoryArcs || generateStoryArcsMutation.isPending || roadmapIsLocked}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {generateStoryArcsMutation.isPending
              ? '生成中…'
              : roadmapIsLocked
                ? '阶段骨架已锁定'
                : storyArcsToShow.length > 0
                  ? '重新生成阶段骨架'
                  : '生成阶段骨架'}
          </button>
          <button
            onClick={() => confirmRoadmapMutation.mutate()}
            disabled={!canLockRoadmap}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {confirmRoadmapMutation.isPending ? '锁定中…' : roadmapIsLocked ? '整书蓝图已锁定' : '锁定整书蓝图'}
          </button>
        </div>
        <div className="grid gap-3 md:grid-cols-4">
          <div className="rounded-xl border border-stone-200 bg-stone-50 px-4 py-3">
            <p className="text-xs font-medium text-stone-500">整书概览</p>
            <p className="mt-1 text-lg font-semibold text-stone-800">
              {storyArcsToShow.length > 0 ? Math.max(...storyArcsToShow.map((item) => item.end_chapter)) : 0} 章
            </p>
          </div>
          <div className="rounded-xl border border-stone-200 bg-stone-50 px-4 py-3">
            <p className="text-xs font-medium text-stone-500">阶段展开</p>
            <p className="mt-1 text-lg font-semibold text-stone-800">{expandedArcNumbers.length}/{storyArcsToShow.length} 幕</p>
          </div>
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3">
            <p className="text-xs font-medium text-rose-500">严重问题</p>
            <p className="mt-1 text-lg font-semibold text-rose-700">{totalFatalRoadmapIssues}</p>
          </div>
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
            <p className="text-xs font-medium text-amber-600">提醒</p>
            <p className="mt-1 text-lg font-semibold text-amber-700">{totalWarningRoadmapIssues}</p>
          </div>
        </div>
        <div className="rounded-xl border border-stone-200 bg-stone-50 px-4 py-3 text-sm text-stone-600">
          <p className="font-medium text-stone-700">
            {roadmapLockState.canLock ? '当前路线已达到锁定条件。' : '当前路线仍不建议锁定整书蓝图。'}
          </p>
          {!roadmapLockState.canLock && roadmapLockState.reasons.length > 0 ? (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-xs">
              {roadmapLockState.reasons.slice(0, 4).map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : null}
        </div>
        {storyArcsToShow.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h4 className="text-sm font-semibold text-stone-800">阶段工作台</h4>
              <span className="text-xs text-stone-500">先展开并判断哪一幕出了问题，再决定是否进入章节细修</span>
            </div>
            <div className="grid gap-3 xl:grid-cols-2">
              {storyArcsToShow.map((arc) => {
                const issueStats = roadmapIssuesByArc.find((item) => item.arcNumber === arc.arc_number)
                const fatalCount = issueStats?.fatalCount ?? 0
                const warningCount = issueStats?.warningCount ?? 0
                const isActive = activeRoadmapArcNumber === arc.arc_number
                const isPending = pendingRoadmapArcNumber === arc.arc_number
                const arcIssues = roadmapIssues.filter((issue) => issue.arc_number === arc.arc_number)
                return (
                  <article
                    key={`${arc.arc_number}-${arc.title}`}
                    className={`rounded-xl border p-4 space-y-3 ${
                      fatalCount > 0
                        ? 'border-rose-200 bg-rose-50/40'
                        : warningCount > 0
                          ? 'border-amber-200 bg-amber-50/40'
                          : 'border-stone-200 bg-stone-50/70'
                    } ${isActive ? 'ring-2 ring-indigo-200' : ''}`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <h5 className="text-sm font-semibold text-stone-800">
                        第 {arc.arc_number} 幕 · {arc.title}
                      </h5>
                      <div className="flex items-center gap-2">
                        {fatalCount > 0 ? (
                          <span className="rounded-full bg-rose-100 px-2 py-1 text-xs font-medium text-rose-700">需重做</span>
                        ) : warningCount > 0 ? (
                          <span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-medium text-amber-700">需优化</span>
                        ) : arc.has_chapters ? (
                          <span className="rounded-full bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-700">
                            已展开
                          </span>
                        ) : (
                          <span className="rounded-full bg-stone-200 px-2 py-1 text-xs font-medium text-stone-700">
                            待展开
                          </span>
                        )}
                        <span className="rounded-full bg-white px-2 py-1 text-xs text-stone-500">
                          第 {arc.start_chapter}-{arc.end_chapter} 章
                        </span>
                        <span
                          className={`rounded-full px-2 py-1 text-xs font-medium ${
                            arc.has_chapters ? 'bg-indigo-100 text-indigo-700' : 'bg-stone-100 text-stone-600'
                          }`}
                        >
                          {arc.has_chapters ? '章节已规划' : '仅有阶段骨架'}
                        </span>
                      </div>
                    </div>
                    <p className="text-sm text-stone-700">{arc.purpose || '未填写阶段目标'}</p>
                    <div className="flex flex-wrap gap-2 text-xs">
                      <span className="rounded-full bg-white px-2 py-1 text-stone-600">严重问题 {fatalCount}</span>
                      <span className="rounded-full bg-white px-2 py-1 text-stone-600">提醒 {warningCount}</span>
                      <span className="rounded-full bg-white px-2 py-1 text-stone-600">
                        时间线{arc.timeline_milestones.length > 0 ? '已推进' : '待补'}
                      </span>
                      <span className="rounded-full bg-white px-2 py-1 text-stone-600">
                        主线{arc.main_progress.length > 0 ? '已推进' : '待补'}
                      </span>
                      <span className="rounded-full bg-white px-2 py-1 text-stone-600">
                        阶段高潮{arc.arc_climax ? '已设置' : '待补'}
                      </span>
                    </div>
                    <div className="grid gap-2 md:grid-cols-2">
                      <div className="rounded-lg bg-white px-3 py-2 text-xs text-stone-600">
                        <p className="font-medium text-stone-700">主线推进</p>
                        <p className="mt-1">{arc.main_progress.length ? arc.main_progress.join('；') : '未填写'}</p>
                      </div>
                      <div className="rounded-lg bg-white px-3 py-2 text-xs text-stone-600">
                        <p className="font-medium text-stone-700">关系推进</p>
                        <p className="mt-1">
                          {arc.relationship_progress.length ? arc.relationship_progress.join('；') : '未填写'}
                        </p>
                      </div>
                      <div className="rounded-lg bg-white px-3 py-2 text-xs text-stone-600">
                        <p className="font-medium text-stone-700">时间里程碑</p>
                        <p className="mt-1">
                          {arc.timeline_milestones.length ? arc.timeline_milestones.join('；') : '未填写'}
                        </p>
                      </div>
                      <div className="rounded-lg bg-white px-3 py-2 text-xs text-stone-600">
                        <p className="font-medium text-stone-700">阶段高潮</p>
                        <p className="mt-1">{arc.arc_climax || '未填写'}</p>
                      </div>
                    </div>
                    {arcIssues.length > 0 ? (
                      <div className="rounded-lg border border-dashed border-stone-300 bg-white px-3 py-3 text-xs text-stone-600">
                        <p className="font-medium text-stone-700">本阶段问题摘要</p>
                        <ul className="mt-2 space-y-1">
                          {arcIssues.slice(0, 3).map((issue, issueIndex) => (
                            <li key={`${issue.type}-${issueIndex}`} className="leading-5">
                              {issue.severity === 'fatal' ? '严重：' : '提醒：'}
                              {issue.message}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    <div className="space-y-2">
                      <label className="block text-xs font-medium text-stone-600">编辑阶段说明 / 重生成要求</label>
                      <textarea
                        value={roadmapArcFeedbackByNumber[arc.arc_number] ?? ''}
                        onChange={(e) =>
                          setRoadmapArcFeedbackByNumber((prev) => ({
                            ...prev,
                            [arc.arc_number]: e.target.value,
                          }))
                        }
                        rows={2}
                        placeholder="例如：不要再重复调查型章节，要更早出现局势升级，并让本阶段结尾形成明确反转。"
                        className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
                      />
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => toggleRoadmapArc(arc.arc_number)}
                        disabled={!arc.has_chapters}
                        className="rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-700 hover:bg-stone-100"
                      >
                        {!arc.has_chapters ? '尚未展开章节' : isActive ? '收起章节' : '查看本阶段章节'}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleStoryArcExpand(arc.arc_number)}
                        disabled={isPending || expandStoryArcMutation.isPending || arc.has_chapters}
                        className="rounded-lg bg-emerald-600 px-3 py-2 text-sm text-white hover:bg-emerald-700 disabled:opacity-50"
                      >
                        {isPending && !arc.has_chapters ? '展开中…' : arc.has_chapters ? '本阶段已展开' : '展开本阶段章节'}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRoadmapArcRegenerate(arc.arc_number)}
                        disabled={isPending || regenerateStoryArcMutation.isPending}
                        className="rounded-lg bg-amber-600 px-3 py-2 text-sm text-white hover:bg-amber-700 disabled:opacity-50"
                      >
                        {isPending ? '重生成中…' : '重生成本阶段骨架'}
                      </button>
                    </div>
                  </article>
                )
              })}
            </div>
          </div>
        )}
        {roadmapIssues.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-sm font-semibold text-stone-800">可行动问题列表</h4>
            <div className="space-y-2">
              {roadmapIssues.map((issue, index) => (
                <div
                  key={`${issue.type}-${issue.chapter_number ?? index}-${issue.story_stage}`}
                  className={`rounded-xl border px-4 py-3 text-sm ${
                    issue.severity === 'fatal'
                      ? 'border-rose-200 bg-rose-50 text-rose-700'
                      : 'border-amber-200 bg-amber-50 text-amber-700'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium">
                      {issue.severity === 'fatal' ? '严重问题' : '提醒'}
                      {issue.chapter_number ? ` · 第 ${issue.chapter_number} 章` : ''}
                    </span>
                    {issue.story_stage ? (
                      <span className="text-xs">
                        {issue.story_stage}
                        {issue.arc_number ? ` · 第 ${issue.arc_number} 幕` : ''}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1">{issue.message}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {issue.chapter_number ? (
                      <button
                        type="button"
                        onClick={() => focusRoadmapChapter(issue.chapter_number!, issue.arc_number)}
                        className="rounded-lg border border-current px-3 py-1.5 text-xs"
                      >
                        定位到章节
                      </button>
                    ) : null}
                    {issue.arc_number ? (
                      <button
                        type="button"
                        onClick={() => jumpToRoadmapArc(issue.arc_number!)}
                        className="rounded-lg border border-current px-3 py-1.5 text-xs"
                      >
                        查看所属阶段
                      </button>
                    ) : null}
                    {issue.arc_number &&
                    ['regenerate_stage', 'regenerate_arc'].includes(issue.suggested_action ?? '') ? (
                      <button
                        type="button"
                        onClick={() => handleRoadmapArcRegenerate(issue.arc_number!)}
                        disabled={pendingRoadmapArcNumber === issue.arc_number}
                        className="rounded-lg bg-current/90 px-3 py-1.5 text-xs text-white disabled:opacity-60"
                      >
                        {pendingRoadmapArcNumber === issue.arc_number ? '重生成中…' : '重生成本阶段骨架'}
                      </button>
                    ) : null}
                    {issue.arc_number && ['review_stage', 'review_arc'].includes(issue.suggested_action ?? '') ? (
                      <button
                        type="button"
                        onClick={() => jumpToRoadmapArc(issue.arc_number!)}
                        className="rounded-lg bg-current/90 px-3 py-1.5 text-xs text-white"
                      >
                        查看所属阶段
                      </button>
                    ) : null}
                    {issue.arc_number && issue.suggested_action === 'expand_arc' ? (
                      <button
                        type="button"
                        onClick={() => handleStoryArcExpand(issue.arc_number!)}
                        disabled={pendingRoadmapArcNumber === issue.arc_number}
                        className="rounded-lg bg-current/90 px-3 py-1.5 text-xs text-white disabled:opacity-60"
                      >
                        {pendingRoadmapArcNumber === issue.arc_number ? '展开中…' : '展开本阶段章节'}
                      </button>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h4 className="text-sm font-semibold text-stone-800">章节细修区</h4>
              <p className="mt-1 text-xs text-stone-500">阶段负责结构，章节负责细节。大问题优先用阶段重生成处理。</p>
            </div>
            {activeRoadmapArcNumber ? (
              <span className="rounded-full bg-indigo-100 px-2 py-1 text-xs font-medium text-indigo-700">
                当前聚焦：第 {activeRoadmapArcNumber} 幕
              </span>
            ) : null}
          </div>
          {visibleRoadmapChapters.map((item) => {
            const index = roadmapToShow.findIndex((row) => row.chapter_number === item.chapter_number)
            const chapterIssues = roadmapIssues.filter((issue) => issue.chapter_number === item.chapter_number)
            return (
            <article
              key={item.chapter_number}
              ref={(node) => {
                roadmapChapterRefs.current[item.chapter_number] = node
              }}
              className={`rounded-xl border p-4 space-y-3 ${
                highlightedRoadmapChapterNumber === item.chapter_number
                  ? 'ring-2 ring-indigo-200'
                  : ''
              } ${
                chapterIssues.some((issue) => issue.severity === 'fatal')
                  ? 'border-rose-200 bg-rose-50/40'
                  : chapterIssues.length > 0
                    ? 'border-amber-200 bg-amber-50/40'
                    : 'border-stone-200'
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <h4 className="text-sm font-semibold text-stone-800">第 {item.chapter_number} 章</h4>
                <div className="flex items-center gap-2">
                  {chapterIssues.length > 0 ? (
                    <span
                      className={`rounded-full px-2 py-1 text-xs font-medium ${
                        chapterIssues.some((issue) => issue.severity === 'fatal')
                          ? 'bg-rose-100 text-rose-700'
                          : 'bg-amber-100 text-amber-700'
                      }`}
                    >
                      {chapterIssues.some((issue) => issue.severity === 'fatal') ? '需重做' : '需优化'}
                    </span>
                  ) : null}
                  <span className="text-xs text-stone-500">
                    计划线索 {item.planned_loops.length} 条
                  </span>
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                <input
                  value={item.story_stage}
                  onChange={(e) =>
                    setRoadmapDraft((prev) =>
                      prev.map((row, rowIndex) => (rowIndex === index ? { ...row, story_stage: e.target.value } : row)),
                    )
                  }
                  placeholder="所属阶段"
                  className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                />
                <input
                  value={item.timeline_anchor}
                  onChange={(e) =>
                    setRoadmapDraft((prev) =>
                      prev.map((row, rowIndex) =>
                        rowIndex === index ? { ...row, timeline_anchor: e.target.value } : row,
                      ),
                    )
                  }
                  placeholder="时间线锚点"
                  className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                />
                <input
                  value={item.chapter_function}
                  onChange={(e) =>
                    setRoadmapDraft((prev) =>
                      prev.map((row, rowIndex) =>
                        rowIndex === index ? { ...row, chapter_function: e.target.value } : row,
                      ),
                    )
                  }
                  placeholder="章节功能"
                  className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                />
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
              <textarea
                value={item.story_progress}
                onChange={(e) =>
                  setRoadmapDraft((prev) =>
                    prev.map((row, rowIndex) =>
                      rowIndex === index ? { ...row, story_progress: e.target.value } : row,
                    ),
                  )
                }
                rows={2}
                placeholder="这一章真正推进了什么主线事实"
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
              <p className="rounded-lg bg-stone-50 px-3 py-2 text-xs text-stone-500">
                若问题属于“重复、停滞、缺少升级”，优先回到上方重生成本阶段；章节卡片主要用于细修与补丁。
              </p>
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
                <textarea
                  value={joinTags(item.new_reveals)}
                  onChange={(e) =>
                    setRoadmapDraft((prev) =>
                      prev.map((row, rowIndex) =>
                        rowIndex === index ? { ...row, new_reveals: parseTags(e.target.value) } : row,
                      ),
                    )
                  }
                  rows={2}
                  placeholder="新揭示信息，多项可用逗号分隔"
                  className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                />
                <textarea
                  value={joinTags(item.status_shift)}
                  onChange={(e) =>
                    setRoadmapDraft((prev) =>
                      prev.map((row, rowIndex) =>
                        rowIndex === index ? { ...row, status_shift: parseTags(e.target.value) } : row,
                      ),
                    )
                  }
                  rows={2}
                  placeholder="状态变化，多项可用逗号分隔"
                  className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                />
              </div>
              <details className="rounded-xl border border-stone-200 bg-stone-50 p-3">
                <summary className="cursor-pointer text-sm font-medium text-stone-700">更多字段</summary>
                <div className="mt-3 space-y-3">
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
                    <input
                      value={item.depends_on_chapters.join('，')}
                      onChange={(e) =>
                        setRoadmapDraft((prev) =>
                          prev.map((row, rowIndex) =>
                            rowIndex === index
                              ? {
                                  ...row,
                                  depends_on_chapters: parseTags(e.target.value)
                                    .map((value) => Number(value))
                                    .filter((value) => Number.isFinite(value)),
                                }
                              : row,
                          ),
                        )
                      }
                      placeholder="承接章节，例如 12，13"
                      className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                    />
                    <input
                      value={item.anti_repeat_signature}
                      onChange={(e) =>
                        setRoadmapDraft((prev) =>
                          prev.map((row, rowIndex) =>
                            rowIndex === index ? { ...row, anti_repeat_signature: e.target.value } : row,
                          ),
                        )
                      }
                      placeholder="内部去重标签"
                      className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                    />
                  </div>
                </div>
              </details>
              <div className="grid gap-2 md:grid-cols-2">
                <div className="rounded-lg bg-stone-50 px-3 py-2 text-xs text-stone-600">
                  主线推进：{item.story_progress || '未指定'}
                </div>
                <div className="rounded-lg bg-stone-50 px-3 py-2 text-xs text-stone-600">
                  时间锚点：{item.timeline_anchor || '未指定'}
                </div>
                <div className="rounded-lg bg-stone-50 px-3 py-2 text-xs text-stone-600">
                  人物推进：{item.character_progress.length > 0 ? item.character_progress.join('；') : '未指定'}
                </div>
                <div className="rounded-lg bg-stone-50 px-3 py-2 text-xs text-stone-600">
                  关系推进：{item.relationship_progress.length > 0 ? item.relationship_progress.join('；') : '未指定'}
                </div>
                <div className="rounded-lg bg-stone-50 px-3 py-2 text-xs text-stone-600">
                  新揭示：{item.new_reveals.length > 0 ? item.new_reveals.join('；') : '未指定'}
                </div>
                <div className="rounded-lg bg-stone-50 px-3 py-2 text-xs text-stone-600">
                  状态变化：{item.status_shift.length > 0 ? item.status_shift.join('；') : '未指定'}
                </div>
              </div>
              {chapterIssues.length > 0 ? (
                <div className="space-y-2">
                  {chapterIssues.map((issue, issueIndex) => (
                    <div
                      key={`${issue.type}-${issueIndex}`}
                      className={`rounded-lg px-3 py-2 text-xs ${
                        issue.severity === 'fatal'
                          ? 'bg-rose-100 text-rose-700'
                          : 'bg-amber-100 text-amber-700'
                      }`}
                    >
                      {issue.message}
                    </div>
                  ))}
                </div>
              ) : null}
            </article>
          )})}
          {storyArcsToShow.length === 0 && (
            <div className="rounded-xl border border-dashed border-stone-300 px-4 py-6 text-sm text-stone-500">
              还没有阶段骨架。请先确认世界观和人物蓝图，再生成整书阶段结构。
            </div>
          )}
          {storyArcsToShow.length > 0 && visibleRoadmapChapters.length === 0 ? (
            <div className="rounded-xl border border-dashed border-stone-300 px-4 py-6 text-sm text-stone-500">
              请先展开某一幕的章节，再进入该阶段的章节细修。
            </div>
          ) : null}
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
