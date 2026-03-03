/**
 * 应用路由配置（含认证守卫）
 */
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AppShell } from '@/components/AppShell'
import Dashboard from '@/pages/Dashboard'
import Run from '@/pages/Run'
import Chapters from '@/pages/Chapters'
import ChapterDetail from '@/pages/ChapterDetail'
import Canon from '@/pages/Canon'
import Staging from '@/pages/Staging'
import Stats from '@/pages/Stats'
import Settings from '@/pages/Settings'
import LoginPage from '@/pages/Login'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'

/** 需要登录的路由守卫：未登录时跳转 /login */
function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  const location = useLocation()

  // 初始化中（user === undefined）：显示加载中，等待检测 Cookie
  if (user === undefined) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <span className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }

  return <>{children}</>
}

function AppRoutes() {
  return (
    <Routes>
      {/* 登录页：不需要认证 */}
      <Route path="/login" element={<LoginPage />} />

      {/* 受保护页面：需要登录 */}
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="run" element={<Run />} />
        <Route path="chapters" element={<Chapters />} />
        <Route path="chapters/:id" element={<ChapterDetail />} />
        <Route path="canon" element={<Canon />} />
        <Route path="staging" element={<Staging />} />
        <Route path="stats" element={<Stats />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
