import React, { useState } from 'react';
import './App.css';
import { Header } from './components/Header';
import { DatasetUploader } from './components/DatasetUploader';
import { Timeline } from './components/Timeline';
import { CodeEditorPane } from './components/CodeEditorPane';
import { ChartViewer } from './components/ChartViewer';
import { ReportViewer } from './components/ReportViewer';
import { useRunState } from './hooks/useRunState';
import { useWebSocket } from './hooks/useWebSocket';

export const App: React.FC = () => {
  const {
    runId,
    status,
    plan,
    events,
    charts,
    finalReport,
    pendingCode,
    currentStepIdx,
    perStepRetryCount,
    isPaused,
    highestSeq,
    setPendingCode,
    handleIncomingEvent,
    startRun,
    pauseRun,
    resumeRun,
    abortRun,
  } = useRunState();

  const { isConnected } = useWebSocket({
    runId,
    lastSeq: highestSeq,
    onEvent: handleIncomingEvent,
  });

  // Mobile navigation tab state: 'timeline' | 'code' | 'results'
  const [activeMobileTab, setActiveMobileTab] = useState<'timeline' | 'code' | 'results'>('timeline');

  const isRunning = status === 'pending' || status === 'planning' || status === 'running';

  return (
    <div className="app-container">
      <Header
        status={status}
        currentStepIdx={currentStepIdx}
        perStepRetryCount={perStepRetryCount}
        plan={plan}
        isWsConnected={isConnected}
      />

      {/* Mobile Tab Navigation (< 768px) */}
      <nav className="mobile-tabs" aria-label="Mobile Navigation">
        <button
          className={`mobile-tab-btn ${activeMobileTab === 'timeline' ? 'active' : ''}`}
          onClick={() => setActiveMobileTab('timeline')}
        >
          Timeline ({events.length})
        </button>
        <button
          className={`mobile-tab-btn ${activeMobileTab === 'code' ? 'active' : ''}`}
          onClick={() => setActiveMobileTab('code')}
        >
          Code {isPaused ? '(Review)' : ''}
        </button>
        <button
          className={`mobile-tab-btn ${activeMobileTab === 'results' ? 'active' : ''}`}
          onClick={() => setActiveMobileTab('results')}
        >
          Chart & Report {charts.length > 0 ? `(${charts.length})` : ''}
        </button>
      </nav>

      <main className="main-content">
        <div className="split-view-layout">
          {/* Left Column: Dataset Setup & Timeline */}
          <div
            className={`split-left-pane ${
              activeMobileTab === 'timeline' ? 'mobile-pane-visible' : 'mobile-pane-hidden'
            }`}
          >
            {status === 'idle' && (
              <DatasetUploader onStartRun={startRun} isLoading={isRunning} />
            )}
            <Timeline events={events} />
          </div>

          {/* Right Column: Code Editor & Results */}
          <div
            className={`split-right-pane ${
              activeMobileTab !== 'timeline' ? 'mobile-pane-visible' : 'mobile-pane-hidden'
            }`}
          >
            {/* Show Code pane on desktop or when active mobile tab is 'code' */}
            <div
              className={`code-section ${
                activeMobileTab === 'results' ? 'mobile-pane-hidden' : ''
              }`}
            >
              <CodeEditorPane
                code={pendingCode}
                status={status}
                isPaused={isPaused}
                onPause={pauseRun}
                onResume={resumeRun}
                onAbort={abortRun}
              />
            </div>

            {/* Show Results pane on desktop or when active mobile tab is 'results' */}
            <div
              className={`results-section ${
                activeMobileTab === 'code' ? 'mobile-pane-hidden' : ''
              }`}
            >
              <ChartViewer charts={charts} />
              <ReportViewer reportMarkdown={finalReport} />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default App;
