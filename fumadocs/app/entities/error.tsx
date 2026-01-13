'use client';

import Link from 'next/link';
import { useEffect } from 'react';

export default function EntitiesError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Entities page error:', error);
  }, [error]);

  return (
    <main className="min-h-screen bg-gray-900 text-white">
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center gap-4 mb-8">
          <Link href="/" className="text-blue-400 hover:text-blue-300">
            Home
          </Link>
          <span className="text-gray-500">/</span>
          <h1 className="text-2xl font-bold">Entities</h1>
        </div>

        <div className="bg-gray-800 rounded-lg p-8 max-w-lg mx-auto text-center">
          <h2 className="text-xl font-semibold text-red-400 mb-4">
            Failed to load entities
          </h2>
          <p className="text-gray-400 mb-6">
            {error.message || 'An unexpected error occurred while loading entities.'}
          </p>
          <div className="flex gap-4 justify-center">
            <button
              onClick={reset}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-white"
            >
              Try again
            </button>
            <Link
              href="/"
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-white"
            >
              Back to Home
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
