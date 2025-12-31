# Qdrant Inter-Agent Communication
## Shared Knowledge Substrate for Specialist Agents

---

## Core Principle

Qdrant isn't just storage - it's the **message bus, event log, and shared memory** for all agents. No direct agent-to-agent calls. Everything flows through collections with semantic relationships.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           QDRANT KNOWLEDGE SUBSTRATE                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  sources    │  │  research   │  │  decisions  │  │  runbooks   │        │
│  │  (network)  │  │  (findings) │  │  (actions)  │  │  (patterns) │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                │                │
│         │    ┌───────────┴────────────────┴────────────────┘                │
│         │    │                                                              │
│  ┌──────┴────┴──────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │  documentation   │  │  agent_     │  │  recommen-  │  │  engage-    │   │
│  │  (docs)          │  │  events     │  │  dations    │  │  ment       │   │
│  └──────────────────┘  └──────┬──────┘  └─────────────┘  └─────────────┘   │
│                               │                                             │
│                               │                                             │
│                    ┌──────────┴──────────┐                                  │
│                    │   EVENT BACKBONE    │                                  │
│                    │   (triggers agents) │                                  │
│                    └─────────────────────┘                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   ┌───────────┐        ┌───────────┐        ┌───────────┐
   │  Research │        │  DocOps   │        │ Architect │
   │  Agent    │        │  Agent    │        │  Agent    │
   └───────────┘        └───────────┘        └───────────┘
```

---

## Part I: Collection Schema (Complete)

### 1. `sources` - Research Agent's Network

```python
sources_schema = {
    # Identity
    "id": "keyword",              # hash of URL
    "url": "keyword",
    "domain": "keyword",
    "type": "keyword",            # rss, github, youtube, reddit, blog, discord
    "name": "text",               # Human-readable name
    
    # Discovery
    "discovery_method": "keyword", # citation, community, github_graph, search, manual
    "discovered_at": "datetime",
    "discovered_via": "keyword",   # ID of source/content that led here
    
    # Quality (multi-dimensional)
    "quality_score": "float",      # Composite 0-1
    "signal_density": "float",
    "freshness": "float",
    "authority": "float",
    "relevance": "float",
    "actionability": "float",
    
    # Performance
    "engagement_score": "float",   # Learned from your behavior
    "fetch_count": "integer",
    "items_found": "integer",
    "items_surfaced": "integer",
    "items_clicked": "integer",
    "items_actioned": "integer",
    
    # Status
    "status": "keyword",           # active, paused, probation, pruned
    "last_fetched": "datetime",
    "last_evaluated": "datetime",
    "prune_reason": "text",
    
    # Metadata
    "tags": "keyword[]",
    "related_sources": "keyword[]" # IDs of semantically similar sources
}
```

### 2. `research` - Discovered Findings

```python
research_schema = {
    # Identity
    "id": "keyword",
    "source_id": "keyword",        # FK to sources
    "url": "keyword",
    "title": "text",
    "summary": "text",
    
    # Classification
    "content_type": "keyword",     # article, release, discussion, video, paper
    "topics": "keyword[]",
    "entities": "keyword[]",       # Tools, projects, people mentioned
    
    # Evaluation
    "relevance_score": "float",
    "novelty_score": "float",      # How new/unique is this?
    "impact_score": "float",       # Potential impact on your architecture
    
    # Status
    "status": "keyword",           # new, digested, clicked, evaluated, implemented, dismissed
    "action": "keyword",           # track, evaluate, ignore
    
    # Timestamps
    "discovered_at": "datetime",
    "published_at": "datetime",
    "digested_at": "datetime",
    "actioned_at": "datetime",
    
    # Cross-agent references
    "recommendation_id": "keyword", # If Architect created recommendation from this
    "documentation_id": "keyword"   # If DocOps documented this
}
```

### 3. `agent_events` - The Event Backbone

```python
agent_events_schema = {
    # Identity
    "id": "keyword",
    "event_type": "keyword",       # See event types below
    "timestamp": "datetime",
    
    # Source
    "source_agent": "keyword",     # research, docops, architect, orchestrator, human
    "source_collection": "keyword",
    "source_id": "keyword",
    
    # Target
    "target_agent": "keyword",     # Who should process this
    "target_collection": "keyword",
    
    # Payload
    "payload": "json",             # Event-specific data
    "priority": "keyword",         # critical, high, normal, low
    
    # Processing
    "status": "keyword",           # pending, processing, completed, failed
    "processed_at": "datetime",
    "processed_by": "keyword",
    "result": "json"
}

