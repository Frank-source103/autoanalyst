import React, { useState } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { ChartSpec } from '../types';

interface ChartViewerProps {
  charts: ChartSpec[];
}

const PALETTE = ['#2563eb', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#64748b'];

export const ChartViewer: React.FC<ChartViewerProps> = ({ charts }) => {
  const [selectedIdx, setSelectedIdx] = useState(0);

  if (!charts || charts.length === 0) {
    return (
      <div className="chart-empty-state">
        <span className="empty-chart-icon" aria-hidden="true">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="20" x2="18" y2="10" />
            <line x1="12" y1="20" x2="12" y2="4" />
            <line x1="6" y1="20" x2="6" y2="14" />
          </svg>
        </span>
        <p>No visualization data produced yet. Charts will render here automatically when generated.</p>
      </div>
    );
  }

  const activeChart = charts[Math.min(selectedIdx, charts.length - 1)];
  const { chart_type, title, x_label, y_label, data, series } = activeChart;

  const dataKeys = series && series.length > 0 ? series : Object.keys(data[0] || {}).filter((k) => k !== 'category' && k !== 'x' && k !== 'name');
  const xKey = Object.keys(data[0] || {}).find((k) => k === 'category' || k === 'x' || k === 'name' || k === 'label') || Object.keys(data[0] || {})[0];

  const renderChart = () => {
    switch (chart_type) {
      case 'line':
        return (
          <LineChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey={xKey} stroke="#94a3b8" />
            <YAxis stroke="#94a3b8" />
            <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#f8fafc' }} />
            <Legend />
            {dataKeys.map((key, i) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={PALETTE[i % PALETTE.length]}
                strokeWidth={2}
                dot={{ r: 3 }}
              />
            ))}
          </LineChart>
        );

      case 'scatter':
        return (
          <ScatterChart margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey={xKey} stroke="#94a3b8" name={x_label || xKey} />
            <YAxis stroke="#94a3b8" name={y_label || 'Value'} />
            <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#f8fafc' }} cursor={{ strokeDasharray: '3 3' }} />
            <Legend />
            {dataKeys.map((key, i) => (
              <Scatter
                key={key}
                name={key}
                data={data}
                fill={PALETTE[i % PALETTE.length]}
              />
            ))}
          </ScatterChart>
        );

      case 'bar_grouped':
      case 'bar':
      default:
        return (
          <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey={xKey} stroke="#94a3b8" />
            <YAxis stroke="#94a3b8" />
            <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#f8fafc' }} />
            <Legend />
            {dataKeys.map((key, i) => (
              <Bar
                key={key}
                dataKey={key}
                fill={PALETTE[i % PALETTE.length]}
                radius={[4, 4, 0, 0]}
              />
            ))}
          </BarChart>
        );
    }
  };

  return (
    <div className="chart-viewer-card">
      <div className="chart-header">
        <h3 className="chart-title">{title}</h3>
        {charts.length > 1 && (
          <div className="chart-tabs">
            {charts.map((c, idx) => (
              <button
                key={idx}
                className={`chart-tab-btn ${selectedIdx === idx ? 'active' : ''}`}
                onClick={() => setSelectedIdx(idx)}
              >
                Chart {idx + 1}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="chart-canvas">
        <ResponsiveContainer width="100%" height={320}>
          {renderChart()}
        </ResponsiveContainer>
      </div>

      <div className="chart-footer">
        <span className="chart-meta">
          Type: <strong>{chart_type}</strong> · Points: <strong>{data.length}</strong>
          {x_label && <> · X-Axis: <span>{x_label}</span></>}
          {y_label && <> · Y-Axis: <span>{y_label}</span></>}
        </span>
      </div>
    </div>
  );
};
