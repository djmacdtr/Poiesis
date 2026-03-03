/**
 * 认证相关 API 服务
 */
import { request } from './http'

export interface UserInfo {
  id: number
  username: string
  role: string
  need_password_change?: boolean
}

/** 登录请求 */
export async function login(username: string, password: string): Promise<UserInfo> {
  return request<UserInfo>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

/** 登出 */
export async function logout(): Promise<void> {
  await request<void>('/api/auth/logout', {
    method: 'POST',
  })
}

/** 获取当前登录用户信息（用于初始化时检测 cookie 是否有效） */
export async function getMe(): Promise<UserInfo> {
  return request<UserInfo>('/api/auth/me', {
    method: 'GET',
  })
}

/** 修改密码 */
export async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
  await request<{ message: string }>('/api/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  })
}
