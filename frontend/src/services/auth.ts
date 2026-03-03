/**
 * 认证相关 API 服务
 */
import { request } from './http'

export interface UserInfo {
  id: number
  username: string
  role: string
}

/** 登录请求 */
export async function login(username: string, password: string): Promise<UserInfo> {
  return request<UserInfo>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
    credentials: 'include',
  })
}

/** 登出 */
export async function logout(): Promise<void> {
  await request<void>('/api/auth/logout', {
    method: 'POST',
    credentials: 'include',
  })
}

/** 获取当前登录用户信息（用于初始化时检测 cookie 是否有效） */
export async function getMe(): Promise<UserInfo> {
  return request<UserInfo>('/api/auth/me', {
    method: 'GET',
    credentials: 'include',
  })
}
