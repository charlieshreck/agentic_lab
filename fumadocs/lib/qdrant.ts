const QDRANT_URL = process.env.QDRANT_URL || 'http://qdrant.ai-platform.svc.cluster.local:6333';
const LITELLM_URL = process.env.LITELLM_URL || 'http://litellm.ai-platform.svc.cluster.local:4000';

export interface SearchResult {
  id: string;
  score: number;
  title: string;
  content: string;
  type: string;
  path?: string;
  metadata?: Record<string, unknown>;
}

async function getEmbedding(text: string): Promise<number[]> {
  const response = await fetch(`${LITELLM_URL}/embeddings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: 'gemini/text-embedding-004',
      input: text,
    }),
  });

  if (!response.ok) {
    throw new Error(`Embedding failed: ${response.statusText}`);
  }

  const data = await response.json();
  return data.data[0].embedding;
}

export async function searchQdrant(
  query: string,
  collection: string = 'documentation',
  limit: number = 10
): Promise<SearchResult[]> {
  try {
    const embedding = await getEmbedding(query);

    const response = await fetch(`${QDRANT_URL}/collections/${collection}/points/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        vector: embedding,
        limit,
        with_payload: true,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      console.error('Qdrant search failed:', error);
      return [];
    }

    const data = await response.json();
    return data.result.map((r: any) => ({
      id: r.id,
      score: r.score,
      title: r.payload?.title || r.payload?.name || 'Untitled',
      content: r.payload?.content || r.payload?.description || '',
      type: r.payload?.type || collection,
      path: r.payload?.path,
      metadata: r.payload,
    }));
  } catch (error) {
    console.error('Qdrant search error:', error);
    return [];
  }
}

export async function searchAllCollections(
  query: string,
  limit: number = 10
): Promise<SearchResult[]> {
  const collections = ['documentation', 'runbooks', 'entities', 'decisions'];
  const results: SearchResult[] = [];

  for (const collection of collections) {
    try {
      const collectionResults = await searchQdrant(query, collection, Math.ceil(limit / 4));
      results.push(...collectionResults);
    } catch {
      // Skip failed collections
    }
  }

  // Sort by score and limit
  return results.sort((a, b) => b.score - a.score).slice(0, limit);
}
