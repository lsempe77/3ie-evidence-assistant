"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import type { PDFDocumentProxy } from "pdfjs-dist";
import "react-pdf/dist/Page/TextLayer.css";
import "react-pdf/dist/Page/AnnotationLayer.css";
import {
  AlertCircle,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Loader2,
  Maximize2,
  RotateCcw,
  Search,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  applyHighlights,
  buildTextLayerIndex,
  clearHighlights,
  findMatches,
  findQuoteMatch,
  normalizeForSearch,
  type HighlightSpec,
  type TextLayerIndex,
} from "./pdfTextLayer";

// Bundled worker: the version must match the pdfjs-dist build the worker is loaded
// from, so it is resolved from the same package rather than a CDN.
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url
).toString();

const MIN_SCALE = 0.3;
const MAX_SCALE = 4;
const ZOOM_STEP = 1.25;
const VIEW_PADDING = 24;

const CITE_CLASS = "pointer-events-none rounded-[3px] bg-highlight/60 text-transparent";
const SEARCH_CLASS = "pointer-events-none rounded-[3px] bg-warning/25 text-transparent";
const SEARCH_ACTIVE_CLASS = "pointer-events-none rounded-[3px] bg-warning/60 text-transparent";

function clampScale(value: number): number {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, value));
}

export interface PdfDocumentViewProps {
  url: string;
  initialPage?: number;
  searchText?: string;
  hideToolbar?: boolean;
  onClose?: () => void;
  className?: string;
}

/**
 * Canvas PDF reader built on react-pdf.
 *
 * The cited passage is highlighted client-side: the text layer is flattened into a
 * separator-free string, the quote is matched in it, and the matching DOM range is
 * wrapped in <mark>. The server's yellow highlight annotation is not drawn
 * (`renderAnnotationLayer={false}`, see the wrapper) so the passage is marked once.
 */
