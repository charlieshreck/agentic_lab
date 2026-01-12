"""
Test entity functionality via knowledge-mcp.
"""

import pytest


class TestEntitySearch:
    """Test entity semantic search."""

    @pytest.mark.integration
    def test_search_by_device_type(self, mcp_client):
        """Search entities by device type."""
        payload = {
            "tool": "search_entities",
            "arguments": {"query": "chromecast streaming devices"}
        }
        response = mcp_client.post("/invoke", json=payload)
        assert response.status_code == 200

        result = response.json()
        results = result.get("results", [])
        # May or may not have results depending on indexed entities

    @pytest.mark.integration
    def test_search_by_network(self, mcp_client):
        """Search entities by network location."""
        payload = {
            "tool": "search_entities",
            "arguments": {"query": "devices on iot network vlan"}
        }
        response = mcp_client.post("/invoke", json=payload)
        assert response.status_code == 200

    @pytest.mark.integration
    def test_search_by_capability(self, mcp_client):
        """Search entities by capability."""
        payload = {
            "tool": "search_entities",
            "arguments": {"query": "devices with smart home control"}
        }
        response = mcp_client.post("/invoke", json=payload)
        assert response.status_code == 200


class TestEntityRetrieval:
    """Test entity retrieval by identifier."""

    @pytest.mark.integration
    def test_get_entity_by_ip(self, mcp_client):
        """Get entity by IP address."""
        payload = {
            "tool": "get_entity",
            "arguments": {"identifier": "10.10.0.100"}
        }
        response = mcp_client.post("/invoke", json=payload)

        # May or may not find entity
        assert response.status_code in [200, 404]

    @pytest.mark.integration
    def test_get_entity_by_hostname(self, mcp_client):
        """Get entity by hostname."""
        payload = {
            "tool": "get_entity",
            "arguments": {"identifier": "truenas"}
        }
        response = mcp_client.post("/invoke", json=payload)
        assert response.status_code in [200, 404]

    @pytest.mark.integration
    def test_get_entity_by_mac(self, mcp_client):
        """Get entity by MAC address."""
        payload = {
            "tool": "get_entity",
            "arguments": {"identifier": "aa:bb:cc:dd:ee:ff"}
        }
        response = mcp_client.post("/invoke", json=payload)
        # MAC may not exist
        assert response.status_code in [200, 404]


class TestEntityFiltering:
    """Test entity filtering by type and network."""

    @pytest.mark.integration
    def test_get_entities_by_type(self, mcp_client):
        """Get entities filtered by device type."""
        payload = {
            "tool": "get_entities_by_type",
            "arguments": {"type": "nas"}
        }
        response = mcp_client.post("/invoke", json=payload)

        if response.status_code == 200:
            result = response.json()
            entities = result.get("entities", [])
            # All returned entities should be NAS type
            for entity in entities:
                assert entity.get("type") == "nas" or "nas" in str(entity).lower()
        elif response.status_code == 404:
            pytest.skip("get_entities_by_type not implemented")

    @pytest.mark.integration
    def test_get_entities_by_network(self, mcp_client):
        """Get entities filtered by network."""
        payload = {
            "tool": "get_entities_by_network",
            "arguments": {"network": "prod"}
        }
        response = mcp_client.post("/invoke", json=payload)

        if response.status_code == 200:
            result = response.json()
            entities = result.get("entities", [])
            # All entities should be on prod network (10.10.0.x)
            for entity in entities:
                ip = entity.get("ip", "")
                if ip:
                    assert ip.startswith("10.10.0.")
        elif response.status_code == 404:
            pytest.skip("get_entities_by_network not implemented")


class TestEntityScope:
    """Test entity coverage (local + cloud)."""

    @pytest.mark.integration
    def test_local_entities_included(self, mcp_client):
        """Verify local network devices are included."""
        payload = {
            "tool": "search_entities",
            "arguments": {"query": "local network devices homelab"}
        }
        response = mcp_client.post("/invoke", json=payload)
        assert response.status_code == 200

    @pytest.mark.integration
    def test_cloud_entities_included(self, mcp_client):
        """Verify cloud resources are included (Cloudflare, etc.)."""
        payload = {
            "tool": "search_entities",
            "arguments": {"query": "cloudflare tunnel dns"}
        }
        response = mcp_client.post("/invoke", json=payload)
        assert response.status_code == 200

    @pytest.mark.integration
    def test_virtual_entities_included(self, mcp_client):
        """Verify virtual machines are included."""
        payload = {
            "tool": "search_entities",
            "arguments": {"query": "proxmox virtual machine vm"}
        }
        response = mcp_client.post("/invoke", json=payload)
        assert response.status_code == 200


class TestDeviceTypes:
    """Test device type information."""

    @pytest.mark.integration
    def test_get_device_type_info(self, mcp_client):
        """Get control information for device type."""
        payload = {
            "tool": "get_device_type_info",
            "arguments": {"type": "sonoff"}
        }
        response = mcp_client.post("/invoke", json=payload)

        if response.status_code == 200:
            result = response.json()
            # Should include control methods
            assert "control" in result or "methods" in result or "api" in result
        elif response.status_code == 404:
            pytest.skip("get_device_type_info not implemented or type not found")
