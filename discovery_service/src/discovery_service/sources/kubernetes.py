"""Sync Kubernetes resources to Neo4j using the Python kubernetes client.

Replaces MCP-based kubectl calls with direct API access to get full object
metadata: ownerReferences, spec.selector, spec.nodeName, metadata.labels.

High-volume sync functions use UNWIND batching for performance.
"""

import logging

from discovery_service.graph.client import Neo4jClient
from discovery_service.graph.lifecycle import mark_active
from discovery_service.kube.client import KubeClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ownership resolution (batch ReplicaSet lookup)
# ---------------------------------------------------------------------------

def _build_rs_owner_map(kube: KubeClient, cluster: str) -> dict[tuple[str, str], tuple[str, str]]:
    """Pre-fetch all ReplicaSets for a cluster and build an owner lookup dict.

    Returns {(rs_name, namespace): (owner_kind, owner_name)} for RS → Deployment/StatefulSet.
    """
    rs_map: dict[tuple[str, str], tuple[str, str]] = {}
    try:
        rs_list = kube.apps_v1(cluster).list_replica_set_for_all_namespaces()
        for rs in rs_list.items:
            if not rs.metadata.owner_references:
                continue
            for ref in rs.metadata.owner_references:
                if ref.kind in ("Deployment", "StatefulSet"):
                    rs_map[(rs.metadata.name, rs.metadata.namespace)] = (ref.kind, ref.name)
                    break
    except Exception as e:
        logger.warning(f"  {cluster}: failed to build RS owner map: {e}")
    return rs_map


def _resolve_owner(rs_map: dict[tuple[str, str], tuple[str, str]], namespace: str, owner_refs) -> tuple[str, str] | None:
    """Resolve ownerReferences chain using pre-built RS lookup dict.

    Returns (kind, name) of the ultimate owner or None.
    """
    if not owner_refs:
        return None
    for ref in owner_refs:
        if ref.kind == "ReplicaSet":
            result = rs_map.get((ref.name, namespace))
            if result:
                return result
        elif ref.kind in ("StatefulSet", "DaemonSet", "Job"):
            return (ref.kind, ref.name)
    return None


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def sync_kubernetes_nodes(neo4j: Neo4jClient, kube: KubeClient) -> int:
    """Sync Kubernetes node info from all clusters to Host nodes."""
    logger.info("Syncing Kubernetes nodes (multi-cluster)...")

    total_count = 0

    for cluster in kube.clusters:
        try:
            nodes = kube.core_v1(cluster).list_node()

            host_rows = []
            for node in nodes.items:
                hostname = node.metadata.name
                if not hostname:
                    continue

                # Extract conditions
                conditions = {}
                k8s_ready = False
                if node.status.conditions:
                    for cond in node.status.conditions:
                        conditions[cond.type] = cond.status
                        if cond.type == "Ready":
                            k8s_ready = cond.status == "True"

                conditions_str = ", ".join(f"{k}={v}" for k, v in conditions.items())

                k8s_version = node.status.node_info.kubelet_version if node.status.node_info else "unknown"
                k8s_os = node.status.node_info.os_image if node.status.node_info else "unknown"

                # Extract internal IP from status.addresses
                internal_ip = ""
                if node.status.addresses:
                    for addr in node.status.addresses:
                        if addr.type == "InternalIP":
                            internal_ip = addr.address
                            break

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
                    "internal_ip": internal_ip,
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
                        h.internal_ip = row.internal_ip,
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

    logger.info(f"Synced {total_count} nodes across {len(kube.clusters)} clusters")
    return total_count


# ---------------------------------------------------------------------------
# Deployments
# ---------------------------------------------------------------------------

def sync_kubernetes_deployments(neo4j: Neo4jClient, kube: KubeClient) -> dict:
    """Sync Kubernetes deployments from all clusters. Returns deploy_status lookup dict."""
    logger.info("Syncing Kubernetes deployments (multi-cluster)...")

    deploy_status: dict[tuple, dict] = {}
    total_count = 0

    for cluster in kube.clusters:
        try:
            deploys = kube.apps_v1(cluster).list_deployment_for_all_namespaces()

            rows = []
            for d in deploys.items:
                name = d.metadata.name
                namespace = d.metadata.namespace
                if not name or not namespace:
                    continue

                replicas = d.spec.replicas or 0
                ready = d.status.ready_replicas or 0
                available = d.status.available_replicas or 0

                if replicas == 0:
                    status = "scaled-down"
                elif ready >= replicas:
                    status = "healthy"
                elif ready > 0:
                    status = "degraded"
                else:
                    status = "unhealthy"

                # Extract selector matchLabels for later pod linking
                selector_labels = {}
                if d.spec.selector and d.spec.selector.match_labels:
                    selector_labels = dict(d.spec.selector.match_labels)

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
                    "selector": str(selector_labels) if selector_labels else "",
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

    logger.info(f"Synced {total_count} deployments across {len(kube.clusters)} clusters")
    return deploy_status


