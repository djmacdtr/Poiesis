/**
 * 应用外壳：左侧导航栏 + 顶部标题栏 + 内容区
 */
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Play,
  BookOpen,
  Globe,
  GitPullRequest,
  Orbit,
  Settings,
  LogOut,
  User,
  PanelsTopLeft,
  FolderKanban,
  FolderOpenDot,
} from 'lucide-react'
import { PoiesisLogo } from '@/components/PoiesisLogo'
import { formatLanguageLabel, formatStylePresetLabel } from '@/lib/display-labels'
import { cn } from '@/lib/utils'
import { useActiveBook, resolveActiveBookId } from '@/contexts/ActiveBookContext'
import { useAuth } from '@/contexts/AuthContext'
import { ChangePasswordModal } from '@/components/ChangePasswordModal'
import { fetchBooks } from '@/services/books'
import type { BookItem } from '@/types'
import { toast } from 'sonner'

interface NavItem {
  to: string
  label: string
  icon: typeof PanelsTopLeft
}

interface NavGroup {
  title: string
  items: NavItem[]
}

/** 分组后的导航更贴合当前产品阶段：主流程是蓝图工作台，其他页面是辅助资产与执行中心。 */
const navGroups: NavGroup[] = [
  {
    title: '创作主流程',
    items: [{ to: '/workspace', label: '创作工作台', icon: PanelsTopLeft }],
  },
  {
    title: '正文资产',
    items: [
      { to: '/chapters', label: '章节总览', icon: BookOpen },
      { to: '/canon', label: '设定总览', icon: Globe },
      { to: '/loops', label: '线索面板', icon: Orbit },
    ],
  },
  {
    title: '执行中心',
    items: [
      { to: '/runs', label: '运行面板', icon: Play },
      { to: '/reviews', label: '审阅队列', icon: GitPullRequest },
    ],
  },
  {
    title: '作品与系统',
    items: [
      { to: '/books', label: '作品库', icon: FolderKanban },
      { to: '/settings', label: '系统设置', icon: Settings },
    ],
  },
]

function formatBookLabel(book: BookItem): string {
  return `${book.name}（${formatLanguageLabel(book.language)} / ${formatStylePresetLabel(book.style_preset)}${book.is_default ? ' / 默认' : ''}）`
}

/**
 * 顶部标题只负责表达“当前所处页面类别”，不承担步骤状态展示。
 * 更细的工作流状态放到工作台内部，避免 AppShell 被蓝图业务细节污染。
 */
function derivePageTitle(pathname: string): string {
  if (pathname.startsWith('/workspace')) return 'AI 小说创作工作台'
  if (pathname.startsWith('/chapters')) return '章节总览'
  if (pathname.startsWith('/canon')) return '设定总览'
  if (pathname.startsWith('/loops')) return '线索面板'
  if (pathname.startsWith('/runs')) return '运行面板'
  if (pathname.startsWith('/reviews')) return '审阅队列'
  if (pathname.startsWith('/books')) return '作品库'
  if (pathname.startsWith('/settings')) return '系统设置'
  if (pathname.startsWith('/dashboard')) return '统计总览'
  return 'Poiesis 控制台'
}

