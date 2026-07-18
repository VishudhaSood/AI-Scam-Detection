import React, { useState, useRef, useEffect } from 'react';
import AnalysisDetails from './AnalysisDetails';

const WS_URL = 'ws://127.0.0.1:8000/api/v1/ws/live';
const CHUNK_MS = 5000; // MediaRecorder timeslice: one binary frame every 5s

const LiveCallMonitor = ({ header }) => {
  // Session status drives the whole UI: idle -> connecting -> live -> stopping -> ended
  const [status, setStatus] = useState('idle');
  const [callerNumber, setCallerNumber] = useState('');
  const [update, setUpdate] = useState(null);       // latest LiveUpdate from server
  const [finalResult, setFinalResult] = useState(null); // LiveFinal (renders via AnalysisDetails)
  const [error, setError] = useState(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // Mutable machinery lives in refs: changing these must not re-render the UI
  const wsRef = useRef(null);
  const recorderRef = useRef(null);
  const streamRef = useRef(null);

  const releaseMic = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  };

  // Safety net: leaving the tab/page mid-session must free the mic and socket
  useEffect(() => {
    return () => {
      if (recorderRef.current && recorderRef.current.state !== 'inactive') {
        recorderRef.current.stop();
      }
      releaseMic();
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.close();
      }
    };
  }, []);

  // Smooth UI timer ticking every second during live monitoring
  useEffect(() => {
    let timerId = null;
    if (status === 'live') {
      timerId = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
    } else if (status === 'idle' || status === 'connecting') {
      setElapsedSeconds(0);
    }
    return () => {
      if (timerId) {
        clearInterval(timerId);
      }
    };
  }, [status]);

  const startMonitoring = async () => {
    setError(null);
    setUpdate(null);
    setFinalResult(null);
    setElapsedSeconds(0);

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      console.error('Microphone access failed:', err);
      setError('Could not access microphone. Please check permissions and try again.');
      return;
    }
    streamRef.current = stream;
    setStatus('connecting');

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      // Protocol: the first frame must be the JSON "start" control message
      ws.send(JSON.stringify({ type: 'start', caller_number: callerNumber.trim() || null }));

      const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '';
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      recorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        // One continuous recorder => only chunk #1 carries the webm header,
        // so the server can byte-append chunks into a single valid file.
        if (e.data && e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
          ws.send(e.data);
        }
      };

      recorder.onstop = () => {
        // dataavailable (final flush) is guaranteed to fire before onstop,
        // so by now every chunk is on the wire and "end" can go out safely.
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'end' }));
        }
        releaseMic();
      };

      recorder.start(CHUNK_MS);
      setStatus('live');
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === 'update') {
        setUpdate(msg);
      } else if (msg.type === 'final') {
        setFinalResult(msg);
        setStatus('ended');
      }
    };

    ws.onerror = () => {
      setError('Connection to the live monitor failed. Is the backend running?');
    };

    ws.onclose = () => {
      releaseMic();
      // If the socket died before the final report arrived, fall back to idle
      setStatus((prev) => (prev === 'ended' ? 'ended' : 'idle'));
    };
  };

  const stopMonitoring = () => {
    setStatus('stopping');
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      recorderRef.current.stop(); // triggers final flush -> "end" -> server "final"
    }
  };

  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const isRunning = status === 'live' || status === 'connecting' || status === 'stopping';

  return (
    <>
      {/* Left Column: Session Controls */}
      <div className="glass-panel upload-card">
        <h2>Live Call Guardian</h2>
        <p className="subtitle">Put the call on speakerphone near this device to monitor it in real time</p>

        {header}

        <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
          Caller number (optional, used in the complaint report)
        </label>
        <input
          type="text"
          value={callerNumber}
          onChange={(e) => setCallerNumber(e.target.value)}
          disabled={isRunning}
          placeholder="+91 ..."
          style={{
            width: '100%',
            padding: '0.6rem 0.8rem',
            marginBottom: '1.25rem',
            background: 'var(--bg-tertiary, rgba(255,255,255,0.05))',
            border: '1px solid var(--border-light, rgba(255,255,255,0.15))',
            borderRadius: '0.5rem',
            color: 'inherit',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.85rem',
          }}
        />

        <div
          className="dropzone"
          style={{
            cursor: 'default',
            borderStyle: status === 'live' ? 'solid' : 'dashed',
            borderColor: status === 'live' ? 'var(--color-scam)' : 'rgba(255,255,255,0.15)',
          }}
        >
          {status === 'live' || status === 'stopping' ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem', width: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <div className="status-dot" style={{ backgroundColor: 'var(--color-scam)', boxShadow: '0 0 8px var(--color-scam)' }}></div>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--color-scam)', fontSize: '0.8rem' }}>
                  {status === 'stopping' ? 'FINALIZING SESSION...' : 'LIVE MONITORING'}
                </span>
              </div>
              <div style={{ fontSize: '2.5rem', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                {formatDuration(elapsedSeconds)}
              </div>
              <button
                type="button"
                onClick={stopMonitoring}
                disabled={status === 'stopping'}
                className="submit-btn"
                style={{ background: 'var(--color-scam)', width: 'auto', padding: '0.6rem 1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
              >
                <span style={{ fontSize: '0.8rem' }}>■</span> End Session
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
              <div className="dropzone-icon" style={{ color: 'var(--accent-purple)', filter: 'drop-shadow(0 0 8px rgba(139, 92, 246, 0.3))' }}>
                <svg style={{ width: '3rem', height: '3rem' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                </svg>
              </div>
              <p style={{ fontWeight: 500 }}>
                {status === 'connecting' ? 'Connecting to monitor...' : 'Speakerphone Live Monitor'}
              </p>
              <button
                type="button"
                onClick={startMonitoring}
                disabled={status === 'connecting'}
                className="submit-btn"
                style={{ width: 'auto', padding: '0.6rem 1.5rem' }}
              >
                {status === 'ended' ? 'Start New Session' : 'Start Live Monitor'}
              </button>
            </div>
          )}
        </div>

        {error && (
          <div style={{
            color: 'var(--color-scam)',
            background: 'rgba(239, 68, 68, 0.1)',
            padding: '0.75rem',
            borderRadius: '0.5rem',
            fontSize: '0.85rem',
            marginTop: '1.25rem',
            border: '1px solid rgba(239, 68, 68, 0.2)',
          }}>
            {error}
          </div>
        )}
      </div>

      {/* Right Column: Live Transcript & Risk (plain rendering for M7) */}
      <div>
        {finalResult ? (
          <AnalysisDetails data={finalResult} />
        ) : (status === 'live' || status === 'stopping' || update) ? (
          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '1rem' }}>
              <h3 style={{ margin: 0 }}>Live Risk</h3>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem' }}>
                {update ? `${update.risk_raw.toFixed(2)} — ${update.label}` : "0.10 — SAFE"}
              </span>
            </div>
            <div style={{
              background: 'rgba(0,0,0,0.25)',
              borderRadius: '0.5rem',
              padding: '1rem',
              minHeight: '12rem',
              maxHeight: '24rem',
              overflowY: 'auto',
              fontSize: '0.9rem',
              lineHeight: 1.6,
            }}>
              <span>{update ? update.transcript_committed : ""}</span>
              {/* Partial tail may still be revised next cycle -> styled as tentative */}
              <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
                {update ? update.transcript_partial : ""}
              </span>
              {(!update || (!update.transcript_committed && !update.transcript_partial)) && (
                <span style={{ color: 'var(--text-muted)' }}>Listening…</span>
              )}
            </div>
          </div>
        ) : (
          <div className="glass-panel placeholder-box">
            <div className="placeholder-icon">📞</div>
            <h3>No Active Session</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', maxWidth: '300px' }}>
              Start the live monitor and put your call on speakerphone. Transcript and risk updates appear here every few seconds.
            </p>
          </div>
        )}
      </div>
    </>
  );
};

export default LiveCallMonitor;
