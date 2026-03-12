/**
 * 关系图谱面板：封装常规视图与全屏查看，避免多个页面重复拼装同一套图谱布局。
 */
import { useState, type ReactNode } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { Expand, X } from 'lucide-react'
import { RelationshipGraphCanvas } from '@/components/relationship-graph/RelationshipGraphCanvas'
import { RelationshipGraphInspector } from '@/components/relationship-graph/RelationshipGraphInspector'
import { RelationshipLegend } from '@/components/relationship-graph/RelationshipLegend'
import type {
  RelationshipGraphEdgeViewModel,
  RelationshipGraphNodeViewModel,
  RelationshipGraphSelection,
} from '@/types'

interface RelationshipGraphPanelProps {
  nodes: RelationshipGraphNodeViewModel[]
  edges: RelationshipGraphEdgeViewModel[]
  selection: RelationshipGraphSelection
  onSelectionChange: (selection: RelationshipGraphSelection) => void
  readOnly?: boolean
  sidebar?: ReactNode
  fullscreenSidebar?: ReactNode
  onJumpToNodeForm?: (nodeId: string) => void
  onJumpToEdgeForm?: (edgeId: string) => void
  onJumpToPending?: () => void
  onJumpToConflict?: () => void
}

export function RelationshipGraphPanel({
  nodes,
  edges,
  selection,
  onSelectionChange,
  readOnly = false,
  sidebar,
  fullscreenSidebar,
  onJumpToNodeForm,
  onJumpToEdgeForm,
  onJumpToPending,
  onJumpToConflict,
}: RelationshipGraphPanelProps) {
  const [open, setOpen] = useState(false)

  const closeAndRun = (callback?: (() => void) | null) => {
    if (!callback) {
      return undefined
    }
    return () => {
      setOpen(false)
      // 等待弹窗关闭动画开始后再滚动到底层表单，避免“跳了但看不见”的体验。
      window.setTimeout(() => {
        callback()
      }, 120)
    }
  }

  const closeAndRunWithArg = <T,>(callback?: ((value: T) => void) | null) => {
    if (!callback) {
      return undefined
    }
    return (value: T) => {
      setOpen(false)
      window.setTimeout(() => {
        callback(value)
      }, 120)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <RelationshipLegend />
        <Dialog.Root open={open} onOpenChange={setOpen}>
          <Dialog.Trigger asChild>
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-stone-700 hover:bg-stone-50"
            >
              <Expand className="h-4 w-4" />
              全屏查看
            </button>
          </Dialog.Trigger>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-[2px]" />
            <Dialog.Content className="fixed inset-4 z-50 rounded-2xl border border-stone-200 bg-white shadow-2xl focus:outline-none xl:inset-8">
              <div className="flex h-full flex-col">
                <div className="flex items-center justify-between gap-3 border-b border-stone-200 px-5 py-4">
                  <div>
                    <Dialog.Title className="text-base font-semibold text-stone-900">人物关系图谱</Dialog.Title>
                    <Dialog.Description className="mt-1 text-sm text-stone-500">
                      在全屏模式下查看人物关系结构，点击节点或关系边仍会联动右侧详情。
                    </Dialog.Description>
                  </div>
                  <Dialog.Close asChild>
                    <button
                      type="button"
                      className="inline-flex items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-stone-700 hover:bg-stone-50"
                    >
                      <X className="h-4 w-4" />
                      关闭
                    </button>
                  </Dialog.Close>
                </div>
                <div className="min-h-0 flex-1 p-5">
                  <div className="grid h-full gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(300px,360px)]">
                    <RelationshipGraphCanvas
                      nodes={nodes}
                      edges={edges}
                      selection={selection}
                      onSelectionChange={onSelectionChange}
                      readOnly={readOnly}
                      heightClassName="h-full min-h-[70vh]"
                    />
                    {fullscreenSidebar ?? (
                      <RelationshipGraphInspector
                        nodes={nodes}
                        edges={edges}
                        selection={selection}
                        onJumpToNodeForm={closeAndRunWithArg(onJumpToNodeForm)}
                        onJumpToEdgeForm={closeAndRunWithArg(onJumpToEdgeForm)}
                        onJumpToPending={closeAndRun(onJumpToPending)}
                        onJumpToConflict={closeAndRun(onJumpToConflict)}
                      />
                    )}
                  </div>
                </div>
              </div>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(280px,360px)]">
        <RelationshipGraphCanvas
          nodes={nodes}
          edges={edges}
          selection={selection}
          onSelectionChange={onSelectionChange}
          readOnly={readOnly}
        />
        {sidebar ?? (
          <RelationshipGraphInspector
            nodes={nodes}
            edges={edges}
            selection={selection}
            onJumpToNodeForm={onJumpToNodeForm}
            onJumpToEdgeForm={onJumpToEdgeForm}
            onJumpToPending={onJumpToPending}
            onJumpToConflict={onJumpToConflict}
          />
        )}
      </div>
    </div>
  )
}
