/**
 * 修改密码弹窗：首次使用默认密码登录后弹出，提示修改
 */
import { useState, type FormEvent } from 'react'
import { KeyRound, X, Eye, EyeOff } from 'lucide-react'
import { changePassword } from '@/services/auth'
import { useAuth } from '@/contexts/AuthContext'
import { ModalBase } from '@/components/ModalBase'
import { toast } from 'sonner'

export function ChangePasswordModal() {
  const { clearPasswordChangeFlag } = useAuth()

  const [oldPwd, setOldPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [confirmPwd, setConfirmPwd] = useState('')
  const [showNew, setShowNew] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)

    if (newPwd.length < 6) {
      setError('新密码长度不得少于 6 位')
      return
    }
    if (newPwd !== confirmPwd) {
      setError('两次输入的密码不一致')
      return
    }
    if (newPwd === oldPwd) {
      setError('新密码不能与当前密码相同')
      return
    }

    setLoading(true)
    try {
      await changePassword(oldPwd, newPwd)
      toast.success('密码修改成功，请妥善保管')
      clearPasswordChangeFlag()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const handleSkip = () => {
    clearPasswordChangeFlag()
    toast.warning('建议尽快修改默认密码以确保安全')
  }

  return (
    <ModalBase open maxWidthClass="max-w-md">
      <div aria-labelledby="change-pwd-title" className="overflow-hidden">
        {/* 顶部装饰带 */}
        <div className="h-1.5 bg-gradient-to-r from-amber-400 via-orange-400 to-rose-400" />

        <div className="p-7 space-y-5">
          {/* 标题区 */}
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center">
                <KeyRound className="w-5 h-5 text-amber-500" />
            </div>
              <div>
                <h2 id="change-pwd-title" className="text-base font-semibold text-gray-800">请修改初始密码</h2>
                <p className="text-xs text-gray-500 mt-0.5">检测到您正在使用默认密码，为安全起见请立即更改</p>
              </div>
            </div>
            <button
              onClick={handleSkip}
              className="text-gray-400 hover:text-gray-600 transition-colors p-1"
              title="稍后再说"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* 错误提示 */}
          {error && (
            <div className="bg-red-50 border border-red-100 text-red-600 text-sm rounded-lg px-4 py-2.5">
              {error}
            </div>
          )}

          {/* 表单 */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="cp-old">
                当前密码
              </label>
              <input
                id="cp-old"
                type="password"
                value={oldPwd}
                onChange={(e) => setOldPwd(e.target.value)}
                required
                autoComplete="current-password"
                placeholder="输入当前密码"
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-300 bg-gray-50"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="cp-new">
                新密码
                <span className="ml-1 font-normal text-gray-400">（至少 6 位）</span>
              </label>
              <div className="relative">
                <input
                  id="cp-new"
                  type={showNew ? 'text' : 'password'}
                  value={newPwd}
                  onChange={(e) => setNewPwd(e.target.value)}
                  required
                  autoComplete="new-password"
                  placeholder="设置新密码"
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 pr-9 text-sm focus:outline-none focus:ring-2 focus:ring-amber-300 bg-gray-50"
                />
                <button
                  type="button"
                  onClick={() => setShowNew((v) => !v)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  tabIndex={-1}
                >
                  {showNew ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1" htmlFor="cp-confirm">
                确认新密码
              </label>
              <input
                id="cp-confirm"
                type="password"
                value={confirmPwd}
                onChange={(e) => setConfirmPwd(e.target.value)}
                required
                autoComplete="new-password"
                placeholder="再次输入新密码"
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-300 bg-gray-50"
              />
            </div>

            <div className="flex gap-3 pt-1">
              <button
                type="submit"
                disabled={loading}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium rounded-lg disabled:opacity-50 transition-colors"
              >
                {loading ? (
                  <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                ) : (
                  <KeyRound className="w-4 h-4" />
                )}
                {loading ? '修改中…' : '确认修改'}
              </button>
              <button
                type="button"
                onClick={handleSkip}
                className="px-4 py-2.5 text-sm text-gray-500 hover:text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
              >
                稍后再说
              </button>
            </div>
          </form>
        </div>
      </div>
    </ModalBase>
  )
}
