/**
 * 场景文本卡片，展示正文和可选的初稿版本。
 */
interface SceneTextCardProps {
  title: string
  text: string
  draftText?: string | null
}

export function SceneTextCard({ title, text, draftText }: SceneTextCardProps) {
  const hasDraft = draftText && draftText.trim() && draftText.trim() !== text.trim()

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-stone-700">{title}</h3>
      <div className="mt-4 max-h-72 overflow-y-auto whitespace-pre-wrap rounded-xl bg-stone-50 p-3 text-sm leading-7 text-stone-700">
        {text || '暂无正文'}
      </div>
      {hasDraft && (
        <details className="mt-4 rounded-xl border border-stone-200 bg-stone-50 p-3">
          <summary className="cursor-pointer text-xs font-medium text-stone-600">查看初稿版本</summary>
          <div className="mt-3 whitespace-pre-wrap text-sm leading-7 text-stone-600">{draftText}</div>
        </details>
      )}
    </section>
  )
}