# Event Types
EVENT_TYPES = {
    # Research Agent events
    "source.discovered": "New source found",
    "source.evaluated": "Source quality assessed",
    "source.pruned": "Source removed from network",
    "finding.new": "New research finding",
    "finding.high_relevance": "Finding scores high on relevance",
    "digest.sent": "Daily digest delivered",
    
    # Human events
    "finding.clicked": "User clicked through to content",
    "finding.evaluate": "User marked for evaluation",
    "finding.irrelevant": "User marked as not relevant",
    "finding.implement": "User wants to implement this",
    
    # DocOps Agent events
    "incident.resolved": "Incident closed, needs documentation",
    "runbook.created": "New runbook generated",
    "runbook.updated": "Existing runbook modified",
    "documentation.gap": "Missing documentation identified",
    "audit.complete": "Weekly audit finished",
    
    # Architect Agent events
    "recommendation.new": "New improvement recommendation",
    "recommendation.approved": "Human approved recommendation",
    "recommendation.rejected": "Human rejected recommendation",
    "review.complete": "Weekly architecture review done",
    "gap.identified": "Architecture gap found",
    
    # System events
    "agent.started": "Agent began processing",
    "agent.completed": "Agent finished cycle",
    "agent.error": "Agent encountered error"
}
```

### 4. `decisions` - Operational History (Existing, Extended)

```python
decisions_schema = {
    # Existing fields
    "id": "keyword",
    "trigger": "text",
    "context": "text",
    "action_taken": "text",
    "outcome": "keyword",
    "human_feedback": "keyword",
    "model_used": "keyword",
    "confidence": "float",
    "timestamp": "datetime",
    
    # New cross-references
    "research_ids": "keyword[]",    # Research findings that informed this
    "runbook_id": "keyword",        # Runbook used/created
    "recommendation_id": "keyword"  # If from Architect recommendation
}
```

### 5. `runbooks` - Operational Knowledge (Existing, Extended)

```python
runbooks_schema = {
    # Existing fields
    "id": "keyword",
    "trigger_pattern": "text",
    "solution": "text",
    "success_rate": "float",
    "approval_count": "integer",
    "automation_level": "keyword",
    "last_used": "datetime",
    
    # New fields
    "documentation_id": "keyword",  # MkDocs page generated
    "source_incident_ids": "keyword[]",  # Incidents that built this
    "related_research": "keyword[]",     # Research that informed this
    "version": "integer",
    "change_history": "json"
}
```

### 6. `documentation` - Docs Index (Existing, Extended)

```python
documentation_schema = {
    # Existing
    "source": "keyword",
    "title": "text",
    "content": "text",
    "doc_type": "keyword",
    "last_updated": "datetime",
    
    # New
    "generated_by": "keyword",      # docops, human, architect
    "source_event_id": "keyword",   # Event that triggered generation
    "git_path": "keyword",          # Path in repo
    "git_sha": "keyword",           # Commit that created/updated
    "pr_url": "keyword",            # PR if pending review
    "status": "keyword",            # draft, pr_pending, published
    "staleness_score": "float",     # How out of date (from audit)
    "related_runbooks": "keyword[]",
    "related_research": "keyword[]"
}
```

### 7. `recommendations` - Architect Output

```python
recommendations_schema = {
    "id": "keyword",
    "title": "text",
    "description": "text",
    "category": "keyword",          # performance, reliability, security, capability
    
    # Scoring
    "impact": "keyword",            # high, medium, low
    "effort": "keyword",            # hours, days, weeks
    "risk": "keyword",              # high, medium, low
    "priority_score": "float",      # Computed from above
    
    # Implementation
    "implementation_steps": "text[]",
    "dependencies": "keyword[]",
    "success_criteria": "text[]",
    
    # Sources
    "source_research": "keyword[]", # Research IDs that informed this
    "source_incidents": "keyword[]", # Incidents that suggested this
    "source_gaps": "keyword[]",     # Documentation gaps
    
    # Status
    "status": "keyword",            # proposed, approved, in_progress, completed, rejected
    "created_at": "datetime",
    "reviewed_at": "datetime",
    "completed_at": "datetime",
    "human_feedback": "text",
    
    # Tracking
    "github_issue": "keyword",      # Issue URL if created
    "documentation_id": "keyword"   # Docs if completed
}
```

### 8. `engagement` - Learning Signal

```python
engagement_schema = {
    "id": "keyword",
    "item_type": "keyword",         # research, recommendation, runbook, doc
    "item_id": "keyword",
    "action": "keyword",            # viewed, clicked, evaluated, implemented, dismissed
    "timestamp": "datetime",
    "context": "json",              # Additional context (position in digest, etc.)
    "feedback": "text"              # Optional human comment
}
```

---

## Part II: Event-Driven Agent Communication

### Event Flow Patterns

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        EVENT FLOW PATTERNS                                   │
└─────────────────────────────────────────────────────────────────────────────┘

1. RESEARCH → ARCHITECT (High Relevance Finding)
   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
   │   Research   │────▶│ agent_events │────▶│  Architect   │
   │   Agent      │     │              │     │  Agent       │
   └──────────────┘     └──────────────┘     └──────────────┘
   
   Event: finding.high_relevance
   Payload: {finding_id, relevance_score, summary}
   Result: Architect evaluates for recommendation

2. HUMAN → ALL AGENTS (Evaluate Request)
   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
   │   Telegram   │────▶│ agent_events │────▶│  All Agents  │
   │   (Human)    │     │              │     │  Subscribe   │
   └──────────────┘     └──────────────┘     └──────────────┘
   
   Event: finding.evaluate
   Payload: {finding_id, user_comment}
   Result: Architect queues for review, Research boosts source

3. ORCHESTRATOR → DOCOPS (Incident Resolved)
   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
   │ Orchestrator │────▶│ agent_events │────▶│   DocOps     │
   │   (main)     │     │              │     │   Agent      │
   └──────────────┘     └──────────────┘     └──────────────┘
   
   Event: incident.resolved
   Payload: {decision_id, trigger, solution, outcome}
   Result: DocOps generates runbook + MkDocs page

4. ARCHITECT → DOCOPS (Recommendation Approved)
   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
   │  Architect   │────▶│ agent_events │────▶│   DocOps     │
   │   Agent      │     │              │     │   Agent      │
   └──────────────┘     └──────────────┘     └──────────────┘
   
   Event: recommendation.approved
   Payload: {recommendation_id, implementation_steps}
   Result: DocOps creates implementation guide

5. DOCOPS → RESEARCH (Documentation Gap)
   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
   │   DocOps     │────▶│ agent_events │────▶│  Research    │
   │   Agent      │     │              │     │  Agent       │
   └──────────────┘     └──────────────┘     └──────────────┘
   
   Event: documentation.gap
   Payload: {topic, missing_info, context}
   Result: Research adds topic to discovery seeds
```

