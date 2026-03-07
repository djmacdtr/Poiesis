/**
 * 统一输入确认弹窗：用于需要填写原因的危险操作。
 */
import { AlertTriangle } from 'lucide-react'
import { ModalBase } from '@/components/ModalBase'

interface PromptModalProps {
  open: boolean
  title: string
  description: string
  value: string
  placeholder?: string
  confirmText?: string
  cancelText?: string
  loading?: boolean
  onChange: (value: string) => void
  onConfirm: () => void
  onCancel: () => void
}

export function PromptModal({
  open,
  title,
  description,
  value,
  placeholder = '请输入内容',
  confirmText = '确认',
  cancelText = '取消',
  loading = false,
  onChange,
  onConfirm,
  onCancel,
}: PromptModalProps) {
  return (
    <ModalBase open={open}>
      <div className="p-6 space-y-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-red-50 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-red-500" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-semibold text-gray-800">{title}</h3>
            <p className="text-sm text-gray-600 leading-relaxed">{description}</p>
          </div>
        </div>

        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          rows={3}
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400 resize-none"
        />

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
            className="px-4 py-2 text-sm rounded-lg text-white bg-red-600 hover:bg-red-700 disabled:opacity-50 transition-colors"
          >
            {loading ? '处理中…' : confirmText}
          </button>
        </div>
      </div>
    </ModalBase>
  )
}
