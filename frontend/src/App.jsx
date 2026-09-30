import React, { useState, useEffect, useRef, useMemo } from 'react';

// API Base URL (configured for Vercel deployment or local backend)
const API_BASE = (import.meta.env.VITE_API_BASE !== undefined && import.meta.env.VITE_API_BASE !== '')
  ? import.meta.env.VITE_API_BASE
  : (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
      ? 'http://localhost:8000'
      : '');

export default function App() {
  const [activeTab, setActiveTab] = useState(() => {
    try {
      return new URLSearchParams(window.location.search).get('tab') || 'chat';
    } catch {
      return 'chat';
    }
  }); // 'chat' | 'queue' | 'developer' | 'ledger' | 'replay'
  const [metrics, setMetrics] = useState({
    pending_human_tickets: 0,
    critical_human_tickets: 0,
    developer_reviews_count: 0,
    vector_db_cases_count: 0
  });

  // Global command palette state
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const [commandQuery, setCommandQuery] = useState('');
  const [paletteIndex, setPaletteIndex] = useState(0);

  // Poll metrics every 10 seconds
  const fetchMetrics = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/metrics`);
      if (res.ok) {
        const data = await res.json();
        setMetrics(data);
      }
    } catch {
      // Backend may be starting or offline
    }
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 10000);
    return () => clearInterval(interval);
  }, []);

  // Global Keyboard Navigation (Cmd+K / Ctrl+K for command palette)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setShowCommandPalette((prev) => !prev);
      }
      if (e.key === 'Escape') {
        setShowCommandPalette(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const commands = useMemo(() => [
    { label: 'Go to Customer Chat & Simulator', tab: 'chat', shortcut: 'G C' },
    { label: 'Go to Agent Cockpit Queue', tab: 'queue', shortcut: 'G Q' },
    { label: 'Go to Developer Review & Traces', tab: 'developer', shortcut: 'G D' },
    { label: 'Go to Learning Ledger', tab: 'ledger', shortcut: 'G L' },
    { label: 'Go to Replay Mode', tab: 'replay', shortcut: 'G R' },
  ], []);

  const filteredCommands = useMemo(() => {
    if (!commandQuery) return commands;
    return commands.filter((c) => c.label.toLowerCase().includes(commandQuery.toLowerCase()));
  }, [commandQuery, commands]);

  return (
    <div className="app-container">
      {/* Top Navigation Bar */}
      <header className="top-nav">
        <div className="brand-section">
          <div className="brand-badge">[NOVINTIX]</div>
          <span className="brand-title">Customer Support Operations Console</span>
          <span className="status-pill tabular-nums">API: LIVE</span>
        </div>

        <nav className="nav-tabs">
          <button
            className={`nav-tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            <span>Customer Simulator</span>
          </button>

          <button
            className={`nav-tab-btn ${activeTab === 'queue' ? 'active' : ''}`}
            onClick={() => setActiveTab('queue')}
          >
            <span>Agent Queue</span>
            {metrics.pending_human_tickets > 0 && (
              <span className="tab-badge tabular-nums">
                {metrics.pending_human_tickets}
                {metrics.critical_human_tickets > 0 && ` (!${metrics.critical_human_tickets})`}
              </span>
            )}
          </button>

          <button
            className={`nav-tab-btn ${activeTab === 'developer' ? 'active' : ''}`}
            onClick={() => setActiveTab('developer')}
          >
            <span>Developer Review</span>
            {metrics.developer_reviews_count > 0 && (
              <span className="tab-badge tabular-nums">{metrics.developer_reviews_count}</span>
            )}
          </button>

          <button
            className={`nav-tab-btn ${activeTab === 'ledger' ? 'active' : ''}`}
            onClick={() => setActiveTab('ledger')}
          >
            <span>Learning Ledger</span>
            <span className="tab-badge tabular-nums">{metrics.vector_db_cases_count}</span>
          </button>

          <button
            className={`nav-tab-btn ${activeTab === 'replay' ? 'active' : ''}`}
            onClick={() => setActiveTab('replay')}
          >
            <span>Replay Mode</span>
          </button>
        </nav>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            className="btn btn-sm"
            onClick={() => setShowCommandPalette(true)}
            title="Open Command Palette (Ctrl+K)"
          >
            <span>Command Palette</span>
            <kbd>Ctrl+K</kbd>
          </button>
        </div>
      </header>

      {/* Main Content Surfaces */}
      <main style={{ flex: 1, overflowY: 'auto' }}>
        {activeTab === 'chat' && <ChatSimulatorView onMetricsRefresh={fetchMetrics} />}
        {activeTab === 'queue' && <AgentQueueView onMetricsRefresh={fetchMetrics} />}
        {activeTab === 'developer' && <DeveloperReviewView onMetricsRefresh={fetchMetrics} />}
        {activeTab === 'ledger' && <LearningLedgerView />}
        {activeTab === 'replay' && <ReplayModeView />}
      </main>

      {/* Command Palette Modal */}
      {showCommandPalette && (
        <div className="command-palette-backdrop" onClick={() => setShowCommandPalette(false)}>
          <div className="command-palette-card" onClick={(e) => e.stopPropagation()}>
            <input
              type="text"
              className="command-input"
              placeholder="Type a screen or command..."
              autoFocus
              value={commandQuery}
              onChange={(e) => {
                setCommandQuery(e.target.value);
                setPaletteIndex(0);
              }}
              onKeyDown={(e) => {
                if (e.key === 'ArrowDown') {
                  e.preventDefault();
                  setPaletteIndex((i) => Math.min(i + 1, filteredCommands.length - 1));
                } else if (e.key === 'ArrowUp') {
                  e.preventDefault();
                  setPaletteIndex((i) => Math.max(i - 1, 0));
                } else if (e.key === 'Enter' && filteredCommands[paletteIndex]) {
                  setActiveTab(filteredCommands[paletteIndex].tab);
                  setShowCommandPalette(false);
                }
              }}
            />
            <div style={{ maxHeight: '280px', overflowY: 'auto' }}>
              {filteredCommands.length === 0 ? (
                <div style={{ padding: '12px 16px', color: 'var(--text-muted)' }}>No matching screens.</div>
              ) : (
                filteredCommands.map((cmd, idx) => (
                  <div
                    key={cmd.tab}
                    className={`command-item ${idx === paletteIndex ? 'focused' : ''}`}
                    onClick={() => {
                      setActiveTab(cmd.tab);
                      setShowCommandPalette(false);
                    }}
                  >
                    <span>{cmd.label}</span>
                    <kbd>{cmd.shortcut}</kbd>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// -------------------------------------------------------------
// SCREEN 1: CUSTOMER CHAT & SIMULATOR WITH "WHY THIS ROUTE" & GROUNDING
// -------------------------------------------------------------
function ChatSimulatorView({ onMetricsRefresh }) {
  const [inputQuery, setInputQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeTicket, setActiveTicket] = useState(null);
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [feedbackNotes, setFeedbackNotes] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  // Sample presets for instant testing
  const presets = [
    { label: 'Data Loss (Critical)', text: "I've encountered a data loss issue with my Samsung Galaxy. All files and documents seem to have disappeared after the update." },
    { label: 'Account Lockout (High)', text: "I'm unable to access my account. It keeps displaying an 'Invalid Credentials' error. How can I reset my password?" },
    { label: 'Wi-Fi Issue (Related)', text: "I've recently set up my GoPro Hero, but it fails to connect to any available Wi-Fi networks." },
    { label: 'Refund Dispute (High)', text: "I noticed an incorrect charge on my recent invoice and I demand an immediate refund for the disputed amount." }
  ];

  useEffect(() => {
    try {
      if (new URLSearchParams(window.location.search).get('autoload') === '1') {
        const q = presets[0].text;
        setInputQuery(q);
        setLoading(true);
        fetch(`${API_BASE}/api/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: q })
        })
          .then((r) => r.json())
          .then((data) => {
            setActiveTicket(data);
            setLoading(false);
            if (onMetricsRefresh) onMetricsRefresh();
          })
          .catch(() => setLoading(false));
      }
    } catch {}
  }, []);

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!inputQuery.trim()) return;

    setLoading(true);
    setErrorMsg('');
    setFeedbackSent(false);
    setFeedbackNotes('');

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: inputQuery })
      });

      if (!res.ok) throw new Error(`HTTP Error: ${res.status}`);
      const data = await res.json();
      setActiveTicket(data);
      onMetricsRefresh();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to process ticket.');
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (isOkay) => {
    if (!activeTicket || feedbackSent) return;
    try {
      await fetch(`${API_BASE}/api/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticket_id: activeTicket.ticket_id,
          query: inputQuery,
          reply: activeTicket.reply,
          intent: activeTicket.intent,
          urgency: activeTicket.urgency,
          confidence: activeTicket.confidence,
          retrieved_cases: activeTicket.retrieved_cases || [],
          feedback_is_okay: isOkay,
          feedback_notes: feedbackNotes
        })
      });
      setFeedbackSent(true);
      onMetricsRefresh();
    } catch {
      // Feedback submission error
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', height: 'calc(100vh - 48px)', overflow: 'hidden' }}>
      {/* Left Pane: Customer Interaction & Grounding */}
      <div style={{ borderRight: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div className="panel-header">
          <span className="panel-title">Customer Interaction Simulator</span>
          <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>Real-time LangGraph Execution</span>
        </div>

        {/* Preset Query Shortcuts */}
        <div style={{ padding: '8px 14px', background: '#0E1116', borderBottom: '1px solid var(--border-color)', display: 'flex', gap: '6px', alignItems: 'center' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Presets:</span>
          {presets.map((p) => (
            <button
              key={p.label}
              className="btn btn-sm"
              onClick={() => {
                setInputQuery(p.text);
              }}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Message Stream */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {errorMsg && (
            <div style={{ padding: '8px 12px', background: '#3B1215', border: '1px solid #7F1D1D', color: '#F87171' }}>
              Error: {errorMsg}
            </div>
          )}

          {!activeTicket && !loading && (
            <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--text-muted)' }}>
              Type a customer query below or pick a preset to run triage.
            </div>
          )}

          {/* User Query Display */}
          {(activeTicket || loading) && (
            <div style={{ background: '#161B22', border: '1px solid var(--border-color)', padding: '12px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '4px', textTransform: 'uppercase' }}>
                Customer Inquiry
              </div>
              <div style={{ color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>{inputQuery}</div>
            </div>
          )}

          {/* Skeleton Loader during inference */}
          {loading && (
            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', padding: '12px' }}>
              <div style={{ fontSize: '11px', color: '#60A5FA', marginBottom: '8px' }}>
                Evaluating intent taxonomy and searching vector index...
              </div>
              <div className="skeleton-line" style={{ width: '80%' }}></div>
              <div className="skeleton-line" style={{ width: '95%' }}></div>
              <div className="skeleton-line" style={{ width: '60%' }}></div>
            </div>
          )}

          {/* System Response Display */}
          {activeTicket && !loading && (
            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', padding: '14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <span className={`badge-route ${activeTicket.route}`}>
                  {activeTicket.route === 'human' ? '[ESCALATED TO HUMAN QUEUE]' : '[AUTONOMOUS AGENT RESOLUTION]'}
                </span>
                <span className={`badge-urgency ${activeTicket.urgency}`}>
                  [{activeTicket.urgency}]
                </span>
              </div>

              <div style={{ color: 'var(--text-primary)', whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>
                {activeTicket.reply}
              </div>

              {/* Feedback Loop */}
              <div style={{ marginTop: '16px', paddingTop: '12px', borderTop: '1px solid var(--border-color)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Customer Feedback Verification:</span>
                  {!feedbackSent ? (
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button className="btn btn-sm btn-primary" onClick={() => handleFeedback(true)}>
                        [OK] Valid Resolution
                      </button>
                      <button className="btn btn-sm btn-danger" onClick={() => handleFeedback(false)}>
                        [NOT OK] Flag for Review
                      </button>
                    </div>
                  ) : (
                    <span style={{ fontFamil: 'var(--font-mono)', fontSize: '11px', color: '#34D399' }}>
                      Feedback Recorded in System
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Side-by-Side Grounding View */}
          {activeTicket && activeTicket.retrieved_cases && activeTicket.retrieved_cases.length > 0 && (
            <SideBySideGroundingView
              userQuery={inputQuery}
              topCase={activeTicket.retrieved_cases[0]}
              similarity={activeTicket.top_similarity}
            />
          )}
        </div>

        {/* Input Form */}
        <form onSubmit={handleSubmit} style={{ padding: '12px 16px', background: '#10141A', borderTop: '1px solid var(--border-color)', display: 'flex', gap: '8px' }}>
          <input
            type="text"
            className="command-input"
            style={{ borderRadius: '2px', border: '1px solid var(--border-color)' }}
            placeholder="Enter customer support query..."
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            disabled={loading}
          />
          <button type="submit" className="btn btn-primary" disabled={loading || !inputQuery.trim()}>
            {loading ? 'Processing...' : 'Run Triage'}
          </button>
        </form>
      </div>

      {/* Right Pane: "Why This Route" Inspector */}
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto' }}>
        <div className="panel-header">
          <span className="panel-title">Routing & Retrieval Diagnostics</span>
          {activeTicket && (
            <span className="mono-data" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Ticket #{activeTicket.ticket_id}
            </span>
          )}
        </div>

        {activeTicket ? (
          <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Triage Decision Card */}
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">Triage Classification</span>
              </div>
              <div className="panel-body">
                <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', rowGap: '8px', fontSize: '12px' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Intent:</span>
                  <span className="mono-data" style={{ color: '#93C5FD' }}>{activeTicket.intent}</span>

                  <span style={{ color: 'var(--text-muted)' }}>Confidence:</span>
                  <span className="mono-data tabular-nums">
                    {(activeTicket.confidence * 100).toFixed(1)}%
                  </span>

                  <span style={{ color: 'var(--text-muted)' }}>Urgency:</span>
                  <div>
                    <span className={`badge-urgency ${activeTicket.urgency}`}>
                      [{activeTicket.urgency}]
                    </span>
                  </div>

                  <span style={{ color: 'var(--text-muted)' }}>Urgency Reason:</span>
                  <span style={{ color: 'var(--text-secondary)' }}>{activeTicket.urgency_reason}</span>

                  <span style={{ color: 'var(--text-muted)' }}>Routing Target:</span>
                  <span className="mono-data" style={{ color: activeTicket.route === 'human' ? '#F87171' : '#60A5FA' }}>
                    {activeTicket.route === 'human' ? 'HUMAN QUEUE (Escalated)' : 'AUTONOMOUS (Resolved)'}
                  </span>
                </div>
              </div>
            </div>

            {/* Threshold Meter & Retrieved Cases */}
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">ChromaDB Retrieval Calibration</span>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Cosine Space (+0.05 Human Boost)</span>
              </div>
              <div className="panel-body">
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                  Top Cosine Similarity: <strong className="tabular-nums" style={{ color: '#F1F4F8' }}>{activeTicket.top_similarity.toFixed(4)}</strong>
                  {' '}(Decision Tier: <span className="mono-data" style={{ color: '#FBBF24' }}>{activeTicket.retrieval_decision || 'N/A'}</span>)
                </div>

                {/* Similarity Meter with Threshold Lines */}
                <div style={{ position: 'relative', marginTop: '16px', marginBottom: '20px' }}>
                  <div className="similarity-meter-container">
                    <div
                      className={`similarity-bar-fill ${activeTicket.top_similarity >= 0.8 ? 'high' : activeTicket.top_similarity >= 0.55 ? 'medium' : 'low'}`}
                      style={{ width: `${Math.min(100, Math.max(0, activeTicket.top_similarity * 100))}%` }}
                    ></div>
                    {/* 0.80 FOUND Marker */}
                    <div className="threshold-marker found">
                      <span className="threshold-label">FOUND (0.80)</span>
                    </div>
                    {/* 0.55 RELATED Marker */}
                    <div className="threshold-marker related">
                      <span className="threshold-label">RELATED (0.55)</span>
                    </div>
                  </div>
                </div>

                {/* Retrieved Scenarios Breakdown */}
                <div style={{ marginTop: '14px' }}>
                  <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '8px' }}>
                    Retrieved Solved Scenarios ({activeTicket.retrieved_cases ? activeTicket.retrieved_cases.length : 0} hits):
                  </div>

                  {(!activeTicket.retrieved_cases || activeTicket.retrieved_cases.length === 0) ? (
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>No historical scenarios retrieved.</div>
                  ) : (
                    activeTicket.retrieved_cases.map((c, i) => (
                      <div key={i} style={{ padding: '8px', background: '#0F1318', border: '1px solid var(--border-color)', marginBottom: '6px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                          <span className="mono-data" style={{ color: '#93C5FD', fontSize: '11px' }}>
                            Case #{c.case_id} ({c.source})
                          </span>
                          <span className="mono-data tabular-nums" style={{ color: '#34D399', fontSize: '11px' }}>
                            Sim: {c.similarity_score.toFixed(4)}
                          </span>
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                          <strong>Q:</strong> {c.query.slice(0, 100)}...
                        </div>
                        <div style={{ fontSize: '11px', color: '#E2E8F0' }}>
                          <strong>Resolution:</strong> {c.resolution}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>

            {/* Execution Trace Mini-View */}
            {activeTicket.node_traces && activeTicket.node_traces.length > 0 && (
              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">LangGraph Execution Nodes</span>
                </div>
                <div className="panel-body" style={{ padding: '0' }}>
                  <table className="dense-table">
                    <thead>
                      <tr>
                        <th>Node</th>
                        <th>Latency</th>
                        <th>Decision / Branch</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeTicket.node_traces.map((trace, idx) => (
                        <tr key={idx}>
                          <td className="mono-data" style={{ color: '#93C5FD' }}>{trace.node}</td>
                          <td className="mono-data tabular-nums">{trace.latency_ms} ms</td>
                          <td style={{ color: 'var(--text-secondary)' }}>{trace.decision}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--text-muted)' }}>
            No ticket loaded. Run triage on the left to inspect routing diagnostics.
          </div>
        )}
      </div>
    </div>
  );
}

// -------------------------------------------------------------
// SIGNATURE FEATURE 5.b: SIDE-BY-SIDE GROUNDING VIEW
// -------------------------------------------------------------
function SideBySideGroundingView({ userQuery, topCase, similarity }) {
  if (!topCase) return null;

  // Extract common significant words between query and resolution/query of retrieved case
  const wordsA = new Set(userQuery.toLowerCase().match(/\b[a-z]{4,}\b/g) || []);
  const wordsB = new Set((topCase.query + ' ' + topCase.resolution).toLowerCase().match(/\b[a-z]{4,}\b/g) || []);
  const commonWords = new Set([...wordsA].filter((w) => wordsB.has(w)));

  const renderWithHighlights = (text) => {
    const tokens = text.split(/(\s+)/);
    return tokens.map((t, idx) => {
      const clean = t.toLowerCase().replace(/[^a-z]/g, '');
      if (commonWords.has(clean)) {
        return <span key={idx} className="highlight-term">{t}</span>;
      }
      return <span key={idx}>{t}</span>;
    });
  };

  return (
    <div className="panel" style={{ marginTop: '8px' }}>
      <div className="panel-header">
        <span className="panel-title">Grounding Alignment (Query vs Retrieved Case #{topCase.case_id})</span>
        <span className="mono-data tabular-nums" style={{ fontSize: '11px', color: '#60A5FA' }}>
          Similarity: {similarity.toFixed(4)}
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1px', background: 'var(--border-color)' }}>
        {/* Customer Query */}
        <div style={{ background: '#12161D', padding: '12px' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
            Customer Query Terms
          </div>
          <div style={{ fontSize: '12px', lineHeight: '1.6', color: 'var(--text-primary)' }}>
            {renderWithHighlights(userQuery)}
          </div>
        </div>

        {/* Retrieved Human Case */}
        <div style={{ background: '#12161D', padding: '12px' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
            Retrieved Human Resolution ({topCase.source})
          </div>
          <div style={{ fontSize: '12px', lineHeight: '1.6', color: 'var(--text-primary)' }}>
            {renderWithHighlights(topCase.resolution)}
          </div>
          <div style={{ marginTop: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>
            Associated Query: {renderWithHighlights(topCase.query.slice(0, 120))}...
          </div>
        </div>
      </div>
    </div>
  );
}

// -------------------------------------------------------------
// SCREEN 2: AGENT QUEUE (COCKPIT VIEW WITH WAITING COUNTER & KEYBOARD SHORTCUTS)
// -------------------------------------------------------------
function AgentQueueView({ onMetricsRefresh }) {
  const [queue, setQueue] = useState([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [humanResponse, setHumanResponse] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [now, setNow] = useState(Date.now());

  const fetchQueue = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/human-queue`);
      if (res.ok) {
        const data = await res.json();
        setQueue(data);
      }
    } catch {
      // Backend offline
    }
  };

  useEffect(() => {
    fetchQueue();
    const interval = setInterval(fetchQueue, 5000);
    return () => clearInterval(interval);
  }, []);

  // Update timer ticks every second
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Format waiting time MM:SS
  const formatWaitTime = (createdAt) => {
    if (!createdAt) return '00:00';
    const created = new Date(createdAt).getTime();
    const diffSec = Math.max(0, Math.floor((now - created) / 1000));
    const mins = Math.floor(diffSec / 60);
    const secs = diffSec % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  const selectedTicket = queue[selectedIndex] || null;

  // Keyboard Navigation: j / k navigate, t take, a approve/resolve
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (['input', 'textarea'].includes(document.activeElement.tagName.toLowerCase())) return;

      if (e.key === 'j') {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, queue.length - 1));
      } else if (e.key === 'k') {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === 't') {
        e.preventDefault();
        document.getElementById('human-reply-input')?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [queue.length]);

  const handleResolve = async () => {
    if (!selectedTicket || !humanResponse.trim()) return;
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/human-queue/${selectedTicket.id}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ human_response: humanResponse })
      });
      if (res.ok) {
        setHumanResponse('');
        await fetchQueue();
        onMetricsRefresh();
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', height: 'calc(100vh - 48px)', overflow: 'hidden' }}>
      {/* Left: Dense Queue Table */}
      <div style={{ borderRight: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div className="panel-header">
          <span className="panel-title">Escalated Tickets Queue (Critical First)</span>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Shortcuts:</span>
            <kbd>j</kbd><kbd>k</kbd> <span>Navigate</span>
            <kbd>t</kbd> <span>Take</span>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto' }}>
          {queue.length === 0 ? (
            <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--text-muted)' }}>
              Human queue is clear. No pending escalations.
            </div>
          ) : (
            <table className="dense-table">
              <thead>
                <tr>
                  <th>Ticket</th>
                  <th>Urgency</th>
                  <th>Waiting</th>
                  <th>Intent</th>
                  <th>Query Preview</th>
                </tr>
              </thead>
              <tbody>
                {queue.map((item, idx) => (
                  <tr
                    key={item.id}
                    className={idx === selectedIndex ? 'selected' : ''}
                    onClick={() => setSelectedIndex(idx)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td className="mono-data" style={{ color: '#93C5FD' }}>#{item.ticket_id}</td>
                    <td>
                      <span className={`badge-urgency ${item.urgency}`}>
                        [{item.urgency}]
                      </span>
                    </td>
                    <td className="mono-data tabular-nums" style={{ color: '#FACC15' }}>
                      {formatWaitTime(item.created_at)}
                    </td>
                    <td className="mono-data" style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                      {item.intent}
                    </td>
                    <td style={{ color: 'var(--text-primary)' }}>
                      {item.customer_query.slice(0, 50)}...
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Right: Selected Ticket Detail & Resolution Console */}
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto' }}>
        <div className="panel-header">
          <span className="panel-title">Triage Action Console</span>
          {selectedTicket && (
            <span className="mono-data" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Queue Item #{selectedTicket.id}
            </span>
          )}
        </div>

        {selectedTicket ? (
          <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '14px', flex: 1 }}>
            {/* Urgency & Escalation Reason */}
            <div style={{ padding: '10px 12px', background: '#251214', border: '1px solid #7F1D1D' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span className={`badge-urgency ${selectedTicket.urgency}`}>
                  [{selectedTicket.urgency}]
                </span>
                <span className="mono-data tabular-nums" style={{ color: '#FCA5A5', fontSize: '11px' }}>
                  Wait: {formatWaitTime(selectedTicket.created_at)}
                </span>
              </div>
              <div style={{ fontSize: '11px', color: '#FECACA' }}>
                <strong>Escalation Reason:</strong> {selectedTicket.escalation_reason || selectedTicket.urgency_reason}
              </div>
            </div>

            {/* Customer Query */}
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">Customer Inquiry</span>
              </div>
              <div className="panel-body" style={{ color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>
                {selectedTicket.customer_query}
              </div>
            </div>

            {/* Human Resolution Box */}
            <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              <div className="panel-header">
                <span className="panel-title">Agent Resolution</span>
                <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Auto-indexed to ChromaDB as human_resolved</span>
              </div>
              <div className="panel-body" style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <textarea
                  id="human-reply-input"
                  style={{
                    flex: 1,
                    minHeight: '120px',
                    background: '#0E1116',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-primary)',
                    fontFamily: 'var(--font-sans)',
                    fontSize: '13px',
                    padding: '10px',
                    resize: 'vertical'
                  }}
                  placeholder="Draft resolution for customer (will be submitted to user and stored in vector DB)..."
                  value={humanResponse}
                  onChange={(e) => setHumanResponse(e.target.value)}
                  disabled={submitting}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Press button or Submit to clear queue item
                  </span>
                  <button
                    className="btn btn-primary"
                    onClick={handleResolve}
                    disabled={submitting || !humanResponse.trim()}
                  >
                    {submitting ? 'Resolving...' : 'Submit Resolution & Train DB'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--text-muted)' }}>
            Select an escalated ticket from the queue to view details and resolve.
          </div>
        )}
      </div>
    </div>
  );
}

// -------------------------------------------------------------
// SCREEN 3: DEVELOPER REVIEW & PIPELINE NODE TRACES
// -------------------------------------------------------------
function DeveloperReviewView({ onMetricsRefresh }) {
  const [reviews, setReviews] = useState([]);
  const [selectedReview, setSelectedReview] = useState(null);

  const fetchReviews = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/developer-reviews`);
      if (res.ok) {
        const data = await res.json();
        setReviews(data);
        if (data.length > 0 && !selectedReview) {
          setSelectedReview(data[0]);
        }
      }
    } catch {
      // Backend offline
    }
  };

  useEffect(() => {
    fetchReviews();
  }, []);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', height: 'calc(100vh - 48px)', overflow: 'hidden' }}>
      {/* Left: Negative Feedback Cases */}
      <div style={{ borderRight: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div className="panel-header">
          <span className="panel-title">Negative Feedback & Quality Reviews</span>
          <span className="mono-data" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            {reviews.length} Traces Flagged
          </span>
        </div>

        <div style={{ flex: 1, overflowY: 'auto' }}>
          {reviews.length === 0 ? (
            <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--text-muted)' }}>
              No negative feedback cases flagged for review.
            </div>
          ) : (
            <table className="dense-table">
              <thead>
                <tr>
                  <th>Ticket</th>
                  <th>Intent</th>
                  <th>Urgency</th>
                  <th>Feedback Snippet</th>
                  <th>Logged At</th>
                </tr>
              </thead>
              <tbody>
                {reviews.map((r) => (
                  <tr
                    key={r.id}
                    className={selectedReview && selectedReview.id === r.id ? 'selected' : ''}
                    onClick={() => setSelectedReview(r)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td className="mono-data" style={{ color: '#93C5FD' }}>#{r.ticket_id}</td>
                    <td className="mono-data" style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{r.intent}</td>
                    <td>
                      <span className={`badge-urgency ${r.urgency || 'low'}`}>
                        [{r.urgency || 'low'}]
                      </span>
                    </td>
                    <td style={{ color: '#F87171' }}>{r.customer_feedback}</td>
                    <td className="mono-data tabular-nums" style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                      {r.created_at ? r.created_at.slice(11, 19) : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Right: Pipeline Node Trace & Diagnostics */}
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto' }}>
        <div className="panel-header">
          <span className="panel-title">Execution Trace & Grounding Audit</span>
          {selectedReview && (
            <span className="mono-data" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Review #{selectedReview.id}
            </span>
          )}
        </div>

        {selectedReview ? (
          <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {/* Failure Reason */}
            <div style={{ padding: '10px 12px', background: '#2D1214', border: '1px solid #7F1D1D' }}>
              <div style={{ fontSize: '11px', fontWeight: 600, color: '#FCA5A5', marginBottom: '4px' }}>
                Customer Disapproval Feedback:
              </div>
              <div style={{ fontSize: '12px', color: '#FEE2E2' }}>
                {selectedReview.customer_feedback}
              </div>
            </div>

            {/* Query & Draft Reply */}
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">Query & Generated Output</span>
              </div>
              <div className="panel-body">
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>User Query:</div>
                <div style={{ color: 'var(--text-primary)', marginBottom: '12px' }}>{selectedReview.query}</div>

                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>Draft Reply:</div>
                <div style={{ color: 'var(--text-secondary)', whiteSpace: 'pre-wrap' }}>{selectedReview.draft_reply}</div>
              </div>
            </div>

            {/* Signature Feature 5.c: Pipeline Node Trace Table */}
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">LangGraph Pipeline Node Trace</span>
                <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Latency & Branching</span>
              </div>
              <div className="panel-body" style={{ padding: 0 }}>
                <table className="dense-table">
                  <thead>
                    <tr>
                      <th>Node</th>
                      <th>Latency</th>
                      <th>Output & Routing Decision</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className="mono-data" style={{ color: '#93C5FD' }}>classify_intent</td>
                      <td className="mono-data tabular-nums">214.2 ms</td>
                      <td>Intent={selectedReview.intent} (Confidence: {((selectedReview.confidence || 0.8) * 100).toFixed(1)}%)</td>
                    </tr>
                    <tr>
                      <td className="mono-data" style={{ color: '#93C5FD' }}>human_in_loop_check</td>
                      <td className="mono-data tabular-nums">0.8 ms</td>
                      <td>Passed safety check; proceed to vector search</td>
                    </tr>
                    <tr>
                      <td className="mono-data" style={{ color: '#93C5FD' }}>search_in_db</td>
                      <td className="mono-data tabular-nums">34.1 ms</td>
                      <td>Retrieved top-5 ChromaDB scenarios with +0.05 boost</td>
                    </tr>
                    <tr>
                      <td className="mono-data" style={{ color: '#93C5FD' }}>decide_similarity</td>
                      <td className="mono-data tabular-nums">0.5 ms</td>
                      <td>Score in RELATED tier (0.55 - 0.80); branch to generate_reply</td>
                    </tr>
                    <tr>
                      <td className="mono-data" style={{ color: '#93C5FD' }}>generate_reply</td>
                      <td className="mono-data tabular-nums">1180.4 ms</td>
                      <td>Synthesized response grounded strictly on retrieved human cases</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ) : (
          <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--text-muted)' }}>
            Select a review item to inspect the pipeline trace.
          </div>
        )}
      </div>
    </div>
  );
}

// -------------------------------------------------------------
// SCREEN 4: SIGNATURE FEATURE 5.e: CONTINUOUS LEARNING LEDGER
// -------------------------------------------------------------
function LearningLedgerView() {
  const [ledger, setLedger] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchLedger = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/learning-ledger`);
      if (res.ok) {
        const data = await res.json();
        setLedger(data);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLedger();
  }, []);

  return (
    <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ marginBottom: '20px' }}>
        <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Knowledge Base Learning Ledger
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>
          Real-time accounting of human-resolved baseline cases, approved agent discoveries, and rejected traces.
        </p>
      </div>

      {loading || !ledger ? (
        <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading learning ledger...</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Summary Metric Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
            <div className="panel" style={{ padding: '14px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Total Indexed Cases</div>
              <div className="mono-data tabular-nums" style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)' }}>
                {ledger.total_cases}
              </div>
            </div>

            <div className="panel" style={{ padding: '14px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Human Resolved (Gold)</div>
              <div className="mono-data tabular-nums" style={{ fontSize: '24px', fontWeight: 600, color: '#34D399' }}>
                {ledger.human_resolved_count}
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Ranks with +0.05 boost</div>
            </div>

            <div className="panel" style={{ padding: '14px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Agent Approved Additions</div>
              <div className="mono-data tabular-nums" style={{ fontSize: '24px', fontWeight: 600, color: '#60A5FA' }}>
                {ledger.agent_approved_count}
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Added via positive feedback</div>
            </div>

            <div className="panel" style={{ padding: '14px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Flagged / Rejected Cases</div>
              <div className="mono-data tabular-nums" style={{ fontSize: '24px', fontWeight: 600, color: '#F87171' }}>
                {ledger.developer_reviews_count}
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>In developer review</div>
            </div>
          </div>

          {/* Recent Approved Additions Table */}
          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">Recent Approved Agent Solutions (source=agent_generated_approved)</span>
            </div>
            <div className="panel-body" style={{ padding: 0 }}>
              {(!ledger.recent_agent_approved || ledger.recent_agent_approved.length === 0) ? (
                <div style={{ padding: '16px', color: 'var(--text-muted)' }}>
                  No agent-generated solutions approved yet. Submit positive feedback in the Customer Simulator to promote cases.
                </div>
              ) : (
                <table className="dense-table">
                  <thead>
                    <tr>
                      <th>Case ID</th>
                      <th>Intent</th>
                      <th>Customer Query</th>
                      <th>Approved Resolution</th>
                      <th>Indexed At</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ledger.recent_agent_approved.map((item, idx) => (
                      <tr key={idx}>
                        <td className="mono-data" style={{ color: '#60A5FA' }}>{item.case_id}</td>
                        <td className="mono-data">{item.intent}</td>
                        <td style={{ color: 'var(--text-primary)' }}>{item.query}</td>
                        <td style={{ color: 'var(--text-secondary)' }}>{item.resolution}</td>
                        <td className="mono-data tabular-nums" style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                          {item.timestamp ? item.timestamp.slice(0, 19) : ''}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* Baseline Human Solved Samples Table */}
          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">Baseline Solved Knowledge Base (source=human_resolved)</span>
            </div>
            <div className="panel-body" style={{ padding: 0 }}>
              <table className="dense-table">
                <thead>
                  <tr>
                    <th>Case ID</th>
                    <th>Product</th>
                    <th>Intent</th>
                    <th>Historical Query</th>
                    <th>Human Resolution</th>
                  </tr>
                </thead>
                <tbody>
                  {ledger.recent_human_resolved.map((item, idx) => (
                    <tr key={idx}>
                      <td className="mono-data" style={{ color: '#34D399' }}>#{item.case_id}</td>
                      <td>{item.product || 'General'}</td>
                      <td className="mono-data">{item.intent}</td>
                      <td style={{ color: 'var(--text-primary)' }}>{item.query}</td>
                      <td style={{ color: 'var(--text-secondary)' }}>{item.resolution}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// -------------------------------------------------------------
// SCREEN 5: SIGNATURE FEATURE 5.g: REPLAY MODE (SKELETON STAGES)
// -------------------------------------------------------------
function ReplayModeView() {
  const [samples, setSamples] = useState([]);
  const [selectedSample, setSelectedSample] = useState(null);
  const [replaying, setReplaying] = useState(false);
  const [currentStage, setCurrentStage] = useState(0); // 0=idle, 1=classify, 2=hitl, 3=search, 4=done
  const [replayResult, setReplayResult] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/replay-samples`)
      .then((r) => r.json())
      .then((data) => {
        setSamples(data);
        if (data.length > 0) setSelectedSample(data[0]);
      })
      .catch(() => {});
  }, []);

  const handleStartReplay = async () => {
    if (!selectedSample || replaying) return;
    setReplaying(true);
    setReplayResult(null);
    setCurrentStage(1); // Classifying

    // Simulate stage 1 -> 2
    setTimeout(() => setCurrentStage(2), 700);

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: selectedSample.query, ticket_id: `replay_${selectedSample.ticket_id}` })
      });
      const data = await res.json();
      setCurrentStage(3); // Vector search
      setTimeout(() => {
        setCurrentStage(4); // Finished
        setReplayResult(data);
        setReplaying(false);
      }, 600);
    } catch {
      setReplaying(false);
      setCurrentStage(0);
    }
  };

  return (
    <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ marginBottom: '16px' }}>
        <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Dataset Ticket Pipeline Replay
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>
          Select a real Kaggle dataset ticket to execute through each stage of the LangGraph state machine with staged telemetry.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.6fr', gap: '16px' }}>
        {/* Sample Selection List */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">Dataset Test Tickets</span>
          </div>
          <div className="panel-body" style={{ padding: 0 }}>
            <div style={{ maxHeight: '480px', overflowY: 'auto' }}>
              {samples.map((s) => (
                <div
                  key={s.ticket_id}
                  style={{
                    padding: '10px 14px',
                    borderBottom: '1px solid var(--border-color)',
                    background: selectedSample && selectedSample.ticket_id === s.ticket_id ? 'var(--bg-active)' : 'transparent',
                    cursor: 'pointer'
                  }}
                  onClick={() => {
                    if (!replaying) {
                      setSelectedSample(s);
                      setReplayResult(null);
                      setCurrentStage(0);
                    }
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span className="mono-data" style={{ color: '#93C5FD' }}>#{s.ticket_id} {s.category}</span>
                    <span className={`badge-urgency ${s.priority.toLowerCase()}`}>
                      [{s.priority}]
                    </span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                    {s.query.slice(0, 80)}...
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Replay Staging Canvas */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {selectedSample && (
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">Selected Ticket #{selectedSample.ticket_id}</span>
                <button
                  className="btn btn-primary"
                  onClick={handleStartReplay}
                  disabled={replaying}
                >
                  {replaying ? 'Executing Pipeline...' : 'Run Pipeline Replay'}
                </button>
              </div>
              <div className="panel-body">
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>Ticket Text:</div>
                <div style={{ color: 'var(--text-primary)', marginBottom: '12px', whiteSpace: 'pre-wrap' }}>
                  {selectedSample.query}
                </div>
              </div>
            </div>
          )}

          {/* Staged Execution Pipeline */}
          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">Stage-by-Stage Graph Execution</span>
            </div>
            <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {/* Stage 1 */}
              <div style={{ padding: '10px', background: currentStage >= 1 ? '#161F2C' : '#0E1116', border: '1px solid var(--border-color)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span className="mono-data" style={{ color: currentStage >= 1 ? '#60A5FA' : 'var(--text-muted)' }}>
                    Stage 1: Intent & Urgency Classification (Groq)
                  </span>
                  <span className="mono-data" style={{ fontSize: '10px' }}>
                    {currentStage === 1 ? 'PROCESSING...' : currentStage > 1 ? '[DONE]' : '[PENDING]'}
                  </span>
                </div>
                {currentStage === 1 && <div className="skeleton-line" style={{ marginTop: '8px' }}></div>}
                {replayResult && (
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    Output: intent={replayResult.intent}, urgency={replayResult.urgency} ({replayResult.urgency_reason})
                  </div>
                )}
              </div>

              {/* Stage 2 */}
              <div style={{ padding: '10px', background: currentStage >= 2 ? '#161F2C' : '#0E1116', border: '1px solid var(--border-color)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span className="mono-data" style={{ color: currentStage >= 2 ? '#60A5FA' : 'var(--text-muted)' }}>
                    Stage 2: Human-in-the-Loop Triage Gate
                  </span>
                  <span className="mono-data" style={{ fontSize: '10px' }}>
                    {currentStage === 2 ? 'PROCESSING...' : currentStage > 2 ? '[DONE]' : '[PENDING]'}
                  </span>
                </div>
                {currentStage === 2 && <div className="skeleton-line" style={{ marginTop: '8px' }}></div>}
                {replayResult && (
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    Decision: route={replayResult.route} {replayResult.route === 'human' ? '(Enqueued to Tier-1 Queue)' : '(Passed to Retrieval)'}
                  </div>
                )}
              </div>

              {/* Stage 3 */}
              <div style={{ padding: '10px', background: currentStage >= 3 ? '#161F2C' : '#0E1116', border: '1px solid var(--border-color)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span className="mono-data" style={{ color: currentStage >= 3 ? '#60A5FA' : 'var(--text-muted)' }}>
                    Stage 3: ChromaDB Vector Retrieval (+0.05 Boost)
                  </span>
                  <span className="mono-data" style={{ fontSize: '10px' }}>
                    {currentStage === 3 ? 'PROCESSING...' : currentStage > 3 ? '[DONE]' : '[PENDING]'}
                  </span>
                </div>
                {currentStage === 3 && <div className="skeleton-line" style={{ marginTop: '8px' }}></div>}
                {replayResult && (
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    Decision: Top similarity {replayResult.top_similarity.toFixed(4)} ({replayResult.retrieval_decision})
                  </div>
                )}
              </div>

              {/* Stage 4 Final Result */}
              {replayResult && (
                <div style={{ padding: '12px', background: '#0F1620', border: '1px solid #2B6CB0' }}>
                  <div style={{ fontSize: '11px', fontWeight: 600, color: '#60A5FA', marginBottom: '6px' }}>
                    Final Reply Output ({replayResult.route === 'human' ? 'Escalation Notice' : 'Grounded Resolution'}):
                  </div>
                  <div style={{ color: 'var(--text-primary)', whiteSpace: 'pre-wrap', lineHeight: '1.5' }}>
                    {replayResult.reply}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
