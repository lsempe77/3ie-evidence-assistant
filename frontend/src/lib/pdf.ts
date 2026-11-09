import { authHeaders } from "@/lib/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** True for PDFs served by our API (access-checked), false for direct storage links. */
export function isApiUrl(url: string): boolean {
  return url.startsWith(API_BASE_URL);
}

/**
 * Fetch a PDF from the API with the user's sign-in token and return a local blob URL.
 *
 * The PDF endpoints check access like every other project endpoint. An <iframe> or a
 * plain link cannot send the Authorization header, so private collections answered
 * "This RAG is private" even to their owner. Fetching here and showing the blob fixes
 * that. Revoke the URL with URL.revokeObjectURL when it is no longer shown.
 */
export async function fetchPdfBlobUrl(url: string): Promise<string> {
  const response = await fetch(url, { headers: await authHeaders() });
  if (!response.ok) {
    throw new Error(
      response.status === 401 || response.status === 403
        ? "You do not have access to this document."
        : response.status === 404
          ? "This document is not available."
          : "The document could not be loaded. Try again."
    );
  }
  const blob = await response.blob();
  return URL.createObjectURL(blob.type ? blob : new Blob([blob], { type: "application/pdf" }));
}

/**
 * Open a PDF in a new tab. The tab is opened at once (inside the click), so pop-up
 * blockers allow it, and pointed at the blob when the download finishes.
 */
export async function openPdfInNewTab(url: string, page?: number): Promise<void> {
  if (!isApiUrl(url)) {
    window.open(page && page > 1 ? `${url}#page=${page}` : url, "_blank", "noopener,noreferrer");
    return;
  }
  const tab = window.open("", "_blank");
  try {
    const blobUrl = await fetchPdfBlobUrl(url);
    const target = page && page > 1 ? `${blobUrl}#page=${page}` : blobUrl;
    if (tab) tab.location.href = target;
    else window.location.href = target;
  } catch (e) {
    const message = e instanceof Error ? e.message : "The document could not be opened.";
    if (tab) {
      tab.document.title = "Document not available";
      tab.document.body.textContent = message;
    }
  }
}
