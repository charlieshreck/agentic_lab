#!/usr/bin/env python3
"""Tasmota MCP server for smart device control and configuration."""
import os
import json
import logging
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastmcp import FastMCP
from pydantic import BaseModel
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
DEVICES_FILE = os.environ.get("DEVICES_FILE", "/data/devices.json")
INITIAL_DEVICES = os.environ.get("TASMOTA_DEVICES", "")  # Comma-separated IPs
COMMAND_TIMEOUT = float(os.environ.get("COMMAND_TIMEOUT", "10.0"))

mcp = FastMCP(
    name="tasmota-mcp",
    instructions="""
    MCP server for Tasmota smart device control.
    Provides tools to control power, configure WiFi/MQTT, and manage devices.
    Tasmota devices expose HTTP API at /cm?cmnd=<command>.
    Common commands: Power, Status, WifiConfig, MqttHost, Upgrade.
    """
)


class TasmotaDevice(BaseModel):
    """Tasmota device model."""
    ip: str
    name: Optional[str] = None
    hostname: Optional[str] = None
    mac: Optional[str] = None
    module: Optional[str] = None
    firmware: Optional[str] = None
    last_seen: Optional[str] = None


class DeviceStatus(BaseModel):
    """Device status response."""
    ip: str
    name: str
    power: str
    wifi_ssid: Optional[str] = None
    wifi_signal: Optional[int] = None
    uptime: Optional[str] = None
    firmware: Optional[str] = None
    mqtt_connected: Optional[bool] = None


class CommandResult(BaseModel):
    """Result of a Tasmota command."""
    ip: str
    success: bool
    command: str
    response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def load_devices() -> Dict[str, TasmotaDevice]:
    """Load devices from persistent storage."""
    devices = {}

    # Load from file if exists
    if Path(DEVICES_FILE).exists():
        try:
            with open(DEVICES_FILE, "r") as f:
                data = json.load(f)
                for ip, info in data.items():
                    devices[ip] = TasmotaDevice(**info)
            logger.info(f"Loaded {len(devices)} devices from {DEVICES_FILE}")
        except Exception as e:
            logger.error(f"Failed to load devices: {e}")

    # Add initial devices from env
    if INITIAL_DEVICES:
        for ip in INITIAL_DEVICES.split(","):
            ip = ip.strip()
            if ip and ip not in devices:
                devices[ip] = TasmotaDevice(ip=ip)
                logger.info(f"Added initial device: {ip}")

    return devices


def save_devices(devices: Dict[str, TasmotaDevice]) -> None:
    """Save devices to persistent storage."""
    try:
        Path(DEVICES_FILE).parent.mkdir(parents=True, exist_ok=True)
        with open(DEVICES_FILE, "w") as f:
            json.dump({ip: d.model_dump() for ip, d in devices.items()}, f, indent=2)
        logger.info(f"Saved {len(devices)} devices to {DEVICES_FILE}")
    except Exception as e:
        logger.error(f"Failed to save devices: {e}")


# Global device registry
DEVICES = load_devices()


async def tasmota_command(ip: str, command: str, timeout: float = COMMAND_TIMEOUT) -> CommandResult:
    """Execute a Tasmota command via HTTP API."""
    url = f"http://{ip}/cm?cmnd={command}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()

            # Tasmota returns JSON
            data = response.json()
            return CommandResult(
                ip=ip,
                success=True,
                command=command,
                response=data
            )
    except httpx.TimeoutException:
        return CommandResult(
            ip=ip,
            success=False,
            command=command,
            error=f"Timeout connecting to {ip}"
        )
    except httpx.HTTPStatusError as e:
        return CommandResult(
            ip=ip,
            success=False,
            command=command,
            error=f"HTTP error: {e.response.status_code}"
        )
    except Exception as e:
        return CommandResult(
            ip=ip,
            success=False,
            command=command,
            error=str(e)
        )


@mcp.resource("health://status")
def health_check() -> str:
    """Health check endpoint."""
    return "healthy"


# =============================================================================
# Device Management Tools
# =============================================================================

@mcp.tool()
async def tasmota_list_devices() -> List[TasmotaDevice]:
    """
    List all registered Tasmota devices.

    Returns:
        List of registered devices with their info
    """
    return list(DEVICES.values())


