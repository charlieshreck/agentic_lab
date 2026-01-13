'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

interface Overview {
  hosts?: { total: number; online: number };
  vms?: { total: number; online: number };
  services?: { total: number; online: number };
  pods?: { total: number; online: number };
  networks?: { total: number; online: number };
}

export default function GraphPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [query, setQuery] = useState('MATCH (n) RETURN labels(n)[0] as type, count(n) as count ORDER BY count DESC LIMIT 10');
  const [queryResult, setQueryResult] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [querying, setQuerying] = useState(false);

  useEffect(() => {
    fetch('/api/graph')
      .then((res) => res.json())
      .then((data) => {
        setOverview(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const runQuery = async () => {
    setQuerying(true);
    try {
      const res = await fetch(`/api/graph?cypher=${encodeURIComponent(query)}`);
      const data = await res.json();
      setQueryResult(data);
    } catch (error) {
      setQueryResult({ error: String(error) });
    } finally {
      setQuerying(false);
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
          <h1 className="text-3xl font-bold">Graph Explorer</h1>
        </div>

        {/* Overview Stats */}
        {loading ? (
          <div className="text-center py-8">Loading overview...</div>
        ) : overview ? (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
            {Object.entries(overview).map(([key, value]) => (
              <div
                key={key}
                className="bg-gray-800 p-4 rounded-lg border border-gray-700"
              >
                <div className="text-2xl font-bold text-blue-400">
                  {value.online}/{value.total}
                </div>
                <div className="text-gray-400 capitalize">{key}</div>
              </div>
            ))}
          </div>
        ) : null}

        {/* Cypher Query Interface */}
        <div className="bg-gray-800 rounded-lg p-6 mb-8">
          <h2 className="text-xl font-semibold mb-4">Cypher Query</h2>
          <div className="space-y-4">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              rows={4}
              className="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-lg text-white font-mono text-sm focus:outline-none focus:border-blue-500"
              placeholder="Enter Cypher query..."
            />
            <div className="flex gap-4">
              <button
                onClick={runQuery}
                disabled={querying}
                className="px-6 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg font-medium disabled:opacity-50"
              >
                {querying ? 'Running...' : 'Run Query'}
              </button>
              <select
                onChange={(e) => setQuery(e.target.value)}
                className="px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg"
              >
                <option value="">Quick Queries...</option>
                <option value="MATCH (n) RETURN labels(n)[0] as type, count(n) as count ORDER BY count DESC">
                  Count by Type
                </option>
                <option value="MATCH (h:Host) WHERE h.status = 'online' RETURN h.ip, h.hostname ORDER BY h.ip LIMIT 20">
                  Online Hosts
                </option>
                <option value="MATCH (h:Host)-[r:CONNECTED_TO]->(n:Network) RETURN n.name, count(h) as hosts ORDER BY hosts DESC">
                  Hosts per Network
                </option>
                <option value="MATCH (h:Host) WHERE h.status = 'offline' RETURN h.ip, h.hostname, h.last_seen ORDER BY h.last_seen DESC LIMIT 10">
                  Recently Offline
                </option>
                <option value="MATCH p=(a)-[r*1..2]-(b) RETURN p LIMIT 25">
                  Sample Relationships
                </option>
              </select>
            </div>
          </div>
        </div>

        {/* Query Results */}
        {queryResult && (
          <div className="bg-gray-800 rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Results</h2>
            {queryResult.error ? (
              <div className="text-red-400">{queryResult.error}</div>
            ) : queryResult.columns && queryResult.data ? (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-700">
                    <tr>
                      {queryResult.columns.map((col: string, idx: number) => (
                        <th key={idx} className="px-4 py-2 text-left">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {queryResult.data.map((row: any[], rowIdx: number) => (
                      <tr key={rowIdx} className="border-t border-gray-700">
                        {row.map((cell, cellIdx) => (
                          <td key={cellIdx} className="px-4 py-2">
                            {typeof cell === 'object'
                              ? JSON.stringify(cell, null, 2)
                              : String(cell ?? '')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-4 text-gray-400 text-sm">
                  {queryResult.data.length} rows returned
                </p>
              </div>
            ) : (
              <pre className="text-sm overflow-x-auto">
                {JSON.stringify(queryResult, null, 2)}
              </pre>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
