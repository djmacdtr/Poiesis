/**
 * 书籍相关 API
 */
import { get, post, request } from './http'
import type { BookItem, BookUpsertRequest } from '@/types'

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
