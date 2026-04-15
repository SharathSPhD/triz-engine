"""Tests for the TRIZ 39x39 Contradiction Matrix."""

import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "data"
MATRIX_PATH = DATA_DIR / "triz-matrix.json"


@pytest.fixture
def matrix():
    with open(MATRIX_PATH) as f:
        return json.load(f)


@pytest.fixture
def parameters(matrix):
    return matrix["parameters"]


@pytest.fixture
def cells(matrix):
    return matrix["matrix"]


class TestMatrixStructure:
    def test_has_parameters(self, matrix):
        assert "parameters" in matrix
        assert isinstance(matrix["parameters"], list)

    def test_has_matrix(self, matrix):
        assert "matrix" in matrix
        assert isinstance(matrix["matrix"], dict)

    def test_exactly_39_parameters(self, parameters):
        assert len(parameters) == 39

    def test_parameter_ids_are_1_through_39(self, parameters):
        ids = sorted(p["id"] for p in parameters)
        assert ids == list(range(1, 40))

    def test_no_duplicate_parameter_ids(self, parameters):
        ids = [p["id"] for p in parameters]
        assert len(ids) == len(set(ids))

    def test_no_duplicate_parameter_names(self, parameters):
        names = [p["name"] for p in parameters]
        assert len(names) == len(set(names))

    def test_parameters_have_required_fields(self, parameters):
        for p in parameters:
            assert "id" in p and "name" in p and "description" in p
            assert isinstance(p["id"], int)
            assert isinstance(p["name"], str) and len(p["name"]) > 0


class TestParameterContent:
    def test_known_parameter_names(self, parameters):
        by_id = {p["id"]: p["name"] for p in parameters}
        assert by_id[1] == "Weight of moving object"
        assert by_id[9] == "Speed"
        assert by_id[14] == "Strength"
        assert by_id[27] == "Reliability"
        assert by_id[39] == "Productivity"

    def test_parameters_have_software_equivalent(self, parameters):
        for p in parameters:
            assert "software_equivalent" in p, (
                f"Parameter {p['id']} missing software_equivalent"
            )
            assert isinstance(p["software_equivalent"], str)
            assert len(p["software_equivalent"]) > 0


class TestMatrixCells:
    def test_cell_values_are_lists_of_ints(self, cells):
        for key, val in cells.items():
            assert isinstance(val, list), f"Cell {key} is not a list"
            for v in val:
                assert isinstance(v, int), f"Cell {key} has non-int value {v}"

    def test_cell_values_in_valid_range(self, cells):
        for key, val in cells.items():
            for v in val:
                assert 1 <= v <= 40, f"Cell {key} has out-of-range principle {v}"

    def test_cell_keys_are_valid_format(self, cells):
        for key in cells:
            parts = key.split("_")
            assert len(parts) == 2, f"Invalid key format: {key}"
            a, b = int(parts[0]), int(parts[1])
            assert 1 <= a <= 39 and 1 <= b <= 39
            assert a != b, f"Diagonal cell found: {key}"

    def test_matrix_has_substantial_coverage(self, cells):
        assert len(cells) >= 500, (
            f"Matrix only has {len(cells)} cells; expected at least 500 populated cells"
        )


class TestKnownCells:
    """Spot-check specific cells from the published Altshuller matrix."""

    def test_weight_moving_vs_speed(self, cells):
        # Improving "Weight of moving object" (1) when "Speed" (9) worsens
        key = "1_9"
        assert key in cells or "9_1" in cells
        cell = cells.get(key, cells.get("9_1", []))
        assert len(cell) > 0, "Cell 1_9 should have recommendations"

    def test_speed_vs_force(self, cells):
        # Improving "Speed" (9) when "Force" (10) worsens
        key = "9_10"
        assert key in cells or "10_9" in cells
        cell = cells.get(key, cells.get("10_9", []))
        assert len(cell) > 0

    def test_reliability_vs_complexity(self, cells):
        # Improving "Reliability" (27) when "Device complexity" (36) worsens
        key = "27_36"
        assert key in cells or "36_27" in cells


class TestMatrixLookup:
    def test_lookup_returns_principles(self, cells):
        nonempty = [(k, v) for k, v in cells.items() if v]
        assert len(nonempty) > 0
        key, val = nonempty[0]
        assert all(1 <= p <= 40 for p in val)

    def test_empty_cells_return_empty_list(self, cells):
        empty = [k for k, v in cells.items() if len(v) == 0]
        for k in empty:
            assert cells[k] == []
