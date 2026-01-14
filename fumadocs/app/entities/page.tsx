'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

interface EntityType {
  type: string;
  count: number;
}

interface Entity {
  ip?: string;
  hostname?: string;
  name?: string;
  title?: string;
  path?: string;
  status?: string;
  network?: string;
  last_seen?: string;
}

// Entity types that don't have status (documents, decisions, etc.)
const DOCUMENT_TYPES = ['RunbookDocument', 'Decision', 'Documentation', 'Event'];

export default function EntitiesPage() {
  const [entityTypes, setEntityTypes] = useState<EntityType[]>([]);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [loading, setLoading] = useState(true);

  // Check if current type should show status column
  const showStatus = selectedType ? !DOCUMENT_TYPES.includes(selectedType) : true;

  useEffect(() => {
    fetch('/api/entities')
      .then((res) => res.json())
      .then((data) => {
        setEntityTypes(data.types || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (selectedType) {
      setLoading(true);
      fetch(`/api/entities?type=${selectedType}`)
        .then((res) => res.json())
        .then((data) => {
          setEntities(data.entities || []);
          setLoading(false);
        })
        .catch(() => setLoading(false));
    }
  }, [selectedType]);

  return (
    <main className="min-h-screen bg-gray-900 text-white">
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center gap-4 mb-8">
          <Link href="/" className="text-blue-400 hover:text-blue-300">
            Home
          </Link>
          <span className="text-gray-500">/</span>
          <h1 className="text-3xl font-bold">Entities</h1>
        </div>

        {loading && !selectedType && (
          <div className="text-center py-8">Loading...</div>
        )}

        {!selectedType && (
          <div className="grid md:grid-cols-3 lg:grid-cols-4 gap-4">
            {entityTypes.map((et) => (
              <button
                key={et.type}
                onClick={() => setSelectedType(et.type)}
                className="p-6 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors border border-gray-700 text-left"
              >
                <div className="text-2xl font-bold text-blue-400">{et.count}</div>
                <div className="text-lg">{et.type}</div>
              </button>
            ))}
          </div>
        )}

        {selectedType && (
          <div>
            <div className="flex items-center gap-4 mb-6">
              <button
                onClick={() => {
                  setSelectedType(null);
                  setEntities([]);
                }}
                className="text-blue-400 hover:text-blue-300"
              >
                All Types
              </button>
              <span className="text-gray-500">/</span>
              <span className="text-xl">{selectedType}</span>
              <span className="text-gray-500">({entities.length})</span>
            </div>

            {loading ? (
              <div className="text-center py-8">Loading...</div>
            ) : (
              <div className="bg-gray-800 rounded-lg overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-700">
                    <tr>
                      <th className="px-4 py-3 text-left">Name/IP</th>
                      {showStatus && <th className="px-4 py-3 text-left">Status</th>}
                      {showStatus && <th className="px-4 py-3 text-left">Network</th>}
                      {showStatus && <th className="px-4 py-3 text-left">Last Seen</th>}
                      <th className="px-4 py-3 text-left">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {entities.map((entity, idx) => (
                      <tr key={idx} className="border-t border-gray-700 hover:bg-gray-750">
                        <td className="px-4 py-3">
                          <div className="font-medium">
                            {entity.title || entity.hostname || entity.name || entity.ip || 'Unknown'}
                          </div>
                          {entity.path && (
                            <div className="text-sm text-gray-400">{entity.path}</div>
                          )}
                          {entity.ip && entity.hostname && (
                            <div className="text-sm text-gray-400">{entity.ip}</div>
                          )}
                        </td>
                        {showStatus && (
                          <td className="px-4 py-3">
                            <span
                              className={`px-2 py-1 rounded text-sm ${
                                entity.status === 'online'
                                  ? 'bg-green-900 text-green-300'
                                  : entity.status === 'offline'
                                  ? 'bg-red-900 text-red-300'
                                  : 'bg-gray-600 text-gray-300'
                              }`}
                            >
                              {entity.status || 'unknown'}
                            </span>
                          </td>
                        )}
                        {showStatus && (
                          <td className="px-4 py-3 text-gray-400">
                            {entity.network || '-'}
                          </td>
                        )}
                        {showStatus && (
                          <td className="px-4 py-3 text-gray-400 text-sm">
                            {entity.last_seen
                              ? new Date(entity.last_seen).toLocaleString()
                              : '-'}
                          </td>
                        )}
                        <td className="px-4 py-3">
                          <Link
                            href={`/entities/${encodeURIComponent(entity.ip || entity.title || entity.name || String(idx))}?type=${selectedType}`}
                            className="text-blue-400 hover:text-blue-300"
                          >
                            View
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
