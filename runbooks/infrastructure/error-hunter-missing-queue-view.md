# Error-Hunter: Missing Estate Work Queue View

## Symptom
Error-hunter API returns `relation "estate_work_queue" does not exist` when querying `/api/estate/queue` or `/api/estate/incidents`.

```
postgresql ERROR:  relation "estate_work_queue" does not exist at character 15
STATEMENT:  SELECT * FROM estate_work_queue WHERE 1=1 LIMIT $1
```

Pulse agent generates alert: `check (#XXX)` warning on startup.

## Root Cause
The `estate_work_queue` PostgreSQL view is not created in the incident_management database. This happens when:

1. **incident-db-init job** runs and creates base schema (incidents, sweep_runs, error_hunter_findings tables)
2. **error-hunter pod** starts and calls `init_db()` to create the view at runtime
3. View creation fails silently or view definition is incomplete/incorrect
4. Error-hunter still starts (view is not strictly required for startup) but API calls that query the view fail

The view definition exists in:
- ConfigMap: `incident-db-schema` (in full schema.sql after line 147)
- Error-hunter code: `kubernetes/applications/error-hunter/error-hunter.yaml` (init_db function)

## Solution

### Step 1: Verify the View is Missing
```bash
kubectl exec -i postgresql-0 -n ai-platform --context admin@agentic-platform -- \
  sh -c 'PGPASSWORD=$POSTGRES_PASSWORD psql -U $POSTGRES_USER -d incident_management -c "\dv estate_work_queue"'
```

Expected output: `Did not find any relation named "estate_work_queue".`

### Step 2: Create the View Manually
```bash
cat <<'EOF' | kubectl exec -i postgresql-0 -n ai-platform --context admin@agentic-platform -- \
  sh -c 'PGPASSWORD=$POSTGRES_PASSWORD psql -U $POSTGRES_USER -d incident_management'
CREATE OR REPLACE VIEW estate_work_queue AS
SELECT
    item_type, id, name, severity, priority, status, description,
    detected_at, last_updated, resolved_at, incident_id, metadata
FROM (
    SELECT
        'finding' as item_type, id, check_name as name, severity,
        classification as priority, status, description,
        first_seen as detected_at, last_seen as last_updated,
        NULL::timestamptz as resolved_at, incident_id,
        evidence::text as metadata,
        CASE severity WHEN 'critical' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END as severity_order
    FROM error_hunter_findings
    WHERE status NOT IN ('resolved', 'ignored')
    UNION ALL
    SELECT
        'incident' as item_type, id, alert_name as name, severity,
        CASE WHEN severity = 'critical' THEN 'fix_now' ELSE 'create_rule' END as priority,
        status, description, detected_at, updated_at as last_updated,
        resolved_at, NULL::integer as incident_id,
        enrichment::text as metadata,
        CASE severity WHEN 'critical' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END as severity_order
    FROM incidents
    WHERE status NOT IN ('resolved', 'false_positive')
) combined
ORDER BY severity_order, detected_at ASC;

-- Verify
SELECT * FROM estate_work_queue LIMIT 1;
EOF
```

**Key Points:**
- Uses UNION to combine findings and incidents tables
- Requires ORDER BY to be outside the UNION (PostgreSQL constraint)
- Filters out resolved/ignored items to show only active work
- Priority is set based on severity and classification

### Step 3: Verify the Fix
```bash
curl http://10.20.0.40:30801/api/estate/health
```

Expected: `"status": "healthy"`

### Step 4: Check Error-Hunter Logs
```bash
kubectl logs error-hunter-<pod> -n ai-platform --context admin@agentic-platform -f
```

Should NOT see `relation "estate_work_queue" does not exist` errors.

## Prevention

1. **Ensure schema init runs on cluster startup**: Check incident-db-init job ConfigMap includes error-hunter section
2. **Verify view creation in error-hunter**: Check error-hunter pod logs on startup for `init_db: schema extensions applied`
3. **Test API endpoints after deployment**: Run curl tests against error-hunter health/queue endpoints during deployment validation

## Related
- ConfigMap: `/home/agentic_lab/kubernetes/applications/incident-db/schema-configmap.yaml`
- Error-hunter code: `/home/agentic_lab/kubernetes/applications/error-hunter/error-hunter.yaml` (lines with init_db)
- Knowledge: Estate operations, Unified queue design

## History
- **2026-02-26**: Incident #215 - View missing after PostgreSQL init, manually created
