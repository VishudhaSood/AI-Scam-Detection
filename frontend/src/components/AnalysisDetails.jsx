import React from 'react';
import RiskGauge from './RiskGauge';

const AnalysisDetails = ({ data }) => {
  if (!data) return null;

  const {
    transcript,
    risk_score,
    label,
    scam_category,
    explanation,
    advisories,
    evidence_breakdown,
    overall_confidence
  } = data;

  // Determine threat level class names
  const getBadgeClass = (lbl) => {
    if (lbl === 'SAFE') return 'risk-badge safe';
    if (lbl === 'SUSPICIOUS') return 'risk-badge suspicious';
    return 'risk-badge scam';
  };

  const handleDownloadComplaint = () => {
    const reportText = `======================================================================
INCIDENT AUDIT REPORT & CYBERCRIME COMPLAINT DRAFT
National Cyber Crime Reporting Portal (cybercrime.gov.in) / Helpline 1930
======================================================================

Date & Time: ${new Date().toLocaleString()}
Threat Evaluation Label: ${label} (Risk Score: ${Math.round(risk_score * 100)}%)
Detected Scam Category: ${scam_category}
Overall Evidence Confidence: ${Math.round((overall_confidence || 0) * 100)}%

----------------------------------------------------------------------
EXECUTIVE SUMMARY & REASONING
----------------------------------------------------------------------
${explanation}

----------------------------------------------------------------------
INCIDENT TRANSCRIPT EXCERPT
----------------------------------------------------------------------
"${transcript}"

----------------------------------------------------------------------
MATCHED REGULATORY ADVISORIES & WARNINGS
----------------------------------------------------------------------
${advisories && advisories.length > 0
  ? advisories.map(a => `- [${a.source}] ${a.title}\n  Details: ${a.description}`).join('\n\n')
  : 'No specific regulatory advisories matched.'}

----------------------------------------------------------------------
RECOMMENDED DEFENSIVE ACTIONS
----------------------------------------------------------------------
1. Do NOT transfer any money or pay any "settlement fees" or "processing charges".
2. Do NOT share OTPs, PINs, bank passwords, or Aadhaar details over the call.
3. If money has already been transferred, report immediately to Helpline 1930 within the golden hour to freeze recipient bank accounts.
4. File an official complaint on https://cybercrime.gov.in and attach this transcript audit report as evidence.
======================================================================`;

    const element = document.createElement("a");
    const file = new Blob([reportText], { type: 'text/plain' });
    element.href = URL.createObjectURL(file);
    element.download = `Cybercrime_Complaint_Draft_${Date.now()}.txt`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  return (
    <div className="results-container">
      {/* 1. Score & Threat Level Box */}
      <div className="glass-panel score-header-box">
        <RiskGauge score={risk_score} />
        
        <div className="risk-level-card">
          <h2>Threat Evaluation</h2>
          <span className={getBadgeClass(label)}>{label}</span>
          
          <div className="metrics-row">
            <div className="metric-tile scam-label">
              <p>Category</p>
              <span>{scam_category}</span>
            </div>
            <div className="metric-tile">
              <p>Confidence</p>
              <span style={{ color: 'var(--accent-purple, #8b5cf6)' }}>
                {Math.round((overall_confidence || 0) * 100)}%
              </span>
            </div>
          </div>

          {(label === 'SCAM' || label === 'SUSPICIOUS') && (
            <button
              type="button"
              onClick={handleDownloadComplaint}
              className="submit-btn"
              style={{
                marginTop: '1rem',
                fontSize: '0.8rem',
                padding: '0.5rem 1rem',
                background: 'rgba(239, 68, 68, 0.2)',
                border: '1px solid var(--color-scam, #ef4444)',
                color: '#fff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem'
              }}
            >
              📥 Download Complaint Draft (1930)
            </button>
          )}
        </div>
      </div>

      {/* Evidence Breakdown Card */}
      {evidence_breakdown && (
        <div className="glass-panel evidence-breakdown-card" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.1rem' }}>
            📊 Evidence Breakdown
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            <div className="evidence-item">
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Transcript Analysis</div>
              <div style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--text-primary)' }}>
                {Math.round(evidence_breakdown.transcript * 100)}%
              </div>
            </div>
            <div className="evidence-item">
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Scam Heuristic Score</div>
              <div style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--text-primary)' }}>
                {Math.round(evidence_breakdown.heuristics * 100)}%
              </div>
            </div>
            <div className="evidence-item">
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>RBI Advisory Match</div>
              <div style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--text-primary)' }}>
                {Math.round(evidence_breakdown.rag_match * 100)}%
              </div>
            </div>
            {evidence_breakdown.verification > 0.0 && (
              <div className="evidence-item" style={{ gridColumn: 'span 2' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Verification Question Verdict Penalty</div>
                <div style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--color-scam, #ef4444)' }}>
                  +{Math.round(evidence_breakdown.verification * 100)}% (EVASIVE/REFUSED)
                </div>
              </div>
            )}
            <div className="evidence-item" style={{ gridColumn: 'span 2' }}>
              <hr style={{ border: 'none', borderTop: '1px solid rgba(255,255,255,0.1)', margin: '0.25rem 0' }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Overall Confidence</span>
                <span style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--accent-purple, #8b5cf6)' }}>
                  {Math.round((overall_confidence || 0) * 100)}%
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Evidence Reasoning Trace Card */}
      {data.reasoning_trace && data.reasoning_trace.length > 0 && (
        <div className="glass-panel reasoning-trace-card" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '1rem' }}>
          <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.1rem' }}>
            🕵️ Evidence Reasoning Trace
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {data.reasoning_trace.map((step, idx) => (
              <div key={idx} style={{ 
                fontSize: '0.85rem', 
                color: 'var(--text-secondary)', 
                lineHeight: 1.5,
                background: 'rgba(255, 255, 255, 0.02)',
                padding: '0.5rem 0.75rem',
                borderRadius: '0.375rem',
                borderLeft: '3px solid ' + (step.startsWith('[Evidence Fusion]') ? 'var(--accent-blue, #3b82f6)' : step.startsWith('[Temporal Adaptation]') ? 'var(--accent-purple, #8b5cf6)' : 'rgba(255, 255, 255, 0.15)')
              }}>
                {step}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 2. Simulated Transcript Box */}
      <div className="glass-panel transcript-card">
        <h3>
          <svg style={{ width: '1.25rem', height: '1.25rem' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
          </svg>
          Call Transcript
        </h3>
        <p className="transcript-body">{transcript}</p>
      </div>

      {/* 3. Reason/Explanation Box */}
      <div className="glass-panel explanation-card">
        <h3>
          <svg style={{ width: '1.25rem', height: '1.25rem' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          AI Scam Analysis
        </h3>
        <p className="explanation-body">{explanation}</p>
      </div>

      {/* 4. RAG Advisories Box */}
      {advisories && advisories.length > 0 && (
        <div className="glass-panel advisories-card">
          <h3>
            <svg style={{ width: '1.25rem', height: '1.25rem' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            Matched Regulatory Advisories
          </h3>
          <div className="advisories-list">
            {advisories.map((advisory, idx) => (
              <div className="advisory-item" key={idx}>
                <div className="advisory-header">
                  <span className="advisory-title">{advisory.title}</span>
                  <span className="advisory-source">{advisory.source}</span>
                </div>
                <p className="advisory-desc">{advisory.description}</p>
                {advisory.url && (
                  <a
                    href={advisory.url}
                    target="_blank"
                    rel="noreferrer"
                    className="advisory-link"
                  >
                    View Official Document
                    <svg style={{ width: '0.85rem', height: '0.85rem' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default AnalysisDetails;
