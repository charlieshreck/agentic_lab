# Cyclical Learning Agentic AI Platform
## Talos Bare Metal + Local/Cloud Hybrid + Vector Knowledge Base

---

## Executive Summary

This architecture delivers a **self-improving homelab AI agent** that learns from every interaction, builds institutional knowledge, and progressively earns autonomy. It combines local inference for speed and privacy with cloud escalation for complex reasoning, unified by a vector knowledge base that enables genuine learning.

**Core Capabilities:**
- **Flexible inference**: Local Ollama, Cloud Gemini/Claude, or both
- **Persistent knowledge**: Vector DB stores decisions, outcomes, and learnings
- **Cyclical learning**: Every action feeds back into the knowledge base
- **Progressive autonomy**: System earns trust through demonstrated reliability
- **Human-in-the-loop**: You remain in control, the AI earns its freedom

**Philosophy**: The AI doesn't just execute tasks—it remembers what worked, learns your preferences, and gets smarter over time.

---

## Part I: The Learning Loop

### The Cyclical Intelligence Model

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         THE LEARNING CYCLE                               │
│                                                                          │
│    ┌──────────┐                                      ┌──────────┐       │
│    │  DETECT  │                                      │  LEARN   │       │
│    │  Event   │                                      │  Update  │       │
│    │  occurs  │                                      │  vectors │       │
│    └────┬─────┘                                      └────▲─────┘       │
│         │                                                 │             │
│         ▼                                                 │             │
│    ┌──────────┐      ┌──────────┐      ┌──────────┐      │             │
│    │ RETRIEVE │      │  REASON  │      │   ACT    │      │             │
│    │ Similar  │─────▶│  Decide  │─────▶│ Execute  │──────┘             │
│    │ contexts │      │  action  │      │  + log   │                    │
│    └──────────┘      └──────────┘      └──────────┘                    │
│         ▲                                                               │
│         │                                                               │
│    ┌────┴─────┐                                                        │
│    │  VECTOR  │  ◄── Runbooks, decisions, outcomes, preferences        │
│    │    DB    │  ◄── System state snapshots, documentation             │
│    │ (Qdrant) │  ◄── Conversation history, human feedback              │
│    └──────────┘                                                        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### What Gets Learned

| Knowledge Type | Source | How It's Used |
|----------------|--------|---------------|
| **Runbooks** | Approved fixes | "I've seen this before, solution X worked" |
| **Outcomes** | Post-action monitoring | "Last time this fix caused Y" |
| **Preferences** | Human approvals/rejections | "Charlie prefers permanent fixes" |
| **Context** | System state at decision time | "This happened during high load" |
| **Documentation** | Ingested docs, READMEs | "The Sonarr API works like this" |
| **Conversations** | Past interactions | "We discussed this architecture before" |

### The Feedback Loop

```python
# Every action creates a learning record
learning_record = {
    "id": uuid4(),
    "timestamp": datetime.utcnow(),
    
    # What triggered this?
    "trigger": {
        "type": "anomaly",  # or "scheduled", "user_request"
        "source": "coroot",
        "description": "Radarr memory at 95%"
    },
    
    # What context was retrieved?
    "retrieved_context": [
        {"runbook_id": "radarr-mem-001", "similarity": 0.89},
        {"past_decision": "dec-2024-12-01", "similarity": 0.76}
    ],
    
    # What was decided?
    "decision": {
        "action": "increase_memory",
        "reasoning": "Pattern matches previous OOM, user preferred permanent fix",
        "confidence": 0.85,
        "model_used": "local/qwen2.5:3b"
    },
    
    # What happened?
    "outcome": {
        "success": True,
        "metrics_before": {"memory_pct": 95},
        "metrics_after": {"memory_pct": 45},
        "side_effects": None,
        "human_feedback": "approved",  # or "rejected", "modified"
        "time_to_resolution": "2m 34s"
    },
    
    # What should be learned?
    "learnings": [
        "Radarr OOM at 95% → increase memory is effective",
        "User approved within 3 minutes → acceptable latency",
        "No side effects observed → safe action"
    ]
}

# Embed and store
embedding = embed(learning_record)
qdrant.upsert(collection="learnings", vectors=[embedding], payload=[learning_record])
```

---

## Part II: Infrastructure Layer

### Hardware: Minisforum UM690L

| Component | Spec | Role |
|-----------|------|------|
| **CPU** | AMD Ryzen 9 6900HX (8C/16T) | Orchestration, embedding |
| **GPU** | Radeon 680M (RDNA2, 12 CUs) | Local LLM inference |
| **RAM** | 32GB DDR5-4800 | Models + Vector DB + Services |
| **Storage** | 1TB + 500GB NVMe | OS/Models + Data/Vectors |

