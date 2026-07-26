import json

import pytest

from coding_agent_workbench.context import audit_context, render_context_markdown


def _row(role, content, **extra):
    return json.dumps(
        {
            "type": role,
            "message": {"role": role, "content": content},
            **extra,
        }
    )


def _text(value):
    return [{"type": "text", "text": value}]


def _build_corpus(root, sessions=40):
    root.mkdir()
    for index in range(sessions):
        private_a = f"private_file_{index}"
        private_b = f"--private-flag-{index}"
        events = [
            _row("user", _text(f"Update {private_a} with {private_b}.")),
            _row(
                "assistant",
                [
                    {
                        "type": "tool_use",
                        "name": "read_file",
                        "input": {"path": " ".join(f"noise_{index}_{n}" for n in range(60))},
                    }
                ],
            ),
            _row("user", _text("synthetic summary"), isCompactSummary=True),
            _row("assistant", _text(" ".join(f"noise_a_{index}_{n}" for n in range(60)))),
            _row("assistant", _text(" ".join(f"noise_b_{index}_{n}" for n in range(60)))),
            _row("assistant", _text(f"Updated {private_a} with {private_b}.")),
        ]
        (root / f"session-{index}.jsonl").write_text(
            "\n".join(events) + "\n",
            encoding="utf-8",
        )


def test_context_audit_is_clustered_private_and_reproducible(tmp_path):
    corpus = tmp_path / "corpus"
    _build_corpus(corpus)

    first = audit_context(corpus, budget=128)
    second = audit_context(corpus, budget=128)

    assert first == second
    assert first["verdict"] == "LEXICAL_PROXY_SUPPORTED"
    assert first["source"]["eligible_cases"] == 40
    assert first["metrics"]["sessions"] == 40
    assert first["metrics"]["session_balanced_delta"] > 0
    assert first["metrics"]["no_oversized_message"]["status"] == "SUPPORTED"
    assert first["metrics"]["no_oversized_message"]["session_balanced_delta"] > 0
    serialized = json.dumps(first)
    assert "private_file_0" not in serialized
    assert "--private-flag-0" not in serialized
    assert str(corpus) not in serialized


def test_context_audit_reports_malformed_input(tmp_path):
    corpus = tmp_path / "corpus"
    _build_corpus(corpus)
    path = corpus / "session-0.jsonl"
    path.write_bytes(path.read_bytes() + b"{invalid json\n\xff\n[]\n")

    report = audit_context(corpus, budget=128)

    assert report["source"]["invalid_json_lines"] == 1
    assert report["source"]["invalid_utf8_lines"] == 1
    assert report["source"]["invalid_record_lines"] == 1


def test_context_audit_separates_human_text_from_tool_results(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    for index in range(30):
        anchor_a = f"mixed_file_{index}"
        anchor_b = f"--mixed-flag-{index}"
        events = [
            _row(
                "user",
                [
                    {"type": "text", "text": f"Update {anchor_a} with {anchor_b}."},
                    {
                        "type": "tool_result",
                        "content": "tool_result_anchor must not become a request anchor",
                    },
                ],
            ),
            _row("assistant", _text(" ".join(f"noise_{index}_{n}" for n in range(130)))),
            _row("assistant", _text(f"Updated {anchor_a} with {anchor_b}.")),
        ]
        (corpus / f"mixed-{index}.jsonl").write_text(
            "\n".join(events) + "\n",
            encoding="utf-8",
        )

    report = audit_context(corpus, budget=128)

    assert report["source"]["eligible_cases"] == 30
    assert report["verdict"] == "LEXICAL_PROXY_NOT_SUPPORTED"


def test_context_audit_rejects_small_or_invalid_corpora(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="no JSONL"):
        audit_context(empty)

    corpus = tmp_path / "small"
    _build_corpus(corpus, sessions=2)
    with pytest.raises(ValueError, match="insufficient eligible cases"):
        audit_context(corpus, budget=128)

    with pytest.raises(ValueError, match="at least 32"):
        audit_context(corpus, budget=16)


def test_context_markdown_keeps_claim_boundary(tmp_path):
    corpus = tmp_path / "corpus"
    _build_corpus(corpus)
    report = audit_context(corpus, budget=128)
    rendered = render_context_markdown(report)
    assert "Context retention audit" in rendered
    assert "not task success" in rendered
