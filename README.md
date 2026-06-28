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

## What It Scores

- tests passed or failed
- whether verification commands were recorded
- diff size and file-count blast radius
- risky code patterns such as dynamic execution, destructive shell, or committed secrets
- privacy leaks in diff text
- weak commit messages
- missing evidence for the stated task

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

## Validate

```bash
scripts/pr_review_check.sh
```
