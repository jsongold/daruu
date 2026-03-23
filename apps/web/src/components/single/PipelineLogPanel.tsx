/**
 * PipelineLogPanel — vertical timeline of pipeline step execution logs.
 *
 * Designed for human readability during prompt tuning:
 * - Scannable timeline with step name, duration bar, and status icon
 * - 1-line summary always visible (no click needed)
 * - Collapsible details for drill-down into sources, prompts, actions
 * - Color coding: green=success, red=error, gray=skipped
 * - Duration bars showing proportional time per step
 */

import { useState } from 'react';
import type { PipelineStepLog } from '../../api/autofillPipelineClient';

interface PipelineLogPanelProps {
  stepLogs: PipelineStepLog[];
}

const STEP_LABELS: Record<string, string> = {
  context_build: 'Context Build',
  rule_analyze: 'Rule Analysis',
  reasoning_precheck: 'Reasoning Pre-Check',
  fill_plan: 'Fill Planning (LLM)',
  fill_plan_turn: 'Fill Plan Turn (LLM)',
  render: 'Render',
};

function StatusIcon({ status }: { status: string }) {
  if (status === 'success') {
    return <span className="text-green-500 text-sm font-bold">&#x2713;</span>;
  }
  if (status === 'error') {
    return <span className="text-red-500 text-sm font-bold">&#x2717;</span>;
  }
  return <span className="text-gray-400 text-sm">&mdash;</span>;
}

