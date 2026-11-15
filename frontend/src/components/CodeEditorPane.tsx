import React, { useState, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import { RunStatus } from '../types';

interface CodeEditorPaneProps {
  code: string;
  status: RunStatus;
  isPaused: boolean;
  onPause: () => Promise<void>;
  onResume: (editedCode?: string) => Promise<void>;
  onAbort: () => Promise<void>;
}

export const CodeEditorPane: React.FC<CodeEditorPaneProps> = ({
  code,
  status,
  isPaused,
  onPause,
  onResume,
  onAbort,
}) => {
  const [editorValue, setEditorValue] = useState<string>(code);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    setEditorValue(code);
  }, [code]);

  const isEditable = isPaused || status === 'paused';
  const isRunning = status === 'running' || status === 'planning';
  const isTerminated = status === 'completed' || status === 'failed' || status === 'aborted';

  const handleResumeClick = async () => {
    setIsSubmitting(true);
    try {
      await onResume(editorValue);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePauseClick = async () => {
    setIsSubmitting(true);
    try {
      await onPause();
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAbortClick = async () => {
    if (window.confirm('Are you sure you want to abort the analysis run?')) {
      setIsSubmitting(true);
      try {
        await onAbort();
      } finally {
        setIsSubmitting(false);
      }
    }
  };

  return (
    <div className="code-editor-pane">
      <div className="editor-toolbar">
        <div className="editor-info">
          <span className="editor-title">Python Code Inspector</span>
          <span className={`editor-mode-badge ${isEditable ? 'mode-editable' : 'mode-readonly'}`}>
            {isEditable ? (
              <>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                </svg>
                Editable (Paused)
              </>
            ) : (
              <>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
                Read-Only
              </>
            )}
          </span>
        </div>

        <div className="editor-controls">
          {isRunning && (
            <button
              onClick={handlePauseClick}
              disabled={isSubmitting}
              className="btn btn-warning btn-sm"
              title="Pause execution before next step"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <rect x="6" y="4" width="4" height="16" />
                <rect x="14" y="4" width="4" height="16" />
              </svg>
              Pause Run
            </button>
          )}

          {isEditable && (
            <button
              onClick={handleResumeClick}
              disabled={isSubmitting || !editorValue.trim()}
              className="btn btn-success btn-sm"
              title="Resume execution with current code"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              Resume Execution
            </button>
          )}

          {!isTerminated && status !== 'idle' && (
            <button
              onClick={handleAbortClick}
              disabled={isSubmitting}
              className="btn btn-danger btn-sm"
              title="Kill sandbox container and terminate run"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="10" />
                <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
              </svg>
              Abort
            </button>
          )}
        </div>
      </div>

      <div className="editor-canvas-container">
        <Editor
          height="100%"
          language="python"
          theme="vs-dark"
          value={editorValue}
          onChange={(val) => setEditorValue(val || '')}
          options={{
            readOnly: !isEditable,
            minimap: { enabled: false },
            fontSize: 13,
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            wordWrap: 'on',
            automaticLayout: true,
            tabSize: 4,
          }}
        />
      </div>

      {isEditable && (
        <div className="editor-notice">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
          Modify or inspect Python code before sending to the container. Click <strong>Resume Execution</strong> to proceed.
        </div>
      )}
    </div>
  );
};
