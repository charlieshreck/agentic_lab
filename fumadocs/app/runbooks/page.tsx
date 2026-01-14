'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

interface Runbook {
  id: string;
  title: string;
  path?: string;
  trigger_pattern?: string;
}

export default function RunbooksPage() {
  const [runbooks, setRunbooks] = useState<Runbook[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/runbooks')
      .then((res) => res.json())
      .then((data) => {
        if (data.error) {
          setError(data.error);
        } else {
          setRunbooks(data.runbooks || []);
        }
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-900 text-white">
        <div className="container mx-auto px-4 py-8">
          <div className="text-center">Loading runbooks...</div>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen bg-gray-900 text-white">
        <div className="container mx-auto px-4 py-8">
          <div className="text-center text-red-400">Error: {error}</div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-900 text-white">
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center gap-4 mb-8">
          <Link href="/" className="text-blue-400 hover:text-blue-300">
            Home
          </Link>
          <span className="text-gray-500">/</span>
          <h1 className="text-3xl font-bold">Runbooks</h1>
        </div>

        <p className="text-gray-400 mb-8">
          Operational procedures and troubleshooting guides for the homelab infrastructure.
        </p>

        {runbooks.length === 0 ? (
          <div className="text-center text-gray-400 py-8">
            No runbooks found in the knowledge base.
          </div>
        ) : (
          <div className="grid gap-4">
            {runbooks.map((runbook) => (
              <Link
                key={runbook.id}
                href={`/runbooks/${encodeURIComponent(runbook.id)}`}
                className="block p-6 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors border border-gray-700"
              >
                <h2 className="text-xl font-semibold mb-2">{runbook.title}</h2>
                {runbook.path && (
                  <p className="text-sm text-gray-500 mb-2">{runbook.path}</p>
                )}
                {runbook.trigger_pattern && (
                  <p className="text-sm text-gray-400">
                    <span className="text-gray-500">Triggers: </span>
                    {runbook.trigger_pattern}
                  </p>
                )}
              </Link>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
