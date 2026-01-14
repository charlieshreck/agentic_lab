'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

interface Runbook {
  id: string;
  title: string;
  content: string;
  solution?: string;
  trigger_pattern?: string;
  path?: string;
}

export default function RunbookDetailPage({ params }: { params: { id: string } }) {
  const [runbook, setRunbook] = useState<Runbook | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/runbooks/${encodeURIComponent(params.id)}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.error) {
          setError(data.error);
        } else {
          setRunbook(data);
        }
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [params.id]);

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-900 text-white">
        <div className="container mx-auto px-4 py-8">
          <div className="text-center">Loading runbook...</div>
        </div>
      </main>
    );
  }

  if (error || !runbook) {
    return (
      <main className="min-h-screen bg-gray-900 text-white">
        <div className="container mx-auto px-4 py-8">
          <Link href="/runbooks" className="text-blue-400 hover:text-blue-300">
            Back to Runbooks
          </Link>
          <div className="mt-8 text-center text-red-400">
            {error || 'Runbook not found'}
          </div>
        </div>
      </main>
    );
  }

  // Simple markdown-like rendering
  const renderContent = (text: string) => {
    return text.split('\n').map((line, i) => {
      // Headers
      if (line.startsWith('### ')) {
        return <h3 key={i} className="text-lg font-semibold mt-6 mb-2">{line.slice(4)}</h3>;
      }
      if (line.startsWith('## ')) {
        return <h2 key={i} className="text-xl font-semibold mt-8 mb-3">{line.slice(3)}</h2>;
      }
      if (line.startsWith('# ')) {
        return <h1 key={i} className="text-2xl font-bold mt-8 mb-4">{line.slice(2)}</h1>;
      }
      // Code blocks (simple single backticks)
      if (line.startsWith('```')) {
        return null; // Skip code fence markers
      }
      // Bullet points
      if (line.startsWith('- ') || line.startsWith('* ')) {
        return <li key={i} className="ml-4">{line.slice(2)}</li>;
      }
      // Numbered lists
      if (/^\d+\.\s/.test(line)) {
        return <li key={i} className="ml-4 list-decimal">{line.replace(/^\d+\.\s/, '')}</li>;
      }
      // Empty lines
      if (line.trim() === '') {
        return <br key={i} />;
      }
      // Code lines (indented or contains backticks)
      if (line.startsWith('    ') || line.includes('`')) {
        return (
          <pre key={i} className="bg-gray-800 p-2 rounded my-1 text-sm overflow-x-auto">
            <code>{line.replace(/`/g, '')}</code>
          </pre>
        );
      }
      // Regular paragraph
      return <p key={i} className="my-2">{line}</p>;
    });
  };

  const content = runbook.content || runbook.solution || '';

  return (
    <main className="min-h-screen bg-gray-900 text-white">
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        <div className="flex items-center gap-4 mb-8">
          <Link href="/" className="text-blue-400 hover:text-blue-300">
            Home
          </Link>
          <span className="text-gray-500">/</span>
          <Link href="/runbooks" className="text-blue-400 hover:text-blue-300">
            Runbooks
          </Link>
          <span className="text-gray-500">/</span>
          <h1 className="text-2xl font-bold">{runbook.title}</h1>
        </div>

        {runbook.path && (
          <p className="text-sm text-gray-500 mb-4">Source: {runbook.path}</p>
        )}

        {runbook.trigger_pattern && (
          <div className="mb-6 p-4 bg-gray-800 rounded-lg border border-gray-700">
            <span className="text-gray-400">Triggers: </span>
            <span className="text-yellow-400">{runbook.trigger_pattern}</span>
          </div>
        )}

        <div className="prose prose-invert max-w-none">
          {renderContent(content)}
        </div>
      </div>
    </main>
  );
}
