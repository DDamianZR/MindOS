"""
Endpoints de aprobaciones (F1-T8/F3-T1/F3-T7): resuelve los `pending_approval` que
`CapabilityExecutor` deja al pausar una capacidad sensible.

Router separado de `main.py` (mismo motivo que en Memory, ver `thinking_router.py`). OJO:
`approval_store`/`capability_registry` son OBJETOS (no funciones) — se acceden vía
`agents_main.approval_store` en cada request, NUNCA importados por nombre a este módulo, porque
eso capturaría la referencia vigente al importar el router (arranque de la app) y un test que
monkeypatchea `agents_main.approval_store` después dejaría de tener efecto aquí. `get_http_client`
y `resolve_service_url` sí son funciones puras (sin estado propio) y se importan directo.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from mindos_common.ids import new_id
from mindos_schemas.api.v1.approval_dto import (
    ApprovalRequestDto,
    ListApprovalsResponse,
    ResolveApprovalRequest,
    ResolveApprovalResponse,
)

from agents.src import main as agents_main
from agents.src.config import settings
from agents.src.domain.executor.capability_executor import CapabilityExecutor
from agents.src.infrastructure.adapters.http_reasoning_recorder import HttpReasoningRecorder
from agents.src.main import get_http_client, resolve_service_url

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


async def _next_step_index(http_client, episode_id: UUID) -> int:
    """Consulta el episodio en Memory para no pisar índices de pasos ya registrados.
    Best-effort: si Memory no responde, usa 0 (el recorder es best-effort de por sí)."""
    try:
        resp = await http_client.get(f"{settings.MEMORY_URL}/api/v1/thinking/episodes/{episode_id}")
        resp.raise_for_status()
        steps = resp.json().get("steps", [])
        return max((s["step_index"] for s in steps), default=-1) + 1
    except Exception:
        return 0


@router.get("/", response_model=ListApprovalsResponse)
async def list_pending_approvals():
    """Bandeja de aprobaciones (F4-T1): las `pending`, más recientes primero. Nota: la ruta es
    '/' (no '') a propósito — con trailing slash reconstruye byte a byte lo que arma el proxy
    del Gateway para `rest_of_path=''`, evitando el 307 de Starlette que el proxy no sigue."""
    records = await agents_main.approval_store.list_pending()
    return ListApprovalsResponse(approvals=[ApprovalRequestDto(**r) for r in records])


@router.get("/{approval_id}", response_model=ApprovalRequestDto)
async def get_approval(approval_id: UUID):
    record = await agents_main.approval_store.get(approval_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Aprobación {approval_id} no encontrada.")
    return ApprovalRequestDto(**record)


@router.post("/{approval_id}/resolve", response_model=ResolveApprovalResponse)
async def resolve_approval(
    approval_id: UUID,
    request: ResolveApprovalRequest,
    http_client=Depends(get_http_client),
):
    approval_store = agents_main.approval_store
    record = await approval_store.get(approval_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Aprobación {approval_id} no encontrada.")
    if record["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La aprobación {approval_id} ya fue resuelta ({record['status']}).",
        )

    executed = False
    if request.approved:
        executor = CapabilityExecutor(
            agents_main.capability_registry, service_url_resolver=resolve_service_url,
            http_client=http_client, approval_store=approval_store,
        )
        result = await executor.execute_capability_by_name(record["capability_name"], record["inputs"])
        result_output = result.output
        executed = result.status == "completed"
    else:
        result_output = "Rechazada por el usuario; la capacidad no se ejecutó."

    new_status = "approved" if request.approved else "rejected"
    updated = await approval_store.resolve(approval_id, status=new_status, result_output=result_output)

    # Deja rastro en el Thinking Graph (F2-T2/F2-T3): el episodio queda con su resolución real
    # en vez de congelado en 'pending_approval' para siempre.
    recorder = HttpReasoningRecorder(settings.MEMORY_URL, http_client=http_client)
    episode_id = record["episode_id"]
    step_index = await _next_step_index(http_client, episode_id)
    await recorder.record_step(
        episode_id=episode_id, step_id=new_id(), step_index=step_index, kind="execute",
        input_text=f"Resolución de aprobación para '{record['capability_name']}'",
        output_text=result_output, capability_name=record["capability_name"], approved=request.approved,
    )
    if not request.approved:
        final_episode_status = "rejected"
    else:
        final_episode_status = "completed" if executed else "failed"
    await recorder.close_episode(episode_id, status=final_episode_status, final_output=result_output)

    return ResolveApprovalResponse(approval=ApprovalRequestDto(**updated), executed=executed)
