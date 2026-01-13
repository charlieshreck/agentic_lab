import { NextRequest, NextResponse } from 'next/server';
import { queryGraph, getInfrastructureOverview } from '@/lib/neo4j';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const cypher = searchParams.get('cypher');

  // Return overview if no query provided
  if (!cypher) {
    const overview = await getInfrastructureOverview();
    return NextResponse.json(overview || { error: 'Failed to get overview' });
  }

  try {
    const result = await queryGraph(cypher);
    return NextResponse.json(result);
  } catch (error) {
    console.error('Graph query error:', error);
    return NextResponse.json(
      { error: 'Query failed', details: String(error) },
      { status: 500 }
    );
  }
}
