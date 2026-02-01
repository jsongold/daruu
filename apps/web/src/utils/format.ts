/**
 * Formatting utilities for display values.
 */

/**
 * Format a file size in bytes to a human-readable string.
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

/**
 * Format a cost value in USD.
 */
export function formatCost(value: number): string {
  if (value === 0) return '$0.00';
  if (value < 0.01) return `$${value.toFixed(6)}`;
  if (value < 1) return `$${value.toFixed(4)}`;
  return `$${value.toFixed(2)}`;
}

/**
 * Format a percentage value.
 */
export function formatPercent(value: number, decimals: number = 0): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * Format a confidence score with color coding.
 */
export function getConfidenceColor(confidence: number | null): string {
  if (confidence === null) return '#9ca3af'; // gray-400
  if (confidence >= 0.8) return '#22c55e'; // green-500
  if (confidence >= 0.5) return '#eab308'; // yellow-500
  return '#ef4444'; // red-500
}

/**
 * Get confidence level label.
 */
export function getConfidenceLevel(confidence: number | null): string {
  if (confidence === null) return 'Unknown';
  if (confidence >= 0.8) return 'High';
  if (confidence >= 0.5) return 'Medium';
  return 'Low';
}

/**
 * Format a date string.
 */
export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/**
 * Format a datetime string.
 */
export function formatDateTime(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Format a relative time string (e.g., "2 minutes ago").
 */
export function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return 'just now';
  if (diffMin < 60) return `${diffMin} minute${diffMin === 1 ? '' : 's'} ago`;
  if (diffHour < 24) return `${diffHour} hour${diffHour === 1 ? '' : 's'} ago`;
  if (diffDay < 7) return `${diffDay} day${diffDay === 1 ? '' : 's'} ago`;
  return formatDate(dateString);
}

/**
 * Truncate a string with ellipsis.
 */
export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return `${str.slice(0, maxLength - 3)}...`;
}

/**
 * Truncate a UUID for display.
 */
export function truncateId(id: string, chars: number = 8): string {
  if (id.length <= chars) return id;
  return `${id.slice(0, chars)}...`;
}

/**
 * Get status color based on job/task status.
 */
export function getStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case 'done':
    case 'completed':
    case 'healthy':
      return '#22c55e'; // green-500
    case 'running':
    case 'pending':
      return '#3b82f6'; // blue-500
    case 'awaiting_input':
    case 'blocked':
    case 'degraded':
      return '#eab308'; // yellow-500
    case 'failed':
    case 'error':
    case 'unhealthy':
      return '#ef4444'; // red-500
    default:
      return '#6b7280'; // gray-500
  }
}

/**
 * Get status background color (lighter version).
 */
export function getStatusBgColor(status: string): string {
  switch (status.toLowerCase()) {
    case 'done':
    case 'completed':
    case 'healthy':
      return '#dcfce7'; // green-100
    case 'running':
    case 'pending':
      return '#dbeafe'; // blue-100
    case 'awaiting_input':
    case 'blocked':
    case 'degraded':
      return '#fef3c7'; // yellow-100
    case 'failed':
    case 'error':
    case 'unhealthy':
      return '#fee2e2'; // red-100
    default:
      return '#f3f4f6'; // gray-100
  }
}

/**
 * Format a status string for display.
 */
export function formatStatus(status: string): string {
  return status
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

/**
 * Get issue severity color.
 */
export function getSeverityColor(severity: string): string {
  switch (severity.toLowerCase()) {
    case 'critical':
    case 'error':
    case 'high':
      return '#ef4444'; // red-500
    case 'warning':
      return '#eab308'; // yellow-500
    case 'info':
      return '#3b82f6'; // blue-500
    default:
      return '#6b7280'; // gray-500
  }
}
