"""CLI for Coding Agent Workbench."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .adoption import adoption_report, load_adoption_records, render_adoption_markdown
from .context import audit_context, render_context_markdown
from .io import blank_attempt, load_attempt, render_table, save_json
from .scoring import check_catalog, evaluate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init-attempt", help="write a blank attempt JSON template")
    init.add_argument("--task-id", required=True)
    init.add_argument("--out", type=Path, required=True)

    eval_cmd = sub.add_parser("evaluate", help="evaluate an attempt JSON file")
    eval_cmd.add_argument("attempt", type=Path)
    eval_cmd.add_argument("--format", choices=["json", "table"], default="json")
    eval_cmd.add_argument("--fail-under", type=int, default=0)

    adoption = sub.add_parser(
        "adoption-report",
        help="summarize coding-agent adoption with task-success denominators",
    )
    adoption.add_argument("records", type=Path)
    adoption.add_argument("--format", choices=["json", "markdown"], default="json")

    context = sub.add_parser(
        "context-audit",
        help="compare raw-tail and active-request-first context retention",
    )
    context.add_argument("corpus", type=Path)
    context.add_argument("--budget", type=int, default=256)
    context.add_argument("--format", choices=["json", "markdown"], default="json")

    sub.add_parser("list-checks", help="list deterministic scoring checks")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "init-attempt":
        save_json(blank_attempt(args.task_id), args.out)
        print(str(args.out))
        return 0
    if args.command == "list-checks":
        print(json.dumps(check_catalog(), indent=2))
        return 0
    if args.command == "evaluate":
        evaluation = evaluate(load_attempt(args.attempt))
        if args.format == "table":
            print(render_table(evaluation), end="")
        else:
            print(json.dumps(evaluation.to_dict(), indent=2))
        if evaluation.score < args.fail_under:
            print(f"score {evaluation.score} is below threshold {args.fail_under}", file=sys.stderr)
            return 1
        return 0
    if args.command == "adoption-report":
        report = adoption_report(load_adoption_records(args.records))
        if args.format == "markdown":
            print(render_adoption_markdown(report), end="")
        else:
            print(json.dumps(report, indent=2))
        return 0
    if args.command == "context-audit":
        report = audit_context(args.corpus, budget=args.budget)
        if args.format == "markdown":
            print(render_context_markdown(report), end="")
        else:
            print(json.dumps(report, indent=2))
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
