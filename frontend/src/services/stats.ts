/**
 * 统计数据服务（基于已有 API 数据本地聚合计算）
 */
import { fetchChaptersByBook } from './chapters'
import { fetchStaging, fetchCanon } from './world'
import type { DashboardStats, WordCountDataPoint } from '@/types'

/** 聚合仪表盘统计数据 */
export async function fetchDashboardStats(bookId: number = 1): Promise<DashboardStats> {
  const [chapters, pending, canon] = await Promise.all([
    fetchChaptersByBook(bookId),
    fetchStaging('pending', bookId),
    fetchCanon(bookId),
  ])

  return {
    totalChapters: chapters.length,
    completedChapters: chapters.filter((c) => c.status === 'completed' || c.status === 'published').length,
    totalWords: chapters.reduce((sum, c) => sum + c.word_count, 0),
    pendingStagingCount: pending.length,
    characterCount: canon.characters.length,
    activeForeshadowingCount: canon.foreshadowing.filter((f) => f.status === 'active').length,
  }
}

/** 生成字数趋势数据（按章节排序） */
export async function fetchWordCountTrend(bookId: number = 1): Promise<WordCountDataPoint[]> {
  const chapters = await fetchChaptersByBook(bookId)
  return chapters
    .slice()
    .sort((a, b) => a.chapter_number - b.chapter_number)
    .map((c) => ({ chapter: c.chapter_number, words: c.word_count }))
}
