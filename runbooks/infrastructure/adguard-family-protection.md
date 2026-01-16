# AdGuard Home Family Protection Configuration

## Overview
AdGuard Home provides DNS-level content filtering for the homelab network. This runbook covers family protection features: parental controls, safe browsing, SafeSearch enforcement, and content filter lists.

## Location
- Server: AdGuard Home on OPNsense (10.10.0.1:3000)
- Web UI: http://10.10.0.1:3000
- Credentials: Infisical `/infrastructure/adguard`

## Current Configuration (2026-01-16)

### Protection Settings
| Setting | Status | Purpose |
|---------|--------|---------|
| Safe Browsing | Enabled | Blocks malware/phishing via Google Safe Browsing |
| Parental Control | Enabled | Blocks adult content categories |
| SafeSearch | Enabled | Enforces safe search on Google, Bing, YouTube, etc. |

### Active Filter Lists

#### Core Protection (~1.7M rules total)
| List | Rules | Purpose |
|------|-------|---------|
| AdGuard DNS filter | 105,212 | Base ad/tracker blocking |
| HaGeZi Pro | 165,153 | Comprehensive ad/tracker/malware |
| HaGeZi Threat Intelligence Feeds | 560,125 | Security threats, malware, phishing |

#### Family Protection
| List | Rules | Purpose |
|------|-------|---------|
| HaGeZi NSFW | 76,743 | Adult content blocking |
| HaGeZi Gambling | 192,859 | Gambling sites blocking |
| OISD NSFW | 369,414 | Additional adult content (comprehensive) |
| Child Protection | 243,363 | Child-specific protections |

#### Legacy (kept for compatibility)
| List | Rules | Purpose |
|------|-------|---------|
| AdAway Default Blocklist | 6,540 | Basic ad blocking |
| Dan Pollock's List | 11,789 | Hosts-based blocking |
| AdGuard DNS Popup Hosts | 1,479 | Popup blocking |

### SafeSearch Enforcement
Enabled for:
- Google
- Bing
- YouTube
- DuckDuckGo
- Yandex
- Pixabay

## MCP Tools

### Check Protection Status
```
Tool: mcp__opnsense__get_adguard_safebrowsing_status
```
Note: May show stale data due to caching. Use direct API for real-time status.

### Check Filter Lists
```
Tool: mcp__opnsense__get_adguard_filters
```

## Direct API Access

### Credentials
```bash
ADGUARD_USER=$(/root/.config/infisical/secrets.sh get /infrastructure/adguard username)
ADGUARD_PASS=$(/root/.config/infisical/secrets.sh get /infrastructure/adguard password)
```

### Check Protection Status
```bash
# Safe Browsing
curl -s -u "${ADGUARD_USER}:${ADGUARD_PASS}" \
  'http://10.10.0.1:3000/control/safebrowsing/status'

# Parental Control
curl -s -u "${ADGUARD_USER}:${ADGUARD_PASS}" \
  'http://10.10.0.1:3000/control/parental/status'

# SafeSearch
curl -s -u "${ADGUARD_USER}:${ADGUARD_PASS}" \
  'http://10.10.0.1:3000/control/safesearch/status'
```

### Enable/Disable Protection
```bash
# Enable Safe Browsing
curl -s -u "${ADGUARD_USER}:${ADGUARD_PASS}" -X POST \
  'http://10.10.0.1:3000/control/safebrowsing/enable'

# Disable Safe Browsing
curl -s -u "${ADGUARD_USER}:${ADGUARD_PASS}" -X POST \
  'http://10.10.0.1:3000/control/safebrowsing/disable'

# Enable Parental Control
curl -s -u "${ADGUARD_USER}:${ADGUARD_PASS}" -X POST \
  'http://10.10.0.1:3000/control/parental/enable'

# Enable SafeSearch (all engines)
curl -s -u "${ADGUARD_USER}:${ADGUARD_PASS}" -X PUT \
  'http://10.10.0.1:3000/control/safesearch/settings' \
  -H 'Content-Type: application/json' \
  -d '{"enabled": true, "bing": true, "duckduckgo": true, "google": true, "pixabay": true, "yandex": true, "youtube": true}'
```

### Manage Filter Lists
```bash
# Add a filter list
curl -s -u "${ADGUARD_USER}:${ADGUARD_PASS}" -X POST \
  'http://10.10.0.1:3000/control/filtering/add_url' \
  -H 'Content-Type: application/json' \
  -d '{"name": "List Name", "url": "https://example.com/list.txt", "whitelist": false}'

# Remove a filter list
curl -s -u "${ADGUARD_USER}:${ADGUARD_PASS}" -X POST \
  'http://10.10.0.1:3000/control/filtering/remove_url' \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.com/list.txt", "whitelist": false}'

# Refresh all filter lists
curl -s -u "${ADGUARD_USER}:${ADGUARD_PASS}" -X POST \
  'http://10.10.0.1:3000/control/filtering/refresh' \
  -H 'Content-Type: application/json' \
  -d '{"whitelist": false}'
```

