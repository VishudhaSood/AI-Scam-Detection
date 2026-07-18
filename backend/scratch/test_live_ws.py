"""
Scratch test for WS /api/v1/ws/live (Milestone 7, Dev 1).

Drives a full session against the in-process app: start -> N binary chunks
(expecting a LiveUpdate after each) -> end (expecting a LiveFinal). Works
against the LiveSession stub today and must keep passing unchanged after
Dev 2's real LiveSession merges.

Run from backend/:  python scratch/test_live_ws.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import LiveFinal, LiveUpdate


def run_session(n_chunks: int = 7) -> None:
    client = TestClient(app)
    with client.websocket_connect("/api/v1/ws/live") as ws:
        ws.send_json({"type": "start", "caller_number": "+91-99999-00000"})

        last_risk = -1.0
        for i in range(n_chunks):
            ws.send_bytes(b"\x1aE\xdf\xa3" + bytes(200))  # fake webm chunk
            update = LiveUpdate.model_validate(ws.receive_json())
            assert update.type == "update"
            assert update.risk_raw >= last_risk, "stub risk should never fall"
            last_risk = update.risk_raw
            print(
                f"cycle {i + 1}: elapsed={update.elapsed_s}s "
                f"risk={update.risk_raw:.2f} label={update.label.value} "
                f"committed={len(update.transcript_committed)}ch "
                f"partial={len(update.transcript_partial)}ch"
            )

        ws.send_json({"type": "end"})
        final = LiveFinal.model_validate(ws.receive_json())
        assert final.type == "final"
        assert final.session_id == update.session_id
        print(f"final: risk={final.risk_score} label={final.label} log_id={final.log_id}")

    print("PASS: full live-session round trip")


if __name__ == "__main__":
    run_session()
