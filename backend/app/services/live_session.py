import time
import numpy as np
from fastapi.concurrency import run_in_threadpool
from app.services.streaming_transcriber import StreamingTranscriber
from app.services.heuristic_scorer import HeuristicScorer
from app.services.risk_engine import AdaptiveRiskEngine

class LiveSession:
    """
    Manages the lifecycle and state processing of a live phone call session.
    Accumulates audio WebM bytes or SpeechRecognition text chunks, evaluates risk using
    HeuristicScorer and throttled RAG incremental LLM audits, runs the AdaptiveRiskEngine,
    and returns real-time fraud updates to the WebSocket.
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
        self.risk_engine = AdaptiveRiskEngine()

        # Incremental LLM audit state variables
        self.llm_audits_done = 0
        self.last_llm_audit_time = 0.0
        self.last_llm_risk = 0.0
        self.pending_questions = []
        self.last_audit_word_count = 0
        
        # Latest LLM audit structured output fields
        self.llm_scam_category = "None"
        self.llm_red_flags = []
        self.llm_suggested_questions = []
        self.llm_safe_actions = []
        self.llm_advisories = []
        self.llm_verdict = "N/A"

    async def process_text_cycle(self, committed: str, partial: str) -> dict:
        """
        Processes a client-side text chunk from browser-native Web Speech API,
        updating the transcript and computing risk scores in real-time.
        """
        self.committed_text = committed
        self.partial_text = partial
        
        full_transcript = self.committed_text
        if self.partial_text:
            full_transcript += (" " if full_transcript else "") + self.partial_text
            
        heuristic_result = HeuristicScorer.score(full_transcript)
        return await self._evaluate_risk_and_llm(full_transcript, heuristic_result.trigger_llm)

    async def process_cycle(self, new_chunk: bytes) -> dict:
        """
        Appends the new binary audio chunk, decodes the full stream, transcribes the active
        PCM block in a worker threadpool, commits the active block text when it exceeds 30s,
        and computes the smoothed risk score.
        """
        self.accumulated_bytes += new_chunk
        pcm_data = await run_in_threadpool(self.transcriber.decode_to_pcm, self.accumulated_bytes)
        
        if pcm_data is None or pcm_data.size == 0:
            return self._build_update(
                risk_raw=0.1,
                risk_smoothed=0.1,
                confidence=0.0,
                mode="MONITOR",
                red_flags=[],
                trigger_llm=False
            )

        active_block_pcm = pcm_data[self.block_start_sample:]
        self.partial_text = await run_in_threadpool(self.transcriber.transcribe_pcm, active_block_pcm)
        
        if len(active_block_pcm) >= 480000:
            if self.partial_text:
                self.committed_text += (" " if self.committed_text else "") + self.partial_text
            self.block_start_sample = len(pcm_data)
            self.partial_text = ""

        full_transcript = self.committed_text
        if self.partial_text:
            full_transcript += (" " if full_transcript else "") + self.partial_text
            
        heuristic_result = HeuristicScorer.score(full_transcript)
        return await self._evaluate_risk_and_llm(full_transcript, heuristic_result.trigger_llm)

    async def _evaluate_risk_and_llm(self, full_transcript: str, trigger_llm: bool) -> dict:
        """
        Runs HeuristicScorer and evaluates the incremental LLM audit throttling policy,
        blending scores and passing it through the AdaptiveRiskEngine.
        """
        words = full_transcript.split()
        word_count = len(words)
        new_speech = word_count > self.last_audit_word_count

        now = time.time()
        time_elapsed = now - self.last_llm_audit_time

        # LLM Throttle Policy:
        # 1. Immediately on high-tier heuristic trigger_llm.
        # 2. When questions were pending and new speech arrived since the last audit (check for answers).
        # 3. Every 20 seconds of elapsed time, if new speech has arrived.
        should_audit = False
        if trigger_llm:
            should_audit = True
        elif self.pending_questions and new_speech:
            should_audit = True
        elif time_elapsed >= 20.0 and new_speech:
            should_audit = True

        if should_audit:
            try:
                from app.rag.query_engine import RAGQueryEngine
                audit_result = await run_in_threadpool(
                    RAGQueryEngine.evaluate_incremental,
                    full_transcript,
                    self.pending_questions
                )
                
                self.llm_audits_done += 1
                self.last_llm_audit_time = now
                self.last_audit_word_count = word_count
                
                self.last_llm_risk = audit_result.get("risk_score", 0.0)
                self.llm_scam_category = audit_result.get("scam_category", "None")
                self.llm_red_flags = audit_result.get("red_flags", [])
                self.llm_suggested_questions = audit_result.get("suggested_questions", [])
                self.llm_safe_actions = audit_result.get("safe_actions", [])
                self.llm_advisories = audit_result.get("advisories", [])
                self.llm_verdict = audit_result.get("question_response_verdict", "N/A")
                
                self.pending_questions = self.llm_suggested_questions
            except Exception as e:
                print(f"Error in incremental LLM audit: {e}")

        # Blend Raw Risk: max of heuristics and latest LLM audit score
        risk_raw = max(HeuristicScorer.score(full_transcript).risk, self.last_llm_risk)

        # Apply Question Response Verdict adjustments:
        # EVASIVE/REFUSED/THREATENED -> +0.20; PLAUSIBLE -> -0.05
        if self.llm_verdict in ["EVASIVE", "REFUSED", "THREATENED"]:
            risk_raw = min(1.0, risk_raw + 0.20)
        elif self.llm_verdict == "PLAUSIBLE":
            risk_raw = max(0.0, risk_raw - 0.05)

        # Run AdaptiveRiskEngine (EMA, ratchet, confidence, state machine)
        smoothed_risk, confidence, mode = self.risk_engine.process_cycle(
            risk_raw=risk_raw,
            word_count=word_count,
            llm_audits_done=self.llm_audits_done
        )

        heuristic_result = HeuristicScorer.score(full_transcript)
        combined_red_flags = list(set(heuristic_result.tier_hits + self.llm_red_flags))

        return self._build_update(
            risk_raw=risk_raw,
            risk_smoothed=smoothed_risk,
            confidence=confidence,
            mode=mode,
            red_flags=combined_red_flags,
            trigger_llm=trigger_llm
        )

    def _build_update(self, risk_raw: float, risk_smoothed: float, confidence: float, mode: str, red_flags: list[str], trigger_llm: bool) -> dict:
        if mode == "DANGER":
            label = "SCAM"
        elif mode == "VERIFY":
            label = "SUSPICIOUS"
        else:
            label = "SAFE"

        # Suggested questions only visible in VERIFY mode; safe actions in DANGER
        suggested_questions = self.llm_suggested_questions if mode == "VERIFY" else []
        safe_actions = self.llm_safe_actions if mode == "DANGER" else []

        elapsed_s = int(time.time() - self.start_time)
        
        advisories_json = []
        for adv in self.llm_advisories:
            advisories_json.append({
                "title": adv.title,
                "source": adv.source,
                "description": adv.description,
                "url": adv.url
            })

        return {
            "type": "update",
            "session_id": self.session_id,
            "elapsed_s": elapsed_s,
            "transcript_committed": self.committed_text,
            "transcript_partial": self.partial_text,
            "risk_raw": risk_raw,
            "risk_smoothed": risk_smoothed,
            "confidence": confidence,
            "label": label,
            "mode": mode,
            "scam_category": self.llm_scam_category,
            "red_flags": red_flags,
            "suggested_questions": suggested_questions,
            "safe_actions": safe_actions,
            "advisories": advisories_json,
            "trigger_llm": trigger_llm
        }
