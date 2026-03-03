/**
 * 加载中占位组件
 */
export function LoadingSpinner({ text = '加载中…' }: { text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-gray-400 gap-3">
      <div className="w-8 h-8 border-2 border-indigo-300 border-t-indigo-600 rounded-full animate-spin" />
      <span className="text-sm">{text}</span>
    </div>
  )
}

/**
 * 错误提示组件
 */
export function ErrorMessage({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      ⚠️ {message}
    </div>
  )
}

/**
 * 空状态组件
 */
export function EmptyState({ text = '暂无数据' }: { text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-gray-400 gap-2">
      <span className="text-4xl">📭</span>
      <span className="text-sm">{text}</span>
    </div>
  )
}
