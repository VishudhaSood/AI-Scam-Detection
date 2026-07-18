import time
import numpy as np
from fastapi.concurrency import run_in_threadpool
from app.services.streaming_transcriber import StreamingTranscriber
from app.services.heuristic_scorer import HeuristicScorer

class LiveSession:
    """
    Manages the lifecycle and state processing of a live phone call session.
    Accumulates audio WebM bytes, decodes them to raw PCM, transcribes the active audio block,
    commits text segments every 30 seconds, and evaluates threat indicators in real-time.
    """
    def __init__(self, session_id: str, caller_number: str = None):
        self.session_id = session_id
        self.caller_number = caller_number
        self.accumulated_bytes = b""
        
        self.committed_text = ""
        self.partial_text = ""
        self.block_start_sample = 0
        
        self.transcriber = StreamingTranscriber()
        self.start_time = time.time()

    async def process_cycle(self, new_chunk: bytes) -> dict:
        """
        Appends the new binary audio chunk, decodes the full stream, transcribes the active
        PCM block in a worker threadpool, commits the active block text when it exceeds 30s,
        and computes the raw risk score using HeuristicScorer.
        """
        # 1. Accumulate audio bytes
        self.accumulated_bytes += new_chunk
        
        # 2. Decode the full WebM audio bytes to 16kHz float32 mono PCM
        pcm_data = await run_in_threadpool(self.transcriber.decode_to_pcm, self.accumulated_bytes)
        
        if pcm_data is None or pcm_data.size == 0:
            # Not enough binary bytes to parse valid container frames yet
            return self._build_update(0.1, [], False)

        # 3. Transcribe only the ACTIVE block (samples since block_start_sample)
        active_block_pcm = pcm_data[self.block_start_sample:]
        
        # Transcribe the raw audio array in a threadpool to prevent blocking the event loop
        self.partial_text = await run_in_threadpool(self.transcriber.transcribe_pcm, active_block_pcm)
        
        # 4. Check if active block length exceeds 30 seconds of audio
        # 30 seconds * 16000 samples/sec = 480,000 samples
        if len(active_block_pcm) >= 480000:
            if self.partial_text:
                self.committed_text += (" " if self.committed_text else "") + self.partial_text
            self.block_start_sample = len(pcm_data)
            self.partial_text = ""

        # 5. Evaluate combined transcript (committed + partial)
        full_transcript = self.committed_text
        if self.partial_text:
            full_transcript += (" " if full_transcript else "") + self.partial_text
            
        heuristic_result = HeuristicScorer.score(full_transcript)
        
        # 6. Build the live update data
        return self._build_update(
            risk_raw=heuristic_result.risk,
            red_flags=heuristic_result.tier_hits,
            trigger_llm=heuristic_result.trigger_llm
        )

    def _build_update(self, risk_raw: float, red_flags: list[str], trigger_llm: bool) -> dict:
        # Map raw risk to labels
        if risk_raw >= 0.75:
            label = "SCAM"
            mode = "DANGER"
        elif risk_raw >= 0.40:
            label = "SUSPICIOUS"
            mode = "VERIFY"
        else:
            label = "SAFE"
            mode = "MONITOR"

        # Determine a rough scam category from context for the skeleton update
        scam_category = "None"
        full_text = (self.committed_text + " " + self.partial_text).lower().strip()
        if red_flags:
            if any(kw in full_text for kw in ["otp", "pin", "cvv", "card blocked", "kyc"]):
                scam_category = "Bank Impersonation (KYC)"
            elif any(kw in full_text for kw in ["lottery", "prize", "win", "crore", "lakh"]):
                scam_category = "Lottery & Prize Scam"
            elif any(kw in full_text for kw in ["police", "cbi", "arrest", "illegal", "package"]):
                scam_category = "Law Enforcement Impersonation"
            else:
                scam_category = "Suspicious Activity"

        elapsed_s = int(time.time() - self.start_time)
        
        return {
            "type": "update",
            "session_id": self.session_id,
            "elapsed_s": elapsed_s,
            "transcript_committed": self.committed_text,
            "transcript_partial": self.partial_text,
            "risk_raw": risk_raw,
            "risk_smoothed": risk_raw,  # No smoothing logic in Milestone 7
            "confidence": 0.5,           # Static confidence placeholder for Milestone 7
            "label": label,
            "mode": mode,
            "scam_category": scam_category,
            "red_flags": red_flags,
            "suggested_questions": [],
            "safe_actions": [],
            "advisories": [],
            "trigger_llm": trigger_llm
        }
