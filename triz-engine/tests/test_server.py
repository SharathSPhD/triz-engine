"""Tests for the TRIZ MCP server tools."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from servers.triz_server import (
    get_principle,
    get_separation_principles,
    list_parameters,
    log_session_entry,
    lookup_matrix,
    score_solution,
    search_principles,
)


class TestGetPrinciple:
    @pytest.mark.asyncio
    async def test_valid_id_returns_principle(self):
        result = await get_principle(1)
        data = json.loads(result)
        assert data["id"] == 1
        assert data["name"] == "Segmentation"
        assert "sub_actions" in data

    @pytest.mark.asyncio
    async def test_invalid_id_returns_error(self):
        result = await get_principle(0)
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_out_of_range_returns_error(self):
        result = await get_principle(41)
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_all_40_retrievable(self):
        for i in range(1, 41):
            result = await get_principle(i)
            data = json.loads(result)
            assert data["id"] == i


class TestSearchPrinciples:
    @pytest.mark.asyncio
    async def test_keyword_search(self):
        result = await search_principles("segmentation")
        data = json.loads(result)
        assert isinstance(data["results"], list)
        assert any(p["id"] == 1 for p in data["results"])

    @pytest.mark.asyncio
    async def test_domain_filter(self):
        result = await search_principles("", domain="software")
        data = json.loads(result)
        assert len(data["results"]) > 0

    @pytest.mark.asyncio
    async def test_max_5_results(self):
        result = await search_principles("object")
        data = json.loads(result)
        assert len(data["results"]) <= 5

    @pytest.mark.asyncio
    async def test_no_match_returns_empty(self):
        result = await search_principles("xyznonexistent")
        data = json.loads(result)
        assert len(data["results"]) == 0


class TestLookupMatrix:
    @pytest.mark.asyncio
    async def test_valid_pair_returns_principles(self):
        result = await lookup_matrix(1, 9)
        data = json.loads(result)
        assert "principles" in data
        assert isinstance(data["principles"], list)
        assert len(data["principles"]) > 0

    @pytest.mark.asyncio
    async def test_result_contains_principle_ids(self):
        result = await lookup_matrix(1, 9)
        data = json.loads(result)
        for pid in data["principles"]:
            assert 1 <= pid <= 40

    @pytest.mark.asyncio
    async def test_invalid_param_returns_error(self):
        result = await lookup_matrix(0, 9)
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_same_param_returns_error(self):
        result = await lookup_matrix(5, 5)
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_known_cell_1_2(self):
        result = await lookup_matrix(1, 2)
        data = json.loads(result)
        assert 15 in data["principles"]


class TestListParameters:
    @pytest.mark.asyncio
    async def test_returns_39_parameters(self):
        result = await list_parameters()
        data = json.loads(result)
        assert len(data["parameters"]) == 39

    @pytest.mark.asyncio
    async def test_parameter_has_id_name_description(self):
        result = await list_parameters()
        data = json.loads(result)
        for p in data["parameters"]:
            assert "id" in p and "name" in p and "description" in p


class TestGetSeparationPrinciples:
    @pytest.mark.asyncio
    async def test_returns_separation_approaches(self):
        result = await get_separation_principles(
            "The wing must be both thick for strength and thin for aerodynamics"
        )
        data = json.loads(result)
        assert "approaches" in data
        assert len(data["approaches"]) > 0

    @pytest.mark.asyncio
    async def test_approaches_have_required_fields(self):
        result = await get_separation_principles("must be both fast and safe")
        data = json.loads(result)
        for a in data["approaches"]:
            assert "type" in a
            assert a["type"] in ("time", "space", "condition", "system_level")
            assert "description" in a


class TestScoreSolution:
    @pytest.mark.asyncio
    async def test_returns_ifr_score(self):
        result = await score_solution(
            problem="System must be fast and reliable",
            solution="Use caching at edge nodes to reduce latency without sacrificing consistency",
        )
        data = json.loads(result)
        assert "ifr_score" in data
        assert 0 <= data["ifr_score"] <= 4

    @pytest.mark.asyncio
    async def test_has_rationale(self):
        result = await score_solution(
            problem="test problem",
            solution="test solution",
        )
        data = json.loads(result)
        assert "rationale" in data
        assert isinstance(data["rationale"], str)


class TestLogSessionEntry:
    @pytest.mark.asyncio
    async def test_creates_log_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / ".triz" / "session.jsonl"
            os.environ["TRIZ_SESSION_DIR"] = tmpdir
            try:
                entry = {
                    "timestamp": "2026-04-15T10:00:00Z",
                    "problem_hash": "abc123",
                    "contradiction_type": "technical",
                    "principles_applied": [1, 15],
                }
                result = await log_session_entry(entry)
                data = json.loads(result)
                assert data["logged"] is True
                assert log_path.exists()
                with open(log_path) as f:
                    logged = json.loads(f.readline())
                assert logged["problem_hash"] == "abc123"
            finally:
                os.environ.pop("TRIZ_SESSION_DIR", None)

    @pytest.mark.asyncio
    async def test_appends_multiple_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["TRIZ_SESSION_DIR"] = tmpdir
            try:
                for i in range(3):
                    await log_session_entry({"index": i})
                log_path = Path(tmpdir) / ".triz" / "session.jsonl"
                lines = log_path.read_text().strip().split("\n")
                assert len(lines) == 3
            finally:
                os.environ.pop("TRIZ_SESSION_DIR", None)
