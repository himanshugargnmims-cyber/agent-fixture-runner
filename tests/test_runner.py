import json
import sys
import tempfile
import unittest
from pathlib import Path

from runner import FixtureError, grade, load_cases, main, run_cases


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_AGENT = ROOT / "examples" / "uppercase_agent.py"


class FixtureRunnerTests(unittest.TestCase):
    def test_example_cases_pass_with_exact_and_equivalent_results(self) -> None:
        cases = load_cases(ROOT / "examples" / "cases.jsonl")
        report = run_cases(cases, [sys.executable, str(EXAMPLE_AGENT)], 2)
        self.assertEqual(report["summary"], {"total": 3, "passed": 3, "failed": 0})
        self.assertEqual([x["status"] for x in report["results"]], ["exact", "exact", "equivalent"])

    def test_equivalence_is_normalization_not_semantics(self) -> None:
        case = {"expected": "Café au lait", "alternatives": [], "match": "equivalent"}
        self.assertEqual(grade("  CAFÉ   AU LAIT  ", case), "equivalent")
        self.assertEqual(grade("coffee with milk", case), "mismatch")

    def test_duplicate_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            row = {"id": "same", "input": "x", "expected": "X"}
            path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(FixtureError, "duplicate id"):
                load_cases(path)

    def test_timeout_fails_case(self) -> None:
        case = {"id": "slow", "input": "", "expected": "ok", "alternatives": [], "match": "exact"}
        report = run_cases([case], [sys.executable, "-c", "import time; time.sleep(1)"], 0.05)
        self.assertEqual(report["results"][0]["status"], "timeout")
        self.assertEqual(report["summary"]["failed"], 1)

    def test_nonzero_exit_fails_even_if_output_matches(self) -> None:
        case = {"id": "bad-exit", "input": "", "expected": "ok", "alternatives": [], "match": "exact"}
        report = run_cases([case], [sys.executable, "-c", "import sys; sys.stdout.write('ok'); sys.exit(1)"], 1)
        self.assertEqual(report["results"][0]["status"], "agent_error")

    def test_cli_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            code = main([str(ROOT / "examples" / "cases.jsonl"), "--timeout", "2", "--report", str(path), "--", sys.executable, str(EXAMPLE_AGENT)])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["summary"]["passed"], 3)


if __name__ == "__main__":
    unittest.main()
