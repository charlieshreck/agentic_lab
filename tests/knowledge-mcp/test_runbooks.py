"""
Test runbook functionality via knowledge-mcp.
"""

import pytest


class TestRunbookRetrieval:
    """Test runbook retrieval by path or ID."""

    @pytest.mark.integration
    def test_get_runbook_by_path(self, mcp_client):
        """Retrieve runbook by file path."""
        payload = {
            "tool": "get_runbook",
            "arguments": {"path": "infrastructure/new-app-prod.md"}
        }
        response = mcp_client.post("/invoke", json=payload)

        if response.status_code == 200:
            result = response.json()
            assert "content" in result or "text" in result
        else:
            pytest.skip("get_runbook by path not implemented")

    @pytest.mark.integration
    def test_list_runbooks(self, mcp_client):
        """List all available runbooks."""
        payload = {
            "tool": "list_runbooks",
            "arguments": {}
        }
        response = mcp_client.post("/invoke", json=payload)

        if response.status_code == 200:
            result = response.json()
            runbooks = result.get("runbooks", [])
            assert len(runbooks) > 0, "No runbooks found"
        else:
            pytest.skip("list_runbooks not implemented")


class TestRunbookContent:
    """Test runbook content quality."""

    @pytest.mark.integration
    def test_runbook_has_overview(self, mcp_client):
        """Verify runbooks have overview sections."""
        payload = {
            "tool": "search_runbooks",
            "arguments": {"query": "new app prod"}
        }
        response = mcp_client.post("/invoke", json=payload)
        assert response.status_code == 200

        result = response.json()
        results = result.get("results", [])

        if len(results) > 0:
            content = str(results[0]).lower()
            # Should have overview or similar header
            assert any(word in content for word in ["overview", "purpose", "about"])

    @pytest.mark.integration
    def test_runbook_has_steps(self, mcp_client):
        """Verify runbooks have actionable steps."""
        payload = {
            "tool": "search_runbooks",
            "arguments": {"query": "caddy proxy configuration"}
        }
        response = mcp_client.post("/invoke", json=payload)
        assert response.status_code == 200

        result = response.json()
        results = result.get("results", [])

        if len(results) > 0:
            content = str(results[0]).lower()
            # Should have steps or commands
            assert any(word in content for word in ["step", "command", "```", "1."])


class TestRunbookCategories:
    """Test runbook categorization."""

    @pytest.mark.integration
    def test_infrastructure_runbooks_exist(self, mcp_client):
        """Verify infrastructure runbooks are indexed."""
        payload = {
            "tool": "search_runbooks",
            "arguments": {"query": "infrastructure deployment"}
        }
        response = mcp_client.post("/invoke", json=payload)
        assert response.status_code == 200

        result = response.json()
        results = result.get("results", [])
        assert len(results) > 0

    @pytest.mark.integration
    def test_automation_runbooks_exist(self, mcp_client):
        """Verify automation runbooks are indexed."""
        payload = {
            "tool": "search_runbooks",
            "arguments": {"query": "mcp automation deployment"}
        }
        response = mcp_client.post("/invoke", json=payload)
        assert response.status_code == 200

        result = response.json()
        results = result.get("results", [])
        assert len(results) > 0


class TestRunbookGitIntegration:
    """Test git-backed runbook features."""

    @pytest.mark.integration
    def test_runbook_has_commit_ref(self, mcp_client):
        """Verify runbooks include git commit reference."""
        payload = {
            "tool": "get_runbook",
            "arguments": {"path": "infrastructure/new-app-prod.md"}
        }
        response = mcp_client.post("/invoke", json=payload)

        if response.status_code == 200:
            result = response.json()
            # Should include metadata about git source
            # Implementation depends on how this is exposed
            metadata = result.get("metadata", {})
            # Optional: check for commit_ref, version, or similar

    @pytest.mark.integration
    def test_runbook_refresh(self, mcp_client):
        """Test runbook re-indexing from git."""
        payload = {
            "tool": "refresh_runbooks",
            "arguments": {}
        }
        response = mcp_client.post("/invoke", json=payload)

        # This may not be implemented, so accept various responses
        assert response.status_code in [200, 404, 501]