### Event Processing

```python
class AgentEventProcessor:
    """Process events from the Qdrant event backbone."""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.qdrant = QdrantClient(host="qdrant", port=6333)
        self.handlers = {}
    
    def subscribe(self, event_type: str, handler: callable):
        """Subscribe to an event type."""
        self.handlers[event_type] = handler
    
    async def poll_events(self):
        """Poll for pending events targeted at this agent."""
        
        events = await self.qdrant.scroll(
            collection_name="agent_events",
            filter=Filter(
                must=[
                    FieldCondition(key="target_agent", match=MatchValue(value=self.agent_name)),
                    FieldCondition(key="status", match=MatchValue(value="pending"))
                ]
            ),
            order_by="timestamp",
            limit=100
        )
        
        for event in events:
            await self.process_event(event)
    
    async def process_event(self, event):
        """Process a single event."""
        
        event_type = event.payload["event_type"]
        
        if event_type not in self.handlers:
            logging.warning(f"No handler for event type: {event_type}")
            return
        
        # Mark as processing
        await self.qdrant.set_payload(
            collection_name="agent_events",
            payload={"status": "processing"},
            points=[event.id]
        )
        
        try:
            result = await self.handlers[event_type](event.payload)
            
            # Mark as completed
            await self.qdrant.set_payload(
                collection_name="agent_events",
                payload={
                    "status": "completed",
                    "processed_at": datetime.utcnow().isoformat(),
                    "processed_by": self.agent_name,
                    "result": result
                },
                points=[event.id]
            )
            
        except Exception as e:
            await self.qdrant.set_payload(
                collection_name="agent_events",
                payload={
                    "status": "failed",
                    "error": str(e)
                },
                points=[event.id]
            )
    
    async def emit_event(
        self,
        event_type: str,
        target_agent: str,
        payload: dict,
        priority: str = "normal"
    ):
        """Emit an event for another agent."""
        
        event_id = f"{self.agent_name}_{event_type}_{datetime.utcnow().timestamp()}"
        
        await self.qdrant.upsert(
            collection_name="agent_events",
            points=[PointStruct(
                id=event_id,
                vector=await self.embed(json.dumps(payload)),  # Semantic searchable
                payload={
                    "id": event_id,
                    "event_type": event_type,
                    "timestamp": datetime.utcnow().isoformat(),
                    "source_agent": self.agent_name,
                    "target_agent": target_agent,
                    "payload": payload,
                    "priority": priority,
                    "status": "pending"
                }
            )]
        )
```

