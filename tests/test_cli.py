import json
from pathlib import Path

from coding_agent_workbench.cli import main

_EXAMPLES = Path(__file__).parents[1] / "examples"


def test_init_attempt_writes_template(tmp_path, capsys):
    out = tmp_path / "attempt.json"
    assert main(["init-attempt", "--task-id", "demo", "--out", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["task_id"] == "demo"
    assert str(out) in capsys.readouterr().out


def test_evaluate_table_output(capsys):
    code = main(["evaluate", str(_EXAMPLES / "good_attempt.json"), "--format", "table", "--fail-under", "90"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Grade: A" in out


def test_fail_under_returns_nonzero(capsys):
    code = main(["evaluate", str(_EXAMPLES / "risky_attempt.json"), "--fail-under", "90"])
    assert code == 1
    assert "below threshold" in capsys.readouterr().err


def test_context_audit_cli(tmp_path, capsys):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    for index in range(30):
        anchor_a = f"target_file_{index}"
        anchor_b = f"--target-flag-{index}"
        rows = [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": f"Update {anchor_a} with {anchor_b}.",
                },
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": " ".join(f"noise_a_{index}_{n}" for n in range(40)),
                },
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": " ".join(f"noise_b_{index}_{n}" for n in range(40)),
                },
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": f"Updated {anchor_a} with {anchor_b}.",
                },
            },
        ]
        (corpus / f"{index}.jsonl").write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n",
            encoding="utf-8",
        )

    assert main(["context-audit", str(corpus), "--budget", "64"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["source"]["eligible_cases"] == 30
    assert report["verdict"] == "LEXICAL_PROXY_SUPPORTED"
