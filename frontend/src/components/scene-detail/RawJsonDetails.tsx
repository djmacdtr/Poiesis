/**
 * 折叠式原始数据调试面板。
 */
interface RawJsonDetailsProps {
  title: string
  value: unknown
}

export function RawJsonDetails({ title, value }: RawJsonDetailsProps) {
  return (
    <details className="rounded-2xl border border-stone-200 bg-white p-4">
      <summary className="cursor-pointer text-sm font-semibold text-stone-700">{title}</summary>
      <pre className="mt-4 overflow-x-auto rounded-xl bg-stone-50 p-3 text-xs text-stone-700">
        {JSON.stringify(value, null, 2)}
      </pre>
    </details>
  )
}
