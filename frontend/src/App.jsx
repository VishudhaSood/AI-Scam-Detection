import React from 'react';
import Dashboard from './components/Dashboard';

function App() {
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
        
        {/* Heartbeat Status Indicator */}
        <div className="header-status">
          <div className="status-dot"></div>
          <span>ANALYSIS NETWORK ONLINE</span>
        </div>
      </header>

      {/* Main Dashboard Control Room */}
      <main>
        <Dashboard />
      </main>
    </div>
  );
}

export default App;
