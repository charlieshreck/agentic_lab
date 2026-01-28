import Link from 'next/link';
import { queryGraph } from '@/lib/neo4j';

export const dynamic = 'force-dynamic';

async function getStats(): Promise<Record<string, number>> {
  try {
    const result = await queryGraph(`
      MATCH (n)
      WHERE NOT any(l IN labels(n) WHERE l STARTS WITH '_')
      WITH labels(n)[0] AS type, count(n) AS count
      WHERE type IS NOT NULL
      RETURN type, count
      ORDER BY count DESC
    `);

    const stats: Record<string, number> = {};
    if (result.data) {
      for (const row of result.data) {
        stats[row[0]] = row[1];
      }
    }
    return stats;
  } catch {
    return {};
  }
}

const STAT_CARDS = [
  { key: 'Host', label: 'Hosts' },
  { key: 'Service', label: 'Services' },
  { key: 'Network', label: 'Networks' },
  { key: 'Pod', label: 'Pods' },
  { key: 'HAEntity', label: 'HA Entities' },
  { key: 'TasmotaDevice', label: 'Tasmota' },
  { key: 'DNSRecord', label: 'DNS Records' },
  { key: 'ArgoApp', label: 'ArgoCD Apps' },
];

export default async function HomePage() {
  const stats = await getStats();

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 to-gray-800 text-white">
      <div className="container mx-auto px-4 py-16">
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold mb-4">Kernow Knowledge</h1>
          <p className="text-xl text-gray-300">
            Infrastructure intelligence for your homelab
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8 max-w-5xl mx-auto">
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
            href="/runbooks"
            className="block p-8 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors border border-gray-700"
          >
            <div className="text-3xl mb-4">📋</div>
            <h2 className="text-xl font-semibold mb-2">Runbooks</h2>
            <p className="text-gray-400">
              Operational procedures and troubleshooting guides
            </p>
          </Link>

          <Link
            href="/search"
            className="block p-8 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors border border-gray-700"
          >
            <div className="text-3xl mb-4">🔍</div>
            <h2 className="text-xl font-semibold mb-2">Search</h2>
            <p className="text-gray-400">
              Semantic search across documentation
            </p>
          </Link>
        </div>

        <div className="mt-16 text-center">
          <h3 className="text-2xl font-semibold mb-6">Quick Stats</h3>
          <div className="flex flex-wrap justify-center gap-4">
            {STAT_CARDS.map(({ key, label }) => (
              <div
                key={key}
                className="bg-gray-800 px-6 py-4 rounded-lg border border-gray-700 min-w-[120px]"
              >
                <div className="text-3xl font-bold text-blue-400">
                  {stats[key] ?? '-'}
                </div>
                <div className="text-gray-400 text-sm">{label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
