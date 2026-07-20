import time
from fastapi.concurrency import run_in_threadpool
from app.services.evidence_provider import EvidenceProvider, Evidence
from app.rag.query_engine import RAGQueryEngine

class WhisperReasoningProvider(EvidenceProvider):
    """
    Evidence provider that performs incremental semantic analysis on transcripts
    using the Qwen LLM and ChromaDB vector store.
    """
    
    @property
    def name(self) -> str:
        return "transcript"

    async def evaluate(self, context: dict) -> Evidence:
        session = context["session"]
        transcript = context["transcript"]
        trigger_llm = context.get("trigger_llm", False)
        
        words = transcript.split()
        word_count = len(words)
        new_speech = word_count > session.last_audit_word_count

        now = time.time()
        time_elapsed = now - session.last_llm_audit_time

        # LLM Throttle Policy (with 10s minimum cooldown to prevent quota death):
        # 1. On high-tier heuristic trigger_llm, BUT only if 10s have passed since last audit.
        # 2. When questions were pending and new speech arrived since the last audit (check for answers).
        # 3. Every 20 seconds of elapsed time, if new speech has arrived.
        # The 10s floor prevents a 3-min call from burning 30+ API calls.
        MIN_AUDIT_INTERVAL = 10.0
        should_audit = False
        if trigger_llm and new_speech and time_elapsed >= MIN_AUDIT_INTERVAL:
            should_audit = True
        elif session.pending_questions and new_speech and time_elapsed >= MIN_AUDIT_INTERVAL:
            should_audit = True
        elif time_elapsed >= 20.0 and new_speech:
            should_audit = True

        if should_audit:
            try:
                audit_result = await run_in_threadpool(
                    RAGQueryEngine.evaluate_incremental,
                    transcript,
                    session.pending_questions
                )
                
                session.llm_audits_done += 1
                session.last_llm_audit_time = now
                session.last_audit_word_count = word_count
                
                session.last_llm_risk = audit_result.get("risk_score", 0.0)
                session.llm_scam_category = audit_result.get("scam_category", "None")
                session.llm_red_flags = audit_result.get("red_flags", [])
                session.llm_suggested_questions = audit_result.get("suggested_questions", [])
                session.llm_safe_actions = audit_result.get("safe_actions", [])
                session.llm_advisories = audit_result.get("advisories", [])
                session.llm_explanation = audit_result.get("explanation", "")

                # A hostile/evasive reaction is a fact about this call: keep it
                # until the caller redeems themselves with a PLAUSIBLE answer.
                # Audits that ran with no pending questions return N/A or
                # NOT_YET_ANSWERED and must not erase an earlier bad verdict
                # (that erasure made risk and safe_actions oscillate every cycle).
                new_verdict = audit_result.get("question_response_verdict", "N/A")
                if (new_verdict in ["EVASIVE", "REFUSED", "THREATENED", "PLAUSIBLE"]
                        or session.llm_verdict not in ["EVASIVE", "REFUSED", "THREATENED"]):
                    session.llm_verdict = new_verdict

                session.pending_questions = session.llm_suggested_questions
            except Exception as e:
                print(f"Error in WhisperReasoningProvider evaluate: {e}")

        # Compute confidence: base confidence on whether any audits have run
        confidence = 1.0 if session.llm_audits_done > 0 else 0.0

        # Surface the audit's own explanation: the offline fallback tags itself
        # "[FALLBACK MOCK ANALYSIS - NO LIVE LLM]", so the trace stays honest
        # about which engine actually produced the verdict.
        explanation = getattr(session, "llm_explanation", "") or \
            f"LLM transcript audit. Category: {session.llm_scam_category}."
        if session.llm_red_flags:
            explanation += f" Detected flags: {', '.join(session.llm_red_flags)}."

        return Evidence(
            source=self.name,
            score=session.last_llm_risk,
            confidence=confidence,
            weight=0.40,
            details={
                "scam_category": session.llm_scam_category,
                "red_flags": session.llm_red_flags,
                "suggested_questions": session.llm_suggested_questions,
                "safe_actions": session.llm_safe_actions,
                "advisories": session.llm_advisories,
                "verdict": session.llm_verdict,
                "audits_done": session.llm_audits_done
            },
            explanation=explanation
        )
