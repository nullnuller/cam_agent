import json
from pathlib import Path

from fastapi.testclient import TestClient

from cam_agent.ui.api import create_ui_api
from cam_agent.ui.history import AuditLogHistoricalRunLoader


def _write_sample_audit(path: Path) -> None:
    record = {
        "timestamp": "2025-01-01T00:00:00Z",
        "user_id": "demo",
        "session_id": "session-1",
        "question": "What is APP6?",
        "action": "allow",
        "raw_model": {"model": "test", "prompt": "prompt", "text": "response"},
        "final_text": "response",
    }
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def test_list_runs(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    _write_sample_audit(audit_path)
    loader = AuditLogHistoricalRunLoader(path=audit_path)
    client = TestClient(create_ui_api(loader=loader))

    response = client.get("/runs")
    assert response.status_code == 200
    runs = response.json()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "demo-session-1"


def test_get_timeline(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    _write_sample_audit(audit_path)
    loader = AuditLogHistoricalRunLoader(path=audit_path)
    client = TestClient(create_ui_api(loader=loader))

    response = client.get("/runs/demo-session-1/timeline")
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "llm_response"
    assert event["payload"]["source"]["model_id"] == "test"
    assert event["payload"]["pii_redacted_text"] == "response"
