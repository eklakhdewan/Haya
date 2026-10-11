"""HINA Orchestrator API Service."""

import asyncio
import inspect
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy import text

from orchestrator.agents.coder import CoderAgent
from orchestrator.agents.device import DeviceAgent
from orchestrator.agents.supervisor import Supervisor
from orchestrator.core.auth import decode_access_token
from orchestrator.core.config import get_settings
from orchestrator.core.database import create_database_runtime
from orchestrator.core.errors import HinaError
from orchestrator.core.models import (
    APIResponse,
    MemoryCandidate,
    MemoryQueryResponse,
    MemoryRecord,
    MobileIntent,
    SandboxExecuteRequest,
    SandboxExecutionResult,
    SupervisorInput,
    SupervisorOutput,
)
from orchestrator.dashboard import DASHBOARD_HTML
from orchestrator.devices.manager import ActionAuditRecord, DeviceInfo, DeviceManager
from orchestrator.devices.persistent_manager import PersistentDeviceManager
from orchestrator.devices.validator import MobileIntentValidator
from orchestrator.gateway.stt_adapter import MockSTTAdapter
from orchestrator.gateway.tts_adapter import MockTTSAdapter
from orchestrator.gateway.voice_gateway import VoiceGateway
from orchestrator.memory.extractor import MemoryExtractor
from orchestrator.memory.lifecycle import MemoryLifecycleManager
from orchestrator.memory.mock_memory import InMemoryGraphStore, InMemoryVectorStore
from orchestrator.observability import trace_manager
from orchestrator.providers.base import LLMProvider
from orchestrator.providers.gemini import GeminiProvider
from orchestrator.providers.mock_llm import MockLLMProvider
from orchestrator.sandbox.base import SandboxAdapter
from orchestrator.sandbox.e2b_adapter import E2BSandboxAdapter
from orchestrator.tools.builtin import CalculatorTool, TimeTool
from orchestrator.tools.registry import ToolRegistry


@asynccontextmanager
async def app_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and dispose persistent security storage with the application."""
    global device_manager
    original_device_manager = device_manager
    runtime = create_database_runtime()
    if runtime is not None:
        try:
            async with runtime.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
                required_tables = {
                    "security_devices",
                    "security_pending_confirmations",
                    "security_used_nonces",
                    "security_completed_intents",
                    "security_action_audit",
                    "alembic_version",
                }
                existing_tables = await connection.run_sync(
                    lambda sync_connection: set(
                        sqlalchemy_inspect(sync_connection).get_table_names()
                    )
                )
                missing_tables = required_tables - existing_tables
                if missing_tables:
                    raise RuntimeError(
                        "Persistent security schema is not migrated. Run "
                        "'alembic upgrade head' before starting the API. Missing: "
                        + ", ".join(sorted(missing_tables))
                    )
            device_manager = PersistentDeviceManager(
                runtime=runtime,
                validator=MobileIntentValidator(),
            )
            app.state.database_runtime = runtime
        except Exception:
            await runtime.dispose()
            raise
    try:
        yield
    finally:
        if runtime is not None:
            device_manager = original_device_manager
            await runtime.dispose()


app = FastAPI(
    title="Hina Orchestrator",
    version="0.1.0",
    description="Autonomous real-time AI companion orchestrator and agent core",
    lifespan=app_lifespan,
)


@app.exception_handler(HinaError)
async def handle_domain_error(request: Request, exc: HinaError) -> JSONResponse:
    """Map domain authorization/policy errors to stable HTTP responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": {"code": exc.code.value, "message": exc.message, "details": exc.details}
        },
    )


# Application state dependencies
settings = get_settings()


