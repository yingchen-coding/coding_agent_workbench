import json
import subprocess
import sys

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


def test_cli_can_emit_adoption_markdown():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "coding_agent_workbench",
            "adoption-report",
            "examples/adoption_signals.json",
            "--format",
            "markdown",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "# Coding Agent Adoption Report" in result.stdout
    assert "local-coding-agent" in result.stdout
