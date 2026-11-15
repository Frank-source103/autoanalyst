import React from 'react';
import { PlanStep, RunStatus } from '../types';

interface HeaderProps {
  status: RunStatus;
  currentStepIdx: number;
  perStepRetryCount: number;
  plan: PlanStep[];
  isWsConnected: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  status,
  currentStepIdx,
  perStepRetryCount,
  plan,
  isWsConnected,
}) => {
  const getStatusBadge = () => {
    switch (status) {
      case 'running':
      case 'planning':
      case 'pending':
        return (
          <span className="badge badge-running">
            <span className="pulse-dot" />
            {status.toUpperCase()}
          </span>
        );
      case 'paused':
        return (
          <span className="badge badge-paused">
            <span className="pause-icon" aria-hidden="true">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="4" width="4" height="16" />
                <rect x="14" y="4" width="4" height="16" />
              </svg>
            </span>
            PAUSED (REVIEW)
          </span>
        );
      case 'completed':
        return (
          <span className="badge badge-completed">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            COMPLETED
          </span>
        );
      case 'failed':
      case 'budget_exceeded':
        return (
          <span className="badge badge-failed">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
            {status.replace('_', ' ').toUpperCase()}
          </span>
        );
      case 'aborted':
        return (
          <span className="badge badge-aborted">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="10" />
              <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
            </svg>
            ABORTED
          </span>
        );
      default:
        return (
          <span className="badge badge-idle">
            IDLE
          </span>
        );
    }
  };

  const getStepProgressText = () => {
    if (plan.length === 0) {
      if (status === 'planning') return 'Formulating analytical plan...';
      if (status === 'pending') return 'Initializing agent...';
      return 'Ready for dataset upload';
    }

    const currentStepNum = Math.min(currentStepIdx + 1, plan.length);
    const stepObj = plan[currentStepIdx] || plan[plan.length - 1];
    const attemptText = perStepRetryCount > 0 ? ` · attempt ${perStepRetryCount + 1}/3` : '';

    return `Step ${currentStepNum}/${plan.length}${attemptText} : ${stepObj.title}`;
  };

  return (
    <header className="app-header">
      <div className="header-left">
        <div className="logo-container">
          <div className="logo-icon" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="12 2 2 22 22 22" />
            </svg>
          </div>
          <div>
            <h1 className="logo-title">AutoAnalyst</h1>
            <p className="logo-subtitle">Data Science & Code Execution Workspace</p>
          </div>
        </div>
      </div>

      <div className="header-center">
        <div className="step-tracker">
          <span className="step-text">{getStepProgressText()}</span>
        </div>
      </div>

      <div className="header-right">
        <div className="ws-indicator" title={isWsConnected ? 'Connected to live agent' : 'Reconnecting...'}>
          <span className={`ws-dot ${isWsConnected ? 'connected' : 'disconnected'}`} />
          <span className="ws-label">{isWsConnected ? 'Live' : 'Syncing'}</span>
        </div>
        {getStatusBadge()}
      </div>
    </header>
  );
};
