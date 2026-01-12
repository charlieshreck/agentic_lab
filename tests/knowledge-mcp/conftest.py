"""
Pytest configuration for knowledge-mcp tests.

These tests verify the knowledge-mcp server functionality
for the Kernow homelab unified knowledge system.
"""

import pytest
import os
import httpx


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires running MCP)"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )


@pytest.fixture
def knowledge_mcp_url():
    """Get the knowledge-mcp URL from environment or default."""
    return os.environ.get(
        "KNOWLEDGE_MCP_URL",
        "http://knowledge-mcp.ai-platform.svc.cluster.local:8080"
    )


@pytest.fixture
def mcp_client(knowledge_mcp_url):
    """Create an HTTP client for MCP requests."""
    return httpx.Client(base_url=knowledge_mcp_url, timeout=30.0)


@pytest.fixture
def qdrant_collections():
    """Expected Qdrant collections."""
    return [
        "documentation",
        "runbooks",
        "decisions",
        "entities",
        "device_types",
        "capability_gaps",
        "skill_gaps",
        "user_feedback",
    ]


@pytest.fixture
def sample_queries():
    """Sample queries for semantic search tests."""
    return {
        "runbooks": [
            "how to add new app to prod",
            "caddy reverse proxy",
            "adguard dns rewrite",
            "mcp deployment",
        ],
        "documentation": [
            "argocd patterns",
            "dual ingress",
            "cluster architecture",
            "domain routing",
        ],
        "entities": [
            "chromecast devices",
            "iot network",
            "proxmox vms",
        ],
    }
