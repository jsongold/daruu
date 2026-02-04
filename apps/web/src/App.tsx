/**
 * Main application component with routing.
 *
 * Routes:
 *   /           - Agent Chat UI (new conversational interface)
 *   /chat       - Agent Chat UI (alias)
 *   /single     - Single-page editor (simple PDF editing)
 *   /admin      - Admin dashboard (legacy job management)
 *   /admin?jobId=x - View specific job
 */

import { useState, useCallback, useEffect } from 'react';
import { AdminPage } from './pages/AdminPage';
import { ChatPage } from './pages/ChatPage';
import { SinglePage } from './pages/SinglePage';
import './App.css';

type AppRoute = 'chat' | 'single' | 'admin';

/**
 * Determine current route from URL path.
 */
function getCurrentRoute(): AppRoute {
  const path = window.location.pathname;
  if (path === '/admin' || path === '/admin/') {
    return 'admin';
  }
  if (path === '/single' || path === '/single/') {
    return 'single';
  }
  // Default to chat for /, /chat, or any other path
  return 'chat';
}

/**
 * Read job ID from URL query params (for admin page).
 */
function getJobIdFromUrl(): string | null {
  const params = new URLSearchParams(window.location.search);
  return params.get('jobId');
}

/**
 * Update URL for admin page with job ID.
 */
function updateAdminUrl(jobId: string | null): void {
  const url = new URL(window.location.origin + '/admin');
  if (jobId) {
    url.searchParams.set('jobId', jobId);
  }
  window.history.pushState({}, '', url.toString());
}

function App() {
  const [route, setRoute] = useState<AppRoute>(getCurrentRoute);
  const [jobId, setJobId] = useState<string | null>(getJobIdFromUrl);

  // Handle browser back/forward navigation
  useEffect(() => {
    const handlePopState = () => {
      setRoute(getCurrentRoute());
      setJobId(getJobIdFromUrl());
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Admin page handlers
  const handleJobSelect = useCallback((newJobId: string) => {
    updateAdminUrl(newJobId);
    setJobId(newJobId);
  }, []);

  const handleClearJob = useCallback(() => {
    updateAdminUrl(null);
    setJobId(null);
  }, []);

  // Navigation between routes
  const navigateTo = useCallback((newRoute: AppRoute) => {
    const pathMap: Record<AppRoute, string> = {
      chat: '/',
      single: '/single',
      admin: '/admin',
    };
    window.history.pushState({}, '', pathMap[newRoute]);
    setRoute(newRoute);
  }, []);

  // Render based on route
  if (route === 'admin') {
    return (
      <div className="app">
        <nav className="app-nav">
          <button className="nav-link" onClick={() => navigateTo('chat')}>
            ← Back to Chat
          </button>
        </nav>
        <AdminPage
          jobId={jobId}
          onJobSelect={handleJobSelect}
          onClearJob={handleClearJob}
        />
      </div>
    );
  }

  if (route === 'single') {
    return <SinglePage />;
  }

  // Default: Chat page
  return (
    <div className="app">
      <ChatPage />
    </div>
  );
}

export default App;