@app.middleware("http")
async def authenticate_http_requests(request: Request, call_next: Any) -> Any:
    """Require a verified bearer JWT on every HTTP route except the liveness endpoint."""
    if request.url.path == "/v1/health" or request.method == "OPTIONS":
        return await call_next(request)
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return JSONResponse(
            status_code=401,
            content={"detail": {"code": "AUTH_REQUIRED", "message": "Bearer token required."}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        request.state.principal = decode_access_token(token.strip())
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )
    return await call_next(request)


def _principal_user_id(request: Request) -> str:
    principal = getattr(request.state, "principal", {})
    user_id = principal.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(status_code=401, detail="Authenticated token has no valid subject.")
    return user_id


def _require_admin(request: Request) -> None:
    if request.state.principal.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator role required.")


# Initialize LLM provider based on settings/environment
llm_provider: LLMProvider
if settings.google_api_key:
    llm_provider = GeminiProvider(api_key=settings.google_api_key, model=settings.llm_model)
else:
    llm_provider = MockLLMProvider()

supervisor = Supervisor(llm_provider=llm_provider)

# Initialize Sandbox adapter
sandbox_adapter: SandboxAdapter
# Runtime API always uses the external sandbox adapter. Tests must inject the mock explicitly.
# Fail closed without E2B credentials rather than execute untrusted code in-process.
sandbox_adapter = E2BSandboxAdapter(api_key=settings.e2b_api_key)

# Initialize Coder Agent
coder_agent = CoderAgent(
    llm_provider=llm_provider,
    sandbox=sandbox_adapter,
    max_repairs=settings.sandbox_max_repairs,
)

# Initialize Memory subsystem
vector_store = InMemoryVectorStore()
graph_store = InMemoryGraphStore()
memory_lifecycle = MemoryLifecycleManager(vector_store=vector_store, graph_store=graph_store)
memory_extractor = MemoryExtractor(llm_provider=llm_provider)

# Initialize Tool registry
tool_registry = ToolRegistry()
tool_registry.register(CalculatorTool())
tool_registry.register(TimeTool())

# Initialize Device subsystem
device_validator = MobileIntentValidator()
device_manager: Any = DeviceManager(validator=device_validator)
device_agent = DeviceAgent(llm_provider=llm_provider)


async def _device_manager_call(method: Any, *args: Any, **kwargs: Any) -> Any:
    """Support synchronous in-memory and asynchronous persistent manager methods."""
    result = method(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


# Initialize Realtime Voice Gateway
stt_adapter = MockSTTAdapter()
tts_adapter = MockTTSAdapter()
voice_gateway = VoiceGateway(
    stt_adapter=stt_adapter,
    tts_adapter=tts_adapter,
    supervisor=supervisor,
    llm_provider=llm_provider,
    tool_registry=tool_registry,
    memory_lifecycle=memory_lifecycle,
)


class Health(BaseModel):
    status: str
    version: str


@app.get("/v1/health", response_model=Health)
async def health() -> Health:
    return Health(status="ok", version="0.1.0")


# --- Developer Dashboard Control Plane ---
@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_view(request: Request) -> HTMLResponse:
    """Serve the developer control plane only to authenticated administrators."""
    _require_admin(request)
    return HTMLResponse(content=DASHBOARD_HTML)


@app.get("/v1/traces", response_model=APIResponse[list[dict[str, Any]]])
async def get_traces(request: Request, limit: int = 50) -> APIResponse[list[dict[str, Any]]]:
    """Retrieve collected traces; trace data is restricted to administrators."""
    _require_admin(request)
    return APIResponse(data=trace_manager.get_traces(limit=max(1, min(limit, 200))))


@app.get("/v1/traces/{trace_id}", response_model=APIResponse[dict[str, Any] | None])
async def get_trace_by_id(trace_id: str, request: Request) -> APIResponse[dict[str, Any] | None]:
    """Retrieve a specific trace; trace data is restricted to administrators."""
    _require_admin(request)
    return APIResponse(data=trace_manager.get_trace(trace_id))


# --- Realtime Voice WebSocket Endpoint ---
@app.websocket("/v1/realtime/ws")
async def realtime_ws(
    websocket: WebSocket, session_id: str | None = None, user_id: str | None = None
) -> None:
    """Bidirectional voice socket authenticated with a short-lived bearer JWT."""
    scheme, _, header_token = websocket.headers.get("authorization", "").partition(" ")
    token = (
        header_token.strip()
        if scheme.lower() == "bearer"
        else websocket.query_params.get("access_token", "")
    )
    try:
        claims = decode_access_token(token)
    except HTTPException:
        await websocket.close(code=4401, reason="Authentication required")
        return
    authenticated_user_id = claims["sub"]
    if user_id is not None and user_id != authenticated_user_id:
        await websocket.close(code=4403, reason="User identity mismatch")
        return
    user_id = authenticated_user_id
    await websocket.accept()
    s_id = session_id or str(uuid4())
    try:
        session = voice_gateway.sessions.get_or_create(s_id, user_id)
    except PermissionError:
        await websocket.close(code=4403, reason="Voice session belongs to another user")
        return

    async def event_sender() -> None:
        try:
            while True:
                event = await session.event_queue.get()
                await websocket.send_json(event.model_dump(mode="json"))
        except Exception:
            pass

    async def audio_sender() -> None:
        try:
            while True:
                chunk = await session.audio_output_queue.get()
                await websocket.send_bytes(chunk)
        except Exception:
            pass

    sender_task1 = asyncio.create_task(event_sender())
    sender_task2 = asyncio.create_task(audio_sender())

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if "bytes" in message and message["bytes"]:
                # Client streamed raw audio frame
                await voice_gateway.handle_audio_chunk(s_id, user_id, message["bytes"])
            elif "text" in message and message["text"]:
                # Client sent text command or simulated turn
                text_content = message["text"].encode("utf-8")
                await voice_gateway.handle_audio_chunk(s_id, user_id, text_content)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        sender_task1.cancel()
        sender_task2.cancel()
        voice_gateway.sessions.remove(s_id)


# --- Supervisor Endpoints ---
@app.post("/v1/supervisor/route", response_model=APIResponse[SupervisorOutput])
async def route_intent(payload: SupervisorInput, request: Request) -> APIResponse[SupervisorOutput]:
    """Route a turn only for the authenticated token subject."""
    if payload.user_id != _principal_user_id(request):
        raise HTTPException(
            status_code=403, detail="user_id must match the authenticated token subject."
        )
    t0 = time.perf_counter()
    trace_manager.start_trace(payload.session_id, "supervisor_route", payload.trace_id)
    try:
        output = await supervisor.route(payload)
        dur_ms = (time.perf_counter() - t0) * 1000
        trace_manager.record_stage(
            payload.trace_id,
            "intent_classification",
            dur_ms,
            {"route": output.route.value, "confidence": output.confidence},
        )
        trace_manager.finish_trace(payload.trace_id, "success")
        return APIResponse(data=output)
    except HinaError as e:
        trace_manager.finish_trace(payload.trace_id, "error", str(e))
        raise HTTPException(
            status_code=e.status_code,
            detail={"code": e.code.value, "message": e.message, "details": e.details},
        )


# --- Tool Endpoints ---
@app.get("/v1/tools", response_model=APIResponse[list[dict[str, Any]]])
async def list_tools() -> APIResponse[list[dict[str, Any]]]:
    """List registered tools and schemas."""
    return APIResponse(data=tool_registry.list_tools())


class ToolExecuteRequest(BaseModel):
    model_config = {"extra": "forbid"}
    tool_name: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(max_length=100)


@app.post("/v1/tools/execute", response_model=APIResponse[dict[str, Any]])
async def execute_tool(
    req: ToolExecuteRequest, request: Request
) -> APIResponse[dict[str, Any]]:
    """Execute a registered tool; this control-plane operation is admin-only."""
    _require_admin(request)
    try:
        result = await tool_registry.execute(req.tool_name, req.payload)
        return APIResponse(data=result)
    except HinaError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"code": e.code.value, "message": e.message, "details": e.details},
        )


