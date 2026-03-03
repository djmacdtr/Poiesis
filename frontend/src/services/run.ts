/**
 * 运行任务相关 API
 */
import { get, post } from './http'
import type { RunResponse, TaskDetail } from '@/types'

/** 启动写作任务 */
export function startRun(chapterCount: number): Promise<RunResponse> {
  return post<RunResponse>('/api/run', { chapter_count: chapterCount })
}

/** 查询任务状态（轮询用） */
export function fetchTaskStatus(taskId: string): Promise<TaskDetail> {
  return get<TaskDetail>(`/api/run/${taskId}`)
}
