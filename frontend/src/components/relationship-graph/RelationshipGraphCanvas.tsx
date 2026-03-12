/**
 * 关系图谱画布：把结构化人物关系渲染成可交互图谱，并与外部表单联动。
 */
import { useEffect, useMemo } from 'react'
import ReactFlow, {
  BaseEdge,
  Background,
  Controls,
  EdgeLabelRenderer,
  Handle,
  MarkerType,
  MiniMap,
  Panel,
  Position,
  getSmoothStepPath,
  useEdgesState,
  useNodesState,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { cn } from '@/lib/utils'
import type {
  RelationshipGraphEdgeViewModel,
  RelationshipGraphNodeViewModel,
  RelationshipGraphSelection,
} from '@/types'

interface RelationshipGraphCanvasProps {
  nodes: RelationshipGraphNodeViewModel[]
  edges: RelationshipGraphEdgeViewModel[]
  selection: RelationshipGraphSelection
  onSelectionChange: (selection: RelationshipGraphSelection) => void
  readOnly?: boolean
  className?: string
  heightClassName?: string
}

interface GraphNodeData {
  node: RelationshipGraphNodeViewModel
}

interface GraphEdgeData {
  edge: RelationshipGraphEdgeViewModel
  lane: number
  pathOffset: number
}

const nodeTypes = {
  character: CharacterGraphNode,
}

const edgeTypes = {
  relationship: RelationshipGraphEdge,
}

export function RelationshipGraphCanvas({
  nodes,
  edges,
  selection,
  onSelectionChange,
  readOnly = false,
  className,
  heightClassName = 'h-[460px]',
}: RelationshipGraphCanvasProps) {
  const layout = useMemo(() => buildOrganizedLayout(nodes), [nodes])
  const flowNodes = useMemo(() => buildFlowNodes(nodes, selection, layout), [layout, nodes, selection])
  const flowEdges = useMemo(() => buildFlowEdges(edges, layout), [edges, layout])
  const [renderNodes, setRenderNodes, onNodesChange] = useNodesState(flowNodes)
  const [renderEdges, setRenderEdges, onEdgesChange] = useEdgesState(flowEdges)

  useEffect(() => {
    setRenderNodes(flowNodes)
  }, [flowNodes, setRenderNodes])

  useEffect(() => {
    setRenderEdges(flowEdges)
  }, [flowEdges, setRenderEdges])

  return (
    <div className={cn(heightClassName, 'overflow-hidden rounded-2xl border border-stone-200 bg-stone-50', className)}>
      <ReactFlow
        nodes={renderNodes}
        edges={renderEdges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={(_, node) => onSelectionChange({ kind: 'node', id: node.id })}
        onEdgeClick={(_, edge) => onSelectionChange({ kind: 'edge', id: edge.id })}
        onPaneClick={() => onSelectionChange(null)}
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable
        edgesFocusable={!readOnly}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        attributionPosition="bottom-left"
      >
        <Background gap={18} size={1} color="#d6d3d1" />
        <MiniMap
          pannable
          zoomable
          nodeColor={(node) => {
            const data = node.data as GraphNodeData | undefined
            return getNodeBackground(data?.node)
          }}
        />
        <Controls showInteractive={!readOnly} />
        <Panel position="top-left">
          <div className="rounded-lg border border-stone-200 bg-white/90 px-3 py-2 text-xs text-stone-600 shadow-sm">
            可拖拽节点、滚轮缩放、点击节点或关系边联动到下方表单。
          </div>
        </Panel>
      </ReactFlow>
    </div>
  )
}

function CharacterGraphNode({ data, selected }: NodeProps<GraphNodeData>) {
  const node = data.node
  return (
    <div
      className={cn(
        'min-w-[164px] rounded-2xl border bg-white px-4 py-3 shadow-sm transition-all',
        node.is_pending ? 'border-dashed border-amber-400' : 'border-stone-300',
        selected ? 'ring-2 ring-indigo-400 ring-offset-2' : '',
      )}
      style={{ background: getNodeBackground(node) }}
    >
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-0 !bg-transparent" />
      <div className="space-y-1">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-semibold text-stone-900">{node.name}</p>
          {node.is_protagonist ? (
            <span className="rounded-full bg-indigo-600 px-2 py-0.5 text-[10px] text-white">主角</span>
          ) : null}
        </div>
        <p className="text-xs text-stone-600">{node.role || '未标注定位'}</p>
        <p className="text-[11px] text-stone-500">关联角色 {node.related_count}</p>
        {node.is_pending ? (
          <p className="text-[11px] font-medium text-amber-700">待确认人物</p>
        ) : null}
      </div>
      {/* 四向隐藏锚点用于平滑布线，避免所有关系都从左右两侧硬连导致缠绕。 */}
      <Handle id="top" type="target" position={Position.Top} className="!h-2 !w-2 !border-0 !bg-transparent" />
      <Handle id="right" type="target" position={Position.Right} className="!h-2 !w-2 !border-0 !bg-transparent" />
      <Handle id="bottom" type="target" position={Position.Bottom} className="!h-2 !w-2 !border-0 !bg-transparent" />
      <Handle id="left" type="target" position={Position.Left} className="!h-2 !w-2 !border-0 !bg-transparent" />
      <Handle id="top" type="source" position={Position.Top} className="!h-2 !w-2 !border-0 !bg-transparent" />
      <Handle id="right" type="source" position={Position.Right} className="!h-2 !w-2 !border-0 !bg-transparent" />
      <Handle id="bottom" type="source" position={Position.Bottom} className="!h-2 !w-2 !border-0 !bg-transparent" />
      <Handle id="left" type="source" position={Position.Left} className="!h-2 !w-2 !border-0 !bg-transparent" />
    </div>
  )
}

function buildFlowNodes(
  nodes: RelationshipGraphNodeViewModel[],
  selection: RelationshipGraphSelection,
  positions: Map<string, { x: number; y: number }>,
): Array<Node<GraphNodeData>> {
  return nodes.map((node) => ({
    id: node.id,
    type: 'character',
    data: { node: { ...node, is_selected: selection?.kind === 'node' && selection.id === node.id } },
    position: positions.get(node.id) ?? { x: 0, y: 0 },
    draggable: true,
    selectable: true,
  }))
}

function buildFlowEdges(
  edges: RelationshipGraphEdgeViewModel[],
  positions: Map<string, { x: number; y: number }>,
): Array<Edge> {
  const edgeHints = buildEdgeHints(edges)
  return edges.map((edge) => {
    const color = getEdgeColor(edge)
    const source = positions.get(edge.source) ?? { x: 0, y: 0 }
    const target = positions.get(edge.target) ?? { x: 0, y: 0 }
    const hint = edgeHints.get(edge.id) ?? { lane: 0, pathOffset: 28 }
    const handles = chooseHandles(source, target, hint.lane)
    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: handles.sourceHandle,
      targetHandle: handles.targetHandle,
      type: 'relationship',
      data: { edge, lane: hint.lane, pathOffset: hint.pathOffset },
      animated: edge.visibility === '误导性表象' || edge.is_conflict,
      pathOptions: {
        borderRadius: 18,
        offset: hint.pathOffset,
      },
      style: {
        stroke: color,
        strokeWidth: Math.max(1.5, edge.intensity),
        strokeDasharray: getEdgeDash(edge),
        opacity: edge.is_pending ? 0.72 : 0.94,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color,
        width: 16,
        height: 16,
      },
      zIndex: edge.is_selected ? 10 : edge.is_conflict ? 9 : 5,
    }
  })
}

function buildOrganizedLayout(nodes: RelationshipGraphNodeViewModel[]): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>()
  if (nodes.length === 0) {
    return positions
  }
  const centerNode = nodes.find((item) => item.is_protagonist) ?? nodes[0]!
  positions.set(centerNode.id, { x: 0, y: 30 })

  const pendingNodes = nodes
    .filter((item) => item.id !== centerNode.id && item.is_pending)
    .sort((left, right) => left.name.localeCompare(right.name, 'zh-CN'))
  const regularNodes = nodes
    .filter((item) => item.id !== centerNode.id && !item.is_pending)
    .sort((left, right) => right.related_count - left.related_count || left.name.localeCompare(right.name, 'zh-CN'))

  const pendingSpacing = 300
  const pendingStart = -((pendingNodes.length - 1) * pendingSpacing) / 2
  pendingNodes.forEach((node, index) => {
    positions.set(node.id, {
      x: pendingStart + index * pendingSpacing,
      y: -280,
    })
  })

  const orbitAngles = [180, 0, 225, 315, 150, 30, 250, 290, 135, 45]
  regularNodes.forEach((node, index) => {
    const layer = Math.floor(index / orbitAngles.length)
    const angle = orbitAngles[index % orbitAngles.length]!
    const radius = 320 + layer * 140
    const radian = (angle * Math.PI) / 180
    positions.set(node.id, {
      x: Math.cos(radian) * radius,
      y: Math.sin(radian) * radius + 40,
    })
  })
  return positions
}

