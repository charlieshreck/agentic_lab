# Matter Hub Commissioning Failure

## Overview

The Home Assistant Matter Hub (`home-assistant-matter-hub`) bridges Home Assistant entities to Matter controllers like Google Home, Apple Home, and Alexa. When the fabric connection is lost or corrupted, devices become unavailable in the Matter controller.

## Symptoms

- Google Home shows "No devices found" when trying to add Matter device
- Google Home app completes Matter animation but fails to find device
- Matter Hub UI shows `Fabrics: 0` (no connected controllers)
- Logs show `commissionable = true` but no successful pairing
- Error in logs: `Offset is outside the bounds of the DataView` during pairing attempts
- Devices previously visible in Google Home are now offline/missing

## Alert Trigger

- `MatterHubFabricDisconnected` alert fires when Matter Hub has zero fabrics for >10 minutes

## Root Cause

The Matter Hub stores fabric credentials and pairing state in `/data/<bridge-id>/`. When this data becomes corrupted or stale (e.g., after a controller removes the fabric without proper cleanup), commissioning attempts fail with parsing errors.

Common causes:
1. Google Home fabric was removed from the Google Home app
2. Pod restart while commissioning was in progress
3. Storage corruption
4. Version upgrade with incompatible state format

## Resolution Steps

### 1. Verify the Issue

Check current fabric status:
```bash
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
  kubectl logs -n apps deployment/matter-hub | grep -iE "fabric|commission"
```

Look for:
- `commissionable = true` (hub is advertising but not connected)
- `Fabrics: 0` or absence of fabric announcements
- `DataView` or parsing errors

### 2. Check for Active Pairing Attempts

Monitor logs during a pairing attempt:
```bash
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
  kubectl logs -n apps deployment/matter-hub -f | grep -iE "pairing|error|channel"
```

If you see `Offset is outside the bounds of the DataView`, proceed to step 3.

### 3. Clear Corrupted Data

Identify and remove the bridge data:
```bash
# List data directory
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
  kubectl exec -n apps deployment/matter-hub -- ls -la /data/

# Remove the bridge data (usually a UUID-like folder)
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
  kubectl exec -n apps deployment/matter-hub -- rm -rf /data/<bridge-id>
```

### 4. Restart the Pod

```bash
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
  kubectl delete pod -n apps -l app=matter-hub
```

Wait for new pod to start:
```bash
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
  kubectl get pods -n apps -l app=matter-hub -w
```

### 5. Get New Pairing Codes

```bash
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
  kubectl logs -n apps deployment/matter-hub | grep -iE "QR|Manual|Passcode"
```

Expected output:
```
is uncommissioned passcode: XXXXXXXX discriminator: XXXX manual pairing code: XXXXXXXXXXX
QR code URL: https://project-chip.github.io/connectedhomeip/qrcode.html?data=MT:...
```

### 6. Pair with Google Home

1. Open Google Home app
2. Tap "+" > "Set up device" > "New device"
3. Select your home
4. Choose "Matter-enabled device"
5. Scan QR code or enter manual pairing code
6. Accept "uncertified device" warning (this is normal for third-party bridges)
7. Wait for "Device connected" confirmation

### 7. Verify Success

Check logs for successful commissioning:
```bash
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
  kubectl logs -n apps deployment/matter-hub | grep -iE "commission.*complete|fabric.*index"
```

Expected:
```
Commissioning completed on fabric #XXXXX as node #XXXXX
```

## Prevention

1. **Don't remove fabric from Google Home app** - If you need to disconnect, use the Matter Hub UI to remove the fabric properly
2. **Backup data before upgrades** - The `/data/` directory contains fabric credentials
3. **Monitor the alert** - `MatterHubFabricDisconnected` fires early to catch issues

## Related Files

- Deployment: `/home/prod_homelab/kubernetes/applications/apps/matter-hub/deployment.yaml`
- Alert rule: `/home/prod_homelab/kubernetes/platform/monitoring/alerts/matter-hub-alerts.yaml`
- Documentation: `/home/prod_homelab/docs/MATTER-BRIDGE-SETUP.md`

## Technical Details

- **Image**: `ghcr.io/t0bst4r/home-assistant-matter-hub:latest`
- **Ports**: 8482 (HTTP UI), 5540 (Matter), 5353 (mDNS)
- **Network**: hostNetwork required for mDNS discovery
- **Storage**: PVC `matter-hub-data` (1Gi, mayastor-3-replica)
- **IP**: Runs on worker nodes (currently 10.10.0.43)

## References

- [Home Assistant Matter Hub GitHub](https://github.com/t0bst4r/home-assistant-matter-hub)
- [Matter Protocol Documentation](https://csa-iot.org/developer-resource/specifications/)
- [GitHub Issues - Commissioning Problems](https://github.com/t0bst4r/home-assistant-matter-hub/issues?q=commissioning)
