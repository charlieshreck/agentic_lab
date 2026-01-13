import { NextRequest, NextResponse } from 'next/server';
import { getEntityContext, generateMermaidDiagram } from '@/lib/neo4j';

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const searchParams = request.nextUrl.searchParams;
  const type = searchParams.get('type') || undefined;
  const withDiagram = searchParams.get('diagram') === 'true';
  const depth = parseInt(searchParams.get('depth') || '2');

  try {
    const context = await getEntityContext(params.id, type);

    if (!context || !context.found) {
      return NextResponse.json(
        { error: 'Entity not found' },
        { status: 404 }
      );
    }

    // Transform Neo4j MCP response to frontend expected format
    // MCP returns: {id, type, found, properties, relationships}
    // Frontend expects: {entity, relationships}
    const entity = {
      id: context.id,
      type: context.type,
      ...context.properties,
    };

    const relationships = (context.relationships || []).map((rel: any) => ({
      type: rel.type,
      target: {
        name: rel.target,
        type: rel.target_type,
      },
    }));

    const response: any = { entity, relationships };

    if (withDiagram) {
      response.diagram = await generateMermaidDiagram(params.id, depth);
    }

    return NextResponse.json(response);
  } catch (error) {
    console.error('Entity context error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch entity', details: String(error) },
      { status: 500 }
    );
  }
}
