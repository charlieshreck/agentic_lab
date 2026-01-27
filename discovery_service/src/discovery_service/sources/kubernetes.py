"""Sync Kubernetes resources (deployments, services, pods, ingresses, nodes, PVCs) to Neo4j.

High-volume sync functions use UNWIND batching for performance.
"""

import logging

from discovery_service.config import K8S_CLUSTERS
from discovery_service.graph.client import Neo4jClient
from discovery_service.graph.lifecycle import mark_active
from discovery_service.mcp.client import McpClient, extract_list

logger = logging.getLogger(__name__)


def sync_kubernetes_deployments(neo4j: Neo4jClient, mcp: McpClient) -> dict:
    """Sync Kubernetes deployments from all clusters. Returns deploy_status lookup dict."""
    logger.info("Syncing Kubernetes deployments (multi-cluster)...")

    deploy_status: dict[tuple, dict] = {}
    total_count = 0

    for cluster in K8S_CLUSTERS:
        try:
            deploys_response = mcp.call_tool(
                "infrastructure", "kubectl_get_deployments",
                {"all_namespaces": True, "cluster": cluster},
            )
            deploys = extract_list(deploys_response, "deployments", "result")

            rows = []
            for d in deploys:
                name = d.get("name")
                namespace = d.get("namespace")
                if not name or not namespace:
                    continue

                replicas = d.get("replicas", 0)
                ready = d.get("ready", 0)
                available = d.get("available", 0)

                if replicas == 0:
                    status = "scaled-down"
                elif ready >= replicas:
                    status = "healthy"
                elif ready > 0:
                    status = "degraded"
                else:
                    status = "unhealthy"

                deploy_status[(name, namespace, cluster)] = {
                    "status": status,
                    "replicas": replicas,
                    "ready": ready,
                    "available": available,
                }

                rows.append({
                    "name": name,
                    "namespace": namespace,
                    "cluster": cluster,
                    "replicas": replicas,
                    "ready": ready,
                    "available": available,
                    "status": status,
                    "selector": d.get("selector", ""),
                })

            if rows:
                neo4j.batch_merge("""
                    MERGE (dep:Deployment {name: row.name, namespace: row.namespace, cluster: row.cluster})
                    SET dep.replicas = row.replicas,
                        dep.ready_replicas = row.ready,
                        dep.available_replicas = row.available,
                        dep.status = row.status,
                        dep.selector = row.selector,
                        dep.last_seen = datetime(),
                        dep.source = 'kubernetes',
                        dep._sync_status = 'active'
                """, rows)

                # BACKED_BY relationships (Service->Deployment by name+namespace match)
                neo4j.batch_merge("""
                    MATCH (s:Service {name: row.name, namespace: row.namespace, cluster: row.cluster})
                    MATCH (dep:Deployment {name: row.name, namespace: row.namespace, cluster: row.cluster})
                    MERGE (s)-[:BACKED_BY]->(dep)
                """, rows)

                mark_active(neo4j, "Deployment",
                            [f"{r['name']}|{r['namespace']}|{r['cluster']}" for r in rows],
                            id_field="name")

            total_count += len(rows)
            logger.info(f"  {cluster}: {len(rows)} deployments")
        except Exception as e:
            logger.error(f"  {cluster}: deployment sync failed: {e}")

    logger.info(f"Synced {total_count} deployments across {len(K8S_CLUSTERS)} clusters")
    return deploy_status


