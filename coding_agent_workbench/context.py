"""Privacy-safe context-retention audits for coding-agent transcripts."""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from collections import Counter, deque
from pathlib import Path
from typing import Iterator

ANCHOR_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:--[a-z][a-z0-9-]{2,}|"
    r"[A-Za-z][A-Za-z0-9]*(?:[_-][A-Za-z0-9]+)+|"
    r"[A-Za-z][A-Za-z0-9]{7,}|"
    r"\d{2,}(?:\.\d+)?%?)(?![A-Za-z0-9_])"
)
STOP_ANCHORS = {
    "assistant",
    "analysis",
    "commentary",
    "developer",
    "function",
    "important",
    "message",
    "permission",
    "response",
    "result",
    "system",
    "thinking",
    "tool_result",
    "tool_use",
}


def _content_text(content: object) -> tuple[str, str, str]:
    if isinstance(content, str):
        return content, content, ""
    if not isinstance(content, list):
        return "", "", ""
    chunks: list[str] = []
    plain_chunks: list[str] = []
    tool_chunks: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type", ""))
        if block_type == "text" and isinstance(block.get("text"), str):
            chunks.append(block["text"])
            plain_chunks.append(block["text"])
        elif block_type == "tool_result":
            value = block.get("content")
            if isinstance(value, str):
                chunks.append(value)
                tool_chunks.append(value)
            elif isinstance(value, list):
                result_chunks = [
                    str(item.get("text", ""))
                    for item in value
                    if isinstance(item, dict) and item.get("type") == "text"
                ]
                chunks.extend(result_chunks)
                tool_chunks.extend(result_chunks)
        elif block_type == "tool_use":
            tool_text = (
                f"{block.get('name', 'tool')} "
                + json.dumps(
                    block.get("input", {}),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            chunks.append(tool_text)
            tool_chunks.append(tool_text)
    return "\n".join(chunks), "\n".join(plain_chunks), "\n".join(tool_chunks)


def _messages(path: Path, parse_stats: Counter[str]) -> Iterator[dict[str, object]]:
    with path.open("rb") as handle:
        for raw_line in handle:
            try:
                line = raw_line.decode("utf-8")
            except UnicodeDecodeError:
                parse_stats["invalid_utf8_lines"] += 1
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                parse_stats["invalid_json_lines"] += 1
                continue
            if not isinstance(row, dict):
                parse_stats["invalid_record_lines"] += 1
                continue
            row_type = row.get("type")
            message = row.get("message")
            if row_type not in {"user", "assistant"} or not isinstance(message, dict):
                continue
            role = str(message.get("role") or row_type)
            text, request_text, tool_text = _content_text(message.get("content"))
            if not text.strip():
                continue
            human_user = (
                role == "user"
                and bool(request_text.strip())
                and not row.get("isMeta")
                and not row.get("isSidechain")
                and not row.get("isCompactSummary")
                and not row.get("isVisibleInTranscriptOnly")
                and not row.get("toolUseResult")
                and not row.get("sourceToolAssistantUUID")
            )
            yield {
                "role": role,
                "text": text,
                "human_user": human_user,
                "plain_text": bool(request_text.strip()),
                "request_text": request_text,
                "tool_text": tool_text,
            }


def _tokens(text: str) -> list[str]:
    return re.findall(r"\S+", text)


def _anchors(text: str) -> set[str]:
    return {
        item.lower()
        for item in ANCHOR_RE.findall(text)
        if item.lower() not in STOP_ANCHORS and len(item) >= 4
    }


def _lifecycle_context(
    current_request: list[str],
    other_tail: deque[str],
    budget: int,
) -> list[str]:
    if len(current_request) >= budget:
        return current_request[:budget]
    remaining = budget - len(current_request)
    return current_request + list(other_tail)[-remaining:]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _session_means(records: list[dict[str, object]], field: str) -> list[float]:
    grouped: dict[str, list[float]] = {}
    for record in records:
        grouped.setdefault(str(record["session"]), []).append(float(record[field]))
    return [_mean(values) for values in grouped.values()]


def _bootstrap_ci(values: list[float], seed: int) -> list[float] | None:
    if not values:
        return None
    rng = random.Random(seed)
    estimates = sorted(
        _mean([values[rng.randrange(len(values))] for _ in values])
        for _ in range(2_000)
    )
    return [round(estimates[49], 6), round(estimates[1949], 6)]


def _sign_test(positive: int, negative: int) -> float:
    sample = positive + negative
    if not sample:
        return 1.0
    boundary = min(positive, negative)
    probability = sum(math.comb(sample, i) for i in range(boundary + 1)) / (2**sample)
    return round(min(1.0, 2 * probability), 10)


def _fingerprint(paths: list[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def audit_context(corpus: Path, budget: int = 256) -> dict[str, object]:
    if budget < 32:
        raise ValueError("budget must be at least 32 whitespace tokens")
    root = corpus.expanduser().resolve()
    paths = sorted(root.rglob("*.jsonl"))
    if not paths:
        raise ValueError("corpus contains no JSONL transcripts")
    records: list[dict[str, object]] = []
    sessions_used = 0
    parse_stats: Counter[str] = Counter()
    for path in paths:
        active_tokens: list[str] | None = None
        active_anchors: set[str] = set()
        request_recorded = False
        largest_intervening_segment = 0
        full_tail: deque[str] = deque(maxlen=budget)
        other_tail: deque[str] = deque(maxlen=budget)
        context_size = 0
        used_session = False
        for message in _messages(path, parse_stats):
            segment = [f"<{message['role']}>"] + _tokens(str(message["text"]))
            if message["human_user"]:
                active_tokens = (
                    [f"<{message['role']}>"]
                    + _tokens(str(message["request_text"]))
                )[:budget]
                active_anchors = _anchors(str(message["request_text"]))
                request_recorded = False
                largest_intervening_segment = 0
                other_tail = deque(full_tail, maxlen=budget)
                tool_segment = _tokens(str(message["tool_text"]))
                if tool_segment:
                    other_tail.extend(["<user-tool>", *tool_segment])
                full_tail.extend(segment)
                context_size += len(segment)
                continue
            is_text_response = message["role"] == "assistant" and message["plain_text"]
            if not is_text_response or active_tokens is None:
                full_tail.extend(segment)
                other_tail.extend(segment)
                context_size += len(segment)
                largest_intervening_segment = max(largest_intervening_segment, len(segment))
                continue
            target = _anchors(str(message["text"])) & active_anchors
            if len(target) >= 2 and context_size > budget and not request_recorded:
                baseline = _anchors(" ".join(full_tail))
                lifecycle = _anchors(
                    " ".join(_lifecycle_context(active_tokens, other_tail, budget))
                )
                base_recall = len(target & baseline) / len(target)
                lifecycle_recall = len(target & lifecycle) / len(target)
                records.append(
                    {
                        "session": str(path.relative_to(root)),
                        "baseline": base_recall,
                        "lifecycle": lifecycle_recall,
                        "delta": lifecycle_recall - base_recall,
                        "clean": largest_intervening_segment <= budget,
                    }
                )
                request_recorded = True
                used_session = True
            full_tail.extend(segment)
            other_tail.extend(segment)
            context_size += len(segment)
            largest_intervening_segment = max(largest_intervening_segment, len(segment))
        sessions_used += int(used_session)
    if len(records) < 30:
        raise ValueError(f"insufficient eligible cases: {len(records)}; need at least 30")

    session_deltas = _session_means(records, "delta")
    clean_records = [record for record in records if record["clean"]]
    clean_deltas = _session_means(clean_records, "delta")
    wins = sum(delta > 0 for delta in session_deltas)
    losses = sum(delta < 0 for delta in session_deltas)
    clean_wins = sum(delta > 0 for delta in clean_deltas)
    clean_losses = sum(delta < 0 for delta in clean_deltas)
    session_counts = Counter(str(record["session"]) for record in records)
    clean_session_count = len({str(record["session"]) for record in clean_records})
    ci = _bootstrap_ci(session_deltas, 20260725 + budget)
    clean_ci = _bootstrap_ci(clean_deltas, 20261725 + budget)
    delta = _mean(session_deltas)
    clean_delta = _mean(clean_deltas) if clean_deltas else None
    clean_supported = (
        len(clean_records) >= 30
        and clean_session_count >= 20
        and clean_ci is not None
        and clean_ci[0] > 0
        and _sign_test(clean_wins, clean_losses) < 0.05
    )
    verdict = (
        "LEXICAL_PROXY_SUPPORTED"
        if (
            delta > 0
            and ci is not None
            and ci[0] > 0
            and _sign_test(wins, losses) < 0.01
            and clean_supported
        )
        else "LEXICAL_PROXY_NOT_SUPPORTED"
    )
    return {
        "schema_version": "1.0",
        "verdict": verdict,
        "source": {
            "files_scanned": len(paths),
            "sessions_used": sessions_used,
            "eligible_cases": len(records),
            "fingerprint_sha256": _fingerprint(paths, root),
            "privacy": "aggregate-only; no transcript text, identifiers, or paths are emitted",
            "invalid_utf8_lines": parse_stats["invalid_utf8_lines"],
            "invalid_json_lines": parse_stats["invalid_json_lines"],
            "invalid_record_lines": parse_stats["invalid_record_lines"],
        },
        "budget_whitespace_tokens": budget,
        "baseline": "raw tail truncation over text, tool-call, and tool-result events",
        "treatment": "active human request first, then recent non-request context",
        "anchor_heuristic": (
            "case-insensitive exact lexical anchors: flags, code-like compound tokens, long "
            "alphanumeric terms, and numeric strings"
        ),
        "metrics": {
            "sessions": len(session_counts),
            "max_cases_from_one_session": max(session_counts.values()),
            "session_balanced_baseline_recall": round(
                _mean(_session_means(records, "baseline")), 6
            ),
            "session_balanced_lifecycle_recall": round(
                _mean(_session_means(records, "lifecycle")), 6
            ),
            "session_balanced_delta": round(delta, 6),
            "session_cluster_bootstrap_95ci": ci,
            "session_wins": wins,
            "session_losses": losses,
            "session_ties": sum(value == 0 for value in session_deltas),
            "session_sign_test_two_sided_p": _sign_test(wins, losses),
            "no_oversized_message": {
                "status": (
                    "SUPPORTED"
                    if clean_supported
                    else "INSUFFICIENT_OR_NOT_SUPPORTED"
                ),
                "cases": len(clean_records),
                "sessions": clean_session_count,
                "session_balanced_delta": (
                    round(clean_delta, 6) if clean_delta is not None else None
                ),
                "session_cluster_bootstrap_95ci": clean_ci,
                "session_sign_test_two_sided_p": _sign_test(
                    clean_wins, clean_losses
                ),
            },
        },
        "claim_boundary": (
            "Outcome-conditioned exact lexical retention only; not task success, answer quality, "
            "semantic retention, causality, or cross-user generalization."
        ),
    }


def render_context_markdown(report: dict[str, object]) -> str:
    source = report["source"]
    metrics = report["metrics"]
    clean = metrics["no_oversized_message"]
    clean_delta = clean["session_balanced_delta"]
    clean_ci = clean["session_cluster_bootstrap_95ci"]
    clean_summary = (
        f"{clean_delta:.3f} (95% CI {clean_ci})"
        if clean_delta is not None and clean_ci is not None
        else "not available"
    )
    return (
        f"# Context retention audit\n\nVerdict: **{report['verdict']}**\n\n"
        f"- Files scanned: {source['files_scanned']}\n"
        f"- Sessions: {metrics['sessions']}\n"
        f"- Eligible cases: {source['eligible_cases']}\n"
        f"- Baseline recall: {metrics['session_balanced_baseline_recall']:.3f}\n"
        f"- Lifecycle recall: {metrics['session_balanced_lifecycle_recall']:.3f}\n"
        f"- Delta: {metrics['session_balanced_delta']:.3f} "
        f"(95% CI {metrics['session_cluster_bootstrap_95ci']})\n"
        f"- Clean stratum: {clean['cases']} cases across {clean['sessions']} sessions; "
        f"delta {clean_summary}; status {clean['status']}\n"
        f"- Invalid input lines: UTF-8={source['invalid_utf8_lines']}, "
        f"JSON={source['invalid_json_lines']}, records={source['invalid_record_lines']}\n\n"
        f"Boundary: {report['claim_boundary']}\n"
    )
