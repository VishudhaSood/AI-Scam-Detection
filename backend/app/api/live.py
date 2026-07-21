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
        and the React client can be built and tested end-to-end.
        """

        def __init__(self, session_id: str, caller_number: str | None = None):
            self.session_id = session_id
            self.caller_number = caller_number
            self.started_at = time.monotonic()
            self.chunk_count = 0
            self.committed = ""

        async def process_cycle(self, chunk: bytes) -> LiveUpdate:
            self.chunk_count += 1
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
                chunk = frame["bytes"]
                # A malformed audio frame must be dropped, never end the session
                try:
                    # Normal Whisper mode: full cycle (STT + risk fusion)
                    raw = await session.process_cycle(chunk)
                    last_update = LiveUpdate.model_validate(raw)
                    await websocket.send_text(last_update.model_dump_json())
                except Exception as e:
                    logger.error(f"Dropped malformed binary frame ({len(chunk)} bytes): {e}")
            elif frame.get("text") is not None:
                message = json.loads(frame["text"])
                if message.get("type") == "end":
                    break
                elif message.get("type") == "text_chunk":
                    raw = await session.process_text_cycle(
                        message.get("transcript_committed", ""),
                        message.get("transcript_partial", "")
                    )
                    last_update = LiveUpdate.model_validate(raw)
                    await websocket.send_text(last_update.model_dump_json())
    except WebSocketDisconnect:
        client_connected = False
    finally:
        # Finalize even on abrupt disconnect: a dropped browser tab must not
        # lose the call data. Send final immediately from cached state to avoid
        # blocking the close on heavy backend inference.
        if session is not None:
            final = _build_final_from_last_update(session, last_update)
            
            # Persist live call log to SQLite DB (Milestone 9)
            try:
                from app.database.connection import SessionLocal
                from app.database import crud
                db = SessionLocal()
                try:
                    db_log = crud.save_analysis_result(db, final)
                    final.log_id = db_log.id
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Failed to persist live call log: {e}")

            if client_connected:
                try:
                    await websocket.send_text(final.model_dump_json())
                except Exception:
                    pass  # client may have already disconnected

    if client_connected:
        try:
            await websocket.close()
        except Exception:
            pass


def _build_final_from_last_update(session, last_update: LiveUpdate | None) -> LiveFinal:
    """
    Instantly assembles the final report from the last cached LiveUpdate.
    This is intentionally synchronous and non-blocking — no heavy inference
    is re-run at teardown time.
    """
    transcript = ""
    if last_update is not None:
        transcript = (last_update.transcript_committed + " " + (last_update.transcript_partial or "")).strip()

    # Use the smoothed/ratcheted score, not risk_raw: the in-call gauge and
    # coach mode are driven by risk_smoothed, so the persisted final report
    # must match what the user actually saw (FLAWS_AND_IMPROVEMENTS.md §5.3).
    risk_score  = last_update.risk_smoothed  if last_update else 0.0
    label       = last_update.label          if last_update else "SAFE"
    scam_cat    = last_update.scam_category  if last_update else "None"
    advisories  = last_update.advisories     if last_update else []

    evidence_breakdown = None
    overall_confidence = 0.0
    reasoning_trace = []
    
    if last_update is not None:
        evidence_breakdown = getattr(last_update, "evidence_breakdown", None)
        overall_confidence = getattr(last_update, "overall_confidence", 0.0)
        reasoning_trace = getattr(last_update, "reasoning_trace", [])

    duration_s = round(time.time() - session.start_time, 1) if hasattr(session, "start_time") else (last_update.elapsed_s if last_update else 0.0)
    timeline = getattr(session, "score_timeline", [])
    peak_risk = max(timeline) if timeline else (last_update.risk_smoothed if last_update else 0.0)
    score_timeline_json = json.dumps(timeline) if timeline else None
    caller_num = getattr(session, "caller_number", None)

    return LiveFinal(
        session_id=session.session_id,
        caller_number=caller_num,
        duration_s=duration_s,
        peak_risk=peak_risk,
        score_timeline=score_timeline_json,
        transcript=transcript or "(no speech captured)",
        risk_score=risk_score,
        label=label,
        scam_category=scam_cat,
        evidence_breakdown=evidence_breakdown,
        overall_confidence=overall_confidence,
        reasoning_trace=reasoning_trace,
        explanation="Live session completed. Risk scores were computed incrementally during the call.",
        advisories=advisories,
    )


async def _finalize_session(session, last_update: LiveUpdate | None) -> LiveFinal:
    """
    Legacy async path kept for backward compatibility.
    Delegates immediately to the synchronous fast path.
    """
    return _build_final_from_last_update(session, last_update)