def sync_kubernetes_services(neo4j: Neo4jClient, mcp: McpClient, deploy_status: dict | None = None) -> int:
    """Sync Kubernetes services and pods from all clusters to Neo4j."""
    logger.info("Syncing Kubernetes services (multi-cluster)...")

    total_svc = 0
    total_pods = 0

    for cluster in K8S_CLUSTERS:
        try:
            # --- Services ---
            services_response = mcp.call_tool(
                "infrastructure", "kubectl_get_services",
                {"all_namespaces": True, "cluster": cluster},
            )
            services = extract_list(services_response, "services", "result")

            svc_rows = []
            for svc in services:
                name = svc.get("name")
                namespace = svc.get("namespace")
                if not name or not namespace:
                    continue

                svc_type = svc.get("type", "ClusterIP")
                cluster_ip = svc.get("cluster_ip", "")

                ports_list = svc.get("ports", [])
                ports_str = ", ".join(
                    f"{p.get('port', '')}:{p.get('target', '')}"
                    + (f" (NP:{p['nodePort']})" if p.get("nodePort") else "")
                    for p in ports_list
                ) if ports_list else ""

                deploy_info = (deploy_status or {}).get((name, namespace, cluster))
                if deploy_info:
                    svc_status = deploy_info["status"]
                    replicas_str = f"{deploy_info['ready']}/{deploy_info['replicas']}"
                else:
                    svc_status = "active" if svc_type in ("ClusterIP", "NodePort", "LoadBalancer") else "unknown"
                    replicas_str = ""

                is_bridge = svc_type == "ClusterIP" and not svc.get("selector")

                svc_rows.append({
                    "name": name,
                    "namespace": namespace,
                    "cluster": cluster,
                    "service_type": svc_type,
                    "cluster_ip": cluster_ip,
                    "ports": ports_str,
                    "status": svc_status,
                    "replicas": replicas_str,
                    "is_bridge": is_bridge,
                })

            if svc_rows:
                neo4j.batch_merge("""
                    MERGE (s:Service {name: row.name, namespace: row.namespace, cluster: row.cluster})
                    SET s.service_type = row.service_type,
                        s.cluster_ip = row.cluster_ip,
                        s.ports = row.ports,
                        s.status = row.status,
                        s.replicas = row.replicas,
                        s.is_bridge = row.is_bridge,
                        s.last_seen = datetime(),
                        s.source = 'kubernetes',
                        s._sync_status = 'active'
                """, svc_rows)

            total_svc += len(svc_rows)

            # --- Pods ---
            pods_response = mcp.call_tool(
                "infrastructure", "kubectl_get_pods",
                {"all_namespaces": True, "cluster": cluster},
            )
            pods = extract_list(pods_response, "pods", "result")

            pod_rows = []
            for pod in pods:
                name = pod.get("name")
                namespace = pod.get("namespace")
                if not name or not namespace:
                    continue

                phase = pod.get("status", "unknown")
                ready = pod.get("ready", False)
                restart_count = pod.get("restarts", 0)

                # Skip completed job pods
                if phase == "Succeeded":
                    continue

                if phase == "Running" and ready:
                    pod_status = "healthy"
                elif phase == "Running" and not ready:
                    pod_status = "degraded"
                elif phase in ("Failed", "Unknown"):
                    pod_status = "unhealthy"
                else:
                    pod_status = phase.lower() if phase else "unknown"

                pod_rows.append({
                    "name": name,
                    "namespace": namespace,
                    "cluster": cluster,
                    "phase": phase,
                    "status": pod_status,
                    "ready": ready,
                    "restart_count": restart_count,
                })

            if pod_rows:
                neo4j.batch_merge("""
                    MERGE (p:Pod {name: row.name, namespace: row.namespace, cluster: row.cluster})
                    SET p.phase = row.phase,
                        p.status = row.status,
                        p.ready = row.ready,
                        p.restart_count = row.restart_count,
                        p.last_seen = datetime(),
                        p.source = 'kubernetes',
                        p._sync_status = 'active'
                    WITH p, row
                    OPTIONAL MATCH (d:Deployment {namespace: row.namespace, cluster: row.cluster})
                    WHERE row.name STARTS WITH d.name + '-'
                    WITH p, d ORDER BY size(d.name) DESC LIMIT 1
                    FOREACH (_ IN CASE WHEN d IS NOT NULL THEN [1] ELSE [] END |
                        MERGE (p)-[:BELONGS_TO]->(d)
                    )
                """, pod_rows)

            total_pods += len(pod_rows)
            logger.info(f"  {cluster}: {len(svc_rows)} services, {len(pod_rows)} pods")
        except Exception as e:
            logger.error(f"  {cluster}: service/pod sync failed: {e}")

    logger.info(f"Synced {total_svc} services, {total_pods} pods across {len(K8S_CLUSTERS)} clusters")
    return total_svc