---

## Part III: Agent Implementations

### Research Agent - Event Wiring

```python
class ResearchAgent:
    def __init__(self):
        self.events = AgentEventProcessor("research")
        self.qdrant = QdrantClient(host="qdrant", port=6333)
        
        # Subscribe to events
        self.events.subscribe("finding.clicked", self.on_finding_clicked)
        self.events.subscribe("finding.evaluate", self.on_finding_evaluate)
        self.events.subscribe("finding.irrelevant", self.on_finding_irrelevant)
        self.events.subscribe("documentation.gap", self.on_documentation_gap)
    
    async def on_finding_clicked(self, payload: dict):
        """User clicked through - boost source."""
        finding = await self.get_finding(payload["finding_id"])
        await self.boost_source_engagement(finding["source_id"], 0.1)
        return {"action": "source_boosted", "amount": 0.1}
    
    async def on_finding_evaluate(self, payload: dict):
        """User wants to evaluate - strong signal + notify architect."""
        finding = await self.get_finding(payload["finding_id"])
        
        # Boost source significantly
        await self.boost_source_engagement(finding["source_id"], 0.3)
        
        # Update finding status
        await self.update_finding_status(payload["finding_id"], "evaluate_requested")
        
        # Emit event for Architect
        await self.events.emit_event(
            event_type="finding.high_relevance",
            target_agent="architect",
            payload={
                "finding_id": payload["finding_id"],
                "title": finding["title"],
                "summary": finding["summary"],
                "relevance_score": finding["relevance_score"],
                "user_requested": True
            },
            priority="high"
        )
        
        return {"action": "queued_for_architect"}
    
    async def on_documentation_gap(self, payload: dict):
        """DocOps found a gap - add to discovery seeds."""
        topic = payload["topic"]
        
        # Add to seed topics for next discovery cycle
        await self.add_discovery_seed(topic, source="docops_gap")
        
        # Immediately probe search for this topic
        results = await self.probe_search(topic)
        
        return {"action": "seed_added", "immediate_results": len(results)}
    
    async def daily_scan(self):
        """Main daily scan - emit events for findings."""
        
        # ... discovery logic ...
        
        for finding in high_relevance_findings:
            # Emit event for findings above threshold
            if finding["relevance_score"] > 0.8:
                await self.events.emit_event(
                    event_type="finding.high_relevance",
                    target_agent="architect",
                    payload={
                        "finding_id": finding["id"],
                        "title": finding["title"],
                        "summary": finding["summary"],
                        "relevance_score": finding["relevance_score"]
                    }
                )
        
        # Emit digest event
        await self.events.emit_event(
            event_type="digest.sent",
            target_agent="system",  # For logging/metrics
            payload={
                "findings_count": len(findings),
                "sources_fetched": len(sources),
                "new_sources": len(new_sources)
            }
        )
```

