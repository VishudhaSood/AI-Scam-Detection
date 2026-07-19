import time
import logging
import numpy as np
from fastapi.concurrency import run_in_threadpool
from app.services.streaming_transcriber import StreamingTranscriber
from app.services.heuristic_scorer import HeuristicScorer
from app.services.deepfake_detector import AASISTDetector, DeepfakeResult
from app.services.risk_engine import AdaptiveRiskEngine, EvidenceFusionEngine

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

        # AASIST Deepfake detection state
        self.last_deepfake_result = DeepfakeResult(
            probability=None,
            label=None,
            confidence=None,
            model="AASIST",
            latency_ms=0.0
        )
        self.last_breakdown = {
            "transcript": 0.0,
            "deepfake": 0.0,
            "heuristics": 0.0,
            "rag_match": 0.0,
            "verification": 0.0
        }

    async def process_text_cycle(self, committed: str, partial: str) -> dict:
        """
        Processes a client-side text chunk from browser-native Web Speech API,
        updating the transcript and computing risk scores in real-time.
        Deepfake detection is handled separately by process_audio_only() when
        background MediaRecorder audio is available.
        """
        self.committed_text = committed
        self.partial_text = partial
        
        full_transcript = self.committed_text
        if self.partial_text:
            full_transcript += (" " if full_transcript else "") + self.partial_text
            
        heuristic_result = HeuristicScorer.score(full_transcript)
        return await self._evaluate_risk_and_llm(full_transcript, heuristic_result.trigger_llm)

    async def process_audio_only(self, audio_bytes: bytes) -> None:
        """
        AASIST-only analysis path for webspeech hybrid mode.
        Called when a 0xDF-tagged audio frame arrives from the background MediaRecorder.
        Runs AASIST deepfake detection on the real audio bytes and updates
        last_deepfake_result WITHOUT re-running Whisper STT or risk fusion.
        The next text_chunk cycle will pick up the updated deepfake result automatically.
        """
        if not audio_bytes or len(audio_bytes) < 1000:
            return
        full_transcript = self.committed_text + " " + self.partial_text
        self.last_deepfake_result = await run_in_threadpool(
            AASISTDetector.detect,
            audio_bytes,
            None,               # No filename in live streams
            full_transcript.strip() or None
        )
        logger.debug(
            f"[process_audio_only] AASIST result: "
            f"prob={self.last_deepfake_result.probability} label={self.last_deepfake_result.label}"
        )

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
        
        if len(active_block_pcm) >= 480000:
            if self.partial_text:
                self.committed_text += (" " if self.committed_text else "") + self.partial_text
            self.block_start_sample = len(pcm_data)
            self.partial_text = ""

        full_transcript = self.committed_text
        if self.partial_text:
            full_transcript += (" " if full_transcript else "") + self.partial_text

        # Extract current cycle PCM for AASIST anti-spoofing analysis
        if is_webm:
            current_cycle_pcm = pcm_data[-80000:] if pcm_data.size >= 80000 else pcm_data
        else:
            current_cycle_pcm = pcm_chunk

        self.last_deepfake_result = await run_in_threadpool(
            AASISTDetector.detect, 
            current_cycle_pcm, 
            None, 
            full_transcript
        )
            
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

        # Run Evidence Fusion: combine Qwen content, AASIST voice deepfake, heuristics, RAG match, and verdict
        heuristic_result = HeuristicScorer.score(full_transcript)
        
        risk_raw, self.last_breakdown = EvidenceFusionEngine.fuse_evidence(
            transcript_risk=self.last_llm_risk,
            deepfake_prob=self.last_deepfake_result.probability,
            heuristic_risk=heuristic_result.risk,
            advisories_count=len(self.llm_advisories),
            verification_verdict=self.llm_verdict
        )

        # Run AdaptiveRiskEngine (EMA, ratchet, confidence, state machine)
        smoothed_risk, confidence, mode = self.risk_engine.process_cycle(
            risk_raw=risk_raw,
            word_count=word_count,
            llm_audits_done=self.llm_audits_done
        )

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
            "trigger_llm": trigger_llm,
            "deepfake_probability": self.last_deepfake_result.probability,
            "deepfake_label": self.last_deepfake_result.label,
            "deepfake_confidence": self.last_deepfake_result.confidence,
            "deepfake_model": self.last_deepfake_result.model,
            "evidence_breakdown": self.last_breakdown,
            "overall_confidence": confidence
        }
