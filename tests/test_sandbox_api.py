"""Integration tests for sandbox and coder API endpoints."""

from fastapi.testclient import TestClient
from orchestrator.main import app, llm_provider
from orchestrator.providers.mock_llm import MockLLMProvider

client = TestClient(app)


def test_api_sandbox_execute_success() -> None:
    req = {
        "language": "python",
        "code": "print(2 + 2)",
        "timeout_ms": 3000,
        "network": "disabled",
    }
    response = client.post("/v1/sandbox/execute", json=req)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "success"
    assert data["stdout"].strip() == "4"
    assert data["exit_code"] == 0


def test_api_sandbox_execute_policy_violation() -> None:
    req = {
        "language": "python",
        "code": "import subprocess\nsubprocess.call(['whoami'])",
        "timeout_ms": 3000,
        "network": "disabled",
    }
    response = client.post("/v1/sandbox/execute", json=req)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "error"
    assert "Prohibited import detected: 'subprocess'" in data["stderr"]


def test_api_coder_task_endpoint() -> None:
    if isinstance(llm_provider, MockLLMProvider):
        llm_provider.register_text_response(
            "square",
            "```python\ndef square(x): return x * x\nprint(square(4))\n```",
        )

    response = client.post(
        "/v1/coder/task",
        json={"task": "Write square function", "timeout_ms": 3000, "network": "disabled"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["success"] is True
    assert "square" in data["final_code"]
    assert data["execution_result"]["stdout"].strip() == "16"
