/**
 * 场景变更面板：分类展示提取出的结构化变化。
 */
import type { SceneChangeSet } from '@/types'
import { buildChangeSections } from '@/lib/scene-detail'

interface SceneChangeSetPanelProps {
  changeset: SceneChangeSet
}

function renderItem(item: Record<string, unknown>): string {
  const preferredKeys = ['title', 'name', 'loop_id', 'event_key', 'rule_key', 'description', 'claim']
  for (const key of preferredKeys) {
    const value = item[key]
    if (typeof value === 'string' && value.trim()) return value
  }
  return JSON.stringify(item, null, 2)
}

export function SceneChangeSetPanel({ changeset }: SceneChangeSetPanelProps) {
  const sections = buildChangeSections(changeset)

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-stone-700">当前变更摘要</h3>
      <div className="mt-4 space-y-4">
        {sections.map((section) => (
          <div key={section.key} className="rounded-xl border border-stone-200 p-3">
            <p className="text-xs font-medium text-stone-500">{section.title}</p>
            {section.items.length > 0 ? (
              <ul className="mt-2 space-y-2">
                {section.items.map((item, index) => (
                  <li key={`${section.key}-${index}`} className="rounded-lg bg-stone-50 px-3 py-2 text-sm text-stone-700">
                    {renderItem(item)}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-stone-400">{section.emptyText}</p>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}
