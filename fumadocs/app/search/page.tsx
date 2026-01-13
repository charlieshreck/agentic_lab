'use client';

import { useState } from 'react';
import Link from 'next/link';

interface SearchResult {
  id: string;
  score: number;
  title: string;
  content: string;
  type: string;
  path?: string;
}

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setSearched(true);

    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
      const data = await res.json();
      setResults(data.results || []);
    } catch (error) {
      console.error('Search failed:', error);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-900 text-white">
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center gap-4 mb-8">
          <Link href="/" className="text-blue-400 hover:text-blue-300">
            Home
          </Link>
          <span className="text-gray-500">/</span>
          <h1 className="text-3xl font-bold">Search</h1>
        </div>

        <form onSubmit={handleSearch} className="mb-8">
          <div className="flex gap-4">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search documentation, runbooks, entities..."
              className="flex-1 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
            />
            <button
              type="submit"
              disabled={loading}
              className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg font-medium disabled:opacity-50"
            >
              {loading ? 'Searching...' : 'Search'}
            </button>
          </div>
        </form>

        {searched && (
          <div>
            <p className="text-gray-400 mb-4">
              {results.length} result{results.length !== 1 ? 's' : ''} for "{query}"
            </p>

            {results.length > 0 ? (
              <div className="space-y-4">
                {results.map((result) => (
                  <div
                    key={result.id}
                    className="p-6 bg-gray-800 rounded-lg border border-gray-700"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="text-lg font-semibold text-blue-400">
                        {result.title}
                      </h3>
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-1 bg-gray-700 text-gray-300 rounded text-sm">
                          {result.type}
                        </span>
                        <span className="text-gray-500 text-sm">
                          {(result.score * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                    <p className="text-gray-400 line-clamp-3">
                      {result.content.slice(0, 300)}
                      {result.content.length > 300 ? '...' : ''}
                    </p>
                    {result.path && (
                      <p className="mt-2 text-sm text-gray-500">{result.path}</p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-gray-400">
                No results found. Try different keywords.
              </div>
            )}
          </div>
        )}

        {!searched && (
          <div className="text-center py-12 text-gray-400">
            <p className="text-xl mb-4">Semantic search across your knowledge base</p>
            <p>
              Search for runbooks, documentation, entities, and decisions using natural
              language.
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
