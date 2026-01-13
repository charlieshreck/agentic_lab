/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  experimental: {
    serverComponentsExternalPackages: ['mermaid'],
  },
  env: {
    QDRANT_URL: process.env.QDRANT_URL || 'http://qdrant.ai-platform.svc.cluster.local:6333',
    NEO4J_URL: process.env.NEO4J_URL || 'http://neo4j-mcp.ai-platform.svc.cluster.local:8000',
    LITELLM_URL: process.env.LITELLM_URL || 'http://litellm.ai-platform.svc.cluster.local:4000',
  },
};

export default nextConfig;