### DocOps Agent - Event Wiring

```python
class DocOpsAgent:
    def __init__(self):
        self.events = AgentEventProcessor("docops")
        self.qdrant = QdrantClient(host="qdrant", port=6333)
        self.git = GitHubClient(repo="charlieshreck/monit_homelab")
        
        # Subscribe to events
        self.events.subscribe("incident.resolved", self.on_incident_resolved)
        self.events.subscribe("recommendation.approved", self.on_recommendation_approved)
        self.events.subscribe("recommendation.completed", self.on_recommendation_completed)
    
    async def on_incident_resolved(self, payload: dict):
        """Incident resolved - generate documentation."""
        
        decision_id = payload["decision_id"]
        decision = await self.get_decision(decision_id)
        
        # Check if similar runbook exists
        similar = await self.find_similar_runbooks(decision["trigger"])
        
        if similar and similar[0].score > 0.9:
            # Update existing runbook
            runbook = await self.update_runbook(similar[0].id, decision)
            action = "runbook_updated"
        else:
            # Create new runbook
            runbook = await self.create_runbook(decision)
            action = "runbook_created"
        
        # Generate MkDocs page
        doc = await self.generate_mkdocs_page(runbook)
        
        # Create PR
        pr = await self.git.create_pr(
            branch=f"docs/runbook-{runbook['id']}",
            files={doc["path"]: doc["content"]},
            title=f"📝 Runbook: {runbook['title']}",
            body=f"Auto-generated from incident resolution.\n\nDecision: {decision_id}"
        )
        
        # Store documentation reference
        await self.qdrant.upsert(
            collection_name="documentation",
            points=[PointStruct(
                id=doc["id"],
                vector=await self.embed(doc["content"]),
                payload={
                    "source": doc["path"],
                    "title": runbook["title"],
                    "doc_type": "runbook",
                    "generated_by": "docops",
                    "source_event_id": payload.get("event_id"),
                    "git_path": doc["path"],
                    "pr_url": pr["url"],
                    "status": "pr_pending",
                    "related_runbooks": [runbook["id"]]
                }
            )]
        )
        
        # Notify via Telegram
        await self.notify(
            topic="documentation",
            message=f"📝 **New Runbook PR**\n\n{runbook['title']}\n\n{pr['url']}"
        )
        
        return {"action": action, "runbook_id": runbook["id"], "pr_url": pr["url"]}
    
    async def on_recommendation_approved(self, payload: dict):
        """Architect recommendation approved - create implementation guide."""
        
        rec_id = payload["recommendation_id"]
        rec = await self.get_recommendation(rec_id)
        
        # Generate implementation guide
        guide = await self.generate_implementation_guide(rec)
        
        # Create PR
        pr = await self.git.create_pr(
            branch=f"docs/guide-{rec_id}",
            files={guide["path"]: guide["content"]},
            title=f"📘 Guide: {rec['title']}",
            body=f"Implementation guide for approved recommendation."
        )
        
        return {"action": "guide_created", "pr_url": pr["url"]}
    
    async def weekly_audit(self):
        """Weekly documentation audit."""
        
        gaps = []
        stale = []
        
        # Find runbooks without documentation
        runbooks = await self.get_all_runbooks()
        for runbook in runbooks:
            if not runbook.get("documentation_id"):
                gaps.append({
                    "type": "missing_doc",
                    "runbook_id": runbook["id"],
                    "topic": runbook["trigger_pattern"]
                })
        
        # Find stale documentation
        docs = await self.get_all_documentation()
        for doc in docs:
            if self.is_stale(doc):
                stale.append(doc)
        
        # Find incidents without runbooks
        recent_incidents = await self.get_recent_incidents(days=30)
        for incident in recent_incidents:
            if not incident.get("runbook_id"):
                # Emit gap event to Research Agent
                await self.events.emit_event(
                    event_type="documentation.gap",
                    target_agent="research",
                    payload={
                        "topic": incident["trigger"],
                        "context": incident["context"],
                        "missing_info": "operational_runbook"
                    }
                )
                gaps.append({
                    "type": "missing_runbook",
                    "incident_id": incident["id"],
                    "topic": incident["trigger"]
                })
        
        # Generate audit report
        report = await self.generate_audit_report(gaps, stale)
        
        await self.notify(
            topic="weekly_reports",
            message=report
        )
        
        return {"gaps": len(gaps), "stale": len(stale)}
```

