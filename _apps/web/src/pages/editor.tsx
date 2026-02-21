import { useMemo, useRef, useState } from "react";

import PlacementLayer from "../components/PlacementLayer";
import PdfViewer, { type PdfViewport } from "../components/PdfViewer";
import {
  analyzeTemplateFromFile,
  analyzeTemplateFromUrl,
} from "../api/client";
import {
  TemplateSchemaSchema,
  defaultTemplateSchema,
  type FieldDefinition,
  type TemplateSchema,
} from "../lib/schema";

const SAMPLE_SCHEMA = defaultTemplateSchema;

export default function EditorPage() {
  const [schema, setSchema] = useState<TemplateSchema>(SAMPLE_SCHEMA);
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(
    schema.fields[0]?.id ?? null,
  );
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfViewport, setPdfViewport] = useState<PdfViewport | null>(null);
  const [pdfUrlInput, setPdfUrlInput] = useState("");
  const objectUrlRef = useRef<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  const selectedField = useMemo(
    () => schema.fields.find((field) => field.id === selectedFieldId) ?? null,
    [schema.fields, selectedFieldId],
  );

  const updateField = (
    fieldId: string,
    patch: Partial<FieldDefinition>,
  ) => {
    setSchema((current) => ({
      ...current,
      fields: current.fields.map((field) =>
        field.id === fieldId ? { ...field, ...patch } : field,
      ),
    }));
  };

  const updatePlacement = (
    fieldId: string,
    placementPatch: Partial<FieldDefinition["placement"]>,
  ) => {
    setSchema((current) => ({
      ...current,
      fields: current.fields.map((field) =>
        field.id === fieldId
          ? {
              ...field,
              placement: { ...field.placement, ...placementPatch },
            }
          : field,
      ),
    }));
  };

  const applySchema = (nextSchema: TemplateSchema) => {
    setSchema(nextSchema);
    setSelectedFieldId(nextSchema.fields[0]?.id ?? null);
  };

  const handleAnalyzeResult = (nextSchema: TemplateSchema) => {
    const validation = TemplateSchemaSchema.safeParse(nextSchema);
    if (!validation.success) {
      console.error("Analyze response validation failed", validation.error);
      const issue = validation.error.issues[0];
      const detail = issue
        ? `${issue.path.join(".") || "schema"}: ${issue.message}`
        : "invalid schema";
      throw new Error(`Analyze response did not match the expected schema: ${detail}`);
    }
    applySchema(validation.data);
  };

  const handleFileChange = async (file: File | null) => {
    if (!file) {
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
      setPdfUrl(null);
      return;
    }
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
    }
    const url = URL.createObjectURL(file);
    objectUrlRef.current = url;
    setPdfUrl(url);

    setAnalyzeError(null);
    setIsAnalyzing(true);
    try {
      const nextSchema = await analyzeTemplateFromFile(file);
      handleAnalyzeResult(nextSchema);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to analyze template.";
      setAnalyzeError(message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleViewportReady = useMemo(
    () => (viewport: PdfViewport | null) => {
      setPdfViewport(viewport);
    },
    [],
  );

  const exportSchema = () => {
    const result = TemplateSchemaSchema.safeParse(schema);
    if (!result.success) {
      alert("Schema is invalid. Fix errors before exporting.");
      console.error(result.error);
      return;
    }
    const json = JSON.stringify(result.data, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${schema.name || "template"}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <main
      style={{
        fontFamily: "system-ui, sans-serif",
        display: "flex",
        minHeight: "100vh",
        background: "#f8fafc",
        color: "#0f172a",
      }}
    >
      <section
        style={{
          width: 320,
          padding: "1.5rem",
          borderRight: "1px solid #e2e8f0",
          background: "#ffffff",
        }}
      >
        <h1 style={{ marginTop: 0 }}>Template Editor</h1>
        <div style={{ marginBottom: "1rem" }}>
          <label style={{ fontWeight: 600, display: "block", marginBottom: 4 }}>
            Load PDF
          </label>
          <input
            type="file"
            accept="application/pdf"
            onChange={(event) => handleFileChange(event.target.files?.[0] ?? null)}
          />
          <div style={{ marginTop: "0.75rem" }}>
            <input
              type="text"
              placeholder="https://example.com/template.pdf"
              value={pdfUrlInput}
              onChange={(event) => setPdfUrlInput(event.target.value)}
              style={{ width: "100%", padding: "0.4rem" }}
            />
            <button
              style={{ marginTop: "0.5rem" }}
              onClick={() => {
                if (objectUrlRef.current) {
                  URL.revokeObjectURL(objectUrlRef.current);
                  objectUrlRef.current = null;
                }
                const nextUrl = pdfUrlInput || null;
                setPdfUrl(nextUrl);
                if (!nextUrl) {
                  return;
                }
                setAnalyzeError(null);
                setIsAnalyzing(true);
                analyzeTemplateFromUrl(nextUrl)
                  .then((nextSchema) => handleAnalyzeResult(nextSchema))
                  .catch((error) => {
                    const message =
                      error instanceof Error
                        ? error.message
                        : "Failed to analyze template.";
                    setAnalyzeError(message);
                  })
                  .finally(() => setIsAnalyzing(false));
              }}
            >
              Load from URL
            </button>
          </div>
        </div>

        <div style={{ marginBottom: "1rem" }}>
          <label style={{ fontWeight: 600, display: "block", marginBottom: 4 }}>
            Fields
          </label>
          {isAnalyzing && (
            <div style={{ fontSize: 12, color: "#475569", marginBottom: 6 }}>
              Analyzing template...
            </div>
          )}
          {analyzeError && (
            <div style={{ fontSize: 12, color: "#b91c1c", marginBottom: 6 }}>
              {analyzeError}
            </div>
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {schema.fields.map((field) => (
              <button
                key={field.id}
                onClick={() => setSelectedFieldId(field.id)}
                style={{
                  textAlign: "left",
                  padding: "0.4rem 0.6rem",
                  borderRadius: 6,
                  border:
                    field.id === selectedFieldId
                      ? "2px solid #2563eb"
                      : "1px solid #cbd5e1",
                  background:
                    field.id === selectedFieldId ? "#eff6ff" : "#f8fafc",
                  color:
                    field.id === selectedFieldId ? "#1d4ed8" : "#0f172a",
                }}
              >
                {field.label}
              </button>
            ))}
          </div>
        </div>

        {selectedField && (
          <div style={{ marginBottom: "1rem" }}>
            <label style={{ fontWeight: 600, display: "block", marginBottom: 4 }}>
              Placement (pt)
            </label>
            <div style={{ display: "grid", gap: 6 }}>
              <label>
                X
                <input
                  type="number"
                  value={selectedField.placement.x}
                  onChange={(event) =>
                    updatePlacement(selectedField.id, {
                      x: Number(event.target.value),
                    })
                  }
                  style={{ width: "100%", padding: "0.3rem" }}
                />
              </label>
              <label>
                Y
                <input
                  type="number"
                  value={selectedField.placement.y}
                  onChange={(event) =>
                    updatePlacement(selectedField.id, {
                      y: Number(event.target.value),
                    })
                  }
                  style={{ width: "100%", padding: "0.3rem" }}
                />
              </label>
              <label>
                Max width
                <input
                  type="number"
                  value={selectedField.placement.max_width}
                  onChange={(event) =>
                    updatePlacement(selectedField.id, {
                      max_width: Number(event.target.value),
                    })
                  }
                  style={{ width: "100%", padding: "0.3rem" }}
                />
              </label>
            </div>
            <label style={{ fontWeight: 600, display: "block", margin: "0.8rem 0 0.4rem" }}>
              Font policy
            </label>
            <div style={{ display: "grid", gap: 6 }}>
              <label>
                Size
                <input
                  type="number"
                  value={selectedField.placement.font_policy.size}
                  onChange={(event) =>
                    updatePlacement(selectedField.id, {
                      font_policy: {
                        ...selectedField.placement.font_policy,
                        size: Number(event.target.value),
                      },
                    })
                  }
                  style={{ width: "100%", padding: "0.3rem" }}
                />
              </label>
              <label>
                Min size
                <input
                  type="number"
                  value={selectedField.placement.font_policy.min_size}
                  onChange={(event) =>
                    updatePlacement(selectedField.id, {
                      font_policy: {
                        ...selectedField.placement.font_policy,
                        min_size: Number(event.target.value),
                      },
                    })
                  }
                  style={{ width: "100%", padding: "0.3rem" }}
                />
              </label>
            </div>
          </div>
        )}

        <button onClick={exportSchema}>Export schema JSON</button>
      </section>

      <section style={{ flex: 1, padding: "2rem", overflow: "auto" }}>
        <div style={{ position: "relative", display: "inline-block" }}>
          <PdfViewer
            pdfUrl={pdfUrl}
            onViewportReady={handleViewportReady}
          />
          {pdfViewport && (
            <div style={{ position: "absolute", inset: 0 }}>
              <PlacementLayer
                fields={schema.fields}
                viewport={pdfViewport}
                selectedFieldId={selectedFieldId}
                onSelect={(fieldId) => setSelectedFieldId(fieldId)}
                onUpdatePlacement={updatePlacement}
              />
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