### Operating System: Talos Linux

Talos provides immutable, API-driven Kubernetes - ideal for a system that manages itself.

```yaml
# talconfig.yaml
clusterName: homelab-ai
talosVersion: v1.12.0
kubernetesVersion: v1.31.0
endpoint: https://192.168.1.50:6443

nodes:
  - hostname: ai-node
    ipAddress: 192.168.1.50
    controlPlane: true
    installDisk: /dev/nvme0n1
    
    schematic:
      customization:
        systemExtensions:
          officialExtensions:
            - siderolabs/amdgpu
            - siderolabs/amd-ucode
        extraKernelArgs:
          - amdgpu.gttsize=131072
          - ttm.pages_limit=33554432

    patches:
      - |-
        cluster:
          allowSchedulingOnControlPlanes: true
        machine:
          kubelet:
            extraMounts:
              - destination: /dev/dri
                type: bind
                source: /dev/dri
                options: [rbind, rshared]
          kernel:
            modules:
              - name: amdgpu
          disks:
            - device: /dev/nvme1n1
              partitions:
                - mountpoint: /var/mnt/data
```

### Storage Architecture

```
/dev/nvme0n1 (1TB) - System + Models
├── Talos OS partitions
├── /var/lib/containers (K8s images)
└── Ollama model storage (~50GB)

/dev/nvme1n1 (500GB) - Data + Vectors
├── Qdrant vectors (~50GB, grows over time)
├── PostgreSQL (runbooks, state)
├── Redis (cache, queues)
└── MinIO (backups, artifacts)
```

### Memory Budget

```
Total: 32GB

Allocated:
├── Talos + K8s overhead      1.5GB
├── Ollama + Model (Q4_K_M)   4-6GB (dynamic)
├── Qdrant Vector DB          2-4GB
├── Embedding model           1GB
├── PostgreSQL                512MB
├── Redis                     256MB
├── LangGraph + Services      1GB
├── Observability             1GB
├── MCP Servers               512MB
└── Buffer                    ~16GB available

Note: Ollama unloads models after KEEP_ALIVE timeout,
freeing memory when not actively inferring.
```

---

## Part III: Inference Layer - Flexible Routing

### The Routing Decision

```python
"""Flexible routing: local, cloud, or both."""

class InferenceRouter:
    def __init__(self, config: RouterConfig):
        self.local_available = self.check_ollama_health()
        self.cloud_available = self.check_api_keys()
        self.mode = config.mode  # "local_first", "cloud_first", "local_only", "cloud_only"
    
    async def route(self, request: InferenceRequest) -> str:
        # Check vector DB for similar past decisions
        similar = await self.retrieve_similar(request.query)
        
        # If we have high-confidence runbook match, might not need LLM at all
        if similar and similar[0].score > 0.95 and similar[0].is_standard_change:
            return "execute_runbook_directly"
        
        # Determine complexity
        complexity = self.estimate_complexity(request, similar)
        
        # Route based on mode and complexity
        if self.mode == "local_only":
            return "ollama/qwen2.5:3b"
        
        elif self.mode == "cloud_only":
            return self.select_cloud_model(complexity)
        
        elif self.mode == "local_first":
            if complexity < 0.6 and self.local_available:
                return "ollama/qwen2.5:3b"
            elif complexity < 0.8:
                return "gemini-pro"
            else:
                return "gemini-thinking"
        
        elif self.mode == "cloud_first":
            if not self.cloud_available:
                return "ollama/qwen2.5:3b"  # Fallback
            return self.select_cloud_model(complexity)
        
        # Hybrid: use local for speed, cloud for verification
        elif self.mode == "hybrid":
            local_result = await self.call_local(request)
            if local_result.confidence > 0.9:
                return local_result
            # Low confidence? Verify with cloud
            cloud_result = await self.call_cloud(request, local_result)
            return cloud_result
    
    def select_cloud_model(self, complexity: float) -> str:
        if complexity < 0.4:
            return "gemini-flash"
        elif complexity < 0.7:
            return "gemini-pro"
        elif complexity < 0.9:
            return "gemini-thinking"
        else:
            return "claude-sonnet"  # Premium reasoning
```

### Mode Configurations

| Mode | When to Use | Behaviour |
|------|-------------|-----------|
| `local_only` | Offline, privacy-critical | All inference on Ollama |
| `cloud_only` | Maximum quality | All inference via Gemini/Claude |
| `local_first` | Default recommended | Local for simple, cloud for complex |
| `cloud_first` | When quality > latency | Cloud preferred, local fallback |
| `hybrid` | High-stakes decisions | Local proposes, cloud verifies |

