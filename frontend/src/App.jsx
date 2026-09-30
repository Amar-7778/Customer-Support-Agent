import React, { useState, useEffect } from 'react';

const API_BASE = '/api';

export default function App() {
  const [activeTab, setActiveTab] = useState('chat'); // 'chat' | 'queue' | 'dev'
  const [metrics, setMetrics] = useState({
    pending_human_tickets: 0,
    critical_human_tickets: 0,
    developer_reviews_count: 0,
    vector_db_cases_count: 0
  });

  // Chat State
  const [query, setQuery] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentResponse, setCurrentResponse] = useState(null);
  const [feedbackGiven, setFeedbackGiven] = useState(null); // 'okay' | 'not_okay'
  const [feedbackNotes, setFeedbackNotes] = useState('');
  const [showNotesInput, setShowNotesInput] = useState(false);
  const [showGroundingCases, setShowGroundingCases] = useState(false);

  // Queue State
  const [queueTickets, setQueueTickets] = useState([]);
  const [resolvingId, setResolvingId] = useState(null);
  const [humanResponseText, setHumanResponseText] = useState({});

  // Developer Reviews State
  const [devReviews, setDevReviews] = useState([]);

  // Fetch metrics & data
  const fetchMetrics = async () => {
    try {
      const res = await fetch(`${API_BASE}/metrics`);
      if (res.ok) {
        const data = await res.json();
        setMetrics(data);
      }
    } catch (err) {
      console.error("Failed to fetch metrics", err);
    }
  };

  const fetchQueue = async () => {
    try {
      const res = await fetch(`${API_BASE}/human-queue`);
      if (res.ok) {
        const data = await res.json();
        setQueueTickets(data);
      }
    } catch (err) {
      console.error("Failed to fetch queue", err);
    }
  };

  const fetchDevReviews = async () => {
    try {
      const res = await fetch(`${API_BASE}/developer-reviews`);
      if (res.ok) {
        const data = await res.json();
        setDevReviews(data);
      }
    } catch (err) {
      console.error("Failed to fetch reviews", err);
    }
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (activeTab === 'queue') fetchQueue();
    if (activeTab === 'dev') fetchDevReviews();
  }, [activeTab]);

  const handleSendChat = async (textToSend) => {
    const q = textToSend || query;
    if (!q.trim()) return;

    setIsProcessing(true);
    setCurrentResponse(null);
    setFeedbackGiven(null);
    setShowNotesInput(false);
    setFeedbackNotes('');

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q })
      });
      if (res.ok) {
        const data = await res.json();
        setCurrentResponse(data);
        fetchMetrics();
      } else {
        alert("Server error processing query.");
      }
    } catch (err) {
      console.error("Error sending query", err);
      alert("Network error connecting to backend.");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleFeedback = async (isOkay) => {
    if (!currentResponse) return;

    if (!isOkay && !showNotesInput) {
      setShowNotesInput(true);
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticket_id: currentResponse.ticket_id,
          query: currentResponse.query || query,
          reply: currentResponse.reply,
          intent: currentResponse.intent,
          urgency: currentResponse.urgency,
          confidence: currentResponse.confidence,
          retrieved_cases: currentResponse.retrieved_cases,
          feedback_is_okay: isOkay,
          feedback_notes: feedbackNotes
        })
      });
      if (res.ok) {
        setFeedbackGiven(isOkay ? 'okay' : 'not_okay');
        setShowNotesInput(false);
        fetchMetrics();
      }
    } catch (err) {
      console.error("Error submitting feedback", err);
    }
  };

  const handleResolveHumanTicket = async (ticketId) => {
    const responseText = humanResponseText[ticketId];
    if (!responseText || !responseText.trim()) {
      alert("Please enter a response for the customer.");
      return;
    }

    setResolvingId(ticketId);
    try {
      const res = await fetch(`${API_BASE}/human-queue/${ticketId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ human_response: responseText })
      });
      if (res.ok) {
        setHumanResponseText(prev => ({ ...prev, [ticketId]: '' }));
        fetchQueue();
        fetchMetrics();
      } else {
        alert("Failed to submit resolution.");
      }
    } catch (err) {
      console.error("Failed to resolve ticket", err);
    } finally {
      setResolvingId(null);
    }
  };

  const sampleQueries = [
    {
      label: "Critical Data Loss",
      query: "I've encountered a data loss issue with my device. All my files and documents have disappeared and work is blocked!"
    },
    {
      label: "Refund / Billing Dispute (High Risk)",
      query: "I was double charged on my credit card and need an immediate refund. I've contacted you twice already."
    },
    {
      label: "Wi-Fi Connection Issue (Standard)",
      query: "I'm having trouble connecting my smart TV to my home Wi-Fi network. It doesn't detect any available networks."
    },
    {
      label: "Account Credentials Lockout",
      query: "I'm unable to access my account. It keeps displaying 'Invalid Credentials' error even though my password is correct."
    }
  ];

  return (
    <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '24px 20px' }}>
      {/* Top Header */}
      <header style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingBottom: '24px',
        borderBottom: '1px solid var(--border-subtle)',
        marginBottom: '28px',
        flexWrap: 'wrap',
        gap: '16px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{
            width: '42px',
            height: '42px',
            borderRadius: '10px',
            background: 'var(--accent-gradient)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 20px var(--accent-glow)'
          }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
              <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
              <line x1="12" y1="22.08" x2="12" y2="12"/>
            </svg>
          </div>
          <div>
            <h1 className="font-display" style={{ fontSize: '22px', fontWeight: '700', letterSpacing: '-0.02em' }}>
              Novintix Support Intelligence
            </h1>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
              Autonomous AI Agent with Human-in-the-Loop Triage & Vector Grounding
            </p>
          </div>
        </div>

        {/* System Badges */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <div style={{
            padding: '6px 12px',
            borderRadius: '20px',
            background: 'rgba(99, 102, 241, 0.1)',
            border: '1px solid rgba(99, 102, 241, 0.25)',
            fontSize: '12px',
            color: '#a5b4fc',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}>
            <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#6366f1' }} className="animate-pulse-subtle"></span>
            Groq · Llama / GPT-OSS
          </div>
          <div style={{
            padding: '6px 12px',
            borderRadius: '20px',
            background: 'rgba(16, 185, 129, 0.1)',
            border: '1px solid rgba(16, 185, 129, 0.25)',
            fontSize: '12px',
            color: '#6ee7b7'
          }}>
            ChromaDB: {metrics.vector_db_cases_count} Solved Cases
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav style={{ display: 'flex', gap: '8px', marginBottom: '24px' }}>
        <button
          onClick={() => setActiveTab('chat')}
          style={{
            padding: '10px 20px',
            borderRadius: '10px',
            border: activeTab === 'chat' ? '1px solid var(--border-active)' : '1px solid var(--border-subtle)',
            background: activeTab === 'chat' ? 'rgba(99, 102, 241, 0.15)' : 'var(--bg-glass)',
            color: activeTab === 'chat' ? '#fff' : 'var(--text-muted)',
            fontWeight: '600',
            fontSize: '14px',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          Customer Chat
        </button>

        <button
          onClick={() => setActiveTab('queue')}
          style={{
            padding: '10px 20px',
            borderRadius: '10px',
            border: activeTab === 'queue' ? '1px solid var(--border-active)' : '1px solid var(--border-subtle)',
            background: activeTab === 'queue' ? 'rgba(99, 102, 241, 0.15)' : 'var(--bg-glass)',
            color: activeTab === 'queue' ? '#fff' : 'var(--text-muted)',
            fontWeight: '600',
            fontSize: '14px',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          Human Queue
          {metrics.pending_human_tickets > 0 && (
            <span style={{
              background: metrics.critical_human_tickets > 0 ? 'var(--critical)' : 'var(--high)',
              color: '#fff',
              fontSize: '11px',
              padding: '2px 7px',
              borderRadius: '10px',
              fontWeight: '700'
            }}>
              {metrics.pending_human_tickets}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('dev')}
          style={{
            padding: '10px 20px',
            borderRadius: '10px',
            border: activeTab === 'dev' ? '1px solid var(--border-active)' : '1px solid var(--border-subtle)',
            background: activeTab === 'dev' ? 'rgba(99, 102, 241, 0.15)' : 'var(--bg-glass)',
            color: activeTab === 'dev' ? '#fff' : 'var(--text-muted)',
            fontWeight: '600',
            fontSize: '14px',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          Developer Reviews
          {metrics.developer_reviews_count > 0 && (
            <span style={{
              background: 'rgba(255, 255, 255, 0.15)',
              color: '#f8fafc',
              fontSize: '11px',
              padding: '2px 7px',
              borderRadius: '10px',
              fontWeight: '700'
            }}>
              {metrics.developer_reviews_count}
            </span>
          )}
        </button>
      </nav>

      {/* TAB 1: CUSTOMER CHAT */}
      {activeTab === 'chat' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '20px' }}>
          {/* Preset Queries */}
          <div className="glass-panel" style={{ padding: '16px 20px' }}>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '10px', fontWeight: '500' }}>
              Quick Scenario Prompts (Test Edge Cases & Urgent Triage):
            </div>
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              {sampleQueries.map((item, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setQuery(item.query);
                    handleSendChat(item.query);
                  }}
                  style={{
                    padding: '8px 14px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-subtle)',
                    background: 'rgba(255, 255, 255, 0.04)',
                    color: 'var(--text-main)',
                    fontSize: '13px',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.04)'}
                >
                  ⚡ {item.label}
                </button>
              ))}
            </div>
          </div>

          {/* Chat Input Bar */}
          <div className="glass-panel" style={{ padding: '18px 20px' }}>
            <form onSubmit={(e) => { e.preventDefault(); handleSendChat(); }} style={{ display: 'flex', gap: '12px' }}>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Describe your issue or question (e.g. refund, crash, connection problem)..."
                disabled={isProcessing}
                style={{
                  flex: 1,
                  background: 'rgba(0, 0, 0, 0.25)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '10px',
                  padding: '14px 18px',
                  color: '#fff',
                  fontSize: '15px',
                  outline: 'none',
                  fontFamily: 'inherit'
                }}
              />
              <button
                type="submit"
                disabled={isProcessing || !query.trim()}
                style={{
                  padding: '14px 28px',
                  borderRadius: '10px',
                  border: 'none',
                  background: isProcessing ? 'var(--text-dim)' : 'var(--accent-gradient)',
                  color: '#fff',
                  fontWeight: '600',
                  fontSize: '15px',
                  cursor: isProcessing ? 'not-allowed' : 'pointer',
                  boxShadow: '0 4px 14px var(--accent-glow)',
                  transition: 'transform 0.1s ease'
                }}
              >
                {isProcessing ? 'Analyzing...' : 'Submit Ticket'}
              </button>
            </form>
          </div>

          {/* Agent Response View */}
          {currentResponse && (
            <div className="glass-panel" style={{ padding: '24px', animation: 'fadeIn 0.3s ease' }}>
              {/* Telemetry Header */}
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '12px',
                paddingBottom: '16px',
                borderBottom: '1px solid var(--border-subtle)',
                marginBottom: '20px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                  {/* Route Badge */}
                  <span style={{
                    padding: '5px 12px',
                    borderRadius: '20px',
                    fontSize: '12px',
                    fontWeight: '700',
                    letterSpacing: '0.04em',
                    textTransform: 'uppercase',
                    background: currentResponse.route === 'human' ? 'var(--high-bg)' : 'rgba(99, 102, 241, 0.15)',
                    color: currentResponse.route === 'human' ? '#f59e0b' : '#a5b4fc',
                    border: currentResponse.route === 'human' ? '1px solid var(--high-border)' : '1px solid rgba(99, 102, 241, 0.4)'
                  }}>
                    {currentResponse.route === 'human' ? '👤 Human Specialist Queue' : '🤖 Autonomous Agent'}
                  </span>

                  {/* Intent Badge */}
                  <span style={{
                    padding: '5px 12px',
                    borderRadius: '20px',
                    fontSize: '12px',
                    fontWeight: '600',
                    background: 'rgba(255, 255, 255, 0.07)',
                    color: '#e2e8f0',
                    border: '1px solid var(--border-subtle)'
                  }}>
                    Intent: {currentResponse.intent}
                  </span>

                  {/* Urgency Badge */}
                  <span style={{
                    padding: '5px 12px',
                    borderRadius: '20px',
                    fontSize: '12px',
                    fontWeight: '700',
                    textTransform: 'uppercase',
                    background: 
                      currentResponse.urgency === 'critical' ? 'var(--critical-bg)' :
                      currentResponse.urgency === 'high' ? 'var(--high-bg)' :
                      currentResponse.urgency === 'medium' ? 'var(--medium-bg)' : 'var(--low-bg)',
                    color: 
                      currentResponse.urgency === 'critical' ? 'var(--critical)' :
                      currentResponse.urgency === 'high' ? 'var(--high)' :
                      currentResponse.urgency === 'medium' ? 'var(--medium)' : 'var(--low)',
                    border: `1px solid ${
                      currentResponse.urgency === 'critical' ? 'var(--critical-border)' :
                      currentResponse.urgency === 'high' ? 'var(--high-border)' :
                      currentResponse.urgency === 'medium' ? 'var(--medium-border)' : 'var(--low-border)'
                    }`
                  }}>
                    Urgency: {currentResponse.urgency}
                  </span>

                  {/* Confidence */}
                  <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                    Confidence: {(currentResponse.confidence * 100).toFixed(0)}%
                  </span>
                </div>

                <div style={{ fontSize: '12px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                  ID: {currentResponse.ticket_id}
                </div>
              </div>

              {/* Urgency Reason Callout */}
              <div style={{
                background: 'rgba(0, 0, 0, 0.25)',
                padding: '10px 14px',
                borderRadius: '8px',
                fontSize: '13px',
                color: '#cbd5e1',
                marginBottom: '20px',
                borderLeft: `3px solid ${
                  currentResponse.urgency === 'critical' ? 'var(--critical)' :
                  currentResponse.urgency === 'high' ? 'var(--high)' : 'var(--accent-primary)'
                }`
              }}>
                <strong>Triage Assessment:</strong> {currentResponse.urgency_reason}
              </div>

              {/* Response Message */}
              <div style={{
                fontSize: '15px',
                lineHeight: '1.7',
                color: '#f8fafc',
                whiteSpace: 'pre-wrap',
                background: 'rgba(255, 255, 255, 0.02)',
                padding: '20px',
                borderRadius: '10px',
                border: '1px solid var(--border-subtle)',
                marginBottom: '24px'
              }}>
                {currentResponse.reply}
              </div>

              {/* Grounding Cases Drawer */}
              {currentResponse.retrieved_cases && currentResponse.retrieved_cases.length > 0 && (
                <div style={{ marginBottom: '24px' }}>
                  <button
                    onClick={() => setShowGroundingCases(!showGroundingCases)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#a5b4fc',
                      fontSize: '13px',
                      fontWeight: '600',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: 0
                    }}
                  >
                    <span>{showGroundingCases ? '▼ Hide' : '▶ Show'} Grounding Cases ({currentResponse.retrieved_cases.length} retrieved, top score: {currentResponse.top_similarity.toFixed(2)})</span>
                  </button>

                  {showGroundingCases && (
                    <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {currentResponse.retrieved_cases.map((c, i) => (
                        <div key={i} style={{
                          background: 'rgba(0, 0, 0, 0.3)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: '8px',
                          padding: '12px 14px',
                          fontSize: '13px'
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                            <span style={{ fontWeight: '600', color: '#e2e8f0' }}>Case #{c.case_id} ({c.source})</span>
                            <span style={{ color: '#6ee7b7' }}>Similarity: {c.similarity_score}</span>
                          </div>
                          <div style={{ color: 'var(--text-muted)', marginBottom: '4px' }}>
                            <strong>Query:</strong> {c.query}
                          </div>
                          <div style={{ color: '#cbd5e1' }}>
                            <strong>Resolution:</strong> {c.resolution}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Step 4: Customer Review Feedback (Two Options: Okay / Not okay) */}
              <div style={{
                paddingTop: '20px',
                borderTop: '1px solid var(--border-subtle)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '14px'
              }}>
                <div style={{ fontSize: '14px', fontWeight: '500', color: 'var(--text-muted)' }}>
                  Was this resolution helpful?
                </div>

                {!feedbackGiven ? (
                  <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                    <button
                      onClick={() => handleFeedback(true)}
                      style={{
                        padding: '8px 18px',
                        borderRadius: '8px',
                        border: '1px solid var(--low-border)',
                        background: 'var(--low-bg)',
                        color: 'var(--low)',
                        fontWeight: '600',
                        fontSize: '13px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                    >
                      👍 Okay
                    </button>

                    <button
                      onClick={() => handleFeedback(false)}
                      style={{
                        padding: '8px 18px',
                        borderRadius: '8px',
                        border: '1px solid var(--critical-border)',
                        background: 'var(--critical-bg)',
                        color: 'var(--critical)',
                        fontWeight: '600',
                        fontSize: '13px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                    >
                      👎 Not okay
                    </button>
                  </div>
                ) : (
                  <div style={{
                    fontSize: '13px',
                    fontWeight: '600',
                    color: feedbackGiven === 'okay' ? 'var(--low)' : 'var(--critical)'
                  }}>
                    {feedbackGiven === 'okay' 
                      ? '✓ Thank you! Case verified and indexed into ChromaDB knowledge base.' 
                      : '✓ Thank you. Telemetry dispatched to Developer Review team.'}
                  </div>
                )}
              </div>

              {/* Not Okay Feedback Input Modal/Form */}
              {showNotesInput && !feedbackGiven && (
                <div style={{ marginTop: '16px', background: 'rgba(0, 0, 0, 0.3)', padding: '16px', borderRadius: '8px' }}>
                  <label style={{ display: 'block', fontSize: '13px', marginBottom: '8px', color: '#e2e8f0' }}>
                    Please tell us what went wrong (this will be sent to the developer team):
                  </label>
                  <div style={{ display: 'flex', gap: '10px' }}>
                    <input
                      type="text"
                      value={feedbackNotes}
                      onChange={(e) => setFeedbackNotes(e.target.value)}
                      placeholder="e.g., The answer missed my specific model or didn't address the crash..."
                      style={{
                        flex: 1,
                        background: 'rgba(255, 255, 255, 0.05)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: '6px',
                        padding: '8px 12px',
                        color: '#fff',
                        fontSize: '13px'
                      }}
                    />
                    <button
                      onClick={() => handleFeedback(false)}
                      style={{
                        padding: '8px 16px',
                        borderRadius: '6px',
                        border: 'none',
                        background: 'var(--critical)',
                        color: '#fff',
                        fontWeight: '600',
                        fontSize: '13px',
                        cursor: 'pointer'
                      }}
                    >
                      Submit Trace
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: HUMAN AGENT QUEUE (Sorted by Urgency) */}
      {activeTab === 'queue' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
            <div>
              <h2 className="font-display" style={{ fontSize: '18px', fontWeight: '700' }}>
                Pending Human Triage Queue
              </h2>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                Sorted strictly by urgency (Critical cases appear first)
              </p>
            </div>
            <button
              onClick={fetchQueue}
              style={{
                padding: '6px 14px',
                borderRadius: '8px',
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid var(--border-subtle)',
                color: '#fff',
                fontSize: '13px',
                cursor: 'pointer'
              }}
            >
              🔄 Refresh Queue
            </button>
          </div>

          {queueTickets.length === 0 ? (
            <div className="glass-panel" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
              No pending tickets in human queue. All tickets currently handled by agent!
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {queueTickets.map((t) => (
                <div key={t.id} className="glass-panel" style={{
                  padding: '20px',
                  borderLeft: `4px solid ${
                    t.urgency === 'critical' ? 'var(--critical)' :
                    t.urgency === 'high' ? 'var(--high)' :
                    t.urgency === 'medium' ? 'var(--medium)' : 'var(--low)'
                  }`
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <span style={{
                        padding: '4px 10px',
                        borderRadius: '20px',
                        fontSize: '11px',
                        fontWeight: '700',
                        textTransform: 'uppercase',
                        background: t.urgency === 'critical' ? 'var(--critical-bg)' : 'var(--high-bg)',
                        color: t.urgency === 'critical' ? 'var(--critical)' : 'var(--high)',
                        border: `1px solid ${t.urgency === 'critical' ? 'var(--critical-border)' : 'var(--high-border)'}`
                      }}>
                        {t.urgency}
                      </span>
                      <span style={{ fontSize: '13px', fontWeight: '600', color: '#e2e8f0' }}>
                        Intent: {t.intent}
                      </span>
                    </div>
                    <span style={{ fontSize: '12px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                      Ticket #{t.ticket_id} · {new Date(t.created_at).toLocaleTimeString()}
                    </span>
                  </div>

                  <div style={{ fontSize: '15px', color: '#fff', marginBottom: '12px', fontWeight: '500' }}>
                    "{t.customer_query}"
                  </div>

                  <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '16px' }}>
                    <strong>Escalation Reason:</strong> {t.escalation_reason}
                  </div>

                  {/* Resolution Input */}
                  <div style={{ display: 'flex', gap: '10px' }}>
                    <textarea
                      rows={2}
                      placeholder="Type official human specialist resolution to send to customer and store in ChromaDB..."
                      value={humanResponseText[t.id] || ''}
                      onChange={(e) => setHumanResponseText({ ...humanResponseText, [t.id]: e.target.value })}
                      style={{
                        flex: 1,
                        background: 'rgba(0, 0, 0, 0.3)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: '8px',
                        padding: '10px 14px',
                        color: '#fff',
                        fontSize: '13px',
                        fontFamily: 'inherit',
                        resize: 'vertical'
                      }}
                    />
                    <button
                      onClick={() => handleResolveHumanTicket(t.id)}
                      disabled={resolvingId === t.id}
                      style={{
                        padding: '0 20px',
                        borderRadius: '8px',
                        border: 'none',
                        background: 'var(--accent-gradient)',
                        color: '#fff',
                        fontWeight: '600',
                        fontSize: '13px',
                        cursor: 'pointer',
                        whiteSpace: 'nowrap'
                      }}
                    >
                      {resolvingId === t.id ? 'Sending...' : 'Resolve & Index'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: DEVELOPER REVIEW (Negative Feedback Traces) */}
      {activeTab === 'dev' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
            <div>
              <h2 className="font-display" style={{ fontSize: '18px', fontWeight: '700' }}>
                Developer Review Traces
              </h2>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                Conversations flagged with "Not okay" customer feedback with complete execution context
              </p>
            </div>
            <button
              onClick={fetchDevReviews}
              style={{
                padding: '6px 14px',
                borderRadius: '8px',
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid var(--border-subtle)',
                color: '#fff',
                fontSize: '13px',
                cursor: 'pointer'
              }}
            >
              🔄 Refresh
            </button>
          </div>

          {devReviews.length === 0 ? (
            <div className="glass-panel" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
              No negative feedback traces logged yet. All feedback has been positive!
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {devReviews.map((r) => (
                <div key={r.id} className="glass-panel" style={{ padding: '20px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <span style={{
                        padding: '3px 8px',
                        borderRadius: '6px',
                        background: 'rgba(244, 63, 94, 0.15)',
                        color: 'var(--critical)',
                        fontSize: '12px',
                        fontWeight: '700'
                      }}>
                        Negative Feedback
                      </span>
                      <span style={{ fontSize: '13px', color: '#cbd5e1' }}>Intent: {r.intent}</span>
                      <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Urgency: {r.urgency}</span>
                    </div>
                    <span style={{ fontSize: '12px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                      Ticket #{r.ticket_id}
                    </span>
                  </div>

                  <div style={{ marginBottom: '10px', fontSize: '14px' }}>
                    <strong style={{ color: '#94a3b8' }}>Customer Query:</strong> "{r.query}"
                  </div>

                  <div style={{ marginBottom: '10px', fontSize: '14px' }}>
                    <strong style={{ color: '#94a3b8' }}>Agent Draft Reply:</strong>
                    <div style={{ background: 'rgba(0,0,0,0.25)', padding: '10px', borderRadius: '6px', marginTop: '4px', color: '#f1f5f9' }}>
                      {r.draft_reply}
                    </div>
                  </div>

                  <div style={{ marginBottom: '10px', fontSize: '14px' }}>
                    <strong style={{ color: 'var(--critical)' }}>Customer Feedback:</strong> "{r.customer_feedback}"
                  </div>

                  {r.retrieved_cases && r.retrieved_cases.length > 0 && (
                    <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: '8px' }}>
                      <strong>Retrieved Cases Grounded Upon:</strong> {r.retrieved_cases.map(c => `[#${c.case_id} (${c.similarity_score})]`).join(', ')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
