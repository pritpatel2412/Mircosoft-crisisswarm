import React, { useState } from 'react';

export default function HumanGate({ mission, onApprove, onReject, onAutofix, isLoading }) {
  const [notes, setNotes] = useState('');
  const verification = mission?.verification || {};
  const issues = verification.issues_found || [];

  return (
    <div style={{
      position: 'fixed',
      top: 0, right: 0, bottom: 0, left: 0,
      backgroundColor: 'rgba(17,17,17,0.7)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      zIndex: 9999,
      padding: '20px'
    }}>
      <div className="card-cream" style={{
        maxWidth: '560px',
        width: '100%',
        boxShadow: 'rgba(0,0,0,0.3) 0px 16px 48px -8px',
        maxHeight: '90vh',
        overflowY: 'auto'
      }}>
        <h3 className="serif-font" style={{
          fontSize: '32px',
          color: 'var(--colors-primary-deep)',
          marginTop: 0,
          marginBottom: '12px'
        }}>
          Human Command Gate
        </h3>
        
        <p style={{ fontSize: '14px', lineHeight: '1.5', color: 'var(--colors-ink)', marginBottom: '20px' }}>
          <strong>Safety Warning:</strong> The deterministic Verifier flagged operational conflicts. 
          <em> AI proposes &mdash; humans authorize.</em> Please review the issues and decide whether to approve or reject deployment.
        </p>

        {/* Highlighted Issues list */}
        <div style={{ marginBottom: '20px' }}>
          {issues.map((issue, index) => (
            <div 
              key={index} 
              style={{
                backgroundColor: '#FFF4F2',
                borderLeft: '4px solid var(--colors-primary-deep)',
                padding: '12px 16px',
                borderRadius: '8px',
                marginBottom: '12px',
                fontSize: '13px',
                color: 'var(--colors-ink)'
              }}
            >
              <div style={{ fontWeight: '700', textTransform: 'uppercase', fontSize: '11px', color: 'var(--colors-primary-deep)', marginBottom: '4px' }}>
                {issue.type} &bull; {issue.severity}
              </div>
              <div style={{ fontWeight: '500' }}>{issue.message}</div>
              {issue.recommended_fix && (
                <div style={{ fontSize: '12px', color: 'var(--colors-slate)', marginTop: '6px', borderTop: '1px solid rgba(0,0,0,0.05)', paddingTop: '6px' }}>
                  <strong>Fix:</strong> {issue.recommended_fix}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Notes Input Area */}
        <div className="form-group">
          <label className="form-label" htmlFor="gate-notes">Commander Notes (Optional)</label>
          <textarea
            id="gate-notes"
            className="form-textarea"
            placeholder="Provide reasons for override or rejection..."
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            disabled={isLoading}
          />
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginTop: '24px' }}>
          <button 
            className="button-primary"
            onClick={() => onApprove(notes)}
            disabled={isLoading}
            style={{ width: '100%' }}
          >
            {isLoading ? 'Processing...' : 'Approve Plan'}
          </button>
          
          <button 
            className="button-secondary"
            onClick={() => onReject(notes)}
            disabled={isLoading}
            style={{ width: '100%', borderColor: 'var(--colors-primary-deep)', color: 'var(--colors-primary-deep)' }}
          >
            Reject Plan
          </button>

          <button 
            className="button-secondary"
            onClick={() => onAutofix(notes)}
            disabled={isLoading}
            style={{ gridColumn: '1 / -1', width: '100%', borderStyle: 'dashed' }}
          >
            Auto-Fix & Re-run
          </button>
        </div>
      </div>
    </div>
  );
}
