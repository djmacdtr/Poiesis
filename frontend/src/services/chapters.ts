/**
 * 章节相关 API
 */
import { get } from './http'
import type { Chapter, ChapterSummaryItem } from '@/types'

/** 获取章节列表 */
export function fetchChapters(): Promise<ChapterSummaryItem[]> {
  return get<ChapterSummaryItem[]>('/api/chapters')
}

/** 获取指定书籍的章节列表 */
export function fetchChaptersByBook(bookId: number): Promise<ChapterSummaryItem[]> {
  return get<ChapterSummaryItem[]>(`/api/chapters?book_id=${bookId}`)
}

/** 获取章节详情 */
export function fetchChapter(id: number, bookId: number = 1): Promise<Chapter> {
  return get<Chapter>(`/api/chapters/${id}?book_id=${bookId}`)
}