### LiteLLM Configuration

```yaml
# litellm-config.yaml
model_list:
  # Local Models
  - model_name: local-fast
    litellm_params:
      model: ollama/qwen2.5:3b
      api_base: http://ollama:11434
    model_info:
      mode: local
      
  - model_name: local-embed
    litellm_params:
      model: ollama/nomic-embed-text
      api_base: http://ollama:11434
    model_info:
      mode: local

  # Cloud Models - Gemini (Primary)
  - model_name: gemini-flash
    litellm_params:
      model: gemini/gemini-2.0-flash
      api_key: os.environ/GEMINI_API_KEY
    model_info:
      mode: cloud
      tier: fast
      
  - model_name: gemini-pro
    litellm_params:
      model: gemini/gemini-1.5-pro
      api_key: os.environ/GEMINI_API_KEY
    model_info:
      mode: cloud
      tier: standard
      
  - model_name: gemini-thinking
    litellm_params:
      model: gemini/gemini-2.0-flash-thinking-exp
      api_key: os.environ/GEMINI_API_KEY
    model_info:
      mode: cloud
      tier: reasoning

  # Cloud Models - Claude (Premium)
  - model_name: claude-sonnet
    litellm_params:
      model: anthropic/claude-sonnet-4-20250514
      api_key: os.environ/ANTHROPIC_API_KEY
    model_info:
      mode: cloud
      tier: premium
      max_budget: 25.00
      
  - model_name: claude-opus
    litellm_params:
      model: anthropic/claude-opus-4-20250514
      api_key: os.environ/ANTHROPIC_API_KEY
    model_info:
      mode: cloud
      tier: critical
      max_budget: 50.00

router_settings:
  routing_strategy: usage-based-routing-v2
  redis_host: redis
  redis_port: 6379
  
  # Fallback chain
  fallbacks:
    - model: gemini-pro
      fallback: [gemini-flash, local-fast]
    - model: claude-sonnet
      fallback: [gemini-thinking, gemini-pro]
```

### Ollama Configuration

```yaml
# ollama-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ollama
  namespace: ai-platform
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ollama
  template:
    metadata:
      labels:
        app: ollama
    spec:
      containers:
        - name: ollama
          image: ollama/ollama:latest
          ports:
            - containerPort: 11434
          env:
            # AMD APU optimizations
            - name: HSA_OVERRIDE_GFX_VERSION
              value: "10.3.0"
            - name: OLLAMA_FLASH_ATTENTION
              value: "1"
            - name: OLLAMA_KV_CACHE_TYPE
              value: "q8_0"
            # Memory management
            - name: OLLAMA_KEEP_ALIVE
              value: "10m"  # Unload after 10 min idle
            - name: OLLAMA_NUM_PARALLEL
              value: "1"
            - name: OLLAMA_MAX_LOADED_MODELS
              value: "2"  # Qwen + embedding
            # Backend
            - name: GGML_VULKAN
              value: "1"
          resources:
            limits:
              memory: "12Gi"
              amd.com/gpu: "1"
          volumeMounts:
            - name: ollama-data
              mountPath: /root/.ollama
            - name: dri
              mountPath: /dev/dri
          securityContext:
            privileged: true
      volumes:
        - name: ollama-data
          persistentVolumeClaim:
            claimName: ollama-pvc
        - name: dri
          hostPath:
            path: /dev/dri
```

---

## Part IV: Vector Knowledge Base

### Qdrant Configuration

```yaml
# qdrant-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: qdrant
  namespace: ai-platform
spec:
  replicas: 1
  selector:
    matchLabels:
      app: qdrant
  template:
    spec:
      containers:
        - name: qdrant
          image: qdrant/qdrant:latest
          ports:
            - containerPort: 6333  # REST
            - containerPort: 6334  # gRPC
          env:
            - name: QDRANT__SERVICE__GRPC_PORT
              value: "6334"
          resources:
            requests:
              memory: "1Gi"
            limits:
              memory: "4Gi"
          volumeMounts:
            - name: qdrant-data
              mountPath: /qdrant/storage
      volumes:
        - name: qdrant-data
          persistentVolumeClaim:
            claimName: qdrant-pvc
```

### Collection Schema