### Architect Agent - Event Wiring

```python
class ArchitectAgent:
    def __init__(self):
        self.events = AgentEventProcessor("architect")
        self.qdrant = QdrantClient(host="qdrant", port=6333)
        self.llm = LiteLLMClient()  # For complex reasoning
        
        # Subscribe to events
        self.events.subscribe("finding.high_relevance", self.on_high_relevance_finding)
        self.events.subscribe("recommendation.approved", self.on_recommendation_approved)
        self.events.subscribe("recommendation.rejected", self.on_recommendation_rejected)
    
    async def on_high_relevance_finding(self, payload: dict):
        """Research found something highly relevant - evaluate for recommendation."""
        
        finding_id = payload["finding_id"]
        finding = await self.get_research_finding(finding_id)
        
        # Get architecture context
        architecture = await self.get_architecture_context()
        
        # Use Claude for deep analysis
        analysis = await self.llm.generate(
            model="claude-sonnet-4-20250514",
            messages=[{
                "role": "system",
                "content": ARCHITECT_AGENT_PROMPT
            }, {
                "role": "user",
                "content": f"""Evaluate this research finding for the architecture:

FINDING:
{json.dumps(finding, indent=2)}

CURRENT ARCHITECTURE:
{architecture}

Should this become a recommendation? If yes, provide:
- Title
- Description
- Impact/Effort/Risk assessment
- Implementation steps
- Success criteria

Respond in JSON.
"""
            }]
        )
        
        result = json.loads(analysis)
        
        if result.get("create_recommendation"):
            # Create recommendation
            rec = await self.create_recommendation(result, source_finding=finding_id)
            
            # Notify human
            await self.notify_recommendation(rec)
            
            return {"action": "recommendation_created", "rec_id": rec["id"]}
        
        return {"action": "finding_noted", "reason": result.get("skip_reason")}
    
    async def on_recommendation_approved(self, payload: dict):
        """Human approved recommendation."""
        
        rec_id = payload["recommendation_id"]
        
        # Update status
        await self.update_recommendation_status(rec_id, "approved")
        
        # Create GitHub issue for tracking
        rec = await self.get_recommendation(rec_id)
        issue = await self.create_github_issue(rec)
        
        # Emit event for DocOps to create implementation guide
        await self.events.emit_event(
            event_type="recommendation.approved",
            target_agent="docops",
            payload={
                "recommendation_id": rec_id,
                "title": rec["title"],
                "implementation_steps": rec["implementation_steps"]
            }
        )
        
        return {"action": "approved", "issue_url": issue["url"]}
    
    async def weekly_review(self):
        """Comprehensive weekly architecture review."""
        
        # Gather all context
        context = {
            "architecture": await self.get_architecture_docs(),
            "incidents": await self.get_recent_incidents(days=30),
            "research_evaluate": await self.get_evaluate_queue(),
            "pending_recommendations": await self.get_pending_recommendations(),
            "documentation_gaps": await self.get_documentation_gaps()
        }
        
        # Deep analysis with Claude
        review = await self.perform_architecture_review(context)
        
        # Generate new recommendations
        for gap in review["identified_gaps"]:
            rec = await self.create_recommendation(gap)
            
        # Update existing recommendations if context changed
        for update in review["recommendation_updates"]:
            await self.update_recommendation(update)
        
        # Generate weekly report
        report = await self.generate_weekly_report(review)
        
        await self.notify(
            topic="weekly_reports",
            message=report
        )
        
        # Emit completion event
        await self.events.emit_event(
            event_type="review.complete",
            target_agent="system",
            payload={
                "new_recommendations": len(review["new_recommendations"]),
                "gaps_identified": len(review["identified_gaps"]),
                "health_score": review["health_score"]
            }
        )
        
        return review
```

