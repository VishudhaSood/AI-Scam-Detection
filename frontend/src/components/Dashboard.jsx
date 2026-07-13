import React, { useState } from 'react';
import AnalysisDetails from './AnalysisDetails';

const Dashboard = () => {
  const [activeTab, setActiveTab] = useState('audio'); // 'audio' or 'text'
  const [textInput, setTextInput] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  // Drag and Drop Handlers
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (isValidAudio(file)) {
        setSelectedFile(file);
        setError(null);
      } else {
        setError("Invalid file format. Please upload WAV, MP3, M4A, OGG, or WEBM audio.");
      }
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (isValidAudio(file)) {
        setSelectedFile(file);
        setError(null);
      } else {
        setError("Invalid file format. Please upload WAV, MP3, M4A, OGG, or WEBM audio.");
      }
    }
  };

  const isValidAudio = (file) => {
    const validExtensions = ['.wav', '.mp3', '.m4a', '.ogg', '.webm'];
    const fileName = file.name.toLowerCase();
    return validExtensions.some(ext => fileName.endsWith(ext));
  };

  const removeFile = (e) => {
    e.stopPropagation();
    setSelectedFile(null);
  };

  // Submit Handler
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    if (activeTab === 'text') {
      if (!textInput.trim()) {
        setError("Please enter a transcript text to analyze.");
        setLoading(false);
        return;
      }
      formData.append('text', textInput);
    } else {
      if (!selectedFile) {
        setError("Please select or drop an audio file.");
        setLoading(false);
        return;
      }
      formData.append('file', selectedFile);
    }

    try {
      const response = await fetch('http://127.0.0.1:8000/api/v1/analyze', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to analyze request');
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      console.error(err);
      setError(err.message || 'An error occurred during communication with the server.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="dashboard-grid">
      {/* Left Column: Upload / Controls Card */}
      <div className="glass-panel upload-card">
        <h2>Threat Scanner</h2>
        <p className="subtitle">Submit call audio or paste a conversation to audit for scams</p>

        {/* Tab Selection */}
        <div className="tab-selector">
          <button 
            type="button" 
            className={`tab-btn ${activeTab === 'audio' ? 'active' : ''}`}
            onClick={() => { setActiveTab('audio'); setError(null); }}
          >
            Call Recording
          </button>
          <button 
            type="button" 
            className={`tab-btn ${activeTab === 'text' ? 'active' : ''}`}
            onClick={() => { setActiveTab('text'); setError(null); }}
          >
            Direct Transcript
          </button>
        </div>

        {/* Form Inputs */}
        <form onSubmit={handleSubmit}>
          {activeTab === 'audio' ? (
            /* Audio File Dropzone */
            <div 
              className={`dropzone ${dragActive ? 'active' : ''}`}
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
              onClick={() => document.getElementById('audio-file-input').click()}
            >
              <input 
                id="audio-file-input"
                type="file" 
                className="file-input-hidden" 
                accept="audio/*"
                onChange={handleFileChange}
              />
              
              {!selectedFile ? (
                <>
                  <div className="dropzone-icon">
                    <svg style={{ width: '3rem', height: '3rem' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                    </svg>
                  </div>
                  <p style={{ fontWeight: 500 }}>Drag & Drop call recording</p>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Supports MP3, WAV, M4A, WEBM</p>
                </>
              ) : (
                <div className="selected-file-info">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflow: 'hidden' }}>
                    <svg style={{ width: '1.25rem', height: '1.25rem', color: 'var(--accent-blue)', flexShrink: 0 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <span style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                      {selectedFile.name}
                    </span>
                  </div>
                  <button type="button" className="remove-file-btn" onClick={removeFile}>
                    ✕
                  </button>
                </div>
              )}
            </div>
          ) : (
            /* Direct Text Transcript Input */
            <textarea
              className="text-area-input"
              placeholder="Example: 'Hello! I am calling from KBC. You have won a 25 Lakh lottery prize. To claim this, please deposit a verification processing fee...'"
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
            />
          )}

          {/* Error Message */}
          {error && (
            <div style={{ 
              color: 'var(--color-scam)', 
              background: 'rgba(239, 68, 68, 0.1)', 
              padding: '0.75rem', 
              borderRadius: '0.5rem', 
              fontSize: '0.85rem',
              marginBottom: '1.5rem',
              border: '1px solid rgba(239, 68, 68, 0.2)'
            }}>
              {error}
            </div>
          )}

          <button 
            type="submit" 
            className="submit-btn"
            disabled={loading || (activeTab === 'audio' ? !selectedFile : !textInput.trim())}
          >
            {loading ? 'Analyzing Call Pattern...' : 'Run Scam Audit'}
          </button>
        </form>
      </div>

      {/* Right Column: Dynamic Results Dashboard */}
      <div>
        {loading && (
          <div className="glass-panel loading-box">
            <div className="spinner"></div>
            <p style={{ fontWeight: 500, color: 'var(--text-secondary)' }}>
              Consulting RAG knowledge bases and analyzing voice biometrics...
            </p>
          </div>
        )}

        {!loading && !result && (
          <div className="glass-panel placeholder-box">
            <div className="placeholder-icon">🛡️</div>
            <h3>Waiting for Call Input</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', maxWidth: '300px' }}>
              Submit an audio file or copy-paste text transcript to trigger the multi-model analysis sequence.
            </p>
          </div>
        )}

        {!loading && result && (
          <AnalysisDetails data={result} />
        )}
      </div>
    </div>
  );
};

export default Dashboard;
