import React from 'react';
import RiskGauge from './RiskGauge';

const AnalysisDetails = ({ data }) => {
  if (!data) return null;

  const {
    transcript,
    risk_score,
    label,
    scam_category,
    deepfake_probability,
    explanation,
    advisories
  } = data;

  // Determine threat level class names
  const getBadgeClass = (lbl) => {
    if (lbl === 'SAFE') return 'risk-badge safe';
    if (lbl === 'SUSPICIOUS') return 'risk-badge suspicious';
    return 'risk-badge scam';
  };

  const isDeepfakeHigh = deepfake_probability > 0.5;

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
            <div className="metric-tile deepfake-probability">
              <p>Voice Clone Prob</p>
              <span className={isDeepfakeHigh ? 'high' : 'low'}>
                {Math.round(deepfake_probability * 100)}%
              </span>
            </div>
          </div>
        </div>
      </div>

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
