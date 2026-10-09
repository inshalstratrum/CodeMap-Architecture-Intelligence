import { Node, Edge, Position } from '@xyflow/react';

export type LayoutDirection = 'LR' | 'TB' | 'RL' | 'BT';

export interface LayoutOptions {
  direction?: LayoutDirection;
  nodeWidth?: number;
  nodeHeight?: number;
  rankSep?: number;
  nodeSep?: number;
  positionCache?: Map<string, { x: number; y: number }>;
  isFullRelayout?: boolean;
}

// Persistent cache surviving tab changes so nodes never lose custom or locked positions
export const globalNodePositionsCache = new Map<string, { x: number; y: number }>();

/**
 * Computes a deterministic tidy hierarchical tree layout for nodes and hierarchy edges.
 * Guarantees zero overlaps and clean centering of parent nodes relative to their children.
 */
export function computeTidyTreeLayout(
  nodes: Node[],
  hierarchyEdges: Edge[],
  direction: LayoutDirection = 'LR'
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  if (nodes.length === 0) return positions;

  const nodeMap = new Map<string, Node>(nodes.map((n) => [n.id, n]));
  const parentMap = new Map<string, string>();
  const childrenMap = new Map<string, string[]>();

  nodes.forEach((n) => childrenMap.set(n.id, []));

  hierarchyEdges.forEach((edge) => {
    if (nodeMap.has(edge.source) && nodeMap.has(edge.target)) {
      parentMap.set(edge.target, edge.source);
      const list = childrenMap.get(edge.source) || [];
      list.push(edge.target);
      childrenMap.set(edge.source, list);
    }
  });

  // Find root nodes (nodes with no incoming hierarchy edges)
  const rootIds = nodes.map((n) => n.id).filter((id) => !parentMap.has(id));
  if (rootIds.length === 0 && nodes.length > 0) {
    rootIds.push(nodes[0].id);
  }

  // Assign depth to all nodes
  const depthMap = new Map<string, number>();
  function computeDepth(id: string, depth: number) {
    depthMap.set(id, depth);
    const children = childrenMap.get(id) || [];
    children.forEach((c) => computeDepth(c, depth + 1));
  }
  rootIds.forEach((r) => computeDepth(r, 0));

  // Post-order traversal to assign vertical slot indices (leaves get unique slots, parents center)
  let currentLeafSlot = 0;
  const slotMap = new Map<string, number>();

  function assignSlots(id: string) {
    const children = childrenMap.get(id) || [];
    if (children.length === 0) {
      slotMap.set(id, currentLeafSlot);
      currentLeafSlot += 1;
    } else {
      children.forEach((c) => assignSlots(c));
      const childSlots = children.map((c) => slotMap.get(c)!);
      const avgSlot = (Math.min(...childSlots) + Math.max(...childSlots)) / 2;
      slotMap.set(id, avgSlot);
    }
  }

  rootIds.forEach((r) => assignSlots(r));

  const rankSep = direction === 'LR' || direction === 'RL' ? 320 : 160;
  const nodeSep = direction === 'LR' || direction === 'RL' ? 100 : 260;

  nodes.forEach((node) => {
    const depth = depthMap.get(node.id) ?? 0;
    const slot = slotMap.get(node.id) ?? 0;

    let x = 0;
    let y = 0;

    switch (direction) {
      case 'LR':
        x = depth * rankSep;
        y = slot * nodeSep;
        break;
      case 'TB':
        x = slot * nodeSep;
        y = depth * rankSep;
        break;
      case 'RL':
        x = -depth * rankSep;
        y = slot * nodeSep;
        break;
      case 'BT':
        x = slot * nodeSep;
        y = -depth * rankSep;
        break;
    }

    positions.set(node.id, { x, y });
  });

  return positions;
}

/**
 * Applies a static layout to nodes and edges.
 *
 * Rules:
 * 1. Existing nodes with cached positions NEVER move or shift when other nodes expand/collapse.
 * 2. Newly revealed children are placed adjacent to their parent and added to the cache.
 * 3. Dependency edges (uses / used by) NEVER affect the physical layout coordinates.
 */
