import React, { useState, useEffect } from 'react';

const ReportModal = ({ isOpen, onClose, initialReportText, sha256Hash, data }) => {
  const [reportContent, setReportContent] = useState('');
  const [currentHash, setCurrentHash] = useState(sha256Hash || '');
  const [copied, setCopied] = useState(false);
  
  // Victim detail input state
  const [victimName, setVictimName] = useState('');
  const [bankName, setBankName] = useState('');
  const [amountLost, setAmountLost] = useState('');
  const [utrRef, setUtrRef] = useState('');

  useEffect(() => {
    if (initialReportText) {
      setReportContent(initialReportText);
    }
  }, [initialReportText]);

  useEffect(() => {
    if (sha256Hash) {
      setCurrentHash(sha256Hash);
    }
  }, [sha256Hash]);

  // Recalculate SHA-256 hash dynamically on text changes
  useEffect(() => {
    if (reportContent && window.crypto && window.crypto.subtle) {
      const encoder = new TextEncoder();
      const dataBuffer = encoder.encode(reportContent);
      window.crypto.subtle.digest('SHA-256', dataBuffer).then(hashBuffer => {
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
        setCurrentHash(hashHex);
      }).catch(err => console.error('SHA-256 computation failed:', err));
    }
  }, [reportContent]);

  if (!isOpen) return null;

  // Insert victim details into the text dynamically if typed
  const handleInsertDetails = () => {
    let extraDetails = '\n----------------------------------------------------------------------\nVICTIM & FINANCIAL LOSS DETAILS (USER SUPPLIED)\n----------------------------------------------------------------------\n';
    if (victimName) extraDetails += `Complainant Name: ${victimName}\n`;
    if (bankName) extraDetails += `Impersonated Institution / Bank: ${bankName}\n`;
    if (amountLost) extraDetails += `Financial Loss Amount: ₹${amountLost}\n`;
    if (utrRef) extraDetails += `Transaction / UTR Ref #: ${utrRef}\n`;

    if (!reportContent.includes('VICTIM & FINANCIAL LOSS DETAILS')) {
      setReportContent(prev => prev + extraDetails);
    }
  };

  const getFullFinalText = () => {
    if (reportContent.includes('DIGITAL INTEGRITY & AUDIT TRAIL')) {
      return reportContent;
    }
    return reportContent + `\n\n======================================================================\nDIGITAL INTEGRITY & AUDIT TRAIL\n======================================================================\nCryptographic SHA-256 Hash: ${currentHash}\nGenerated & Verified by AI Scam Detection Platform Engine\n======================================================================`;
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

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.8)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1100,
      padding: '1.5rem'
    }}>
      <div className="glass-panel" style={{
        width: '100%',
        maxWidth: '820px',
        maxHeight: '90vh',
        display: 'flex',
        flexDirection: 'column',
        padding: '1.5rem',
        background: 'var(--bg-secondary, #111827)',
        border: '1px solid var(--border-light, rgba(255, 255, 255, 0.15))',
        borderRadius: '0.75rem',
        boxShadow: '0 20px 40px rgba(0,0,0,0.5)'
      }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '0.75rem' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.25rem', color: '#fff', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              📝 Cybercrime Incident Complaint Editor
            </h3>
            <span style={{ fontSize: '0.7rem', color: 'var(--accent-blue, #3b82f6)', fontFamily: 'var(--font-mono)' }}>
              🛡️ Legal Audit SHA-256: {currentHash ? currentHash.substring(0, 24) + '...' : 'computing...'}
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '1.5rem', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>

        {/* Form Inputs for Victim Details */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.5rem', marginBottom: '0.75rem' }}>
          <div>
            <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '2px' }}>Your Name (Optional)</label>
            <input
              type="text"
              placeholder="e.g. Rahul Sharma"
              value={victimName}
              onChange={(e) => setVictimName(e.target.value)}
              onBlur={handleInsertDetails}
              style={{ width: '100%', padding: '0.35rem 0.6rem', fontSize: '0.75rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '0.375rem', color: '#fff' }}
            />
          </div>
          <div>
            <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '2px' }}>Bank / Institution (Optional)</label>
            <input
              type="text"
              placeholder="e.g. SBI / HDFC"
              value={bankName}
              onChange={(e) => setBankName(e.target.value)}
              onBlur={handleInsertDetails}
              style={{ width: '100%', padding: '0.35rem 0.6rem', fontSize: '0.75rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '0.375rem', color: '#fff' }}
            />
          </div>
          <div>
            <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '2px' }}>Loss Amount ₹ (Optional)</label>
            <input
              type="number"
              placeholder="e.g. 50000"
              value={amountLost}
              onChange={(e) => setAmountLost(e.target.value)}
              onBlur={handleInsertDetails}
              style={{ width: '100%', padding: '0.35rem 0.6rem', fontSize: '0.75rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '0.375rem', color: '#fff' }}
            />
          </div>
          <div>
            <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '2px' }}>UTR / Ref # (Optional)</label>
            <input
              type="text"
              placeholder="e.g. UTR123456789"
              value={utrRef}
              onChange={(e) => setUtrRef(e.target.value)}
              onBlur={handleInsertDetails}
              style={{ width: '100%', padding: '0.35rem 0.6rem', fontSize: '0.75rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '0.375rem', color: '#fff' }}
            />
          </div>
        </div>

        {/* Editable Textarea */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', marginBottom: '1rem' }}>
          <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.35rem', display: 'flex', justifyContent: 'space-between' }}>
            <span>Editable Complaint Body (Review & edit before downloading)</span>
            <span>{reportContent.length} chars</span>
          </label>
          <textarea
            value={reportContent}
            onChange={(e) => setReportContent(e.target.value)}
            rows={12}
            style={{
              width: '100%',
              flex: 1,
              padding: '0.75rem',
              fontSize: '0.8rem',
              fontFamily: 'var(--font-mono, monospace)',
              lineHeight: 1.5,
              background: 'rgba(0, 0, 0, 0.4)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              borderRadius: '0.375rem',
              color: '#f3f4f6',
              resize: 'vertical'
            }}
          />
        </div>

        {/* Government Portal Links & Action Buttons */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {/* External Links */}
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

          {/* Action Buttons */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button
              type="button"
              onClick={handleCopy}
              className="submit-btn"
              style={{ background: copied ? 'var(--color-safe, #10b981)' : 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.2)', width: 'auto', padding: '0.5rem 1.25rem', fontSize: '0.8rem' }}
            >
              {copied ? '✓ Copied to Clipboard!' : '📋 Copy Text'}
            </button>
            <button
              type="button"
              onClick={handleDownload}
              className="submit-btn"
              style={{ width: 'auto', padding: '0.5rem 1.25rem', fontSize: '0.8rem', background: 'var(--accent-purple, #8b5cf6)' }}
            >
              📥 Download Official .txt Complaint
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReportModal;
