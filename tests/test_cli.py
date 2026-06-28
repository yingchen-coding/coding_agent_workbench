import json

from coding_agent_workbench.cli import main


def test_init_attempt_writes_template(tmp_path, capsys):
    out = tmp_path / "attempt.json"
    assert main(["init-attempt", "--task-id", "demo", "--out", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["task_id"] == "demo"
    assert str(out) in capsys.readouterr().out


def test_evaluate_table_output(capsys):
    code = main(["evaluate", "examples/good_attempt.json", "--format", "table", "--fail-under", "90"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Grade: A" in out


def test_fail_under_returns_nonzero(capsys):
    code = main(["evaluate", "examples/risky_attempt.json", "--fail-under", "90"])
    assert code == 1
    assert "below threshold" in capsys.readouterr().err