# ---------------------------------------------------------------------------
# StatefulSets (NEW)
# ---------------------------------------------------------------------------

def sync_kubernetes_statefulsets(neo4j: Neo4jClient, kube: KubeClient) -> int:
    """Sync Kubernetes StatefulSets from all clusters."""
    logger.info("Syncing Kubernetes StatefulSets (multi-cluster)...")

    total_count = 0

    for cluster in kube.clusters:
        try:
            sts_list = kube.apps_v1(cluster).list_stateful_set_for_all_namespaces()

            rows = []
            for sts in sts_list.items:
                name = sts.metadata.name
                namespace = sts.metadata.namespace
                if not name or not namespace:
                    continue

                replicas = sts.spec.replicas or 0
                ready = sts.status.ready_replicas or 0

                if replicas == 0:
                    status = "scaled-down"
                elif ready >= replicas:
                    status = "healthy"
                elif ready > 0:
                    status = "degraded"
                else:
                    status = "unhealthy"

                selector_labels = {}
                if sts.spec.selector and sts.spec.selector.match_labels:
                    selector_labels = dict(sts.spec.selector.match_labels)

                rows.append({
                    "name": name,
                    "namespace": namespace,
                    "cluster": cluster,
                    "replicas": replicas,
                    "ready": ready,
                    "status": status,
                    "selector": str(selector_labels) if selector_labels else "",
                    "service_name": sts.spec.service_name or "",
                })

            if rows:
                neo4j.batch_merge("""
                    MERGE (sts:StatefulSet {name: row.name, namespace: row.namespace, cluster: row.cluster})
                    SET sts.replicas = row.replicas,
                        sts.ready_replicas = row.ready,
                        sts.status = row.status,
                        sts.selector = row.selector,
                        sts.service_name = row.service_name,
                        sts.last_seen = datetime(),
                        sts.source = 'kubernetes',
                        sts._sync_status = 'active'
                """, rows)

                # BACKED_BY: headless service -> StatefulSet
                neo4j.batch_merge("""
                    MATCH (s:Service {namespace: row.namespace, cluster: row.cluster})
                    WHERE s.name = row.service_name
                    MATCH (sts:StatefulSet {name: row.name, namespace: row.namespace, cluster: row.cluster})
                    MERGE (s)-[:BACKED_BY]->(sts)
                """, [r for r in rows if r["service_name"]])

                mark_active(neo4j, "StatefulSet",
                            [f"{r['name']}|{r['namespace']}|{r['cluster']}" for r in rows],
                            id_field="name")

            total_count += len(rows)
            logger.info(f"  {cluster}: {len(rows)} StatefulSets")
        except Exception as e:
            logger.error(f"  {cluster}: StatefulSet sync failed: {e}")

    logger.info(f"Synced {total_count} StatefulSets across {len(kube.clusters)} clusters")
    return total_count


# ---------------------------------------------------------------------------
# DaemonSets
# ---------------------------------------------------------------------------

