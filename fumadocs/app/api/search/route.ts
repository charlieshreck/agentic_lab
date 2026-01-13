import { NextRequest, NextResponse } from 'next/server';
import { searchAllCollections, searchQdrant } from '@/lib/qdrant';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const query = searchParams.get('q');
  const collection = searchParams.get('collection');
  const limit = parseInt(searchParams.get('limit') || '10');

  if (!query) {
    return NextResponse.json({ error: 'Missing query parameter' }, { status: 400 });
  }

  try {
    const results = collection
      ? await searchQdrant(query, collection, limit)
      : await searchAllCollections(query, limit);

    return NextResponse.json({
      query,
      results,
      count: results.length,
    });
  } catch (error) {
    console.error('Search error:', error);
    return NextResponse.json(
      { error: 'Search failed', details: String(error) },
      { status: 500 }
    );
  }
}
