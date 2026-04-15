"""Live MCP server integration tests.

Spawns triz_server.py as a real MCP subprocess via FastMCP Client
and sends actual JSON-RPC tool calls over stdio transport.
"""

import json

import pytest
from fastmcp import Client


SERVER_PATH = "servers/triz_server.py"


@pytest.fixture
async def mcp_client():
    """Create a FastMCP client connected to the live triz-knowledge server."""
    client = Client(SERVER_PATH)
    async with client:
        yield client


class TestMCPServerLive:
    """Verify the MCP server responds to real tool calls over stdio."""

    @pytest.mark.asyncio
    async def test_server_lists_tools(self, mcp_client):
        tools = await mcp_client.list_tools()
        tool_names = {t.name for t in tools}
        expected = {
            "get_principle",
            "search_principles",
            "lookup_matrix",
            "list_parameters",
            "get_separation_principles",
            "score_solution",
            "log_session_entry",
        }
        assert expected == tool_names, f"Missing tools: {expected - tool_names}"

    @pytest.mark.asyncio
    async def test_get_principle_live(self, mcp_client):
        result = await mcp_client.call_tool("get_principle", {"id": 1})
        data = json.loads(result.content[0].text)
        assert data["id"] == 1
        assert data["name"] == "Segmentation"
        assert "sub_actions" in data
        assert len(data["sub_actions"]) >= 2

    @pytest.mark.asyncio
    async def test_get_principle_invalid_id(self, mcp_client):
        result = await mcp_client.call_tool("get_principle", {"id": 99})
        data = json.loads(result.content[0].text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_search_principles_live(self, mcp_client):
        result = await mcp_client.call_tool(
            "search_principles", {"query": "segmentation"}
        )
        data = json.loads(result.content[0].text)
        assert len(data["results"]) >= 1
        assert any(p["id"] == 1 for p in data["results"])

    @pytest.mark.asyncio
    async def test_search_principles_with_domain(self, mcp_client):
        result = await mcp_client.call_tool(
            "search_principles", {"query": "", "domain": "software"}
        )
        data = json.loads(result.content[0].text)
        assert data["total"] > 0

    @pytest.mark.asyncio
    async def test_lookup_matrix_live(self, mcp_client):
        result = await mcp_client.call_tool(
            "lookup_matrix", {"param_a": 1, "param_b": 9}
        )
        data = json.loads(result.content[0].text)
        assert "principles" in data
        assert isinstance(data["principles"], list)
        assert data["improving"]["id"] == 1
        assert data["worsening"]["id"] == 9

    @pytest.mark.asyncio
    async def test_lookup_matrix_invalid(self, mcp_client):
        result = await mcp_client.call_tool(
            "lookup_matrix", {"param_a": 5, "param_b": 5}
        )
        data = json.loads(result.content[0].text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_list_parameters_live(self, mcp_client):
        result = await mcp_client.call_tool("list_parameters", {})
        data = json.loads(result.content[0].text)
        assert len(data["parameters"]) == 39
        names = {p["name"] for p in data["parameters"]}
        assert "Speed" in names
        assert "Reliability" in names

    @pytest.mark.asyncio
    async def test_get_separation_principles_live(self, mcp_client):
        result = await mcp_client.call_tool(
            "get_separation_principles",
            {"contradiction": "The system must be both fast during peak hours and energy-efficient during off-peak"},
        )
        data = json.loads(result.content[0].text)
        assert len(data["approaches"]) == 4
        types = {a["type"] for a in data["approaches"]}
        assert types == {"time", "space", "condition", "system_level"}

    @pytest.mark.asyncio
    async def test_score_solution_live(self, mcp_client):
        result = await mcp_client.call_tool(
            "score_solution",
            {
                "problem": "Cache must be consistent and available",
                "solution": "Use CRDTs to achieve automatic conflict resolution that inherently eliminates consistency-availability contradiction without additional components",
            },
        )
        data = json.loads(result.content[0].text)
        assert "ifr_score" in data
        assert 0 <= data["ifr_score"] <= 4
        assert "rationale" in data
        assert "criteria_met" in data

    @pytest.mark.asyncio
    async def test_log_session_entry_live(self, mcp_client):
        from pathlib import Path

        result = await mcp_client.call_tool(
            "log_session_entry",
            {"entry": {"test": True, "problem": "TB-01", "principles": [1, 15]}},
        )
        data = json.loads(result.content[0].text)
        assert data["logged"] is True
        assert "path" in data

        log_path = Path(data["path"])
        assert log_path.exists(), f"Session log not found at {log_path}"
        lines = log_path.read_text().strip().split("\n")
        last_entry = json.loads(lines[-1])
        assert last_entry["test"] is True
        assert last_entry["problem"] == "TB-01"
