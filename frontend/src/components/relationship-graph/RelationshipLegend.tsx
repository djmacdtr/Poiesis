/**
 * 关系图谱图例：固定视觉语义，帮助作者快速理解节点与边的颜色含义。
 */
export function RelationshipLegend() {
  return (
    <div className="rounded-xl border border-stone-200 bg-stone-50 p-3">
      <p className="text-xs font-medium text-stone-600">图谱图例</p>
      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <div className="space-y-2">
          <p className="text-xs font-medium text-stone-500">人物节点</p>
          <div className="flex flex-wrap gap-2 text-xs text-stone-600">
            <span className="rounded-full border border-indigo-400 bg-indigo-50 px-2 py-1">主角</span>
            <span className="rounded-full border border-stone-300 bg-white px-2 py-1">核心角色</span>
            <span className="rounded-full border border-dashed border-amber-400 bg-amber-50 px-2 py-1">待确认角色</span>
          </div>
        </div>
        <div className="space-y-2">
          <p className="text-xs font-medium text-stone-500">关系边</p>
          <div className="flex flex-wrap gap-2 text-xs text-stone-600">
            <span className="rounded-full bg-emerald-50 px-2 py-1 text-emerald-700">正向</span>
            <span className="rounded-full bg-rose-50 px-2 py-1 text-rose-700">负向</span>
            <span className="rounded-full bg-amber-50 px-2 py-1 text-amber-700">复杂</span>
            <span className="rounded-full bg-violet-50 px-2 py-1 text-violet-700">伪装</span>
            <span className="rounded-full bg-yellow-50 px-2 py-1 text-yellow-700">待确认</span>
            <span className="rounded-full bg-red-50 px-2 py-1 text-red-700">冲突</span>
          </div>
        </div>
      </div>
    </div>
  )
}