@mcp.tool()
async def tasmota_add_device(
    ip: str,
    name: Optional[str] = None
) -> str:
    """
    Add a Tasmota device by IP address.

    Args:
        ip: Device IP address (e.g., 192.168.1.100)
        name: Optional friendly name

    Returns:
        Status message
    """
    if ip in DEVICES:
        return f"Device {ip} already registered"

    # Verify device is reachable and is Tasmota
    result = await tasmota_command(ip, "Status%200")

    if not result.success:
        return f"Failed to reach device at {ip}: {result.error}"

    # Extract device info from Status 0
    device = TasmotaDevice(ip=ip, name=name)

    if result.response:
        status = result.response.get("Status", {})
        device.name = name or status.get("DeviceName", status.get("FriendlyName", [ip])[0] if isinstance(status.get("FriendlyName"), list) else ip)
        device.module = status.get("Module")

        # Get network info
        net = result.response.get("StatusNET", {})
        device.hostname = net.get("Hostname")
        device.mac = net.get("Mac")

        # Get firmware info
        fw = result.response.get("StatusFWR", {})
        device.firmware = fw.get("Version")

    DEVICES[ip] = device
    save_devices(DEVICES)

    return f"Added device: {device.name} ({ip})"


@mcp.tool()
async def tasmota_remove_device(ip: str) -> str:
    """
    Remove a Tasmota device from the registry.

    Args:
        ip: Device IP address to remove

    Returns:
        Status message
    """
    if ip not in DEVICES:
        return f"Device {ip} not found"

    device = DEVICES.pop(ip)
    save_devices(DEVICES)

    return f"Removed device: {device.name or ip}"


@mcp.tool()
async def tasmota_discover(
    network: str = "192.168.1",
    start: int = 1,
    end: int = 254,
    timeout: float = 2.0
) -> List[Dict[str, str]]:
    """
    Scan network for Tasmota devices.

    Args:
        network: Network prefix (e.g., 192.168.1)
        start: Start of IP range to scan
        end: End of IP range to scan
        timeout: Timeout per device in seconds

    Returns:
        List of discovered devices with IP and name
    """
    discovered = []

    async def check_device(ip: str) -> Optional[Dict[str, str]]:
        result = await tasmota_command(ip, "Status", timeout=timeout)
        if result.success and result.response:
            status = result.response.get("Status", {})
            name = status.get("DeviceName") or status.get("FriendlyName", [ip])
            if isinstance(name, list):
                name = name[0] if name else ip
            return {"ip": ip, "name": name}
        return None

    # Scan in batches to avoid overwhelming the network
    batch_size = 20
    for i in range(start, end + 1, batch_size):
        batch_end = min(i + batch_size, end + 1)
        tasks = [
            check_device(f"{network}.{j}")
            for j in range(i, batch_end)
        ]
        results = await asyncio.gather(*tasks)

        for result in results:
            if result:
                discovered.append(result)
                logger.info(f"Discovered Tasmota: {result['ip']} ({result['name']})")

    return discovered


# =============================================================================
# Power Control Tools
# =============================================================================

@mcp.tool()
async def tasmota_power(
    ip: str,
    action: str = "toggle",
    relay: int = 1
) -> str:
    """
    Control device power state.

    Args:
        ip: Device IP address
        action: Power action - on, off, toggle, or blink
        relay: Relay number (1-based, for multi-relay devices)

    Returns:
        Current power state after action
    """
    action_map = {
        "on": "1",
        "off": "0",
        "toggle": "2",
        "blink": "3",
    }

    if action.lower() not in action_map:
        return f"Invalid action: {action}. Use: on, off, toggle, blink"

    cmd = f"Power{relay}%20{action_map[action.lower()]}"
    result = await tasmota_command(ip, cmd)

    if not result.success:
        return f"Failed: {result.error}"

    power_key = f"POWER{relay}" if relay > 1 else "POWER"
    state = result.response.get(power_key, result.response.get("POWER", "unknown"))

    return f"Power{relay}: {state}"


@mcp.tool()
async def tasmota_power_all(
    action: str = "toggle"
) -> List[Dict[str, str]]:
    """
    Control power on all registered devices.

    Args:
        action: Power action - on, off, toggle

    Returns:
        List of results for each device
    """
    results = []

    for ip in DEVICES:
        result = await tasmota_power(ip, action)
        results.append({"ip": ip, "result": result})

    return results


# =============================================================================
# Status Tools
# =============================================================================