# --- Sandbox Endpoints ---
@app.post("/v1/sandbox/execute", response_model=APIResponse[SandboxExecutionResult])
async def execute_sandbox(
    req: SandboxExecuteRequest, request: Request
) -> APIResponse[SandboxExecutionResult]:
    """Execute code in the isolated sandbox; this endpoint is admin-only."""
    _require_admin(request)
    if len(req.code) > 100_000:
        raise HTTPException(status_code=413, detail="Code exceeds the 100 KB limit.")
    try:
        result = await sandbox_adapter.execute(
            code=req.code,
            timeout_ms=req.timeout_ms,
            network=req.network,
        )
        return APIResponse(data=result)
    except HinaError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"code": e.code.value, "message": e.message, "details": e.details},
        )


class CoderTaskRequest(BaseModel):
    task: str = Field(min_length=1, max_length=20_000)
    timeout_ms: int = Field(default=5000, ge=1000, le=60_000)
    network: Literal["enabled", "disabled"] = "disabled"


@app.post("/v1/coder/task", response_model=APIResponse[dict[str, Any]])
async def run_coder_task(
    req: CoderTaskRequest, request: Request
) -> APIResponse[dict[str, Any]]:
    """Run autonomous Coder agent flow; this endpoint is admin-only."""
    _require_admin(request)
    try:
        result = await coder_agent.run(
            task_description=req.task,
            timeout_ms=req.timeout_ms,
            network=req.network,
        )
        return APIResponse(
            data={
                "task": result.task,
                "final_code": result.final_code,
                "execution_result": result.execution_result.model_dump(),
                "repairs_attempted": result.repairs_attempted,
                "success": result.success,
            }
        )
    except HinaError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"code": e.code.value, "message": e.message, "details": e.details},
        )