function chooseHandles(
  source: { x: number; y: number },
  target: { x: number; y: number },
  lane: number,
): { sourceHandle: 'top' | 'right' | 'bottom' | 'left'; targetHandle: 'top' | 'right' | 'bottom' | 'left' } {
  const dx = target.x - source.x
  const dy = target.y - source.y
  if (Math.abs(dx) >= Math.abs(dy)) {
    if (lane > 0) {
      return { sourceHandle: 'top', targetHandle: 'top' }
    }
    if (lane < 0) {
      return { sourceHandle: 'bottom', targetHandle: 'bottom' }
    }
    return dx >= 0
      ? { sourceHandle: 'right', targetHandle: 'left' }
      : { sourceHandle: 'left', targetHandle: 'right' }
  }
  if (lane > 0) {
    return { sourceHandle: 'left', targetHandle: 'left' }
  }
  if (lane < 0) {
    return { sourceHandle: 'right', targetHandle: 'right' }
  }
  return dy >= 0
    ? { sourceHandle: 'bottom', targetHandle: 'top' }
    : { sourceHandle: 'top', targetHandle: 'bottom' }
}

function RelationshipGraphEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  style,
  data,
}: EdgeProps<GraphEdgeData>) {
  const edge = data?.edge
  const lane = data?.lane ?? 0
  const pathOffset = data?.pathOffset ?? 28
  const [path, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    borderRadius: 18,
    offset: pathOffset,
  })

  const backgroundTone = edge?.is_conflict
    ? 'rgba(254, 226, 226, 0.96)'
    : edge?.is_pending
      ? 'rgba(254, 243, 199, 0.96)'
      : 'rgba(255,255,255,0.96)'
  const shift = getLabelShift(sourceX, sourceY, targetX, targetY, lane, id)

  return (
    <>
      <BaseEdge id={id} path={path} markerEnd={markerEnd} style={style} />
      <EdgeLabelRenderer>
        <div
          className="pointer-events-none absolute rounded-full border border-stone-200 px-2.5 py-1 text-[11px] font-semibold text-stone-700 shadow-sm"
          style={{
            transform: `translate(-50%, -50%) translate(${labelX + shift.x}px, ${labelY + shift.y}px)`,
            background: backgroundTone,
            boxShadow: '0 2px 10px rgba(0,0,0,0.06)',
          }}
        >
          {edge?.relation_type || '未命名关系'}
        </div>
      </EdgeLabelRenderer>
    </>
  )
}

