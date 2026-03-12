/**
 * 书籍相关 API
 */
import { get, post, request } from './http'
import type {
  BlueprintGenerateRequest,
  BlueprintReplanRequest,
  BookBlueprint,
  BookItem,
  BookUpsertRequest,
  ChapterRoadmapItem,
  CharacterBlueprint,
  ConceptVariant,
  ConceptVariantRegenerationResult,
  CreationIntent,
  RelationshipBlueprintEdge,
  RelationshipGraphResponse,
  RelationshipPendingItem,
  RelationshipReplanResponse,
  WorldBlueprint,
} from '@/types'

/** 获取书籍列表 */
export function fetchBooks(): Promise<BookItem[]> {
  return get<BookItem[]>('/api/books')
}

/** 创建书籍 */
export function createBook(payload: BookUpsertRequest): Promise<BookItem> {
  return post<BookItem>('/api/books', payload)
}

/** 更新书籍 */
export function updateBook(bookId: number, payload: BookUpsertRequest): Promise<BookItem> {
  return request<BookItem>(`/api/books/${bookId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

/** 读取整书蓝图 */
export function fetchBookBlueprint(bookId: number): Promise<BookBlueprint> {
  return get<BookBlueprint>(`/api/books/${bookId}/blueprint`)
}

/** 保存作者创作意图 */
export function saveCreationIntent(bookId: number, payload: CreationIntent): Promise<BookBlueprint> {
  return post<BookBlueprint>(`/api/books/${bookId}/creation-intent`, payload)
}

/** 生成候选方向 */
export function generateConceptVariants(bookId: number): Promise<BookBlueprint> {
  return post<BookBlueprint>(`/api/books/${bookId}/concept-variants:generate`, {})
}

/** 选择候选方向 */
export function selectConceptVariant(bookId: number, variantId: number): Promise<BookBlueprint> {
  return post<BookBlueprint>(`/api/books/${bookId}/concept-variants/${variantId}/select`, {})
}

/** 仅重生成单条候选方向 */
export function regenerateConceptVariant(
  bookId: number,
  variantId: number,
): Promise<ConceptVariantRegenerationResult> {
  return post<ConceptVariantRegenerationResult>(`/api/books/${bookId}/concept-variants/${variantId}:regenerate`, {})
}

/** 人工接受单版重生成提案 */
export function acceptRegeneratedConceptVariant(
  bookId: number,
  variantId: number,
  proposal: ConceptVariant,
): Promise<BookBlueprint> {
  return post<BookBlueprint>(`/api/books/${bookId}/concept-variants/${variantId}:accept-regenerated`, {
    proposal,
  })
}

/** 生成世界观蓝图 */
export function generateWorldBlueprint(bookId: number, payload: BlueprintGenerateRequest): Promise<BookBlueprint> {
  return post<BookBlueprint>(`/api/books/${bookId}/blueprint/world:generate`, payload)
}

/** 确认世界观蓝图 */
export function confirmWorldBlueprint(bookId: number, draft: WorldBlueprint | null): Promise<BookBlueprint> {
  return post<BookBlueprint>(`/api/books/${bookId}/blueprint/world:confirm`, { draft })
}

/** 生成人物蓝图 */
export function generateCharacterBlueprint(bookId: number, payload: BlueprintGenerateRequest): Promise<BookBlueprint> {
  return post<BookBlueprint>(`/api/books/${bookId}/blueprint/characters:generate`, payload)
}

/** 确认人物蓝图 */
export function confirmCharacterBlueprint(
  bookId: number,
  draft: CharacterBlueprint[],
  relationshipGraph: RelationshipBlueprintEdge[],
): Promise<BookBlueprint> {
  return post<BookBlueprint>(`/api/books/${bookId}/blueprint/characters:confirm`, {
    characters: draft,
    relationship_graph: relationshipGraph,
  })
}

/** 生成章节路线 */
export function generateRoadmap(bookId: number, payload: BlueprintGenerateRequest): Promise<BookBlueprint> {
  return post<BookBlueprint>(`/api/books/${bookId}/blueprint/roadmap:generate`, payload)
}

/** 只重生成某个阶段的章节路线 */
export function regenerateRoadmapStage(
  bookId: number,
  arcNumber: number,
  payload: BlueprintGenerateRequest,
): Promise<BookBlueprint> {
  return post<BookBlueprint>(`/api/books/${bookId}/blueprint/roadmap/stages/${arcNumber}:regenerate`, payload)
}

/** 确认章节路线 */
export function confirmRoadmap(bookId: number, draft: ChapterRoadmapItem[]): Promise<BookBlueprint> {
  return post<BookBlueprint>(`/api/books/${bookId}/blueprint/roadmap:confirm`, { draft })
}

/** 对未来章节重规划 */
export function replanBlueprint(bookId: number, payload: BlueprintReplanRequest): Promise<BookBlueprint> {
  return post<BookBlueprint>(`/api/books/${bookId}/blueprint/replan`, payload)
}

/** 读取关系图谱工作态 */
export function fetchRelationshipGraph(bookId: number): Promise<RelationshipGraphResponse> {
  return get<RelationshipGraphResponse>(`/api/books/${bookId}/relationship-graph`)
}

/** 确认关系图谱 */
export function confirmRelationshipGraph(
  bookId: number,
  edges: RelationshipBlueprintEdge[],
): Promise<BookBlueprint> {
  return post<BookBlueprint>(`/api/books/${bookId}/relationship-graph/confirm`, { edges })
}

/** 新增或编辑关系边 */
export function upsertRelationshipEdge(
  bookId: number,
  edge: RelationshipBlueprintEdge,
): Promise<RelationshipGraphResponse> {
  return post<RelationshipGraphResponse>(`/api/books/${bookId}/relationship-edges`, { edge })
}

/** 更新关系边 */
export function updateRelationshipEdge(
  bookId: number,
  edgeId: string,
  edge: RelationshipBlueprintEdge,
): Promise<RelationshipGraphResponse> {
  return request<RelationshipGraphResponse>(`/api/books/${bookId}/relationship-edges/${edgeId}`, {
    method: 'PUT',
    body: JSON.stringify({ edge }),
  })
}

/** 读取待确认人物/关系 */
export function fetchRelationshipPending(bookId: number): Promise<{ items: RelationshipPendingItem[] }> {
  return get<{ items: RelationshipPendingItem[] }>(`/api/books/${bookId}/relationship-pending`)
}

/** 确认待确认项 */
export function confirmRelationshipPending(bookId: number, itemId: number): Promise<RelationshipGraphResponse> {
  return post<RelationshipGraphResponse>(`/api/books/${bookId}/relationship-pending/${itemId}/confirm`, {})
}

/** 拒绝待确认项 */
export function rejectRelationshipPending(bookId: number, itemId: number): Promise<RelationshipGraphResponse> {
  return post<RelationshipGraphResponse>(`/api/books/${bookId}/relationship-pending/${itemId}/reject`, {})
}

/** 创建关系重规划请求 */
export function createRelationshipReplan(
  bookId: number,
  payload: { edge_id: string; reason: string; desired_change: string },
): Promise<RelationshipReplanResponse> {
  return post<RelationshipReplanResponse>(`/api/books/${bookId}/relationship-replan`, payload)
}

/** 读取关系重规划提案 */
export function fetchRelationshipReplan(
  bookId: number,
  requestId: number,
): Promise<RelationshipReplanResponse> {
  return get<RelationshipReplanResponse>(`/api/books/${bookId}/relationship-replan/${requestId}`)
}

/** 确认关系重规划提案 */
export function confirmRelationshipReplan(
  bookId: number,
  requestId: number,
  proposalId: string,
): Promise<RelationshipGraphResponse> {
  return post<RelationshipGraphResponse>(`/api/books/${bookId}/relationship-replan/${requestId}/confirm`, {
    proposal_id: proposalId,
  })
}
