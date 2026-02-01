import { useState } from "react";
import "./RawJsonViewer.css";

interface RawJsonViewerProps {
  data: unknown;
  title?: string;
}

export function RawJsonViewer({ data, title = "Raw JSON" }: RawJsonViewerProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [copied, setCopied] = useState(false);

  const formattedJson = JSON.stringify(data, null, 2);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(formattedJson);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      // Fallback for browsers that don't support clipboard API
      const textArea = document.createElement("textarea");
      textArea.value = formattedJson;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand("copy");
      document.body.removeChild(textArea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="raw-json-viewer">
      <div className="raw-json-header">
        <button
          className="raw-json-toggle"
          onClick={() => setIsCollapsed(!isCollapsed)}
          aria-label={isCollapsed ? "Expand JSON" : "Collapse JSON"}
        >
          <span className={`toggle-icon ${isCollapsed ? "collapsed" : ""}`}>
            {isCollapsed ? "+" : "-"}
          </span>
          <h3 className="raw-json-title">{title}</h3>
        </button>
        <div className="raw-json-actions">
          <button
            className="raw-json-copy-btn"
            onClick={handleCopy}
            aria-label="Copy JSON to clipboard"
          >
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
      </div>
      {!isCollapsed && (
        <div className="raw-json-content">
          <pre className="raw-json-pre">
            <code className="raw-json-code">{formattedJson}</code>
          </pre>
        </div>
      )}
    </div>
  );
}