---

## Part IV: Semantic Cross-References

### Finding Related Content Across Collections

```python
class CrossCollectionSearch:
    """Search semantically across all collections."""
    
    def __init__(self):
        self.qdrant = QdrantClient(host="qdrant", port=6333)
        self.collections = [
            "sources", "research", "decisions", "runbooks",
            "documentation", "recommendations"
        ]
    
    async def find_related(
        self,
        query: str,
        source_collection: str = None,
        limit_per_collection: int = 3
    ) -> dict:
        """Find related content across all collections."""
        
        embedding = await self.embed(query)
        
        results = {}
        
        for collection in self.collections:
            if collection == source_collection:
                continue  # Skip source collection
            
            hits = await self.qdrant.search(
                collection_name=collection,
                query_vector=embedding,
                limit=limit_per_collection
            )
            
            results[collection] = [
                {
                    "id": hit.id,
                    "score": hit.score,
                    "payload": hit.payload
                }
                for hit in hits
            ]
        
        return results
    
    async def build_context_for_decision(self, trigger: str, alert: dict) -> dict:
        """Build comprehensive context for a decision from all collections."""
        
        query = f"{trigger} {alert.get('message', '')}"
        related = await self.find_related(query)
        
        context = {
            "similar_incidents": related.get("decisions", []),
            "applicable_runbooks": related.get("runbooks", []),
            "relevant_documentation": related.get("documentation", []),
            "related_research": related.get("research", []),
            "pending_recommendations": related.get("recommendations", [])
        }
        
        return context
    
    async def link_entities(self, source_id: str, source_collection: str):
        """Automatically link related entities across collections."""
        
        source = await self.qdrant.retrieve(
            collection_name=source_collection,
            ids=[source_id]
        )
        
        if not source:
            return
        
        # Build query from source content
        query = self.extract_query_text(source[0])
        related = await self.find_related(query, source_collection)
        
        # Store links in source payload
        links = {
            f"related_{collection}": [r["id"] for r in items if r["score"] > 0.7]
            for collection, items in related.items()
        }
        
        await self.qdrant.set_payload(
            collection_name=source_collection,
            payload=links,
            points=[source_id]
        )
```

---

## Part V: Deployment Architecture

### Single Platform Deployment

```yaml
# kubernetes/platform/mcp-system/agents/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: mcp-system

resources:
  # Shared infrastructure
  - qdrant-deployment.yaml
  - qdrant-pvc.yaml
  
  # Agent deployments
  - research-agent-cronjob.yaml
  - docops-agent-cronjob.yaml
  - architect-agent-cronjob.yaml
  
  # Event processor (always running)
  - event-processor-deployment.yaml
  
  # Telegram service
  - telegram-service-deployment.yaml
  
  # MkDocs (continuous)
  - mkdocs-deployment.yaml

configMapGenerator:
  - name: agent-config
    literals:
      - QDRANT_HOST=qdrant.mcp-system.svc.cluster.local
      - QDRANT_PORT=6333
      - OLLAMA_HOST=ollama.mcp-system.svc.cluster.local
      - LITELLM_HOST=litellm.mcp-system.svc.cluster.local
      - TELEGRAM_FORUM_ID=${TELEGRAM_FORUM_ID}
      - GIT_REPO=charlieshreck/monit_homelab
```

### Event Processor (Always Running)