# --- Memory Endpoints ---
class MemoryQueryApiRequest(BaseModel):
    user_id: str | None = None
    query: str
    top_k: int = 5
    include_graph: bool = True


@app.post("/v1/memory/query", response_model=APIResponse[MemoryQueryResponse])
async def query_memory(
    req: MemoryQueryApiRequest, request: Request
) -> APIResponse[MemoryQueryResponse]:
    """Perform memory retrieval only within the authenticated user's namespace."""
    user_id = _principal_user_id(request)
    if req.user_id is not None and req.user_id != user_id:
        raise HTTPException(status_code=403, detail="Cannot query another user's memory.")
    items = await memory_lifecycle.query(
        user_id=user_id,
        query_text=req.query,
        top_k=req.top_k,
        include_graph=req.include_graph,
    )
    return APIResponse(data=MemoryQueryResponse(items=items))


class MemoryExtractRequest(BaseModel):
    model_config = {"extra": "forbid"}
    session_id: str = Field(min_length=1, max_length=200)
    transcript: list[dict[str, str]] = Field(min_length=1, max_length=100)


class MemoryExtractResponse(BaseModel):
    candidates: list[MemoryCandidate] = Field(default_factory=list)


@app.post("/v1/memory/extract", response_model=APIResponse[MemoryExtractResponse])
async def extract_memory(
    req: MemoryExtractRequest, request: Request
) -> APIResponse[MemoryExtractResponse]:
    """Extract candidate facts from a bounded transcript for the authenticated user."""
    _principal_user_id(request)
    if sum(len(item.get("content", "")) for item in req.transcript) > 50_000:
        raise HTTPException(status_code=413, detail="Transcript exceeds the 50 KB limit.")
    candidates = await memory_extractor.extract(
        transcript=req.transcript,
        turn_id=req.session_id,
    )
    return APIResponse(data=MemoryExtractResponse(candidates=candidates))


class MemoryStoreRequest(BaseModel):
    user_id: str | None = None
    candidate: MemoryCandidate


@app.post("/v1/memory/store", response_model=APIResponse[MemoryRecord])
async def store_memory(req: MemoryStoreRequest, request: Request) -> APIResponse[MemoryRecord]:
    """Persist a memory candidate only in the authenticated user's namespace."""
    user_id = _principal_user_id(request)
    if req.user_id is not None and req.user_id != user_id:
        raise HTTPException(
            status_code=403, detail="Cannot store memory in another user's namespace."
        )
    rec = await memory_lifecycle.store_candidate(user_id=user_id, candidate=req.candidate)
    return APIResponse(data=rec)


