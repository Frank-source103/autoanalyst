import React from 'react';
import Markdown from 'react-markdown';

interface ReportViewerProps {
  reportMarkdown: string | null;
}

export const ReportViewer: React.FC<ReportViewerProps> = ({ reportMarkdown }) => {
  if (!reportMarkdown) {
    return (
      <div className="report-empty-state">
        <span className="empty-report-icon" aria-hidden="true">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
        </span>
        <p>Analytical report will be synthesized upon conclusion of all steps.</p>
      </div>
    );
  }

  return (
    <div className="report-viewer-card">
      <div className="report-header">
        <h3 className="report-title">Analytical Synthesis Report</h3>
        <span className="report-badge">SYNTHESIS</span>
      </div>
      <div className="report-markdown-content">
        {/* Raw HTML stays disabled by default in react-markdown */}
        <Markdown>{reportMarkdown}</Markdown>
      </div>
    </div>
  );
};
