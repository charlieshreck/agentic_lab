# AdGuardFiltersStale

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | AdGuardFiltersStale |
| **Severity** | Warning |
| **Source** | error-hunter sweep (AdGuard API) |
| **Clusters Affected** | Global (AdGuard on OPNsense 10.10.0.1) |

## Description

This alert fires when one or more AdGuard Home filter lists have not been updated within the expected threshold (typically 7 days). Stale filters mean new threats, malware domains, and unwanted content may not be blocked.

**AdGuard Home**: Running on OPNsense (10.10.0.1), port 3000
**Auth**: Infisical `/infrastructure/adguard/` (USERNAME, PASSWORD)

## Quick Diagnosis

### 1. Check filter status

```
# Via MCP tool (preferred)
mcp__home__adguard_get_filtering_status()
# Check last_updated timestamps on enabled filters
```

### 2. Check auto-update interval

The filtering config includes an `interval` field (in hours). If set to `0`, auto-update is disabled.

```bash
curl -s "http://10.10.0.1:3000/control/filtering/status" -u "chaz:$PASSWORD" | python3 -m json.tool
# Check the "interval" field
```

## Common Causes

### 1. Auto-Update Interval Disabled (interval=0)

**Symptoms:**
- All filters show the same last_updated date
- The `interval` field in filtering config is `0`

**Verification:**
```bash
curl -s "http://10.10.0.1:3000/control/filtering/status" -u "chaz:$PASSWORD" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'interval={d[\"interval\"]}')"
```

**Resolution:**
```bash
# Get password from Infisical
PASSWORD=$(mcp__infrastructure__get_secret(path="/infrastructure/adguard", key="PASSWORD"))

# Trigger immediate filter refresh
curl -s -X POST "http://10.10.0.1:3000/control/filtering/refresh" \
  -u "chaz:$PASSWORD" -H "Content-Type: application/json" \
  -d '{"whitelist": false}'

# Set auto-update interval to 24 hours
curl -s -X POST "http://10.10.0.1:3000/control/filtering/config" \
  -u "chaz:$PASSWORD" -H "Content-Type: application/json" \
  -d '{"enabled": true, "interval": 24}'
```

### 2. Upstream Filter URL Unreachable

**Symptoms:**
- Some filters update but others don't
- Filter URL returns errors or timeouts

**Verification:**
```bash
# Check if the filter URL is reachable from OPNsense
sshpass -p 'H4ckwh1z' ssh root@10.10.0.1 "fetch -o /dev/null https://cdn.jsdelivr.net/gh/hagezi/dns-blocklists@latest/adblock/pro.txt 2>&1 | head -5"
```

**Resolution:**
- Check DNS resolution on OPNsense
- Check internet connectivity
- Consider switching to mirror URLs if primary is down

### 3. OPNsense/AdGuard Service Restart

**Symptoms:**
- Filters were up to date, then became stale after a reboot
- Auto-update interval reset to 0

**Verification:**
- Check OPNsense uptime: `ssh root@10.10.0.1 "uptime"`
- Check if AdGuard config was reset

**Resolution:**
- Re-apply the auto-update interval setting (see cause 1)

## Active Filter Lists

| Filter | Type | Expected Rules |
|--------|------|---------------|
| AdGuard DNS Popup Hosts | Popup blocking | ~1,260 |
| HaGeZi Pro | General blocking | ~189,785 |
| HaGeZi Threat Intelligence | Threat feeds | ~576,754 |
| HaGeZi NSFW | Adult content | ~69,225 |
| HaGeZi Gambling | Gambling sites | ~187,259 |
| OISD NSFW | Adult content | ~317,812 |
| Child Protection | Child safety | ~243,363 |

## Prevention

1. **Set auto-update interval to 24 hours** — ensures daily filter refreshes
2. **Monitor filter freshness** — error-hunter checks this periodically
3. **After OPNsense updates** — verify AdGuard auto-update interval is preserved
4. **Backup AdGuard config** — export settings before OPNsense upgrades

## Detection Methods

| Method | Status |
|--------|--------|
| error-hunter sweep (AdGuard API) | Active — checks filter last_updated timestamps |
| alerting-pipeline | Active — polls AdGuard via home-mcp |

## Related Runbooks

- [AdGuard Family Protection](/home/agentic_lab/runbooks/infrastructure/adguard-family-protection.md)
- [DNS Architecture](/home/agentic_lab/runbooks/infrastructure/dns-architecture.md)
