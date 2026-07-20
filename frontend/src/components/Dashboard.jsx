import React, { useState, useEffect, useRef } from 'react';
import AnalysisDetails from './AnalysisDetails';
import LiveCallMonitor from './LiveCallMonitor';

const Dashboard = () => {
  const [activeTab, setActiveTab] = useState('audio'); // 'audio', 'text', or 'live'
  const [audioMode, setAudioMode] = useState('upload'); // 'upload' or 'record'
  const [textInput, setTextInput] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  // History Drawer State
  const [showHistory, setShowHistory] = useState(false);
  const [historyLogs, setHistoryLogs] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Recording State
  const [isRecording, setIsRecording] = useState(false);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const mediaRecorderRef = useRef(null);
  const recordingIntervalRef = useRef(null);
  const audioChunksRef = useRef([]);

  // Clean up Object URL on unmount or file change
  useEffect(() => {
    if (selectedFile) {
      const url = URL.createObjectURL(selectedFile);
      setAudioUrl(url);
      return () => URL.revokeObjectURL(url);
    } else {
      setAudioUrl(null);
    }
  }, [selectedFile]);

  // Clean up recording interval on unmount
  useEffect(() => {
    return () => {
      if (recordingIntervalRef.current) {
        clearInterval(recordingIntervalRef.current);
      }
    };
  }, []);

  const fetchHistory = async () => {
    setLoadingHistory(true);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/analyze/history?limit=20');
      if (res.ok) {
        const data = await res.json();
        setHistoryLogs(data);
      }
    } catch (err) {
      console.error('Failed to fetch history:', err);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleOpenHistory = () => {
    setShowHistory(true);
    fetchHistory();
  };

  const handleSelectHistoryItem = (log) => {
    setResult(log);
    setActiveTab('text'); // Switch to main tab so AnalysisDetails renders cleanly
    setShowHistory(false);
  };

  // Microphone recording handlers
  const startRecording = async () => {
    setError(null);
    setSelectedFile(null);
    audioChunksRef.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      let mimeType = 'audio/webm';
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'audio/ogg';
      }
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'audio/wav';
      }
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = '';
      }

      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      recorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: mimeType || 'audio/webm' });
        const ext = mimeType.includes('wav') ? 'wav' : mimeType.includes('ogg') ? 'ogg' : 'webm';
        const file = new File([blob], `recorded_call.${ext}`, { type: blob.type });
        setSelectedFile(file);
        stream.getTracks().forEach(track => track.stop());
      };

      recorder.start();
      setIsRecording(true);
      setRecordingDuration(0);

      recordingIntervalRef.current = setInterval(() => {
        setRecordingDuration(prev => prev + 1);
      }, 1000);

    } catch (err) {
      console.error('Error starting audio recording:', err);
      setError('Could not access microphone. Please check permissions and try again.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    if (recordingIntervalRef.current) {
      clearInterval(recordingIntervalRef.current);
      recordingIntervalRef.current = null;
    }
    setIsRecording(false);
  };

  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

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

  // Shared tab header component
  const tabSelector = (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
      <div className="tab-selector" style={{ margin: 0, flex: 1 }}>
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
        <button
          type="button"
          className={`tab-btn ${activeTab === 'live' ? 'active' : ''}`}
          onClick={() => { setActiveTab('live'); setError(null); }}
        >
          Live Monitor
        </button>
      </div>
      <button
        type="button"
        onClick={handleOpenHistory}
        style={{
          marginLeft: '0.75rem',
          padding: '0.45rem 0.8rem',
          fontSize: '0.75rem',
          background: 'rgba(139, 92, 246, 0.15)',
          border: '1px solid var(--accent-purple, #8b5cf6)',
          color: '#fff',
          borderRadius: '0.375rem',
          cursor: 'pointer',
          fontWeight: 500,
          whiteSpace: 'nowrap'
        }}
      >
        📜 Past Audits
      </button>
    </div>
  );

  // History modal markup shared across all tabs
  const historyModalMarkup = showHistory && (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0,0,0,0.75)',
      backdropFilter: 'blur(5px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '1.5rem'
    }}>
      <div className="glass-panel" style={{
        width: '100%',
        maxWidth: '650px',
        maxHeight: '80vh',
        display: 'flex',
        flexDirection: 'column',
        padding: '1.5rem',
        background: 'var(--bg-secondary, #111827)',
        border: '1px solid var(--border-light, rgba(255,255,255,0.15))'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h3 style={{ margin: 0, fontSize: '1.2rem' }}>📜 Saved Call Scan History</h3>
          <button
            type="button"
            onClick={() => setShowHistory(false)}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '1.25rem', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>

        <div style={{ overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {loadingHistory ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Loading history logs...</div>
          ) : historyLogs.length === 0 ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>No past call scans recorded yet.</div>
          ) : (
            historyLogs.map((log, idx) => (
              <div
                key={idx}
                onClick={() => handleSelectHistoryItem(log)}
                style={{
                  padding: '0.85rem 1rem',
                  background: 'rgba(255, 255, 255, 0.03)',
                  borderRadius: '0.5rem',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', overflow: 'hidden', paddingRight: '1rem' }}>
                  <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                    {log.transcript}
                  </span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {new Date(log.analyzed_at).toLocaleString()} · Category: {log.scam_category}
                  </span>
                </div>
                <span className={`risk-badge ${log.label === 'SCAM' ? 'scam' : log.label === 'SUSPICIOUS' ? 'suspicious' : 'safe'}`} style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}>
                  {log.label} ({Math.round(log.risk_score * 100)}%)
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );

  return (
    <>
      {activeTab === 'live' ? (
        <div className="dashboard-grid">
          <LiveCallMonitor header={tabSelector} />
        </div>
      ) : (
        <div className="dashboard-grid">
          {/* Left Column: Upload / Controls Card */}
          <div className="glass-panel upload-card">
            <h2>Threat Scanner</h2>
            <p className="subtitle">Submit call audio or paste a conversation to audit for scams</p>

            {tabSelector}

            {/* Form Inputs */}
            <form onSubmit={handleSubmit}>
              {activeTab === 'audio' ? (
                <>
                  {/* Audio Mode Sub-selector */}
                  <div className="audio-mode-selector" style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem' }}>
                    <button 
                      type="button" 
                      className={`tab-btn sub-tab ${audioMode === 'upload' ? 'active' : ''}`}
                      style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }}
                      onClick={() => { setAudioMode('upload'); setError(null); }}
                    >
                      Upload File
                    </button>
                    <button 
                      type="button" 
                      className={`tab-btn sub-tab ${audioMode === 'record' ? 'active' : ''}`}
                      style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }}
                      onClick={() => { setAudioMode('record'); setError(null); }}
                    >
                      Record Mic
                    </button>
                  </div>

                  {audioMode === 'upload' ? (
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
                    /* Live Mic Recording Control Box */
                    <div 
                      className="dropzone" 
                      style={{ cursor: 'default', borderStyle: isRecording ? 'solid' : 'dashed', borderColor: isRecording ? 'var(--color-scam)' : 'rgba(255,255,255,0.15)' }}
                    >
                      {isRecording ? (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem', width: '100%' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <div className="status-dot" style={{ backgroundColor: 'var(--color-scam)', boxShadow: '0 0 8px var(--color-scam)' }}></div>
                            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--color-scam)', fontSize: '0.8rem' }}>RECORDING IN PROGRESS</span>
                          </div>
                          <div style={{ fontSize: '2.5rem', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                            {formatDuration(recordingDuration)}
                          </div>
                          <button 
                            type="button" 
                            onClick={stopRecording}
                            className="submit-btn" 
                            style={{ background: 'var(--color-scam)', width: 'auto', padding: '0.6rem 1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
                          >
                            <span style={{ fontSize: '0.8rem' }}>■</span> Stop Recording
                          </button>
                        </div>
                      ) : !selectedFile ? (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
                          <div className="dropzone-icon" style={{ color: 'var(--accent-purple)', filter: 'drop-shadow(0 0 8px rgba(139, 92, 246, 0.3))' }}>
                            <svg style={{ width: '3rem', height: '3rem' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                            </svg>
                          </div>
                          <p style={{ fontWeight: 500 }}>Live Microphone Feed</p>
                          <button 
                            type="button" 
                            onClick={startRecording}
                            className="submit-btn" 
                            style={{ width: 'auto', padding: '0.6rem 1.5rem' }}
                          >
                            Start Recording
                          </button>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem', width: '100%' }}>
                          <div className="selected-file-info">
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflow: 'hidden' }}>
                              <svg style={{ width: '1.25rem', height: '1.25rem', color: 'var(--color-safe)', flexShrink: 0 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2z" />
                              </svg>
                              <span style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                                {selectedFile.name} (Recorded Call)
                              </span>
                            </div>
                            <button type="button" className="remove-file-btn" onClick={removeFile}>
                              ✕
                            </button>
                          </div>

                          {audioUrl && (
                            <div style={{ width: '100%', marginTop: '0.5rem' }}>
                              <audio src={audioUrl} controls style={{ width: '100%' }} />
                            </div>
                          )}

                          <button 
                            type="button" 
                            onClick={startRecording}
                            className="submit-btn" 
                            style={{ width: 'auto', padding: '0.5rem 1.2rem', fontSize: '0.85rem', background: 'var(--bg-tertiary)', border: '1px solid var(--border-light)' }}
                          >
                            Re-record Call
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </>
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
              Consulting RAG knowledge bases and evaluating scam threat patterns...
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
      )}

      {/* History Modal Overlay (rendered unconditionally across all tabs) */}
      {historyModalMarkup}
    </>
  );
};

export default Dashboard;
