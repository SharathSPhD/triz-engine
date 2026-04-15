"""Tests for external benchmark adapters."""

import json
from pathlib import Path

import pytest

from benchmark.external.trizbench_adapter import (
    score_contradiction_prediction,
    score_principle_prediction,
)
from benchmark.external.macgyver_adapter import (
    _level_score,
    format_prompt as macgyver_format,
    TRIZ_SYSTEM_PROMPT,
    VANILLA_SYSTEM_PROMPT,
)
from benchmark.external.cresowlve_adapter import (
    score_answer,
)


class TestTrizbenchScoring:
    def test_exact_match(self):
        sub = {"contradiction_type": "technical", "triz_param_a": 28, "triz_param_b": 30}
        gt = {"contradiction_type": "technical", "triz_param_a": 28, "triz_param_b": 30}
        result = score_contradiction_prediction(sub, gt)
        assert result["type_correct"]
        assert result["params_exact"]

    def test_wrong_type(self):
        sub = {"contradiction_type": "physical", "triz_param_a": 28, "triz_param_b": 30}
        gt = {"contradiction_type": "technical", "triz_param_a": 28, "triz_param_b": 30}
        result = score_contradiction_prediction(sub, gt)
        assert not result["type_correct"]

    def test_partial_param_match(self):
        sub = {"contradiction_type": "technical", "triz_param_a": 28, "triz_param_b": 99}
        gt = {"contradiction_type": "technical", "triz_param_a": 28, "triz_param_b": 30}
        result = score_contradiction_prediction(sub, gt)
        assert result["type_correct"]
        assert not result["params_exact"]
        assert result["params_partial"]

    def test_principle_exact_f1(self):
        result = score_principle_prediction([1, 15, 35], [1, 15, 35])
        assert result["f1"] == 1.0

    def test_principle_partial(self):
        result = score_principle_prediction([1, 15], [1, 15, 35])
        assert 0.0 < result["f1"] < 1.0
        assert result["precision"] == 1.0
        assert result["recall"] < 1.0

    def test_principle_no_overlap(self):
        result = score_principle_prediction([2, 3], [1, 15, 35])
        assert result["f1"] == 0.0

    def test_principle_empty(self):
        result = score_principle_prediction([], [1, 15, 35])
        assert result["f1"] == 0.0

    def test_principle_both_empty(self):
        result = score_principle_prediction([], [])
        assert result["f1"] == 1.0


class TestMacGyverScoring:
    def test_level_scores(self):
        assert _level_score("perfect") == 1.0
        assert _level_score("correct") == 0.75
        assert _level_score("partial") == 0.4
        assert _level_score("wrong") == 0.0

    def test_format_prompt(self):
        problem = {"problem": "How to open a locked door with a credit card?"}
        prompt = macgyver_format(problem)
        assert "credit card" in prompt
        assert "creative" in prompt.lower()

    def test_triz_system_prompt_has_principles(self):
        assert "Principle 1" in TRIZ_SYSTEM_PROMPT
        assert "Segmentation" in TRIZ_SYSTEM_PROMPT
        assert "contradiction" in TRIZ_SYSTEM_PROMPT.lower()

    def test_no_judge_returns_unscored(self):
        from benchmark.external.macgyver_adapter import score_macgyver_solution
        result = score_macgyver_solution("problem", "solution", "reference")
        assert result["level"] == "unscored"


class TestCresOWLveScoring:
    def test_exact_match(self):
        result = score_answer("What?", "The answer is fire", "fire")
        assert result["correct"]

    def test_no_match(self):
        result = score_answer("What?", "I think water", "fire")
        assert not result["correct"]

    def test_alternative_match(self):
        result = score_answer(
            "What?", "The answer is flame", "fire",
            other_answers=["flame", "blaze"],
        )
        assert result["correct"]

    def test_llm_judge_correct(self):
        def mock_judge(prompt):
            return "CORRECT. The answer captures the key insight."

        result = score_answer("Q?", "fire", "flame", judge_fn=mock_judge)
        assert result["correct"]
        assert result["method"] == "llm_judge"

    def test_llm_judge_incorrect(self):
        def mock_judge(prompt):
            return "INCORRECT. The answer misses the point."

        result = score_answer("Q?", "water", "fire", judge_fn=mock_judge)
        assert not result["correct"]


