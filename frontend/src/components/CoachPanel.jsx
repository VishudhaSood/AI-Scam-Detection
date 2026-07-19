import React from 'react';

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

const CoachPanel = ({ update }) => {
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

      {items.length > 0 ? (
        <ol className="coach-list">
          {items.map((item, idx) => (
            <li key={idx}>{item}</li>
          ))}
        </ol>
      ) : meta.fallback ? (
        <p className="coach-fallback">{meta.fallback}</p>
      ) : null}

      {redFlags.length > 0 && (
        <div>
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
