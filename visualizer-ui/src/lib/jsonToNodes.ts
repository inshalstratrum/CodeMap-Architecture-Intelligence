import { Node, Edge } from '@xyflow/react';
import { FieldItem } from '../components/NodeCard';

interface ParseContext {
  nodes: Node[];
  edges: Edge[];
  collapsedNodeIds: Set<string>;
  idCounter: number;
}

export function parseJsonToGraph(
  data: unknown,
  collapsedNodeIds: Set<string> = new Set()
): { nodes: Node[]; edges: Edge[] } {
  const ctx: ParseContext = {
    nodes: [],
    edges: [],
    collapsedNodeIds,
    idCounter: 0,
  };

  if (data === null || data === undefined) {
    return { nodes: [], edges: [] };
  }

  const rootId = 'node_0';
  buildNode(data, rootId, 'root', '', ctx, true);

  return { nodes: ctx.nodes, edges: ctx.edges };
}

function buildNode(
  val: unknown,
  nodeId: string,
  keyName: string,
  parentId: string,
  ctx: ParseContext,
  isRoot = false
): string {
  const isParentCollapsed = parentId ? isAncestorCollapsed(parentId, ctx) : false;
  const isThisCollapsed = ctx.collapsedNodeIds.has(nodeId);

  const fields: FieldItem[] = [];
  const childrenToProcess: { childVal: unknown; childKey: string; edgeLabel: string }[] = [];

  if (Array.isArray(val)) {
    val.forEach((item, idx) => {
      const childKey = `[${idx}]`;
      if (typeof item === 'object' && item !== null) {
        childrenToProcess.push({
          childVal: item,
          childKey: childKey,
          edgeLabel: keyName || `item_${idx}`,
        });
      } else {
        fields.push({
          key: String(idx),
          value: item,
          type: getType(item),
        });
      }
    });
  } else if (typeof val === 'object' && val !== null) {
    const entries = Object.entries(val);
    entries.forEach(([k, v]) => {
      if (typeof v === 'object' && v !== null) {
        const isArr = Array.isArray(v);
        const childCount = isArr ? v.length : Object.keys(v).length;
        fields.push({
          key: k,
          value: null,
          type: isArr ? 'array' : 'object',
          childCount,
        });

        childrenToProcess.push({
          childVal: v,
          childKey: k,
          edgeLabel: k,
        });
      } else {
        fields.push({
          key: k,
          value: v as string | number | boolean | null,
          type: getType(v),
        });
      }
    });
  } else {
    fields.push({
      key: keyName || 'value',
      value: val as string | number | boolean | null,
      type: getType(val),
    });
  }

  const hasChildren = childrenToProcess.length > 0;
  let title = keyName || (Array.isArray(val) ? `fruits: [${val.length} items]` : 'object');
  if (Array.isArray(val)) {
    title = `${keyName || 'items'}: [${val.length} items]`;
  } else if (typeof val === 'object' && val !== null && !isRoot) {
    const nameProp = (val as Record<string, unknown>).name;
    if (typeof nameProp === 'string') {
      title = `name: ${nameProp}`;
    }
  }

  if (!isParentCollapsed) {
    ctx.nodes.push({
      id: nodeId,
      type: 'jsonNode',
      position: { x: 0, y: 0 },
      data: {
        title,
        isRoot,
        fields,
        hasChildren,
        collapsed: isThisCollapsed,
      },
    });

    if (parentId) {
      ctx.edges.push({
        id: `edge_${parentId}_${nodeId}`,
        source: parentId,
        target: nodeId,
        type: 'smoothstep',
        label: keyName,
        style: { stroke: '#475569', strokeWidth: 1.8 },
        labelStyle: { fill: '#94a3b8', fontSize: 11, fontFamily: 'monospace', fontWeight: 500 },
        labelBgStyle: { fill: '#0f172a', fillOpacity: 0.85 },
        labelBgPadding: [4, 2],
        labelBgBorderRadius: 4,
      });
    }
  }

  // Recurse into children
  childrenToProcess.forEach(({ childVal, childKey }) => {
    ctx.idCounter++;
    const childId = `node_${ctx.idCounter}`;
    buildNode(childVal, childId, childKey, nodeId, ctx, false);
  });

  return nodeId;
}

function isAncestorCollapsed(nodeId: string, ctx: ParseContext): boolean {
  if (ctx.collapsedNodeIds.has(nodeId)) return true;
  const inEdge = ctx.edges.find((e) => e.target === nodeId);
  if (inEdge) {
    return isAncestorCollapsed(inEdge.source, ctx);
  }
  return false;
}

function getType(val: unknown): FieldItem['type'] {
  if (val === null) return 'null';
  if (Array.isArray(val)) return 'array';
  if (typeof val === 'number') return 'number';
  if (typeof val === 'boolean') return 'boolean';
  if (typeof val === 'object') return 'object';
  return 'string';
}
