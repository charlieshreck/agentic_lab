import { NextRequest, NextResponse } from 'next/server';

const KNOWLEDGE_API = process.env.KNOWLEDGE_API_URL || 'http://10.20.0.40:31084';

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    // Use query param format for knowledge MCP
    const response = await fetch(
      `${KNOWLEDGE_API}/api/runbook?id=${encodeURIComponent(params.id)}`,
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
    if (data.status === 'ok' && data.data) {
      return NextResponse.json(data.data);
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