class TestRunnerIntegration:
    """Test the new runner features (dynamic loading, failure taxonomy, etc.)."""

    def test_load_participant_configs(self):
        from benchmark.runner import load_participant_configs
        configs = load_participant_configs()
        assert "triz-engine" in configs
        assert "vanilla-claude" in configs
        assert configs["triz-engine"]["use_mcp"] is True
        assert configs["vanilla-claude"]["use_mcp"] is False

    def test_triz_engine_is_plugin_type(self):
        from benchmark.runner import load_participant_configs
        configs = load_participant_configs()
        assert configs["triz-engine"]["type"] == "plugin"

    def test_vanilla_claude_is_baseline(self):
        from benchmark.runner import load_participant_configs
        configs = load_participant_configs()
        assert configs["vanilla-claude"]["type"] == "baseline"

    def test_external_participants_detected(self):
        from benchmark.runner import load_participant_configs
        configs = load_participant_configs()
        external = {
            name for name, cfg in configs.items()
            if cfg.get("type") == "external"
        }
        assert "gpt4o-triz" in external or "gemini-triz" in external

    def test_validate_submission_valid(self):
        from benchmark.runner import validate_submission
        sub = {
            "contradiction_type": "technical",
            "triz_param_a": 28,
            "triz_param_b": 30,
            "principles_applied": [1, 15],
            "solution_summary": "Test solution",
        }
        issues = validate_submission(sub)
        assert len(issues) == 0

    def test_validate_submission_missing_fields(self):
        from benchmark.runner import validate_submission
        sub = {"contradiction_type": "technical"}
        issues = validate_submission(sub)
        assert len(issues) >= 3

    def test_validate_submission_invalid_type(self):
        from benchmark.runner import validate_submission
        sub = {
            "contradiction_type": "invalid",
            "triz_param_a": 28,
            "triz_param_b": 30,
            "principles_applied": [1],
            "solution_summary": "Test",
        }
        issues = validate_submission(sub)
        assert any("Invalid contradiction_type" in i for i in issues)

    def test_validate_submission_invalid_param(self):
        from benchmark.runner import validate_submission
        sub = {
            "contradiction_type": "technical",
            "triz_param_a": 99,
            "triz_param_b": 30,
            "principles_applied": [1],
            "solution_summary": "Test",
        }
        issues = validate_submission(sub)
        assert any("triz_param_a" in i for i in issues)

    def test_run_status_enum(self):
        from benchmark.runner import RunStatus
        assert RunStatus.SUCCESS.value == "success"
        assert RunStatus.INFRA_FAILURE.value == "infra_failure"
        assert RunStatus.PARSE_FAILURE.value == "parse_failure"
        assert RunStatus.TIMEOUT_FAILURE.value == "timeout_failure"

    def test_extract_scores_filters_failures(self):
        from benchmark.runner import extract_scores, RunStatus
        results = {
            ("a", "TB-01"): {"status": RunStatus.SUCCESS, "final_score": 85.0},
            ("a", "TB-02"): {"status": RunStatus.INFRA_FAILURE, "final_score": None},
            ("b", "TB-01"): {"status": "success", "final_score": 45.0},
        }
        scores = extract_scores(results)
        assert ("a", "TB-01") in scores
        assert ("b", "TB-01") in scores
        assert ("a", "TB-02") not in scores

    def test_generate_mcp_config(self):
        from benchmark.runner import _generate_mcp_config
        config_path = _generate_mcp_config()
        assert config_path.exists()
        data = json.loads(config_path.read_text())
        assert "mcpServers" in data
        assert "triz-knowledge" in data["mcpServers"]
        server = data["mcpServers"]["triz-knowledge"]
        assert Path(server["command"]).exists()
        assert Path(server["args"][0]).exists()