def sync_kubernetes_daemonsets(neo4j: Neo4jClient, kube: KubeClient) -> int:
    """Sync Kubernetes DaemonSets from all clusters."""
    logger.info("Syncing Kubernetes DaemonSets (multi-cluster)...")

    total_count = 0

    for cluster in kube.clusters:
        try:
            ds_list = kube.apps_v1(cluster).list_daemon_set_for_all_namespaces()

            rows = []
            for ds in ds_list.items:
                name = ds.metadata.name
                namespace = ds.metadata.namespace
                if not name or not namespace:
                    continue

                desired = ds.status.desired_number_scheduled or 0
                ready = ds.status.number_ready or 0
                available = ds.status.number_available or 0

                if desired == 0:
                    status = "scaled-down"
                elif ready >= desired:
                    status = "healthy"
                elif ready > 0:
                    status = "degraded"
                else:
                    status = "unhealthy"

                selector_labels = {}
                if ds.spec.selector and ds.spec.selector.match_labels:
                    selector_labels = dict(ds.spec.selector.match_labels)

                rows.append({
                    "name": name,
                    "namespace": namespace,
                    "cluster": cluster,
                    "desired": desired,
                    "ready": ready,
                    "available": available,
                    "status": status,
                    "selector": str(selector_labels) if selector_labels else "",
                })

            if rows:
                neo4j.batch_merge("""
                    MERGE (ds:DaemonSet {name: row.name, namespace: row.namespace, cluster: row.cluster})
                    SET ds.desired = row.desired,
                        ds.ready = row.ready,
                        ds.available = row.available,
                        ds.status = row.status,
                        ds.selector = row.selector,
                        ds.last_seen = datetime(),
                        ds.source = 'kubernetes',
                        ds._sync_status = 'active'
                """, rows)

                mark_active(neo4j, "DaemonSet",
                            [f"{r['name']}|{r['namespace']}|{r['cluster']}" for r in rows],
                            id_field="name")

            total_count += len(rows)
            logger.info(f"  {cluster}: {len(rows)} DaemonSets")
        except Exception as e:
            logger.error(f"  {cluster}: DaemonSet sync failed: {e}")

    logger.info(f"Synced {total_count} DaemonSets across {len(kube.clusters)} clusters")
    return total_count


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

