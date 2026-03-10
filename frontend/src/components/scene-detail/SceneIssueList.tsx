/**
 * 场景问题列表：按严重级别分组展示。
 */
import type { SceneIssue } from '@/types'
import { groupIssues, issueSeverityTone } from '@/lib/scene-detail'

interface SceneIssueListProps {
  issues: SceneIssue[]
}

export function SceneIssueList({ issues }: SceneIssueListProps) {
  const groups = groupIssues(issues)

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-stone-700">当前校验问题</h3>
      {groups.length === 0 ? (
        <p className="mt-4 text-sm text-emerald-700">当前场景没有校验问题，可以直接进入后续流程。</p>
      ) : (
        <div className="mt-4 space-y-4">
          {groups.map((group) => (
            <div key={group.severity}>
              <p className="text-xs font-medium text-stone-500">{group.label}</p>
              <div className="mt-2 space-y-2">
                {group.items.map((issue, index) => (
                  <div
                    key={`${issue.type}-${index}`}
                    className={`rounded-xl border p-3 ${issueSeverityTone[group.severity]}`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-medium">{issue.reason}</p>
                      <span className="text-xs opacity-80">{issue.type}</span>
                    </div>
                    {(issue.repair_hint || issue.location) && (
                      <div className="mt-2 space-y-1 text-xs">
                        {issue.repair_hint && <p>修复建议：{issue.repair_hint}</p>}
                        {issue.location && <p>位置：{issue.location}</p>}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
