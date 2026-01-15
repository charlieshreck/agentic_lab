# IoT Network Management (Kernow-IoT)

## Overview

Dedicated 2.4GHz WiFi SSID for IoT devices, providing organizational separation and RF optimization without VLAN isolation (due to unmanaged switches).

## Network Details

| Property | Value |
|----------|-------|
| SSID | Kernow-IoT |
| Band | 2.4GHz only |
| Security | WPA2-PSK |
| Password | Same as main network (Kernow) |
| VLAN | None (same subnet as main) |
| Subnet | 10.10.0.0/24 |
| Client Isolation | Disabled |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         IoT Communication                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐         MQTT (1883)          ┌─────────────────┐  │
│  │ MQTT Broker  │◄────────────────────────────►│ Tasmota Devices │  │
│  │ 10.10.0.91   │                              │ (26 devices)    │  │
│  │ mqtt.kernow.io                              │ 10.10.0.191-249 │  │
│  └──────┬───────┘                              └────────┬────────┘  │
│         │                                               │           │
│         │ MQTT                                   HTTP (80)          │
│         ▼                                               │           │
│  ┌──────────────┐                              ┌─────────────────┐  │
│  │ Home         │                              │ Tasmota MCP     │  │
│  │ Assistant    │                              │ (agentic)       │  │
│  │ 10.10.0.144  │                              │ Port 31100      │  │
│  └──────────────┘                              └─────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Devices on Kernow-IoT

### Tasmota (26 devices - Automated Migration)
All Tasmota devices were migrated on 2026-01-15 using the Tasmota MCP.

Configuration applied:
- SSID1: Kernow-IoT (primary)
- SSID2: Kernow (fallback)

### Other IoT Devices (Manual Migration Required)
Tracked in Vikunja project "IoT Network Migration" (ID: 18):
- Nest Thermostats (3)
- Nest Protects (6)
- Nest Hello Doorbell + Cam (2)
- Google Home/Mini/Audio (9)
- Chromecast (2)
- Meross Smart Plugs (2)
- Twinkly Lights (1)
- Fellow Aiden Kettle (1)
- WiFi Washing Machine (1)

## Adding New Tasmota Device

```bash
# Using Tasmota MCP
tasmota_command(ip, "Backlog SSID1 Kernow-IoT; Password1 <password>; SSID2 Kernow; Password2 <password>")
tasmota_restart(ip)

# Verify
tasmota_command(ip, "Status 11")  # Check SSId field
```

## Adding Other IoT Device

1. Open device's app (Google Home, Meross, Twinkly, etc.)
2. Navigate to device settings → WiFi
3. Select "Kernow-IoT" network
4. Enter password
5. Verify in UniFi dashboard

## Verification

### Check Device SSID (Tasmota)
```bash
tasmota_command(ip, "Status 11")
# Look for: "SSId": "Kernow-IoT"
```

### Check UniFi Clients
```bash
# Via UniFi MCP
unifi_list_clients(search="device_name")
# Verify wlanconf_id matches Kernow-IoT
```

## Troubleshooting

### Device Won't Connect to Kernow-IoT
1. Verify device supports 2.4GHz (5GHz-only devices won't work)
2. Check password is correct
3. Ensure device is in range of AP broadcasting Kernow-IoT

### Tasmota Fallback Behavior
If Tasmota device can't reach SSID1, it automatically tries SSID2 after 3 connection failures. This provides resilience if Kernow-IoT has issues.

### MQTT Connection Lost After Migration
- Verify MQTT broker (mqtt.kernow.io / 10.10.0.91) is reachable
- Check device MQTT settings: `tasmota_command(ip, "MqttHost")`
- No firewall rules needed (same subnet)

## Decision Record

**Decision**: Separate SSID without VLAN isolation
**Date**: 2026-01-15
**Rationale**: Unmanaged switches cannot pass VLAN tags. Separate SSID provides organizational benefits and RF optimization without breaking connectivity.
**Alternatives Considered**:
- Full VLAN isolation (requires managed switches)
- Single SSID for all devices
- Separate physical network

## Related Resources

- Vikunja: https://vikunja.kernow.io → "IoT Network Migration"
- UniFi: Network → WiFi → Kernow-IoT
- Knowledge Base: Search "kernow-iot" or "iot network"
