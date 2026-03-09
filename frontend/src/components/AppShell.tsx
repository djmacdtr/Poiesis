/**
 * 应用外壳：左侧导航栏 + 顶部标题栏 + 内容区
 */
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  Play,
  BookOpen,
  Globe,
  GitPullRequest,
  Orbit,
  BookMarked,
  Settings,
  LogOut,
  User,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'
import { ChangePasswordModal } from '@/components/ChangePasswordModal'
import { toast } from 'sonner'

/** 导航菜单项定义 */
const navItems = [
  { to: '/', label: '仪表盘', icon: LayoutDashboard, end: true },
  { to: '/runs', label: 'Run Board', icon: Play, end: false },
  { to: '/reviews', label: 'Review Queue', icon: GitPullRequest, end: false },
  { to: '/loops', label: 'Loop Board', icon: Orbit, end: false },
  { to: '/chapters', label: '章节列表', icon: BookOpen, end: false },
  { to: '/canon', label: 'Canon Explorer', icon: Globe, end: false },
  { to: '/books', label: '书籍管理', icon: BookMarked, end: false },
  { to: '/settings', label: '系统设置', icon: Settings, end: false },
]

export function AppShell() {
  const { user, logout, needPasswordChange } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    try {
      await logout()
      navigate('/login', { replace: true })
    } catch {
      toast.error('退出登录失败，请重试')
    }
  }

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900">
      {/* 首次登录修改密码弹窗 */}
      {needPasswordChange && <ChangePasswordModal />}

      {/* 左侧导航 */}
      <aside className="w-56 shrink-0 bg-white border-r border-gray-200 flex flex-col">
        {/* Logo / 品牌 */}
        <div className="h-16 flex items-center px-6 border-b border-gray-200">
          <span className="text-xl font-bold text-indigo-600">Poiesis</span>
          <span className="ml-2 text-sm text-gray-400">控制台</span>
        </div>

        {/* 菜单列表 */}
        <nav className="flex-1 py-4 overflow-y-auto">
          <ul className="space-y-1 px-3">
            {navItems.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-indigo-50 text-indigo-700'
                        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900',
                    )
                  }
                >
                  <item.icon className="w-4 h-4 shrink-0" />
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        {/* 底部版本信息 */}
        <div className="p-4 border-t border-gray-200 text-xs text-gray-400 text-center">
          Poiesis v0.1.0
        </div>
      </aside>

      {/* 右侧主区域 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 顶部栏 */}
        <header className="h-16 shrink-0 bg-white border-b border-gray-200 flex items-center justify-between px-6">
          <h1 className="text-base font-semibold text-gray-700">AI 小说 Scene 工作台</h1>

          {/* 用户信息与退出按钮 */}
          {user && (
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5 text-sm text-gray-600">
                <User className="w-4 h-4 text-gray-400" />
                <span>{user.username}</span>
                {user.role === 'admin' && (
                  <span className="text-xs px-1.5 py-0.5 bg-indigo-50 text-indigo-600 rounded">
                    管理员
                  </span>
                )}
              </div>
              <button
                onClick={handleLogout}
                className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-red-600 transition-colors px-2 py-1 rounded hover:bg-red-50"
                title="退出登录"
              >
                <LogOut className="w-4 h-4" />
                退出
              </button>
            </div>
          )}
        </header>

        {/* 页面内容 */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
