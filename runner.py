"""Run deterministic JSONL fixtures against a subprocess agent."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any


class FixtureError(ValueError):
    """Raised when a fixture file is malformed."""


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise FixtureError(f"Cannot read {path}: {exc}") from exc

    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FixtureError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(case, dict):
            raise FixtureError(f"{path}:{line_number}: expected a JSON object")
        allowed = {"id", "input", "expected", "alternatives", "match"}
        unknown = set(case) - allowed
        if unknown:
            raise FixtureError(f"{path}:{line_number}: unknown field(s): {', '.join(sorted(unknown))}")
        for key in ("id", "input", "expected"):
            if not isinstance(case.get(key), str):
                raise FixtureError(f"{path}:{line_number}: {key} must be a string")
        if not case["id"].strip():
            raise FixtureError(f"{path}:{line_number}: id cannot be empty")
        if case["id"] in seen:
            raise FixtureError(f"{path}:{line_number}: duplicate id {case['id']!r}")
        seen.add(case["id"])
        alternatives = case.get("alternatives", [])
        if not isinstance(alternatives, list) or not all(isinstance(x, str) for x in alternatives):
            raise FixtureError(f"{path}:{line_number}: alternatives must be an array of strings")
        if case.get("match", "exact") not in {"exact", "equivalent"}:
            raise FixtureError(f"{path}:{line_number}: match must be exact or equivalent")
        cases.append({
            "id": case["id"],
            "input": case["input"],
            "expected": case["expected"],
            "alternatives": alternatives,
            "match": case.get("match", "exact"),
        })
    if not cases:
        raise FixtureError(f"{path}: no fixtures found")
    return cases


def grade(output: str, case: dict[str, Any]) -> str:
    accepted = [case["expected"], *case["alternatives"]]
    if output in accepted:
        return "exact"
    if case["match"] == "equivalent" and _normalized(output) in {_normalized(x) for x in accepted}:
        return "equivalent"
    return "mismatch"


def run_cases(cases: list[dict[str, Any]], command: list[str], timeout: float) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for case in cases:
        started = time.monotonic()
        result: dict[str, Any] = {"id": case["id"], "match": case["match"]}
        try:
            process = subprocess.run(
                command,
                input=case["input"],
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
            result.update({
                "output": process.stdout,
                "stderr": process.stderr,
                "exit_code": process.returncode,
                "status": grade(process.stdout, case) if process.returncode == 0 else "agent_error",
            })
        except subprocess.TimeoutExpired as exc:
            result.update({"status": "timeout", "output": _as_text(exc.stdout), "stderr": _as_text(exc.stderr), "exit_code": None})
        except OSError as exc:
            result.update({"status": "agent_error", "output": "", "stderr": str(exc), "exit_code": None})
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        results.append(result)

    passed = sum(result["status"] in {"exact", "equivalent"} for result in results)
    return {
        "schema_version": 1,
        "command": command,
        "timeout_seconds": timeout,
        "summary": {"total": len(results), "passed": passed, "failed": len(results) - passed},
        "results": results,
    }


def _as_text(value: bytes | str | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixtures", type=Path, help="JSONL fixture file")
    parser.add_argument("--timeout", type=float, default=5.0, help="seconds per fixture (default: 5)")
    parser.add_argument("--report", type=Path, help="write a JSON report here")
    if "--" not in arguments:
        parser.parse_args(arguments)  # allow --help to exit normally
        parser.error("provide an agent command after --")
    separator = arguments.index("--")
    args = parser.parse_args(arguments[:separator])
    command = arguments[separator + 1 :]
    if not command:
        parser.error("provide an agent command after --")
    if not 0 < args.timeout <= 3600:
        parser.error("--timeout must be greater than 0 and at most 3600")
    try:
        cases = load_cases(args.fixtures)
    except FixtureError as exc:
        print(f"Fixture error: {exc}", file=sys.stderr)
        return 2
    report = run_cases(cases, command, args.timeout)
    for result in report["results"]:
        print(f"{result['id']}: {result['status']}")
    summary = report["summary"]
    print(f"Passed {summary['passed']}/{summary['total']} fixtures")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Report: {args.report}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