@app.delete("/v1/memory/{memory_id}", response_model=APIResponse[dict[str, Any]])
async def delete_memory(
    memory_id: str, request: Request, user_id: str | None = None
) -> APIResponse[dict[str, Any]]:
    """Delete memory only from the authenticated user's namespace."""
    authenticated_user_id = _principal_user_id(request)
    if user_id is not None and user_id != authenticated_user_id:
        raise HTTPException(status_code=403, detail="Cannot delete another user's memory.")
    deleted = await memory_lifecycle.delete_memory(
        user_id=authenticated_user_id, memory_id=memory_id
    )
    return APIResponse(data={"memory_id": memory_id, "deleted": deleted})


# --- Device Endpoints ---
class DeviceRegisterRequest(BaseModel):
    device_id: str
    user_id: str
    name: str = "Android Device"


@app.post("/v1/device/register", response_model=APIResponse[DeviceInfo])
async def register_device(req: DeviceRegisterRequest, request: Request) -> APIResponse[DeviceInfo]:
    """Enroll a mobile device for the authenticated owner only."""
    user_id = _principal_user_id(request)
    if req.user_id != user_id:
        raise HTTPException(
            status_code=403, detail="user_id must match the authenticated token subject."
        )
    info = await _device_manager_call(
        device_manager.register_device, device_id=req.device_id, user_id=user_id, name=req.name
    )
    return APIResponse(data=info)


class DeviceRevokeRequest(BaseModel):
    device_id: str


@app.post("/v1/device/revoke", response_model=APIResponse[dict[str, bool]])
async def revoke_device(req: DeviceRevokeRequest, request: Request) -> APIResponse[dict[str, bool]]:
    """Revoke only a device owned by the authenticated user."""
    revoked = await _device_manager_call(
        device_manager.revoke_device, req.device_id, user_id=_principal_user_id(request)
    )
    return APIResponse(data={"revoked": revoked})


@app.post("/v1/device/actions", response_model=APIResponse[dict[str, Any]])
async def submit_device_action(
    intent: MobileIntent, request: Request
) -> APIResponse[dict[str, Any]]:
    """Execute or request approval for an intent owned by the authenticated user."""
    try:
        result = await device_manager.execute_intent(
            intent=intent, user_id=_principal_user_id(request)
        )
        return APIResponse(data=result)
    except HinaError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"code": e.code.value, "message": e.message, "details": e.details},
        )


class DeviceConfirmRequest(BaseModel):
    intent_id: str
    confirmation_token: str


@app.post("/v1/device/confirm", response_model=APIResponse[dict[str, bool]])
async def confirm_device_action(
    req: DeviceConfirmRequest, request: Request
) -> APIResponse[dict[str, bool]]:
    """Approve a pending action only as its authenticated owner."""
    confirmed = await _device_manager_call(
        device_manager.confirm_action,
        req.intent_id,
        req.confirmation_token,
        user_id=_principal_user_id(request),
    )
    if not confirmed:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "POLICY_DENIED",
                "message": "Invalid, expired, or unauthorized confirmation token.",
            },
        )
    return APIResponse(data={"confirmed": True})


@app.get("/v1/device/audit", response_model=APIResponse[list[ActionAuditRecord]])
async def get_device_audit(
    request: Request, device_id: str | None = None
) -> APIResponse[list[ActionAuditRecord]]:
    """Retrieve audit records for the authenticated user only."""
    user_id = _principal_user_id(request)
    if device_id is not None and not await _device_manager_call(
        device_manager.owns_device, device_id, user_id=user_id
    ):
        raise HTTPException(
            status_code=403, detail="Cannot inspect another user's device audit trail."
        )
    audit_trail = await _device_manager_call(
        device_manager.get_audit_trail, device_id=device_id, user_id=user_id
    )
    return APIResponse(data=audit_trail)