def sync_kubernetes_ingresses(neo4j: Neo4jClient, mcp: McpClient) -> int:
    """Sync Kubernetes ingresses from all clusters to Neo4j."""
    logger.info("Syncing Kubernetes ingresses (multi-cluster)...")

    total_count = 0

    for cluster in K8S_CLUSTERS:
        try:
            ingresses_response = mcp.call_tool(
                "infrastructure", "kubectl_get_ingresses",
                {"all_namespaces": True, "cluster": cluster},
            )
            ingresses = extract_list(ingresses_response, "ingresses", "result")

            count = 0
            for ing in ingresses:
                name = ing.get("name")
                namespace = ing.get("namespace")
                if not name or not namespace:
                    continue

                ingress_class = ing.get("class", "")
                has_tls = ing.get("tls", False)
                hosts_data = ing.get("hosts", [])

                all_hosts = []
                all_paths = []
                backend_services = []
                for h in hosts_data:
                    host = h.get("host", "*")
                    all_hosts.append(host)
                    for p in h.get("paths", []):
                        path = p.get("path", "/") if isinstance(p, dict) else p
                        svc_name = p.get("service", "") if isinstance(p, dict) else ""
                        port = p.get("port", "") if isinstance(p, dict) else ""
                        all_paths.append(f"{host}{path} -> {svc_name}:{port}" if svc_name else f"{host}{path}")
                        if svc_name:
                            backend_services.append((svc_name, namespace))

                ing_status = "active" if backend_services else "inactive"

                neo4j.write("""
                MERGE (i:Ingress {name: $name, namespace: $namespace, cluster: $cluster})
                SET i.ingress_class = $ingress_class,
                    i.hosts = $hosts,
                    i.paths = $paths,
                    i.tls = $tls,
                    i.status = $status,
                    i.last_seen = datetime(),
                    i.source = 'kubernetes',
                    i._sync_status = 'active'
                """, {
                    "name": name,
                    "namespace": namespace,
                    "cluster": cluster,
                    "ingress_class": ingress_class,
                    "hosts": ", ".join(all_hosts),
                    "paths": "; ".join(all_paths),
                    "tls": has_tls,
                    "status": ing_status,
                })
                count += 1

                # ROUTES_TO relationships to backend services
                for svc_name, svc_ns in backend_services:
                    neo4j.write("""
                    MATCH (i:Ingress {name: $ing_name, namespace: $namespace, cluster: $cluster})
                    MATCH (s:Service {name: $svc_name, namespace: $namespace, cluster: $cluster})
                    MERGE (i)-[:ROUTES_TO]->(s)
                    """, {
                        "ing_name": name,
                        "svc_name": svc_name,
                        "namespace": svc_ns,
                        "cluster": cluster,
                    })

            total_count += count
            logger.info(f"  {cluster}: {count} ingresses")
        except Exception as e:
            logger.error(f"  {cluster}: ingress sync failed: {e}")

    logger.info(f"Synced {total_count} ingresses across {len(K8S_CLUSTERS)} clusters")
    return total_count


