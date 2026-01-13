'use client';

import Link from 'next/link';
import { useEffect } from 'react';

export default function EntityError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Entity page error:', error);
  }, [error]);

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
        </div>

        <div className="bg-gray-800 rounded-lg p-8 max-w-lg mx-auto text-center">
          <h2 className="text-xl font-semibold text-red-400 mb-4">
            Failed to load entity
          </h2>
          <p className="text-gray-400 mb-6">
            {error.message || 'An unexpected error occurred while loading this entity.'}
          </p>
          <div className="flex gap-4 justify-center">
            <button
              onClick={reset}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-white"
            >
              Try again
            </button>
            <Link
              href="/entities"
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-white"
            >
              Back to Entities
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
