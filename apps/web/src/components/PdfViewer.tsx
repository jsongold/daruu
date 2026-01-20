import { useEffect, useRef, useState } from "react";
import { GlobalWorkerOptions, getDocument } from "pdfjs-dist";

GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

export type PdfViewport = {
  width: number;
  height: number;
  scale: number;
  pageWidth: number;
  pageHeight: number;
};

type PdfViewerProps = {
  pdfUrl: string | null;
  targetWidth?: number;
  onViewportReady?: (viewport: PdfViewport | null) => void;
};

export default function PdfViewer({
  pdfUrl,
  targetWidth = 800,
  onViewportReady,
}: PdfViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [status, setStatus] = useState<string>("No PDF loaded");

  useEffect(() => {
    let cancelled = false;

    async function render() {
      if (!pdfUrl || !canvasRef.current) {
        onViewportReady?.(null);
        setStatus("No PDF loaded");
        return;
      }

      setStatus("Loading PDF...");
      const loadingTask = getDocument(pdfUrl);
      const pdf = await loadingTask.promise;
      const page = await pdf.getPage(1);

      const unscaledViewport = page.getViewport({ scale: 1 });
      const scale = targetWidth / unscaledViewport.width;
      const viewport = page.getViewport({ scale });

      if (cancelled || !canvasRef.current) {
        return;
      }

      const canvas = canvasRef.current;
      const context = canvas.getContext("2d");
      if (!context) {
        throw new Error("Canvas 2D context is not available");
      }

      canvas.width = viewport.width;
      canvas.height = viewport.height;

      await page.render({ canvasContext: context, viewport }).promise;
      if (!cancelled) {
        onViewportReady?.({
          width: viewport.width,
          height: viewport.height,
          scale,
          pageWidth: unscaledViewport.width,
          pageHeight: unscaledViewport.height,
        });
        setStatus("PDF loaded");
      }
    }

    render().catch((error) => {
      if (!cancelled) {
        console.error(error);
        setStatus("Failed to load PDF");
        onViewportReady?.(null);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [pdfUrl, targetWidth, onViewportReady]);

  return (
    <div style={{ position: "relative" }}>
      <canvas ref={canvasRef} />
      {!pdfUrl && (
        <div style={{ padding: "1rem", color: "#666" }}>{status}</div>
      )}
    </div>
  );
}
