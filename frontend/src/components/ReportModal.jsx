import React, { useState, useEffect } from 'react';

const ReportModal = ({
  isOpen,
  onClose,
  initialReportText,
  sha256Hash,
  isLoading,
  reportVersion,
  canRegenerate,
  onRegenerate,
}) => {
  const [copied, setCopied] = useState(false);
  const [confirmRegen, setConfirmRegen] = useState(false);

  // Complainant-supplied details. These live in state and are composed into a
  // clearly-labelled section only at output time — they are NEVER written into
  // the AI body, so they can always be corrected and they stay OUTSIDE the seal.
  const [victimName, setVictimName] = useState('');
  const [bankName, setBankName] = useState('');
  const [amountLost, setAmountLost] = useState('');
  const [utrRef, setUtrRef] = useState('');

  // The AI audit record is read-only: it is the sealed machine finding. The user
  // customises the complaint through the fields above, not by editing this text.
  const reportBody = initialReportText || '';

  // A new draft (or a regenerated one) clears the user-entered details and any
  // pending regenerate confirmation, so nothing leaks between incidents.
  useEffect(() => {
    setVictimName('');
    setBankName('');
    setAmountLost('');
    setUtrRef('');
    setConfirmRegen(false);
  }, [initialReportText]);

  if (!isOpen) return null;

  // The complainant's own details, as a separate section explicitly marked
  // user-supplied and outside the AI audit seal.
  const buildUserSection = () => {
    const lines = [];
    if (victimName) lines.push(`Complainant Name: ${victimName}`);
    if (bankName) lines.push(`Impersonated Institution / Bank: ${bankName}`);
    if (amountLost) lines.push(`Financial Loss Amount: ₹${amountLost}`);
    if (utrRef) lines.push(`Transaction / UTR Ref #: ${utrRef}`);
    if (lines.length === 0) return '';
    return (
      '\n\n======================================================================\n' +
      'COMPLAINANT-SUPPLIED DETAILS (entered by user; NOT part of the AI audit seal)\n' +
      '======================================================================\n' +
      lines.join('\n')
    );
  };

  // Final document = sealed AI body + the seal block (the server hash computed
  // over exactly that body) + the user-supplied section. The seal covers ONLY the
  // AI record above it — the user's own entries sit outside it, by design.
  const getFullFinalText = () => {
    const seal =
      '\n\n======================================================================\n' +
      'DIGITAL INTEGRITY & AUDIT SEAL\n' +
      '======================================================================\n' +
      `This SHA-256 seal covers the AI audit record above (Version ${reportVersion || 1}).\n` +
      'Any change to that record produces a different hash.\n' +
      `Cryptographic SHA-256: ${sha256Hash || '(unavailable)'}\n` +
      'Generated & Verified by AI Scam Detection Platform Engine\n' +
      '======================================================================';
    return reportBody + seal + buildUserSection();
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(getFullFinalText());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const finalText = getFullFinalText();
    const blob = new Blob([finalText], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `Cybercrime_Complaint_${new Date().toISOString().slice(0, 10)}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // Regenerating overwrites a sealed document, so it takes two clicks: the first
  // arms it (and auto-disarms after 4s), the second actually redoes it.
  const handleRegenerateClick = () => {
    if (!confirmRegen) {
      setConfirmRegen(true);
      setTimeout(() => setConfirmRegen(false), 4000);
      return;
    }
    setConfirmRegen(false);
    if (onRegenerate) onRegenerate();
  };

  const actionsDisabled = isLoading || !reportBody;
  const inputStyle = {
    width: '100%', padding: '0.35rem 0.6rem', fontSize: '0.75rem',
    background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.15)',
    borderRadius: '0.375rem', color: '#fff',
  };
  const labelStyle = { fontSize: '0.7rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '2px' };

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0, 0, 0, 0.8)', backdropFilter: 'blur(8px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 1100, padding: '1.5rem',
    }}>
      <div className="glass-panel" style={{
        width: '100%', maxWidth: '820px', maxHeight: '90vh',
        display: 'flex', flexDirection: 'column', padding: '1.5rem',
        background: 'var(--bg-secondary, #111827)',
        border: '1px solid var(--border-light, rgba(255, 255, 255, 0.15))',
        borderRadius: '0.75rem', boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '0.75rem' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.25rem', color: '#fff', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              📝 Cybercrime Incident Complaint Editor
            </h3>
            <span style={{ fontSize: '0.7rem', color: 'var(--accent-blue, #3b82f6)', fontFamily: 'var(--font-mono)' }}>
              🛡️ Audit Seal SHA-256: {isLoading ? 'sealing…' : (sha256Hash ? sha256Hash.substring(0, 24) + '…' : '(unavailable)')}
              {'  ·  '}v{reportVersion || 1}
            </span>
          </div>
          <button type="button" onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '1.5rem', cursor: 'pointer' }}>
            ✕
          </button>
        </div>

        {/* Complainant detail inputs — always live-editable, composed at output */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.5rem', marginBottom: '0.35rem' }}>
          <div>
            <label style={labelStyle}>Your Name (Optional)</label>
            <input type="text" placeholder="e.g. Rahul Sharma" value={victimName} onChange={(e) => setVictimName(e.target.value)} style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>Bank / Institution (Optional)</label>
            <input type="text" placeholder="e.g. SBI / HDFC" value={bankName} onChange={(e) => setBankName(e.target.value)} style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>Loss Amount ₹ (Optional)</label>
            <input type="number" placeholder="e.g. 50000" value={amountLost} onChange={(e) => setAmountLost(e.target.value)} style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>UTR / Ref # (Optional)</label>
            <input type="text" placeholder="e.g. UTR123456789" value={utrRef} onChange={(e) => setUtrRef(e.target.value)} style={inputStyle} />
          </div>
        </div>
        <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', margin: '0 0 0.75rem 0' }}>
          These are added as a separate “complainant-supplied” section — outside the AI seal — when you copy or download. Edit freely; corrections always apply.
        </p>

        {/* Sealed AI audit body — read-only */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', marginBottom: '1rem' }}>
          <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.35rem', display: 'flex', justifyContent: 'space-between' }}>
            <span>🔒 AI Audit Record (sealed &amp; read-only)</span>
            <span>{isLoading ? 'drafting…' : `${reportBody.length} chars`}</span>
          </label>
          <textarea
            value={isLoading ? 'Drafting complaint from the audited call record…' : reportBody}
            readOnly
            rows={12}
            style={{
              width: '100%', flex: 1, padding: '0.75rem', fontSize: '0.8rem',
              fontFamily: 'var(--font-mono, monospace)', lineHeight: 1.5,
              background: 'rgba(0, 0, 0, 0.4)', border: '1px solid rgba(255, 255, 255, 0.15)',
              borderRadius: '0.375rem', color: isLoading ? 'var(--text-muted, #9ca3af)' : '#f3f4f6',
              fontStyle: isLoading ? 'italic' : 'normal', resize: 'vertical', cursor: 'default',
            }}
          />
        </div>

        {/* Government Portal Links & Action Buttons */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <a href="https://cybercrime.gov.in" target="_blank" rel="noreferrer" className="advisory-link" style={{ fontSize: '0.7rem', padding: '0.3rem 0.6rem' }}>
              🚨 Helpline 1930 Cybercrime Portal
            </a>
            <a href="https://sancharsaathi.gov.in/sachet" target="_blank" rel="noreferrer" className="advisory-link" style={{ fontSize: '0.7rem', padding: '0.3rem 0.6rem' }}>
              🛡️ DoT Chakshu Portal
            </a>
            <a href="https://sachet.rbi.org.in" target="_blank" rel="noreferrer" className="advisory-link" style={{ fontSize: '0.7rem', padding: '0.3rem 0.6rem' }}>
              🏛️ RBI Sachet Fraud Portal
            </a>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap' }}>
            {/* Regenerate (left): only for a saved call, two-step to avoid an
                accidental overwrite of a sealed document. */}
            <div>
              {canRegenerate && (
                <button
                  type="button"
                  onClick={handleRegenerateClick}
                  disabled={isLoading}
                  className="submit-btn"
                  title="Deliberately re-draft this report; overwrites the current sealed version and bumps its version number."
                  style={{
                    width: 'auto', padding: '0.5rem 1.1rem', fontSize: '0.8rem',
                    background: confirmRegen ? 'var(--color-scam, #ef4444)' : 'rgba(255,255,255,0.08)',
                    border: '1px solid rgba(255,255,255,0.2)',
                    opacity: isLoading ? 0.45 : 1, cursor: isLoading ? 'not-allowed' : 'pointer',
                  }}
                >
                  {isLoading ? '⏳ Drafting…' : confirmRegen ? `⚠️ Confirm — overwrite sealed v${reportVersion || 1}?` : '🔄 Regenerate'}
                </button>
              )}
            </div>

            {/* Copy / Download (right) */}
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button
                type="button" onClick={handleCopy} disabled={actionsDisabled} className="submit-btn"
                style={{ background: copied ? 'var(--color-safe, #10b981)' : 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.2)', width: 'auto', padding: '0.5rem 1.25rem', fontSize: '0.8rem', opacity: actionsDisabled ? 0.45 : 1, cursor: actionsDisabled ? 'not-allowed' : 'pointer' }}
              >
                {copied ? '✓ Copied to Clipboard!' : '📋 Copy Text'}
              </button>
              <button
                type="button" onClick={handleDownload} disabled={actionsDisabled} className="submit-btn"
                style={{ width: 'auto', padding: '0.5rem 1.25rem', fontSize: '0.8rem', background: 'var(--accent-purple, #8b5cf6)', opacity: actionsDisabled ? 0.45 : 1, cursor: actionsDisabled ? 'not-allowed' : 'pointer' }}
              >
                📥 Download Official .txt Complaint
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReportModal;
