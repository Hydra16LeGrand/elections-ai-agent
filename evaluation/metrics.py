"""Scoring functions for evaluation."""
import re
from typing import Union


def score_fact_lookup(actual: str, expected: str) -> dict:
    """Score fact lookup by exact or partial match."""
    if not actual or not expected:
        return {"score": 0.0, "match_type": "empty", "passed": False}

    actual_clean = actual.strip().upper()
    expected_clean = expected.strip().upper()

    # Exact match
    if actual_clean == expected_clean:
        return {"score": 1.0, "match_type": "exact", "passed": True}

    # Partial match - expected contained in actual
    if expected_clean in actual_clean:
        return {"score": 1.0, "match_type": "partial_contains", "passed": True}

    # Partial match - actual contained in expected
    if actual_clean in expected_clean:
        return {"score": 1.0, "match_type": "partial_reverse", "passed": True}

    # Check for name components (e.g., "KONE Yeo Jerome" vs "KONÉ Yéo Jérôme")
    actual_tokens = set(re.findall(r'[A-ZÀ-Ÿ]+', actual_clean))
    expected_tokens = set(re.findall(r'[A-ZÀ-Ÿ]+', expected_clean))

    if expected_tokens and actual_tokens:
        overlap = len(expected_tokens & actual_tokens) / len(expected_tokens)
        if overlap >= 0.7:
            return {"score": overlap, "match_type": "token_overlap", "passed": True}

    return {"score": 0.0, "match_type": "no_match", "passed": False}


def score_aggregation(actual: Union[int, float, str],
                      expected: Union[int, float],
                      tolerance_percent: float = 5.0) -> dict:
    """Score aggregation result with tolerance."""
    try:
        if isinstance(actual, str):
            # Extract number from text
            numbers = re.findall(r'[\d\s]+', actual.replace(',', '.').replace(' ', ''))
            if numbers:
                actual_val = float(numbers[0].replace(' ', ''))
            else:
                return {"score": 0.0, "error": "no_number_found", "passed": False}
        else:
            actual_val = float(actual)

        expected_val = float(expected)

        if expected_val == 0:
            diff = abs(actual_val)
            tolerance = tolerance_percent / 100.0
        else:
            diff = abs(actual_val - expected_val) / expected_val * 100
            tolerance = tolerance_percent

        passed = diff <= tolerance

        if passed:
            return {
                "score": 1.0,
                "diff_percent": round(diff, 2),
                "actual": actual_val,
                "expected": expected_val,
                "passed": True
            }
        else:
            return {
                "score": max(0, 1 - (diff / 100)),
                "diff_percent": round(diff, 2),
                "actual": actual_val,
                "expected": expected_val,
                "passed": False
            }

    except (ValueError, TypeError) as e:
        return {"score": 0.0, "error": str(e), "passed": False}


def calculate_metrics(results: list) -> dict:
    """Calculate aggregate metrics from results list."""
    if not results:
        return {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "pass_rate": 0.0,
            "avg_score": 0.0,
            "by_type": {}
        }

    passed = sum(1 for r in results if r.get('passed', False))
    total = len(results)

    scores = [r.get('score', 0) for r in results]
    avg_score = sum(scores) / len(scores) if scores else 0

    # Group by type
    by_type = {}
    for r in results:
        q_type = r.get('question_type', 'unknown')
        if q_type not in by_type:
            by_type[q_type] = {"total": 0, "passed": 0, "failed": 0}
        by_type[q_type]["total"] += 1
        if r.get('passed', False):
            by_type[q_type]["passed"] += 1
        else:
            by_type[q_type]["failed"] += 1

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total * 100, 1),
        "avg_score": round(avg_score, 3),
        "by_type": by_type
    }
