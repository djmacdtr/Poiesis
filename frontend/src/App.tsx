/**
 * 应用路由配置（含认证守卫）
 */
import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AppShell } from '@/components/AppShell'
import { ActiveBookProvider } from '@/contexts/ActiveBookContext'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'

const Dashboard = lazy(() => import('@/pages/Dashboard'))
const WorkspacePage = lazy(() => import('@/pages/Workspace'))
const RunBoard = lazy(() => import('@/pages/RunBoard'))
const SceneRunDetail = lazy(() => import('@/pages/SceneRunDetail'))
const ReviewQueue = lazy(() => import('@/pages/ReviewQueue'))
const LoopBoard = lazy(() => import('@/pages/LoopBoard'))
const Chapters = lazy(() => import('@/pages/Chapters'))
const ChapterDetail = lazy(() => import('@/pages/ChapterDetail'))
const Canon = lazy(() => import('@/pages/Canon'))
const Settings = lazy(() => import('@/pages/Settings'))
const Books = lazy(() => import('@/pages/Books'))
const LoginPage = lazy(() => import('@/pages/Login'))

function RouteFallback() {
  return (
    <div className="min-h-[240px] flex items-center justify-center rounded-xl border border-gray-200 bg-white text-sm text-gray-500">
      页面加载中…
    </div>
  )
}

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
    <Suspense fallback={<RouteFallback />}>
      {/* 页面级懒加载优先压缩首屏主包，尤其是图表和后台管理页。 */}
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
          <Route index element={<Navigate to="/workspace" replace />} />
          <Route path="workspace" element={<WorkspacePage />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="runs" element={<RunBoard />} />
          <Route path="runs/:runId" element={<SceneRunDetail />} />
          <Route path="reviews" element={<ReviewQueue />} />
          <Route path="loops" element={<LoopBoard />} />
          <Route path="chapters" element={<Chapters />} />
          <Route path="chapters/:id" element={<ChapterDetail />} />
          <Route path="canon" element={<Canon />} />
          <Route path="books" element={<Books />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </Suspense>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ActiveBookProvider>
          <AppRoutes />
        </ActiveBookProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
