/**
 * 场景规划卡片。
 */
import type { ScenePlan } from '@/types'

interface ScenePlanCardProps {
  plan: ScenePlan
}

function PlanField({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-stone-50 p-3">
      <p className="text-xs font-medium text-stone-500">{label}</p>
      <p className="mt-1 text-sm leading-6 text-stone-700">{value || '—'}</p>
    </div>
  )
}

export function ScenePlanCard({ plan }: ScenePlanCardProps) {
  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-stone-700">场景规划</h3>
        <span className="text-xs text-stone-400">场景 {plan.scene_number}</span>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <PlanField label="标题" value={plan.title} />
        <PlanField label="目标" value={plan.goal} />
        <PlanField label="冲突" value={plan.conflict} />
        <PlanField label="转折" value={plan.turning_point} />
        <PlanField label="地点" value={plan.location} />
        <PlanField label="视角角色" value={plan.pov_character} />
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-xl bg-stone-50 p-3">
          <p className="text-xs font-medium text-stone-500">要求推进的剧情线索</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {plan.required_loops.length > 0 ? (
              plan.required_loops.map((item) => (
                <span key={item} className="rounded-full bg-white px-2 py-1 text-xs text-stone-600">
                  {item}
                </span>
              ))
            ) : (
              <span className="text-xs text-stone-400">没有指定剧情线索</span>
            )}
          </div>
        </div>
        <div className="rounded-xl bg-stone-50 p-3">
          <p className="text-xs font-medium text-stone-500">连续性要求</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {plan.continuity_requirements.length > 0 ? (
              plan.continuity_requirements.map((item) => (
                <span key={item} className="rounded-full bg-white px-2 py-1 text-xs text-stone-600">
                  {item}
                </span>
              ))
            ) : (
              <span className="text-xs text-stone-400">没有指定连续性要求</span>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
