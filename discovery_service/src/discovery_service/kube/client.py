"""Multi-cluster Kubernetes API client.

Uses per-cluster ApiClient instances to avoid global state issues
with the kubernetes library.
"""

import logging
import os

from kubernetes import config
from kubernetes.client import ApiClient, AppsV1Api, CoreV1Api, NetworkingV1Api
from kubernetes.config import new_client_from_config

logger = logging.getLogger(__name__)


class KubeClient:
    """Multi-cluster Kubernetes API client.

    Parameters
    ----------
    kubeconfigs : dict[str, str | None]
        Mapping of cluster name to kubeconfig file path.
        ``None`` means use the in-cluster service account.
    """

    def __init__(self, kubeconfigs: dict[str, str | None]):
        self._clients: dict[str, ApiClient] = {}
        for cluster, path in kubeconfigs.items():
            try:
                if path is None:
                    config.load_incluster_config()
                    self._clients[cluster] = ApiClient()
                    logger.info(f"  {cluster}: using in-cluster service account")
                elif os.path.exists(path):
                    self._clients[cluster] = new_client_from_config(config_file=path)
                    logger.info(f"  {cluster}: loaded kubeconfig from {path}")
                else:
                    logger.warning(f"  {cluster}: kubeconfig not found at {path}, skipping")
            except Exception as e:
                logger.error(f"  {cluster}: failed to create client: {e}")

    @property
    def clusters(self) -> list[str]:
        """Return list of successfully initialised cluster names."""
        return list(self._clients.keys())

    def core_v1(self, cluster: str) -> CoreV1Api:
        return CoreV1Api(self._clients[cluster])

    def apps_v1(self, cluster: str) -> AppsV1Api:
        return AppsV1Api(self._clients[cluster])

    def networking_v1(self, cluster: str) -> NetworkingV1Api:
        return NetworkingV1Api(self._clients[cluster])

    def close(self):
        for client in self._clients.values():
            try:
                client.close()
            except Exception:
                pass
