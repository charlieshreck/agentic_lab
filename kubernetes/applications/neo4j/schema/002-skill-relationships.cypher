// Neo4j Schema Migration: Skill Relationships
// Version: 1.2.0
// Date: 2026-01-30
// Purpose: Add Domain-MCP-Skill relationships for skills orchestration (Project 05)
//
// Reviewed: Claude (2026-01-30), Gemini (2026-01-30) - Ready for deployment

// ============================================================================
// ADDITIONAL INDEXES (Run after 001-reasoning-graph.cypher)
// ============================================================================

// Skill command index for fast slash command lookup
CREATE INDEX skill_commands IF NOT EXISTS FOR (sk:Skill) ON (sk.commands);

// MCP uniqueness
CREATE CONSTRAINT mcp_id IF NOT EXISTS FOR (m:MCP) REQUIRE m.id IS UNIQUE;

// ============================================================================
// MCP SERVER NODES
// ============================================================================

// Define MCP server nodes with tool counts (approximate)
MERGE (m:MCP {id: "infrastructure-mcp"})
SET m.tools_count = 95,
    m.description = "Kubernetes, Proxmox, TrueNAS, Cloudflare, OPNsense, Caddy, Infisical";

MERGE (m:MCP {id: "observability-mcp"})
SET m.tools_count = 45,
    m.description = "Keep alerts, Coroot metrics, VictoriaMetrics, AlertManager, Grafana, Gatus";

MERGE (m:MCP {id: "knowledge-mcp"})
SET m.tools_count = 72,
    m.description = "Qdrant, Neo4j graph, Outline wiki, Vikunja tasks";

MERGE (m:MCP {id: "home-mcp"})
SET m.tools_count = 68,
    m.description = "Home Assistant, Tasmota, UniFi network, AdGuard DNS, Homepage";

MERGE (m:MCP {id: "media-mcp"})
SET m.tools_count = 85,
    m.description = "Plex, Sonarr, Radarr, Prowlarr, Overseerr, Tautulli, Transmission, SABnzbd";

MERGE (m:MCP {id: "external-mcp"})
SET m.tools_count = 42,
    m.description = "SearXNG web search, GitHub, Reddit, Wikipedia, Playwright browser";

// ============================================================================
// SKILL-TO-DOMAIN RELATIONSHIPS
// ============================================================================

// Infrastructure skill -> Domain
MATCH (sk:Skill {id: "infra"})
MATCH (d:Domain {id: "infra"})
MERGE (sk)-[:BELONGS_TO]->(d);

// Observability skill -> Domain
MATCH (sk:Skill {id: "obs"})
MATCH (d:Domain {id: "obs"})
MERGE (sk)-[:BELONGS_TO]->(d);

// Security skill -> Domain
MATCH (sk:Skill {id: "security"})
MATCH (d:Domain {id: "security"})
MERGE (sk)-[:BELONGS_TO]->(d);

// Data skill -> Domain
MATCH (sk:Skill {id: "data"})
MATCH (d:Domain {id: "data"})
MERGE (sk)-[:BELONGS_TO]->(d);

// Home skill -> Domain (need to create home domain)
MERGE (d:Domain {id: "home"})
SET d.name = "Home Automation",
    d.keywords = ["light", "switch", "tasmota", "home assistant", "automation", "iot"];

MATCH (sk:Skill {id: "home"})
MATCH (d:Domain {id: "home"})
MERGE (sk)-[:BELONGS_TO]->(d);

// Media skill -> Domain (need to create media domain)
MERGE (d:Domain {id: "media"})
SET d.name = "Media",
    d.keywords = ["plex", "sonarr", "radarr", "movie", "tv", "streaming", "download"];

MATCH (sk:Skill {id: "media"})
MATCH (d:Domain {id: "media"})
MERGE (sk)-[:BELONGS_TO]->(d);

// ============================================================================
// SKILL-TO-MCP RELATIONSHIPS
// ============================================================================

// Infrastructure skill uses MCPs
MATCH (sk:Skill {id: "infra"})
MATCH (m1:MCP {id: "infrastructure-mcp"})
MATCH (m2:MCP {id: "knowledge-mcp"})
MERGE (sk)-[:USES_MCP {priority: "primary"}]->(m1)
MERGE (sk)-[:USES_MCP {priority: "primary"}]->(m2);

// Observability skill uses MCPs
MATCH (sk:Skill {id: "obs"})
MATCH (m1:MCP {id: "observability-mcp"})
MATCH (m2:MCP {id: "knowledge-mcp"})
MERGE (sk)-[:USES_MCP {priority: "primary"}]->(m1)
MERGE (sk)-[:USES_MCP {priority: "primary"}]->(m2);

