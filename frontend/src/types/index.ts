/**
 * Data structures and event types for AutoAnalyst frontend.
 */

export type EventType =
  | 'state_transition'
  | 'plan'
  | 'thought'
  | 'code'
  | 'execution_started'
  | 'stdout'
  | 'stderr'
  | 'execution_result'
  | 'chart'
  | 'retry'
  | 'paused'
  | 'resumed'
  | 'report'
  | 'run_status';

export interface AgentEvent {
  seq: number;
  run_id: string;
  timestamp: string;
  event_type: EventType;
  data: Record<string, any>;
}

export interface PlanStep {
  step_id: number;
  title: string;
  description: string;
  is_critical: boolean;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
}

export interface ChartSpec {
  chart_type: 'line' | 'bar' | 'scatter' | 'bar_grouped';
  title: string;
  x_label?: string;
  y_label?: string;
  data: Array<Record<string, any>>;
  series?: string[];
}

export type RunStatus =
  | 'idle'
  | 'pending'
  | 'planning'
  | 'running'
  | 'paused'
  | 'completed'
  | 'failed'
  | 'aborted'
  | 'budget_exceeded';

export interface DatasetMeta {
  datasetId: string;
  filename: string;
  filePath: string;
  fileType: string;
  sizeBytes: number;
}
