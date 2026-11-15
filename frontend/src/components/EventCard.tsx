import React, { useState } from 'react';
import { AgentEvent } from '../types';

interface EventCardProps {
  event: AgentEvent;
}

export const EventCard: React.FC<EventCardProps> = ({ event }) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [showFullOutput, setShowFullOutput] = useState(false);

  const renderContent = () => {
    switch (event.event_type) {
      case 'thought':
        return (
          <div className="event-thought">
            <div className="thought-header">
              <span className="thought-icon" aria-hidden="true">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 2a4 4 0 0 1 4 4c0 1.5-.8 2.8-2 3.5V11a2 2 0 0 1-2 2h0a2 2 0 0 1-2-2V9.5C8.8 8.8 8 7.5 8 6a4 4 0 0 1 4-4z" />
                  <path d="M9 18h6" />
                  <path d="M10 22h4" />
                </svg>
              </span>
              <span className="thought-label">Agent Thought</span>
              {event.data?.step_id && (
                <span className="step-pill">Step {event.data.step_id}</span>
              )}
            </div>
            <p className="thought-body">{event.data?.thought}</p>
          </div>
        );

      case 'code':
        const codeText = event.data?.code || '';
        return (
          <div className="event-code">
            <div className="code-header" onClick={() => setIsExpanded(!isExpanded)}>
              <span className="code-icon" aria-hidden="true">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="16 18 22 12 16 6" />
                  <polyline points="8 6 2 12 8 18" />
                </svg>
              </span>
              <span className="code-label">
                {event.data?.is_correction ? 'Self-Corrected Script' : 'Generated Python Script'}
              </span>
              {event.data?.is_correction && (
                <span className="badge-correction">Correction</span>
              )}
              <span className="collapse-toggle" aria-hidden="true">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points={isExpanded ? '6 9 12 15 18 9' : '9 18 15 12 9 6'} />
                </svg>
              </span>
            </div>
            {isExpanded && (
              <pre className="code-block">
                <code>{codeText}</code>
              </pre>
            )}
          </div>
        );

      case 'stdout':
      case 'stderr':
        const isErr = event.event_type === 'stderr';
        const rawText = event.data?.text || '';
        const lines = rawText.split('\n');
        const isTruncated = lines.length > 8 && !showFullOutput;
        const visibleText = isTruncated ? lines.slice(0, 8).join('\n') : rawText;

        return (
          <div className={`event-log ${isErr ? 'log-stderr' : 'log-stdout'}`}>
            <div className="log-header">
              <span className="log-icon" aria-hidden="true">
                {isErr ? (
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#fca5a5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                    <line x1="12" y1="9" x2="12" y2="13" />
                    <line x1="12" y1="17" x2="12.01" y2="17" />
                  </svg>
                ) : (
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="4 17 10 11 4 5" />
                    <line x1="12" y1="19" x2="20" y2="19" />
                  </svg>
                )}
              </span>
              <span className="log-label">{isErr ? 'Sandbox Stderr' : 'Sandbox Stdout'}</span>
              <span className="log-step">Step {event.data?.step_id}</span>
            </div>
            <pre className="log-body">{visibleText}</pre>
            {lines.length > 8 && (
              <button
                className="show-more-btn"
                onClick={() => setShowFullOutput(!showFullOutput)}
              >
                {showFullOutput ? 'Show Less' : `Show More (${lines.length - 8} lines hidden)`}
              </button>
            )}
          </div>
        );

      case 'execution_started':
        return (
          <div className="event-info">
            <span className="info-icon" aria-hidden="true">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
              </svg>
            </span>
            <span>
              Container started execution for <strong>Step {event.data?.step_id}: {event.data?.title}</strong>
            </span>
          </div>
        );

      case 'execution_result':
        const isSuccess = event.data?.status === 'success';
        return (
          <div className={`event-result ${isSuccess ? 'result-success' : 'result-failed'}`}>
            <div className="result-header">
              <span className="result-icon" aria-hidden="true">
                {isSuccess ? (
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                )}
              </span>
              <span className="result-title">
                Execution {isSuccess ? 'Succeeded' : 'Failed'}
              </span>
              <span className="result-duration">{event.data?.duration_seconds}s</span>
            </div>
            {event.data?.error_signature && (
              <div className="result-error">
                <strong>Error Signature:</strong> {event.data.error_signature}
              </div>
            )}
          </div>
        );

      case 'chart':
        return (
          <div className="event-chart-notice">
            <span className="chart-icon" aria-hidden="true">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="20" x2="18" y2="10" />
                <line x1="12" y1="20" x2="12" y2="4" />
                <line x1="6" y1="20" x2="6" y2="14" />
              </svg>
            </span>
            <span>
              Generated visualization: <strong>{event.data?.chart?.title || 'Chart Output'}</strong> ({event.data?.chart?.chart_type})
            </span>
          </div>
        );

      case 'retry':
        return (
          <div className="event-retry-banner">
            <span className="retry-icon" aria-hidden="true">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="1 4 1 10 7 10" />
                <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
              </svg>
            </span>
            <div>
              <strong>Self-Correction Retry #{event.data?.retry_count}:</strong>{' '}
              {event.data?.reason || event.data?.error_signature || 'Retrying failed step'}
            </div>
          </div>
        );

      case 'paused':
        return (
          <div className="event-pause-banner">
            <span className="pause-icon" aria-hidden="true">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="4" width="4" height="16" />
                <rect x="14" y="4" width="4" height="16" />
              </svg>
            </span>
            <div>
              <strong>Execution Paused for Human Review:</strong> Review or edit the pending script in the Monaco editor, then click <strong>Resume</strong>.
            </div>
          </div>
        );

      case 'resumed':
        return (
          <div className="event-resume-banner">
            <span className="resume-icon" aria-hidden="true">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
            </span>
            <span>
              Execution resumed {event.data?.edited_by_user ? '(with user code modifications)' : ''}
            </span>
          </div>
        );

      case 'state_transition':
        return (
          <div className="event-transition">
            <span>State transition: <strong>{event.data?.from}</strong> → <strong>{event.data?.to}</strong></span>
          </div>
        );

      default:
        return null;
    }
  };

  const content = renderContent();
  if (!content) return null;

  return (
    <div className={`timeline-card card-type-${event.event_type}`}>
      <div className="card-seq-badge">#{event.seq}</div>
      {content}
    </div>
  );
};