export function applyStaticTreeLayout(
  nodes: Node[],
  edges: Edge[],
  options: LayoutOptions = {}
): { nodes: Node[]; edges: Edge[] } {
  const direction = options.direction || 'LR';
  const positionCache = options.positionCache || new Map<string, { x: number; y: number }>();
  const isFullRelayout = options.isFullRelayout ?? false;

  const targetPosition =
    direction === 'LR'
      ? Position.Left
      : direction === 'TB'
      ? Position.Top
      : direction === 'RL'
      ? Position.Right
      : Position.Bottom;

  const sourcePosition =
    direction === 'LR'
      ? Position.Right
      : direction === 'TB'
      ? Position.Bottom
      : direction === 'RL'
      ? Position.Left
      : Position.Top;

  // Filter hierarchy edges from dependency overlay edges
  const hierarchyEdges = edges.filter(
    (e) => !e.id.startsWith('dep_uses_') && !e.id.startsWith('dep_usedby_')
  );

  if (isFullRelayout || positionCache.size === 0) {
    const newPositions = computeTidyTreeLayout(nodes, hierarchyEdges, direction);
    newPositions.forEach((pos, id) => {
      positionCache.set(id, pos);
    });
  } else {
    // Incremental static positioning:
    // Any node already in positionCache remains 100% frozen in place!
    const nodeMap = new Map<string, Node>(nodes.map((n) => [n.id, n]));
    const parentMap = new Map<string, string>();
    const childrenMap = new Map<string, string[]>();

    hierarchyEdges.forEach((edge) => {
      if (nodeMap.has(edge.source) && nodeMap.has(edge.target)) {
        parentMap.set(edge.target, edge.source);
        const list = childrenMap.get(edge.source) || [];
        list.push(edge.target);
        childrenMap.set(edge.source, list);
      }
    });

    const rankSep = direction === 'LR' || direction === 'RL' ? 320 : 160;
    const nodeSep = direction === 'LR' || direction === 'RL' ? 95 : 260;

    const unpositioned = nodes.filter((n) => !positionCache.has(n.id));

    let iterations = 0;
    while (unpositioned.length > 0 && iterations < 50) {
      iterations++;
      let placedAny = false;

      for (let i = unpositioned.length - 1; i >= 0; i--) {
        const node = unpositioned[i];
        const parentId = parentMap.get(node.id);

        if (parentId && positionCache.has(parentId)) {
          const parentPos = positionCache.get(parentId)!;
          const siblings = childrenMap.get(parentId) || [node.id];
          const childIndex = Math.max(0, siblings.indexOf(node.id));
          const totalChildren = Math.max(1, siblings.length);
          const offset = (childIndex - (totalChildren - 1) / 2) * nodeSep;

          let x = parentPos.x;
          let y = parentPos.y;

          switch (direction) {
            case 'LR':
              x = parentPos.x + rankSep;
              y = parentPos.y + offset;
              break;
            case 'TB':
              x = parentPos.x + offset;
              y = parentPos.y + rankSep;
              break;
            case 'RL':
              x = parentPos.x - rankSep;
              y = parentPos.y + offset;
              break;
            case 'BT':
              x = parentPos.x + offset;
              y = parentPos.y - rankSep;
              break;
          }

          positionCache.set(node.id, { x, y });
          unpositioned.splice(i, 1);
          placedAny = true;
        } else if (!parentId) {
          positionCache.set(node.id, { x: 0, y: 0 });
          unpositioned.splice(i, 1);
          placedAny = true;
        }
      }

      if (!placedAny && unpositioned.length > 0) {
        unpositioned.forEach((n, idx) => {
          positionCache.set(n.id, { x: 320, y: idx * nodeSep });
        });
        break;
      }
    }
  }

  const layoutedNodes = nodes.map((node) => {
    const pos = positionCache.get(node.id) || { x: 0, y: 0 };
    return {
      ...node,
      targetPosition,
      sourcePosition,
      position: { x: pos.x, y: pos.y },
    };
  });

  return { nodes: layoutedNodes, edges };
}

// Backward-compatible alias for existing callers
export function getLayoutedElements(
  nodes: Node[],
  edges: Edge[],
  options: LayoutOptions = {}
) {
  return applyStaticTreeLayout(nodes, edges, options);
}

