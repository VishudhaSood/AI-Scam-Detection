import time
import logging
import numpy as np
from fastapi.concurrency import run_in_threadpool
from app.services.streaming_transcriber import StreamingTranscriber
from app.services.heuristic_scorer import HeuristicScorer
from app.services.risk_engine import AdaptiveRiskEngine, EvidenceFusionEngine
from app.services.evidence_orchestrator import EvidenceOrchestrator

logger = logging.getLogger("app.services.live_session")

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
        self.pcm_buffer = np.array([], dtype=np.float32)
        
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
        self.llm_explanation = ""

        # Sticky coach guidance: consecutive audits may return empty lists
        # (e.g. the fallback clears them once pending questions reset), which
        # made the UI flicker between guidance and its absence. Once issued,
        # guidance survives until the mode gates it out.
        self.sticky_questions = []
        self.sticky_safe_actions = []

        self.last_breakdown = {
            "transcript": 0.0,
            "heuristics": 0.0,
            "rag_match": 0.0,
            "verification": 0.0
        }
        self.orchestrator = EvidenceOrchestrator()
        self.last_reasoning_trace = []

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
        Appends the new binary audio chunk (detecting raw float32 PCM vs container WebM),
        decodes/handles it, transcribes the active PCM block, and computes the risk score.
        """
        if not new_chunk:
            return self._build_update(
                risk_raw=0.1,
                risk_smoothed=0.1,
                confidence=0.0,
                mode="MONITOR",
                red_flags=[],
                trigger_llm=False
            )

        # Detect WebM vs raw float32 PCM (WebM files start with EBML header b'\x1a\x45\xdf\xa3')
        is_webm = new_chunk.startswith(b'\x1a\x45\xdf\xa3') or (len(self.accumulated_bytes) > 0)
        
        if is_webm:
            self.accumulated_bytes += new_chunk
            pcm_data = await run_in_threadpool(self.transcriber.decode_to_pcm, self.accumulated_bytes)
        else:
            # Direct raw float32 PCM from browser AudioContext
            pcm_chunk = np.frombuffer(new_chunk, dtype=np.float32)
            self.pcm_buffer = np.concatenate([self.pcm_buffer, pcm_chunk])
            pcm_data = self.pcm_buffer

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

        # Commit at 15s (240k samples @16kHz), not 30s: the whole active block is
        # re-transcribed every cycle, and near a 30s block CPU Whisper exceeds the
        # 5s chunk budget — frames backlog and the transcript stalls, then jumps.
        if len(active_block_pcm) >= 240000:
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
        Delegates evaluation to the modular EvidenceOrchestrator.
        """
        context = {
            "session": self,
            "transcript": full_transcript,
            "trigger_llm": trigger_llm
        }
        
        # Run orchestration
        eval_result = await self.orchestrator.evaluate(context)
        
        # Cache the reasoning trace for inclusion in the final report
        self.last_reasoning_trace = eval_result["reasoning_trace"]
        
        # Determine combined red flags
        heuristic_result = HeuristicScorer.score(full_transcript)
        combined_red_flags = list(set(heuristic_result.tier_hits + self.llm_red_flags))
        
        return self._build_update(
            risk_raw=eval_result["risk_raw"],
            risk_smoothed=eval_result["risk_smoothed"],
            confidence=eval_result["confidence"],
            mode=eval_result["mode"],
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

        # Suggested questions only visible in VERIFY mode; safe actions in DANGER.
        # Sticky caches keep the last non-empty guidance so an audit that returns
        # empty lists doesn't blank (and un-blank) the coach panel between cycles.
        if self.llm_suggested_questions:
            self.sticky_questions = self.llm_suggested_questions
        if self.llm_safe_actions:
            self.sticky_safe_actions = self.llm_safe_actions

        suggested_questions = (self.llm_suggested_questions or self.sticky_questions) if mode == "VERIFY" else []
        safe_actions = (self.llm_safe_actions or self.sticky_safe_actions) if mode == "DANGER" else []

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
            "trigger_llm": trigger_llm,
            "evidence_breakdown": self.last_breakdown,
            "overall_confidence": confidence,
            "reasoning_trace": self.last_reasoning_trace
        }