function DurationBar({ durationMs, maxMs }: { durationMs: number; maxMs: number }) {
  const pct = maxMs > 0 ? Math.max((durationMs / maxMs) * 100, 2) : 0;
  return (
    <div className="w-20 h-1.5 bg-gray-100 rounded-full overflow-hidden">
      <div
        className="h-full bg-blue-400 rounded-full transition-all"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function formatMs(ms: number): string {
  if (ms >= 1000) {
    return `${(ms / 1000).toFixed(1)}s`;
  }
  return `${ms}ms`;
}

export function PipelineLogPanel({ stepLogs }: PipelineLogPanelProps) {
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());

  if (stepLogs.length === 0) {
    return (
      <div className="p-4 text-center">
        <p className="text-sm text-gray-500">No pipeline logs yet</p>
        <p className="text-xs text-gray-400 mt-1">Run autofill to see step-by-step execution logs</p>
      </div>
    );
  }

  const totalMs = stepLogs.reduce((sum, s) => sum + s.duration_ms, 0);
  const maxStepMs = Math.max(...stepLogs.map(s => s.duration_ms));

  const toggleStep = (name: string) => {
    setExpandedSteps(prev => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  };

  return (
    <div className="p-4 space-y-1">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-800">Pipeline Execution</h3>
        <span className="text-xs text-gray-500">total: {formatMs(totalMs)}</span>
      </div>

      {/* Timeline */}
      <div className="space-y-2">
        {stepLogs.map(log => {
          const isExpanded = expandedSteps.has(log.step_name);
          const label = STEP_LABELS[log.step_name] || log.step_name;

          return (
            <div key={log.step_name} className="border border-gray-200 rounded-lg overflow-hidden">
              {/* Step header — always visible */}
              <button
                onClick={() => toggleStep(log.step_name)}
                className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-50 transition-colors"
              >
                <StatusIcon status={log.status} />
                <span className="text-sm font-medium text-gray-700 whitespace-nowrap">{label}</span>
                <DurationBar durationMs={log.duration_ms} maxMs={maxStepMs} />
                <span className="text-xs text-gray-500 whitespace-nowrap ml-auto">{formatMs(log.duration_ms)}</span>
                <svg
                  className={`w-3.5 h-3.5 text-gray-400 transition-transform shrink-0 ${isExpanded ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {/* Summary line — always visible below header */}
              <div className="px-3 pb-2 -mt-1">
                <p className="text-xs text-gray-500 ml-5">{log.summary}</p>
              </div>

              {/* Error message */}
              {log.error && (
                <div className="mx-3 mb-2 px-2 py-1 bg-red-50 rounded text-xs text-red-700">
                  {log.error}
                </div>
              )}

              {/* Expanded details */}
              {isExpanded && (
                <div className="border-t border-gray-100 bg-gray-50 px-3 py-2">
                  <StepDetails stepName={log.step_name} details={log.details} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================================
// Step-specific detail renderers
// ============================================================================

function StepDetails({ stepName, details }: { stepName: string; details: Record<string, unknown> }) {
  switch (stepName) {
    case 'context_build':
      return <ContextBuildDetails details={details} />;
    case 'rule_analyze':
      return <RuleAnalyzeDetails details={details} />;
    case 'fill_plan':
    case 'fill_plan_turn':
      return <FillPlanDetails details={details} />;
    case 'render':
      return <RenderDetails details={details} />;
    default:
      return <GenericDetails details={details} />;
  }
}

// --- Context Build ---

interface DataSourceInfo {
  name: string;
  type: string;
  field_count: number;
}

interface CandidateInfo {
  field_id: string;
  source_key: string;
  score: number;
}

function ContextBuildDetails({ details }: { details: Record<string, unknown> }) {
  const sources = (details.data_sources || []) as DataSourceInfo[];
  const candidates = (details.top_candidates || []) as CandidateInfo[];

  return (
    <div className="space-y-2">
      {sources.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-gray-600 mb-1">Data Sources</h4>
          <div className="space-y-0.5">
            {sources.map((s, i) => (
              <div key={i} className="flex justify-between text-xs text-gray-600">
                <span>{s.name} <span className="text-gray-400">({s.type})</span></span>
                <span className="text-gray-400">{s.field_count} fields</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {candidates.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-gray-600 mb-1">Top Matches</h4>
          <div className="space-y-0.5">
            {candidates.map((c, i) => (
              <div key={i} className="flex items-center gap-1.5 text-xs text-gray-600">
                <span className="font-medium">{c.field_id}</span>
                <span className="text-gray-400">&larr;</span>
                <span>{c.source_key}</span>
                <span className="ml-auto text-gray-400">({c.score.toFixed(2)})</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// --- Rule Analyze ---

function RuleAnalyzeDetails({ details }: { details: Record<string, unknown> }) {
  const rules = (details.rules || []) as string[];

  if (rules.length === 0) {
    return <p className="text-xs text-gray-400">No rules applied</p>;
  }

  return (
    <div>
      <h4 className="text-xs font-medium text-gray-600 mb-1">Rules</h4>
      <ul className="space-y-0.5">
        {rules.map((r, i) => (
          <li key={i} className="text-xs text-gray-600 bg-white rounded px-2 py-1">{r}</li>
        ))}
      </ul>
    </div>
  );
}

// --- Fill Plan ---

interface ActionInfo {
  field_id: string;
  action: string;
  value?: string | null;
  confidence?: number;
  reason?: string | null;
}

function FillPlanDetails({ details }: { details: Record<string, unknown> }) {
  const [showPrompt, setShowPrompt] = useState(false);
  const [showResponse, setShowResponse] = useState(false);
  const [showActions, setShowActions] = useState(false);

  const modelUsed = details.model_used as string | null;
  const systemPrompt = details.system_prompt as string | null;
  const userPrompt = details.user_prompt as string | null;
  const rawResponse = details.raw_llm_response as string | null;
  const actions = (details.actions || []) as ActionInfo[];

  return (
    <div className="space-y-2">
      {modelUsed && (
        <div className="text-xs text-gray-500">Model: <span className="font-medium text-gray-700">{modelUsed}</span></div>
      )}

      {/* Prompt toggle */}
      {(systemPrompt || userPrompt) && (
        <div className="border border-gray-200 rounded overflow-hidden">
          <button
            onClick={() => setShowPrompt(p => !p)}
            className="w-full flex items-center justify-between px-2 py-1.5 text-xs font-medium text-gray-600 hover:bg-white transition-colors"
          >
            <span>Prompt</span>
            <span className="text-gray-400">{showPrompt ? '▲' : '▼'}</span>
          </button>
          {showPrompt && (
            <div className="border-t border-gray-200 bg-white px-2 py-2 space-y-2">
              {systemPrompt && (
                <div>
                  <div className="text-xs font-medium text-gray-500 mb-0.5">System</div>
                  <pre className="text-xs font-mono whitespace-pre-wrap text-gray-700 max-h-48 overflow-y-auto bg-gray-50 rounded p-2">
                    {systemPrompt}
                  </pre>
                </div>
              )}
              {userPrompt && (
                <div>
                  <div className="text-xs font-medium text-gray-500 mb-0.5">User</div>
                  <pre className="text-xs font-mono whitespace-pre-wrap text-gray-700 max-h-48 overflow-y-auto bg-gray-50 rounded p-2">
                    {userPrompt}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* LLM Response toggle */}
      {rawResponse && (
        <div className="border border-gray-200 rounded overflow-hidden">
          <button
            onClick={() => setShowResponse(r => !r)}
            className="w-full flex items-center justify-between px-2 py-1.5 text-xs font-medium text-gray-600 hover:bg-white transition-colors"
          >
            <span>LLM Response</span>
            <span className="text-gray-400">{showResponse ? '▲' : '▼'}</span>
          </button>
          {showResponse && (
            <div className="border-t border-gray-200 bg-white px-2 py-2">
              <pre className="text-xs font-mono whitespace-pre-wrap text-gray-700 max-h-64 overflow-y-auto bg-gray-50 rounded p-2">
                {formatJsonSafe(rawResponse)}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Actions toggle */}
      {actions.length > 0 && (
        <div className="border border-gray-200 rounded overflow-hidden">
          <button
            onClick={() => setShowActions(a => !a)}
            className="w-full flex items-center justify-between px-2 py-1.5 text-xs font-medium text-gray-600 hover:bg-white transition-colors"
          >
            <span>Actions ({actions.length})</span>
            <span className="text-gray-400">{showActions ? '▲' : '▼'}</span>
          </button>
          {showActions && (
            <div className="border-t border-gray-200 bg-white px-2 py-2 space-y-1">
              {actions.map((a, i) => (
                <ActionRow key={i} action={a} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ActionRow({ action }: { action: ActionInfo }) {
  const isFill = action.action === 'fill';
  const isSkip = action.action === 'skip';

  return (
    <div className="flex items-start gap-1.5 text-xs">
      <span className="mt-0.5 shrink-0">
        {isFill && <ConfidenceDot confidence={action.confidence ?? 0} />}
        {isSkip && <span className="inline-block w-2 h-2 rounded-full bg-gray-300 mt-0.5" />}
        {!isFill && !isSkip && <span className="inline-block w-2 h-2 rounded-full bg-amber-400 mt-0.5" />}
      </span>
      <span className="font-medium text-gray-700">{action.field_id}</span>
      {isFill && action.value && (
        <>
          <span className="text-gray-400">=</span>
          <span className="text-gray-600 truncate max-w-[120px]">&quot;{action.value}&quot;</span>
          {action.confidence != null && (
            <span className="text-gray-400 ml-auto shrink-0">({(action.confidence * 100).toFixed(0)}%)</span>
          )}
        </>
      )}
      {isSkip && action.reason && (
        <span className="text-gray-400 truncate">&mdash; {action.reason}</span>
      )}
    </div>
  );
}

function ConfidenceDot({ confidence }: { confidence: number }) {
  let color = 'bg-orange-400';
  if (confidence >= 0.9) {
    color = 'bg-green-500';
  } else if (confidence >= 0.7) {
    color = 'bg-yellow-400';
  }
  return <span className={`inline-block w-2 h-2 rounded-full ${color}`} />;
}

// --- Render ---

interface FieldResultInfo {
  field_id: string;
  status: string;
  value_written?: string | null;
}

function RenderDetails({ details }: { details: Record<string, unknown> }) {
  const results = (details.field_results || []) as FieldResultInfo[];
  const docRef = details.filled_document_ref as string | null;

  return (
    <div className="space-y-2">
      {docRef && (
        <div className="text-xs text-gray-500">Output: <span className="font-mono text-gray-600">{docRef}</span></div>
      )}
      {results.length > 0 && (
        <div className="space-y-0.5">
          {results.map((r, i) => (
            <div key={i} className="flex items-center gap-1.5 text-xs text-gray-600">
              <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${
                r.status === 'success' ? 'bg-green-500' : r.status === 'failed' ? 'bg-red-500' : 'bg-gray-300'
              }`} />
              <span className="font-medium">{r.field_id}</span>
              {r.value_written && (
                <span className="text-gray-400 truncate max-w-[150px]">{r.value_written}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// --- Generic fallback ---

function GenericDetails({ details }: { details: Record<string, unknown> }) {
  return (
    <pre className="text-xs font-mono whitespace-pre-wrap text-gray-700 max-h-64 overflow-y-auto">
      {JSON.stringify(details, null, 2)}
    </pre>
  );
}

// --- Helpers ---

function formatJsonSafe(raw: string): string {
  try {
    const parsed = JSON.parse(raw);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return raw;
  }
}
