"""Input/output helpers."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .models import Attempt, Evaluation


def load_attempt(path: Path) -> Attempt:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("attempt file must contain a JSON object")
    return Attempt.from_dict(data)


def save_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    # atomic write: a same-directory temp + os.replace so an interrupted run never leaves a partial
    # file where a valid one is expected
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def render_table(evaluation: Evaluation) -> str:
    lines = [
        f"Task: {evaluation.attempt.task_id or '-'}",
        f"Grade: {evaluation.grade} ({evaluation.score}/100)",
        "",
        "| Severity | Code | Finding | Fix |",
        "|---|---|---|---|",
    ]
    if not evaluation.findings:
        lines.append("| ok | - | No findings | - |")
    for finding in evaluation.findings:
        lines.append(f"| {finding.severity} | {finding.code} | {finding.message} | {finding.fix} |")
    return "\n".join(lines) + "\n"


def blank_attempt(task_id: str) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "goal": "",
        "changed_files": [],
        "verification": [{"command": "", "status": "", "notes": ""}],
        "diff_text": "",
        "commit_message": "",
        "notes": "",
    }