function buildEdgeHints(
  edges: RelationshipGraphEdgeViewModel[],
): Map<string, { lane: number; pathOffset: number }> {
  const byPair = new Map<string, RelationshipGraphEdgeViewModel[]>()
  for (const edge of edges) {
    const pairKey = [edge.source, edge.target].sort().join('::')
    const bucket = byPair.get(pairKey) ?? []
    bucket.push(edge)
    byPair.set(pairKey, bucket)
  }

  const hints = new Map<string, { lane: number; pathOffset: number }>()
  for (const bucket of byPair.values()) {
    const sorted = [...bucket].sort((left, right) => left.id.localeCompare(right.id, 'en'))
    const lanes = buildLaneSequence(sorted.length)
    sorted.forEach((edge, index) => {
      const lane = lanes[index] ?? 0
      hints.set(edge.id, {
        lane,
        pathOffset: 28 + Math.abs(lane) * 24,
      })
    })
  }
  return hints
}

function buildLaneSequence(count: number): number[] {
  if (count <= 1) {
    return [0]
  }
  const lanes: number[] = []
  for (let index = 0; index < count; index += 1) {
    if (count % 2 === 1 && index === 0) {
      lanes.push(0)
      continue
    }
    const order = count % 2 === 1 ? index : index + 1
    const magnitude = Math.ceil(order / 2)
    const sign = order % 2 === 1 ? 1 : -1
    lanes.push(magnitude * sign)
  }
  return lanes
}

function getLabelShift(
  sourceX: number,
  sourceY: number,
  targetX: number,
  targetY: number,
  lane: number,
  edgeId: string,
): { x: number; y: number } {
  const dx = targetX - sourceX
  const dy = targetY - sourceY
  const isMostlyHorizontal = Math.abs(dx) >= Math.abs(dy)
  const signedLane = lane === 0 ? hashToSigned(edgeId) : lane > 0 ? 1 : -1
  const laneMagnitude = Math.max(1, Math.abs(lane))
  const laneExtra = lane === 0 ? 0 : (laneMagnitude - 1) * 12

  if (isMostlyHorizontal) {
    return { x: 0, y: signedLane * (22 + laneExtra) }
  }
  return { x: signedLane * (30 + laneExtra), y: 0 }
}

function hashToSigned(value: string): 1 | -1 {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0
  }
  return hash % 2 === 0 ? 1 : -1
}

function getNodeBackground(node: RelationshipGraphNodeViewModel | undefined): string {
  if (!node) {
    return '#ffffff'
  }
  if (node.is_pending) {
    return '#fef3c7'
  }
  if (node.is_protagonist) {
    return '#eef2ff'
  }
  return '#ffffff'
}

function getEdgeColor(edge: RelationshipGraphEdgeViewModel): string {
  if (edge.is_conflict) {
    return '#dc2626'
  }
  if (edge.is_pending) {
    return '#ca8a04'
  }
  if (edge.polarity === '正向') {
    return '#059669'
  }
  if (edge.polarity === '负向') {
    return '#e11d48'
  }
  if (edge.polarity === '伪装') {
    return '#7c3aed'
  }
  return '#d97706'
}

function getEdgeDash(edge: RelationshipGraphEdgeViewModel): string | undefined {
  if (edge.is_pending) {
    return '8 6'
  }
  if (edge.visibility === '半公开') {
    return '6 4'
  }
  if (edge.visibility === '隐藏') {
    return '2 6'
  }
  if (edge.visibility === '误导性表象') {
    return '10 4 2 4'
  }
  return undefined
}
