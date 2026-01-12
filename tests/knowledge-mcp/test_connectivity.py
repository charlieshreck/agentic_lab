"""
Test knowledge-mcp connectivity and basic health.
"""

import pytest
import httpx


class TestConnectivity:
    """Test MCP server connectivity."""

    @pytest.mark.integration
    def test_mcp_server_reachable(self, mcp_client):
        """Verify knowledge-mcp server is reachable."""
        try:
            response = mcp_client.get("/health")
            assert response.status_code == 200
        except httpx.ConnectError:
            pytest.fail("Cannot connect to knowledge-mcp server")

    @pytest.mark.integration
    def test_mcp_tools_endpoint(self, mcp_client):
        """Verify MCP tools endpoint returns tool list."""
        response = mcp_client.get("/tools")
        assert response.status_code == 200
        tools = response.json()
        assert isinstance(tools, list)
        assert len(tools) > 0

    @pytest.mark.integration
    def test_required_tools_available(self, mcp_client):
        """Verify required tools are available."""
        response = mcp_client.get("/tools")
        tools = response.json()
        tool_names = [t.get("name") for t in tools]

        required_tools = [
            "search_runbooks",
            "search_docs",
            "search_entities",
            "get_entity",
        ]

        for tool in required_tools:
            assert tool in tool_names, f"Required tool '{tool}' not found"

    @pytest.mark.integration
    def test_qdrant_connection(self, mcp_client):
        """Verify Qdrant database is accessible via MCP."""
        # Attempt a simple search that requires Qdrant
        payload = {
            "tool": "search_docs",
            "arguments": {"query": "test"}
        }
        response = mcp_client.post("/invoke", json=payload)
        # Even if no results, should not error
        assert response.status_code in [200, 404]


class TestCollections:
    """Test Qdrant collection existence."""

    @pytest.mark.integration
    def test_collections_exist(self, mcp_client, qdrant_collections):
        """Verify expected Qdrant collections exist."""
        # This assumes knowledge-mcp has a list_collections tool
        payload = {
            "tool": "list_collections",
            "arguments": {}
        }
        response = mcp_client.post("/invoke", json=payload)

        if response.status_code == 200:
            result = response.json()
            existing = result.get("collections", [])

            for collection in qdrant_collections:
                assert collection in existing, f"Collection '{collection}' not found"
        else:
            pytest.skip("list_collections tool not available")


class TestEnvironment:
    """Test environment configuration."""

    @pytest.mark.unit
    def test_mcp_url_configured(self, knowledge_mcp_url):
        """Verify MCP URL is properly configured."""
        assert knowledge_mcp_url is not None
        assert knowledge_mcp_url.startswith("http")

    @pytest.mark.unit
    def test_cluster_network_in_url(self, knowledge_mcp_url):
        """Verify URL uses cluster-internal addressing when expected."""
        # In-cluster URL should use service discovery
        if "svc.cluster.local" in knowledge_mcp_url:
            assert "ai-platform" in knowledge_mcp_url
        # External URL should use node IP
        elif "10.20.0.40" in knowledge_mcp_url:
            assert ":31" in knowledge_mcp_url  # NodePort range
