import { NextResponse } from 'next/server';

const KNOWLEDGE_API = process.env.KNOWLEDGE_API_URL || 'http://knowledge-mcp.ai-platform.svc.cluster.local:8000';

export async function GET() {
  try {
    const response = await fetch(`${KNOWLEDGE_API}/api/runbooks?limit=100`, {
      next: { revalidate: 60 },
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: 'Failed to fetch runbooks' },
        { status: response.status }
      );
    }

    const data = await response.json();
    // Handle knowledge MCP response format
    if (data.status === 'ok') {
      return NextResponse.json({ runbooks: data.runbooks || [] });
    }
    return NextResponse.json(data);
  } catch (error) {
    console.error('Runbooks API error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