```python
"""Qdrant collections for the knowledge base."""
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

client = QdrantClient(host="qdrant", port=6333)

# Collection: Runbooks (approved fixes)
client.create_collection(
    collection_name="runbooks",
    vectors_config=VectorParams(size=768, distance=Distance.COSINE)
)

# Collection: Decisions (every action taken)
client.create_collection(
    collection_name="decisions",
    vectors_config=VectorParams(size=768, distance=Distance.COSINE)
)

# Collection: System Documentation
client.create_collection(
    collection_name="documentation",
    vectors_config=VectorParams(size=768, distance=Distance.COSINE)
)

# Collection: Conversations (past interactions)
client.create_collection(
    collection_name="conversations",
    vectors_config=VectorParams(size=768, distance=Distance.COSINE)
)

# Collection: System State Snapshots
client.create_collection(
    collection_name="state_snapshots",
    vectors_config=VectorParams(size=768, distance=Distance.COSINE)
)
```

### Embedding Pipeline

```python
"""Embedding service using local or cloud models."""
import httpx
from typing import List

class EmbeddingService:
    def __init__(self, mode: str = "local"):
        self.mode = mode
        self.ollama_url = "http://ollama:11434"
        self.dimension = 768
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        if self.mode == "local":
            return await self._embed_local(texts)
        else:
            return await self._embed_cloud(texts)
    
    async def _embed_local(self, texts: List[str]) -> List[List[float]]:
        """Use nomic-embed-text via Ollama."""
        embeddings = []
        async with httpx.AsyncClient() as client:
            for text in texts:
                response = await client.post(
                    f"{self.ollama_url}/api/embeddings",
                    json={"model": "nomic-embed-text", "prompt": text}
                )
                embeddings.append(response.json()["embedding"])
        return embeddings
    
    async def _embed_cloud(self, texts: List[str]) -> List[List[float]]:
        """Use Gemini embedding API."""
        # Implementation for cloud embeddings
        pass

# Usage
embedder = EmbeddingService(mode="local")
vectors = await embedder.embed(["Radarr OOM at 95% memory usage"])
```

### Knowledge Ingestion

```python
"""Ingest documentation and system state into vector DB."""
from pathlib import Path
import yaml

class KnowledgeIngester:
    def __init__(self, qdrant: QdrantClient, embedder: EmbeddingService):
        self.qdrant = qdrant
        self.embedder = embedder
    
    async def ingest_runbooks(self, runbook_dir: Path):
        """Ingest runbook YAML files."""
        for file in runbook_dir.glob("*.yaml"):
            runbook = yaml.safe_load(file.read_text())
            
            # Create searchable text
            text = f"""
            Trigger: {runbook['trigger']['description']}
            Condition: {runbook['trigger']['condition']}
            Solutions: {', '.join(s['description'] for s in runbook['solutions'])}
            """
            
            embedding = await self.embedder.embed([text])
            
            self.qdrant.upsert(
                collection_name="runbooks",
                points=[PointStruct(
                    id=runbook['id'],
                    vector=embedding[0],
                    payload=runbook
                )]
            )
    
    async def ingest_documentation(self, docs_dir: Path):
        """Ingest markdown documentation."""
        for file in docs_dir.glob("**/*.md"):
            content = file.read_text()
            
            # Chunk large documents
            chunks = self.chunk_text(content, max_tokens=500)
            
            for i, chunk in enumerate(chunks):
                embedding = await self.embedder.embed([chunk])
                
                self.qdrant.upsert(
                    collection_name="documentation",
                    points=[PointStruct(
                        id=f"{file.stem}_{i}",
                        vector=embedding[0],
                        payload={
                            "source": str(file),
                            "chunk_index": i,
                            "content": chunk
                        }
                    )]
                )
    
    async def snapshot_system_state(self):
        """Capture current system state for context."""
        state = {
            "timestamp": datetime.utcnow().isoformat(),
            "pods": await self.get_pod_status(),
            "resources": await self.get_resource_usage(),
            "recent_events": await self.get_recent_events(),
            "active_alerts": await self.get_active_alerts()
        }
        
        text = self.state_to_text(state)
        embedding = await self.embedder.embed([text])
        
        self.qdrant.upsert(
            collection_name="state_snapshots",
            points=[PointStruct(
                id=f"state_{datetime.utcnow().timestamp()}",
                vector=embedding[0],
                payload=state
            )]
        )
```

### Retrieval Augmented Decision Making

