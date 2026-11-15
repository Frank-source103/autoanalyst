import React, { useState } from 'react';
import { DatasetMeta } from '../types';

interface DatasetUploaderProps {
  onStartRun: (question: string, datasetPath: string, filename: string, reviewBeforeRun: boolean) => Promise<void>;
  isLoading: boolean;
}

export const DatasetUploader: React.FC<DatasetUploaderProps> = ({ onStartRun, isLoading }) => {
  const [fileMeta, setFileMeta] = useState<DatasetMeta | null>(null);
  const [question, setQuestion] = useState(
    'Analyze product category performance, calculate total sales, and generate a category revenue chart.'
  );
  const [reviewBeforeRun, setReviewBeforeRun] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setErrorMessage(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Upload failed');
      }

      const data = await res.json();
      setFileMeta({
        datasetId: data.dataset_id,
        filename: data.filename,
        filePath: data.file_path,
        fileType: data.file_type,
        sizeBytes: data.size_bytes,
      });
    } catch (err: any) {
      setErrorMessage(err.message || 'File upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleLoadSample = async () => {
    setUploading(true);
    setErrorMessage(null);
    try {
      const res = await fetch('/api/upload/sample', { method: 'POST' });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Sample load failed');
      }
      const data = await res.json();
      setFileMeta({
        datasetId: data.dataset_id,
        filename: data.filename,
        filePath: data.file_path,
        fileType: data.file_type,
        sizeBytes: data.size_bytes,
      });
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to load sample dataset');
    } finally {
      setUploading(false);
    }
  };

  const handleLaunch = async () => {
    if (!fileMeta || !question.trim()) return;
    try {
      setErrorMessage(null);
      await onStartRun(question.trim(), fileMeta.filePath, fileMeta.filename, reviewBeforeRun);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to start run');
    }
  };

  return (
    <div className="dataset-uploader-card">
      <div className="card-header">
        <h2 className="card-title">Dataset & Query Setup</h2>
        <span className="card-badge">INPUT</span>
      </div>

      <div className="upload-section">
        <label className="upload-dropzone">
          <input
            type="file"
            accept=".csv,.parquet"
            onChange={handleFileUpload}
            disabled={uploading || isLoading}
            className="file-input-hidden"
          />
          <div className="dropzone-content">
            <span className="dropzone-icon" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="12" y1="18" x2="12" y2="12" />
                <polyline points="9 15 12 12 15 15" />
              </svg>
            </span>
            {fileMeta ? (
              <div className="file-info">
                <span className="file-name">{fileMeta.filename}</span>
                <span className="file-size">
                  ({(fileMeta.sizeBytes / 1024).toFixed(1)} KB · {fileMeta.fileType.toUpperCase()})
                </span>
              </div>
            ) : (
              <div className="dropzone-prompt">
                <span className="dropzone-primary">Select or drop CSV / Parquet dataset</span>
                <span className="dropzone-sub">Mounted read-only inside sandbox container</span>
              </div>
            )}
          </div>
        </label>
        <button
          type="button"
          onClick={handleLoadSample}
          disabled={uploading || isLoading}
          className="btn btn-secondary btn-sm"
          style={{ width: '100%' }}
        >
          Load Sample E-Commerce Dataset
        </button>
      </div>

      <div className="query-section">
        <label className="form-label" htmlFor="user-question-input">
          Analytical Question
        </label>
        <textarea
          id="user-question-input"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question in plain English (e.g. Find customer segments with highest growth...)"
          className="question-textarea"
          rows={3}
          disabled={isLoading}
        />
      </div>

      <div className="controls-row">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={reviewBeforeRun}
            onChange={(e) => setReviewBeforeRun(e.target.checked)}
            disabled={isLoading}
          />
          <span className="checkbox-text">
            <strong>Review code before run</strong> (Pauses before script execution)
          </span>
        </label>

        <button
          onClick={handleLaunch}
          disabled={!fileMeta || !question.trim() || isLoading || uploading}
          className="btn btn-primary start-btn"
        >
          {isLoading ? 'Agent Running...' : 'Start Autonomous Analysis'}
        </button>
      </div>

      {errorMessage && <div className="error-banner">{errorMessage}</div>}
    </div>
  );
};
