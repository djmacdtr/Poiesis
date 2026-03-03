/**
 * 认证上下文：提供全局用户状态与登录/登出操作
 */
import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import { getMe, login as apiLogin, logout as apiLogout, type UserInfo } from '@/services/auth'

interface AuthState {
  /** 当前登录用户，null 表示未登录，undefined 表示正在初始化 */
  user: UserInfo | null | undefined
  /** 是否需要修改密码（使用默认密码登录时为 true） */
  needPasswordChange: boolean
  /** 标记密码已修改完成（关闭弹窗用） */
  clearPasswordChangeFlag: () => void
  /** 登录操作 */
  login: (username: string, password: string) => Promise<void>
  /** 登出操作 */
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null | undefined>(undefined)
  const [needPasswordChange, setNeedPasswordChange] = useState(false)

  // 初始化：尝试从 Cookie 还原登录状态
  useEffect(() => {
    getMe()
      .then((u) => setUser(u))
      .catch(() => setUser(null))
  }, [])

  const login = async (username: string, password: string) => {
    const u = await apiLogin(username, password)
    setUser(u)
    if (u.need_password_change) {
      setNeedPasswordChange(true)
    }
  }

  const logout = async () => {
    await apiLogout()
    setUser(null)
    setNeedPasswordChange(false)
  }

  const clearPasswordChangeFlag = () => setNeedPasswordChange(false)

  return (
    <AuthContext.Provider value={{ user, needPasswordChange, clearPasswordChangeFlag, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

/** 获取认证上下文（必须在 AuthProvider 内使用） */
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth 必须在 AuthProvider 内使用')
  return ctx
}
