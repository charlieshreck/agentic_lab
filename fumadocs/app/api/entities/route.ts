import { NextRequest, NextResponse } from 'next/server';
import { queryGraph, getEntitiesByType, getHostsOnNetwork } from '@/lib/neo4j';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const type = searchParams.get('type');
  const network = searchParams.get('network');
  const limit = parseInt(searchParams.get('limit') || '100');

  try {
    let entities;

    if (network) {
      entities = await getHostsOnNetwork(network);
    } else if (type) {
      entities = await getEntitiesByType(type, limit);
    } else {
      // Return all entity types with counts
      const result = await queryGraph(`
        MATCH (n)
        WHERE NOT any(l IN labels(n) WHERE l STARTS WITH 'Archived')
          AND (n.status IS NULL OR n.status IN ['online', 'stale'])
        WITH labels(n)[0] as type, count(n) as count
        WHERE type IS NOT NULL
        RETURN type, count
        ORDER BY count DESC
      `);

      return NextResponse.json({
        types: result.data?.map((row: any[]) => ({
          type: row[0],
          count: row[1],
        })) || [],
      });
    }

    return NextResponse.json({
      type: type || 'all',
      network: network || null,
      entities,
      count: entities?.length || 0,
    });
  } catch (error) {
    console.error('Entities error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch entities', details: String(error) },
      { status: 500 }
    );
  }
}
