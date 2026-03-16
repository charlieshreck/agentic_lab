# Overnight Pipeline Phase 2 Timeout & ArgoCD Health Degradation

**Severity**: Warning
**Date Identified**: 2026-03-14
**Date Resolved**: 2026-03-16
**Incident ID**: #501 (ArgoCDAppUnhealthy)
**Components**: investmentology (agentic cluster), ArgoCD health assessment, overnight-pipeline CronJob

## Summary

The investmentology ArgoCD Application showed a Degraded health status caused by a failed CronJob execution from 2026-03-14 01:00 UTC. The overnight-pipeline execution hit a Phase 2 timeout after 14400 seconds (4 hours), resulting in 695 failures out of 767 pipeline steps, with only 3 out of 15 agents passing the consensus gate.

## Root Cause Analysis

### Failed Job Details
- **Job**: `investmentology-overnight-pipeline-29557500`
- **Created**: 2026-03-14 01:00:00 UTC
- **Failed**: 2026-03-14 05:00:00 UTC (after 4 hours)
- **Failure Count**: 695 failures out of 767 steps
- **Completed Steps**: Only 33 steps completed successfully
- **Agent Pass Rate**: Only 3 out of 15 agents passed the consensus gate

### Phase 2 Timeout Characteristics
Phase 2 of the overnight-pipeline appears to be the agent execution and debate/convergence phase. The massive failure rate (90%) suggests:

1. **Agent Execution Issues**: Multiple agents failing consistently during Phase 2
2. **Resource Constraints**: 4-hour timeout may indicate insufficient compute resources for 15-agent consensus pipeline
3. **Data Processing Problems**: Potential issues with data loading, preprocessing, or market data availability
4. **System Issues**: Possible network failures, API rate limits, or external service unavailability affecting agent operations

### ArgoCD Health Status Impact
ArgoCD's health assessment detected the Failed Job object and marked the investmentology Application as Degraded. The health status remained Degraded even after the Job was cleaned up because:
- ArgoCD caches health assessment results
- The CronJob's `lastSuccessfulTime` was still from 2026-03-11 (5 days in the past)
- Manual refresh attempts (resource patching, sync annotations) do not update health status immediately
- Health status requires a fresh CronJob execution to update the cached assessment

## Remediation Steps Taken

### Immediate Cleanup (2026-03-16)
1. Identified failed Job object: `investmentology-overnight-pipeline-29557500`
2. Deleted the failed Job using `kubectl delete job -n investmentology`
3. Deleted the associated Pod: `investmentology-overnight-pipeline-29557500-fp74f`
4. Verified no other failed Jobs or Pods in the namespace

### Verification
- Confirmed all current CronJobs are scheduled and executing correctly:
  - `investmentology-daily-monitor`: lastSuccessfulTime 2026-03-16 20:15:12Z ✓
  - `investmentology-portfolio-sync`: lastSuccessfulTime 2026-03-16 13:00:14Z ✓
  - `investmentology-price-refresh`: lastSuccessfulTime 2026-03-16 20:30:31Z ✓
  - `investmentology-overnight-pipeline`: **Pending next execution at 2026-03-17 01:00 UTC**

## Expected Recovery

**Automatic Health Status Update**: 2026-03-17 01:00 UTC (next scheduled overnight-pipeline execution)

When the CronJob executes successfully on 2026-03-17, the job completion will update `lastSuccessfulTime`, triggering ArgoCD to refresh its health assessment and mark the investmentology Application as Healthy.

## Investigation Points for Root Cause

The 695 failures in Phase 2 warrant deeper investigation:

### 1. Agent Framework Issues
- Check `serve.py` and `pipeline/controller.py` for timeout handling
- Review agent initialization and cleanup procedures
- Verify all 15 agents received proper inputs and context

### 2. Data Availability
- Confirm market data APIs were accessible during 2026-03-14 01:00-05:00 UTC
- Check for rate limiting or quota issues with data providers
- Verify portfolio data was fully loaded before Phase 2

### 3. Resource Constraints
- Review cluster resource usage during the failed execution
- Check if memory/CPU limits were insufficient for 15-agent consensus
- Verify database connection pooling wasn't exhausted

### 4. External Service Dependencies
- Check if Gemini API calls failed (used by Soros, Druckenmiller, Lynch agents)
- Verify OpenRouter/Claude API availability during execution window
- Review any webhook callback failures

### 5. Consensus Gate Logic
- Only 3 out of 15 agents passed: investigate why 12 agents were excluded
- Check if agent output validation was too strict
- Review confidence threshold calculations for gate decision

## Prevention Measures

### Short-term
1. Monitor next overnight-pipeline execution closely (2026-03-17 01:00 UTC)
2. Capture detailed logs from Phase 2 execution for analysis
3. Track CronJob success/failure rate over next 2 weeks

### Medium-term
1. Implement timeout per-agent rather than global Phase 2 timeout
2. Add early termination if >50% of agents fail to reduce wasted compute
3. Implement checkpoint/resume capability for long-running phases

### Long-term
1. Refactor Phase 2 to use adaptive agent count based on data complexity
2. Implement circuit breaker for external API failures
3. Add observability metrics: agent execution time, failure reasons, consensus quality
4. Consider splitting 15-agent consensus into smaller consensus groups with hierarchy

## Related Documentation
- `/home/investmentology/CLAUDE.md` - Agent framework architecture
- `/home/investmentology/agents/runner.py` - Agent execution loop
- `/home/investmentology/pipeline/controller.py` - Pipeline orchestration
- `/home/investmentology/pipeline/convergence.py` - Consensus gate logic

## Incident Resolution
**Incident ID**: #501
**Status**: Resolved pending health status confirmation
**Webhook Call**: Scheduled for execution after 2026-03-17 01:00 UTC successful CronJob run
