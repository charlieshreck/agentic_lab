# Network Discovery Runbook

## Overview

The network entity discovery system maintains an inventory of all devices on the homelab networks. It runs automatically every 4 hours but can be triggered manually when needed.

## Architecture

```
Sources (6)          Discovery Job          Storage
------------         -------------          -------
OPNsense DHCP  -->                     --> Qdrant (semantic)
UniFi Clients  -->   Fingerprinting    --> Neo4j (relationships)
Proxmox VMs    -->   + Embedding
TrueNAS        -->
nmap Sweep     -->
mDNS/Bonjour   -->
```

### Schedule

| Job | Schedule | Purpose |
|-----|----------|---------|
| `network-entity-discovery` | `0 */4 * * *` (every 4h) | Discover and fingerprint devices |
| `graph-sync` | `15 */4 * * *` (15 min after) | Sync to Neo4j, run lifecycle |

## Prerequisites

```bash
# Set kubeconfig for agentic cluster
export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig
```

## Trigger Discovery Manually

### Run Full Discovery

```bash
# Create job from CronJob template
kubectl create job discovery-$(date +%s) \
  --from=cronjob/network-entity-discovery -n ai-platform

# Watch progress
kubectl logs -n ai-platform -l job-name=discovery-* -f --tail=100
```

### Run Graph Sync (after discovery completes)

```bash
# Create graph-sync job
kubectl create job graph-sync-$(date +%s) \
  --from=cronjob/graph-sync -n ai-platform

# Watch progress
kubectl logs -n ai-platform -l job-name=graph-sync-* -f --tail=100
```

## Verify Results

### Check Qdrant Entities

```bash
# Count entities
curl -s "http://10.20.0.40:31084/api/search?q=*&collection=entities&limit=1" | jq '.count'

# Search for specific device
curl -s "http://10.20.0.40:31084/api/search?q=chromecast&collection=entities" | jq '.results[].payload.hostname'

# List all IoT devices
curl -s "http://10.20.0.40:31084/api/search?q=iot&collection=entities&limit=50" | jq '.results[].payload | {ip, hostname, type}'
```

### Check Neo4j Hosts

```bash
# Count online hosts
curl -s -X POST "http://10.20.0.40:31098/api/query" \
  -H "Content-Type: application/json" \
  -d '{"q": "MATCH (h:Host) WHERE h.status=\"online\" RETURN count(h)"}' | jq

# Check for stale hosts
curl -s -X POST "http://10.20.0.40:31098/api/query" \
  -H "Content-Type: application/json" \
  -d '{"q": "MATCH (h:Host) WHERE h.status=\"stale\" RETURN h.ip, h.hostname"}' | jq

# View network topology
curl -s -X POST "http://10.20.0.40:31098/api/query" \
  -H "Content-Type: application/json" \
  -d '{"q": "MATCH (n:Network)<-[:CONNECTED_TO]-(h:Host) RETURN n.name, count(h)"}' | jq
```

## Troubleshooting

### Discovery Job Failing

1. **Check job status:**
   ```bash
   kubectl get jobs -n ai-platform | grep discovery
   kubectl describe job <job-name> -n ai-platform
   ```

2. **Check pod logs:**
   ```bash
   kubectl logs -n ai-platform -l job-name=discovery-* --tail=200
   ```

3. **Common issues:**
   - MCP server unavailable (check health endpoints)
   - Network connectivity to source APIs
   - Qdrant/Neo4j unavailable

### Graph Sync Failing

1. **Check Neo4j credentials:**
   ```bash
   # Verify secret exists
   kubectl get secret neo4j-credentials -n ai-platform -o jsonpath='{.data.NEO4J_PASSWORD}' | base64 -d

   # Test Neo4j connection
   curl -u neo4j:<password> http://neo4j.ai-platform.svc:7474/db/neo4j/tx/commit \
     -H "Content-Type: application/json" \
     -d '{"statements":[{"statement":"RETURN 1"}]}'
   ```

2. **Check Infisical sync:**
   ```bash
   # Verify InfisicalSecret status
   kubectl get infisicalsecret neo4j-infisical -n ai-platform -o yaml
   ```

### All Devices Showing Offline

This usually means graph-sync hasn't run successfully:

1. **Check last successful sync:**
   ```bash
   kubectl get jobs -n ai-platform | grep graph-sync
   ```

2. **Force sync:**
   ```bash
   kubectl create job graph-sync-force-$(date +%s) \
     --from=cronjob/graph-sync -n ai-platform
   ```

3. **Lifecycle thresholds:**
   - Stale: 8 hours after last_seen
   - Offline: 48 hours after becoming stale
   - Archived: 14 days after becoming offline

## Configuration

### Lifecycle Thresholds

| Status | Threshold | Duration String |
|--------|-----------|-----------------|
| Stale | 8 hours | `PT8H` |
| Offline | 48 hours | `P2D` |
| Archived | 14 days | `P14D` |

### Fingerprinting

HTTP fingerprinting probes these device types:
- Tasmota (`/cm?cmnd=Status%200`)
- Shelly (`/shelly`, `/rpc/Shelly.GetDeviceInfo`)
- ESPHome (`/`)
- WLED (`/json/info`)
- Synology (`/webapi/query.cgi`)
- Home Assistant (`/api/`)
- Plex (`/identity`)
- Jellyfin (`/System/Info/Public`)

Timeout: 2 seconds per probe (parallel execution)

### Data Sources

| Source | MCP Server | Data Retrieved |
|--------|------------|----------------|
| OPNsense | opnsense-mcp | DHCP leases (IP, MAC, hostname) |
| UniFi | unifi-mcp | Clients, APs, switches, OUI |
| Proxmox | proxmox-mcp | VMs with status |
| TrueNAS | truenas-mcp | System info |
| Home Assistant | home-assistant-mcp | Device areas/locations |
| nmap | (local) | Network sweep |
| mDNS | (local) | Service discovery |

## Related

- [MCP Servers Runbook](./mcp-servers.md) - MCP server deployment and health
- [DNS Architecture](./dns-architecture.md) - Network DNS configuration
