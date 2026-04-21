"""Tests for evaluation module."""
import pytest
from evaluation.metrics import score_fact_lookup, score_aggregation, calculate_metrics
from evaluation.eval_runner import load_dataset


class TestScoreFactLookup:
    """Tests for fact lookup scoring."""

    def test_exact_match(self):
        result = score_fact_lookup("KONÉ Yéo Jérôme", "KONÉ Yéo Jérôme")
        assert result["passed"] is True
        assert result["match_type"] == "exact"

    def test_partial_contains(self):
        result = score_fact_lookup("Le candidat KONÉ Yéo Jérôme a gagné", "KONÉ Yéo Jérôme")
        assert result["passed"] is True
        assert result["match_type"] == "partial_contains"

    def test_token_overlap(self):
        # Test case where most tokens match but not exact
        result = score_fact_lookup("KONE et YEO et JEROME RHDP", "KONE YEO JEROME")
        assert result["passed"] is True
        assert result["match_type"] == "token_overlap"

    def test_no_match(self):
        result = score_fact_lookup("Aucun résultat trouvé", "KONÉ Yéo Jérôme")
        assert result["passed"] is False
        assert result["match_type"] == "no_match"

    def test_empty_input(self):
        result = score_fact_lookup("", "KONÉ Yéo Jérôme")
        assert result["passed"] is False


class TestScoreAggregation:
    """Tests for aggregation scoring."""

    def test_exact_value(self):
        result = score_aggregation(137, 137, 5)
        assert result["passed"] is True
        assert result["diff_percent"] == 0

    def test_within_tolerance(self):
        result = score_aggregation(140, 137, 5)
        assert result["passed"] is True

    def test_outside_tolerance(self):
        result = score_aggregation(200, 137, 5)
        assert result["passed"] is False

    def test_extract_from_text(self):
        result = score_aggregation("Le RHDP a remporté 137 sièges", 137, 5)
        assert result["passed"] is True
        assert result["actual"] == 137.0

    def test_empty_string(self):
        result = score_aggregation("", 137, 5)
        assert result["passed"] is False


class TestCalculateMetrics:
    """Tests for metrics aggregation."""

    def test_empty_results(self):
        result = calculate_metrics([])
        assert result["total"] == 0
        assert result["pass_rate"] == 0.0

    def test_all_pass(self):
        results = [
            {"question_type": "fact_lookup", "score": 1.0, "passed": True},
            {"question_type": "fact_lookup", "score": 1.0, "passed": True},
        ]
        result = calculate_metrics(results)
        assert result["total"] == 2
        assert result["passed"] == 2
        assert result["pass_rate"] == 100.0
        assert result["avg_score"] == 1.0

    def test_mixed_results(self):
        results = [
            {"question_type": "fact_lookup", "score": 1.0, "passed": True},
            {"question_type": "aggregation", "score": 0.5, "passed": False},
        ]
        result = calculate_metrics(results)
        assert result["total"] == 2
        assert result["passed"] == 1
        assert result["pass_rate"] == 50.0
        assert result["by_type"]["fact_lookup"]["passed"] == 1
        assert result["by_type"]["aggregation"]["failed"] == 1


class TestDataset:
    """Tests for dataset loading and structure."""

    def test_load_dataset(self):
        dataset = load_dataset("evaluation/dataset.json")
        assert len(dataset) >= 15

    def test_required_fields(self):
        dataset = load_dataset("evaluation/dataset.json")
        for item in dataset:
            assert "id" in item
            assert "type" in item
            assert "question" in item
            if item["type"] == "fact_lookup":
                assert "expected_answer" in item
            if item["type"] == "aggregation":
                assert "expected_value" in item
