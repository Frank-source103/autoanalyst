import { useState, useCallback, useMemo } from 'react';
import { AgentEvent, ChartSpec, PlanStep, RunStatus } from '../types';

export function useRunState() {
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<RunStatus>('idle');
  const [userQuestion, setUserQuestion] = useState<string>('');
  const [plan, setPlan] = useState<PlanStep[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [charts, setCharts] = useState<ChartSpec[]>([]);
  const [finalReport, setFinalReport] = useState<string | null>(null);
  const [pendingCode, setPendingCode] = useState<string>('');
  const [currentStepIdx, setCurrentStepIdx] = useState<number>(0);
  const [perStepRetryCount, setPerStepRetryCount] = useState<number>(0);
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [activeSeconds, setActiveSeconds] = useState<number>(0);

  const highestSeq = useMemo(() => {
    if (events.length === 0) return 0;
    return Math.max(...events.map((e) => e.seq));
  }, [events]);

  const handleIncomingEvent = useCallback((event: AgentEvent) => {
    setEvents((prev) => {
      // Deduplicate by seq and maintain monotonic ordering
      if (prev.some((e) => e.seq === event.seq)) return prev;
      const updated = [...prev, event];
      updated.sort((a, b) => a.seq - b.seq);
      return updated;
    });

    switch (event.event_type) {
      case 'plan':
        if (event.data?.steps) {
          setPlan(event.data.steps);
        }
        break;

      case 'code':
        if (event.data?.code) {
          setPendingCode(event.data.code);
        }
        break;

      case 'chart':
        if (event.data?.chart) {
          setCharts((prev) => [...prev, event.data.chart]);
        }
        break;

      case 'report':
        if (event.data?.markdown) {
          setFinalReport(event.data.markdown);
        }
        break;

      case 'paused':
        setIsPaused(true);
        setStatus('paused');
        if (event.data?.pending_code) {
          setPendingCode(event.data.pending_code);
        }
        break;

      case 'resumed':
        setIsPaused(false);
        setStatus('running');
        if (event.data?.code) {
          setPendingCode(event.data.code);
        }
        break;

      case 'run_status':
        if (event.data?.status) {
          setStatus(event.data.status as RunStatus);
          if (event.data.status === 'completed' || event.data.status === 'failed' || event.data.status === 'aborted') {
            setIsPaused(false);
          }
        }
        break;

      case 'retry':
        if (typeof event.data?.retry_count === 'number') {
          setPerStepRetryCount(event.data.retry_count);
        }
        break;

      case 'execution_started':
        if (typeof event.data?.step_id === 'number') {
          setCurrentStepIdx(event.data.step_id - 1);
        }
        break;

      default:
        break;
    }
  }, []);

  const startRun = async (
    question: string,
    datasetPath: string,
    filename: string,
    reviewBeforeRun: boolean
  ) => {
    setUserQuestion(question);
    setStatus('pending');
    setEvents([]);
    setPlan([]);
    setCharts([]);
    setFinalReport(null);
    setPendingCode('');
    setCurrentStepIdx(0);
    setPerStepRetryCount(0);
    setIsPaused(false);

    const res = await fetch('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_question: question,
        dataset_path: datasetPath,
        filename,
        review_before_run: reviewBeforeRun,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to start run');
    }

    const data = await res.json();
    setRunId(data.run_id);
    return data.run_id;
  };

  const pauseRun = async () => {
    if (!runId) return;
    await fetch(`/api/runs/${runId}/pause`, { method: 'POST' });
    setIsPaused(true);
    setStatus('paused');
  };

  const resumeRun = async (editedCode?: string) => {
    if (!runId) return;
    await fetch(`/api/runs/${runId}/resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ edited_code: editedCode }),
    });
    setIsPaused(false);
    setStatus('running');
  };

  const abortRun = async () => {
    if (!runId) return;
    await fetch(`/api/runs/${runId}/abort`, { method: 'POST' });
    setStatus('aborted');
    setIsPaused(false);
  };

  return {
    runId,
    status,
    userQuestion,
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
  };
}
