import { NextRequest, NextResponse } from 'next/server';

const NEO4J_API = process.env.NEO4J_API_URL || 'http://10.20.0.40:31098';

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const searchParams = request.nextUrl.searchParams;
  const entityType = searchParams.get('type') || 'Host';
  const depth = searchParams.get('depth') || '2';

  try {
    const response = await fetch(
      `${NEO4J_API}/api/graph?id=${encodeURIComponent(params.id)}&type=${entityType}&depth=${depth}`,
      { next: { revalidate: 60 } }
    );

    if (!response.ok) {
      return NextResponse.json(
        { error: 'Failed to fetch graph data' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Graph API error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
