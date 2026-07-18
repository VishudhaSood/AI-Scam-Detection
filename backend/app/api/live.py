import json
import logging
import time
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.models.schemas import LiveFinal, LiveStart, LiveUpdate, RiskLabel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["Live Monitor"])

try:
    # Dev 2's real session engine (Milestone 7, feature/m7-stream-core).
    # Until that branch merges, the ImportError path below provides a stub
    # honoring the same interface, so this file needs no edits at merge time.
    from app.services.live_session import LiveSession
except ImportError as import_error:
    # Loud fallback: during integration a missing dependency in Dev 2's
    # module would otherwise silently demo the stub instead of the real thing.
    logger.warning("LiveSession stub active — real service not importable: %s", import_error)

    class LiveSession:
        """
        STUB — stands in for Dev 2's LiveSession so the WebSocket plumbing
        and the React client can be built and tested end-to-end. Produces
        clearly-fake canned transcript text and a slowly rising risk score.

        Mirrors the real interface (verified against Dev 2's branch):
            LiveSession(session_id: str, caller_number: str | None = None)
            await process_cycle(chunk: bytes) -> dict | LiveUpdate
        finalize() is scheduled for Milestone 9; the endpoint tolerates
        its absence and builds a fallback LiveFinal from the last update.
        """

        def __init__(self, session_id: str, caller_number: str | None = None):
            self.session_id = session_id
            self.caller_number = caller_number
            self.started_at = time.monotonic()
            self.chunk_count = 0
            self.committed = ""

        async def process_cycle(self, chunk: bytes) -> LiveUpdate:
            self.chunk_count += 1
            # Commit the previous partial every 3 chunks to exercise the
            # committed-vs-partial rendering split in the UI.
            partial = f"[stub] chunk {self.chunk_count} received ({len(chunk)} bytes). "
            if self.chunk_count % 3 == 0:
                self.committed += partial
                partial = ""
            risk = round(min(0.9, self.chunk_count * 0.05), 2)
            return LiveUpdate(
                session_id=self.session_id,
                elapsed_s=round(time.monotonic() - self.started_at, 1),
                transcript_committed=self.committed,
                transcript_partial=partial,
                risk_raw=risk,
                label=RiskLabel.SUSPICIOUS if risk >= 0.4 else RiskLabel.SAFE,
            )


@router.websocket("/live")
async def live_monitor(websocket: WebSocket):
    """
    WS /api/v1/ws/live — live call monitoring session.

    Protocol (NEW_ARCHITECTURE.md §4): one JSON "start" frame, then any mix
    of binary audio frames (5s webm chunks) and a final JSON "end" frame.
    The server pushes a JSON LiveUpdate after each audio frame and a
    LiveFinal when the session ends, including on abrupt disconnect.
    """
    await websocket.accept()
    session = None
    last_update = None
    client_connected = True
    try:
        start = LiveStart.model_validate(await websocket.receive_json())
        session = LiveSession(str(uuid.uuid4()), caller_number=start.caller_number)

        while True:
            frame = await websocket.receive()
            if frame.get("bytes") is not None:
                # Boundary validation: process_cycle may return a dict or a
                # model; the wire only ever carries a contract-checked
                # LiveUpdate (internal extras like trigger_llm are dropped).
                raw = await session.process_cycle(frame["bytes"])
                last_update = LiveUpdate.model_validate(raw)
                await websocket.send_text(last_update.model_dump_json())
            elif frame.get("text") is not None:
                message = json.loads(frame["text"])
                if message.get("type") == "end":
                    break
    except WebSocketDisconnect:
        client_connected = False
    finally:
        # Finalize even on abrupt disconnect: a dropped browser tab must not
        # lose the call data. LiveSession.finalize() lands in Milestone 9;
        # until then a fallback final is assembled from the last update.
        if session is not None:
            final = await _finalize_session(session, last_update)
            if client_connected:
                await websocket.send_text(final.model_dump_json())

    if client_connected:
        await websocket.close()


async def _finalize_session(session, last_update: LiveUpdate | None) -> LiveFinal:
    """
    Uses LiveSession.finalize() when available (Milestone 9); otherwise
    builds the final report from the last pushed update so the client
    always receives a closing "final" frame.
    """
    if hasattr(session, "finalize"):
        return LiveFinal.model_validate(await session.finalize())

    transcript = ""
    if last_update is not None:
        transcript = (last_update.transcript_committed + " " + last_update.transcript_partial).strip()
    return LiveFinal(
        session_id=session.session_id,
        transcript=transcript or "(no speech captured)",
        risk_score=last_update.risk_raw if last_update else 0.0,
        label=last_update.label if last_update else "SAFE",
        scam_category=last_update.scam_category if last_update else "None",
        deepfake_probability=0.0,
        explanation="Live session summary (heuristic-only, Milestone 7). Full analysis arrives with session finalization in Milestone 9.",
        advisories=last_update.advisories if last_update else [],
    )
