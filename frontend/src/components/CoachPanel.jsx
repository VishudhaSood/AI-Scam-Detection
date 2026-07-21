import React, { useState } from 'react';

// Live coaching card (M8). The server's state machine decides the mode and
// what guidance to send (schemas.py LiveUpdate) — this component only renders
// what it is told: suggested_questions arrive non-empty only in VERIFY,
// safe_actions only in DANGER.
const MODE_META = {
  MONITOR: {
    className: 'monitor',
    title: 'Monitoring',
    hint: 'No strong scam signals yet. Stay on speakerphone and keep listening.',
  },
  VERIFY: {
    className: 'verify',
    title: 'Verify the Caller',
    hint: 'Suspicious claims detected. Ask these questions and watch how the caller reacts:',
    fallback: 'Ask who they are and which organisation they represent, then hang up and call that organisation back on its official number.',
  },
  DANGER: {
    className: 'danger',
    title: 'High Scam Risk',
    hint: 'Strong scam patterns detected. Do not share anything. Recommended actions:',
    fallback: 'Hang up now. Never share OTPs, PINs, or card details, and make no payment. Verify by calling the official number yourself.',
  },
};

const CoachPanel = ({ update, onPrepareComplaint }) => {
  const [reactionLogged, setReactionLogged] = useState(null);
  const mode = update?.mode || 'MONITOR';
  const meta = MODE_META[mode] || MODE_META.MONITOR;
  const redFlags = update?.red_flags || [];

  // VERIFY coaches with questions to ask; DANGER with defensive actions
  const items = mode === 'VERIFY'
    ? (update?.suggested_questions || [])
    : mode === 'DANGER'
      ? (update?.safe_actions || [])
      : [];

  return (
    <div className="glass-panel coach-card">
      <div className={`coach-banner ${meta.className}`}>
        <span className="coach-mode-chip">{mode}</span>
        <div>
          <div className="coach-title">{meta.title}</div>
          <div className="coach-hint">{meta.hint}</div>
        </div>
      </div>

      {mode === 'DANGER' && onPrepareComplaint && (
        <button
          type="button"
          onClick={onPrepareComplaint}
          style={{
            marginTop: '0.75rem',
            width: '100%',
            padding: '0.6rem 1rem',
            fontSize: '0.8rem',
            fontWeight: 600,
            background: 'rgba(239, 68, 68, 0.25)',
            border: '1px solid var(--color-scam, #ef4444)',
            color: '#fff',
            borderRadius: '0.375rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem',
            boxShadow: '0 0 12px rgba(239, 68, 68, 0.3)'
          }}
        >
          🚨 Prepare Cybercrime Complaint Now (Mid-Call Shortcut)
        </button>
      )}

      {items.length > 0 ? (
        <ol className="coach-list">
          {items.map((item, idx) => (
            <li key={idx}>{item}</li>
          ))}
        </ol>
      ) : meta.fallback ? (
        <p className="coach-fallback">{meta.fallback}</p>
      ) : null}

      {/* Interactive caller reaction feedback buttons in VERIFY mode */}
      {mode === 'VERIFY' && (
        <div style={{ marginTop: '0.85rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '0.5rem', fontWeight: 600 }}>
            How did the caller react when you asked?
          </p>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={() => setReactionLogged('EVASIVE')}
              style={{
                fontSize: '0.75rem',
                padding: '0.35rem 0.65rem',
                borderRadius: '0.375rem',
                background: reactionLogged === 'EVASIVE' ? 'var(--color-scam)' : 'rgba(239,68,68,0.15)',
                border: '1px solid var(--color-scam, #ef4444)',
                color: '#fff',
                cursor: 'pointer',
                fontWeight: 500
              }}
            >
              🛑 Caller Refused / Evasive
            </button>
            <button
              type="button"
              onClick={() => setReactionLogged('THREATENED')}
              style={{
                fontSize: '0.75rem',
                padding: '0.35rem 0.65rem',
                borderRadius: '0.375rem',
                background: reactionLogged === 'THREATENED' ? 'var(--color-scam)' : 'rgba(239,68,68,0.15)',
                border: '1px solid var(--color-scam, #ef4444)',
                color: '#fff',
                cursor: 'pointer',
                fontWeight: 500
              }}
            >
              🤬 Caller Became Hostile / Angry
            </button>
          </div>
          {reactionLogged && (
            <div style={{ fontSize: '0.8rem', color: 'var(--color-scam, #ef4444)', marginTop: '0.5rem', fontWeight: 600 }}>
              ⚠️ High Risk Confirmed: Evasive or hostile reaction indicates a scam call. Hang up immediately!
            </div>
          )}
        </div>
      )}

      {redFlags.length > 0 && (
        <div style={{ marginTop: '0.85rem' }}>
          <p className="red-flag-heading">Red flags heard on this call</p>
          <div className="red-flag-chips">
            {redFlags.map((flag, idx) => (
              <span className="red-flag-chip" key={idx}>{flag}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default CoachPanel;
