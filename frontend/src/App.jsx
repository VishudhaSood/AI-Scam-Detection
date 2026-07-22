import React, { useState } from 'react';
import Dashboard from './components/Dashboard';
import LoginModal from './components/LoginModal';
import { useAuth } from './context/AuthContext';

function App() {
  const { user, logout } = useAuth();
  const [showLogin, setShowLogin] = useState(false);

  return (
    <div className="app-container">
      {/* Premium Header Layout */}
      <header className="header">
        <div className="logo-section">
          <div className="logo-badge">🛡️</div>
          <div className="logo-text">
            <h1>AI Scam Guard</h1>
            <p>Real-Time Fraud Evaluation Engine</p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {/* Heartbeat Status Indicator */}
          <div className="header-status">
            <div className="status-dot"></div>
            <span>ANALYSIS NETWORK ONLINE</span>
          </div>

          {/* Auth control: account + log out, or a log-in button */}
          {user ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }} title={user.email}>
                👤 {user.email}
              </span>
              <button
                type="button"
                onClick={logout}
                style={{ padding: '0.4rem 0.75rem', fontSize: '0.75rem', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.18)', color: '#fff', borderRadius: '0.375rem', cursor: 'pointer' }}
              >
                Log out
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setShowLogin(true)}
              style={{ padding: '0.45rem 0.9rem', fontSize: '0.78rem', background: 'rgba(139, 92, 246, 0.15)', border: '1px solid var(--accent-purple, #8b5cf6)', color: '#fff', borderRadius: '0.375rem', cursor: 'pointer', fontWeight: 600, whiteSpace: 'nowrap' }}
            >
              🔐 Log in
            </button>
          )}
        </div>
      </header>

      {/* Main Dashboard Control Room */}
      <main>
        <Dashboard />
      </main>

      <LoginModal isOpen={showLogin} onClose={() => setShowLogin(false)} />
    </div>
  );
}

export default App;
