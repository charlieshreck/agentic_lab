import Link from 'next/link';

export default function HomePage() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 to-gray-800 text-white">
      <div className="container mx-auto px-4 py-16">
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold mb-4">Kernow Knowledge</h1>
          <p className="text-xl text-gray-300">
            Infrastructure intelligence for your homelab
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 max-w-4xl mx-auto">
          <Link
            href="/entities"
            className="block p-8 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors border border-gray-700"
          >
            <div className="text-3xl mb-4">🖥️</div>
            <h2 className="text-xl font-semibold mb-2">Entities</h2>
            <p className="text-gray-400">
              Browse all hosts, VMs, services, and network devices
            </p>
          </Link>

          <Link
            href="/graph"
            className="block p-8 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors border border-gray-700"
          >
            <div className="text-3xl mb-4">🔗</div>
            <h2 className="text-xl font-semibold mb-2">Graph</h2>
            <p className="text-gray-400">
              Explore relationships and dependencies
            </p>
          </Link>

          <Link
            href="/search"
            className="block p-8 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors border border-gray-700"
          >
            <div className="text-3xl mb-4">🔍</div>
            <h2 className="text-xl font-semibold mb-2">Search</h2>
            <p className="text-gray-400">
              Semantic search across documentation and runbooks
            </p>
          </Link>
        </div>

        <div className="mt-16 text-center">
          <h3 className="text-2xl font-semibold mb-6">Quick Stats</h3>
          <div className="flex justify-center gap-8">
            <div className="bg-gray-800 px-6 py-4 rounded-lg border border-gray-700">
              <div className="text-3xl font-bold text-blue-400">84</div>
              <div className="text-gray-400">Hosts</div>
            </div>
            <div className="bg-gray-800 px-6 py-4 rounded-lg border border-gray-700">
              <div className="text-3xl font-bold text-blue-400">3</div>
              <div className="text-gray-400">Networks</div>
            </div>
            <div className="bg-gray-800 px-6 py-4 rounded-lg border border-gray-700">
              <div className="text-3xl font-bold text-blue-400">-</div>
              <div className="text-gray-400">Services</div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
