# Coding Agent Workbench

[![CI](https://github.com/yingchen-coding/coding_agent_workbench/actions/workflows/ci.yml/badge.svg)](https://github.com/yingchen-coding/coding_agent_workbench/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Evaluate coding-agent attempts with deterministic checks instead of vibes.

The workbench takes a JSON attempt record and grades whether an agent produced a small, tested,
reviewable, safe change. It is designed for local benchmarks, team dogfooding, and public demos
where the important question is:

> Did the agent actually complete the coding task without hidden regressions or risky edits?

## Install

```bash
python -m pip install -e .
```

## Quick Start

Evaluate an example:

```bash
python -m coding_agent_workbench evaluate examples/good_attempt.json --format table
```

Create a blank attempt template:

```bash
python -m coding_agent_workbench init-attempt --task-id parser-null-handling --out attempt.json
```

List scoring checks:

```bash
python -m coding_agent_workbench list-checks
```

Summarize adoption without confusing usage growth for task success:

```bash
python -m coding_agent_workbench adoption-report examples/adoption_signals.json --format markdown
```

## What It Scores

- tests passed or failed
- whether verification commands were recorded
- diff size and file-count blast radius
- risky code patterns such as dynamic execution, destructive shell, or committed secrets
- privacy leaks in diff text
- weak commit messages
- missing evidence for the stated task

## Adoption Reports

`adoption-report` turns weekly or monthly coding-agent rollout records into a grounded adoption
verdict. It requires task denominators, not just token volume or headline usage growth.

Each record can include:

```json
{
  "tool": "local-coding-agent",
  "period": "2026-W26",
  "workflow": "small bug fixes",
  "attempted_tasks": 10,
  "completed_tasks": 8,
  "accepted_changes": 8,
  "reverted_changes": 0,
  "verified_tasks": 9,
  "tokens": 240000,
  "cost": 9.6
}
```

The report emits completion rate, acceptance rate, revert rate, verification coverage, cost per
completed task, and an `adopt` / `pilot` / `do-not-scale` verdict. This keeps coding-agent
adoption claims honest: usage is interesting, but verified completed work is the signal.

## Attempt Schema

```json
{
  "task_id": "parser-null-handling",
  "goal": "Handle null values in the parser without changing output schema.",
  "changed_files": ["src/parser.py", "tests/test_parser.py"],
  "verification": [
    {"command": "pytest tests/test_parser.py -q", "status": "passed"}
  ],
  "diff_text": "... unified diff or extracted patch text ...",
  "commit_message": "Handle null parser values",
  "notes": "Short evidence summary."
}
```

