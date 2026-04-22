"""
RouteWise MCP Server

Exposes the 4 tools via the MCP stdio transport so any MCP-compatible
client (Claude Desktop, Claude Code, etc.) can call them directly.

Run from the backend/ directory:
    python mcp_server.py

The server imports the same tool implementations used by FastAPI —
no code is duplicated.
"""

import sys
from pathlib import Path

# Ensure the backend/ directory is on the path when running directly
sys.path.insert(0, str(Path(__file__).parent))

import asyncio
from mcp.server.fastmcp import FastMCP

from app.tools.route_summary import get_route_summary as _get_route_summary
from app.tools.traffic_snapshot import get_traffic_snapshot as _get_traffic_snapshot
from app.tools.demand_estimate import get_demand_estimate as _get_demand_estimate
from app.tools.route_recommendation import generate_route_recommendation as _generate_recommendation

mcp = FastMCP("RouteWise")


@mcp.tool()
async def get_route_summary(dataset_id: str, route_id: str) -> dict:
    """
    Returns a detailed summary of a single bus route including stops,
    distance, duration, bus capacity, and estimated ridership load factor.
    Call this for each route you want to analyze.
    """
    result = await _get_route_summary(dataset_id, route_id)
    return result.model_dump()


@mcp.tool()
async def get_traffic_snapshot(dataset_id: str) -> dict:
    """
    Returns simulated morning peak traffic conditions for all zones in the
    dataset, including congestion level and estimated delay minutes.
    """
    result = await _get_traffic_snapshot(dataset_id)
    return result.model_dump()


@mcp.tool()
async def get_demand_estimate(dataset_id: str) -> dict:
    """
    Returns ridership demand estimates per zone based on proxy enrollment
    data, current bus capacity allocation, and utilization rates.
    """
    result = await _get_demand_estimate(dataset_id)
    return result.model_dump()


@mcp.tool()
async def generate_route_recommendation(dataset_id: str) -> dict:
    """
    Runs the full AI analysis loop and returns a structured route
    optimization recommendation with inefficiency findings, specific
    route edits, expected improvements, and a plain-English explanation.

    Available dataset_ids: bellevue_elementary, bellevue_middle
    """
    result = await _generate_recommendation(dataset_id)
    return result.model_dump()


if __name__ == "__main__":
    mcp.run()
