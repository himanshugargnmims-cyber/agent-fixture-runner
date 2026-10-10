# Agent Fixture Runner

A small, dependency-free harness for testing command-line agents against JSONL fixtures. It runs a fresh process for each case, sends the case input on standard input, and grades standard output with deterministic rules. No model API, account, or network service is required by the runner.

## Run the example

Requires Python 3.10 or newer.

```bash
python3 runner.py examples/cases.jsonl --timeout 3 --report reports/example.json -- python3 examples/uppercase_agent.py
python3 -m unittest discover -s tests -v
```

The example should report 3/3 passing. The runner exits `0` when all cases pass, `1` when a case fails, and `2` for invalid fixtures or arguments.

## Fixture format

One JSON object per line. Blank lines are ignored. Each object has:

| Field | Meaning |
| --- | --- |
| `id` | Unique, nonempty case ID. |
| `input` | String sent to the agent's standard input. |
| `expected` | Primary expected standard output, as a string. |
| `alternatives` | Optional array of other acceptable strings. |
| `match` | `exact` (default) or `equivalent`. |

```json
{"id":"greeting","input":"hello","expected":"HELLO","match":"exact"}
{"id":"spacing","input":"hello world","expected":"HELLO WORLD","match":"equivalent"}
```

`exact` compares every character, including trailing newlines. `equivalent` applies Unicode NFKC normalization, case folding, and whitespace collapsing before comparison. It is a text normalization rule, **not** a semantic or factual equivalence judge. If an output matches an alternative byte-for-byte, it is recorded as `exact`; if it only matches after normalization, it is `equivalent`.

## Agent protocol

For each fixture, the runner executes the command after `--` with no shell, writes `input` to its standard input, and captures its standard output and standard error. The agent should print only its answer to standard output. A nonzero exit code, timeout, or mismatched output fails that case. Commands are executed relative to the current working directory.

```bash
python3 runner.py path/to/cases.jsonl -- python3 path/to/my_agent.py
```

The JSON report includes each case's result, duration, captured output, exit code, and a summary. It contains fixture text and agent output; review it before sharing. The runner does not sandbox the command. Run only agents and fixtures you trust.

## Why this exists

Agent outputs can vary, and a passing example is easier to trust when the expected behavior is explicit and rerunnable. This project is intentionally a small test harness rather than a model leaderboard. Add domain-specific fixtures and human review for claims that deterministic text checks cannot establish.

## Contributing

Open an issue with a reproducible fixture and expected result. Keep scoring changes documented, because changing normalization can change past verdicts.

## License

MIT. See [LICENSE](LICENSE).

