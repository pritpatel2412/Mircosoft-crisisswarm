import React from 'react';

export default function DebateChamber({ debate }) {
  if (!debate || !debate.rounds || debate.rounds.length === 0) {
    return null;
  }

  const roundColors = {
    "Resource": "var(--colors-primary)", 
    "Routing": "var(--colors-sunshine-500)", 
    "Commander": "var(--colors-ink)"
  };

  const getRounds = () => {
    return debate.rounds;
  };

  return (
    <div className="card-base" id="agent-debate-chamber">
      <h3 className="serif-font" style={{ fontSize: '24px', marginBottom: '8px' }}>Agent Debate Chamber</h3>
      <p style={{ fontSize: '13px', color: 'var(--colors-slate)', marginBottom: '20px' }}>
        Before operational plans are finalized, the Resource and Routing agents submit conflicting proposals. The Commander mediates to establish a safe, balanced response plan.
      </p>

      {getRounds().map((rnd, i) => {
        const speaker = rnd.speaker || "?";
        const color = roundColors[speaker] || "var(--colors-steel)";
        const stance = (rnd.stance || "").replace(/_/g, " ");

        // Collect proposals if available
        const proposals = rnd.proposals || rnd.counter_proposals || rnd.final_allocations || [];

        return (
          <div 
            key={i}
            style={{
              borderLeft: `4px solid ${color}`,
              padding: '16px 20px',
              margin: '16px 0',
              backgroundColor: 'var(--colors-cream-soft)',
              borderRadius: '8px',
              borderTop: '1px solid var(--colors-beige-deep)',
              borderRight: '1px solid var(--colors-beige-deep)',
              borderBottom: '1px solid var(--colors-beige-deep)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ color: color, fontWeight: '700', fontSize: '15px' }}>
                Round {rnd.round} &mdash; {speaker}
              </span>
              <span className="badge-cream" style={{ textTransform: 'capitalize' }}>
                {stance}
              </span>
            </div>

            <p style={{ fontSize: '14px', lineHeight: '1.5', color: 'var(--colors-charcoal)', marginBottom: proposals.length > 0 ? '12px' : '0' }}>
              "{rnd.message}"
            </p>

            {proposals.length > 0 && (
              <div style={{ overflowX: 'auto', marginTop: '12px' }}>
                <table className="data-table" style={{ margin: '0' }}>
                  <thead>
                    <tr>
                      <th>Zone</th>
                      <th>Ambulances</th>
                      <th>Basis / Rationale</th>
                    </tr>
                  </thead>
                  <tbody>
                    {proposals.map((p, idx) => (
                      <tr key={idx}>
                        <td><strong>{p.zone}</strong></td>
                        <td>{p.ambulances}</td>
                        <td style={{ color: 'var(--colors-slate)' }}>{p.rationale || p.basis || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}

      <div style={{
        marginTop: '20px',
        padding: '12px 16px',
        backgroundColor: 'var(--colors-cream)',
        border: '1px solid var(--colors-beige-deep)',
        borderRadius: '8px',
        fontSize: '14px',
        fontWeight: '500',
        color: 'var(--colors-primary-deep)',
        display: 'flex',
        alignItems: 'center',
        gap: '8px'
      }}>
        <span>📢</span>
        <span>{debate.outcome_summary}</span>
      </div>
    </div>
  );
}
