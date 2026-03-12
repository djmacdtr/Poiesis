/**
 * 图谱全屏编辑侧栏：在全屏模式下直接编辑当前选中的人物或关系边。
 */
import type { CharacterBlueprint, CharacterNode, RelationshipBlueprintEdge, RelationshipConflictReport } from '@/types'

interface RelationshipGraphWorkspaceEditorProps {
  selectedCharacter: CharacterBlueprint | null
  selectedEdge: RelationshipBlueprintEdge | null
  relationshipNodes: CharacterNode[]
  relationshipConflict: RelationshipConflictReport | null
  onCharacterChange: (patch: Partial<CharacterBlueprint>) => void
  onCommitCharacter: () => void
  onEdgeChange: (patch: Partial<RelationshipBlueprintEdge>) => void
  onSaveEdge: () => void
  onDeleteEdge: () => void
  isCharacterEditing: boolean
  isCharacterDirty: boolean
  onStartCharacterEdit: () => void
  onCancelCharacterEdit: () => void
  isEditing: boolean
  isDirty: boolean
  onStartEdit: () => void
  onCancelEdit: () => void
  onJumpToPending?: () => void
  onJumpToConflict?: () => void
  isSavingEdge?: boolean
}

export function RelationshipGraphWorkspaceEditor({
  selectedCharacter,
  selectedEdge,
  relationshipNodes,
  relationshipConflict,
  onCharacterChange,
  onCommitCharacter,
  onEdgeChange,
  onSaveEdge,
  onDeleteEdge,
  isCharacterEditing,
  isCharacterDirty,
  onStartCharacterEdit,
  onCancelCharacterEdit,
  isEditing,
  isDirty,
  onStartEdit,
  onCancelEdit,
  onJumpToPending,
  onJumpToConflict,
  isSavingEdge = false,
}: RelationshipGraphWorkspaceEditorProps) {
  return (
    <aside className="h-full overflow-y-auto rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
      <h5 className="text-sm font-semibold text-stone-800">全屏编辑面板</h5>
      {!selectedCharacter && !selectedEdge ? (
        <div className="mt-4 rounded-xl border border-dashed border-stone-300 px-4 py-6 text-sm text-stone-500">
          点击左侧图谱中的人物节点或关系边，这里会直接显示可编辑表单。
        </div>
      ) : null}

      {selectedCharacter ? (
        <div className="mt-4 space-y-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-lg font-semibold text-stone-900">编辑人物</p>
              <p className="mt-1 text-sm text-stone-500">当前人物：{selectedCharacter.name || '未命名角色'}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              {isCharacterEditing ? (
                <span className="rounded-full bg-amber-100 px-2 py-1 text-amber-700">编辑中</span>
              ) : (
                <span className="rounded-full bg-emerald-100 px-2 py-1 text-emerald-700">草稿已保存</span>
              )}
            </div>
          </div>
          <p className="rounded-xl bg-stone-50 px-3 py-2 text-xs text-stone-600">
            这里保存的是当前人物草稿，仍需点击“确认人物蓝图”后才会正式生效。
          </p>
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-stone-500">姓名</label>
              <input
                value={selectedCharacter.name}
                onChange={(e) => onCharacterChange({ name: e.target.value })}
                disabled={!isCharacterEditing}
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm disabled:bg-stone-50 disabled:text-stone-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-stone-500">定位</label>
              <input
                value={selectedCharacter.role}
                onChange={(e) => onCharacterChange({ role: e.target.value })}
                disabled={!isCharacterEditing}
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm disabled:bg-stone-50 disabled:text-stone-500"
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-stone-500">公开人格</label>
            <textarea
              value={selectedCharacter.public_persona}
              onChange={(e) => onCharacterChange({ public_persona: e.target.value })}
              rows={3}
              disabled={!isCharacterEditing}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm disabled:bg-stone-50 disabled:text-stone-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-stone-500">核心动机</label>
            <input
              value={selectedCharacter.core_motivation}
              onChange={(e) => onCharacterChange({ core_motivation: e.target.value })}
              disabled={!isCharacterEditing}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm disabled:bg-stone-50 disabled:text-stone-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-stone-500">致命缺口</label>
            <input
              value={selectedCharacter.fatal_flaw}
              onChange={(e) => onCharacterChange({ fatal_flaw: e.target.value })}
              disabled={!isCharacterEditing}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm disabled:bg-stone-50 disabled:text-stone-500"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            {!isCharacterEditing ? (
              <button
                type="button"
                onClick={onStartCharacterEdit}
                className="rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-700 hover:bg-stone-50"
              >
                编辑
              </button>
            ) : null}
            {isCharacterEditing ? (
              <button
                type="button"
                onClick={onCommitCharacter}
                disabled={!isCharacterDirty}
                className="rounded-lg bg-stone-800 px-3 py-2 text-sm text-white hover:bg-stone-900 disabled:opacity-50"
              >
                {isCharacterDirty ? '完成编辑' : '已保存到草稿'}
              </button>
            ) : null}
            {isCharacterEditing ? (
              <button
                type="button"
                onClick={onCancelCharacterEdit}
                className="rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-600 hover:bg-stone-50"
              >
                取消
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {selectedEdge ? (
        <div className="mt-4 space-y-3">
          <div className="flex items-start justify-between gap-3">
            <div>
            <p className="text-lg font-semibold text-stone-900">编辑关系边</p>
            <p className="mt-1 text-sm text-stone-500">
              {selectedEdge.source_character_id} → {selectedEdge.target_character_id}
            </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              {relationshipConflict?.edge_id === selectedEdge.edge_id ? (
                <span className="rounded-full bg-red-100 px-2 py-1 text-red-700">冲突待处理</span>
              ) : isEditing ? (
                <span className="rounded-full bg-amber-100 px-2 py-1 text-amber-700">编辑中</span>
              ) : (
                <span className="rounded-full bg-emerald-100 px-2 py-1 text-emerald-700">已保存</span>
              )}
            </div>
          </div>

          {relationshipConflict?.edge_id === selectedEdge.edge_id ? (
            <div className="rounded-xl border border-red-200 bg-red-50/70 p-3 text-sm text-red-800">
              <p className="font-medium">当前关系修改已命中已发布事实冲突</p>
              <p className="mt-1">{relationshipConflict.conflict_summary}</p>
              {onJumpToConflict ? (
                <button
                  type="button"
                  onClick={onJumpToConflict}
                  className="mt-3 rounded-lg border border-red-300 px-3 py-2 text-sm text-red-700 hover:bg-red-100"
                >
                  查看冲突与重规划
                </button>
              ) : null}
            </div>
          ) : null}

          <div className="grid gap-2 md:grid-cols-2">
            <select
              value={selectedEdge.source_character_id}
              onChange={(e) => onEdgeChange({ source_character_id: e.target.value })}
              disabled={!isEditing}
              className="rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white disabled:bg-stone-50 disabled:text-stone-500"
            >
              {relationshipNodes.map((node) => (
                <option key={node.character_id} value={node.character_id}>
                  {node.name}
                </option>
              ))}
            </select>
            <select
              value={selectedEdge.target_character_id}
              onChange={(e) => onEdgeChange({ target_character_id: e.target.value })}
              disabled={!isEditing}
              className="rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white disabled:bg-stone-50 disabled:text-stone-500"
            >
              {relationshipNodes.map((node) => (
                <option key={node.character_id} value={node.character_id}>
                  {node.name}
                </option>
              ))}
            </select>
          </div>

          <input
            value={selectedEdge.relation_type}
            onChange={(e) => onEdgeChange({ relation_type: e.target.value })}
            disabled={!isEditing}
            className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm disabled:bg-stone-50 disabled:text-stone-500"
            placeholder="关系类型"
          />

          <div className="grid gap-2 md:grid-cols-4">
            <select
              value={selectedEdge.polarity}
              onChange={(e) => onEdgeChange({ polarity: e.target.value as RelationshipBlueprintEdge['polarity'] })}
              disabled={!isEditing}
              className="rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white disabled:bg-stone-50 disabled:text-stone-500"
            >
              <option value="正向">正向</option>
              <option value="负向">负向</option>
              <option value="复杂">复杂</option>
              <option value="伪装">伪装</option>
            </select>
            <select
              value={selectedEdge.visibility}
              onChange={(e) => onEdgeChange({ visibility: e.target.value as RelationshipBlueprintEdge['visibility'] })}
              disabled={!isEditing}
              className="rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white disabled:bg-stone-50 disabled:text-stone-500"
            >
              <option value="公开">公开</option>
              <option value="半公开">半公开</option>
              <option value="隐藏">隐藏</option>
              <option value="误导性表象">误导性表象</option>
            </select>
            <select
              value={selectedEdge.stability}
              onChange={(e) => onEdgeChange({ stability: e.target.value as RelationshipBlueprintEdge['stability'] })}
              disabled={!isEditing}
              className="rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white disabled:bg-stone-50 disabled:text-stone-500"
            >
              <option value="稳定">稳定</option>
              <option value="脆弱">脆弱</option>
              <option value="正在转变">正在转变</option>
            </select>
            <input
              value={String(selectedEdge.intensity)}
              onChange={(e) => onEdgeChange({ intensity: parseIntensity(e.target.value) })}
              disabled={!isEditing}
              className="rounded-lg border border-stone-300 px-3 py-2 text-sm disabled:bg-stone-50 disabled:text-stone-500"
              placeholder="强度 1-5"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-stone-500">关系摘要</label>
            <textarea
              value={selectedEdge.summary}
              onChange={(e) => onEdgeChange({ summary: e.target.value })}
              rows={3}
              disabled={!isEditing}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm disabled:bg-stone-50 disabled:text-stone-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-stone-500">隐藏真相 / 关系底牌</label>
            <textarea
              value={selectedEdge.hidden_truth}
              onChange={(e) => onEdgeChange({ hidden_truth: e.target.value })}
              rows={3}
              disabled={!isEditing}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm disabled:bg-stone-50 disabled:text-stone-500"
            />
          </div>
          <label className="flex items-center gap-2 text-xs text-stone-600">
            <input
              type="checkbox"
              checked={selectedEdge.non_breakable_without_reveal}
              disabled={!isEditing}
              onChange={(e) => onEdgeChange({ non_breakable_without_reveal: e.target.checked })}
            />
            必须通过“揭示事件”才能合法改写
          </label>

          <div className="flex flex-wrap gap-2">
            {!isEditing ? (
              <button
                type="button"
                onClick={onStartEdit}
                className="rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-700 hover:bg-stone-50"
              >
                编辑
              </button>
            ) : null}
            {isEditing ? (
              <button
                type="button"
                onClick={onSaveEdge}
                disabled={isSavingEdge || !isDirty}
                className="rounded-lg bg-stone-800 px-3 py-2 text-sm text-white hover:bg-stone-900 disabled:opacity-50"
              >
                {isSavingEdge ? '保存中…' : isDirty ? '保存这条关系' : '已保存'}
              </button>
            ) : null}
            {isEditing ? (
              <button
                type="button"
                onClick={onCancelEdit}
                className="rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-600 hover:bg-stone-50"
              >
                取消
              </button>
            ) : null}
            <button
              type="button"
              onClick={onDeleteEdge}
              className="rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-600 hover:bg-stone-50"
            >
              删除
            </button>
            {selectedEdge.edge_id.startsWith('pending:') && onJumpToPending ? (
              <button
                type="button"
                onClick={onJumpToPending}
                className="rounded-lg border border-amber-300 px-3 py-2 text-sm text-amber-700 hover:bg-amber-50"
              >
                跳转到待确认队列
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
    </aside>
  )
}

function parseIntensity(value: string): number {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) {
    return 3
  }
  return Math.max(1, Math.min(5, Math.round(parsed)))
}
