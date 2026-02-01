/**
 * Main application component.
 * Single page at /admin that handles both job creation and job viewing.
 *
 * Route:
 *   /admin          - Admin dashboard (create job or view existing job)
 *   /admin?jobId=x  - View specific job
 */

import { useState, useCallback, useEffect } from 'react';
import { AdminPage } from './pages/AdminPage';

const BASE_PATH = '/admin';

/**
 * Check if current path is the admin route.
 */
function isAdminPath(): boolean {
  return window.location.pathname === BASE_PATH || window.location.pathname === `${BASE_PATH}/`;
}

/**
 * Read job ID from URL query params.
 */
function getJobIdFromUrl(): string | null {
  const params = new URLSearchParams(window.location.search);
  return params.get('jobId');
}

/**
 * Update URL with job ID (or clear it).
 */
function updateUrl(jobId: string | null): void {
  const url = new URL(window.location.origin + BASE_PATH);
  if (jobId) {
    url.searchParams.set('jobId', jobId);
  }
  window.history.pushState({}, '', url.toString());
}

/**
 * Get initial job ID from URL.
 * Redirects to /admin if accessing root or unknown path.
 */
function getInitialJobId(): string | null {
  // Redirect to /admin if not already there
  if (!isAdminPath()) {
    const jobId = getJobIdFromUrl();
    const url = new URL(window.location.origin + BASE_PATH);
    if (jobId) {
      url.searchParams.set('jobId', jobId);
    }
    window.history.replaceState({}, '', url.toString());
  }

  return getJobIdFromUrl();
}

function App() {
  const [jobId, setJobId] = useState<string | null>(getInitialJobId);

  // Handle browser back/forward navigation
  useEffect(() => {
    const handlePopState = () => {
      setJobId(getJobIdFromUrl());
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const handleJobSelect = useCallback((newJobId: string) => {
    updateUrl(newJobId);
    setJobId(newJobId);
  }, []);

  const handleClearJob = useCallback(() => {
    updateUrl(null);
    setJobId(null);
  }, []);

  return (
    <AdminPage
      jobId={jobId}
      onJobSelect={handleJobSelect}
      onClearJob={handleClearJob}
    />
  );
}

export default App;
