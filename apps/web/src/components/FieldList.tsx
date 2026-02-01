import { useState } from "react";
import type { Field, Issue } from "../api/jobClient";
import "./FieldList.css";

interface FieldListProps {
  fields: Field[];
  issues: Issue[];
  onFieldSelect?: (field: Field) => void;
  onFieldEdit?: (fieldId: string, value: string) => void;
}

export function FieldList({
  fields,
  issues,
  onFieldSelect,
  onFieldEdit,
}: FieldListProps) {
  const [filter, setFilter] = useState<"all" | "issues" | "low_confidence" | "missing">("all");
  const [sortBy, setSortBy] = useState<"name" | "confidence" | "page">("name");
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>("");

  const getFieldIssues = (fieldId: string): Issue[] => {
    return issues.filter((issue) => issue.field_id === fieldId);
  };

  const getConfidenceColor = (confidence: number | null): string => {
    if (confidence === null) return "#999";
    if (confidence >= 0.8) return "#22c55e"; // green
    if (confidence >= 0.5) return "#eab308"; // yellow
    return "#ef4444"; // red
  };

  const filteredFields = fields.filter((field) => {
    if (filter === "all") return true;
    if (filter === "issues") return getFieldIssues(field.id).length > 0;
    if (filter === "low_confidence")
      return field.confidence !== null && field.confidence < 0.7;
    if (filter === "missing") return !field.value;
    return true;
  });

  const sortedFields = [...filteredFields].sort((a, b) => {
    if (sortBy === "name") return a.name.localeCompare(b.name);
    if (sortBy === "confidence") {
      const confA = a.confidence ?? 0;
      const confB = b.confidence ?? 0;
      return confB - confA;
    }
    if (sortBy === "page") return a.page - b.page;
    return 0;
  });

  const handleEdit = (field: Field) => {
    setEditingField(field.id);
    setEditValue(field.value || "");
  };

  const handleSave = (fieldId: string) => {
    if (onFieldEdit) {
      onFieldEdit(fieldId, editValue);
    }
    setEditingField(null);
    setEditValue("");
  };

  const handleCancel = () => {
    setEditingField(null);
    setEditValue("");
  };

  return (
    <div className="field-list">
      <div className="field-list-header">
        <h2>Fields ({filteredFields.length})</h2>
        <div className="field-list-controls">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as any)}
            className="filter-select"
          >
            <option value="all">All Fields</option>
            <option value="issues">With Issues</option>
            <option value="low_confidence">Low Confidence</option>
            <option value="missing">Missing Values</option>
          </select>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            className="sort-select"
          >
            <option value="name">Sort by Name</option>
            <option value="confidence">Sort by Confidence</option>
            <option value="page">Sort by Page</option>
          </select>
        </div>
      </div>

      <div className="field-list-items">
        {sortedFields.map((field) => {
          const fieldIssues = getFieldIssues(field.id);
          const isEditing = editingField === field.id;

          return (
            <div
              key={field.id}
              className={`field-item ${fieldIssues.length > 0 ? "has-issues" : ""} ${
                field.confidence !== null && field.confidence < 0.7 ? "low-confidence" : ""
              } ${!field.value ? "missing-value" : ""}`}
              onClick={() => onFieldSelect?.(field)}
            >
              <div className="field-item-header">
                <div className="field-name-row">
                  <span className="field-name">{field.name}</span>
                  <span className="field-type">{field.field_type}</span>
                  {field.is_required && (
                    <span className="field-required">Required</span>
                  )}
                </div>
                {field.confidence !== null && (
                  <div
                    className="field-confidence"
                    style={{ color: getConfidenceColor(field.confidence) }}
                  >
                    {(field.confidence * 100).toFixed(0)}%
                  </div>
                )}
              </div>

              {isEditing ? (
                <div className="field-edit">
                  <input
                    type="text"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    className="field-edit-input"
                    autoFocus
                  />
                  <div className="field-edit-actions">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSave(field.id);
                      }}
                      className="btn-save"
                    >
                      Save
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleCancel();
                      }}
                      className="btn-cancel"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="field-value-row">
                  <div className="field-value">
                    {field.value || (
                      <span className="field-value-empty">No value</span>
                    )}
                  </div>
                  {field.is_editable && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleEdit(field);
                      }}
                      className="btn-edit"
                    >
                      Edit
                    </button>
                  )}
                </div>
              )}

              {fieldIssues.length > 0 && (
                <div className="field-issues">
                  {fieldIssues.map((issue) => (
                    <div
                      key={issue.id}
                      className={`field-issue field-issue-${issue.severity}`}
                    >
                      <span className="issue-icon">
                        {issue.severity === "error" ? "❌" : "⚠️"}
                      </span>
                      <span className="issue-message">{issue.message}</span>
                      {issue.suggested_action && (
                        <span className="issue-action">
                          {issue.suggested_action}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}

              <div className="field-meta">
                Page {field.page} • {field.bbox.x.toFixed(0)}, {field.bbox.y.toFixed(0)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
