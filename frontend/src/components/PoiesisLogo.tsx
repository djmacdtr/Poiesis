/**
 * Poiesis 品牌 Logo。
 * 这套 SVG 原本只存在于登录页，本次抽到共享组件后，
 * 左侧导航、登录页以及后续可能出现的品牌位都可以复用同一套图形语言。
 */
interface PoiesisLogoProps {
  size?: number
  className?: string
}

export function PoiesisLogo({ size = 64, className = '' }: PoiesisLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Poiesis Logo"
      className={className}
    >
      <circle cx="32" cy="32" r="30" stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.3" />
      <circle cx="32" cy="32" r="22" stroke="currentColor" strokeWidth="1" strokeOpacity="0.15" />

      <path
        d="M20 46 Q28 30 44 18"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path d="M44 18 L41 23 L46 21 Z" fill="currentColor" fillOpacity="0.8" />

      <path
        d="M28 38 Q34 28 42 20"
        stroke="currentColor"
        strokeWidth="0.8"
        strokeOpacity="0.4"
        strokeLinecap="round"
      />
      <path
        d="M25 41 Q32 30 41 21"
        stroke="currentColor"
        strokeWidth="0.6"
        strokeOpacity="0.25"
        strokeLinecap="round"
      />
      <path
        d="M31 35 Q36 26 43 19"
        stroke="currentColor"
        strokeWidth="0.6"
        strokeOpacity="0.25"
        strokeLinecap="round"
      />

      <path
        d="M16 48 Q22 44 28 46 Q34 48 40 44 Q46 40 48 44"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeOpacity="0.5"
      />
      <circle cx="20" cy="46" r="2" fill="currentColor" fillOpacity="0.6" />
    </svg>
  )
}