```python
"""RAG for decision making."""

class DecisionRAG:
    def __init__(self, qdrant: QdrantClient, embedder: EmbeddingService):
        self.qdrant = qdrant
        self.embedder = embedder
    
    async def retrieve_context(self, query: str, limit: int = 5) -> dict:
        """Retrieve relevant context from all collections."""
        embedding = await self.embedder.embed([query])
        
        context = {}
        
        # Search runbooks
        context["runbooks"] = self.qdrant.search(
            collection_name="runbooks",
            query_vector=embedding[0],
            limit=limit
        )
        
        # Search past decisions
        context["past_decisions"] = self.qdrant.search(
            collection_name="decisions",
            query_vector=embedding[0],
            limit=limit
        )
        
        # Search documentation
        context["documentation"] = self.qdrant.search(
            collection_name="documentation",
            query_vector=embedding[0],
            limit=limit
        )
        
        return context
    
    async def build_prompt(self, query: str, context: dict) -> str:
        """Build LLM prompt with retrieved context."""
        prompt = f"""You are a homelab management AI. Use the following context to make decisions.

## Relevant Runbooks
{self.format_runbooks(context['runbooks'])}

## Similar Past Decisions
{self.format_decisions(context['past_decisions'])}

## Relevant Documentation
{self.format_docs(context['documentation'])}

## Current Query
{query}

Based on the context above, provide your analysis and recommendation.
If a runbook matches closely, reference it.
If past decisions are relevant, learn from their outcomes.
"""
        return prompt
```

---

## Part V: Human-in-the-Loop Layer

### Approval Workflow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        APPROVAL WORKFLOW                                 │
│                                                                          │
│  Detection ──▶ Triage ──▶ Retrieve Context ──▶ Generate Solutions       │
│                                                     │                    │
│                                                     ▼                    │
│                               ┌─────────────────────────────────────┐   │
│                               │  Signal: "🔔 Issue Detected"        │   │
│                               │                                      │   │
│                               │  Radarr memory at 95%               │   │
│                               │                                      │   │
│                               │  Similar to: runbook-mem-001 (89%)  │   │
│                               │  Last time: memory increase worked  │   │
│                               │                                      │   │
│                               │  [Yes, investigate] [No, expected]  │   │
│                               └─────────────────────────────────────┘   │
│                                                     │                    │
│                                                     │ "Yes"             │
│                                                     ▼                    │
│                               ┌─────────────────────────────────────┐   │
│                               │  Signal: "📋 Solutions"             │   │
│                               │                                      │   │
│                               │  1. Increase memory 1GB→2GB         │   │
│                               │     Past success: 4/4 (100%)        │   │
│                               │     Confidence: 92%                 │   │
│                               │                                      │   │
│                               │  2. Restart pod (temporary)         │   │
│                               │     Past success: 3/3 (100%)        │   │
│                               │     Confidence: 88%                 │   │
│                               │                                      │   │
│                               │  [1] [2] [ignore] [custom]          │   │
│                               └─────────────────────────────────────┘   │
│                                                     │                    │
│                                                     │ "1"               │
│                                                     ▼                    │
│  Execute ──▶ Monitor ──▶ Record Outcome ──▶ Update Vectors ──▶ Learn   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Progressive Autonomy Levels

```yaml
# autonomy-config.yaml
levels:
  # Level 0: Notify only, no action
  notify_only:
    actions: []
    description: "Just tell me about issues"
    
  # Level 1: Propose solutions, await approval
  propose:
    actions: [analyze, retrieve, propose]
    description: "Research and suggest, I'll decide"
    
  # Level 2: Execute with approval
  supervised:
    actions: [analyze, retrieve, propose, execute_on_approval]
    description: "Do it when I say yes"
    
  # Level 3: Standard changes auto-execute
  standard_auto:
    actions: [analyze, retrieve, propose, execute_standard, await_approval_for_new]
    description: "Trusted fixes auto-run, new stuff needs approval"
    
  # Level 4: Execute, notify after
  autonomous_notify:
    actions: [analyze, retrieve, decide, execute, notify]
    description: "Handle it, let me know what you did"
    
  # Level 5: Full autonomy (specific domains)
  full_auto:
    actions: [analyze, retrieve, decide, execute]
    description: "You've got this, only escalate emergencies"

# Per-domain autonomy
domain_levels:
  media_stack:
    level: standard_auto
    includes: [sonarr, radarr, plex, prowlarr]
    
  infrastructure:
    level: supervised
    includes: [kubernetes, argocd, storage]
    
  network:
    level: propose
    includes: [opnsense, cloudflare, dns]
    
  security:
    level: notify_only
    includes: [firewall_rules, certificates, access]
```

### Runbook Promotion Criteria

