/**
 * 人物关系图谱视图模型：把后端关系数据收口成前端可直接渲染的节点与边。
 */
import type {
  Character,
  CharacterBlueprint,
  CharacterNode,
  RelationshipBlueprintEdge,
  RelationshipConflictReport,
  RelationshipGraphEdgeViewModel,
  RelationshipGraphNodeViewModel,
  RelationshipGraphSelection,
  RelationshipPendingItem,
} from '@/types'

export function normalizeCharacterNodeId(name: string): string {
  return name.trim().replace(/\s+/g, '_')
}

export function buildCharacterNodesFromBlueprint(characters: CharacterBlueprint[]): CharacterNode[] {
  return characters.map((character) => ({
    character_id: normalizeCharacterNodeId(character.name),
    name: character.name,
    role: character.role,
    public_persona: character.public_persona,
    core_motivation: character.core_motivation,
    fatal_flaw: character.fatal_flaw,
    non_negotiable_traits: character.non_negotiable_traits,
    arc_outline: character.arc_outline,
    faction_affiliation: '',
    status: 'active',
  }))
}

export function buildCharacterNodesFromCanon(characters: Character[]): CharacterNode[] {
  return characters.map((character) => {
    const attributes = character.attributes ?? {}
    const rawTraits = Array.isArray(attributes.non_negotiable_traits) ? attributes.non_negotiable_traits : []
    const rawArc = Array.isArray(attributes.arc_outline) ? attributes.arc_outline : []
    return {
      character_id: normalizeCharacterNodeId(character.name),
      name: character.name,
      role: typeof attributes.role === 'string' ? attributes.role : '',
      public_persona: character.description,
      core_motivation: character.core_motivation,
      fatal_flaw: typeof attributes.fatal_flaw === 'string' ? attributes.fatal_flaw : '',
      non_negotiable_traits: rawTraits.filter((item): item is string => typeof item === 'string'),
      arc_outline: rawArc.filter((item): item is string => typeof item === 'string'),
      faction_affiliation: typeof attributes.faction_affiliation === 'string' ? attributes.faction_affiliation : '',
      status: character.status,
    }
  })
}

interface BuildRelationshipGraphViewModelArgs {
  nodes: CharacterNode[]
  edges: RelationshipBlueprintEdge[]
  pending: RelationshipPendingItem[]
  selection: RelationshipGraphSelection
  conflict?: RelationshipConflictReport | null
  replanEdgeId?: string | null
}

export function buildRelationshipGraphViewModel({
  nodes,
  edges,
  pending,
  selection,
  conflict,
  replanEdgeId,
}: BuildRelationshipGraphViewModelArgs): {
  nodes: RelationshipGraphNodeViewModel[]
  edges: RelationshipGraphEdgeViewModel[]
} {
  const nodeMap = new Map<string, CharacterNode>()
  for (const node of nodes) {
    nodeMap.set(node.character_id, node)
  }

  for (const item of pending) {
    if (item.item_type !== 'character' || !item.character) {
      continue
    }
    if (!nodeMap.has(item.character.character_id)) {
      nodeMap.set(item.character.character_id, item.character)
    }
  }

  for (const edge of edges) {
    ensureEdgeEndpoint(nodeMap, edge.source_character_id)
    ensureEdgeEndpoint(nodeMap, edge.target_character_id)
  }
  for (const item of pending) {
    if (item.item_type !== 'relationship' || !item.relationship) {
      continue
    }
    ensureEdgeEndpoint(nodeMap, item.relationship.source_character_id)
    ensureEdgeEndpoint(nodeMap, item.relationship.target_character_id)
  }

  const pendingNodeIds = new Set(
    pending
      .filter((item) => item.item_type === 'character' && item.character)
      .map((item) => item.character!.character_id),
  )
  const pendingEdgeIds = new Set(
    pending
      .filter((item) => item.item_type === 'relationship' && item.relationship)
      .map((item) => item.relationship!.edge_id),
  )

  const allEdges = [...edges]
  for (const item of pending) {
    if (item.item_type === 'relationship' && item.relationship) {
      allEdges.push(item.relationship)
    }
  }

  const relatedCountByNode = new Map<string, number>()
  for (const edge of allEdges) {
    relatedCountByNode.set(edge.source_character_id, (relatedCountByNode.get(edge.source_character_id) ?? 0) + 1)
    relatedCountByNode.set(edge.target_character_id, (relatedCountByNode.get(edge.target_character_id) ?? 0) + 1)
  }

  const viewNodes = [...nodeMap.values()].map((node) => ({
    id: node.character_id,
    name: node.name,
    role: node.role,
    public_persona: node.public_persona,
    core_motivation: node.core_motivation,
    fatal_flaw: node.fatal_flaw,
    related_count: relatedCountByNode.get(node.character_id) ?? 0,
    is_protagonist: node.role.includes('主角'),
    is_pending: pendingNodeIds.has(node.character_id) || node.status === 'pending',
    is_selected: selection?.kind === 'node' && selection.id === node.character_id,
  }))

  const seenEdgeIds = new Set<string>()
  const viewEdges: RelationshipGraphEdgeViewModel[] = []
  for (const edge of allEdges) {
    if (seenEdgeIds.has(edge.edge_id)) {
      continue
    }
    seenEdgeIds.add(edge.edge_id)
    const selectedByEdge = selection?.kind === 'edge' && selection.id === edge.edge_id
    const selectedByNode =
      selection?.kind === 'node' &&
      (selection.id === edge.source_character_id || selection.id === edge.target_character_id)
    viewEdges.push({
      id: edge.edge_id,
      source: edge.source_character_id,
      target: edge.target_character_id,
      source_name: nodeMap.get(edge.source_character_id)?.name ?? edge.source_character_id,
      target_name: nodeMap.get(edge.target_character_id)?.name ?? edge.target_character_id,
      relation_type: edge.relation_type || '未命名关系',
      polarity: edge.polarity,
      intensity: edge.intensity,
      visibility: edge.visibility,
      stability: edge.stability,
      summary: edge.summary,
      hidden_truth: edge.hidden_truth,
      non_breakable_without_reveal: edge.non_breakable_without_reveal,
      is_pending: pendingEdgeIds.has(edge.edge_id),
      is_conflict: conflict?.edge_id === edge.edge_id,
      has_replan: replanEdgeId === edge.edge_id,
      is_selected: selectedByEdge || Boolean(selectedByNode),
    })
  }

  return {
    nodes: viewNodes,
    edges: viewEdges,
  }
}

function ensureEdgeEndpoint(nodeMap: Map<string, CharacterNode>, characterId: string): void {
  if (!characterId || nodeMap.has(characterId)) {
    return
  }
  nodeMap.set(characterId, {
    character_id: characterId,
    name: characterId.replace(/_/g, ' '),
    role: '未确认角色',
    public_persona: '',
    core_motivation: '',
    fatal_flaw: '',
    non_negotiable_traits: [],
    arc_outline: [],
    faction_affiliation: '',
    status: 'pending',
  })
}