def sync_kubernetes_nodes(neo4j: Neo4jClient, mcp: McpClient) -> int:
    """Sync Kubernetes node info from all clusters to Host nodes."""
    logger.info("Syncing Kubernetes nodes (multi-cluster)...")

    total_count = 0

    for cluster in K8S_CLUSTERS:
        try:
            nodes_response = mcp.call_tool(
                "infrastructure", "kubectl_get_nodes", {"cluster": cluster},
            )
            nodes = extract_list(nodes_response, "nodes", "result")

            host_rows = []
            for node in nodes:
                hostname = node.get("name", "")
                if not hostname:
                    continue

                k8s_ready = node.get("ready", False)
                k8s_version = node.get("version", "unknown")
                k8s_os = node.get("os", "unknown")
                conditions = node.get("conditions", {})
                conditions_str = (
                    ", ".join(f"{k}={v}" for k, v in conditions.items())
                    if isinstance(conditions, dict) else ""
                )

                if any(kw in hostname.lower() for kw in ("control", "master", "cp")):
                    k8s_role = "control-plane"
                else:
                    k8s_role = "worker"

                host_status = "healthy" if k8s_ready else "unhealthy"
                network_name = {"agentic": "agentic", "prod": "prod", "monit": "monitoring"}.get(cluster, cluster)

                host_rows.append({
                    "hostname": hostname,
                    "k8s_version": k8s_version,
                    "k8s_os": k8s_os,
                    "k8s_ready": k8s_ready,
                    "k8s_conditions": conditions_str,
                    "k8s_role": k8s_role,
                    "cluster": cluster,
                    "status": host_status,
                    "network": network_name,
                })

            if host_rows:
                neo4j.batch_merge("""
                    MERGE (h:Host {hostname: row.hostname})
                    SET h.k8s_version = row.k8s_version,
                        h.k8s_os = row.k8s_os,
                        h.k8s_ready = row.k8s_ready,
                        h.k8s_conditions = row.k8s_conditions,
                        h.k8s_role = row.k8s_role,
                        h.cluster = row.cluster,
                        h.status = row.status,
                        h.last_seen = datetime(),
                        h._sync_status = 'active'
                    WITH h, row
                    MERGE (n:Network {name: row.network})
                    MERGE (h)-[:CONNECTED_TO]->(n)
                """, host_rows)

                mark_active(neo4j, "Host",
                            [r["hostname"] for r in host_rows],
                            id_field="hostname")

            total_count += len(host_rows)
            logger.info(f"  {cluster}: {len(host_rows)} nodes")
        except Exception as e:
            logger.error(f"  {cluster}: node sync failed: {e}")

    logger.info(f"Synced {total_count} nodes across {len(K8S_CLUSTERS)} clusters")
    return total_count


def sync_kubernetes_pvcs(neo4j: Neo4jClient, mcp: McpClient) -> int:
    """Sync PVCs from all clusters to Neo4j."""
    logger.info("Syncing Kubernetes PVCs (multi-cluster)...")

    total_count = 0

    for cluster in K8S_CLUSTERS:
        try:
            pvcs_response = mcp.call_tool(
                "infrastructure", "kubectl_get_pvcs",
                {"all_namespaces": True, "cluster": cluster},
            )
            pvcs = extract_list(pvcs_response, "pvcs", "result")

            pvc_rows = []
            for pvc in pvcs:
                name = pvc.get("name")
                namespace = pvc.get("namespace")
                if not name or not namespace:
                    continue

                phase = pvc.get("status", "unknown").lower()
                capacity = pvc.get("capacity", "")
                storage_class = pvc.get("storage_class", "")
                volume_name = pvc.get("volume_name", "")
                pvc_status = {"bound": "healthy", "pending": "pending", "lost": "unhealthy"}.get(phase, phase)

                pvc_rows.append({
                    "name": name,
                    "namespace": namespace,
                    "cluster": cluster,
                    "status": pvc_status,
                    "capacity": capacity,
                    "storage_class": storage_class,
                    "volume_name": volume_name,
                })

            if pvc_rows:
                neo4j.batch_merge("""
                    MERGE (pvc:PersistentVolumeClaim {name: row.name, namespace: row.namespace, cluster: row.cluster})
                    SET pvc.status = row.status,
                        pvc.capacity = row.capacity,
                        pvc.storage_class = row.storage_class,
                        pvc.volume_name = row.volume_name,
                        pvc.last_seen = datetime(),
                        pvc.source = 'kubernetes',
                        pvc._sync_status = 'active'
                """, pvc_rows)

                # Link PVC->Service by namespace + name prefix
                neo4j.batch_merge("""
                    MATCH (pvc:PersistentVolumeClaim {name: row.name, namespace: row.namespace, cluster: row.cluster})
                    MATCH (s:Service {namespace: row.namespace, cluster: row.cluster})
                    WHERE row.name STARTS WITH s.name AND size(s.name) > 2
                    WITH pvc, s ORDER BY size(s.name) DESC LIMIT 1
                    MERGE (pvc)-[:CLAIMED_BY]->(s)
                """, pvc_rows)

            total_count += len(pvc_rows)
            logger.info(f"  {cluster}: {len(pvc_rows)} PVCs")
        except Exception as e:
            logger.error(f"  {cluster}: PVC sync failed: {e}")

    logger.info(f"Synced {total_count} PVCs across {len(K8S_CLUSTERS)} clusters")
    return total_count
