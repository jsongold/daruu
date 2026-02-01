import { useState, useEffect } from "react";
import { JobViewer } from "./JobViewer";
import { JobCreator } from "./JobCreator";
import { getJob, checkApiHealth } from "../api/jobClient";
import "./JobInput.css";

type ViewMode = "input" | "create" | "viewer";

export function JobInput() {
  const [viewMode, setViewMode] = useState<ViewMode>("input");
  const [jobId, setJobId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    // Check API health on mount
    checkApiHealth().then(setApiHealthy);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!jobId.trim()) return;
    
    setLoading(true);
    setError(null);
    
    try {
      // Validate job exists before showing viewer
      await getJob(jobId.trim());
      setViewMode("viewer");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load job");
    } finally {
      setLoading(false);
    }
  };

  const handleJobCreated = (newJobId: string) => {
    setJobId(newJobId);
    setViewMode("viewer");
  };

  if (viewMode === "viewer" && jobId) {
    return <JobViewer jobId={jobId} />;
  }

  if (viewMode === "create") {
    return (
      <div className="job-input">
        <div className="job-input-container">
          <button
            onClick={() => setViewMode("input")}
            className="btn-back"
          >
            ← Back
          </button>
          <JobCreator onJobCreated={handleJobCreated} />
        </div>
      </div>
    );
  }

  return (
    <div className="job-input">
      <div className="job-input-container">
        <h1>Daru PDF - Job Viewer</h1>
        <p>Upload documents to create a new job or enter an existing job ID</p>
        
        {apiHealthy === false && (
          <div className="job-input-warning">
            ⚠️ Cannot connect to API at {import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"}
            <br />
            <small>Make sure the API server is running: <code>make run-api</code></small>
          </div>
        )}
        
        {apiHealthy === true && (
          <div className="job-input-success">
            ✓ Connected to API
          </div>
        )}

        <div className="job-input-tabs">
          <button
            onClick={() => setViewMode("create")}
            className="tab-button"
            disabled={apiHealthy === false}
          >
            📤 Create New Job
          </button>
          <button
            onClick={() => setViewMode("input")}
            className="tab-button active"
            disabled={apiHealthy === false}
          >
            🔍 Load Existing Job
          </button>
        </div>

        {viewMode === "input" && (
          <>
            <form onSubmit={handleSubmit} className="job-input-form">
              <input
                type="text"
                value={jobId}
                onChange={(e) => setJobId(e.target.value)}
                placeholder="Enter job ID (e.g., dae6caff-e436-4643-a841-f2e0c5ba3ae1)"
                className="job-input-field"
                required
                disabled={apiHealthy === false}
              />
              <button 
                type="submit" 
                className="btn-primary" 
                disabled={loading || apiHealthy === false}
              >
                {loading ? "Loading..." : "Load Job"}
              </button>
            </form>
            
            {error && (
              <div className="job-input-error">
                <strong>Error:</strong> {error}
                <br />
                <small>
                  <strong>Common causes:</strong>
                  <ul>
                    <li><strong>Job not found:</strong> Jobs are stored in-memory and are lost when the server restarts. You need to create a new job.</li>
                    <li><strong>Wrong job ID:</strong> Double-check the job ID from your terminal/API response</li>
                    <li><strong>Server restarted:</strong> If the API server was restarted, all jobs are lost</li>
                  </ul>
                  <strong>Solution:</strong> Use "Create New Job" tab to upload documents and create a new job.
                </small>
              </div>
            )}
            
            <div className="job-input-hint">
              <p><strong>Note:</strong> Jobs are stored in-memory and will be lost if the server restarts.</p>
              <p>Example job ID from your terminal:</p>
              <code>dae6caff-e436-4643-a841-f2e0c5ba3ae1</code>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
