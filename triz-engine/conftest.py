import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def data_dir():
    return DATA_DIR


@pytest.fixture
def knowledge_base(data_dir):
    with open(data_dir / "triz-knowledge-base.json") as f:
        return json.load(f)


@pytest.fixture
def matrix_data(data_dir):
    with open(data_dir / "triz-matrix.json") as f:
        return json.load(f)
