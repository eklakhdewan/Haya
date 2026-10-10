"""HINA Orchestrator API Service."""

import asyncio
import time
from typing import Any
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from orchestrator.agents.coder import CoderAgent
from orchestrator.agents.device import DeviceAgent
from orchestrator.agents.supervisor import Supervisor
from orchestrator.core.auth import decode_access_token
from orchestrator.core.config import get_settings
from orchestrator.core.errors import HinaError
from orchestrator.dashboard import DASHBOARD_HTML
from orchestrator.observability import trace_manager
from orchestrator.core.models import (
    APIResponse,
    MemoryCandidate,
    MemoryQueryItem,
    MemoryQueryRequest,
    MemoryQueryResponse,
    MemoryRecord,
    MobileIntent,
    SandboxExecuteRequest,
    SandboxExecutionResult,
    SupervisorInput,
    SupervisorOutput,
)
from orchestrator.devices.manager import ActionAuditRecord, DeviceInfo, DeviceManager
from orchestrator.devices.validator import MobileIntentValidator
from orchestrator.gateway.events import RealtimeEventType
from orchestrator.gateway.stt_adapter import MockSTTAdapter
from orchestrator.gateway.tts_adapter import MockTTSAdapter
from orchestrator.gateway.voice_gateway import VoiceGateway
from orchestrator.memory.extractor import MemoryExtractor
from orchestrator.memory.lifecycle import MemoryLifecycleManager
from orchestrator.memory.mock_memory import InMemoryGraphStore, InMemoryVectorStore
from orchestrator.memory.neo4j_adapter import Neo4jGraphAdapter
from orchestrator.memory.qdrant_adapter import QdrantVectorAdapter
from orchestrator.providers.base import LLMProvider
from orchestrator.providers.gemini import GeminiProvider
from orchestrator.providers.mock_llm import MockLLMProvider
from orchestrator.sandbox.base import SandboxAdapter
from orchestrator.sandbox.e2b_adapter import E2BSandboxAdapter
from orchestrator.sandbox.mock_sandbox import MockSandboxAdapter
from orchestrator.tools.builtin import CalculatorTool, TimeTool
from orchestrator.tools.registry import ToolRegistry

