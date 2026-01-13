'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

interface Entity {
  ip?: string;
  hostname?: string;
  name?: string;
  status?: string;
  network?: string;
  last_seen?: string;
  vendor?: string;
  [key: string]: unknown;
}

interface Relationship {
  type: string;
  target: Entity;
}

interface EntityContext {
  entity: Entity;
  relationships: Relationship[];
  diagram?: string;
}

export default function EntityDetailPage({ params }: { params: { id: string } }) {
  const [context, setContext] = useState<EntityContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/entities/${params.id}?diagram=true`)
      .then((res) => {
        if (!res.ok) throw new Error('Entity not found');
        return res.json();
      })
      .then((data) => {
        setContext(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [params.id]);

  useEffect(() => {
    // Initialize Mermaid after component mounts
    if (context?.diagram) {
      import('mermaid').then((mermaid) => {
        mermaid.default.initialize({ startOnLoad: true, theme: 'dark' });
        mermaid.default.run();
      });
    }
  }, [context?.diagram]);

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
        <div>Loading...</div>
      </main>
    );
  }

  if (error || !context) {
    return (
      <main className="min-h-screen bg-gray-900 text-white">
        <div className="container mx-auto px-4 py-8">
          <Link href="/entities" className="text-blue-400 hover:text-blue-300">
            Back to Entities
          </Link>
          <div className="mt-8 text-center text-red-400">
            {error || 'Entity not found'}
          </div>
        </div>
      </main>
    );
  }

  const { entity, relationships, diagram } = context;

  return (
    <main className="min-h-screen bg-gray-900 text-white">
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center gap-4 mb-8">
          <Link href="/" className="text-blue-400 hover:text-blue-300">
            Home
          </Link>
          <span className="text-gray-500">/</span>
          <Link href="/entities" className="text-blue-400 hover:text-blue-300">
            Entities
          </Link>
          <span className="text-gray-500">/</span>
          <h1 className="text-2xl font-bold">
            {entity.hostname || entity.name || entity.ip || params.id}
          </h1>
        </div>

        <div className="grid md:grid-cols-2 gap-8">
          {/* Entity Properties */}
          <div className="bg-gray-800 rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Properties</h2>
            <dl className="space-y-3">
              {Object.entries(entity)
                .filter(([key]) => !key.startsWith('_'))
                .map(([key, value]) => (
                  <div key={key} className="flex">
                    <dt className="w-1/3 text-gray-400">{key}</dt>
                    <dd className="w-2/3">
                      {typeof value === 'object'
                        ? JSON.stringify(value)
                        : String(value ?? '-')}
                    </dd>
                  </div>
                ))}
            </dl>
          </div>

          {/* Relationships */}
          <div className="bg-gray-800 rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">
              Relationships ({relationships?.length || 0})
            </h2>
            {relationships && relationships.length > 0 ? (
              <ul className="space-y-3">
                {relationships.map((rel, idx) => (
                  <li
                    key={idx}
                    className="flex items-center gap-3 p-3 bg-gray-700 rounded"
                  >
                    <span className="px-2 py-1 bg-blue-900 text-blue-300 rounded text-sm">
                      {rel.type}
                    </span>
                    <Link
                      href={`/entities/${rel.target.ip || rel.target.name}`}
                      className="text-blue-400 hover:text-blue-300"
                    >
                      {rel.target.hostname || rel.target.name || rel.target.ip}
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-gray-400">No relationships found</p>
            )}
          </div>
        </div>

        {/* Relationship Diagram */}
        {diagram && (
          <div className="mt-8 bg-gray-800 rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Relationship Graph</h2>
            <div className="mermaid bg-gray-900 rounded-lg p-4 overflow-x-auto">
              {diagram}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
