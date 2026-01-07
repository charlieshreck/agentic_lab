#!/usr/bin/env python3
"""Home Assistant MCP server for smart home control."""
import os
import logging
import httpx
from typing import List, Optional
from fastmcp import FastMCP
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
HA_URL = os.environ.get("HA_URL", "http://homeassistant.local:8123")
HA_TOKEN = os.environ.get("HA_TOKEN", "")

mcp = FastMCP(
    name="home-assistant-mcp",
    instructions="""
    MCP server for Home Assistant smart home control.
    Provides tools to control lights, climate, and view sensor states.
    Always confirm actions before executing them.
    """
)


class LightState(BaseModel):
    entity_id: str
    friendly_name: str
    state: str
    brightness: Optional[int] = None
    color_temp: Optional[int] = None


class ClimateState(BaseModel):
    entity_id: str
    friendly_name: str
    state: str
    temperature: Optional[float] = None
    target_temp: Optional[float] = None
    hvac_mode: Optional[str] = None


class SensorState(BaseModel):
    entity_id: str
    friendly_name: str
    state: str
    unit: Optional[str] = None
    device_class: Optional[str] = None


async def ha_request(
    method: str,
    endpoint: str,
    data: dict = None,
    timeout: float = 30.0
) -> dict:
    """Make authenticated request to Home Assistant API."""
    if not HA_TOKEN:
        raise ValueError("HA_TOKEN environment variable not set")

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.request(
            method,
            f"{HA_URL}/api/{endpoint}",
            headers={
                "Authorization": f"Bearer {HA_TOKEN}",
                "Content-Type": "application/json"
            },
            json=data
        )
        response.raise_for_status()
        return response.json() if response.content else {}


@mcp.resource("health://status")
def health_check() -> str:
    """Health check endpoint."""
    return "healthy"


@mcp.tool()
async def list_lights() -> List[LightState]:
    """
    List all light entities and their current state.

    Returns:
        List of light states with brightness and color info
    """
    try:
        states = await ha_request("GET", "states")
        lights = []
        for state in states:
            if state["entity_id"].startswith("light."):
                attrs = state.get("attributes", {})
                lights.append(LightState(
                    entity_id=state["entity_id"],
                    friendly_name=attrs.get("friendly_name", state["entity_id"]),
                    state=state["state"],
                    brightness=attrs.get("brightness"),
                    color_temp=attrs.get("color_temp")
                ))
        return lights
    except Exception as e:
        logger.error(f"Failed to list lights: {e}")
        return []


@mcp.tool()
async def turn_on_light(
    entity_id: str,
    brightness: Optional[int] = None,
    color_temp: Optional[int] = None
) -> str:
    """
    Turn on a light with optional brightness and color temperature.

    Args:
        entity_id: The light entity ID (e.g., light.living_room)
        brightness: Brightness level 0-255
        color_temp: Color temperature in mireds (lower = warmer)

    Returns:
        Status message
    """
    try:
        data = {"entity_id": entity_id}
        if brightness is not None:
            data["brightness"] = min(255, max(0, brightness))
        if color_temp is not None:
            data["color_temp"] = color_temp

        await ha_request("POST", "services/light/turn_on", data)
        return f"Turned on {entity_id}"
    except Exception as e:
        logger.error(f"Failed to turn on light: {e}")
        return f"Error: {str(e)}"


@mcp.tool()
async def turn_off_light(entity_id: str) -> str:
    """
    Turn off a light.

    Args:
        entity_id: The light entity ID (e.g., light.living_room)

    Returns:
        Status message
    """
    try:
        await ha_request("POST", "services/light/turn_off", {"entity_id": entity_id})
        return f"Turned off {entity_id}"
    except Exception as e:
        logger.error(f"Failed to turn off light: {e}")
        return f"Error: {str(e)}"