@mcp.tool()
async def tasmota_status(ip: str) -> DeviceStatus:
    """
    Get comprehensive device status.

    Args:
        ip: Device IP address

    Returns:
        Device status including power, WiFi, uptime
    """
    result = await tasmota_command(ip, "Status%200")

    if not result.success:
        return DeviceStatus(
            ip=ip,
            name=DEVICES.get(ip, TasmotaDevice(ip=ip)).name or ip,
            power="unavailable"
        )

    resp = result.response or {}
    status = resp.get("Status", {})
    status_sts = resp.get("StatusSTS", {})
    status_net = resp.get("StatusNET", {})
    status_fwr = resp.get("StatusFWR", {})

    # Get power state(s)
    power = status_sts.get("POWER", status_sts.get("POWER1", "unknown"))

    return DeviceStatus(
        ip=ip,
        name=status.get("DeviceName", DEVICES.get(ip, TasmotaDevice(ip=ip)).name or ip),
        power=power,
        wifi_ssid=status_net.get("SSId"),
        wifi_signal=status_net.get("Signal"),
        uptime=status_sts.get("Uptime"),
        firmware=status_fwr.get("Version"),
        mqtt_connected=status_sts.get("MqttCount", 0) > 0
    )


@mcp.tool()
async def tasmota_status_all() -> List[DeviceStatus]:
    """
    Get status of all registered devices.

    Returns:
        List of device statuses
    """
    tasks = [tasmota_status(ip) for ip in DEVICES]
    return await asyncio.gather(*tasks)


# =============================================================================
# Configuration Tools
# =============================================================================

@mcp.tool()
async def tasmota_wifi_config(
    ip: str,
    ssid: Optional[str] = None,
    password: Optional[str] = None,
    ssid2: Optional[str] = None,
    password2: Optional[str] = None
) -> str:
    """
    Configure WiFi settings on device.

    Args:
        ip: Device IP address
        ssid: Primary WiFi SSID
        password: Primary WiFi password
        ssid2: Backup WiFi SSID (optional)
        password2: Backup WiFi password (optional)

    Returns:
        Configuration result
    """
    results = []

    if ssid:
        cmd = f"SSID1%20{ssid}"
        result = await tasmota_command(ip, cmd)
        results.append(f"SSID1: {'OK' if result.success else result.error}")

    if password:
        cmd = f"Password1%20{password}"
        result = await tasmota_command(ip, cmd)
        results.append(f"Password1: {'OK' if result.success else result.error}")

    if ssid2:
        cmd = f"SSID2%20{ssid2}"
        result = await tasmota_command(ip, cmd)
        results.append(f"SSID2: {'OK' if result.success else result.error}")

    if password2:
        cmd = f"Password2%20{password2}"
        result = await tasmota_command(ip, cmd)
        results.append(f"Password2: {'OK' if result.success else result.error}")

    if not results:
        # Just show current config
        result = await tasmota_command(ip, "SSID")
        if result.success:
            return f"Current WiFi: {result.response}"
        return f"Failed to get WiFi config: {result.error}"

    return "; ".join(results)


@mcp.tool()
async def tasmota_mqtt_config(
    ip: str,
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    topic: Optional[str] = None,
    client: Optional[str] = None
) -> str:
    """
    Configure MQTT settings on device.

    Args:
        ip: Device IP address
        host: MQTT broker hostname/IP
        port: MQTT broker port (default 1883)
        user: MQTT username
        password: MQTT password
        topic: MQTT topic (device identifier)
        client: MQTT client ID

    Returns:
        Configuration result
    """
    results = []

    if host:
        cmd = f"MqttHost%20{host}"
        result = await tasmota_command(ip, cmd)
        results.append(f"MqttHost: {'OK' if result.success else result.error}")

    if port:
        cmd = f"MqttPort%20{port}"
        result = await tasmota_command(ip, cmd)
        results.append(f"MqttPort: {'OK' if result.success else result.error}")

    if user:
        cmd = f"MqttUser%20{user}"
        result = await tasmota_command(ip, cmd)
        results.append(f"MqttUser: {'OK' if result.success else result.error}")

    if password:
        cmd = f"MqttPassword%20{password}"
        result = await tasmota_command(ip, cmd)
        results.append(f"MqttPassword: {'OK' if result.success else result.error}")

    if topic:
        cmd = f"Topic%20{topic}"
        result = await tasmota_command(ip, cmd)
        results.append(f"Topic: {'OK' if result.success else result.error}")

    if client:
        cmd = f"MqttClient%20{client}"
        result = await tasmota_command(ip, cmd)
        results.append(f"MqttClient: {'OK' if result.success else result.error}")

    if not results:
        # Show current MQTT config
        result = await tasmota_command(ip, "Status%206")
        if result.success:
            mqtt = result.response.get("StatusMQT", {})
            return f"MQTT Config: Host={mqtt.get('MqttHost')}, Port={mqtt.get('MqttPort')}, Topic={mqtt.get('Topic')}"
        return f"Failed to get MQTT config: {result.error}"

    return "; ".join(results)


