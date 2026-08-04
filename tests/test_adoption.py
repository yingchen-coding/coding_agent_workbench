import json
import subprocess
import sys
from pathlib import Path

import pytest

from coding_agent_workbench.adoption import (
    adoption_report,
    load_adoption_records,
    render_adoption_markdown,
)


def test_adoption_report_uses_real_denominators(tmp_path):
    path = tmp_path / "adoption.json"
    path.write_text(
        json.dumps(
            [
                {
                    "tool": "agent-a",
                    "attempted_tasks": 10,
                    "completed_tasks": 8,
                    "accepted_changes": 7,
                    "reverted_changes": 1,
                    "verified_tasks": 8,
                    "tokens": 1000,
                    "cost": 2.5,
                }
            ]
        ),
        encoding="utf-8",
    )
    report = adoption_report(load_adoption_records(path))
    assert report["totals"]["completion_rate"] == 0.8
    assert report["totals"]["acceptance_rate"] == 0.7
    assert report["totals"]["verification_coverage"] == 0.8
    assert report["totals"]["cost_per_completed_task"] == 0.3125
    assert report["totals"]["verdict"] == "pilot"


def test_adoption_report_rejects_impossible_counts(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            [
                {
                    "tool": "agent-a",
                    "attempted_tasks": 2,
                    "completed_tasks": 3,
                    "accepted_changes": 1,
                    "reverted_changes": 0,
                    "verified_tasks": 1,
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="cannot exceed attempted_tasks"):
        load_adoption_records(path)


def test_adoption_markdown_shows_verdict_and_warnings():
    report = adoption_report(
        [
            {
                "tool": "agent-a",
                "period": "",
                "workflow": "bug fixes",
                "attempted_tasks": 5,
                "completed_tasks": 2,
                "accepted_changes": 2,
                "reverted_changes": 1,
                "verified_tasks": 2,
                "tokens": 0.0,
                "cost": 0.0,
            }
        ]
    )
    markdown = render_adoption_markdown(report)
    assert "# Coding Agent Adoption Report" in markdown
    assert "Verdict: do-not-scale" in markdown
    assert "Warnings" in markdown


_EXAMPLES = Path(__file__).parents[1] / "examples"


def test_cli_can_emit_adoption_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "coding_agent_workbench",
            "adoption-report",
            str(_EXAMPLES / "adoption_signals.json"),
            "--format",
            "markdown",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "# Coding Agent Adoption Report" in result.stdout
    assert "local-coding-agent" in result.stdout


def test_load_adoption_records_reports_bad_number_with_location(tmp_path):
    # A non-numeric field must fail with a clear, located error — never a raw traceback, and never a
    # silent coercion to 0 (which could flip the adopt/pilot/do-not-scale verdict).
    path = tmp_path / "adoption.json"
    path.write_text(json.dumps([{"tool": "a", "attempted_tasks": "lots"}]), encoding="utf-8")
    with pytest.raises(ValueError, match=r"record 1 field 'attempted_tasks' must be a number"):
        load_adoption_records(path)


def test_load_adoption_records_rejects_fractional_task_count(tmp_path):
    path = tmp_path / "adoption.json"
    path.write_text(json.dumps([{"tool": "a", "attempted_tasks": 3.5}]), encoding="utf-8")
    with pytest.raises(ValueError, match="must be a whole number"):
        load_adoption_records(path)


def test_load_adoption_records_accepts_numeric_strings_and_whole_floats(tmp_path):
    path = tmp_path / "adoption.json"
    path.write_text(json.dumps([{
        "tool": "a", "attempted_tasks": "5", "completed_tasks": 5.0,
        "tokens": "1200.5", "cost": "0.4",
    }]), encoding="utf-8")
    records = load_adoption_records(path)
    assert records[0]["attempted_tasks"] == 5
    assert records[0]["completed_tasks"] == 5
    assert records[0]["tokens"] == 1200.5


def test_save_json_is_atomic_no_temp_left(tmp_path):
    from coding_agent_workbench.io import save_json
    p = tmp_path / "out.json"
    save_json({"k": "v"}, p)
    assert [f.name for f in tmp_path.iterdir() if ".tmp." in f.name] == []
    assert json.loads(p.read_text())["k"] == "v"


def test_load_adoption_records_rejects_negative_tokens_or_cost(tmp_path):
    # A negative cost/tokens value used to pass validation silently and flow into
    # cost_per_completed_task, producing a nonsensical negative cost figure in the adoption
    # report instead of a located, actionable error.
    for field, value in (("tokens", -1), ("cost", -0.01)):
        path = tmp_path / "adoption.json"
        path.write_text(
            json.dumps([{"tool": "a", "attempted_tasks": 1, field: value}]), encoding="utf-8"
        )
        with pytest.raises(ValueError, match=f"field '{field}' cannot be negative"):
            load_adoption_records(path)


def test_load_adoption_records_rejects_non_finite_numbers(tmp_path):
    # "nan"/"inf" parse as floats but are not real measurements; int(NaN) would raise a cryptic
    # error, so they must be rejected with the same clear, located message as any other bad number.
    for bad in ("nan", "inf", "-inf"):
        path = tmp_path / "adoption.json"
        path.write_text(json.dumps([{"tool": "a", "attempted_tasks": bad}]), encoding="utf-8")
        with pytest.raises(ValueError, match="must be a finite number"):
            load_adoption_records(path)