@mcp.tool()
async def list_climate() -> List[ClimateState]:
    """
    List all climate/thermostat entities.

    Returns:
        List of climate states with temperature info
    """
    try:
        states = await ha_request("GET", "states")
        climate = []
        for state in states:
            if state["entity_id"].startswith("climate."):
                attrs = state.get("attributes", {})
                climate.append(ClimateState(
                    entity_id=state["entity_id"],
                    friendly_name=attrs.get("friendly_name", state["entity_id"]),
                    state=state["state"],
                    temperature=attrs.get("current_temperature"),
                    target_temp=attrs.get("temperature"),
                    hvac_mode=attrs.get("hvac_mode")
                ))
        return climate
    except Exception as e:
        logger.error(f"Failed to list climate: {e}")
        return []


@mcp.tool()
async def set_climate(
    entity_id: str,
    temperature: float,
    hvac_mode: Optional[str] = None
) -> str:
    """
    Set climate/thermostat temperature.

    Args:
        entity_id: Climate entity ID
        temperature: Target temperature
        hvac_mode: Optional mode (heat, cool, auto, off)

    Returns:
        Status message
    """
    try:
        data = {"entity_id": entity_id, "temperature": temperature}
        if hvac_mode:
            data["hvac_mode"] = hvac_mode

        await ha_request("POST", "services/climate/set_temperature", data)
        return f"Set {entity_id} to {temperature}°"
    except Exception as e:
        logger.error(f"Failed to set climate: {e}")
        return f"Error: {str(e)}"


@mcp.tool()
async def get_sensor_state(entity_id: str) -> SensorState:
    """
    Get the current state of any sensor or entity.

    Args:
        entity_id: The entity ID to query

    Returns:
        Sensor state with attributes
    """
    try:
        state = await ha_request("GET", f"states/{entity_id}")
        attrs = state.get("attributes", {})
        return SensorState(
            entity_id=state["entity_id"],
            friendly_name=attrs.get("friendly_name", state["entity_id"]),
            state=state["state"],
            unit=attrs.get("unit_of_measurement"),
            device_class=attrs.get("device_class")
        )
    except Exception as e:
        logger.error(f"Failed to get sensor state: {e}")
        return SensorState(
            entity_id=entity_id,
            friendly_name=entity_id,
            state="unavailable"
        )


@mcp.tool()
async def run_automation(automation_id: str) -> str:
    """
    Trigger a Home Assistant automation.

    Args:
        automation_id: The automation entity ID

    Returns:
        Status message
    """
    try:
        await ha_request("POST", "services/automation/trigger", {"entity_id": automation_id})
        return f"Triggered automation {automation_id}"
    except Exception as e:
        logger.error(f"Failed to run automation: {e}")
        return f"Error: {str(e)}"


@mcp.tool()
async def run_script(script_id: str) -> str:
    """
    Run a Home Assistant script.

    Args:
        script_id: The script entity ID

    Returns:
        Status message
    """
    try:
        await ha_request("POST", "services/script/turn_on", {"entity_id": script_id})
        return f"Executed script {script_id}"
    except Exception as e:
        logger.error(f"Failed to run script: {e}")
        return f"Error: {str(e)}"


@mcp.tool()
async def list_areas() -> List[dict]:
    """
    List all areas (rooms) configured in Home Assistant.

    Returns:
        List of areas with their IDs and names
    """
    try:
        areas = await ha_request("GET", "config/area_registry")
        return [{"area_id": a["area_id"], "name": a["name"]} for a in areas]
    except Exception as e:
        logger.error(f"Failed to list areas: {e}")
        return []


def main():
    port = int(os.environ.get("PORT", "8000"))
    transport = os.environ.get("MCP_TRANSPORT", "sse")

    logger.info(f"Starting home-assistant MCP server on port {port} with {transport} transport")

    if transport == "http":
        from starlette.middleware.cors import CORSMiddleware
        app = mcp.streamable_http_app()
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        mcp.run(transport="sse", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
