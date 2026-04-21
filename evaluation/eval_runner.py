"""Offline evaluation runner for CI Elections AI Agent."""
import json
import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.sql_agent import ask_hybrid
from .metrics import score_fact_lookup, score_aggregation, calculate_metrics


def load_dataset(path: str = "evaluation/dataset.json") -> list:
    """Load evaluation dataset from JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def run_single_test(question_data: dict, timeout: int = 60) -> dict:
    """Run a single evaluation test case."""
    qid = question_data['id']
    qtype = question_data['type']
    question = question_data['question']

    result = {
        'id': qid,
        'question_type': qtype,
        'question': question,
        'passed': False,
        'score': 0.0,
        'actual': None,
        'expected': None,
        'error': None,
        'trace': None,
        'duration_ms': 0
    }

    start = time.time()
    try:
        response = ask_hybrid(question)
        duration = int((time.time() - start) * 1000)

        result['duration_ms'] = duration
        result['actual'] = response.get('narrative', '')
        result['trace'] = response.get('trace', {})

        if qtype == 'fact_lookup':
            expected = question_data['expected_answer']
            result['expected'] = expected
            score_result = score_fact_lookup(result['actual'], expected)
            result.update(score_result)

        elif qtype == 'aggregation':
            expected = question_data['expected_value']
            tolerance = question_data.get('tolerance_percent', 5)
            result['expected'] = expected
            score_result = score_aggregation(result['actual'], expected, tolerance)
            result.update(score_result)

    except Exception as e:
        result['duration_ms'] = int((time.time() - start) * 1000)
        result['error'] = str(e)

    return result


def run_evaluation(dataset_path: str = "evaluation/dataset.json",
                   output_path: Optional[str] = None) -> dict:
    """Run full evaluation suite and generate report."""
    print(f"\n{'='*60}")
    print("CI ELECTIONS - OFFLINE EVALUATION SUITE")
    print(f"{'='*60}\n")

    dataset = load_dataset(dataset_path)
    print(f"Loaded {len(dataset)} test cases from {dataset_path}\n")

    results = []
    failures = []

    for i, test_case in enumerate(dataset, 1):
        print(f"[{i}/{len(dataset)}] Running: {test_case['id']} ({test_case['type']})")
        print(f"    Q: {test_case['question']}")

        result = run_single_test(test_case)
        results.append(result)

        status = "PASS" if result['passed'] else "FAIL"
        print(f"    Status: {status} | Score: {result['score']:.2f}")

        if not result['passed']:
            failures.append(result)
            if result.get('error'):
                print(f"    Error: {result['error'][:100]}")

        print()

    metrics = calculate_metrics(results)

    report = {
        'summary': metrics,
        'results': results,
        'failures': failures
    }

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"Full report saved to: {output_path}")

    print_summary(metrics, failures)

    return report


def print_summary(metrics: dict, failures: list):
    """Print evaluation summary table."""
    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}\n")

    print(f"Total Tests:    {metrics['total']}")
    print(f"Passed:         {metrics['passed']}")
    print(f"Failed:         {metrics['failed']}")
    print(f"Pass Rate:      {metrics['pass_rate']}%")
    print(f"Avg Score:      {metrics['avg_score']}")

    print(f"\n{'-'*40}")
    print("By Question Type:")
    print(f"{'-'*40}")

    for qtype, stats in metrics['by_type'].items():
        rate = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
        print(f"  {qtype:20} {stats['passed']}/{stats['total']} ({rate:.1f}%)")

    if failures:
        print(f"\n{'='*60}")
        print(f"FAILURES ({len(failures)} tests)")
        print(f"{'='*60}\n")

        for f in failures[:10]:
            print(f"  ID:      {f['id']}")
            print(f"  Q:       {f['question']}")
            print(f"  Type:    {f['question_type']}")
            print(f"  Expected: {f['expected']}")
            print(f"  Actual:   {f['actual'][:100]}..." if len(str(f['actual'])) > 100 else f"  Actual:   {f['actual']}")
            if f.get('match_type'):
                print(f"  Match:   {f['match_type']}")
            if f.get('diff_percent') is not None:
                print(f"  Diff:    {f['diff_percent']}%")
            if f.get('error'):
                print(f"  Error:   {f['error']}")
            print()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Run offline evaluation suite')
    parser.add_argument('--dataset', default='evaluation/dataset.json',
                        help='Path to dataset JSON')
    parser.add_argument('--output', '-o', default=None,
                        help='Output path for JSON report')
    parser.add_argument('--filter', '-f', default=None,
                        help='Filter by question type (fact_lookup|aggregation)')

    args = parser.parse_args()

    run_evaluation(args.dataset, args.output)


if __name__ == "__main__":
    main()
