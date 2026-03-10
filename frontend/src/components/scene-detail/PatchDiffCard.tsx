/**
 * patch 历史与修补前后对照卡片。
 */
import type { ScenePatchRecord } from '@/types'
import { summarizePatchResult } from '@/lib/scene-detail'
import { formatDateTime } from '@/lib/utils'
import { StatusPill } from './StatusPill'

interface PatchDiffCardProps {
  patches: ScenePatchRecord[]
}

export function PatchDiffCard({ patches }: PatchDiffCardProps) {
  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-stone-700">修补历史</h3>
      {patches.length === 0 ? (
        <p className="mt-4 text-sm text-stone-400">当前场景还没有修补记录。</p>
      ) : (
        <div className="mt-4 space-y-4">
          {patches.map((patch) => (
            <article key={patch.id} className="rounded-xl border border-stone-200 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-stone-800">修补记录 #{patch.id}</p>
                  <p className="mt-1 text-xs text-stone-400">{formatDateTime(patch.created_at)}</p>
                </div>
                <StatusPill
                  label={patch.applied_successfully ? '修补通过' : '仍需处理'}
                  tone={patch.applied_successfully ? 'success' : 'warning'}
                />
              </div>

              <div className="mt-4 rounded-xl bg-stone-50 p-3">
                <p className="text-xs font-medium text-stone-500">修补要求</p>
                <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-stone-700">{patch.patch_text}</p>
              </div>

              <div className="mt-4 grid gap-3 lg:grid-cols-2">
                <div className="rounded-xl bg-stone-50 p-3">
                  <p className="text-xs font-medium text-stone-500">修补前文本</p>
                  <div className="mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap text-sm leading-6 text-stone-700">
                    {patch.before_text || '—'}
                  </div>
                </div>
                <div className="rounded-xl bg-stone-50 p-3">
                  <p className="text-xs font-medium text-stone-500">修补后文本</p>
                  <div className="mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap text-sm leading-6 text-stone-700">
                    {patch.after_text || '—'}
                  </div>
                </div>
              </div>

              <div className="mt-4 rounded-xl bg-stone-50 p-3">
                <p className="text-xs font-medium text-stone-500">校验结果</p>
                <p className="mt-1 text-sm text-stone-700">{summarizePatchResult(patch)}</p>
                {patch.verifier_issues.length > 0 && (
                  <ul className="mt-2 space-y-1 text-xs text-stone-600">
                    {patch.verifier_issues.map((issue, index) => (
                      <li key={`${patch.id}-${index}`}>- {issue.reason}</li>
                    ))}
                  </ul>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
