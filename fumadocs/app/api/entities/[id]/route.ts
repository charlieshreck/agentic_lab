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

    if (!context) {
      return NextResponse.json(
        { error: 'Entity not found' },
        { status: 404 }
      );
    }

    const response: any = { ...context };

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
