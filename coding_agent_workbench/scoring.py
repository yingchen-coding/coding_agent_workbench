"""Deterministic scoring for coding-agent attempts."""
from __future__ import annotations

import re

from .models import Attempt, Evaluation, Finding


RISK_PATTERNS = [
    ("CAW301", "critical", re.compile(r"\b(eval|exec)\s*\("), "Remove dynamic execution."),
    ("CAW302", "critical", re.compile(r"\brm\s+-rf\b"), "Remove destructive shell operations."),
    ("CAW303", "critical", re.compile(r"\b(ghp_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]{20,})\b"), "Remove and rotate committed secrets."),
    (
        "CAW304",
        "major",
        re.compile("/" + r"Users/[A-Za-z0-9._-]+|/home/[A-Za-z0-9._-]+"),
        "Replace local paths with neutral placeholders.",
    ),
]

WEAK_COMMIT = re.compile(r"^(fix|update|changes|wip|stuff|misc|work)$", re.IGNORECASE)


def grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def evaluate(attempt: Attempt, *, max_files: int = 8, max_diff_lines: int = 500) -> Evaluation:
    findings: list[Finding] = []
    score = 100

    if not attempt.task_id:
        findings.append(Finding("CAW001", "major", "Missing task_id.", "Set a stable task_id."))
        score -= 12
    if not attempt.goal:
        findings.append(Finding("CAW002", "major", "Missing task goal.", "State the intended behavior change."))
        score -= 12
    if not attempt.changed_files:
        findings.append(Finding("CAW101", "major", "No changed files recorded.", "Record changed_files."))
        score -= 15
    if len(attempt.changed_files) > max_files:
        findings.append(
            Finding(
                "CAW102",
                "major",
                f"Large blast radius: {len(attempt.changed_files)} files changed.",
                "Split the task or justify the broad diff.",
            )
        )
        score -= min(20, len(attempt.changed_files) - max_files)

    if not attempt.verification:
        findings.append(Finding("CAW201", "critical", "No verification commands recorded.", "Run and record tests or checks."))
        score -= 30
    else:
        failed = [item for item in attempt.verification if item.status.lower() not in {"passed", "pass", "ok"}]
        if failed:
            findings.append(
                Finding(
                    "CAW202",
                    "critical",
                    f"{len(failed)} verification command(s) did not pass.",
                    "Fix the implementation and rerun verification.",
                )
            )
            score -= 25

    diff_lines = len(attempt.diff_text.splitlines())
    if diff_lines > max_diff_lines:
        findings.append(
            Finding(
                "CAW103",
                "minor",
                f"Large diff: {diff_lines} lines.",
                "Reduce unrelated changes or split the task.",
            )
        )
        score -= min(10, (diff_lines - max_diff_lines) // 100 + 1)

    for code, severity, pattern, fix in RISK_PATTERNS:
        match = pattern.search(attempt.diff_text)
        if match:
            findings.append(Finding(code, severity, f"Risky diff pattern found: {match.group(0)}", fix))
            score -= 35 if severity == "critical" else 18

    message = attempt.commit_message.strip()
    if not message:
        findings.append(Finding("CAW401", "minor", "No commit message recorded.", "Record the intended commit message."))
        score -= 5
    elif WEAK_COMMIT.match(message):
        findings.append(Finding("CAW402", "minor", f"Weak commit message: {message}", "Use a functional summary."))
        score -= 5

    if not attempt.notes.strip():
        findings.append(Finding("CAW501", "minor", "No evidence notes recorded.", "Add a short evidence summary."))
        score -= 5

    score = max(0, min(100, score))
    return Evaluation(score=score, grade=grade(score), findings=findings, attempt=attempt)


def check_catalog() -> list[dict[str, str]]:
    return [
        {"code": "CAW001", "severity": "major", "meaning": "task id is missing"},
        {"code": "CAW101", "severity": "major", "meaning": "changed files are missing or too broad"},
        {"code": "CAW201", "severity": "critical", "meaning": "verification is missing"},
        {"code": "CAW202", "severity": "critical", "meaning": "verification failed"},
        {"code": "CAW301-304", "severity": "critical/major", "meaning": "risky or private diff content"},
        {"code": "CAW401-402", "severity": "minor", "meaning": "commit message is missing or weak"},
        {"code": "CAW501", "severity": "minor", "meaning": "evidence notes are missing"},
    ]