```python
"""Automatic promotion of runbooks to standard changes."""

@dataclass
class PromotionCriteria:
    min_approvals: int = 5
    min_success_rate: float = 0.95
    days_since_failure: int = 30
    max_blast_radius: str = "single_pod"
    must_be_reversible: bool = True

async def evaluate_promotion(runbook: Runbook) -> bool:
    """Check if runbook should be promoted to standard change."""
    criteria = PromotionCriteria()
    
    # Get execution history
    executions = await get_runbook_executions(runbook.id)
    
    # Check approval count
    approved = [e for e in executions if e.human_feedback == "approved"]
    if len(approved) < criteria.min_approvals:
        return False
    
    # Check success rate
    successful = [e for e in executions if e.outcome.success]
    success_rate = len(successful) / len(executions)
    if success_rate < criteria.min_success_rate:
        return False
    
    # Check recency of failures
    failures = [e for e in executions if not e.outcome.success]
    if failures:
        last_failure = max(f.timestamp for f in failures)
        days_ago = (datetime.utcnow() - last_failure).days
        if days_ago < criteria.days_since_failure:
            return False
    
    # Check blast radius
    if runbook.blast_radius not in ["single_pod", "single_service"]:
        return False
    
    # Check reversibility
    if not runbook.has_rollback:
        return False
    
    return True

async def promote_runbook(runbook: Runbook):
    """Promote runbook to standard change."""
    runbook.automation_level = "standard"
    await save_runbook(runbook)
    
    # Notify human
    await send_signal(f"""
    🎉 Runbook Promoted to Standard Change
    
    {runbook.name}
    
    Based on:
    - {runbook.approval_count} successful approvals
    - {runbook.success_rate*100:.0f}% success rate
    - No failures in {runbook.days_since_failure} days
    
    This will now auto-execute when triggered.
    Reply 'demote {runbook.id}' to revert.
    """)
```

### Weekly Learning Report

```python
"""Generate weekly learning report."""

async def generate_weekly_report() -> str:
    report = f"""
📊 **Weekly Learning Report** ({date_range})

## Actions Summary
- Auto-executed (standard): {auto_count}
- With approval: {approved_count}
- Declined by human: {declined_count}
- Failed actions: {failed_count}

## Knowledge Growth
- New runbooks created: {new_runbooks}
- Runbooks promoted to standard: {promoted}
- Patterns learned: {new_patterns}
- Documentation ingested: {new_docs}

## Model Usage
- Local inference: {local_calls} calls ({local_pct}%)
- Cloud inference: {cloud_calls} calls ({cloud_pct}%)
- Average confidence: {avg_confidence:.0%}
- Retrieval hit rate: {retrieval_hits:.0%}

## Learning Insights
{format_insights(insights)}

## Recommendations
{format_recommendations(recommendations)}

## Your Preferences Observed
- Response time: {avg_response_time} (you like quick approvals)
- Preferred solutions: {preferred_solution_types}
- Topics you always approve: {auto_approve_topics}
- Topics requiring careful review: {careful_topics}

## Next Week
- Scheduled queries: {scheduled_queries}
- Pending promotions: {pending_promotions}
- Items needing review: {review_items}
"""
    return report
```

---

## Part VI: MCP Server Layer

### Server Architecture

```
LangGraph Orchestrator
         │
         ├──▶ home-assistant-mcp ──▶ Home Assistant API
         │                           ├── Lights (Tasmota)
         │                           ├── Climate
         │                           └── Automations
         │
         ├──▶ arr-suite-mcp ──▶ *arr APIs
         │                      ├── Sonarr
         │                      ├── Radarr
         │                      ├── Prowlarr
         │                      └── SABnzbd
         │
         ├──▶ infrastructure-mcp ──▶ K8s / System
         │                           ├── kubectl
         │                           ├── ArgoCD
         │                           └── MinIO
         │
         ├──▶ network-mcp ──▶ Network Infra
         │                    ├── OPNsense
         │                    ├── Cloudflare
         │                    └── UniFi
         │
         └──▶ knowledge-mcp ──▶ Knowledge Base
                               ├── Qdrant search
                               ├── Runbook lookup
                               └── Documentation
```

### Knowledge MCP Server

