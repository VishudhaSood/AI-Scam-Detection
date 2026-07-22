import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

const LoginModal = ({ isOpen, onClose }) => {
  const { login, register } = useAuth();
  const [mode, setMode] = useState('login'); // 'login' | 'signup'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (!isOpen) return null;

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      if (mode === 'login') await login(email.trim(), password);
      else await register(email.trim(), password);
      setEmail('');
      setPassword('');
      onClose();
    } catch (err) {
      setError(err.message || 'Something went wrong.');
    } finally {
      setBusy(false);
    }
  };

  const inputStyle = {
    width: '100%', padding: '0.6rem 0.75rem', fontSize: '0.85rem', marginTop: '0.25rem',
    background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.15)',
    borderRadius: '0.5rem', color: '#fff',
  };

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(8px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 1200, padding: '1.5rem',
    }}>
      <div className="glass-panel" style={{
        width: '100%', maxWidth: '400px', padding: '1.75rem',
        background: 'var(--bg-secondary, #111827)',
        border: '1px solid var(--border-light, rgba(255,255,255,0.15))',
        borderRadius: '0.75rem', boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
          <h3 style={{ margin: 0, fontSize: '1.2rem', color: '#fff' }}>
            {mode === 'login' ? '🔐 Log in' : '✨ Create account'}
          </h3>
          <button type="button" onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '1.4rem', cursor: 'pointer' }}>✕</button>
        </div>
        <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '0 0 1.1rem 0' }}>
          Optional — sign in to keep a private audit history. You can keep using the app without an account.
        </p>

        <form onSubmit={submit}>
          <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            Email
            <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" style={inputStyle} />
          </label>
          <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'block', marginTop: '0.9rem' }}>
            Password {mode === 'signup' && <span style={{ color: 'var(--text-muted)' }}>(min 6 characters)</span>}
            <input type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" style={inputStyle} />
          </label>

          {error && (
            <div style={{ marginTop: '0.9rem', color: 'var(--color-scam, #ef4444)', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', padding: '0.5rem 0.65rem', borderRadius: '0.5rem', fontSize: '0.78rem' }}>
              {error}
            </div>
          )}

          <button type="submit" className="submit-btn" disabled={busy} style={{ width: '100%', marginTop: '1.1rem', opacity: busy ? 0.6 : 1, cursor: busy ? 'not-allowed' : 'pointer' }}>
            {busy ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}
          </button>
        </form>

        <div style={{ marginTop: '1rem', textAlign: 'center', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
          {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
          <button
            type="button"
            onClick={() => { setMode(mode === 'login' ? 'signup' : 'login'); setError(''); }}
            style={{ background: 'none', border: 'none', color: 'var(--accent-purple, #8b5cf6)', cursor: 'pointer', fontWeight: 600, padding: 0 }}
          >
            {mode === 'login' ? 'Sign up' : 'Log in'}
          </button>
        </div>

        <div style={{ marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(255,255,255,0.08)', fontSize: '0.7rem', color: 'var(--text-muted)', textAlign: 'center' }}>
          Demo account: <span style={{ fontFamily: 'var(--font-mono)' }}>demo@aiscamguard.local</span> / <span style={{ fontFamily: 'var(--font-mono)' }}>demo1234</span>
        </div>
      </div>
    </div>
  );
};

export default LoginModal;
