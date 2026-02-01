/**
 * Custom hooks for job state management.
 * Provides polling and real-time updates for job context.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { JobContext, JobStatus, RunMode } from '../types/api';
import {
  getJob,
  runJob,
  submitAnswers,
  submitEdits,
  subscribeToJobEvents,
  ApiError,
} from '../api/client';
import type { FieldAnswer, FieldEdit } from '../types/api';

export interface UseJobOptions {
  /** Poll interval in milliseconds (default: 2000) */
  pollInterval?: number;
  /** Whether to use SSE for real-time updates */
  useSSE?: boolean;
  /** Whether to start polling immediately */
  autoStart?: boolean;
}

export interface UseJobReturn {
  /** Current job context */
  job: JobContext | null;
  /** Loading state */
  loading: boolean;
  /** Error message if any */
  error: string | null;
  /** Whether the job is in a running state */
  isRunning: boolean;
  /** Refresh the job data */
  refresh: () => Promise<void>;
  /** Run the job with specified mode */
  run: (mode: RunMode, maxSteps?: number) => Promise<void>;
  /** Submit answers for fields */
  submitFieldAnswers: (answers: FieldAnswer[]) => Promise<void>;
  /** Submit edits for fields */
  submitFieldEdits: (edits: FieldEdit[]) => Promise<void>;
  /** Clear error */
  clearError: () => void;
}

const RUNNING_STATUSES: JobStatus[] = ['running', 'awaiting_input'];

export function useJob(jobId: string | null, options: UseJobOptions = {}): UseJobReturn {
  const {
    pollInterval = 2000,
    useSSE = false,
    autoStart = true,
  } = options;

  const [job, setJob] = useState<JobContext | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  const pollTimeoutRef = useRef<number | null>(null);
  const sseCleanupRef = useRef<(() => void) | null>(null);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const fetchJob = useCallback(async () => {
    if (!jobId) return;

    try {
      const data = await getJob(jobId);
      setJob(data);
      setError(null);
      return data;
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to fetch job';
      setError(message);
      throw err;
    }
  }, [jobId]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      await fetchJob();
    } finally {
      setLoading(false);
    }
  }, [fetchJob]);

  const run = useCallback(async (mode: RunMode, maxSteps?: number) => {
    if (!jobId) return;

    setIsRunning(true);
    setError(null);

    try {
      const result = await runJob(jobId, {
        run_mode: mode,
        max_steps: maxSteps,
      });
      setJob(result.job_context);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to run job';
      setError(message);
      throw err;
    } finally {
      setIsRunning(false);
    }
  }, [jobId]);

  const submitFieldAnswers = useCallback(async (answers: FieldAnswer[]) => {
    if (!jobId || answers.length === 0) return;

    setIsRunning(true);
    setError(null);

    try {
      const updatedJob = await submitAnswers(jobId, answers);
      setJob(updatedJob);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to submit answers';
      setError(message);
      throw err;
    } finally {
      setIsRunning(false);
    }
  }, [jobId]);

  const submitFieldEdits = useCallback(async (edits: FieldEdit[]) => {
    if (!jobId || edits.length === 0) return;

    setIsRunning(true);
    setError(null);

    try {
      const updatedJob = await submitEdits(jobId, edits);
      setJob(updatedJob);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to submit edits';
      setError(message);
      throw err;
    } finally {
      setIsRunning(false);
    }
  }, [jobId]);

  // Initial fetch
  useEffect(() => {
    if (!jobId || !autoStart) return;

    setLoading(true);
    fetchJob().finally(() => setLoading(false));
  }, [jobId, autoStart, fetchJob]);

  // Polling for running jobs
  useEffect(() => {
    if (!jobId || !job || useSSE) return;

    const shouldPoll = RUNNING_STATUSES.includes(job.status);

    if (shouldPoll) {
      pollTimeoutRef.current = window.setTimeout(async () => {
        try {
          await fetchJob();
        } catch {
          // Error already handled in fetchJob
        }
      }, pollInterval);
    }

    return () => {
      if (pollTimeoutRef.current) {
        window.clearTimeout(pollTimeoutRef.current);
        pollTimeoutRef.current = null;
      }
    };
  }, [jobId, job, useSSE, pollInterval, fetchJob]);

  // SSE subscription
  useEffect(() => {
    if (!jobId || !useSSE) return;

    sseCleanupRef.current = subscribeToJobEvents(
      jobId,
      (event) => {
        // Refresh on certain events
        if (
          event.event === 'status_changed' ||
          event.event === 'field_updated' ||
          event.event === 'job_completed'
        ) {
          fetchJob().catch(() => {
            // Error handled in fetchJob
          });
        }
      },
      (err) => {
        // Fall back to polling on SSE error
        setError(`Real-time connection error: ${err.message}`);
      }
    );

    return () => {
      if (sseCleanupRef.current) {
        sseCleanupRef.current();
        sseCleanupRef.current = null;
      }
    };
  }, [jobId, useSSE, fetchJob]);

  return {
    job,
    loading,
    error,
    isRunning,
    refresh,
    run,
    submitFieldAnswers,
    submitFieldEdits,
    clearError,
  };
}

/**
 * Hook for simple job polling without actions.
 */
export function useJobPolling(
  jobId: string | null,
  intervalMs: number = 2000
): { job: JobContext | null; loading: boolean; error: string | null } {
  const { job, loading, error } = useJob(jobId, {
    pollInterval: intervalMs,
    useSSE: false,
    autoStart: true,
  });

  return { job, loading, error };
}