// Security skill uses MCPs
MATCH (sk:Skill {id: "security"})
MATCH (m1:MCP {id: "infrastructure-mcp"})
MATCH (m2:MCP {id: "knowledge-mcp"})
MERGE (sk)-[:USES_MCP {priority: "primary"}]->(m1)
MERGE (sk)-[:USES_MCP {priority: "primary"}]->(m2);

// Data skill uses MCPs
MATCH (sk:Skill {id: "data"})
MATCH (m:MCP {id: "knowledge-mcp"})
MERGE (sk)-[:USES_MCP {priority: "primary"}]->(m);

// Home skill uses MCPs
MATCH (sk:Skill {id: "home"})
MATCH (m1:MCP {id: "home-mcp"})
MATCH (m2:MCP {id: "knowledge-mcp"})
MERGE (sk)-[:USES_MCP {priority: "primary"}]->(m1)
MERGE (sk)-[:USES_MCP {priority: "primary"}]->(m2);

// Media skill uses MCPs
MATCH (sk:Skill {id: "media"})
MATCH (m1:MCP {id: "media-mcp"})
MATCH (m2:MCP {id: "knowledge-mcp"})
MERGE (sk)-[:USES_MCP {priority: "primary"}]->(m1)
MERGE (sk)-[:USES_MCP {priority: "primary"}]->(m2);

// ============================================================================
// ENHANCED SKILL PROPERTIES
// ============================================================================

// Update skills with new properties for Project 05
MATCH (sk:Skill {id: "infra"})
SET sk.commands = ["/troubleshoot", "/deploy", "/remediate", "/cluster"],
    sk.runbook_patterns = ["runbooks/infrastructure/*.md", "runbooks/alerts/pod-*.md"],
    sk.priority_keywords = ["crash", "restart", "scale", "deploy", "oom", "evicted"],
    sk.version = "1.1.0",
    sk.updated_at = datetime();

MATCH (sk:Skill {id: "obs"})
SET sk.commands = ["/investigate", "/status", "/metrics"],
    sk.runbook_patterns = ["runbooks/alerts/*.md", "runbooks/troubleshooting/*.md"],
    sk.priority_keywords = ["alert", "metric", "anomaly", "threshold", "latency"],
    sk.version = "1.1.0",
    sk.updated_at = datetime();

MATCH (sk:Skill {id: "security"})
SET sk.commands = ["/security", "/audit", "/certs"],
    sk.runbook_patterns = ["runbooks/security/*.md"],
    sk.priority_keywords = ["cert", "ssl", "auth", "firewall", "secret"],
    sk.version = "1.1.0",
    sk.updated_at = datetime();

MATCH (sk:Skill {id: "data"})
SET sk.commands = ["/learn", "/search", "/knowledge"],
    sk.runbook_patterns = ["runbooks/data/*.md"],
    sk.priority_keywords = ["backup", "restore", "database", "index"],
    sk.version = "1.1.0",
    sk.updated_at = datetime();

MATCH (sk:Skill {id: "home"})
SET sk.commands = ["/home", "/lights", "/devices"],
    sk.runbook_patterns = ["runbooks/home/*.md"],
    sk.priority_keywords = ["light", "switch", "sensor", "automation"],
    sk.version = "1.1.0",
    sk.updated_at = datetime();

MATCH (sk:Skill {id: "media"})
SET sk.commands = ["/media", "/plex", "/download"],
    sk.runbook_patterns = ["runbooks/media/*.md"],
    sk.priority_keywords = ["movie", "show", "download", "streaming"],
    sk.version = "1.1.0",
    sk.updated_at = datetime();

// ============================================================================
// EXTERNAL/RESEARCH SKILL (NEW)
// ============================================================================

MERGE (sk:Skill {id: "research"})
SET sk.name = "Research & External",
    sk.mcps = ["external"],
    sk.system_prompt_ref = "skills/research.md",
    sk.commands = ["/research", "/search", "/web"],
    sk.runbook_patterns = [],
    sk.priority_keywords = ["search", "web", "github", "documentation"],
    sk.version = "1.0.0",
    sk.created_at = datetime();

// Link research skill to external MCP
MATCH (sk:Skill {id: "research"})
MATCH (m1:MCP {id: "external-mcp"})
MATCH (m2:MCP {id: "knowledge-mcp"})
MERGE (sk)-[:USES_MCP {priority: "primary"}]->(m1)
MERGE (sk)-[:USES_MCP {priority: "primary"}]->(m2);

// Create external domain
MERGE (d:Domain {id: "external"})
SET d.name = "External Research",
    d.keywords = ["search", "web", "github", "reddit", "documentation", "api"];

MATCH (sk:Skill {id: "research"})
MATCH (d:Domain {id: "external"})
MERGE (sk)-[:BELONGS_TO]->(d);

// ============================================================================
// VERIFICATION QUERY
// ============================================================================

// Verify the migration
MATCH (sk:Skill)-[:USES_MCP]->(m:MCP)
RETURN sk.id as skill, collect(m.id) as mcps
ORDER BY sk.id;