@mcp.tool()
async def tasmota_set_name(ip: str, name: str) -> str:
    """
    Set device friendly name.

    Args:
        ip: Device IP address
        name: New friendly name

    Returns:
        Result message
    """
    cmd = f"DeviceName%20{name}"
    result = await tasmota_command(ip, cmd)

    if result.success:
        # Update local registry
        if ip in DEVICES:
            DEVICES[ip].name = name
            save_devices(DEVICES)
        return f"Device name set to: {name}"

    return f"Failed: {result.error}"


# =============================================================================
# Advanced Tools
# =============================================================================

@mcp.tool()
async def tasmota_command_raw(
    ip: str,
    command: str
) -> CommandResult:
    """
    Execute any Tasmota command directly.

    Args:
        ip: Device IP address
        command: Raw Tasmota command (e.g., "Status 0", "Backlog Power ON; Delay 100; Power OFF")

    Returns:
        Command result with response data
    """
    # URL encode spaces
    cmd = command.replace(" ", "%20")
    return await tasmota_command(ip, cmd)


@mcp.tool()
async def tasmota_upgrade(
    ip: str,
    url: Optional[str] = None
) -> str:
    """
    Trigger firmware upgrade on device.

    Args:
        ip: Device IP address
        url: OTA firmware URL (optional, uses default Tasmota OTA if not specified)

    Returns:
        Upgrade status
    """
    if url:
        # Set OTA URL first
        cmd = f"OtaUrl%20{url}"
        result = await tasmota_command(ip, cmd)
        if not result.success:
            return f"Failed to set OTA URL: {result.error}"

    # Trigger upgrade
    result = await tasmota_command(ip, "Upgrade%201")

    if result.success:
        return f"Upgrade initiated on {ip}. Device will restart when complete."

    return f"Failed to start upgrade: {result.error}"


@mcp.tool()
async def tasmota_restart(ip: str) -> str:
    """
    Restart the device.

    Args:
        ip: Device IP address

    Returns:
        Result message
    """
    result = await tasmota_command(ip, "Restart%201")

    if result.success:
        return f"Restart command sent to {ip}"

    return f"Failed: {result.error}"


@mcp.tool()
async def tasmota_get_sensors(ip: str) -> Dict[str, Any]:
    """
    Get sensor readings from device (temperature, humidity, energy, etc.).

    Args:
        ip: Device IP address

    Returns:
        Sensor data dictionary
    """
    result = await tasmota_command(ip, "Status%2010")

    if result.success:
        return result.response.get("StatusSNS", {})

    return {"error": result.error}


@mcp.tool()
async def tasmota_get_energy(ip: str) -> Dict[str, Any]:
    """
    Get energy monitoring data (for devices with power monitoring).

    Args:
        ip: Device IP address

    Returns:
        Energy data (voltage, current, power, energy)
    """
    result = await tasmota_command(ip, "Status%208")

    if result.success:
        return result.response.get("StatusSNS", {}).get("ENERGY", {})

    return {"error": result.error}


# =============================================================================
# REST API Endpoints
# =============================================================================

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount


async def api_index(request):
    """REST endpoint listing available APIs."""
    return JSONResponse({
        "status": "ok",
        "endpoints": [
            "/api/devices - List all devices",
            "/api/status - Get status of all devices",
            "/api/power/<ip>/<action> - Control device power",
        ]
    })


async def api_devices(request):
    """REST endpoint for listing devices."""
    try:
        data = await tasmota_list_devices()
        return JSONResponse({"status": "ok", "data": [d.model_dump() for d in data]})
    except Exception as e:
        logger.error(f"REST api_devices error: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


async def api_status(request):
    """REST endpoint for device status."""
    try:
        data = await tasmota_status_all()
        return JSONResponse({"status": "ok", "data": [d.model_dump() for d in data]})
    except Exception as e:
        logger.error(f"REST api_status error: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


def main():
    import uvicorn
    from starlette.middleware.cors import CORSMiddleware

    port = int(os.environ.get("PORT", "8000"))

    logger.info(f"Starting tasmota MCP server on port {port}")
    logger.info(f"Registered devices: {len(DEVICES)}")

    # REST routes
    rest_routes = [
        Route("/api", api_index),
        Route("/api/devices", api_devices),
        Route("/api/status", api_status),
    ]

    # Combine REST routes with MCP app
    mcp_app = mcp.http_app()
    app = Starlette(routes=rest_routes + [Mount("/mcp", app=mcp_app)])

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