```python
"""MCP server for knowledge base operations."""
from fastmcp import FastMCP
from qdrant_client import QdrantClient

mcp = FastMCP(name="knowledge-mcp")
qdrant = QdrantClient(host="qdrant", port=6333)
embedder = EmbeddingService(mode="local")

@mcp.tool()
async def search_runbooks(query: str, limit: int = 5) -> list:
    """Search for relevant runbooks based on the issue description."""
    embedding = await embedder.embed([query])
    results = qdrant.search(
        collection_name="runbooks",
        query_vector=embedding[0],
        limit=limit
    )
    return [
        {
            "id": r.id,
            "score": r.score,
            "name": r.payload.get("name"),
            "trigger": r.payload.get("trigger"),
            "solutions": r.payload.get("solutions"),
            "success_rate": r.payload.get("success_rate"),
            "automation_level": r.payload.get("automation_level")
        }
        for r in results
    ]

@mcp.tool()
async def search_past_decisions(query: str, limit: int = 5) -> list:
    """Search for similar past decisions and their outcomes."""
    embedding = await embedder.embed([query])
    results = qdrant.search(
        collection_name="decisions",
        query_vector=embedding[0],
        limit=limit
    )
    return [
        {
            "id": r.id,
            "score": r.score,
            "trigger": r.payload.get("trigger"),
            "action": r.payload.get("action"),
            "outcome": r.payload.get("outcome"),
            "human_feedback": r.payload.get("human_feedback")
        }
        for r in results
    ]

@mcp.tool()
async def search_documentation(query: str, limit: int = 5) -> list:
    """Search ingested documentation for relevant information."""
    embedding = await embedder.embed([query])
    results = qdrant.search(
        collection_name="documentation",
        query_vector=embedding[0],
        limit=limit
    )
    return [
        {
            "source": r.payload.get("source"),
            "content": r.payload.get("content"),
            "score": r.score
        }
        for r in results
    ]

@mcp.tool()
async def record_decision(decision: dict) -> str:
    """Record a decision and its outcome for future learning."""
    text = f"""
    Trigger: {decision['trigger']}
    Action: {decision['action']}
    Reasoning: {decision['reasoning']}
    Outcome: {decision['outcome']}
    """
    embedding = await embedder.embed([text])
    
    qdrant.upsert(
        collection_name="decisions",
        points=[PointStruct(
            id=decision['id'],
            vector=embedding[0],
            payload=decision
        )]
    )
    return f"Recorded decision {decision['id']}"

@mcp.tool()
async def get_user_preferences() -> dict:
    """Retrieve learned user preferences."""
    # Aggregate from past decisions
    decisions = qdrant.scroll(
        collection_name="decisions",
        limit=1000
    )
    
    preferences = analyze_preferences(decisions)
    return preferences
```

---

## Part VII: Observability & Feedback

### Metrics Collection

```yaml
# Key metrics for the learning system
metrics:
  # Inference metrics
  - inference_requests_total{model, mode}
  - inference_latency_seconds{model, mode}
  - inference_confidence{model}
  
  # Retrieval metrics
  - retrieval_requests_total{collection}
  - retrieval_hit_rate{collection}
  - retrieval_latency_seconds{collection}
  
  # Decision metrics
  - decisions_total{outcome, human_feedback}
  - decision_confidence_histogram
  - time_to_human_response_seconds
  
  # Learning metrics
  - runbooks_total{automation_level}
  - runbook_promotions_total
  - knowledge_base_size{collection}
  
  # Autonomy metrics
  - auto_executed_actions_total{domain}
  - human_overrides_total{domain}
  - escalation_rate{domain}
```

### Grafana Dashboard Panels

```
┌─────────────────────────────────────────────────────────────────┐
│  LEARNING SYSTEM DASHBOARD                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ Decisions   │  │ Success     │  │ Autonomy    │             │
│  │ Today: 12   │  │ Rate: 94%   │  │ Level: 67%  │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Decision Outcomes Over Time                             │   │
│  │  ████████████████░░░░ Auto-executed                     │   │
│  │  ██████████░░░░░░░░░░ Human approved                    │   │
│  │  ██░░░░░░░░░░░░░░░░░░ Human rejected                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────┐  ┌──────────────────────┐           │
│  │  Model Usage         │  │  Knowledge Growth     │           │
│  │  Local: 65%          │  │  Runbooks: 47         │           │
│  │  Cloud: 35%          │  │  Decisions: 1,247     │           │
│  │                      │  │  Docs: 89 pages       │           │
│  └──────────────────────┘  └──────────────────────┘           │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Retrieval Quality                                       │   │
│  │  Runbook matches: 89% relevance                         │   │
│  │  Doc hits: 76% useful                                   │   │
│  │  Decision similarity: 82% accurate                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part VIII: GitOps & Deployment

### Repository Structure

```
homelab-ai/
├── apps/
│   ├── ai-platform/
│   │   ├── ollama/
│   │   ├── qdrant/
│   │   ├── litellm/
│   │   ├── langgraph/
│   │   └── signal-cli/
│   ├── mcp-servers/
│   │   ├── home-assistant/
│   │   ├── arr-suite/
│   │   ├── infrastructure/
│   │   ├── network/
│   │   └── knowledge/
│   └── observability/
│       ├── coroot/
│       ├── prometheus/
│       └── grafana/
├── infrastructure/
│   ├── talos/
│   │   ├── talconfig.yaml
│   │   └── patches/
│   └── storage/
├── knowledge/
│   ├── runbooks/
│   │   └── *.yaml
│   ├── documentation/
│   │   └── *.md
│   └── prompts/
│       └── *.yaml
├── secrets/
│   └── .sops.yaml
└── argocd/
    └── app-of-apps.yaml
