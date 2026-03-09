/**
 * Scene 工作台相关 API
 */
import { get, post } from './http'
import type {
  ChapterDetailResponse,
  LoopState,
  ReviewQueueItem,
  RunResponse,
  SceneDetailResponse,
  SceneRunDetail,
  SceneRunSummary,
} from '@/types'

/** 启动新的 scene 驱动 run */
export function startSceneRun(chapterCount: number, bookId: number = 1): Promise<RunResponse> {
  return post<RunResponse>('/api/runs', { chapter_count: chapterCount, book_id: bookId })
}

/** 获取 scene 驱动 run 列表 */
export function fetchSceneRuns(): Promise<SceneRunSummary[]> {
  return get<SceneRunSummary[]>('/api/runs')
}

/** 获取单个 run 详情 */
export function fetchSceneRunDetail(runId: number): Promise<SceneRunDetail> {
  return get<SceneRunDetail>(`/api/runs/${runId}`)
}

/** 获取章节详情 */
export function fetchSceneChapterDetail(runId: number, chapterNumber: number): Promise<ChapterDetailResponse> {
  return get<ChapterDetailResponse>(`/api/runs/${runId}/chapters/${chapterNumber}`)
}

/** 获取 scene 详情 */
export function fetchSceneDetail(
  runId: number,
  chapterNumber: number,
  sceneNumber: number,
): Promise<SceneDetailResponse> {
  return get<SceneDetailResponse>(`/api/runs/${runId}/chapters/${chapterNumber}/scenes/${sceneNumber}`)
}

/** 获取 review 队列 */
export function fetchReviewQueue(bookId: number = 1): Promise<{ items: ReviewQueueItem[] }> {
  return get<{ items: ReviewQueueItem[] }>(`/api/reviews?book_id=${bookId}`)
}

/** 批准 review */
export function approveReview(reviewId: number): Promise<ReviewQueueItem> {
  return post<ReviewQueueItem>(`/api/reviews/${reviewId}/approve`, {})
}

/** 标记 retry */
export function retryReview(reviewId: number): Promise<ReviewQueueItem> {
  return post<ReviewQueueItem>(`/api/reviews/${reviewId}/retry`, {})
}

/** 提交 patch */
export function patchReview(reviewId: number, patchText: string): Promise<ReviewQueueItem> {
  return post<ReviewQueueItem>(`/api/reviews/${reviewId}/patch`, { patch_text: patchText })
}

/** 获取 loop board */
export function fetchLoops(bookId: number = 1): Promise<{ items: LoopState[] }> {
  return get<{ items: LoopState[] }>(`/api/loops?book_id=${bookId}`)
}
