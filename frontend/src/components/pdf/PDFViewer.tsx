"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Loader2, AlertCircle, RotateCcw } from "lucide-react";
import { fetchPdfBlobUrl, isApiUrl } from "@/lib/pdf";

interface PDFViewerProps {
  url: string;
  initialPage?: number;
  searchText?: string; // shown by the caller in the cited-passage card
  onClose?: () => void;
  className?: string;
  /** Hide the toolbar for embedded use */
  hideToolbar?: boolean;
}

/**
 * PDF viewer using the browser's native viewer in an iframe.
 *
 * The PDF is fetched with the user's sign-in token and shown from a blob URL, because
 * an iframe cannot send the Authorization header that private collections require.
 * The page is selected with the #page=N fragment.
 */
export function PDFViewer({ url, initialPage = 1, className = "" }: PDFViewerProps) {
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
  const src = blobUrl ? (initialPage > 1 ? `${blobUrl}#page=${initialPage}` : blobUrl) : null;

  return (
    <div className={`relative flex h-full w-full flex-col ${className}`}>
      <div className="relative flex-1">
        {!src && !error && (
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

        {src && (
          <iframe key={src} src={src} className="absolute inset-0 h-full w-full border-0" title="Document" />
        )}
      </div>
    </div>
  );
}

/** Same as PDFViewer, kept for older imports. */
export const SimplePDFViewer = PDFViewer;

export default PDFViewer;
