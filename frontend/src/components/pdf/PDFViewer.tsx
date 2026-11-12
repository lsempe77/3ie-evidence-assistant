"use client";

import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { Button } from "@/components/ui/button";
import { AlertCircle, FileText, Loader2, RotateCcw } from "lucide-react";
import { fetchPdfBlobUrl, isApiUrl } from "@/lib/pdf";

// react-pdf and pdf.js touch window and spawn a worker, so the reader is loaded
// only in the browser and only when a document is actually shown.
const PdfDocumentView = dynamic(() => import("./PdfDocumentView"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center bg-surface-1">
      <p className="flex items-center gap-2 text-body text-ink-muted" role="status">
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        Loading the document…
      </p>
    </div>
  ),
});

interface PDFViewerProps {
  url: string;
  initialPage?: number;
  searchText?: string; // shown by the caller in the cited-passage card
  onClose?: () => void;
  className?: string;
  /** Hide the viewer's own toolbar chrome for embedded use */
  hideToolbar?: boolean;
}

/**
 * Loads a PDF and shows it in the canvas reader.
 *
 * The PDF is fetched with the user's sign-in token and shown from a blob URL, because
 * private collections require the Authorization header that a plain link or iframe
 * cannot send. Direct storage links are used as-is.
 */
export function PDFViewer({
  url,
  initialPage = 1,
  searchText,
  hideToolbar = false,
  onClose,
  className = "",
}: PDFViewerProps) {
  const [attempt, setAttempt] = useState(0);
  // Result of the last download, tagged with the url and attempt it belongs to, so a
  // new url or a retry shows the loading state without resetting state in the effect.
  const [loaded, setLoaded] = useState<{ key: string; blob?: string; error?: string } | null>(null);
  const direct = !isApiUrl(url); // presigned storage links need no sign-in token
  const key = `${url}|${attempt}`;

  useEffect(() => {
    if (direct) return;
    let cancelled = false;
    let created: string | null = null;
    fetchPdfBlobUrl(url)
      .then((u) => {
        created = u;
        if (cancelled) URL.revokeObjectURL(u);
        else setLoaded({ key, blob: u });
      })
      .catch((e) => {
        if (!cancelled) setLoaded({ key, error: e instanceof Error ? e.message : "The document could not be loaded." });
      });
    return () => {
      cancelled = true;
      if (created) URL.revokeObjectURL(created);
    };
  }, [url, key, direct]);

  const current = loaded?.key === key ? loaded : null;
  const blobUrl = direct ? url : current?.blob ?? null;
  const error = direct ? null : current?.error ?? null;

  return (
    <div className={`relative flex h-full w-full flex-col ${className}`}>
      <div className="relative flex-1 overflow-hidden">
        {!url && (
          <div className="absolute inset-0 flex items-center justify-center bg-surface-1 p-4">
            <p className="flex items-center gap-2 text-body text-ink-muted">
              <FileText className="size-4" aria-hidden="true" />
              No document selected.
            </p>
          </div>
        )}

        {url && !blobUrl && !error && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-surface-1">
            <p className="flex items-center gap-2 text-body text-ink-muted" role="status">
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              Loading the document…
            </p>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-surface-1 p-4">
            <div className="flex max-w-sm flex-col items-center gap-3 text-center" role="alert">
              <AlertCircle className="size-6 text-danger" aria-hidden="true" />
              <p className="text-body text-ink">{error}</p>
              <Button variant="outline" size="sm" onClick={() => setAttempt((a) => a + 1)}>
                <RotateCcw aria-hidden="true" />
                Try again
              </Button>
            </div>
          </div>
        )}

        {blobUrl && (
          <PdfDocumentView
            key={`${blobUrl}|${initialPage}|${searchText ?? ""}`}
            url={blobUrl}
            initialPage={initialPage}
            searchText={searchText}
            hideToolbar={hideToolbar}
            onClose={onClose}
          />
        )}
      </div>
    </div>
  );
}

/** Same as PDFViewer, kept for older imports. */
export const SimplePDFViewer = PDFViewer;

export default PDFViewer;
