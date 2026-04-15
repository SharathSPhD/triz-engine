"""Tests for TRIZ separation principles and physical contradiction support."""

import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "data"
SEP_PATH = DATA_DIR / "separation-principles.json"

VALID_TYPES = {"time", "space", "condition", "system_level"}


@pytest.fixture
def sep_data():
    with open(SEP_PATH) as f:
        return json.load(f)


@pytest.fixture
def principles_list(sep_data):
    return sep_data["separation_principles"]


class TestSeparationSchema:
    def test_has_schema_version(self, sep_data):
        assert sep_data["schema_version"] == "1.0"

    def test_has_separation_principles(self, sep_data):
        assert "separation_principles" in sep_data

    def test_exactly_4_separation_types(self, principles_list):
        assert len(principles_list) == 4

    def test_all_types_present(self, principles_list):
        types = {p["type"] for p in principles_list}
        assert types == VALID_TYPES

    def test_no_duplicate_types(self, principles_list):
        types = [p["type"] for p in principles_list]
        assert len(types) == len(set(types))


class TestSeparationContent:
    def test_each_has_required_fields(self, principles_list):
        required = {"type", "name", "description", "when_to_use", "related_principles",
                     "principle_rationale", "software_examples"}
        for p in principles_list:
            missing = required - set(p.keys())
            assert not missing, f"{p['type']} missing fields: {missing}"

    def test_related_principles_are_valid_ids(self, principles_list):
        for p in principles_list:
            for pid in p["related_principles"]:
                assert 1 <= pid <= 40, f"{p['type']} has invalid principle ID {pid}"

    def test_related_principles_nonempty(self, principles_list):
        for p in principles_list:
            assert len(p["related_principles"]) >= 3

    def test_when_to_use_nonempty(self, principles_list):
        for p in principles_list:
            assert len(p["when_to_use"]) >= 2

    def test_software_examples_nonempty(self, principles_list):
        for p in principles_list:
            assert len(p["software_examples"]) >= 2

    def test_principle_rationale_matches_related(self, principles_list):
        for p in principles_list:
            related_set = set(p["related_principles"])
            rationale_set = {int(k) for k in p["principle_rationale"].keys()}
            assert rationale_set == related_set, (
                f"{p['type']}: rationale keys {rationale_set} don't match "
                f"related_principles {related_set}"
            )


class TestSeparationSpecific:
    def test_time_has_dynamics_principle(self, principles_list):
        time_sep = next(p for p in principles_list if p["type"] == "time")
        assert 15 in time_sep["related_principles"]

    def test_space_has_segmentation_principle(self, principles_list):
        space_sep = next(p for p in principles_list if p["type"] == "space")
        assert 1 in space_sep["related_principles"]

    def test_condition_has_feedback_principle(self, principles_list):
        cond_sep = next(p for p in principles_list if p["type"] == "condition")
        assert 23 in cond_sep["related_principles"]

    def test_system_level_has_composite_principle(self, principles_list):
        sys_sep = next(p for p in principles_list if p["type"] == "system_level")
        assert 40 in sys_sep["related_principles"]
