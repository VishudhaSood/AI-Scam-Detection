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

        # LLM Throttle Policy:
        # 1. Immediately on high-tier heuristic trigger_llm.
        # 2. When questions were pending and new speech arrived since the last audit (check for answers).
        # 3. Every 20 seconds of elapsed time, if new speech has arrived.
        should_audit = False
        if trigger_llm:
            should_audit = True
        elif session.pending_questions and new_speech:
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
                session.llm_verdict = audit_result.get("question_response_verdict", "N/A")
                
                session.pending_questions = session.llm_suggested_questions
            except Exception as e:
                print(f"Error in WhisperReasoningProvider evaluate: {e}")

        # Compute confidence: base confidence on whether any audits have run
        confidence = 1.0 if session.llm_audits_done > 0 else 0.0
        
        explanation = f"Qwen LLM analyzed transcript content. Category: {session.llm_scam_category}."
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