def sync_kubernetes_services(neo4j: Neo4jClient, kube: KubeClient, deploy_status: dict | None = None) -> int:
    """Sync Kubernetes services from all clusters to Neo4j.

    Extracts spec.selector for later pod linking via link_services_to_pods().
    """
    logger.info("Syncing Kubernetes services (multi-cluster)...")

    total_svc = 0

    for cluster in kube.clusters:
        try:
            services = kube.core_v1(cluster).list_service_for_all_namespaces()

            svc_rows = []
            for svc in services.items:
                name = svc.metadata.name
                namespace = svc.metadata.namespace
                if not name or not namespace:
                    continue

                svc_type = svc.spec.type or "ClusterIP"
                cluster_ip = svc.spec.cluster_ip or ""

                # Format ports
                ports_str = ""
                if svc.spec.ports:
                    port_parts = []
                    for p in svc.spec.ports:
                        part = f"{p.port}:{p.target_port}"
                        if p.node_port:
                            part += f" (NP:{p.node_port})"
                        port_parts.append(part)
                    ports_str = ", ".join(port_parts)

                deploy_info = (deploy_status or {}).get((name, namespace, cluster))
                if deploy_info:
                    svc_status = deploy_info["status"]
                    replicas_str = f"{deploy_info['ready']}/{deploy_info['replicas']}"
                else:
                    svc_status = "active" if svc_type in ("ClusterIP", "NodePort", "LoadBalancer") else "unknown"
                    replicas_str = ""

                # Extract selector for pod linking
                selector = dict(svc.spec.selector) if svc.spec.selector else {}
                is_bridge = svc_type == "ClusterIP" and not selector

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
                    "selector": str(selector) if selector else "",
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
                        s.selector = row.selector,
                        s.last_seen = datetime(),
                        s.source = 'kubernetes',
                        s._sync_status = 'active'
                """, svc_rows)

            total_svc += len(svc_rows)
            logger.info(f"  {cluster}: {len(svc_rows)} services")
        except Exception as e:
            logger.error(f"  {cluster}: service sync failed: {e}")

    logger.info(f"Synced {total_svc} services across {len(kube.clusters)} clusters")
    return total_svc


# ---------------------------------------------------------------------------
# Pods
# ---------------------------------------------------------------------------

def sync_kubernetes_pods(neo4j: Neo4jClient, kube: KubeClient) -> int:
    """Sync Kubernetes pods from all clusters.

    Extracts ownerReferences for accurate Pod->Deployment/StatefulSet linking
    and spec.nodeName for Pod->Host SCHEDULED_ON relationships.
    """
    logger.info("Syncing Kubernetes pods (multi-cluster)...")

    total_pods = 0

    for cluster in kube.clusters:
        try:
            # Pre-fetch all ReplicaSets for batch ownership resolution
            rs_map = _build_rs_owner_map(kube, cluster)
            logger.info(f"  {cluster}: built RS owner map ({len(rs_map)} entries)")

            pods = kube.core_v1(cluster).list_pod_for_all_namespaces()

            pod_rows = []
            ownership_rows = []  # (pod_name, pod_ns, cluster, owner_kind, owner_name)
            schedule_rows = []   # (pod_name, pod_ns, cluster, node_name)

            for pod in pods.items:
                name = pod.metadata.name
                namespace = pod.metadata.namespace
                if not name or not namespace:
                    continue

                phase = pod.status.phase or "Unknown"

                # Determine readiness from container statuses
                ready = False
                restart_count = 0
                if pod.status.container_statuses:
                    ready = all(cs.ready for cs in pod.status.container_statuses)
                    restart_count = sum(cs.restart_count for cs in pod.status.container_statuses)

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

                # Extract labels for service selector matching
                labels = dict(pod.metadata.labels) if pod.metadata.labels else {}

                pod_rows.append({
                    "name": name,
                    "namespace": namespace,
                    "cluster": cluster,
                    "phase": phase,
                    "status": pod_status,
                    "ready": ready,
                    "restart_count": restart_count,
                    "labels": str(labels) if labels else "",
                })

                # Resolve ownership via ownerReferences (batch RS lookup)
                owner = _resolve_owner(rs_map, namespace, pod.metadata.owner_references)
                if owner:
                    ownership_rows.append({
                        "pod_name": name,
                        "pod_ns": namespace,
                        "cluster": cluster,
                        "owner_kind": owner[0],
                        "owner_name": owner[1],
                    })

                # Pod -> Host scheduling
                node_name = pod.spec.node_name
                if node_name:
                    schedule_rows.append({
                        "pod_name": name,
                        "pod_ns": namespace,
                        "cluster": cluster,
                        "node_name": node_name,
                    })

            if pod_rows:
                neo4j.batch_merge("""
                    MERGE (p:Pod {name: row.name, namespace: row.namespace, cluster: row.cluster})
                    SET p.phase = row.phase,
                        p.status = row.status,
                        p.ready = row.ready,
                        p.restart_count = row.restart_count,
                        p.labels = row.labels,
                        p.last_seen = datetime(),
                        p.source = 'kubernetes',
                        p._sync_status = 'active'
                """, pod_rows)

            # BELONGS_TO: Pod -> Deployment (via ownerReferences)
            deploy_owners = [r for r in ownership_rows if r["owner_kind"] == "Deployment"]
            if deploy_owners:
                neo4j.batch_merge("""
                    MATCH (p:Pod {name: row.pod_name, namespace: row.pod_ns, cluster: row.cluster})
                    MATCH (d:Deployment {name: row.owner_name, namespace: row.pod_ns, cluster: row.cluster})
                    MERGE (p)-[:BELONGS_TO]->(d)
                """, deploy_owners)

            # BELONGS_TO: Pod -> StatefulSet (via ownerReferences)
            sts_owners = [r for r in ownership_rows if r["owner_kind"] == "StatefulSet"]
            if sts_owners:
                neo4j.batch_merge("""
                    MATCH (p:Pod {name: row.pod_name, namespace: row.pod_ns, cluster: row.cluster})
                    MATCH (sts:StatefulSet {name: row.owner_name, namespace: row.pod_ns, cluster: row.cluster})
                    MERGE (p)-[:BELONGS_TO]->(sts)
                """, sts_owners)

            # BELONGS_TO: Pod -> DaemonSet (via ownerReferences)
            ds_owners = [r for r in ownership_rows if r["owner_kind"] == "DaemonSet"]
            if ds_owners:
                neo4j.batch_merge("""
                    MATCH (p:Pod {name: row.pod_name, namespace: row.pod_ns, cluster: row.cluster})
                    MATCH (ds:DaemonSet {name: row.owner_name, namespace: row.pod_ns, cluster: row.cluster})
                    MERGE (p)-[:BELONGS_TO]->(ds)
                """, ds_owners)

            # SCHEDULED_ON: Pod -> Host (via spec.nodeName)
            if schedule_rows:
                neo4j.batch_merge("""
                    MATCH (p:Pod {name: row.pod_name, namespace: row.pod_ns, cluster: row.cluster})
                    MATCH (h:Host {hostname: row.node_name})
                    MERGE (p)-[:SCHEDULED_ON]->(h)
                """, schedule_rows)

            total_pods += len(pod_rows)
            logger.info(f"  {cluster}: {len(pod_rows)} pods ({len(deploy_owners)} deploy, {len(sts_owners)} sts, {len(ds_owners)} ds, {len(schedule_rows)} scheduled)")
        except Exception as e:
            logger.error(f"  {cluster}: pod sync failed: {e}")

    logger.info(f"Synced {total_pods} pods across {len(kube.clusters)} clusters")
    return total_pods


# ---------------------------------------------------------------------------
# Service -> Pod linking (post-sync pass)
# ---------------------------------------------------------------------------

def link_services_to_pods(neo4j: Neo4jClient, kube: KubeClient) -> int:
    """Post-sync pass: create SELECTS relationships from Services to Pods based on label selectors.

    For each Service that has a selector, find Pods in the same namespace/cluster
    whose labels are a superset of the selector.
    """
    logger.info("Linking services to pods via selectors...")

    total_links = 0

    for cluster in kube.clusters:
        try:
            services = kube.core_v1(cluster).list_service_for_all_namespaces()

            for svc in services.items:
                selector = svc.spec.selector
                if not selector:
                    continue

                name = svc.metadata.name
                namespace = svc.metadata.namespace

                # Build a label selector string for the K8s API
                label_selector = ",".join(f"{k}={v}" for k, v in selector.items())

                try:
                    matching_pods = kube.core_v1(cluster).list_namespaced_pod(
                        namespace=namespace,
                        label_selector=label_selector,
                    )
                except Exception:
                    continue

                if not matching_pods.items:
                    continue

                link_rows = []
                for pod in matching_pods.items:
                    if pod.status.phase == "Succeeded":
                        continue
                    link_rows.append({
                        "svc_name": name,
                        "pod_name": pod.metadata.name,
                        "namespace": namespace,
                        "cluster": cluster,
                    })

                if link_rows:
                    neo4j.batch_merge("""
                        MATCH (s:Service {name: row.svc_name, namespace: row.namespace, cluster: row.cluster})
                        MATCH (p:Pod {name: row.pod_name, namespace: row.namespace, cluster: row.cluster})
                        MERGE (s)-[:SELECTS]->(p)
                    """, link_rows)
                    total_links += len(link_rows)

            logger.info(f"  {cluster}: {total_links} service->pod links")
        except Exception as e:
            logger.error(f"  {cluster}: service->pod linking failed: {e}")

    logger.info(f"Created {total_links} service->pod SELECTS relationships")
    return total_links


# ---------------------------------------------------------------------------
# Ingresses
# ---------------------------------------------------------------------------

def sync_kubernetes_ingresses(neo4j: Neo4jClient, kube: KubeClient) -> int:
    """Sync Kubernetes ingresses from all clusters to Neo4j."""
    logger.info("Syncing Kubernetes ingresses (multi-cluster)...")

    total_count = 0

    for cluster in kube.clusters:
        try:
            ingresses = kube.networking_v1(cluster).list_ingress_for_all_namespaces()

            count = 0
            for ing in ingresses.items:
                name = ing.metadata.name
                namespace = ing.metadata.namespace
                if not name or not namespace:
                    continue

                ingress_class = ing.spec.ingress_class_name or ""
                has_tls = bool(ing.spec.tls)

                all_hosts = []
                all_paths = []
                backend_services = []

                if ing.spec.rules:
                    for rule in ing.spec.rules:
                        host = rule.host or "*"
                        all_hosts.append(host)
                        if rule.http and rule.http.paths:
                            for p in rule.http.paths:
                                path = p.path or "/"
                                svc_name = ""
                                port = ""
                                if p.backend and p.backend.service:
                                    svc_name = p.backend.service.name or ""
                                    if p.backend.service.port:
                                        port = str(p.backend.service.port.number or p.backend.service.port.name or "")
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

    logger.info(f"Synced {total_count} ingresses across {len(kube.clusters)} clusters")
    return total_count


# ---------------------------------------------------------------------------
# PVCs
# ---------------------------------------------------------------------------

def sync_kubernetes_pvcs(neo4j: Neo4jClient, kube: KubeClient) -> int:
    """Sync PVCs from all clusters to Neo4j."""
    logger.info("Syncing Kubernetes PVCs (multi-cluster)...")

    total_count = 0

    for cluster in kube.clusters:
        try:
            pvcs = kube.core_v1(cluster).list_persistent_volume_claim_for_all_namespaces()

            pvc_rows = []
            for pvc in pvcs.items:
                name = pvc.metadata.name
                namespace = pvc.metadata.namespace
                if not name or not namespace:
                    continue

                phase = (pvc.status.phase or "unknown").lower()
                capacity = ""
                if pvc.status.capacity:
                    capacity = pvc.status.capacity.get("storage", "")
                storage_class = pvc.spec.storage_class_name or ""
                volume_name = pvc.spec.volume_name or ""
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

    logger.info(f"Synced {total_count} PVCs across {len(kube.clusters)} clusters")
    return total_count
