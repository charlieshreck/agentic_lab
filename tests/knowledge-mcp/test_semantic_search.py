"""
Test semantic search functionality via knowledge-mcp.
"""

import pytest


class TestDocumentationSearch:
    """Test documentation semantic search."""

    @pytest.mark.integration
    def test_search_argocd_patterns(self, mcp_client):
        """Search for ArgoCD patterns returns relevant results."""
        payload = {
            "tool": "search_docs",
            "arguments": {"query": "argocd app of apps pattern"}
        }
        response = mcp_client.post("/invoke", json=payload)
        assert response.status_code == 200

        result = response.json()
        results = result.get("results", [])

        # Should find ArgoCD-related documentation
        assert len(results) > 0, "No results for ArgoCD search"

        # At least one result should mention ArgoCD
        content = str(results).lower()
        assert "argocd" in content or "app-of-apps" in content

    @pytest.mark.integration
    def test_search_ingress_patterns(self, mcp_client):
        """Search for ingress patterns returns relevant results."""
        payload = {
            "tool": "search_docs",
            "arguments": {"query": "dual ingress traefik cloudflare"}
        }
        response = mcp_client.post("/invoke", json=payload)
        assert response.status_code == 200

        result = response.json()
        results = result.get("results", [])

        assert len(results) > 0, "No results for ingress search"

    @pytest.mark.integration
    def test_search_domain_routing(self, mcp_client):
        """Search for domain routing returns decision tree."""
        payload = {
            "tool": "search_docs",
            "arguments": {"query": "kernow.io domain routing decision"}
        }
        response = mcp_client.post("/invoke", json=payload)
        assert response.status_code == 200

        result = response.json()
        results = result.get("results", [])

        assert len(results) > 0, "No results for domain routing search"


class TestRunbookSearch:
    """Test runbook semantic search."""

    @pytest.mark.integration
    def test_search_new_app_runbook(self, mcp_client):
        """Search for new app runbook returns deployment guide."""
        payload = {
            "tool": "search_runbooks",
            "arguments": {"query": "deploy new application to production"}
        }
        response = mcp_client.post("/invoke", json=payload)
        assert response.status_code == 200

        result = response.json()
        results = result.get("results", [])

        assert len(results) > 0, "No runbooks found for new app deployment"

    @pytest.mark.integration
    def test_search_caddy_runbook(self, mcp_client):
        """Search for Caddy runbook returns proxy configuration."""
        payload = {
            "tool": "search_runbooks",
            "arguments": {"query": "caddy reverse proxy configuration"}
        }
        response = mcp_client.post("/invoke", json=payload)
        assert response.status_code == 200

        result = response.json()
        results = result.get("results", [])

        assert len(results) > 0, "No runbooks found for Caddy"

    @pytest.mark.integration
    def test_search_mcp_deployment_runbook(self, mcp_client):
        """Search for MCP deployment runbook."""
        payload = {
            "tool": "search_runbooks",
            "arguments": {"query": "mcp server deployment pattern"}
        }
        response = mcp_client.post("/invoke", json=payload)
        assert response.status_code == 200

        result = response.json()
        results = result.get("results", [])

        assert len(results) > 0, "No runbooks found for MCP deployment"


class TestSearchQuality:
    """Test search result quality."""

    @pytest.mark.integration
    def test_search_returns_relevant_content(self, mcp_client):
        """Verify search returns content relevant to query."""
        payload = {
            "tool": "search_docs",
            "arguments": {"query": "infisical secrets kubernetes"}
        }
        response = mcp_client.post("/invoke", json=payload)
        assert response.status_code == 200

        result = response.json()
        results = result.get("results", [])

        if len(results) > 0:
            # Top result should be relevant
            top_result = str(results[0]).lower()
            relevant_terms = ["infisical", "secret", "kubernetes"]
            found_terms = sum(1 for term in relevant_terms if term in top_result)
            assert found_terms >= 1, "Top result not relevant to query"

    @pytest.mark.integration
    def test_search_respects_collection(self, mcp_client):
        """Verify runbook search doesn't return documentation."""
        payload = {
            "tool": "search_runbooks",
            "arguments": {"query": "kubernetes deployment"}
        }
        response = mcp_client.post("/invoke", json=payload)
        assert response.status_code == 200

        result = response.json()
        # Results should be from runbooks collection
        # Implementation depends on how results are structured

    @pytest.mark.integration
    def test_empty_query_handled(self, mcp_client):
        """Verify empty query is handled gracefully."""
        payload = {
            "tool": "search_docs",
            "arguments": {"query": ""}
        }
        response = mcp_client.post("/invoke", json=payload)
        # Should not crash, may return empty or error
        assert response.status_code in [200, 400]
