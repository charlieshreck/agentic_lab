"""MCP and REST HTTP client using urllib (stdlib only)."""

import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class McpClient:
    """Call MCP tools via JSON-RPC/SSE and plain REST endpoints."""

    def __init__(self, servers: dict[str, str]):
        """*servers* maps logical names to base URLs, e.g. {"infrastructure": "http://..."}."""
        self.servers = servers

    def call_tool(self, server: str, tool_name: str, arguments: dict | None = None) -> dict | list:
        """Call an MCP tool via JSON-RPC with SSE response parsing."""
        url = f"{self.servers.get(server, '')}/mcp"

        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {},
            },
        }

        req = Request(
            url,
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            method="POST",
        )

        try:
            with urlopen(req, timeout=30) as resp:
                raw = resp.read().decode()
                # Parse SSE format: "event: message\ndata: {...}"
                for line in raw.split("\n"):
                    if line.startswith("data: "):
                        result = json.loads(line[6:])
                        if "result" in result and "content" in result["result"]:
                            content = result["result"]["content"]
                            if content and len(content) > 0:
                                text = content[0].get("text", "{}")
                                return json.loads(text) if text.startswith(("{", "[")) else {"text": text}
                        return result.get("result", {})
                # Fallback: try parsing as plain JSON (non-SSE response)
                try:
                    result = json.loads(raw)
                    if "result" in result and "content" in result["result"]:
                        content = result["result"]["content"]
                        if content and len(content) > 0:
                            text = content[0].get("text", "{}")
                            return json.loads(text) if text.startswith(("{", "[")) else {"text": text}
                    return result.get("result", {})
                except json.JSONDecodeError:
                    pass
                return {}
        except (URLError, HTTPError) as e:
            logger.warning(f"MCP call {server}/{tool_name} failed: {e}")
            return {}
        except json.JSONDecodeError as e:
            logger.warning(f"MCP call {server}/{tool_name} JSON parse failed: {e}")
            return {}

    def call_rest(self, base_url: str, endpoint: str) -> dict | list:
        """Call a REST API endpoint directly."""
        url = f"{base_url}{endpoint}"
        req = Request(url, headers={"Accept": "application/json"}, method="GET")
        try:
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except (URLError, HTTPError) as e:
            logger.warning(f"REST call {url} failed: {e}")
            return {}
        except json.JSONDecodeError as e:
            logger.warning(f"REST call {url} JSON parse failed: {e}")
            return {}


def extract_list(response, *keys) -> list:
    """Extract a list from an MCP tool response, handling various formats."""
    if isinstance(response, list):
        return response
    if isinstance(response, dict):
        if "result" in response and isinstance(response["result"], list):
            return response["result"]
        for key in keys:
            if key in response and isinstance(response[key], list):
                return response[key]
    return []
