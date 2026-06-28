"""Adoption metrics for coding-agent rollouts."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


REQUIRED_NUMERIC_FIELDS = (
    "attempted_tasks",
    "completed_tasks",
    "accepted_changes",
    "reverted_changes",
    "verified_tasks",
)


def load_adoption_records(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("records"), list):
        data = data["records"]
    if not isinstance(data, list):
        raise ValueError("adoption input must be a JSON array or an object with records[]")
    records = []
    for index, raw in enumerate(data, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"record {index} must be an object")
        records.append(_normalize_record(raw, index))
    return records


def adoption_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_tool: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_tool[str(record["tool"])].append(record)

    tool_reports = [_summarize_group(tool, rows) for tool, rows in sorted(by_tool.items())]
    totals = _summarize_group("all", records)
    return {
        "records": len(records),
        "totals": totals,
        "tools": tool_reports,
        "warnings": _warnings(totals, tool_reports),
    }


def render_adoption_markdown(report: dict[str, Any]) -> str:
    totals = report["totals"]
    lines = [
        "# Coding Agent Adoption Report",
        "",
        f"- Records: {report['records']}",
        f"- Attempted tasks: {totals['attempted_tasks']}",
        f"- Completed tasks: {totals['completed_tasks']}",
        f"- Completion rate: {_pct(totals['completion_rate'])}",
        f"- Acceptance rate: {_pct(totals['acceptance_rate'])}",
        f"- Revert rate: {_pct(totals['revert_rate'])}",
        f"- Verification coverage: {_pct(totals['verification_coverage'])}",
        f"- Cost per completed task: {totals['cost_per_completed_task']:.4f}",
        f"- Verdict: {totals['verdict']}",
        "",
        "## By Tool",
        "",
    ]
    for item in report["tools"]:
        lines.append(
            "- {tool}: {completed}/{attempted} completed, {acceptance} accepted, "
            "{reverts} reverted, {verified} verified, verdict={verdict}".format(
                tool=item["tool"],
                completed=item["completed_tasks"],
                attempted=item["attempted_tasks"],
                acceptance=_pct(item["acceptance_rate"]),
                reverts=_pct(item["revert_rate"]),
                verified=_pct(item["verification_coverage"]),
                verdict=item["verdict"],
            )
        )
    warnings = report.get("warnings") or []
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines) + "\n"


def _normalize_record(raw: dict[str, Any], index: int) -> dict[str, Any]:
    record = {
        "tool": str(raw.get("tool") or raw.get("agent") or raw.get("provider") or "unknown"),
        "period": str(raw.get("period") or ""),
        "workflow": str(raw.get("workflow") or "unknown"),
        "tokens": float(raw.get("tokens") or 0),
        "cost": float(raw.get("cost") or 0),
    }
    for field in REQUIRED_NUMERIC_FIELDS:
        value = int(raw.get(field) or 0)
        if value < 0:
            raise ValueError(f"record {index} field {field} cannot be negative")
        record[field] = value
    attempted = record["attempted_tasks"]
    for field in ("completed_tasks", "accepted_changes", "reverted_changes", "verified_tasks"):
        if record[field] > attempted:
            raise ValueError(f"record {index} field {field} cannot exceed attempted_tasks")
    if record["reverted_changes"] > record["accepted_changes"]:
        raise ValueError(f"record {index} reverted_changes cannot exceed accepted_changes")
    return record


def _summarize_group(tool: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    attempted = sum(item["attempted_tasks"] for item in records)
    completed = sum(item["completed_tasks"] for item in records)
    accepted = sum(item["accepted_changes"] for item in records)
    reverted = sum(item["reverted_changes"] for item in records)
    verified = sum(item["verified_tasks"] for item in records)
    tokens = sum(float(item["tokens"]) for item in records)
    cost = sum(float(item["cost"]) for item in records)
    return {
        "tool": tool,
        "attempted_tasks": attempted,
        "completed_tasks": completed,
        "accepted_changes": accepted,
        "reverted_changes": reverted,
        "verified_tasks": verified,
        "tokens": round(tokens, 4),
        "cost": round(cost, 4),
        "completion_rate": _ratio(completed, attempted),
        "acceptance_rate": _ratio(accepted, attempted),
        "revert_rate": _ratio(reverted, accepted),
        "verification_coverage": _ratio(verified, attempted),
        "cost_per_completed_task": _ratio_float(cost, completed),
        "verdict": _verdict(attempted, completed, accepted, reverted, verified),
    }


def _warnings(totals: dict[str, Any], tools: list[dict[str, Any]]) -> list[str]:
    warnings = []
    if totals["attempted_tasks"] == 0:
        warnings.append("No attempted task denominator; adoption claims are not meaningful.")
    if totals["verification_coverage"] < 0.8:
        warnings.append("Verification coverage below 80%; usage growth may hide regressions.")
    if totals["revert_rate"] > 0.1:
        warnings.append("Revert rate above 10%; accepted changes are not stable enough.")
    for item in tools:
        if item["completion_rate"] < 0.6 and item["attempted_tasks"] >= 5:
            warnings.append(f"{item['tool']} has low completion rate for a non-trivial sample.")
    return warnings


def _verdict(
    attempted: int,
    completed: int,
    accepted: int,
    reverted: int,
    verified: int,
) -> str:
    if attempted == 0:
        return "insufficient-denominator"
    completion = _ratio(completed, attempted)
    acceptance = _ratio(accepted, attempted)
    verification = _ratio(verified, attempted)
    revert = _ratio(reverted, accepted)
    if completion >= 0.8 and acceptance >= 0.7 and verification >= 0.8 and revert <= 0.1:
        return "adopt"
    if completion >= 0.6 and acceptance >= 0.5 and verification >= 0.6 and revert <= 0.2:
        return "pilot"
    return "do-not-scale"


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _ratio_float(numerator: float, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"
