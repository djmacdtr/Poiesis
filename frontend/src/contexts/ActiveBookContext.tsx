/**
 * 当前作品上下文：
 * 统一维护“当前激活书籍”，避免工作台、设定页、章节页各自维护一套本地状态，
 * 导致左侧快捷切书后页面不联动的问题。
 */
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

const ACTIVE_BOOK_ID_KEY = 'poiesis.activeBookId'

interface ActiveBookContextValue {
  activeBookId: number
  setActiveBookId: (bookId: number) => void
}

const ActiveBookContext = createContext<ActiveBookContextValue | null>(null)

/**
 * 读取当前作品的初始值。
 * 这里故意只依赖 localStorage，不读取 query 参数：
 * 1. Context 是全局共享状态，不应该耦合某个具体页面的路由；
 * 2. 页面级 query 会在各自页面中解析后，再回写到这里，形成“页面解析 -> 全局共享”的单向流程。
 */
function readInitialActiveBookId(): number {
  if (typeof window === 'undefined') {
    return 1
  }
  const raw = window.localStorage.getItem(ACTIVE_BOOK_ID_KEY)
  const parsed = raw ? Number(raw) : NaN
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1
}

export function ActiveBookProvider({ children }: { children: ReactNode }) {
  const [activeBookId, setActiveBookId] = useState<number>(readInitialActiveBookId)

  useEffect(() => {
    /**
     * 当前作品一旦变更，就立刻写回 localStorage。
     * 这样章节总览、设定总览、工作台、作品库即使分别刷新，也会尽量落到同一本书上。
     */
    if (typeof window === 'undefined') {
      return
    }
    window.localStorage.setItem(ACTIVE_BOOK_ID_KEY, String(activeBookId))
  }, [activeBookId])

  const value = useMemo(
    () => ({
      activeBookId,
      setActiveBookId,
    }),
    [activeBookId],
  )

  return <ActiveBookContext.Provider value={value}>{children}</ActiveBookContext.Provider>
}

export function useActiveBook() {
  const context = useContext(ActiveBookContext)
  if (!context) {
    throw new Error('useActiveBook 必须在 ActiveBookProvider 内使用')
  }
  return context
}

/**
 * 解析“当前作品”的最终有效值。
 * 这里统一处理三个现实问题：
 * 1. localStorage 或 query 里残留了已经不存在的书籍 id；
 * 2. 刚创建或删除作品后，页面还持有旧 id；
 * 3. 初次进入时还没有明确指定当前书，需要回退到默认作品或第一本作品。
 */
export function resolveActiveBookId(
  candidateId: number,
  books: Array<{ id: number; is_default: boolean }>,
): number {
  if (books.some((item) => item.id === candidateId)) {
    return candidateId
  }
  return books.find((item) => item.is_default)?.id ?? books[0]?.id ?? 1
}
