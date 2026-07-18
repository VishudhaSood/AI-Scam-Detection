import json
import time
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.models.schemas import LiveFinal, LiveStart, LiveUpdate, RiskLabel

router = APIRouter(prefix="/ws", tags=["Live Monitor"])

try:
    # Dev 2's real session engine (Milestone 7, feature/m7-stream-core).
    # Until that branch merges, the ImportError path below provides a stub
    # honoring the same interface, so this file needs no edits at merge time.
    from app.services.live_session import LiveSession
except ImportError:

    class LiveSession:
        """
        STUB — stands in for Dev 2's LiveSession so the WebSocket plumbing
        and the React client can be built and tested end-to-end. Produces
        clearly-fake canned transcript text and a slowly rising risk score.

        Interface contract (Dev 2 must match):
            LiveSession(caller_number: str | None)
            await process_chunk(chunk: bytes) -> LiveUpdate
            await finalize() -> LiveFinal
        """

        def __init__(self, caller_number: str | None = None):
            self.session_id = str(uuid.uuid4())
            self.caller_number = caller_number
            self.started_at = time.monotonic()
            self.chunk_count = 0
            self.committed = ""

        async def process_chunk(self, chunk: bytes) -> LiveUpdate:
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

        async def finalize(self) -> LiveFinal:
            return LiveFinal(
                session_id=self.session_id,
                transcript=self.committed or "[stub] no audio processed",
                risk_score=round(min(0.9, self.chunk_count * 0.05), 2),
                label="SUSPICIOUS" if self.chunk_count >= 8 else "SAFE",
                scam_category="None",
                deepfake_probability=0.0,
                explanation="[stub] LiveSession stub summary — real analysis arrives with Dev 2's merge.",
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
    client_connected = True
    try:
        start = LiveStart.model_validate(await websocket.receive_json())
        session = LiveSession(caller_number=start.caller_number)

        while True:
            frame = await websocket.receive()
            if frame.get("bytes") is not None:
                update = await session.process_chunk(frame["bytes"])
                await websocket.send_text(update.model_dump_json())
            elif frame.get("text") is not None:
                message = json.loads(frame["text"])
                if message.get("type") == "end":
                    break
    except WebSocketDisconnect:
        client_connected = False
    finally:
        # Finalize even on abrupt disconnect: a dropped browser tab must not
        # lose the call data (persistence itself lands in Milestone 9).
        if session is not None:
            final = await session.finalize()
            if client_connected:
                await websocket.send_text(final.model_dump_json())

    if client_connected:
        await websocket.close()
