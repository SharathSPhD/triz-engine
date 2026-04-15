"""Tests for the TRIZ 40 Inventive Principles knowledge base."""

import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "data"
KB_PATH = DATA_DIR / "triz-knowledge-base.json"

REQUIRED_PRINCIPLE_FIELDS = {
    "id",
    "name",
    "description",
    "sub_actions",
    "categories",
    "contradiction_types",
    "domains",
    "software_patterns",
    "examples",
}

VALID_DOMAINS = {"software", "hardware", "process", "business", "electrical", "mechanical"}
VALID_CONTRADICTION_TYPES = {"technical", "physical"}
VALID_CATEGORIES = {
    "structural",
    "spatial",
    "temporal",
    "behavioral",
    "informational",
    "material",
    "energetic",
    "functional",
}


@pytest.fixture
def kb():
    with open(KB_PATH) as f:
        return json.load(f)


@pytest.fixture
def principles(kb):
    return kb["principles"]


class TestSchemaStructure:
    def test_has_schema_version(self, kb):
        assert "schema_version" in kb
        assert kb["schema_version"] == "1.0"

    def test_has_principles_array(self, kb):
        assert "principles" in kb
        assert isinstance(kb["principles"], list)

    def test_exactly_40_principles(self, principles):
        assert len(principles) == 40

    def test_principle_ids_are_1_through_40(self, principles):
        ids = sorted(p["id"] for p in principles)
        assert ids == list(range(1, 41))

    def test_no_duplicate_ids(self, principles):
        ids = [p["id"] for p in principles]
        assert len(ids) == len(set(ids))

    def test_no_duplicate_names(self, principles):
        names = [p["name"] for p in principles]
        assert len(names) == len(set(names))


class TestPrincipleFields:
    def test_all_required_fields_present(self, principles):
        for p in principles:
            missing = REQUIRED_PRINCIPLE_FIELDS - set(p.keys())
            assert not missing, f"Principle {p.get('id', '?')} missing fields: {missing}"

    def test_id_is_int(self, principles):
        for p in principles:
            assert isinstance(p["id"], int), f"Principle {p['id']} id not int"

    def test_name_is_nonempty_string(self, principles):
        for p in principles:
            assert isinstance(p["name"], str) and len(p["name"]) > 0

    def test_description_is_nonempty_string(self, principles):
        for p in principles:
            assert isinstance(p["description"], str) and len(p["description"]) > 10

    def test_at_least_2_sub_actions(self, principles):
        for p in principles:
            assert len(p["sub_actions"]) >= 2, (
                f"Principle {p['id']} '{p['name']}' has {len(p['sub_actions'])} sub_actions"
            )

    def test_at_least_1_domain(self, principles):
        for p in principles:
            assert len(p["domains"]) >= 1

    def test_domains_are_valid(self, principles):
        for p in principles:
            for d in p["domains"]:
                assert d in VALID_DOMAINS, f"Principle {p['id']}: invalid domain '{d}'"

    def test_at_least_1_example(self, principles):
        for p in principles:
            assert len(p["examples"]) >= 1, f"Principle {p['id']} has no examples"

    def test_examples_have_domain_and_text(self, principles):
        for p in principles:
            for ex in p["examples"]:
                assert "domain" in ex and "example" in ex

    def test_at_least_1_software_pattern(self, principles):
        for p in principles:
            assert len(p["software_patterns"]) >= 1, (
                f"Principle {p['id']} '{p['name']}' has no software_patterns"
            )

    def test_contradiction_types_valid(self, principles):
        for p in principles:
            assert len(p["contradiction_types"]) >= 1
            for ct in p["contradiction_types"]:
                assert ct in VALID_CONTRADICTION_TYPES

    def test_categories_valid(self, principles):
        for p in principles:
            assert len(p["categories"]) >= 1
            for cat in p["categories"]:
                assert cat in VALID_CATEGORIES, (
                    f"Principle {p['id']}: invalid category '{cat}'"
                )


class TestSearch:
    def test_search_by_name_segmentation(self, principles):
        matches = [p for p in principles if "segmentation" in p["name"].lower()]
        assert len(matches) == 1
        assert matches[0]["id"] == 1

    def test_search_by_domain_software(self, principles):
        sw = [p for p in principles if "software" in p["domains"]]
        assert len(sw) == 40, "Every principle should have a software domain mapping"

    def test_search_by_keyword_in_description(self, principles):
        matches = [p for p in principles if "divide" in p["description"].lower()]
        assert any(p["id"] == 1 for p in matches)

    def test_search_by_category(self, principles):
        structural = [p for p in principles if "structural" in p["categories"]]
        assert len(structural) >= 3


class TestSpecificPrinciples:
    """Spot-check specific principles against known TRIZ data."""

    def test_principle_1_segmentation(self, principles):
        p1 = next(p for p in principles if p["id"] == 1)
        assert p1["name"] == "Segmentation"
        assert "microservices" in p1["software_patterns"] or "microservice" in str(
            p1["software_patterns"]
        ).lower()

    def test_principle_40_composite_materials(self, principles):
        p40 = next(p for p in principles if p["id"] == 40)
        assert p40["name"] == "Composite Materials"

    def test_principle_22_blessing_in_disguise(self, principles):
        p22 = next(p for p in principles if p["id"] == 22)
        assert "blessing" in p22["name"].lower() or "disguise" in p22["name"].lower()

    def test_principle_15_dynamics(self, principles):
        p15 = next(p for p in principles if p["id"] == 15)
        assert p15["name"] == "Dynamics"
