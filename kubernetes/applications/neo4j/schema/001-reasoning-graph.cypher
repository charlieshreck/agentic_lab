// Neo4j Reasoning Graph Schema
// Version: 1.1.0 (Flattened for Community Edition)
// Date: 2026-01-25
// Purpose: Self-learning knowledge system for agentic operations
//
// Note: Properties flattened from maps to primitives for Neo4j Community Edition compatibility
// Ground Truth Probe Operators (for RunbookVersion.ground_truth_probes):
//   Comparison: <, >, =, <=, >=
//   String: contains, not_contains, matches, not_matches, regex
//   Range: between (expects {min, max})
//
// Reviewed: Claude (2026-01-25), Gemini (2026-01-25) - Ready for deployment

// ============================================================================
// CONSTRAINTS (Run first)
// ============================================================================

// Uniqueness constraints
CREATE CONSTRAINT problem_id IF NOT EXISTS FOR (p:Problem) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT solution_id IF NOT EXISTS FOR (s:Solution) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT context_id IF NOT EXISTS FOR (c:Context) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT runbook_id IF NOT EXISTS FOR (r:Runbook) REQUIRE r.id IS UNIQUE;
CREATE CONSTRAINT runbook_version_id IF NOT EXISTS FOR (rv:RunbookVersion) REQUIRE rv.id IS UNIQUE;
CREATE CONSTRAINT skill_id IF NOT EXISTS FOR (sk:Skill) REQUIRE sk.id IS UNIQUE;
CREATE CONSTRAINT artifact_id IF NOT EXISTS FOR (a:Artifact) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT execution_id IF NOT EXISTS FOR (e:Execution) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT config_id IF NOT EXISTS FOR (c:Config) REQUIRE c.id IS UNIQUE;

// ============================================================================
// INDEXES (Run after constraints)
// ============================================================================

// Problem indexes
CREATE INDEX problem_domain IF NOT EXISTS FOR (p:Problem) ON (p.domain);
CREATE INDEX problem_last_ref IF NOT EXISTS FOR (p:Problem) ON (p.last_referenced);
CREATE INDEX problem_qdrant IF NOT EXISTS FOR (p:Problem) ON (p.qdrant_vector_id);

// Solution indexes
CREATE INDEX solution_archived IF NOT EXISTS FOR (s:Solution) ON (s.archived);
CREATE INDEX solution_confidence IF NOT EXISTS FOR (s:Solution) ON (s.confidence);

// Runbook indexes
CREATE INDEX runbook_automation IF NOT EXISTS FOR (r:Runbook) ON (r.automation_level);
CREATE INDEX runbook_problem_class IF NOT EXISTS FOR (r:Runbook) ON (r.problem_class);

// RunbookVersion indexes
CREATE INDEX runbook_version_hash IF NOT EXISTS FOR (rv:RunbookVersion) ON (rv.content_hash);
CREATE INDEX runbook_version_parent IF NOT EXISTS FOR (rv:RunbookVersion) ON (rv.runbook_id);

// Execution indexes
CREATE INDEX execution_timestamp IF NOT EXISTS FOR (e:Execution) ON (e.timestamp);
CREATE INDEX execution_success IF NOT EXISTS FOR (e:Execution) ON (e.success);
CREATE INDEX execution_verified IF NOT EXISTS FOR (e:Execution) ON (e.verified);

// Skill indexes
CREATE INDEX skill_name IF NOT EXISTS FOR (sk:Skill) ON (sk.name);

// Full-text index for semantic search fallback
CREATE FULLTEXT INDEX problem_description IF NOT EXISTS FOR (p:Problem) ON EACH [p.description];
CREATE FULLTEXT INDEX runbook_name IF NOT EXISTS FOR (r:Runbook) ON EACH [r.name, r.problem_class];

// ============================================================================
// GLOBAL CONFIGURATION (Flattened properties)
// ============================================================================