## Recommended Filter Lists

### HaGeZi Lists (Recommended)
| List | URL | Purpose |
|------|-----|---------|
| Pro | `https://cdn.jsdelivr.net/gh/hagezi/dns-blocklists@latest/adblock/pro.txt` | Balanced blocking |
| Pro++ | `https://cdn.jsdelivr.net/gh/hagezi/dns-blocklists@latest/adblock/proplus.txt` | Aggressive (may break shopping) |
| TIF | `https://cdn.jsdelivr.net/gh/hagezi/dns-blocklists@latest/adblock/tif.txt` | Threat intelligence |
| NSFW | `https://cdn.jsdelivr.net/gh/hagezi/dns-blocklists@latest/adblock/nsfw.txt` | Adult content |
| Gambling | `https://cdn.jsdelivr.net/gh/hagezi/dns-blocklists@latest/adblock/gambling.txt` | Gambling |
| Fake | `https://cdn.jsdelivr.net/gh/hagezi/dns-blocklists@latest/adblock/fake.txt` | Scams, fraud |

### OISD Lists
| List | URL | Purpose |
|------|-----|---------|
| NSFW | `https://nsfw.oisd.nl` | Comprehensive adult content |
| Full | `https://big.oisd.nl` | Full blocking (aggressive) |

### Child Protection
| List | URL | Purpose |
|------|-----|---------|
| RPiList Child Protection | `https://raw.githubusercontent.com/RPiList/specials/master/Blocklisten/child-protection` | Child-specific |

## Per-Client Configuration (Future)

AdGuard Home supports client-specific settings. This allows different protection levels per device.

### Potential Groups
| Group | Devices | Settings |
|-------|---------|----------|
| Adults | Wife's iPhone, Mac | No parental controls, basic blocking |
| Kids | iPad, Pixel, iMac | Full parental controls, all filters |

### Implementation
1. Define clients in AdGuard Home → Settings → Client Settings
2. Assign devices by MAC address (more reliable than IP)
3. Configure per-client filter lists and protection settings

## Troubleshooting

### Site Incorrectly Blocked
1. Check query log: `mcp__opnsense__get_adguard_query_log`
2. Identify blocking list from log
3. Add allowlist rule:
   ```bash
   # Add to user rules via API
   curl -s -u "${ADGUARD_USER}:${ADGUARD_PASS}" -X POST \
     'http://10.10.0.1:3000/control/filtering/set_rules' \
     -H 'Content-Type: application/json' \
     -d '{"rules": ["@@||example.com^$important"]}'
   ```

### Gaming Issues (Roblox, Minecraft)
- Roblox analytics (`ecsv2.roblox.com`) may be blocked - allowlist if issues
- Minecraft/Mojang authentication domains are not blocked

### Streaming Issues (Netflix, Disney+)
- All major streaming compatible with HaGeZi Pro
- If issues, check for CDN domains in query log

### Shopping Links Not Working
- Using HaGeZi Pro (NOT Pro++) specifically to preserve Google Ads shopping links
- If shopping links break, check if Pro++ was accidentally added

## Current Allowlist

```
@@||a1.api.bbc.co.uk^$important
@@||bbcsmarttv.2cnt.net^$important
@@||r.bbci.co.uk^$important
@@||bbcandroid.2cnt.net^$important
@@||bbcios.2cnt.net^$important
@@||a1-api-bbc-co-uk-cddc.at-o.net^$important
@@||mybbc-analytics.files.bbci.co.uk^$important
@@||urbanoutfitters.com^$important
```

## Related Runbooks
- `adguard-rewrite.md` - DNS rewrites for internal services
- `dns-architecture.md` - Split-DNS architecture (AdGuard + Unbound)

## Maintenance

### Update Filter Lists
Lists auto-update on configured interval. To force refresh:
```bash
curl -s -u "${ADGUARD_USER}:${ADGUARD_PASS}" -X POST \
  'http://10.10.0.1:3000/control/filtering/refresh' \
  -H 'Content-Type: application/json' \
  -d '{"whitelist": false}'
```

### Monitor Blocking Rate
Check stats via: `mcp__adguard__adguard_get_stats`
- Target: 25-35% blocking rate for family protection
- Lower than 20% may indicate issues with filter lists

## Change History

| Date | Change | By |
|------|--------|-----|
| 2026-01-16 | Initial family protection setup: enabled Safe Browsing, Parental Control, SafeSearch; added HaGeZi Pro/TIF/NSFW/Gambling, OISD NSFW, Child Protection lists | Claude |
