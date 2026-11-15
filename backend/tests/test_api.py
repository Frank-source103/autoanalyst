"""API REST endpoints and WebSocket protocol tests."""

import io
import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from backend.app.core.event_store import event_store
from backend.app.core.events import make_event
from backend.app.main import app


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Ensure database tables exist before API tests run."""
    await event_store.init_db()


def test_health_endpoint():
    """Verify health endpoint responds with status ok."""
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_valid_csv():
    """Verify uploading a valid CSV file succeeds and returns metadata."""
    client = TestClient(app)
    csv_content = b"category,revenue\nElectronics,1200\nFurniture,800\n"

    response = client.post(
        "/api/upload",
        files={"file": ("sales_data.csv", io.BytesIO(csv_content), "text/csv")},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "sales_data.csv"
    assert data["file_type"] == "csv"
    assert data["size_bytes"] == len(csv_content)
    assert os.path.exists(data["file_path"])


def test_upload_valid_parquet():
    """Verify uploading a parquet file is accepted."""
    client = TestClient(app)
    # Minimal binary mock payload with .parquet extension
    parquet_content = b"PAR1mock_binary_parquet_content"

    response = client.post(
        "/api/upload",
        files={"file": ("dataset.parquet", io.BytesIO(parquet_content), "application/octet-stream")},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "dataset.parquet"
    assert data["file_type"] == "parquet"


def test_upload_invalid_extension_rejected():
    """Verify non-CSV/Parquet extensions are rejected with 400 Bad Request."""
    client = TestClient(app)
    bad_content = b"print('malicious')"

    response = client.post(
        "/api/upload",
        files={"file": ("script.py", io.BytesIO(bad_content), "text/plain")},
    )

    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_upload_empty_file_rejected():
    """Verify empty file is rejected."""
    client = TestClient(app)

    response = client.post(
        "/api/upload",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
    )

    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_rest_run_lifecycle():
    """Verify full REST lifecycle: create, get, pause, resume, abort."""
    client = TestClient(app)

    # 1. Create a dummy dataset
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        f.write(b"colA,colB\n1,2\n")
        dummy_dataset = f.name

    try:
        # 2. Start a run
        create_res = client.post(
            "/api/runs",
            json={
                "user_question": "Analyze dataset revenue",
                "dataset_path": dummy_dataset,
                "review_before_run": True,
            },
        )
        assert create_res.status_code == 201
        run_id = create_res.json()["run_id"]

        # 3. Get run details
        get_res = client.get(f"/api/runs/{run_id}")
        assert get_res.status_code == 200
        detail = get_res.json()
        assert detail["run_id"] == run_id
        assert detail["user_question"] == "Analyze dataset revenue"

        # 4. Pause run
        pause_res = client.post(f"/api/runs/{run_id}/pause")
        assert pause_res.status_code == 200
        assert pause_res.json()["status"] == "pausing"

        # 5. Resume run
        resume_res = client.post(
            f"/api/runs/{run_id}/resume",
            json={"edited_code": "print('User code edit')"},
        )
        assert resume_res.status_code == 200
        assert resume_res.json()["status"] == "resumed"

        # 6. Abort run
        abort_res = client.post(f"/api/runs/{run_id}/abort")
        assert abort_res.status_code == 200
        assert abort_res.json()["status"] == "aborted"

    finally:
        if os.path.exists(dummy_dataset):
            os.remove(dummy_dataset)


@pytest.mark.asyncio
async def test_websocket_monotonic_event_replay():
    """Verify WebSocket connection automatically replays missed events based on last_seq."""
    run_id = "test-ws-replay-run"

    # Pre-populate event store with 5 sequential events
    events = [
        make_event(seq=1, run_id=run_id, event_type="state_transition", data={"to": "planning"}),
        make_event(seq=2, run_id=run_id, event_type="plan", data={"steps": []}),
        make_event(seq=3, run_id=run_id, event_type="thought", data={"thought": "Processing step 1"}),
        make_event(seq=4, run_id=run_id, event_type="code", data={"code": "x = 1"}),
        make_event(seq=5, run_id=run_id, event_type="execution_started", data={"step_id": 1}),
    ]
    await event_store.save_events(events)

    client = TestClient(app)

    # Reconnect asking for events after seq=2
    with client.websocket_connect(f"/ws/runs/{run_id}?last_seq=2") as ws:
        # Client should immediately receive events 3, 4, and 5 in monotonic order
        e3 = ws.receive_json()
        assert e3["seq"] == 3
        assert e3["event_type"] == "thought"

        e4 = ws.receive_json()
        assert e4["seq"] == 4
        assert e4["event_type"] == "code"

        e5 = ws.receive_json()
        assert e5["seq"] == 5
        assert e5["event_type"] == "execution_started"

        # Test heartbeat ping/pong
        ws.send_text('{"type": "ping"}')
        pong = ws.receive_json()
        assert pong.get("type") == "pong"
