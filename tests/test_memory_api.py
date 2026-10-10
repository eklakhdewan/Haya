"""Integration tests for Memory API endpoints."""

from fastapi.testclient import TestClient

from orchestrator.main import app
from tests.security_helpers import auth_headers

client = TestClient(app, headers=auth_headers("api-user-test", "user"))


def test_api_memory_lifecycle_flow() -> None:
    # 1. Extract candidates from transcript
    extract_req = {
        "session_id": "session-api-test",
        "transcript": [
            {"role": "user", "content": "I am working on HINA right now."},
        ],
    }
    extract_resp = client.post("/v1/memory/extract", json=extract_req)
    assert extract_resp.status_code == 200
    candidates = extract_resp.json()["data"]["candidates"]
    assert len(candidates) >= 1
    cand = candidates[0]
    assert cand["object"] == "HINA"

    # 2. Store candidate
    store_req = {
        "user_id": "api-user-test",
        "candidate": cand,
    }
    store_resp = client.post("/v1/memory/store", json=store_req)
    assert store_resp.status_code == 200
    stored_rec = store_resp.json()["data"]
    memory_id = stored_rec["id"]
    assert memory_id is not None

    # 3. Query memory
    query_req = {
        "user_id": "api-user-test",
        "query": "HINA project",
        "top_k": 5,
        "include_graph": True,
    }
    query_resp = client.post("/v1/memory/query", json=query_req)
    assert query_resp.status_code == 200
    items = query_resp.json()["data"]["items"]
    assert len(items) >= 1
    assert items[0]["memory_id"] == memory_id

    # 4. Delete memory
    del_resp = client.delete(f"/v1/memory/{memory_id}?user_id=api-user-test")
    assert del_resp.status_code == 200
    assert del_resp.json()["data"]["deleted"] is True

    # 5. Verify deleted from query
    query_resp_2 = client.post("/v1/memory/query", json=query_req)
    items_after = query_resp_2.json()["data"]["items"]
    assert not any(i["memory_id"] == memory_id for i in items_after)
