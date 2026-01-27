# Discovery Service

Graph sync service for Kernow homelab. Discovers infrastructure from MCP servers and syncs the topology to Neo4j.

## Data Sources

- **Proxmox** — VMs via infrastructure-mcp
- **TrueNAS** — Storage pools, datasets, shares via infrastructure-mcp
- **Kubernetes** — Deployments, services, pods, ingresses, nodes, PVCs (3 clusters)
- **UniFi** — Network devices and clients via home-mcp
- **Coroot** — Service health and dependency map via observability-mcp
- **Gatus** — Endpoint uptime monitoring (direct HTTP)
- **Home Assistant** — Area/location data via home-mcp
- **ArgoCD** — GitOps applications via infrastructure-mcp
- **Keep** — Alert aggregation via observability-mcp
- **Grafana** — Dashboard metadata via observability-mcp
- **Knowledge** — Runbook relationships via knowledge-mcp REST API
- **DNS** — AdGuard rewrites and Unbound overrides via infrastructure-mcp

## Running

```bash
# Install
pip install .

# Run (requires NEO4J_URI and MCP environment variables)
python -m discovery_service.main
```

## Docker

```bash
docker build -t discovery-service .
docker run --rm \
  -e NEO4J_URI=bolt://neo4j:7687 \
  -e NEO4J_USER=neo4j \
  -e NEO4J_PASSWORD=secret \
  discovery-service
```

## Architecture

The service uses a **Mark & Sweep** lifecycle pattern:

1. **Mark** — All syncable nodes are marked `_sync_status = 'stale'` before sync
2. **Sync** — Each source marks discovered nodes as `_sync_status = 'active'`
3. **Sweep** — Nodes still marked `stale` after sync are deleted (no longer exist)

High-volume Kubernetes syncs use **UNWIND batching** for performance.

Neo4j access uses the official **Bolt driver** (`neo4j` Python package).