export function AppShell() {
  const { user, logout, needPasswordChange } = useAuth()
  const { activeBookId, setActiveBookId } = useActiveBook()
  const navigate = useNavigate()
  const location = useLocation()

  const { data: books = [] } = useQuery<BookItem[]>({
    queryKey: ['books'],
    queryFn: fetchBooks,
    staleTime: 30_000,
  })

  /**
   * AppShell 只负责消费“当前作品”，不负责决定 query 优先级。
   * 这里统一读取全局 context，再用书籍列表做一次兜底解析，避免渲染不存在的作品 id。
   */
  const resolvedBookId = resolveActiveBookId(activeBookId, books)
  const activeBook = useMemo(
    () => books.find((item) => item.id === resolvedBookId) ?? null,
    [books, resolvedBookId],
  )
  const pageTitle = derivePageTitle(location.pathname)

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
      <aside className="w-72 shrink-0 border-r border-stone-200 bg-[#fbfaf8] flex flex-col">
        {/* 品牌区只保留 logo 与品牌名，不再堆放说明文字，避免左栏顶部信息过重。 */}
        <div className="border-b border-stone-200 px-6 py-5">
          <div className="flex items-center gap-3">
            {/*
              这里复用登录页的品牌 Logo，让导航入口与登录入口使用同一套视觉锚点。
              用户进入控制台后，左栏顶部应该先识别品牌，而不是继续阅读解释性段落。
            */}
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-emerald-100 bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.18),_rgba(255,255,255,0.95)_65%)] text-emerald-700 shadow-sm">
              <PoiesisLogo size={38} />
            </div>
            <div className="min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold text-emerald-700">Poiesis</span>
                <span className="text-sm text-stone-400">创作台</span>
              </div>
              <div className="mt-2 flex items-center gap-2 text-[11px] font-medium tracking-[0.18em] text-stone-400">
                <span className="h-px w-5 bg-stone-300" />
                蓝图工作台
              </div>
            </div>
          </div>
        </div>

        <div className="border-b border-stone-200 px-6 py-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-stone-400">当前作品</p>
          <select
            value={resolvedBookId}
            onChange={(event) => setActiveBookId(Number(event.target.value))}
            className="mt-3 w-full rounded-xl border border-stone-300 bg-white px-3 py-2.5 text-sm text-stone-700"
          >
            {books.map((book) => (
              <option key={book.id} value={book.id}>
                {formatBookLabel(book)}
              </option>
            ))}
          </select>
          {activeBook ? (
            <div className="mt-3 rounded-2xl border border-stone-200 bg-white px-3 py-3">
              <div className="flex items-center gap-2 text-sm font-medium text-stone-800">
                <FolderOpenDot className="h-4 w-4 text-emerald-600" />
                {activeBook.name}
              </div>
              <p className="mt-1 text-xs leading-5 text-stone-500">
                语言：{formatLanguageLabel(activeBook.language)} · 文风：{formatStylePresetLabel(activeBook.style_preset)}
              </p>
            </div>
          ) : null}
        </div>

        {/* 菜单列表 */}
        <nav className="flex-1 overflow-y-auto px-4 py-4">
          <div className="space-y-6">
            {navGroups.map((group) => (
              <section key={group.title}>
                <p className="px-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-stone-400">
                  {group.title}
                </p>
                <ul className="mt-2 space-y-1">
                  {group.items.map((item) => (
                    <li key={item.to}>
                      <NavLink
                        to={item.to}
                        className={({ isActive }) =>
                          cn(
                            'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors',
                            isActive
                              ? 'bg-emerald-50 text-emerald-800 shadow-sm'
                              : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900',
                          )
                        }
                      >
                        <item.icon className="h-4 w-4 shrink-0" />
                        {item.label}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        </nav>

        {/* 底部版本信息 */}
        <div className="border-t border-stone-200 p-4 text-center text-xs text-stone-400">
          Poiesis v0.1.0 · 工作台重构中
        </div>
      </aside>

      {/* 右侧主区域 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 顶部栏 */}
        <header className="h-16 shrink-0 bg-white border-b border-stone-200 flex items-center justify-between px-6">
          <div>
            <h1 className="text-base font-semibold text-stone-800">{pageTitle}</h1>
            <p className="mt-0.5 text-xs text-stone-500">
              {activeBook ? `当前作品：${activeBook.name}` : '尚未选择作品'}
            </p>
          </div>

          {/* 用户信息与退出按钮 */}
          {user && (
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5 text-sm text-stone-600">
                <User className="w-4 h-4 text-stone-400" />
                <span>{user.username}</span>
                {user.role === 'admin' && (
                  <span className="text-xs px-1.5 py-0.5 bg-emerald-50 text-emerald-700 rounded">
                    管理员
                  </span>
                )}
              </div>
              <button
                onClick={handleLogout}
                className="flex items-center gap-1.5 text-sm text-stone-500 hover:text-red-600 transition-colors px-2 py-1 rounded hover:bg-red-50"
                title="退出登录"
              >
                <LogOut className="w-4 h-4" />
                退出
              </button>
            </div>
          )}
        </header>

        {/* 页面内容 */}
        <main className="flex-1 overflow-y-auto bg-stone-50 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
