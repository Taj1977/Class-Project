"""
mcp/server.py

UC4: Integration with Large Language Models (LLM).

Exposes the platform's capabilities as MCP tools so an LLM client
(e.g. Claude Desktop, or any MCP-compatible assistant) can call them
directly and ground its answers in real data from the data warehouse,
instead of generic finance knowledge.

Tools exposed:
- list_assets
- get_asset
- list_sources
- fetch_time_series
- summarize_trend
- compare_assets

This talks directly to MongoDB (same db layer as the API) rather than
calling the REST API over HTTP, to keep the MCP server self-contained.

Run: python -m app.mcp.server
Then point an MCP-compatible client at this script (stdio transport).
"""
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import json

from app.db.connection import get_db
from app.db.temporal_repo import list_current_assets
from app.analytics.engine import compute_trend, forecast_next_price

server = Server("acme-dwh-mcp")


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="list_assets",
            description="List all financial assets currently available in the data warehouse, optionally filtered by instrument class (e.g. 'crypto').",
            inputSchema={
                "type": "object",
                "properties": {"instrumentClass": {"type": "string"}},
            },
        ),
        Tool(
            name="get_asset",
            description="Get full details for a single asset by its assetId.",
            inputSchema={
                "type": "object",
                "properties": {"assetId": {"type": "string"}},
                "required": ["assetId"],
            },
        ),
        Tool(
            name="list_sources",
            description="List all data sources (providers) registered in the data warehouse.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="fetch_time_series",
            description="Fetch time series price data for an asset from a given data source.",
            inputSchema={
                "type": "object",
                "properties": {
                    "assetId": {"type": "string"},
                    "dataSourceId": {"type": "string"},
                },
                "required": ["assetId", "dataSourceId"],
            },
        ),
        Tool(
            name="summarize_trend",
            description="Summarize the price trend (min/max/avg/% change) for an asset over the data available.",
            inputSchema={
                "type": "object",
                "properties": {
                    "assetId": {"type": "string"},
                    "dataSourceId": {"type": "string"},
                },
                "required": ["assetId", "dataSourceId"],
            },
        ),
        Tool(
            name="compare_assets",
            description="Compare the trend of two assets (same data source) side by side.",
            inputSchema={
                "type": "object",
                "properties": {
                    "assetIdA": {"type": "string"},
                    "assetIdB": {"type": "string"},
                    "dataSourceId": {"type": "string"},
                },
                "required": ["assetIdA", "assetIdB", "dataSourceId"],
            },
        ),
    ]


def _text(payload) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, default=str, indent=2))]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    db = get_db()

    if name == "list_assets":
        assets = list_current_assets(instrument_class=arguments.get("instrumentClass"))
        return _text([{"assetId": a["assetId"], "symbol": a["symbol"]} for a in assets])

    if name == "get_asset":
        doc = db.assets.find_one({"assetId": arguments["assetId"], "validTo": None})
        if not doc:
            return _text({"error": "Asset not found"})
        doc.pop("_id", None)
        return _text(doc)

    if name == "list_sources":
        sources = list(db.datasources.find({}, {"_id": 0}))
        return _text(sources)

    if name == "fetch_time_series":
        points = list(
            db.timeseries.find(
                {"assetId": arguments["assetId"], "dataSourceId": arguments["dataSourceId"], "isDeleted": False},
                {"_id": 0},
            ).sort("timestamp", 1)
        )
        return _text(points)

    if name == "summarize_trend":
        result = compute_trend(arguments["assetId"], arguments["dataSourceId"])
        return _text(result or {"error": "Not enough data"})

    if name == "compare_assets":
        a = compute_trend(arguments["assetIdA"], arguments["dataSourceId"])
        b = compute_trend(arguments["assetIdB"], arguments["dataSourceId"])
        return _text({"assetA": a, "assetB": b})

    return _text({"error": f"Unknown tool: {name}"})


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
