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
  CreationIntent,
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
export function regenerateConceptVariant(bookId: number, variantId: number): Promise<BookBlueprint> {
  return post<BookBlueprint>(`/api/books/${bookId}/concept-variants/${variantId}:regenerate`, {})
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
): Promise<BookBlueprint> {
  return post<BookBlueprint>(`/api/books/${bookId}/blueprint/characters:confirm`, { draft })
}

/** 生成章节路线 */
export function generateRoadmap(bookId: number, payload: BlueprintGenerateRequest): Promise<BookBlueprint> {
  return post<BookBlueprint>(`/api/books/${bookId}/blueprint/roadmap:generate`, payload)
}

/** 确认章节路线 */
export function confirmRoadmap(bookId: number, draft: ChapterRoadmapItem[]): Promise<BookBlueprint> {
  return post<BookBlueprint>(`/api/books/${bookId}/blueprint/roadmap:confirm`, { draft })
}

/** 对未来章节重规划 */
export function replanBlueprint(bookId: number, payload: BlueprintReplanRequest): Promise<BookBlueprint> {
  return post<BookBlueprint>(`/api/books/${bookId}/blueprint/replan`, payload)
}
