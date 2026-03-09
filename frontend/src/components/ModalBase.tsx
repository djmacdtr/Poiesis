/**
 * 统一弹窗骨架组件：封装遮罩、容器与可访问性属性。
 */
import type { ReactNode } from 'react'

interface ModalBaseProps {
  open: boolean
  children: ReactNode
  maxWidthClass?: string
  ariaLabelledBy?: string
  ariaDescribedBy?: string
}

export function ModalBase({ open, children, maxWidthClass = 'max-w-md', ariaLabelledBy, ariaDescribedBy }: ModalBaseProps) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={ariaLabelledBy}
        aria-describedby={ariaDescribedBy}
        className={`relative w-full rounded-2xl border border-gray-100 bg-white shadow-xl ${maxWidthClass}`}
      >
        {children}
      </div>
    </div>
  )
}
