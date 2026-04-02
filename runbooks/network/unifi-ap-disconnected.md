# UniFi AP Disconnected

## Alert
- **Name**: UniFi-AP-Disconnected
- **Domain**: network
- **Severity**: warning
- **Source**: Estate Patrol sweep (`mcp__home__unifi_list_devices`)

## Symptoms
- UniFi controller shows AP with `state: 0` (disconnected)
- AP IP address not responding to ping
- 0 clients associated with the AP
- Other APs remain healthy

## Investigation Steps

1. **Verify from UniFi controller**:
   ```
   mcp__home__unifi_list_devices
   ```
   Look for `state: 0` or `state: 4` (disconnected/adopting).

2. **Ping the AP**:
   ```bash
   ping -c 3 <AP_IP>
   ```

3. **Check if it's a controller-only issue** (AP might be up but disconnected from controller):
   ```bash
   curl -s --connect-timeout 3 http://<AP_IP> 2>/dev/null && echo "HTTP responding" || echo "Unreachable"
   ```

4. **Check PoE port on switch** (if applicable):
   ```
   mcp__infrastructure__omada_get_switch_ports
   ```
   Look for the port connected to the AP — check link status and PoE delivery.

## Root Causes

| Cause | Likelihood | Fix |
|-------|-----------|-----|
| Power loss (PoE or adapter) | High | Check PoE port, power cycle |
| Ethernet cable disconnected | Medium | Physical inspection |
| AP firmware crash | Medium | Power cycle the AP |
| Switch port fault | Low | Move to another port |
| Hardware failure | Low | Replace AP |

## Fix

**This always requires physical inspection.** Estate Patrol cannot fix this remotely.

1. Check the physical location — is the AP powered on (LED status)?
2. Check the ethernet cable connection at both ends
3. If PoE: check the switch port is delivering power
4. Power cycle: unplug and replug the ethernet/power
5. If AP comes back, check for firmware update
6. If AP doesn't come back after power cycle, it may need factory reset or replacement

## Validation

After physical intervention:
```
mcp__home__unifi_list_devices
```
Verify `state: 1` and clients > 0.

## AP Inventory

| AP Name | IP | Model | Location |
|---------|------|-------|----------|
| U7 Pro | 10.10.0.106 | U7PRO | Main area |
| U7-Pro-Wall | 10.10.0.108 | U7PIW | Wall mount |
| U7-Pro-Playroom | 10.10.0.109 | U7PRO | Playroom |

## Lessons Learned
- 2026-04-02: U7-Pro-Playroom found disconnected during 18:00 sweep. Not pingable. Escalated for physical inspection.