MERGE (c:Config {id: "global"})
SET c.confidence_autonomous_execution = 0.85,
    c.confidence_prompted_execution = 0.60,
    c.time_decay_half_life_days = 90,
    c.pruning_min_attempts_to_archive = 5,
    c.pruning_archive_threshold = 0.20,
    c.pruning_stale_days = 90,
    c.promotion_manual_to_prompted_min_executions = 5,
    c.promotion_manual_to_prompted_min_success_rate = 0.90,
    c.promotion_prompted_to_standard_min_executions = 10,
    c.promotion_prompted_to_standard_min_success_rate = 0.90,
    c.promotion_standard_to_autonomous_min_executions = 20,
    c.promotion_standard_to_autonomous_min_success_rate = 0.95,
    c.circuit_breaker_consecutive_failures_threshold = 3,
    c.circuit_breaker_failures_window_hours = 24,
    c.circuit_breaker_cooldown_hours = 1,
    c.created_at = datetime(),
    c.updated_at = datetime();

// ============================================================================
// CORE SKILLS (Bootstrap)
// ============================================================================

// Infrastructure skill
MERGE (sk:Skill {id: "infra"})
SET sk.name = "Infrastructure Operations",
    sk.mcps = ["infrastructure"],
    sk.system_prompt_ref = "skills/infra.md",
    sk.created_at = datetime();

// Observability skill
MERGE (sk:Skill {id: "obs"})
SET sk.name = "Observability & Monitoring",
    sk.mcps = ["observability"],
    sk.system_prompt_ref = "skills/obs.md",
    sk.created_at = datetime();

// Security skill
MERGE (sk:Skill {id: "security"})
SET sk.name = "Security Operations",
    sk.mcps = ["infrastructure"],
    sk.system_prompt_ref = "skills/security.md",
    sk.created_at = datetime();

// Data skill
MERGE (sk:Skill {id: "data"})
SET sk.name = "Data & Knowledge Management",
    sk.mcps = ["knowledge"],
    sk.system_prompt_ref = "skills/data.md",
    sk.created_at = datetime();

// Home automation skill
MERGE (sk:Skill {id: "home"})
SET sk.name = "Home Automation",
    sk.mcps = ["home"],
    sk.system_prompt_ref = "skills/home.md",
    sk.created_at = datetime();

// Media skill
MERGE (sk:Skill {id: "media"})
SET sk.name = "Media Management",
    sk.mcps = ["media"],
    sk.system_prompt_ref = "skills/media.md",
    sk.created_at = datetime();

// ============================================================================
// PROBLEM DOMAINS (Bootstrap)
// ============================================================================

// Create domain reference nodes for quick lookups
MERGE (d:Domain {id: "infra"})
SET d.name = "Infrastructure",
    d.keywords = ["kubernetes", "k8s", "pod", "node", "terraform", "proxmox", "storage", "vm", "container"];

MERGE (d:Domain {id: "security"})
SET d.name = "Security",
    d.keywords = ["cert", "ssl", "tls", "auth", "vault", "secret", "firewall", "cve"];

MERGE (d:Domain {id: "obs"})
SET d.name = "Observability",
    d.keywords = ["alert", "metric", "prometheus", "grafana", "log", "monitor", "trace"];

MERGE (d:Domain {id: "dns"})
SET d.name = "DNS",
    d.keywords = ["dns", "domain", "adguard", "unbound", "resolve", "record"];

MERGE (d:Domain {id: "network"})
SET d.name = "Network",
    d.keywords = ["network", "vlan", "ip", "dhcp", "route", "switch", "wifi"];

MERGE (d:Domain {id: "data"})
SET d.name = "Data",
    d.keywords = ["database", "postgres", "qdrant", "neo4j", "backup", "redis"];

// ============================================================================
// VERIFICATION QUERY
// ============================================================================

// Run this to verify schema deployment
MATCH (n) WHERE n:Config OR n:Skill OR n:Domain
RETURN labels(n)[0] AS type, count(n) AS count
ORDER BY type;
