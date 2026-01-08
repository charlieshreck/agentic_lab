#!/usr/bin/env python3
"""Infisical MCP server for secrets management."""
import os
import logging
from typing import List, Dict, Any
from fastmcp import FastMCP
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

INFISICAL_HOST = os.environ.get("INFISICAL_HOST", "https://app.infisical.com")
INFISICAL_CLIENT_ID = os.environ.get("INFISICAL_CLIENT_ID", "")
INFISICAL_CLIENT_SECRET = os.environ.get("INFISICAL_CLIENT_SECRET", "")
INFISICAL_WORKSPACE_ID = os.environ.get("INFISICAL_WORKSPACE_ID", "")

mcp = FastMCP(
    name="infisical-mcp",
    instructions="""
    MCP server for Infisical secrets management.
    Provides tools to list and read secrets (not create/modify for safety).
    """
)


async def get_token() -> str:
    """Authenticate and get access token."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{INFISICAL_HOST}/api/v1/auth/universal-auth/login",
            json={"clientId": INFISICAL_CLIENT_ID, "clientSecret": INFISICAL_CLIENT_SECRET}
        )
        response.raise_for_status()
        return response.json().get("accessToken", "")


async def infisical_api(endpoint: str) -> Any:
    """Make authenticated API call to Infisical."""
    token = await get_token()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{INFISICAL_HOST}/api{endpoint}",
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def list_folders(path: str = "/", environment: str = "prod") -> List[str]:
    """List folders at a path."""
    try:
        result = await infisical_api(
            f"/v1/folders?workspaceId={INFISICAL_WORKSPACE_ID}&environment={environment}&path={path}"
        )
        return [f["name"] for f in result.get("folders", [])]
    except Exception as e:
        logger.error(f"Failed to list folders: {e}")
        return []


@mcp.tool()
async def list_secrets(path: str = "/", environment: str = "prod") -> List[str]:
    """List secret keys at a path (not values)."""
    try:
        result = await infisical_api(
            f"/v3/secrets/raw?workspaceSlug=agentic-platform&environment={environment}&secretPath={path}"
        )
        return [s["secretKey"] for s in result.get("secrets", [])]
    except Exception as e:
        logger.error(f"Failed to list secrets: {e}")
        return []


@mcp.tool()
async def get_secret(path: str, key: str, environment: str = "prod") -> Dict[str, Any]:
    """Get a specific secret value."""
    try:
        result = await infisical_api(
            f"/v3/secrets/raw/{key}?workspaceSlug=agentic-platform&environment={environment}&secretPath={path}"
        )
        secret = result.get("secret", {})
        return {"key": secret.get("secretKey"), "value": secret.get("secretValue")}
    except Exception as e:
        logger.error(f"Failed to get secret: {e}")
        return {"error": str(e)}


def main():
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(mcp.get_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