```yaml
# kubernetes/platform/mcp-system/agents/event-processor-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-event-processor
  namespace: mcp-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: agent-event-processor
  template:
    metadata:
      labels:
        app: agent-event-processor
    spec:
      containers:
      - name: processor
        image: ghcr.io/charlieshreck/agent-event-processor:v1
        env:
        - name: POLL_INTERVAL_SECONDS
          value: "10"
        - name: QDRANT_HOST
          valueFrom:
            configMapKeyRef:
              name: agent-config
              key: QDRANT_HOST
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 500m
            memory: 512Mi
```

---

## Part VI: The Complete Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DAILY CYCLE (6am)                                   │
└─────────────────────────────────────────────────────────────────────────────┘

6:00 AM - Research Agent Wakes
    │
    ├─1─▶ Traverse source network (autonomous discovery)
    │     └─▶ Citation crawl, community mine, GitHub graph
    │
    ├─2─▶ Fetch from active sources (quality-ranked)
    │
    ├─3─▶ Evaluate findings (LLM scoring)
    │
    ├─4─▶ Store in Qdrant:research
    │     └─▶ Emit finding.high_relevance for top items
    │
    └─5─▶ Send daily digest to Telegram
          └─▶ Emit digest.sent event

Throughout Day - Human Engagement
    │
    ├─▶ Click finding → finding.clicked event
    │   └─▶ Research Agent boosts source
    │
    ├─▶ Mark "Evaluate" → finding.evaluate event
    │   └─▶ Research boosts source
    │   └─▶ Architect queues for review
    │
    └─▶ Mark "Irrelevant" → finding.irrelevant event
        └─▶ Research penalizes source

Throughout Day - Incident Resolution
    │
    └─▶ Orchestrator resolves incident
        └─▶ incident.resolved event
            └─▶ DocOps creates runbook + MkDocs page + PR

┌─────────────────────────────────────────────────────────────────────────────┐
│                          WEEKLY CYCLE (Sunday)                               │
└─────────────────────────────────────────────────────────────────────────────┘

2:00 AM - DocOps Audit
    │
    ├─▶ Find stale documentation
    ├─▶ Find undocumented runbooks
    ├─▶ Find incidents without runbooks
    │   └─▶ Emit documentation.gap events
    │
    └─▶ Generate audit report → Telegram

10:00 AM - Architect Review
    │
    ├─▶ Gather all context from Qdrant
    ├─▶ Review pending evaluate queue
    ├─▶ Analyze architecture gaps
    ├─▶ Generate recommendations
    │   └─▶ Store in Qdrant:recommendations
    │
    └─▶ Generate weekly report → Telegram
        └─▶ Inline buttons: Approve / Reject / Defer

Human Reviews Recommendations
    │
    ├─▶ Approve → recommendation.approved event
    │   └─▶ DocOps creates implementation guide
    │   └─▶ GitHub issue created
    │
    └─▶ Reject → recommendation.rejected event
        └─▶ Architect learns from feedback
```

---

## Part VII: Collection Initialization

```python
# scripts/init_qdrant_collections.py
"""Initialize all Qdrant collections for the agent system."""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(host="qdrant", port=6333)

COLLECTIONS = {
    "sources": {"size": 768, "distance": Distance.COSINE},
    "research": {"size": 768, "distance": Distance.COSINE},
    "agent_events": {"size": 768, "distance": Distance.COSINE},
    "decisions": {"size": 768, "distance": Distance.COSINE},
    "runbooks": {"size": 768, "distance": Distance.COSINE},
    "documentation": {"size": 768, "distance": Distance.COSINE},
    "recommendations": {"size": 768, "distance": Distance.COSINE},
    "engagement": {"size": 768, "distance": Distance.COSINE},
}

def init_collections():
    for name, config in COLLECTIONS.items():
        try:
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=config["size"],
                    distance=config["distance"]
                )
            )
            print(f"Created collection: {name}")
        except Exception as e:
            if "already exists" in str(e):
                print(f"Collection exists: {name}")
            else:
                raise

if __name__ == "__main__":
    init_collections()
```

---

This is the complete nervous system. Qdrant holds everything, agents communicate through events, and the whole thing learns from your engagement.

Ready to start building the Docker images for these agents?
