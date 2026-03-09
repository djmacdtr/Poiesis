/**
 * 运行任务相关 API
 */
import { get, post, request } from './http'
import type { RunResponse, TaskDetail } from '@/types'

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''

export interface PruneTaskHistoryResponse {
  removed: number
  remaining: number
}

/** 启动写作任务 */
export function startRun(chapterCount: number, bookId: number = 1): Promise<RunResponse> {
  return post<RunResponse>('/api/run', { chapter_count: chapterCount, book_id: bookId })
}

/** 查询任务状态（轮询用） */
export function fetchTaskStatus(taskId: string): Promise<TaskDetail> {
  return get<TaskDetail>(`/api/run/${taskId}`)
}

/** 查询任务列表（最近更新在前） */
export function fetchTaskList(): Promise<TaskDetail[]> {
  return get<TaskDetail[]>('/api/run')
}

/** 清理任务历史，保留最近 keep 条 */
export function pruneTaskHistory(keep: number): Promise<PruneTaskHistoryResponse> {
  return request<PruneTaskHistoryResponse>(`/api/run/history?keep=${keep}`, {
    method: 'DELETE',
  })
}

/** 订阅任务 SSE 事件流（日志 + 预览文本） */
export function createTaskEventSource(taskId: string): EventSource {
  const path = `/api/run/${taskId}/events`
  const url = BASE_URL ? `${BASE_URL}${path}` : path
  return new EventSource(url, { withCredentials: true })
}
