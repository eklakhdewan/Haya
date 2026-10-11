"""Failure-mode tests for E2B adapter boundaries."""

import sys
from types import SimpleNamespace

import pytest

from orchestrator.core.errors import ProviderUnavailableError
from orchestrator.core.models import SandboxExecutionResult
from orchestrator.sandbox.e2b_adapter import E2BSandboxAdapter


@pytest.mark.asyncio
async def test_missing_e2b_sdk_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "e2b_code_interpreter", None)
    adapter = E2BSandboxAdapter(api_key="configured-test-key")
    with pytest.raises(ProviderUnavailableError, match="install e2b-code-interpreter"):
        await adapter.execute("print(1 + 1)", timeout_ms=3000, network="disabled")


@pytest.mark.asyncio
async def test_provider_outage_returns_error_without_local_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = E2BSandboxAdapter(api_key="configured-test-key")

    def outage(code: str, timeout_ms: int, started: float) -> SandboxExecutionResult:
        raise ConnectionError("provider unavailable")

    monkeypatch.setattr(adapter, "_execute_isolated", outage)
    result = await adapter.execute("print(1 + 1)", timeout_ms=3000, network="disabled")
    assert result.status == "error"
    assert "Sandbox provider failed" in result.stderr


@pytest.mark.asyncio
async def test_provider_timeout_is_reported_as_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = E2BSandboxAdapter(api_key="configured-test-key")

    def timeout(code: str, timeout_ms: int, started: float) -> SandboxExecutionResult:
        raise TimeoutError("provider timed out")

    monkeypatch.setattr(adapter, "_execute_isolated", timeout)
    result = await adapter.execute("print(1 + 1)", timeout_ms=3000, network="disabled")
    assert result.status == "timeout"
    assert result.exit_code == 124


@pytest.mark.asyncio
async def test_malformed_provider_result_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = E2BSandboxAdapter(api_key="configured-test-key")

    def malformed(code: str, timeout_ms: int, started: float) -> object:
        return SimpleNamespace(stdout="unexpected")

    monkeypatch.setattr(adapter, "_execute_isolated", malformed)
    with pytest.raises(ProviderUnavailableError, match="invalid result"):
        await adapter.execute("print(1 + 1)", timeout_ms=3000, network="disabled")


@pytest.mark.asyncio
async def test_sandbox_output_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = E2BSandboxAdapter(api_key="configured-test-key")

    def oversized(code: str, timeout_ms: int, started: float) -> SandboxExecutionResult:
        return SandboxExecutionResult(
            status="success",
            stdout="x" * 110_000,
            stderr="y" * 30_000,
        )

    monkeypatch.setattr(adapter, "_execute_isolated", oversized)
    result = await adapter.execute("print(1 + 1)", timeout_ms=3000, network="disabled")
    assert len(result.stdout) == 100_000
    assert len(result.stderr) == 20_000
