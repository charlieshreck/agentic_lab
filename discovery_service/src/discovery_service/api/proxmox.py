"""Multi-host synchronous Proxmox API client.

Supports multiple standalone Proxmox hosts (not clustered).
Each host has its own API endpoint and token credentials.
"""

import logging
import re

import httpx

logger = logging.getLogger(__name__)


class ProxmoxClient:
    """Multi-host synchronous Proxmox API client."""

    def __init__(self, hosts: dict[str, dict]):
        """Initialise per-host httpx clients with PVEAPIToken auth.

        Parameters
        ----------
        hosts : dict
            {"ruapehu": {"url": "https://...", "token_id": "...", "token_secret": "..."}, ...}
        """
        self._clients: dict[str, httpx.Client] = {}
        self._urls: dict[str, str] = {}

        for name, cfg in hosts.items():
            url = cfg.get("url", "").rstrip("/")
            token_id = cfg.get("token_id", "")
            token_secret = cfg.get("token_secret", "")

            if not url or not token_id or not token_secret:
                logger.warning(f"Proxmox host {name}: incomplete credentials, skipping")
                continue

            self._urls[name] = url
            self._clients[name] = httpx.Client(
                base_url=f"{url}/api2/json",
                headers={"Authorization": f"PVEAPIToken={token_id}={token_secret}"},
                verify=False,
                timeout=30.0,
            )
            logger.info(f"Proxmox client ready: {name} ({url})")

    @property
    def hosts(self) -> list[str]:
        return list(self._clients.keys())

    def _get(self, host: str, path: str) -> dict | list:
        resp = self._clients[host].get(path)
        resp.raise_for_status()
        return resp.json().get("data", {})

    def list_nodes(self, host: str) -> list[dict]:
        return self._get(host, "/nodes")

    def list_vms(self, host: str, node: str) -> list[dict]:
        return self._get(host, f"/nodes/{node}/qemu")

    def list_containers(self, host: str, node: str) -> list[dict]:
        return self._get(host, f"/nodes/{node}/lxc")

    def get_vm_config(self, host: str, node: str, vmid: int) -> dict:
        return self._get(host, f"/nodes/{node}/qemu/{vmid}/config")

    def get_vm_interfaces(self, host: str, node: str, vmid: int) -> list[dict]:
        """Get VM network interfaces via QEMU guest agent."""
        data = self._get(host, f"/nodes/{node}/qemu/{vmid}/agent/network-get-interfaces")
        if isinstance(data, dict):
            return data.get("result", [])
        return data if isinstance(data, list) else []

    def get_container_config(self, host: str, node: str, vmid: int) -> dict:
        return self._get(host, f"/nodes/{node}/lxc/{vmid}/config")

    def list_storage(self, host: str) -> list[dict]:
        return self._get(host, "/storage")

    def close(self):
        for client in self._clients.values():
            client.close()


def extract_vm_ip(interfaces: list[dict]) -> str:
    """Extract primary IPv4 address from QEMU guest agent interfaces."""
    for iface in interfaces:
        if iface.get("name") in ("lo", "lo0"):
            continue
        for addr in iface.get("ip-addresses", []):
            if addr.get("ip-address-type") == "ipv4":
                ip = addr.get("ip-address", "")
                if ip and not ip.startswith("127."):
                    return ip
    return ""


def extract_lxc_ip(config: dict) -> str:
    """Extract IPv4 address from LXC container config (net0/net1 fields)."""
    for key in ("net0", "net1", "net2"):
        net_str = config.get(key, "")
        if not net_str:
            continue
        # Format: name=eth0,bridge=vmbr0,ip=10.10.0.100/24,...
        match = re.search(r"ip=(\d+\.\d+\.\d+\.\d+)", net_str)
        if match:
            return match.group(1)
    return ""
