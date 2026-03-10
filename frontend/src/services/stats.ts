/**
 * 统计数据服务（围绕新 scene 工作台聚合）
 */
import { fetchChaptersByBook } from './chapters'
import { fetchReviewQueue, fetchLoops } from './run'
import { fetchCanon } from './world'
import type { DashboardStats, WordCountDataPoint } from '@/types'

/** 聚合仪表盘统计数据 */
export async function fetchDashboardStats(bookId: number = 1): Promise<DashboardStats> {
  const [chapters, reviews, loops, canon] = await Promise.all([
    fetchChaptersByBook(bookId),
    fetchReviewQueue(bookId),
    fetchLoops(bookId),
    fetchCanon(bookId),
  ])

  return {
    totalChapters: chapters.length,
    completedChapters: chapters.filter((c) => c.status === 'ready_to_publish' || c.status === 'published').length,
    totalWords: chapters.reduce((sum, c) => sum + c.word_count, 0),
    pendingReviewCount: reviews.items.filter((item) => item.status === 'pending').length,
    characterCount: canon.characters.length,
    activeLoopCount: loops.items.filter((item) => item.status !== 'resolved' && item.status !== 'dropped').length,
    readyToPublishCount: chapters.filter((c) => c.status === 'ready_to_publish').length,
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
