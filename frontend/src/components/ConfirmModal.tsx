/**
 * 统一确认弹窗组件：用于危险操作二次确认。
 */
import { AlertTriangle } from 'lucide-react'
import { ModalBase } from '@/components/ModalBase'

interface ConfirmModalProps {
  open: boolean
  title: string
  description: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
  loading?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmModal({
  open,
  title,
  description,
  confirmText = '确认',
  cancelText = '取消',
  danger = false,
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  if (!open) return null

  const accentBg = danger ? 'bg-red-50' : 'bg-amber-50'
  const accentText = danger ? 'text-red-500' : 'text-amber-500'
  const confirmClass = danger
    ? 'bg-red-600 hover:bg-red-700 text-white'
    : 'bg-amber-500 hover:bg-amber-600 text-white'

  return (
    <ModalBase open={open}>
      <div className="p-6 space-y-4">
        <div className="flex items-start gap-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${accentBg}`}>
            <AlertTriangle className={`w-5 h-5 ${accentText}`} />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-semibold text-gray-800">{title}</h3>
            <p className="text-sm text-gray-600 leading-relaxed">{description}</p>
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-1">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 text-sm text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-50 transition-colors"
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={`px-4 py-2 text-sm rounded-lg disabled:opacity-50 transition-colors ${confirmClass}`}
          >
            {loading ? '处理中…' : confirmText}
          </button>
        </div>
      </div>
    </ModalBase>
  )
}
