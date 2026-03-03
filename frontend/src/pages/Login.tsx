/**
 * 登录页面 — 文艺风设计
 * 左侧：水墨意境插画 + 品牌故事
 * 右侧：简洁登录表单
 */
import { useState, type FormEvent } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'

/** Poiesis 品牌 SVG 图标（钢笔 + 羽毛 + 书卷） */
function PoiesisLogo({ size = 64 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Poiesis Logo"
    >
      {/* 外圆 */}
      <circle cx="32" cy="32" r="30" stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.3" />
      {/* 内圆 */}
      <circle cx="32" cy="32" r="22" stroke="currentColor" strokeWidth="1" strokeOpacity="0.15" />

      {/* 羽毛笔主干 */}
      <path
        d="M20 46 Q28 30 44 18"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      {/* 笔尖 */}
      <path
        d="M44 18 L41 23 L46 21 Z"
        fill="currentColor"
        fillOpacity="0.8"
      />
      {/* 羽毛纹理线条 */}
      <path d="M28 38 Q34 28 42 20" stroke="currentColor" strokeWidth="0.8" strokeOpacity="0.4" strokeLinecap="round" />
      <path d="M25 41 Q32 30 41 21" stroke="currentColor" strokeWidth="0.6" strokeOpacity="0.25" strokeLinecap="round" />
      <path d="M31 35 Q36 26 43 19" stroke="currentColor" strokeWidth="0.6" strokeOpacity="0.25" strokeLinecap="round" />

      {/* 书卷底部装饰 */}
      <path
        d="M16 48 Q22 44 28 46 Q34 48 40 44 Q46 40 48 44"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeOpacity="0.5"
      />
      {/* 墨滴 */}
      <circle cx="20" cy="46" r="2" fill="currentColor" fillOpacity="0.6" />
    </svg>
  )
}

