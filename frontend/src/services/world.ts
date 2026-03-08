/**
 * 世界设定相关 API（Canon & Staging）
 */
import { get, post } from './http'
import type { CanonData, StagingChange, StagingFilter } from '@/types'

/** 获取 Canon 数据 */
export function fetchCanon(bookId?: number): Promise<CanonData> {
  const query = bookId ? `?book_id=${bookId}` : ''
  return get<CanonData>(`/api/world/canon${query}`)
}

/** 获取 Staging 列表 */
export function fetchStaging(filter: StagingFilter = 'all', bookId?: number): Promise<StagingChange[]> {
  const params = new URLSearchParams()
  if (filter !== 'all') params.set('status', filter)
  if (bookId) params.set('book_id', String(bookId))
  const query = params.toString()
  return get<StagingChange[]>(`/api/world/staging${query ? `?${query}` : ''}`)
}

/** 审批通过 Staging 变更 */
export function approveStaging(id: number, comment?: string): Promise<StagingChange> {
  return post<StagingChange>(`/api/world/staging/${id}/approve`, { comment })
}

/** 拒绝 Staging 变更 */
export function rejectStaging(id: number, reason: string): Promise<StagingChange> {
  return post<StagingChange>(`/api/world/staging/${id}/reject`, { reason })
}
