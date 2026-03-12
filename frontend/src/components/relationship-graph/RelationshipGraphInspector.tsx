/**
 * 图谱详情侧栏：选中人物或关系边时，展示当前焦点的结构化信息与跳转动作。
 */
import type { ReactNode } from 'react'
import type {
  RelationshipGraphEdgeViewModel,
  RelationshipGraphNodeViewModel,
  RelationshipGraphSelection,
} from '@/types'

interface RelationshipGraphInspectorProps {
  nodes: RelationshipGraphNodeViewModel[]
  edges: RelationshipGraphEdgeViewModel[]
  selection: RelationshipGraphSelection
  onJumpToNodeForm?: (nodeId: string) => void
  onJumpToEdgeForm?: (edgeId: string) => void
  onJumpToPending?: () => void
  onJumpToConflict?: () => void
}

export function RelationshipGraphInspector({
  nodes,
  edges,
  selection,
  onJumpToNodeForm,
  onJumpToEdgeForm,
  onJumpToPending,
  onJumpToConflict,
}: RelationshipGraphInspectorProps) {
  const selectedNode = selection?.kind === 'node' ? nodes.find((item) => item.id === selection.id) ?? null : null
  const selectedEdge = selection?.kind === 'edge' ? edges.find((item) => item.id === selection.id) ?? null : null

  return (
    <aside className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
      <h5 className="text-sm font-semibold text-stone-800">图谱详情</h5>
      {!selectedNode && !selectedEdge ? (
        <div className="mt-4 rounded-xl border border-dashed border-stone-300 px-4 py-6 text-sm text-stone-500">
          点击图谱中的人物节点或关系边，这里会展示详细说明，并联动到对应的编辑区域。
        </div>
      ) : null}

      {selectedNode ? (
        <div className="mt-4 space-y-3">
          <div>
            <p className="text-lg font-semibold text-stone-900">{selectedNode.name}</p>
            <p className="mt-1 text-sm text-stone-500">{selectedNode.role || '未标注定位'}</p>
          </div>
          <DetailRow label="公开人格" value={selectedNode.public_persona || '未填写'} />
          <DetailRow label="核心动机" value={selectedNode.core_motivation || '未填写'} />
          <DetailRow label="致命缺口" value={selectedNode.fatal_flaw || '未填写'} />
          <DetailRow label="关联角色数" value={String(selectedNode.related_count)} />
          <div className="flex flex-wrap gap-2 text-xs">
            {selectedNode.is_protagonist ? (
              <span className="rounded-full bg-indigo-50 px-2 py-1 text-indigo-700">主角</span>
            ) : null}
            {selectedNode.is_pending ? (
              <span className="rounded-full bg-amber-50 px-2 py-1 text-amber-700">待确认</span>
            ) : null}
          </div>
          {onJumpToNodeForm ? (
            <button
              type="button"
              onClick={() => onJumpToNodeForm(selectedNode.id)}
              className="rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-700 hover:bg-stone-50"
            >
              跳转到人物表单
            </button>
          ) : null}
        </div>
      ) : null}

      {selectedEdge ? (
        <div className="mt-4 space-y-3">
          <div>
            <p className="text-lg font-semibold text-stone-900">{selectedEdge.relation_type}</p>
            <p className="mt-1 text-sm text-stone-500">
              {selectedEdge.source_name} → {selectedEdge.target_name}
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <Tag>{selectedEdge.polarity}</Tag>
            <Tag>{selectedEdge.visibility}</Tag>
            <Tag>{selectedEdge.stability}</Tag>
            <Tag>强度 {selectedEdge.intensity}</Tag>
            {selectedEdge.is_pending ? <Tag tone="amber">待确认</Tag> : null}
            {selectedEdge.is_conflict ? <Tag tone="red">冲突</Tag> : null}
            {selectedEdge.has_replan ? <Tag tone="violet">已有重规划提案</Tag> : null}
          </div>
          <DetailRow label="关系摘要" value={selectedEdge.summary || '未填写'} multiline />
          <DetailRow label="隐藏真相" value={selectedEdge.hidden_truth || '未填写'} multiline />
          <DetailRow
            label="改写限制"
            value={selectedEdge.non_breakable_without_reveal ? '需要先经过揭示事件' : '可直接调整'}
          />
          <div className="flex flex-wrap gap-2">
            {onJumpToEdgeForm ? (
              <button
                type="button"
                onClick={() => onJumpToEdgeForm(selectedEdge.id)}
                className="rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-700 hover:bg-stone-50"
              >
                跳转到关系表单
              </button>
            ) : null}
            {selectedEdge.is_pending && onJumpToPending ? (
              <button
                type="button"
                onClick={onJumpToPending}
                className="rounded-lg border border-amber-300 px-3 py-2 text-sm text-amber-700 hover:bg-amber-50"
              >
                跳转到待确认队列
              </button>
            ) : null}
            {selectedEdge.is_conflict && onJumpToConflict ? (
              <button
                type="button"
                onClick={onJumpToConflict}
                className="rounded-lg border border-red-300 px-3 py-2 text-sm text-red-700 hover:bg-red-50"
              >
                查看冲突与重规划
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
    </aside>
  )
}

function DetailRow({
  label,
  value,
  multiline = false,
}: {
  label: string
  value: string
  multiline?: boolean
}) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium text-stone-500">{label}</p>
      <p className={multiline ? 'text-sm leading-6 text-stone-700' : 'text-sm text-stone-700'}>{value}</p>
    </div>
  )
}

function Tag({
  children,
  tone = 'stone',
}: {
  children: ReactNode
  tone?: 'stone' | 'amber' | 'red' | 'violet'
}) {
  const toneClass =
    tone === 'amber'
      ? 'bg-amber-50 text-amber-700'
      : tone === 'red'
        ? 'bg-red-50 text-red-700'
        : tone === 'violet'
          ? 'bg-violet-50 text-violet-700'
          : 'bg-stone-100 text-stone-700'
  return <span className={`rounded-full px-2 py-1 ${toneClass}`}>{children}</span>
}
