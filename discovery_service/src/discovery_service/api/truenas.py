"""Multi-instance synchronous TrueNAS API client.

Supports multiple TrueNAS SCALE instances with Bearer token auth.
"""

import logging

import httpx

logger = logging.getLogger(__name__)


class TrueNASClient:
    """Multi-instance synchronous TrueNAS API client."""

    def __init__(self, instances: dict[str, dict]):
        """Initialise per-instance httpx clients with Bearer token auth.

        Parameters
        ----------
        instances : dict
            {"hdd": {"url": "https://...", "api_key": "..."}, ...}
        """
        self._clients: dict[str, httpx.Client] = {}

        for name, cfg in instances.items():
            url = cfg.get("url", "").rstrip("/")
            api_key = cfg.get("api_key", "")

            if not url or not api_key:
                logger.warning(f"TrueNAS instance {name}: incomplete credentials, skipping")
                continue

            self._clients[name] = httpx.Client(
                base_url=f"{url}/api/v2.0",
                headers={"Authorization": f"Bearer {api_key}"},
                verify=False,
                timeout=30.0,
            )
            logger.info(f"TrueNAS client ready: {name} ({url})")

    @property
    def instances(self) -> list[str]:
        return list(self._clients.keys())

    def _get(self, instance: str, path: str) -> dict | list:
        resp = self._clients[instance].get(path)
        resp.raise_for_status()
        return resp.json()

    def list_pools(self, instance: str) -> list[dict]:
        return self._get(instance, "/pool")

    def list_datasets(self, instance: str) -> list[dict]:
        return self._get(instance, "/pool/dataset")

    def list_nfs_shares(self, instance: str) -> list[dict]:
        return self._get(instance, "/sharing/nfs")

    def list_smb_shares(self, instance: str) -> list[dict]:
        return self._get(instance, "/sharing/smb")

    def list_alerts(self, instance: str) -> list[dict]:
        return self._get(instance, "/alert/list")

    def list_apps(self, instance: str) -> list[dict]:
        return self._get(instance, "/app")

    def list_snapshots(self, instance: str) -> list[dict]:
        return self._get(instance, "/zfs/snapshot")

    def close(self):
        for client in self._clients.values():
            client.close()
