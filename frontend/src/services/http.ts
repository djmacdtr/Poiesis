/**
 * HTTP 基础封装
 * baseURL 来自环境变量 VITE_API_BASE_URL
 */

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''

/** 通用请求函数，自动处理 JSON 序列化与错误提示 */
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = BASE_URL ? `${BASE_URL}${path}` : path
  const res = await fetch(url, {
    credentials: 'include',  // 携带 HttpOnly Cookie
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })

  if (!res.ok) {
    let message = `请求失败：${res.status} ${res.statusText}`
    try {
      const body = await res.json() as { detail?: string; message?: string }
      message = body.detail ?? body.message ?? message
    } catch {
      // 忽略 JSON 解析错误
    }
    throw new Error(message)
  }

  // 204 No Content
  if (res.status === 204) {
    return undefined as T
  }

  return res.json() as Promise<T>
}

/** GET 请求 */
export function get<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'GET' })
}

/** POST 请求 */
export function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
}