app = FastAPI(
    title="Hina Orchestrator",
    version="0.1.0",
    description="Autonomous real-time AI companion orchestrator and agent core",
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
if settings.e2b_api_key:
    sandbox_adapter = E2BSandboxAdapter(api_key=settings.e2b_api_key)
else:
    sandbox_adapter = MockSandboxAdapter()

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
device_manager = DeviceManager(validator=device_validator)
device_agent = DeviceAgent(llm_provider=llm_provider)

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
async def realtime_ws(websocket: WebSocket, session_id: str | None = None, user_id: str | None = None) -> None:
    """Bidirectional voice socket authenticated with a short-lived bearer JWT."""
    scheme, _, header_token = websocket.headers.get("authorization", "").partition(" ")
    token = header_token.strip() if scheme.lower() == "bearer" else websocket.query_params.get("access_token", "")
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
    session = voice_gateway.sessions.get_or_create(s_id, user_id)

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
        raise HTTPException(status_code=403, detail="user_id must match the authenticated token subject.")
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
    tool_name: str
    payload: dict[str, Any]


@app.post("/v1/tools/execute", response_model=APIResponse[dict[str, Any]])
async def execute_tool(req: ToolExecuteRequest) -> APIResponse[dict[str, Any]]:
    """Execute a registered tool with schema validation."""
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
async def execute_sandbox(req: SandboxExecuteRequest) -> APIResponse[SandboxExecutionResult]:
    """Execute code in isolated sandbox per API_SPEC."""
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
    task: str
    timeout_ms: int = 5000
    network: str = "disabled"


@app.post("/v1/coder/task", response_model=APIResponse[dict[str, Any]])
async def run_coder_task(req: CoderTaskRequest) -> APIResponse[dict[str, Any]]:
    """Run autonomous Coder agent flow (generate -> check -> execute -> repair)."""
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
    user_id: str = "default-user"
    query: str
    top_k: int = 5
    include_graph: bool = True


@app.post("/v1/memory/query", response_model=APIResponse[MemoryQueryResponse])
async def query_memory(req: MemoryQueryApiRequest, request: Request) -> APIResponse[MemoryQueryResponse]:
    """Perform memory retrieval only within the authenticated user's namespace."""
    user_id = _principal_user_id(request)
    items = await memory_lifecycle.query(
        user_id=user_id,
        query_text=req.query,
        top_k=req.top_k,
        include_graph=req.include_graph,
    )
    return APIResponse(data=MemoryQueryResponse(items=items))


class MemoryExtractRequest(BaseModel):
    session_id: str
    transcript: list[dict[str, str]]


class MemoryExtractResponse(BaseModel):
    candidates: list[MemoryCandidate] = Field(default_factory=list)


@app.post("/v1/memory/extract", response_model=APIResponse[MemoryExtractResponse])
async def extract_memory(req: MemoryExtractRequest) -> APIResponse[MemoryExtractResponse]:
    """Extract candidate facts from turn transcript per API_SPEC."""
    candidates = await memory_extractor.extract(
        transcript=req.transcript,
        turn_id=req.session_id,
    )
    return APIResponse(data=MemoryExtractResponse(candidates=candidates))


class MemoryStoreRequest(BaseModel):
    user_id: str = "default-user"
    candidate: MemoryCandidate


@app.post("/v1/memory/store", response_model=APIResponse[MemoryRecord])
async def store_memory(req: MemoryStoreRequest, request: Request) -> APIResponse[MemoryRecord]:
    """Persist a memory candidate only in the authenticated user's namespace."""
    user_id = _principal_user_id(request)
    rec = await memory_lifecycle.store_candidate(user_id=user_id, candidate=req.candidate)
    return APIResponse(data=rec)


@app.delete("/v1/memory/{memory_id}", response_model=APIResponse[dict[str, Any]])
async def delete_memory(memory_id: str, request: Request, user_id: str | None = None) -> APIResponse[dict[str, Any]]:
    """Delete memory only from the authenticated user's namespace."""
    authenticated_user_id = _principal_user_id(request)
    if user_id is not None and user_id != authenticated_user_id:
        raise HTTPException(status_code=403, detail="Cannot delete another user's memory.")
    deleted = await memory_lifecycle.delete_memory(user_id=authenticated_user_id, memory_id=memory_id)
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
        raise HTTPException(status_code=403, detail="user_id must match the authenticated token subject.")
    info = device_manager.register_device(device_id=req.device_id, user_id=user_id, name=req.name)
    return APIResponse(data=info)


class DeviceRevokeRequest(BaseModel):
    device_id: str


@app.post("/v1/device/revoke", response_model=APIResponse[dict[str, bool]])
async def revoke_device(req: DeviceRevokeRequest, request: Request) -> APIResponse[dict[str, bool]]:
    """Revoke only a device owned by the authenticated user."""
    revoked = device_manager.revoke_device(req.device_id, user_id=_principal_user_id(request))
    return APIResponse(data={"revoked": revoked})


@app.post("/v1/device/actions", response_model=APIResponse[dict[str, Any]])
async def submit_device_action(intent: MobileIntent, request: Request) -> APIResponse[dict[str, Any]]:
    """Execute or request approval for an intent owned by the authenticated user."""
    try:
        result = await device_manager.execute_intent(intent=intent, user_id=_principal_user_id(request))
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
async def confirm_device_action(req: DeviceConfirmRequest, request: Request) -> APIResponse[dict[str, bool]]:
    """Approve a pending action only as its authenticated owner."""
    confirmed = device_manager.confirm_action(req.intent_id, req.confirmation_token, user_id=_principal_user_id(request))
    return APIResponse(data={"confirmed": confirmed})


@app.get("/v1/device/audit", response_model=APIResponse[list[ActionAuditRecord]])
async def get_device_audit(request: Request, device_id: str | None = None) -> APIResponse[list[ActionAuditRecord]]:
    """Retrieve audit records for the authenticated user only."""
    user_id = _principal_user_id(request)
    if device_id is not None and not device_manager.is_device_authorized(device_id, user_id=user_id):
        raise HTTPException(status_code=403, detail="Cannot inspect another user's device audit trail.")
    audit_trail = device_manager.get_audit_trail(device_id=device_id, user_id=user_id)
    return APIResponse(data=audit_trail)
