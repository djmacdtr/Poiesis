/**
 * 世界设定相关 API
 */
import { get } from './http'
import type { CanonData } from '@/types'

/** 获取 Canon 数据 */
export function fetchCanon(bookId?: number): Promise<CanonData> {
  const query = bookId ? `?book_id=${bookId}` : ''
  return get<CanonData>(`/api/canon${query}`)
}
