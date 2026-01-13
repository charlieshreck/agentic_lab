const NEO4J_MCP_URL = process.env.NEO4J_URL || 'http://neo4j-mcp.ai-platform.svc.cluster.local:8000';

export interface Entity {
  id: string;
  type: string;
  name?: string;
  ip?: string;
  hostname?: string;
  status?: string;
  network?: string;
  last_seen?: string;
  [key: string]: unknown;
}

export interface Relationship {
  type: string;
  target: Entity;
  properties?: Record<string, unknown>;
}

export interface EntityContext {
  entity: Entity;
  relationships: Relationship[];
}

export async function queryGraph(cypher: string): Promise<any> {
  try {
    const response = await fetch(`${NEO4J_MCP_URL}/api/query?q=${encodeURIComponent(cypher)}`);
    if (!response.ok) {
      const error = await response.text();
      console.error('Neo4j query failed:', error);
      return { columns: [], data: [], error: error };
    }
    return await response.json();
  } catch (error) {
    console.error('Neo4j query error:', error);
    return { columns: [], data: [], error: String(error) };
  }
}

export async function getInfrastructureOverview(): Promise<any> {
  try {
    const response = await fetch(`${NEO4J_MCP_URL}/api/overview`);
    if (!response.ok) {
      return null;
    }
    return await response.json();
  } catch (error) {
    console.error('Overview error:', error);
    return null;
  }
}

export async function getEntityContext(id: string, type?: string): Promise<EntityContext | null> {
  try {
    const params = new URLSearchParams({ id });
    if (type) params.append('type', type);

    const response = await fetch(`${NEO4J_MCP_URL}/api/entity?${params}`);
    if (!response.ok) {
      return null;
    }
    return await response.json();
  } catch (error) {
    console.error('Entity context error:', error);
    return null;
  }
}

export async function getEntitiesByType(type: string, limit: number = 100): Promise<Entity[]> {
  const result = await queryGraph(`
    MATCH (e:${type})
    RETURN e
    ORDER BY e.last_seen DESC
    LIMIT ${limit}
  `);

  if (result.error || !result.data) {
    return [];
  }

  return result.data.map((row: any[]) => row[0] as Entity);
}

export async function getHostsOnNetwork(network: string): Promise<Entity[]> {
  const result = await queryGraph(`
    MATCH (h:Host)-[:CONNECTED_TO]->(n:Network {name: $network})
    RETURN h
    ORDER BY h.ip
  `.replace('$network', `'${network}'`));

  if (result.error || !result.data) {
    return [];
  }

  return result.data.map((row: any[]) => row[0] as Entity);
}

export async function generateMermaidDiagram(entityId: string, depth: number = 2): Promise<string> {
  // Query entity and its relationships
  const result = await queryGraph(`
    MATCH path = (e {ip: '${entityId}'})-[r*1..${depth}]-(related)
    RETURN e, relationships(path), nodes(path)
    LIMIT 50
  `);

  if (result.error || !result.data || result.data.length === 0) {
    return 'graph LR\n  A[No relationships found]';
  }

  // Build Mermaid diagram
  const nodes = new Map<string, string>();
  const edges: string[] = [];

  result.data.forEach((row: any[]) => {
    const path = row[2] as any[];
    for (let i = 0; i < path.length; i++) {
      const node = path[i];
      const nodeId = node.ip || node.name || node.id || `node_${i}`;
      const nodeLabel = node.hostname || node.name || node.ip || 'Unknown';
      nodes.set(nodeId, `${sanitizeId(nodeId)}[${nodeLabel}]`);
    }

    const rels = row[1] as any[];
    for (let i = 0; i < rels.length; i++) {
      const rel = rels[i];
      const sourceNode = path[i];
      const targetNode = path[i + 1];
      if (sourceNode && targetNode) {
        const sourceId = sourceNode.ip || sourceNode.name || sourceNode.id;
        const targetId = targetNode.ip || targetNode.name || targetNode.id;
        edges.push(`${sanitizeId(sourceId)} -->|${rel.type || 'RELATED'}| ${sanitizeId(targetId)}`);
      }
    }
  });

  const diagramLines = ['graph TD'];
  nodes.forEach((nodeDef) => diagramLines.push(`  ${nodeDef}`));
  edges.forEach((edge) => diagramLines.push(`  ${edge}`));

  return diagramLines.join('\n');
}

function sanitizeId(id: string): string {
  return id.replace(/[^a-zA-Z0-9]/g, '_');
}