```

### ArgoCD App-of-Apps

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: homelab-ai
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/yourrepo/homelab-ai
    path: argocd
    targetRevision: HEAD
  destination:
    server: https://kubernetes.default.svc
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

---

## Part IX: Implementation Timeline

### Phase 1: Foundation (Week 1-2)
- [ ] Install Talos Linux on UM690L
- [ ] Configure AMD GPU extensions
- [ ] Deploy ArgoCD + SOPS
- [ ] Set up Renovate
- [ ] Deploy PostgreSQL + Redis

### Phase 2: Inference Layer (Week 2-3)
- [ ] Deploy Ollama with AMD optimizations
- [ ] Pull Qwen 2.5 3B + nomic-embed-text
- [ ] Validate local inference (target: 35+ t/s)
- [ ] Deploy LiteLLM with routing config
- [ ] Connect Gemini + Claude APIs

### Phase 3: Knowledge Base (Week 3-4)
- [ ] Deploy Qdrant
- [ ] Create collection schemas
- [ ] Build embedding pipeline
- [ ] Ingest initial documentation
- [ ] Test retrieval quality

### Phase 4: MCP Servers (Week 4-5)
- [ ] Build knowledge-mcp
- [ ] Build infrastructure-mcp
- [ ] Build home-assistant-mcp
- [ ] Build arr-suite-mcp
- [ ] Test tool execution

### Phase 5: Human-in-the-Loop (Week 5-6)
- [ ] Deploy Signal CLI
- [ ] Build notification service
- [ ] Build approval handler
- [ ] Configure autonomy levels
- [ ] Create initial runbooks

### Phase 6: Observability (Week 6-7)
- [ ] Deploy Coroot
- [ ] Deploy Prometheus + Grafana
- [ ] Build learning dashboard
- [ ] Configure alert → AI pipeline

### Phase 7: Go Live (Week 7-8)
- [ ] Enable VERBOSE MODE
- [ ] Start learning cycle
- [ ] Monitor all decisions
- [ ] Tune retrieval quality
- [ ] First runbook promotions

### Phase 8: Progressive Autonomy (Month 3+)
- [ ] Promote high-confidence runbooks
- [ ] Expand domain autonomy
- [ ] Reduce notification frequency
- [ ] Quarterly trust reviews

---

## Appendix: Configuration Reference

### Mode Switching

```bash
# Set inference mode via ConfigMap
kubectl patch configmap ai-config -n ai-platform \
  --patch '{"data": {"INFERENCE_MODE": "local_first"}}'

# Modes: local_only, cloud_only, local_first, cloud_first, hybrid
```

### Environment Variables

```bash
# Ollama (AMD APU)
HSA_OVERRIDE_GFX_VERSION=10.3.0
OLLAMA_FLASH_ATTENTION=1
OLLAMA_KV_CACHE_TYPE=q8_0
OLLAMA_KEEP_ALIVE=10m
GGML_VULKAN=1

# Cloud APIs
GEMINI_API_KEY=your-key
ANTHROPIC_API_KEY=your-key

# Routing
INFERENCE_MODE=local_first
CLOUD_ESCALATION_THRESHOLD=0.6
LOCAL_CONFIDENCE_THRESHOLD=0.85

# Learning
PROMOTION_MIN_APPROVALS=5
PROMOTION_MIN_SUCCESS_RATE=0.95
```

### Port Reference

| Service | Port | Protocol |
|---------|------|----------|
| Ollama | 11434 | HTTP |
| Qdrant REST | 6333 | HTTP |
| Qdrant gRPC | 6334 | gRPC |
| LiteLLM | 4000 | HTTP |
| LangGraph | 8000 | HTTP |
| Signal CLI | 8080 | HTTP |
| MCP Servers | 8001-8010 | HTTP/SSE |
| Prometheus | 9090 | HTTP |
| Grafana | 3000 | HTTP |
| Coroot | 8081 | HTTP |
| ArgoCD | 8443 | HTTPS |

---

## Conclusion

This architecture creates a **genuinely learning system** - not just automation, but an AI that:

1. **Remembers** every decision, outcome, and your feedback
2. **Retrieves** relevant context before acting
3. **Reasons** using local or cloud models as appropriate
4. **Acts** through MCP tools with human approval
5. **Learns** from outcomes and updates its knowledge

**The key insight**: Autonomy is earned, not configured. The system starts by asking permission for everything, then gradually proves it can be trusted with more independence.

**Flexibility built-in**: Switch between local-only, cloud-only, or hybrid inference based on your needs—privacy, offline operation, or maximum quality.

**The learning loop is the differentiator**: Every interaction makes the system smarter. In six months, it will know your homelab better than any generic AI ever could.