export default function PdfDocumentView({
  url,
  initialPage = 1,
  searchText,
  hideToolbar = false,
  onClose,
  className,
}: PdfDocumentViewProps) {
  const [numPages, setNumPages] = useState(0);
  const [docError, setDocError] = useState<string | null>(null);
  const [docAttempt, setDocAttempt] = useState(0);
  const [scale, setScale] = useState(1);
  const [fitWidth, setFitWidth] = useState(true);
  const [pageSize, setPageSize] = useState<{ width: number; height: number } | null>(null);
  const [containerWidth, setContainerWidth] = useState(0);
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [pageInput, setPageInput] = useState(String(initialPage));
  const [citePage, setCitePage] = useState(initialPage);
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [matchCount, setMatchCount] = useState(0);
  const [activeMatch, setActiveMatch] = useState(-1);
  const [indexVersion, setIndexVersion] = useState(0);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const pagesRef = useRef<Map<number, HTMLDivElement>>(new Map());
  const matchesRef = useRef<Array<{ page: number; start: number }>>([]);
  const scrollFrameRef = useRef(0);
  const citeScrolledRef = useRef("");

  // Fit-to-width is derived during render from the container width and page geometry, so the
  // last user-chosen zoom is kept as a fallback for when fit-to-width is off.
  const fitScale =
    fitWidth && pageSize && containerWidth > VIEW_PADDING * 2
      ? clampScale((containerWidth - VIEW_PADDING * 2) / pageSize.width)
      : null;
  const renderScale = fitScale ?? scale;

  const scrollToPage = useCallback((page: number, smooth: boolean) => {
    const container = scrollRef.current;
    const element = pagesRef.current.get(page);
    if (!container || !element) return;
    container.scrollTo({ top: Math.max(0, element.offsetTop - 8), behavior: smooth ? "smooth" : "auto" });
  }, []);

  const setPageElement = useCallback((element: HTMLDivElement | null) => {
    if (!element) return;
    const page = Number(element.getAttribute("data-page-number"));
    if (Number.isFinite(page) && page > 0) pagesRef.current.set(page, element);
  }, []);

  const handleTextLayerRendered = useCallback(() => {
    setIndexVersion((version) => version + 1);
  }, []);

  const handleDocumentLoad = useCallback((document: PDFDocumentProxy) => {
    pagesRef.current.clear();
    setNumPages(document.numPages);
    setDocError(null);
    document
      .getPage(1)
      .then((page) => {
        const viewport = page.getViewport({ scale: 1 });
        setPageSize({ width: viewport.width, height: viewport.height });
      })
      .catch(() => setPageSize(null));
  }, []);

  useEffect(() => {
    const element = scrollRef.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) setContainerWidth(entry.contentRect.width);
    });
    observer.observe(element);
    setContainerWidth(element.clientWidth);
    return () => observer.disconnect();
  }, []);

  // Rebuild the text index, then paint the cited passage and the search matches.
  useEffect(() => {
    const needle = normalizeForSearch(submittedQuery);
    const quote = searchText ?? "";

    const layers = new Map<number, HTMLElement>();
    const indexes = new Map<number, TextLayerIndex>();
    for (const [page, element] of pagesRef.current) {
      const layer = element.querySelector<HTMLElement>(".react-pdf__Page__textContent");
      if (!layer) continue;
      clearHighlights(layer);
      layers.set(page, layer);
      indexes.set(page, buildTextLayerIndex(layer));
    }

    const pages = Array.from(indexes.keys()).sort((left, right) => left - right);

    const matches: Array<{ page: number; start: number }> = [];
    if (needle) {
      for (const page of pages) {
        const index = indexes.get(page);
        if (!index) continue;
        for (const start of findMatches(index, submittedQuery, true)) {
          matches.push({ page, start });
        }
      }
    }
    matchesRef.current = matches;
    // The match counter describes the DOM work done in this effect: the text index and the
    // painted highlights only exist after react-pdf has rendered the text layer, so the count
    // cannot be derived during render. The effect is the only place it can be read.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMatchCount(matches.length);

    let quoteMatch: { start: number; length: number } | null = null;
    let quotePage = initialPage;
    if (normalizeForSearch(quote).length >= 6) {
      const order = pages.includes(initialPage)
        ? [initialPage, ...pages.filter((page) => page !== initialPage)]
        : pages;
      for (const page of order) {
        const index = indexes.get(page);
        if (!index) continue;
        const found = findQuoteMatch(index, quote);
        if (found) {
          quoteMatch = found;
          quotePage = page;
          break;
        }
      }
    }
    setCitePage(quotePage);

    const searchByPage = new Map<number, Array<{ start: number; global: number }>>();
    matches.forEach((match, global) => {
      const list = searchByPage.get(match.page) ?? [];
      list.push({ start: match.start, global });
      searchByPage.set(match.page, list);
    });

    const active = matches.length === 0 ? -1 : activeMatch < 0 ? 0 : Math.min(activeMatch, matches.length - 1);

    for (const page of pages) {
      const index = indexes.get(page);
      const layer = layers.get(page);
      if (!index || !layer) continue;
      const specs: HighlightSpec[] = [];
      if (quoteMatch && page === quotePage) {
        specs.push({
          start: quoteMatch.start,
          end: quoteMatch.start + quoteMatch.length,
          className: CITE_CLASS,
          group: "cite",
        });
      }
      for (const item of searchByPage.get(page) ?? []) {
        specs.push({
          start: item.start,
          end: item.start + needle.length,
          className: item.global === active ? SEARCH_ACTIVE_CLASS : SEARCH_CLASS,
          group: "search",
          matchIndex: item.global,
          active: item.global === active,
        });
      }
      applyHighlights(layer, index, specs);
    }

    if (active !== activeMatch) setActiveMatch(active);
  }, [activeMatch, indexVersion, initialPage, numPages, searchText, submittedQuery]);

  useEffect(() => {
    const key = `${initialPage}|${searchText ?? ""}`;
    if (citeScrolledRef.current === key) return;
    if (!pagesRef.current.get(citePage)) return;
    citeScrolledRef.current = key;
    scrollToPage(citePage, false);
  }, [citePage, indexVersion, initialPage, scrollToPage, searchText]);

  useEffect(() => {
    if (activeMatch < 0) return;
    const mark = scrollRef.current?.querySelector(`mark[data-pdf-match="${activeMatch}"]`);
    mark?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [activeMatch]);

  useEffect(() => {
    return () => {
      if (scrollFrameRef.current) window.cancelAnimationFrame(scrollFrameRef.current);
    };
  }, []);

  const handleScroll = useCallback(() => {
    if (scrollFrameRef.current) return;
    scrollFrameRef.current = window.requestAnimationFrame(() => {
      scrollFrameRef.current = 0;
      const container = scrollRef.current;
      if (!container) return;
      const top = container.scrollTop;
      let best = 1;
      let bestDistance = Infinity;
      pagesRef.current.forEach((element, page) => {
        const distance = Math.abs(element.offsetTop - top - 8);
        if (distance < bestDistance) {
          bestDistance = distance;
          best = page;
        }
      });
      setCurrentPage(best);
    });
  }, []);

  const goToPage = useCallback(
    (page: number) => {
      const target = Math.min(Math.max(1, page), numPages || 1);
      setCurrentPage(target);
      setPageInput(String(target));
      scrollToPage(target, true);
    },
    [numPages, scrollToPage]
  );

  const zoomBy = useCallback(
    (factor: number) => {
      setFitWidth(false);
      setScale(clampScale((fitScale ?? scale) * factor));
    },
    [fitScale, scale]
  );

  const zoomIn = useCallback(() => zoomBy(ZOOM_STEP), [zoomBy]);

  const zoomOut = useCallback(() => zoomBy(1 / ZOOM_STEP), [zoomBy]);

  const resetZoom = useCallback(() => {
    setFitWidth(false);
    setScale(1);
  }, []);

  const submitSearch = useCallback(() => {
    setSubmittedQuery(query.trim());
    setActiveMatch(0);
  }, [query]);

  const stepMatch = useCallback((direction: 1 | -1) => {
    setActiveMatch((current) => {
      const count = matchesRef.current.length;
      if (count === 0) return -1;
      if (current < 0) return direction === 1 ? 0 : count - 1;
      return (current + direction + count) % count;
    });
  }, []);

  const retryDocument = useCallback(() => {
    setDocError(null);
    setDocAttempt((attempt) => attempt + 1);
  }, []);

  return (
    <div className={cn("relative flex h-full w-full flex-col overflow-hidden bg-surface-1 text-ink", className)}>
      <div
        className={cn(
          "flex flex-wrap items-center gap-x-2 gap-y-1 px-2 py-1.5",
          !hideToolbar && "border-b border-hairline bg-surface-1"
        )}
      >
        <div className="flex items-center gap-0.5">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => goToPage(currentPage - 1)}
            disabled={currentPage <= 1}
            aria-label="Previous page"
          >
            <ChevronLeft aria-hidden="true" />
          </Button>
          <Input
            aria-label="Page number"
            inputMode="numeric"
            value={pageInput}
            onChange={(event) => setPageInput(event.target.value.replace(/[^0-9]/g, ""))}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                goToPage(Number(pageInput) || currentPage);
              }
            }}
            onBlur={() => goToPage(Number(pageInput) || currentPage)}
            className="h-7 w-11 px-1 text-center text-caption"
          />
          <span className="text-caption tabular-nums text-ink-muted">/ {numPages || "–"}</span>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => goToPage(currentPage + 1)}
            disabled={numPages === 0 || currentPage >= numPages}
            aria-label="Next page"
          >
            <ChevronRight aria-hidden="true" />
          </Button>
        </div>

        <div className="flex items-center gap-0.5">
          <Button variant="ghost" size="icon-sm" onClick={zoomOut} aria-label="Zoom out">
            <ZoomOut aria-hidden="true" />
          </Button>
          <span className="w-10 text-center text-caption tabular-nums text-ink-muted">
            {Math.round(renderScale * 100)}%
          </span>
          <Button variant="ghost" size="icon-sm" onClick={zoomIn} aria-label="Zoom in">
            <ZoomIn aria-hidden="true" />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setFitWidth(true)}
            aria-label="Fit to width"
            aria-pressed={fitWidth}
          >
            <Maximize2 aria-hidden="true" />
          </Button>
          <Button variant="ghost" size="icon-sm" onClick={resetZoom} aria-label="Reset zoom">
            <RotateCcw aria-hidden="true" />
          </Button>
        </div>

        <div className="ml-auto flex items-center gap-0.5">
          <div className="relative">
            <Search
              className="pointer-events-none absolute top-1/2 left-2 size-3.5 -translate-y-1/2 text-ink-subtle"
              aria-hidden="true"
            />
            <Input
              type="search"
              aria-label="Search in document"
              placeholder="Search…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  submitSearch();
                }
              }}
              className="h-7 w-40 pr-2 pl-7 text-caption"
            />
          </div>
          <span className="w-16 text-center text-caption tabular-nums text-ink-muted" role="status" aria-live="polite">
            {submittedQuery ? (matchCount ? `${activeMatch + 1} of ${matchCount}` : "No matches") : ""}
          </span>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => stepMatch(-1)}
            disabled={matchCount === 0}
            aria-label="Previous match"
          >
            <ChevronUp aria-hidden="true" />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => stepMatch(1)}
            disabled={matchCount === 0}
            aria-label="Next match"
          >
            <ChevronDown aria-hidden="true" />
          </Button>
        </div>

        {onClose && !hideToolbar && (
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close document">
            <X aria-hidden="true" />
          </Button>
        )}
      </div>

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="relative min-h-0 flex-1 overflow-auto bg-surface-1"
      >
        <div className="flex min-h-full w-max min-w-full flex-col items-center p-6">
          <Document
            key={docAttempt}
            file={url}
            suspense={false}
            onLoadSuccess={handleDocumentLoad}
            onLoadError={() => setDocError("This document could not be opened.")}
            className="flex flex-col items-center gap-4"
            loading={
              <div className="flex items-center justify-center py-16">
                <p className="flex items-center gap-2 text-body text-ink-muted" role="status">
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  Loading the document…
                </p>
              </div>
            }
          >
            {Array.from({ length: numPages }, (_, pageIndex) => {
              const pageNumber = pageIndex + 1;
              return (
                <Page
                  key={pageNumber}
                  pageNumber={pageNumber}
                  scale={renderScale}
                  renderAnnotationLayer={false}
                  onRenderTextLayerSuccess={handleTextLayerRendered}
                  inputRef={setPageElement}
                  loading={null}
                  className="overflow-hidden rounded-sm border border-hairline bg-canvas shadow-sm"
                />
              );
            })}
          </Document>
        </div>
      </div>

      {docError && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-surface-1 p-4">
          <div className="flex max-w-sm flex-col items-center gap-3 text-center" role="alert">
            <AlertCircle className="size-6 text-danger" aria-hidden="true" />
            <p className="text-body text-ink">{docError}</p>
            <Button variant="outline" size="sm" onClick={retryDocument}>
              <RotateCcw aria-hidden="true" />
              Try again
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
