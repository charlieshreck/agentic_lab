"""Discovery Service entry point — orchestrates graph sync."""

import logging
import sys
from datetime import datetime

from discovery_service.config import (
    KUBECONFIGS,
    MCP_SERVERS,
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USER,
    SYNCABLE_LABELS,
)
from discovery_service.graph.client import Neo4jClient
from discovery_service.graph.lifecycle import (
    dedup_network_nodes,
    mark_all_stale,
    run_lifecycle_management,
    sweep_stale,
)
from discovery_service.kube.client import KubeClient
from discovery_service.mcp.client import McpClient
from discovery_service.sources.homelab import sync_argocd_apps, sync_ha_areas
from discovery_service.sources.knowledge import sync_runbooks
from discovery_service.sources.kubernetes import (
    link_services_to_pods,
    sync_kubernetes_deployments,
    sync_kubernetes_ingresses,
    sync_kubernetes_nodes,
    sync_kubernetes_pods,
    sync_kubernetes_pvcs,
    sync_kubernetes_services,
    sync_kubernetes_statefulsets,
)
from discovery_service.sources.network import sync_dns_topology, sync_unifi_devices
from discovery_service.sources.observability import (
    sync_coroot_service_map,
    sync_coroot_services,
    sync_gatus_health,
    sync_grafana_dashboards,
    sync_keep_alerts,
)
from discovery_service.sources.proxmox import sync_proxmox_vms
from discovery_service.sources.truenas import sync_truenas_storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    logger.info("Starting graph-sync job")
    start_time = datetime.now()

    neo4j = Neo4jClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    mcp = McpClient(MCP_SERVERS)

    # Verify Neo4j connection
    if not neo4j.verify():
        logger.error("Neo4j connection failed")
        return 1
    logger.info("Neo4j connection verified")

    # Initialise multi-cluster Kubernetes client (direct API)
    logger.info("Initialising Kubernetes clients...")
    kube = KubeClient(KUBECONFIGS)
    logger.info(f"Kubernetes clients ready for clusters: {kube.clusters}")

    # Phase 1: Mark all syncable nodes as stale
    mark_all_stale(neo4j, SYNCABLE_LABELS)

    # Phase 2: Sync from each source (marks active during sync)
    results: dict[str, int] = {}
    deploy_status: dict = {}

    try:
        results["proxmox_vms"] = sync_proxmox_vms(neo4j, mcp)
    except Exception as e:
        logger.error(f"Proxmox sync failed: {e}")
        results["proxmox_vms"] = 0

    try:
        results["unifi_devices"] = sync_unifi_devices(neo4j, mcp)
    except Exception as e:
        logger.error(f"UniFi sync failed: {e}")
        results["unifi_devices"] = 0

    try:
        results["truenas_storage"] = sync_truenas_storage(neo4j, mcp)
    except Exception as e:
        logger.error(f"TrueNAS sync failed: {e}")
        results["truenas_storage"] = 0

    # --- Kubernetes sync (direct API via KubeClient) ---
    # Nodes first (creates Host nodes for SCHEDULED_ON)
    try:
        results["k8s_nodes"] = sync_kubernetes_nodes(neo4j, kube)
    except Exception as e:
        logger.error(f"Kubernetes nodes sync failed: {e}")
        results["k8s_nodes"] = 0

    # Deployments (provides deploy_status lookup for services)
    try:
        deploy_status = sync_kubernetes_deployments(neo4j, kube)
        results["deployments"] = len(deploy_status)
    except Exception as e:
        logger.error(f"Kubernetes deployments sync failed: {e}")
        results["deployments"] = 0

    # StatefulSets
    try:
        results["statefulsets"] = sync_kubernetes_statefulsets(neo4j, kube)
    except Exception as e:
        logger.error(f"Kubernetes StatefulSets sync failed: {e}")
        results["statefulsets"] = 0

    # Services (selector extracted for pod linking)
    try:
        results["kubernetes"] = sync_kubernetes_services(neo4j, kube, deploy_status)
    except Exception as e:
        logger.error(f"Kubernetes services sync failed: {e}")
        results["kubernetes"] = 0

    # Pods (ownership + scheduling via ownerReferences + nodeName)
    try:
        results["pods"] = sync_kubernetes_pods(neo4j, kube)
    except Exception as e:
        logger.error(f"Kubernetes pods sync failed: {e}")
        results["pods"] = 0

    # Post-sync: Service->Pod linking via selectors
    try:
        results["svc_pod_links"] = link_services_to_pods(neo4j, kube)
    except Exception as e:
        logger.error(f"Service->Pod linking failed: {e}")
        results["svc_pod_links"] = 0

    # Ingresses
    try:
        results["ingresses"] = sync_kubernetes_ingresses(neo4j, kube)
    except Exception as e:
        logger.error(f"Kubernetes ingresses sync failed: {e}")
        results["ingresses"] = 0

    try:
        results["runbooks"] = sync_runbooks(neo4j, mcp)
    except Exception as e:
        logger.error(f"Runbooks sync failed: {e}")
        results["runbooks"] = 0

    try:
        coroot_count, _anomalous = sync_coroot_services(neo4j, mcp)
        results["coroot_services"] = coroot_count
    except Exception as e:
        logger.error(f"Coroot sync failed: {e}")
        results["coroot_services"] = 0

    try:
        results["coroot_service_map"] = sync_coroot_service_map(neo4j, mcp)
    except Exception as e:
        logger.error(f"Coroot service map sync failed: {e}")
        results["coroot_service_map"] = 0

    try:
        results["gatus_health"] = sync_gatus_health(neo4j, mcp)
    except Exception as e:
        logger.error(f"Gatus sync failed: {e}")
        results["gatus_health"] = 0

    try:
        results["ha_areas"] = sync_ha_areas(neo4j, mcp)
    except Exception as e:
        logger.error(f"HA area sync failed: {e}")
        results["ha_areas"] = 0

    try:
        results["argocd_apps"] = sync_argocd_apps(neo4j, mcp)
    except Exception as e:
        logger.error(f"ArgoCD apps sync failed: {e}")
        results["argocd_apps"] = 0

    try:
        results["pvcs"] = sync_kubernetes_pvcs(neo4j, kube)
    except Exception as e:
        logger.error(f"Kubernetes PVCs sync failed: {e}")
        results["pvcs"] = 0

    try:
        results["dns_topology"] = sync_dns_topology(neo4j, mcp)
    except Exception as e:
        logger.error(f"DNS topology sync failed: {e}")
        results["dns_topology"] = 0

    try:
        results["keep_alerts"] = sync_keep_alerts(neo4j, mcp)
    except Exception as e:
        logger.error(f"Keep alerts sync failed: {e}")
        results["keep_alerts"] = 0

    try:
        results["grafana_dashboards"] = sync_grafana_dashboards(neo4j, mcp)
    except Exception as e:
        logger.error(f"Grafana dashboards sync failed: {e}")
        results["grafana_dashboards"] = 0

    # Phase 3: Sweep stale nodes and clean up
    try:
        dedup_network_nodes(neo4j)
    except Exception as e:
        logger.error(f"Network dedup failed: {e}")

    try:
        sweep_stale(neo4j, SYNCABLE_LABELS)
    except Exception as e:
        logger.error(f"Sweep failed: {e}")

    try:
        run_lifecycle_management(neo4j)
    except Exception as e:
        logger.error(f"Lifecycle management failed: {e}")

    kube.close()
    neo4j.close()

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"Graph sync completed in {elapsed:.1f}s: {results}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
