import { NextRequest, NextResponse } from 'next/server';

const KNOWLEDGE_API = process.env.KNOWLEDGE_API_URL || 'http://knowledge-mcp.ai-platform.svc.cluster.local:8000';

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    // Fetch runbook by ID from knowledge MCP
    const response = await fetch(
      `${KNOWLEDGE_API}/api/runbooks/${encodeURIComponent(params.id)}`,
      { next: { revalidate: 60 } }
    );

    if (!response.ok) {
      return NextResponse.json(
        { error: 'Runbook not found' },
        { status: response.status }
      );
    }

    const data = await response.json();
    // Handle knowledge MCP response format
    if (data.status === 'ok' && data.runbook) {
      return NextResponse.json(data.runbook);
    }
    if (data.status === 'error') {
      return NextResponse.json({ error: data.error }, { status: 404 });
    }
    return NextResponse.json(data);
  } catch (error) {
    console.error('Runbook API error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
