# Device Context Skill

This skill provides context assembly for network devices and infrastructure components.

## When to Use

Use this approach when asked about:
- A specific device, host, or IP address
- Network entity details, status, or configuration
- Impact analysis ("what breaks if X fails?")
- Device relationships and dependencies
- Location-based queries ("devices in living room")

## Context Assembly Steps

When a user asks about a device or infrastructure component, gather context from both knowledge stores:

### Step 1: Get Entity Details from Qdrant (via knowledge-mcp)

Use `search_entities()` or `get_entity()` for:
- IP, MAC, hostname identification
- Device type, category, manufacturer
- Location, capabilities, interfaces
- Firmware version, status
- Discovery source and timestamps

Example queries:
- `search_entities("chromecast in living room")`
- `get_entity("10.10.0.50")`
- `get_entities_by_type("tasmota")`

### Step 2: Get Relationships from Neo4j (via neo4j-mcp)

Use `get_entity_context()` or `query_graph()` for:
- Network connections (CONNECTED_TO)
- Physical location (LOCATED_IN)
- VM hosting (HOSTS, SCHEDULED_ON)
- WiFi connections (CONNECTED_VIA)
- Service dependencies (DEPENDS_ON)

Example queries:
- `get_entity_context("10.10.0.50", "Host")`
- `query_graph("MATCH (h:Host {ip: '10.10.0.50'})-[r]-() RETURN type(r), r")`

### Step 3: Get Impact Analysis (if needed)

Use `get_impact_analysis()` when asked about:
- "What breaks if this goes down?"
- "What depends on this service?"
- Failure scenarios and recovery

Example:
- `get_impact_analysis("Host", "10.10.0.50")`

## Response Pattern

Combine the information into a coherent response:

```
[Device Name] is a [type] [category] device:
- IP: [ip], MAC: [mac]
- Location: [location]
- Status: [status] (last seen: [timestamp])
- Connected to: [network] via [ap/switch]
- Related: [list of dependent services/hosts]
```

## When to Use Each Tool

| Question Type | Primary Tool | Secondary Tool |
|--------------|--------------|----------------|
| "What is this device?" | knowledge-mcp.get_entity() | - |
| "Find smart lights" | knowledge-mcp.search_entities() | - |
| "What's connected to this?" | neo4j-mcp.get_entity_context() | knowledge-mcp |
| "What breaks if X fails?" | neo4j-mcp.get_impact_analysis() | knowledge-mcp |
| "Devices in living room" | knowledge-mcp.search_entities() | neo4j-mcp |
| "Network topology" | neo4j-mcp.query_graph() | - |

## Notes

- Qdrant (knowledge-mcp) is the source of truth for entity **details**
- Neo4j (neo4j-mcp) is the source of truth for **relationships**
- Always check both when full context is needed
- If one source is unavailable, use the other and note the limitation
