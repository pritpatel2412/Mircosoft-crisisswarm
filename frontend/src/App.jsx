import React, { useState, useEffect } from 'react';
import CommandMap from './components/CommandMap';
import AIScorecard from './components/AIScorecard';
import DebateChamber from './components/DebateChamber';
import HumanGate from './components/HumanGate';

const DEFAULT_MUMBAI_SCENARIO = (
  "DISASTER ALERT: 6.8 magnitude earthquake struck Mumbai at 14:32 IST. " +
  "Estimated 450 casualties across 3 zones: Dharavi (200), Kurla (150), Andheri (100). " +
  "8 buildings collapsed. Western Express Highway blocked. Bandra-Worli Sea Link operational. " +
  "12 hospitals on alert. Coordinate full emergency response immediately."
);

export default function App() {
  // --- UI Configurations ---
  const [activeTab, setActiveTab] = useState('single'); // 'single' | 'arena'
  const [scenarioText, setScenarioText] = useState(DEFAULT_MUMBAI_SCENARIO);
  const [strategy, setStrategy] = useState('default');
  const [officerName, setOfficerName] = useState('Incident Commander');
  const [strictGate, setStrictGate] = useState(false);
  const [conflictDemo, setConflictDemo] = useState(false);
  const [injectAftershock, setInjectAftershock] = useState(true);

  // --- Swarm Execution States ---
  const [mission, setMission] = useState(null);
  const [arenaResults, setArenaResults] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  // --- Crisis Replay Slider Index ---
  const [replayFrameIdx, setReplayFrameIdx] = useState(0);

  // --- Active Page Navigation and Log Filter States ---
  const [activePage, setActivePage] = useState('command'); // 'command' | 'scorecard' | 'debate' | 'arena'
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedAgentFilter, setSelectedAgentFilter] = useState('all');

  // Load default scenario on mount
  useEffect(() => {
    fetch('/api/scenarios/demo')
      .then(res => res.json())
      .then(data => {
        if (data.scenario_text) setScenarioText(data.scenario_text);
      })
      .catch(() => {});
  }, []);

  // --- Trigger Single Swarm Run ---
  const handleActivateSwarm = async () => {
    setIsLoading(true);
    setErrorMessage('');
    setArenaResults(null);
    setMission(null);

    try {
      const response = await fetch('/api/run-swarm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario_text: scenarioText,
          strategy,
          conflict_demo: conflictDemo
        })
      });

      const data = await response.json();
      if (response.ok) {
        // If human approval is not strictly required by verification AND we are not forcing it, auto-approve
        if (data.status === "awaiting_human_approval" && !strictGate && data.verification?.verification_status === "PASSED") {
          await handleFinalize(data, "approved", "Auto-approved — verifier passed", "System");
        } else {
          setMission(data);
          // Set slider to last frame
          if (data.replay?.frames) {
            setReplayFrameIdx(data.replay.frames.length - 1);
          }
        }
      } else {
        setErrorMessage(data.detail || 'Failed to activate the disaster swarm.');
      }
    } catch (err) {
      setErrorMessage('Backend server unreachable. Make sure uvicorn is running on port 8000.');
    } finally {
      setIsLoading(false);
    }
  };

  // --- Trigger Swarm Arena Comparison ---
  const handleActivateArena = async () => {
    setIsLoading(true);
    setErrorMessage('');
    setMission(null);
    setArenaResults(null);

    try {
      const response = await fetch('/api/arena', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario_text: scenarioText,
          inject_aftershock: injectAftershock
        })
      });

      const data = await response.json();
      if (response.ok) {
        setArenaResults(data);
        setActivePage('arena');
      } else {
        setErrorMessage(data.detail || 'Failed to run Swarm Arena comparison.');
      }
    } catch (err) {
      setErrorMessage('Backend server unreachable. Make sure uvicorn is running on port 8000.');
    } finally {
      setIsLoading(false);
    }
  };

  // --- Finalize Mission approval/rejection ---
  const handleFinalize = async (pendingMission, decision, notes = '', officer = officerName) => {
    setIsLoading(true);
    setErrorMessage('');
    try {
      const response = await fetch('/api/finalize-mission', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pending: pendingMission || mission,
          decision,
          officer,
          notes
        })
      });

      const data = await response.json();
      if (response.ok) {
        setMission(data);
        if (data.replay?.frames) {
          setReplayFrameIdx(data.replay.frames.length - 1);
        }
      } else {
        setErrorMessage(data.detail || 'Failed to finalize command action.');
      }
    } catch (err) {
      setErrorMessage('Failed to finalize command action.');
    } finally {
      setIsLoading(false);
    }
  };

  // --- Trigger Aftershock ---
  const handleInjectAftershock = async () => {
    if (!mission) return;
    setIsLoading(true);
    setErrorMessage('');
    try {
      const response = await fetch('/api/aftershock', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pending: mission })
      });

      const data = await response.json();
      if (response.ok) {
        setMission(data);
        if (data.replay?.frames) {
          setReplayFrameIdx(data.replay.frames.length - 1);
        }
      } else {
        setErrorMessage(data.detail || 'Failed to apply judge aftershock.');
      }
    } catch (err) {
      setErrorMessage('Failed to apply judge aftershock.');
    } finally {
      setIsLoading(false);
    }
  };

  // --- Download plain text SitRep ---
  const handleDownloadSitRep = () => {
    if (!mission) return;
    // Build identical plain text summary
    const s = mission.situation || {};
    const m = mission.metrics || {};
    const text = `
============================================================
  CRISISSWARM — INCIDENT SITUATION REPORT
============================================================
Generated: ${new Date().toISOString()}
Strategy: ${mission.strategy || 'default'}
Round: ${mission.round_label || 'initial'}
Mission Score: ${m.mission_score || 0}/100

SITUATION:
Disaster type: ${s.disaster_type || '—'}
Location: ${s.location || '—'}
Severity: ${s.severity || '—'}
Summary: ${s.summary || '—'}

MISSION METRICS:
Lives saved (simulated): ${m.lives_saved || 0}
Response time: ${m.response_time_min || 0} min
Zone coverage %: ${m.coverage_pct || 0}%

EXECUTIVE SUMMARY:
${mission.report?.text_summary || 'No summary compiled.'}
    `;

    const element = document.createElement("a");
    const file = new Blob([text], { type: 'text/plain' });
    element.href = URL.createObjectURL(file);
    element.download = "crisisswarm_sitrep.txt";
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  // --- Download Audit Log JSON ---
  const handleDownloadAudit = () => {
    if (!mission) return;
    const audit = {
      verification: mission.verification,
      human_approval: mission.human_approval,
      metrics: mission.metrics,
      debate_summary: mission.debate?.outcome_summary,
      replay_steps: mission.replay?.frames?.map(f => f.step) || [],
      digital_twin: mission.digital_twin
    };

    const element = document.createElement("a");
    const file = new Blob([JSON.stringify(audit, null, 2)], { type: 'application/json' });
    element.href = URL.createObjectURL(file);
    element.download = "crisisswarm_audit.json";
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  // --- Timeline scrub resolver ---
  const getActiveWorld = () => {
    if (!mission) return {};
    const frames = mission.replay?.frames || [];
    if (frames.length > 0 && frames[replayFrameIdx]) {
      return frames[replayFrameIdx].world || mission.digital_twin;
    }
    return mission.digital_twin || {};
  };

  const getActiveDetail = () => {
    if (!mission) return '';
    const frames = mission.replay?.frames || [];
    if (frames.length > 0 && frames[replayFrameIdx]) {
      return frames[replayFrameIdx].detail || '';
    }
    return 'Final simulation world state loaded.';
  };

  const getActiveStepLabel = () => {
    if (!mission) return '';
    const frames = mission.replay?.frames || [];
    if (frames.length > 0 && frames[replayFrameIdx]) {
      return `${replayFrameIdx}: ${frames[replayFrameIdx].step || 'Simulation Stage'}`;
    }
    return 'Final Mission Report';
  };

  const isSwarmAwaitsApproval = mission?.status === 'awaiting_human_approval';

  const filteredTranscript = (mission?.transcript || []).filter(msg => {
    const matchesAgent = selectedAgentFilter === 'all' || msg.agent === selectedAgentFilter;
    const matchesSearch = msg.message.toLowerCase().includes(searchTerm.toLowerCase()) || msg.agent.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesAgent && matchesSearch;
  });

  return (
    <div>
      {/* 1. Header Banner & Sticky Nav */}
      <div className="promo-banner">
        Frontier AI in Emergency Logistics &mdash; Powered by <strong>Groq (Llama 3.3 70B)</strong>
        <a href="https://console.groq.com/" target="_blank" rel="noreferrer">Explore Groq Console &rarr;</a>
      </div>
      
      <div className="top-nav">
        <a className="top-nav-logo" href="#active-command-center">
          CRISIS SWARM_ <span style={{ fontFamily: 'Inter', fontWeight: 400, fontSize: '14px', color: 'var(--colors-primary)' }}>COMMAND_CENTER</span>
        </a>
        <div className="top-nav-links">
          <button 
            className={`nav-link-btn ${activePage === 'command' ? 'active' : ''}`} 
            onClick={() => setActivePage('command')}
          >
            Command Center
          </button>
          <button 
            className={`nav-link-btn ${activePage === 'scorecard' ? 'active' : ''}`} 
            onClick={() => setActivePage('scorecard')}
          >
            AI Scorecard
          </button>
          <button 
            className={`nav-link-btn ${activePage === 'debate' ? 'active' : ''}`} 
            onClick={() => setActivePage('debate')}
          >
            Debate & Logs
          </button>
          <button 
            className={`nav-link-btn ${activePage === 'arena' ? 'active' : ''}`} 
            onClick={() => {
              setActivePage('arena');
              setActiveTab('arena');
            }}
          >
            Swarm Arena (A vs B)
          </button>
        </div>
        <a className="top-nav-cta" href="https://github.com/pritpatel2412/Mircosoft-crisisswarm" target="_blank" rel="noreferrer">View Repository</a>
      </div>

      <div className="app-container">
        {/* 2. Hero Sunset Band */}
        <div className="hero-band-sunset" id="active-command-center">
          <div className="hero-left">
            <div className="hero-display-text">Frontier AI.<br />In your hands.</div>
            <p className="hero-subtitle-text">
              CrisisSwarm coordinates 13 specialist agents across one situation brief, 
              triaging casualties, deploying ambulances, planning routes, and broadcasting multilingual alerts.
            </p>
          </div>
          <div className="hero-right">
            <div style={{
              width: '240px',
              height: '240px',
              borderRadius: '12px',
              background: 'linear-gradient(135deg, #FF9E2C 0%, #FF5A36 50%, #FF3E1B 100%)',
              boxShadow: 'rgba(0,0,0,0.15) 0 8px 24px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'center',
              textAlign: 'center',
              padding: '20px',
              boxSizing: 'border-box',
              border: '1px solid rgba(255,255,255,0.2)'
            }}>
              <div style={{ fontFamily: "'Playfair Display', serif", fontSize: '72px', fontWeight: '700', color: 'white', lineHeight: 1 }}>CS</div>
              <div style={{ fontFamily: "'Inter', sans-serif", fontSize: '11px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '2px', color: 'white', marginTop: '10px' }}>CRISIS SWARM</div>
            </div>
          </div>
        </div>

        {/* Display Error Message */}
        {errorMessage && (
          <div style={{
            backgroundColor: '#FFF4F2',
            border: '1px solid var(--colors-primary-deep)',
            borderLeft: '4px solid var(--colors-primary-deep)',
            padding: '16px 20px',
            borderRadius: '12px',
            color: 'var(--colors-primary-deep)',
            fontWeight: '500',
            fontSize: '14px',
            marginBottom: '24px'
          }}>
            ⚠️ {errorMessage}
          </div>
        )}

        {/* 3. Core Panels Grid */}
        <div className="control-grid">
          {/* Left Column: Contextual parameters depending on the active page */}
          
          {activePage === 'command' && (
            <div className="sidebar-panel">
              <h3 className="serif-font" style={{ fontSize: '22px', marginBottom: '16px', borderBottom: '1px solid var(--colors-beige-deep)', paddingBottom: '8px' }}>Control Panel</h3>
              
              <div className="form-group">
                <label className="form-label" htmlFor="officer">Incident Commander</label>
                <input
                  id="officer"
                  type="text"
                  className="form-input"
                  value={officerName}
                  onChange={(e) => setOfficerName(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Operation Mode</label>
                <div style={{ display: 'flex', gap: '10px', marginTop: '4px' }}>
                  <label className="radio-option">
                    <input
                      type="radio"
                      name="tabMode"
                      checked={activeTab === 'single'}
                      onChange={() => { setActiveTab('single'); setErrorMessage(''); }}
                    />
                    Single Swarm
                  </label>
                  <label className="radio-option">
                    <input
                      type="radio"
                      name="tabMode"
                      checked={activeTab === 'arena'}
                      onChange={() => { setActiveTab('arena'); setErrorMessage(''); setActivePage('arena'); }}
                    />
                    Swarm Arena
                  </label>
                </div>
              </div>

              <div className="form-group" style={{ marginTop: '16px', borderTop: '1px solid var(--colors-beige-deep)', paddingTop: '16px' }}>
                <label className="form-label" htmlFor="scenario">Disaster Prompt / Scenario</label>
                <textarea
                  id="scenario"
                  className="form-textarea"
                  value={scenarioText}
                  onChange={(e) => setScenarioText(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="strategy">Response Strategy</label>
                <select
                  id="strategy"
                  className="form-input"
                  value={strategy}
                  onChange={(e) => setStrategy(e.target.value)}
                >
                  <option value="default">Default Balanced (Commander Decision)</option>
                  <option value="medical_first">Swarm A — Medical First (Acuity Surge)</option>
                  <option value="resource_balanced">Swarm B — Resource Balanced (Even Split)</option>
                </select>
              </div>

              <div className="checkbox-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={strictGate}
                    onChange={(e) => setStrictGate(e.target.checked)}
                  />
                  <div>
                    <strong>Strict human gate</strong>
                    <span style={{ fontSize: '12px', color: 'var(--colors-steel)', display: 'block', marginTop: '2px' }}>
                      Always require Commander sign-off
                    </span>
                  </div>
                </label>
                
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={conflictDemo}
                    onChange={(e) => setConflictDemo(e.target.checked)}
                  />
                  <div>
                    <strong>Conflict demo mode</strong>
                    <span style={{ fontSize: '12px', color: 'var(--colors-steel)', display: 'block', marginTop: '2px' }}>
                      Cap ambulances to 5 to force verifier failure
                    </span>
                  </div>
                </label>
              </div>

              <button 
                className="button-primary" 
                onClick={handleActivateSwarm}
                disabled={isLoading}
                style={{ marginTop: '24px' }}
              >
                {isLoading ? 'Running Digital Simulation...' : 'ACTIVATE SWARM'}
              </button>
            </div>
          )}

          {activePage === 'scorecard' && (
            <div className="sidebar-panel">
              <h3 className="serif-font" style={{ fontSize: '22px', marginBottom: '16px', borderBottom: '1px solid var(--colors-beige-deep)', paddingBottom: '8px' }}>Safety Audit</h3>
              <p style={{ fontSize: '14px', lineHeight: '1.5', color: 'var(--colors-slate)', marginBottom: '16px' }}>
                This auditing console tracks multi-agent logistics compliance, safety thresholds, and structural constraints.
              </p>
              
              <div className="checkbox-group" style={{ borderTop: 'none', paddingTop: 0 }}>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={strictGate}
                    onChange={(e) => setStrictGate(e.target.checked)}
                  />
                  <div>
                    <strong>Strict human gate</strong>
                    <span style={{ fontSize: '12px', color: 'var(--colors-steel)', display: 'block', marginTop: '2px' }}>
                      Always require Commander sign-off
                    </span>
                  </div>
                </label>
              </div>
              
              <div style={{ marginTop: '24px', padding: '16px', backgroundColor: 'var(--colors-cream)', borderRadius: '8px', border: '1px solid var(--colors-beige-deep)' }}>
                <span style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: 'var(--colors-primary)' }}>Responsible AI Guidelines</span>
                <p style={{ fontSize: '12px', color: 'var(--colors-slate)', marginTop: '6px', lineHeight: '1.4' }}>
                  Emergency dispatch Swarms must pass five distinct verifier gates (Resource check, Routing validity, Commander sign-off, Explainable logic, Post-incident learning) before dispatching units on public roads.
                </p>
              </div>
            </div>
          )}

          {activePage === 'debate' && (
            <div className="sidebar-panel">
              <h3 className="serif-font" style={{ fontSize: '22px', marginBottom: '16px', borderBottom: '1px solid var(--colors-beige-deep)', paddingBottom: '8px' }}>Log Search</h3>
              
              <div className="form-group">
                <label className="form-label" htmlFor="search-logs">Search Message Logs</label>
                <input
                  id="search-logs"
                  type="text"
                  className="search-input"
                  placeholder="Type keywords..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Filter by Agent</label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
                  {[
                    { id: 'all', label: 'All Agent Discussions' },
                    { id: 'Commander', label: 'Commander Mediator' },
                    { id: 'Situation', label: 'Situation Reporter' },
                    { id: 'Triage', label: 'Triage Specialist' },
                    { id: 'Resource', label: 'Resource Allocator' },
                    { id: 'Routing', label: 'Routing Strategist' },
                    { id: 'Verifier', label: 'Safety Verifier' }
                  ].map(agent => (
                    <button
                      key={agent.id}
                      className={`agent-filter-btn ${selectedAgentFilter === agent.id ? 'active' : ''}`}
                      onClick={() => setSelectedAgentFilter(agent.id)}
                    >
                      {agent.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activePage === 'arena' && (
            <div className="sidebar-panel">
              <h3 className="serif-font" style={{ fontSize: '22px', marginBottom: '16px', borderBottom: '1px solid var(--colors-beige-deep)', paddingBottom: '8px' }}>Arena Controls</h3>
              <p style={{ fontSize: '14px', lineHeight: '1.5', color: 'var(--colors-slate)', marginBottom: '16px' }}>
                Compare Swarm A (Medical Triage) vs Swarm B (Resource Triage) under custom incident profiles.
              </p>

              <div className="form-group">
                <label className="form-label" htmlFor="officer-arena">Incident Commander</label>
                <input
                  id="officer-arena"
                  type="text"
                  className="form-input"
                  value={officerName}
                  onChange={(e) => setOfficerName(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="scenario-arena">Disaster Scenario</label>
                <textarea
                  id="scenario-arena"
                  className="form-textarea"
                  value={scenarioText}
                  onChange={(e) => setScenarioText(e.target.value)}
                />
              </div>

              <div className="checkbox-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={injectAftershock}
                    onChange={(e) => setInjectAftershock(e.target.checked)}
                  />
                  <div>
                    <strong>Inject live aftershock</strong>
                    <span style={{ fontSize: '12px', color: 'var(--colors-steel)', display: 'block', marginTop: '2px' }}>
                      Simulate mid-mission event triggers for round 2
                    </span>
                  </div>
                </label>
              </div>

              <button 
                className="button-primary" 
                onClick={handleActivateArena}
                disabled={isLoading}
                style={{ marginTop: '24px' }}
              >
                {isLoading ? 'Running Swarm Battle...' : 'RUN SWARM ARENA'}
              </button>
            </div>
          )}

          {/* Right Column: Dynamic Output Workspace depending on the active page */}
          <div>
            {isLoading && (
              <div className="card-cream" style={{ textAlign: 'center', padding: '60px 40px' }}>
                <div style={{
                  width: '40px',
                  height: '40px',
                  border: '4px solid var(--colors-cream-deeper)',
                  borderTop: '4px solid var(--colors-primary)',
                  borderRadius: '50%',
                  animation: 'spin 1s linear infinite',
                  margin: '0 auto 16px'
                }}></div>
                <h4 className="serif-font" style={{ fontSize: '22px', marginBottom: '8px' }}>Orchestrating Specialised Swarm Agents...</h4>
                <p style={{ fontSize: '14px', color: 'var(--colors-slate)' }}>Triaging casualties and allocating physical units on the digital twin.</p>
                <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
              </div>
            )}

            {/* PAGE 1: Command Center */}
            {!isLoading && activePage === 'command' && (
              mission ? (
                <div>
                  {/* KPI Metrics Widgets */}
                  {mission.metrics && (
                    <div className="metrics-grid">
                      <div className="metric-container">
                        <span className="metric-label">Lives Saved</span>
                        <span className="metric-value accented">{mission.metrics.lives_saved}</span>
                      </div>
                      <div className="metric-container">
                        <span className="metric-label">Response Time</span>
                        <span className="metric-value">
                          {mission.metrics.response_time_min} <span style={{ fontSize: '14px', fontWeight: 400, color: 'var(--colors-steel)' }}>min</span>
                        </span>
                      </div>
                      <div className="metric-container">
                        <span className="metric-label">Zone Coverage</span>
                        <span className="metric-value">
                          {mission.metrics.coverage_pct}<span style={{ fontSize: '14px', fontWeight: 400, color: 'var(--colors-steel)' }}>%</span>
                        </span>
                      </div>
                      <div className="metric-container">
                        <span className="metric-label">Risk Level</span>
                        <span className="metric-value">
                          {mission.metrics.risk_score}<span style={{ fontSize: '14px', fontWeight: 400, color: 'var(--colors-steel)' }}>%</span>
                        </span>
                      </div>
                      <div className="metric-container featured">
                        <span className="metric-label" style={{ color: 'var(--colors-ink)' }}>Mission Score</span>
                        <span className="metric-value featured">
                          {mission.metrics.mission_score}<span style={{ fontSize: '14px', fontWeight: 400, color: 'var(--colors-steel)' }}>/100</span>
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Interactive Vector Map */}
                  <div className="card-base" style={{ padding: '16px' }}>
                    <h4 className="serif-font" style={{ fontSize: '20px', margin: '8px 8px 16px' }}>Live Command Map</h4>
                    <CommandMap world={getActiveWorld()} routes={mission.routes} />
                    
                    {/* Crisis Replay scrub slider */}
                    {mission.replay?.frames?.length > 0 && (
                      <div className="replay-timeline">
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '13px' }}>
                          <strong>Crisis Replay Slider</strong>
                          <span className="badge-cream">{getActiveStepLabel()}</span>
                        </div>
                        <input
                          type="range"
                          className="replay-slider"
                          min="0"
                          max={mission.replay.frames.length - 1}
                          value={replayFrameIdx}
                          onChange={(e) => setReplayFrameIdx(parseInt(e.target.value))}
                        />
                        <span style={{ fontSize: '12px', color: 'var(--colors-slate)', marginTop: '4px' }}>
                          {getActiveDetail()}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Operational Actions */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px', marginBottom: '24px' }}>
                    <button className="button-secondary" onClick={handleInjectAftershock} style={{ borderStyle: 'dashed' }}>
                      ⚡ Inject Aftershock & Re-plan
                    </button>
                    <button className="button-secondary" onClick={handleDownloadSitRep}>
                      📄 Download SitRep (txt)
                    </button>
                    <button className="button-secondary" onClick={handleDownloadAudit}>
                      📁 Download Audit Log (JSON)
                    </button>
                  </div>

                  {/* Verification Banner */}
                  {mission.verification && (
                    <div style={{
                      backgroundColor: mission.verification.verification_status === 'PASSED' ? '#EBFBEE' : '#FFF4F2',
                      borderLeft: `4px solid ${mission.verification.verification_status === 'PASSED' ? '#27ae60' : 'var(--colors-primary-deep)'}`,
                      padding: '16px 20px',
                      borderRadius: '12px',
                      marginBottom: '24px',
                      fontSize: '14px',
                      color: 'var(--colors-ink)'
                    }}>
                      <strong>Verification Status: {mission.verification.verification_status}</strong>
                      <span style={{ display: 'block', fontSize: '12px', color: 'var(--colors-slate)', marginTop: '4px' }}>
                        Safety confidence index: {parseFloat(mission.verification.confidence_score).toFixed(2)} &bull; Issues detected: {mission.verification.issues_found?.length || 0}
                      </span>
                    </div>
                  )}

                  {/* Incident Report Executive text */}
                  {mission.report?.text_summary && (
                    <div className="card-cream">
                      <h3 className="serif-font" style={{ fontSize: '24px', color: 'var(--colors-primary-deep)', marginBottom: '12px' }}>Incident Command Situation Report</h3>
                      <p style={{ fontSize: '15px', lineHeight: '1.6', color: 'var(--colors-ink)' }}>{mission.report.text_summary}</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="card-cream" style={{ padding: '48px 32px', textAlign: 'center' }}>
                  <h3 className="serif-font" style={{ fontSize: '26px', margin: 0 }}>Command Pipeline Ready</h3>
                  <p style={{ fontSize: '14px', color: 'var(--colors-slate)', maxWidth: '560px', margin: '10px auto 0' }}>
                    Click <strong>ACTIVATE SWARM</strong> on the parameters sidebar to run the multi-agent orchestration. You will see coordinates mapping, replay sliders, AI scorecard matrices, and human gates.
                  </p>
                </div>
              )
            )}

            {/* PAGE 2: Responsible AI Scorecard */}
            {!isLoading && activePage === 'scorecard' && (
              mission ? (
                <div>
                  <h3 className="serif-font" style={{ fontSize: '28px', marginBottom: '16px' }}>Responsible AI Audit</h3>
                  
                  {/* Scorecard Component */}
                  <AIScorecard 
                    verification={mission.verification}
                    humanApproval={mission.human_approval}
                    trust={mission.trust}
                    debate={mission.debate}
                    afterAction={mission.after_action}
                  />

                  {/* Explainability trust overlay */}
                  {mission.trust?.explanations?.length > 0 && (
                    <div className="card-base" style={{ marginTop: '24px' }}>
                      <h4 className="serif-font" style={{ fontSize: '20px', marginBottom: '12px' }}>Human Trust &mdash; Explainable Logic</h4>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        {mission.trust.explanations.map((ex, idx) => (
                          <div key={idx} style={{ fontSize: '14px', borderBottom: idx === mission.trust.explanations.length - 1 ? 'none' : '1px solid var(--colors-hairline-soft)', paddingBottom: '12px' }}>
                            <strong style={{ color: 'var(--colors-primary)' }}>{ex.decision}</strong>
                            <ul style={{ paddingLeft: '20px', marginTop: '6px', color: 'var(--colors-slate)' }}>
                              {ex.because?.map((r, rIdx) => <li key={rIdx}>{r}</li>)}
                            </ul>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Timelines and Forecast */}
                  {mission.forecast?.timeline?.length > 0 && (
                    <div className="card-base" style={{ marginTop: '24px' }}>
                      <h4 className="serif-font" style={{ fontSize: '20px', marginBottom: '8px' }}>Disaster Forecast Timeline</h4>
                      <p style={{ fontSize: '13px', color: 'var(--colors-slate)', marginBottom: '16px' }}>{mission.forecast.forecast_summary}</p>
                      
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        {mission.forecast.timeline.map((block, idx) => (
                          <div key={idx} style={{ borderLeft: '3px solid var(--colors-beige-deep)', paddingLeft: '16px', fontSize: '14px' }}>
                            <strong style={{ color: 'var(--colors-ink)' }}>+{block.horizon_hours}h Outlook</strong>
                            <ul style={{ paddingLeft: '20px', marginTop: '4px', color: 'var(--colors-slate)' }}>
                              {block.predictions?.map((p, pIdx) => <li key={pIdx}>{p}</li>)}
                            </ul>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Mutual aid Marketplace */}
                  {mission.marketplace?.transfer_plan?.length > 0 && (
                    <div className="card-cream-soft" style={{ marginTop: '24px' }}>
                      <h4 className="serif-font" style={{ fontSize: '18px', color: 'var(--colors-primary-deep)', marginBottom: '6px' }}>Resource Marketplace &mdash; Mutual Aid</h4>
                      <p style={{ fontSize: '13px', color: 'var(--colors-slate)' }}>{mission.marketplace.suggested_summary}</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="card-cream" style={{ padding: '48px 32px', textAlign: 'center' }}>
                  <h3 className="serif-font" style={{ fontSize: '26px', margin: 0 }}>Responsible AI Audit</h3>
                  <p style={{ fontSize: '14px', color: 'var(--colors-slate)', maxWidth: '560px', margin: '10px auto 0' }}>
                    No active mission found. Please return to the <strong>Command Center</strong> and run a swarm simulation first.
                  </p>
                </div>
              )
            )}

            {/* PAGE 3: Debate Chamber & Message Logs */}
            {!isLoading && activePage === 'debate' && (
              mission ? (
                <div>
                  <h3 className="serif-font" style={{ fontSize: '28px', marginBottom: '16px' }}>Debate Chamber</h3>
                  
                  {/* Debate chamber Component */}
                  <DebateChamber debate={mission.debate} />

                  {/* Interactive Filtered Transcript */}
                  <div className="card-base" style={{ marginTop: '24px' }}>
                    <h4 className="serif-font" style={{ fontSize: '20px', marginBottom: '12px' }}>Filtered Agent Logs ({filteredTranscript.length})</h4>
                    
                    {(searchTerm || selectedAgentFilter !== 'all') && (
                      <div style={{ marginBottom: '12px', fontSize: '13px', color: 'var(--colors-slate)' }}>
                        Active filters: {selectedAgentFilter !== 'all' ? `Role: ${selectedAgentFilter}` : ''} {searchTerm ? `Keyword: "${searchTerm}"` : ''} 
                        <button 
                          onClick={() => { setSearchTerm(''); setSelectedAgentFilter('all'); }} 
                          style={{ marginLeft: '10px', background: 'none', border: 'none', color: 'var(--colors-primary)', cursor: 'pointer', textDecoration: 'underline', padding: 0 }}
                        >
                          Clear all filters
                        </button>
                      </div>
                    )}
                    
                    <div style={{ maxHeight: '450px', overflowY: 'auto', border: '1px solid var(--colors-hairline)', borderRadius: '8px', padding: '12px', backgroundColor: 'var(--colors-surface)' }}>
                      {filteredTranscript.length > 0 ? (
                        filteredTranscript.map((msg, idx) => {
                          const COLORS = {
                            "Situation": "#636efa", "Commander": "#1f77b4", "Triage": "#ff7f0e",
                            "Resource": "#2ca02c", "Routing": "#d62728", "Comms": "#9467bd",
                            "Verifier": "#e377c2", "DigitalTwin": "#bcbd22", "Forecast": "#7f7f7f"
                          };
                          const col = COLORS[msg.agent] || "var(--colors-steel)";
                          return (
                            <div key={idx} style={{ 
                              padding: '12px', 
                              backgroundColor: 'var(--colors-canvas)', 
                              border: '1px solid var(--colors-hairline-soft)', 
                              borderRadius: '6px', 
                              borderLeft: `4px solid ${col}`, 
                              marginBottom: '10px' 
                            }}>
                              <div style={{ fontSize: '11px', fontWeight: '700', color: col, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{msg.agent}</div>
                              <div style={{ fontSize: '13px', color: 'var(--colors-charcoal)', marginTop: '4px', lineHeight: '1.4' }}>{msg.message}</div>
                            </div>
                          );
                        })
                      ) : (
                        <div style={{ textAlign: 'center', padding: '32px', color: 'var(--colors-slate)', fontSize: '14px' }}>
                          No messages match your search or filter criteria.
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="card-cream" style={{ padding: '48px 32px', textAlign: 'center' }}>
                  <h3 className="serif-font" style={{ fontSize: '26px', margin: 0 }}>Debate Chamber</h3>
                  <p style={{ fontSize: '14px', color: 'var(--colors-slate)', maxWidth: '560px', margin: '10px auto 0' }}>
                    No active transcripts. Run a swarm simulation in the <strong>Command Center</strong> to populate agent dialogues and logs.
                  </p>
                </div>
              )
            )}

            {/* PAGE 4: Swarm Arena Comparison */}
            {!isLoading && activePage === 'arena' && (
              arenaResults ? (
                <div>
                  <h3 className="serif-font" style={{ fontSize: '28px', marginBottom: '16px' }}>Swarm Arena Leaderboard</h3>
                  
                  {/* Winner KPI */}
                  {arenaResults.winner && (
                    <div className="metrics-grid">
                      <div className="metric-container featured">
                        <span className="metric-label" style={{ color: 'var(--colors-ink)' }}>Arena Winner</span>
                        <span className="metric-value featured" style={{ fontSize: '26px' }}>{arenaResults.winner.label}</span>
                      </div>
                      <div className="metric-container">
                        <span className="metric-label">Lives Saved (Winner)</span>
                        <span className="metric-value accented">{arenaResults.winner.metrics?.lives_saved}</span>
                      </div>
                      <div className="metric-container">
                        <span className="metric-label">Response Time</span>
                        <span className="metric-value">
                          {arenaResults.winner.metrics?.response_time_min} <span style={{ fontSize: '14px', color: 'var(--colors-steel)' }}>min</span>
                        </span>
                      </div>
                      <div className="metric-container">
                        <span className="metric-label">Mission Score</span>
                        <span className="metric-value">{arenaResults.winner.metrics?.mission_score}</span>
                      </div>
                    </div>
                  )}

                  {/* Comparison visual chart widgets (Pure CSS bars) */}
                  {arenaResults.comparison && (
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '24px' }}>
                      <div className="card-base" style={{ padding: '20px' }}>
                        <h4 className="serif-font" style={{ fontSize: '16px', marginBottom: '16px' }}>Lives Saved Side-by-Side</h4>
                        {Object.entries(arenaResults.comparison.lives_saved?.values || {}).map(([key, val]) => (
                          <div key={key} style={{ marginBottom: '12px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', fontWeight: '500', marginBottom: '4px' }}>
                              <span>{key}</span>
                              <strong>{val}</strong>
                            </div>
                            <div style={{ width: '100%', height: '14px', backgroundColor: 'var(--colors-cream-deeper)', borderRadius: '4px', overflow: 'hidden' }}>
                              <div style={{
                                width: `${Math.min(100, (val / 100) * 100)}%`,
                                height: '100%',
                                backgroundColor: key.includes('Medical') ? 'var(--colors-primary)' : 'var(--colors-sunshine-500)',
                                transition: 'width 0.4s ease'
                              }}></div>
                            </div>
                          </div>
                        ))}
                      </div>

                      <div className="card-base" style={{ padding: '20px' }}>
                        <h4 className="serif-font" style={{ fontSize: '16px', marginBottom: '16px' }}>Mission Score Comparison</h4>
                        {Object.entries(arenaResults.comparison.mission_score?.values || {}).map(([key, val]) => (
                          <div key={key} style={{ marginBottom: '12px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', fontWeight: '500', marginBottom: '4px' }}>
                              <span>{key}</span>
                              <strong>{val}/100</strong>
                            </div>
                            <div style={{ width: '100%', height: '14px', backgroundColor: 'var(--colors-cream-deeper)', borderRadius: '4px', overflow: 'hidden' }}>
                              <div style={{
                                width: `${val}%`,
                                height: '100%',
                                backgroundColor: key.includes('Medical') ? 'var(--colors-primary)' : 'var(--colors-sunshine-500)',
                                transition: 'width 0.4s ease'
                              }}></div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Leaderboards Details table */}
                  <div className="card-base">
                    <h4 className="serif-font" style={{ fontSize: '18px', marginBottom: '12px' }}>Strategy Ranking Details</h4>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Rank</th>
                          <th>Strategy</th>
                          <th>Round</th>
                          <th>Score</th>
                          <th>Saved</th>
                          <th>ETA</th>
                          <th>Verification</th>
                        </tr>
                      </thead>
                      <tbody>
                        {arenaResults.leaderboard?.map((entry, idx) => (
                          <tr key={idx} style={{ backgroundColor: entry.winner ? 'var(--colors-cream-soft)' : 'transparent' }}>
                            <td><strong>{entry.rank}</strong></td>
                            <td><strong>{entry.label}</strong></td>
                            <td>Round {entry.round}</td>
                            <td><strong style={{ color: 'var(--colors-primary-deep)' }}>{entry.metrics?.mission_score}</strong></td>
                            <td>{entry.metrics?.lives_saved}</td>
                            <td>{entry.metrics?.response_time_min} min</td>
                            <td>
                              <span className={entry.verification_status === 'PASSED' ? 'badge-cream' : 'badge-orange'} style={{ fontSize: '10px' }}>
                                {entry.verification_status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Round summaries breakdown */}
                  {arenaResults.rounds?.map((rnd, index) => (
                    <div key={index} className="card-cream-soft" style={{ marginBottom: '16px' }}>
                      <h4 className="serif-font" style={{ fontSize: '16px', textTransform: 'capitalize', color: 'var(--colors-primary-deep)', marginBottom: '8px' }}>
                        Round {rnd.round} &mdash; {rnd.label.replace(/_/g, ' ')}
                      </h4>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {rnd.results?.map((res, rIdx) => (
                          <div key={rIdx} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', borderBottom: rIdx === rnd.results.length - 1 ? 'none' : '1px solid rgba(0,0,0,0.05)', paddingBottom: '6px' }}>
                            <span>{res.label}</span>
                            <strong>Score: {res.mission_score} &bull; Verification: {res.verification_status}</strong>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="card-cream" style={{ padding: '48px 32px', textAlign: 'center' }}>
                  <h3 className="serif-font" style={{ fontSize: '26px', margin: 0 }}>Swarm Arena Ready</h3>
                  <p style={{ fontSize: '14px', color: 'var(--colors-slate)', maxWidth: '560px', margin: '10px auto 0' }}>
                    Click <strong>RUN SWARM ARENA</strong> on the parameters sidebar to run Swarm A (Medical First) and Swarm B (Resource Balanced) competing side by side under active aftershock incidents.
                  </p>
                </div>
              )
            )}
          </div>
        </div>

        {/* 4. Bottom Sunset Stripe & Footer */}
        <div className="sunset-stripe-band"></div>
        
        <div className="footer-region">
          <div className="footer-col">
            <div className="footer-col-title">CrisisSwarm</div>
            <p style={{ fontSize: '13px', lineHeight: '1.5', color: 'var(--colors-slate)', marginTop: 0 }}>
              Frontier AI-driven multi-agent coordination for emergency logistics and casualty triage. Made for Microsoft Build AI Hackathon 2026.
            </p>
          </div>
          <div className="footer-col">
            <div className="footer-col-title">Explore</div>
            <a href="#active-command-center" onClick={(e) => { e.preventDefault(); setActivePage('command'); }}>Command Center</a>
            <a href="#verification-results" onClick={(e) => { e.preventDefault(); setActivePage('scorecard'); }}>AI Scorecard</a>
            <a href="#agent-debate-chamber" onClick={(e) => { e.preventDefault(); setActivePage('debate'); }}>Debate Chamber</a>
            <a href="#live-agent-transcript" onClick={(e) => { e.preventDefault(); setActivePage('debate'); }}>Agent Log</a>
          </div>
          <div className="footer-col">
            <div className="footer-col-title">Build</div>
            <a href="https://console.groq.com/" target="_blank" rel="noreferrer">Groq API</a>
            <a href="https://streamlit.io/" target="_blank" rel="noreferrer">Streamlit</a>
            <a href="https://deck.gl/pydeck" target="_blank" rel="noreferrer">Pydeck</a>
          </div>
          <div className="footer-col">
            <div className="footer-col-title">Legal</div>
            <a href="#active-command-center">Responsible AI License</a>
            <a href="#active-command-center">Privacy Policy</a>
            <a href="#active-command-center">Terms of Use</a>
          </div>
          <div className="footer-col">
            <div className="footer-col-title">Team</div>
            <span style={{ fontSize: '13px', color: 'var(--colors-slate)' }}>Tejas & Team</span>
          </div>
          <div className="footer-bottom">
            <span>&copy; 2026 CrisisSwarm. All rights reserved.</span>
            <span>Frontier AI. In your hands.</span>
          </div>
        </div>
      </div>

      {/* 5. Human Gate modal overlay */}
      {isSwarmAwaitsApproval && (
        <HumanGate 
          mission={mission}
          isLoading={isLoading}
          onApprove={(notes) => handleFinalize(mission, "approved", notes)}
          onReject={(notes) => handleFinalize(mission, "rejected", notes)}
          onAutofix={async () => {
            // run_swarm automatically attempts to fix or re-run
            await handleActivateSwarm();
          }}
        />
      )}
    </div>
  );
}
