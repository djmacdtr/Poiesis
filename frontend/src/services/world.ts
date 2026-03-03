/**
 * 世界设定相关 API（Canon & Staging）
 */
import { get, post } from './http'
import type { CanonData, StagingChange, StagingFilter } from '@/types'

/** 获取 Canon 数据 */
export function fetchCanon(): Promise<CanonData> {
  return get<CanonData>('/api/world/canon')
}

/** 获取 Staging 列表 */
export function fetchStaging(filter: StagingFilter = 'all'): Promise<StagingChange[]> {
  const query = filter === 'all' ? '' : `?status=${filter}`
  return get<StagingChange[]>(`/api/world/staging${query}`)
}

/** 审批通过 Staging 变更 */
export function approveStaging(id: number, comment?: string): Promise<StagingChange> {
  return post<StagingChange>(`/api/world/staging/${id}/approve`, { comment })
}

/** 拒绝 Staging 变更 */
export function rejectStaging(id: number, reason: string): Promise<StagingChange> {
  return post<StagingChange>(`/api/world/staging/${id}/reject`, { reason })
}
