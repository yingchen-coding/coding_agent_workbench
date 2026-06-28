"""Data models for coding-agent attempt evaluation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Verification:
    command: str
    status: str
    notes: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Verification":
        return cls(
            command=str(raw.get("command", "")),
            status=str(raw.get("status", "")),
            notes=str(raw.get("notes", "")),
        )


@dataclass(frozen=True)
class Attempt:
    task_id: str
    goal: str
    changed_files: list[str] = field(default_factory=list)
    verification: list[Verification] = field(default_factory=list)
    diff_text: str = ""
    commit_message: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Attempt":
        verification = raw.get("verification", [])
        if not isinstance(verification, list):
            raise ValueError("verification must be a list")
        changed_files = raw.get("changed_files", [])
        if not isinstance(changed_files, list):
            raise ValueError("changed_files must be a list")
        return cls(
            task_id=str(raw.get("task_id", "")),
            goal=str(raw.get("goal", "")),
            changed_files=[str(item) for item in changed_files],
            verification=[Verification.from_dict(item) for item in verification],
            diff_text=str(raw.get("diff_text", "")),
            commit_message=str(raw.get("commit_message", "")),
            notes=str(raw.get("notes", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "changed_files": self.changed_files,
            "verification": [item.__dict__ for item in self.verification],
            "diff_text": self.diff_text,
            "commit_message": self.commit_message,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str
    fix: str


@dataclass(frozen=True)
class Evaluation:
    score: int
    grade: str
    findings: list[Finding]
    attempt: Attempt

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "grade": self.grade,
            "findings": [item.__dict__ for item in self.findings],
            "attempt": self.attempt.to_dict(),
        }
