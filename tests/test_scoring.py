import json
from pathlib import Path

from coding_agent_workbench.io import load_attempt
from coding_agent_workbench.models import Attempt, Verification
from coding_agent_workbench.scoring import evaluate


ROOT = Path(__file__).resolve().parents[1]


def test_good_attempt_scores_a():
    result = evaluate(load_attempt(ROOT / "examples" / "good_attempt.json"))
    assert result.grade == "A"
    assert result.score >= 90
    assert result.findings == []


def test_missing_verification_is_critical():
    result = evaluate(Attempt(task_id="x", goal="do x", changed_files=["a.py"]))
    assert any(finding.code == "CAW201" for finding in result.findings)
    assert result.score < 80


def test_failed_verification_and_eval_are_critical():
    result = evaluate(load_attempt(ROOT / "examples" / "risky_attempt.json"))
    codes = {finding.code for finding in result.findings}
    assert "CAW202" in codes
    assert "CAW301" in codes
    assert result.grade == "F"


def test_large_blast_radius_penalized():
    attempt = Attempt(
        task_id="broad",
        goal="change many things",
        changed_files=[f"file_{idx}.py" for idx in range(20)],
        verification=[Verification(command="pytest -q", status="passed")],
        notes="verified",
    )
    result = evaluate(attempt, max_files=3)
    assert any(finding.code == "CAW102" for finding in result.findings)


def test_local_path_in_diff_is_flagged():
    attempt = Attempt(
        task_id="path",
        goal="avoid private path",
        changed_files=["README.md"],
        verification=[Verification(command="pytest -q", status="passed")],
        diff_text="example /" + "Users/example/project",
        notes="verified",
    )
    result = evaluate(attempt)
    assert any(finding.code == "CAW304" for finding in result.findings)


def test_attempt_round_trip(tmp_path):
    path = tmp_path / "attempt.json"
    path.write_text(
        json.dumps(
            {
                "task_id": "x",
                "goal": "g",
                "changed_files": ["a.py"],
                "verification": [{"command": "pytest -q", "status": "passed"}],
            }
        ),
        encoding="utf-8",
    )
    attempt = load_attempt(path)
    assert attempt.task_id == "x"
    assert attempt.verification[0].status == "passed"