/** 左侧背景装饰：水墨意境 SVG */
function InkBackground() {
  return (
    <svg
      className="absolute inset-0 w-full h-full"
      viewBox="0 0 400 600"
      preserveAspectRatio="xMidYMid slice"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* 远山（淡） */}
      <path
        d="M0 320 Q60 200 120 260 Q180 320 240 180 Q300 40 360 120 Q400 160 400 120 L400 600 L0 600 Z"
        fill="white"
        fillOpacity="0.04"
      />
      {/* 近山 */}
      <path
        d="M0 400 Q80 300 160 360 Q240 420 320 280 Q360 210 400 260 L400 600 L0 600 Z"
        fill="white"
        fillOpacity="0.06"
      />
      {/* 竹叶群 1 */}
      <g transform="translate(60, 120)" opacity="0.18">
        <line x1="0" y1="80" x2="0" y2="0" stroke="white" strokeWidth="2" strokeLinecap="round" />
        <path d="M0 20 Q-20 5 -35 10" stroke="white" strokeWidth="1.5" strokeLinecap="round" fill="none" />
        <path d="M0 30 Q20 12 38 18" stroke="white" strokeWidth="1.5" strokeLinecap="round" fill="none" />
        <path d="M0 45 Q-22 28 -40 35" stroke="white" strokeWidth="1.5" strokeLinecap="round" fill="none" />
        <path d="M0 55 Q18 38 35 42" stroke="white" strokeWidth="1.5" strokeLinecap="round" fill="none" />
      </g>
      {/* 竹叶群 2 */}
      <g transform="translate(330, 80)" opacity="0.14">
        <line x1="0" y1="100" x2="0" y2="0" stroke="white" strokeWidth="2" strokeLinecap="round" />
        <path d="M0 15 Q-18 2 -30 8" stroke="white" strokeWidth="1.5" strokeLinecap="round" fill="none" />
        <path d="M0 28 Q16 10 30 16" stroke="white" strokeWidth="1.5" strokeLinecap="round" fill="none" />
        <path d="M0 42 Q-20 26 -36 30" stroke="white" strokeWidth="1.5" strokeLinecap="round" fill="none" />
        <path d="M0 56 Q17 38 32 44" stroke="white" strokeWidth="1.5" strokeLinecap="round" fill="none" />
        <path d="M0 68 Q-15 52 -28 56" stroke="white" strokeWidth="1.5" strokeLinecap="round" fill="none" />
      </g>
      {/* 飘落的书页 */}
      <g opacity="0.1">
        <path d="M120 200 Q130 190 145 195 Q140 210 125 208 Z" fill="white" />
        <path d="M280 150 Q292 140 308 145 Q303 162 288 158 Z" fill="white" />
        <path d="M200 350 Q212 338 228 344 Q222 362 207 356 Z" fill="white" />
      </g>
      {/* 水波纹（底部） */}
      <g transform="translate(0, 500)" opacity="0.08">
        <path d="M0 30 Q50 10 100 30 Q150 50 200 30 Q250 10 300 30 Q350 50 400 30" stroke="white" strokeWidth="1.5" fill="none" />
        <path d="M0 50 Q50 30 100 50 Q150 70 200 50 Q250 30 300 50 Q350 70 400 50" stroke="white" strokeWidth="1" fill="none" />
      </g>
    </svg>
  )
}

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const from = (location.state as { from?: string } | null)?.from ?? '/'

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(username, password)
      navigate(from, { replace: true })
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* ── 左侧：品牌区域 ── */}
      <div
        className="hidden lg:flex lg:w-[52%] relative flex-col items-center justify-center px-12 overflow-hidden"
        style={{
          background: 'linear-gradient(145deg, #1a1a2e 0%, #16213e 40%, #0f3460 70%, #1a1a3e 100%)',
        }}
      >
        <InkBackground />

        {/* 内容层 */}
        <div className="relative z-10 text-center text-white space-y-8 max-w-sm">
          {/* Logo 图标 */}
          <div className="flex justify-center">
            <div className="text-amber-300">
              <PoiesisLogo size={80} />
            </div>
          </div>

          {/* 品牌名 */}
          <div>
            <h1
              className="text-5xl font-light tracking-[0.3em] text-white"
              style={{ fontFamily: "'Georgia', 'Palatino Linotype', serif", letterSpacing: '0.35em' }}
            >
              POIESIS
            </h1>
            <div className="mt-2 flex items-center justify-center gap-3">
              <div className="h-px w-12 bg-amber-300/40" />
              <span className="text-xs tracking-widest text-amber-200/70 uppercase">自主叙事引擎</span>
              <div className="h-px w-12 bg-amber-300/40" />
            </div>
          </div>

          {/* 引言 */}
          <blockquote className="space-y-2">
            <p
              className="text-base text-white/75 leading-relaxed italic"
              style={{ fontFamily: "'Georgia', serif" }}
            >
              "文字是时间的镜子，<br/>
              每一章，都是世界的呼吸。"
            </p>
            <footer className="text-xs text-white/40 tracking-wider">— Poiesis 创作引擎</footer>
          </blockquote>

          {/* 特性标签 */}
          <div className="flex flex-wrap justify-center gap-2">
            {['世界模型', '跨章连续', '自主生成', '可审批修订'].map((tag) => (
              <span
                key={tag}
                className="text-xs px-3 py-1 rounded-full border border-white/15 text-white/50 backdrop-blur-sm"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>

        {/* 底部版权 */}
        <div className="absolute bottom-6 text-xs text-white/25 tracking-wider z-10">
          Poiesis v0.1.0 · 自主长篇叙事生成引擎
        </div>
      </div>

      {/* ── 右侧：登录表单区域 ── */}
      <div className="flex-1 flex items-center justify-center bg-stone-50 px-6 py-12">
        <div className="w-full max-w-sm space-y-8">

          {/* 移动端 Logo（仅在小屏显示） */}
          <div className="lg:hidden text-center space-y-3">
            <div className="flex justify-center text-indigo-900">
              <PoiesisLogo size={56} />
            </div>
            <h1
              className="text-3xl font-light tracking-[0.3em] text-indigo-900"
              style={{ fontFamily: "'Georgia', serif" }}
            >
              POIESIS
            </h1>
          </div>

          {/* 标题 */}
          <div className="space-y-1">
            <h2 className="text-2xl font-light text-gray-800" style={{ fontFamily: "'Georgia', serif" }}>
              欢迎回来
            </h2>
            <p className="text-sm text-gray-400">请登录以进入创作控制台</p>
          </div>

          {/* 错误提示 */}
          {error && (
            <div className="flex items-start gap-2.5 bg-red-50 border border-red-100 text-red-600 text-sm rounded-xl px-4 py-3">
              <span className="mt-0.5 shrink-0">✕</span>
              <span>{error}</span>
            </div>
          )}

          {/* 登录表单 */}
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* 用户名 */}
            <div className="space-y-1.5">
              <label
                className="block text-xs font-medium text-gray-500 tracking-wide uppercase"
                htmlFor="username"
              >
                用户名
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoComplete="username"
                placeholder="请输入用户名"
                className="w-full bg-white border border-gray-200 rounded-xl px-4 py-3 text-sm text-gray-800 placeholder-gray-300 focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 transition-all"
              />
            </div>

            {/* 密码 */}
            <div className="space-y-1.5">
              <label
                className="block text-xs font-medium text-gray-500 tracking-wide uppercase"
                htmlFor="password"
              >
                密码
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPwd ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  placeholder="请输入密码"
                  className="w-full bg-white border border-gray-200 rounded-xl px-4 py-3 pr-11 text-sm text-gray-800 placeholder-gray-300 focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPwd((v) => !v)}
                  tabIndex={-1}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-300 hover:text-gray-500 transition-colors"
                  aria-label={showPwd ? '隐藏密码' : '显示密码'}
                >
                  {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* 提交按钮 */}
            <button
              type="submit"
              disabled={loading}
              className="w-full relative py-3 rounded-xl text-sm font-medium text-white transition-all disabled:opacity-60"
              style={{
                background: loading
                  ? '#6366f1'
                  : 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
                boxShadow: loading ? 'none' : '0 4px 20px rgba(79,70,229,0.35)',
              }}
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  登录中…
                </span>
              ) : (
                '进入控制台'
              )}
            </button>
          </form>

          {/* 底部提示 */}
          <p className="text-xs text-center text-gray-300">
            默认账号 <span className="font-mono text-gray-400">admin / admin</span>，首次登录后请修改密码
          </p>
        </div>
      </div>
    </div>
  )
}

