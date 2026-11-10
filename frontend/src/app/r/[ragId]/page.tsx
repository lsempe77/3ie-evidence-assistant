"use client";

/**
 * Ask screen (DESIGN.md, Overview and Responsive behaviour).
 *
 * Wide screens: history (256px) | answer column (max 760px) | sources panel.
 * Below 1280px the sources panel becomes a "Sources" tab beside "Answer".
 * Below 1024px the history becomes a drawer opened from the top bar.
 */

import { useState, useCallback, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  defaultSettings,
  EvidencePanel,
  AnswerPanel,
  SearchInput,
  CompareModal,
  ChatHistory,
} from "@/components/workbench";
import type { ChatHistoryItem, SearchSettings } from "@/components/workbench";
import { AppTopBar } from "@/components/layout/AppTopBar";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import {
  ExternalLink,
  Copy,
  Check,
  Loader2,
  PanelLeftClose,
  PanelLeft,
  History,
  ArrowLeft,
  RotateCcw,
} from "lucide-react";
import { Study, Citation, EvidenceHealth, AnswerStyle } from "@/types";
import { PDFViewer } from "@/components/pdf";
import {
  getChatHistory,
  addChatHistory,
  deleteChatHistoryItem,
  authHeaders,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { postEventStream, StreamUnavailableError } from "@/lib/stream";
import { AnswerProgress, emptyProgress } from "@/components/workbench/AnswerProgress";
import type { AnswerProgressState, ProgressStage } from "@/components/workbench/AnswerProgress";
import { openPdfInNewTab } from "@/lib/pdf";

const defaultEvidenceHealth: EvidenceHealth = {
  studyCount: 0,
  dateRange: "",
  gaps: [],
  coverageWarning: undefined,
};

// Shown on an empty Ask screen. Phrased to work for any collection of evaluations.
const EXAMPLE_QUESTIONS = [
  "What are the main effects on household income and consumption?",
  "Which studies are randomised controlled trials, and what did they find?",
  "Do the effects last after the programme ends?",
  "Where is the evidence weakest or missing?",
];

interface QueryResult {
  answer?: string;
  citations?: Citation[];
  studies?: Study[];
  suggestions?: string[];
  evidenceHealth?: EvidenceHealth;
  studiesRead?: number;
}

interface RAGProject {
  id: string;
  name: string;
  description: string | null;
  is_public: boolean;
}

type LoadError = "not_found" | "sign_in" | "private" | "failed" | "offline";

const LOAD_ERRORS: Record<LoadError, { title: string; body: string }> = {
  not_found: {
    title: "Collection not found",
    body: "The link may be wrong, or the collection was deleted.",
  },
  sign_in: {
    title: "Sign in to open this collection",
    body: "This collection is private. Sign in with the account that has access.",
  },
  private: {
    title: "This collection is private",
    body: "Your account does not have access. Ask the owner to share it or make it public.",
  },
  failed: {
    title: "The collection could not be loaded",
    body: "Something went wrong on our side. Try again in a minute.",
  },
  offline: {
    title: "Cannot reach the server",
    body: "Check your connection and try again.",
  },
};

/** The cited passage above the PDF, so it can be found with Ctrl+F or Cmd+F. */
function PassageCard({ snippet, page }: { snippet: string; page: number }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  return (
    <div className="border-b border-hairline bg-surface-1 p-3">
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <p className="tabular text-caption font-medium text-ink-muted">Cited passage, page {page}</p>
        <Button variant="ghost" size="sm" onClick={handleCopy}>
          {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
          <span aria-live="polite">{copied ? "Copied" : "Copy"}</span>
        </Button>
      </div>
      <blockquote className="line-clamp-4 border-l-4 border-highlight bg-canvas px-3 py-2 text-body text-ink">
        “{snippet}”
      </blockquote>
    </div>
  );
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function RAGChatPage() {
  const params = useParams();
  const ragId = params.ragId as string;

  const [project, setProject] = useState<RAGProject | null>(null);
  const [projectLoading, setProjectLoading] = useState(true);
  const [projectError, setProjectError] = useState<LoadError | null>(null);

  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [studies, setStudies] = useState<Study[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [answer, setAnswer] = useState("");
  const [evidenceHealth, setEvidenceHealth] = useState<EvidenceHealth>(defaultEvidenceHealth);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [studiesRead, setStudiesRead] = useState<number | undefined>();
  const [progress, setProgress] = useState<AnswerProgressState | null>(null);
  const [arrivingStudies, setArrivingStudies] = useState<Study[]>([]);

  const [selectedStudies, setSelectedStudies] = useState<Study[]>([]);
  const [highlightedCitation, setHighlightedCitation] = useState<number | undefined>();
  const [searchSettings] = useState<SearchSettings>(defaultSettings);
  const [isCompareModalOpen, setIsCompareModalOpen] = useState(false);

  const [chatHistory, setChatHistory] = useState<ChatHistoryItem[]>([]);
  const [currentQueryId, setCurrentQueryId] = useState<string | undefined>();
  const [isSidebarOpen, setIsSidebarOpen] = useState(true); // 1024px and up
  const [isHistoryDrawerOpen, setIsHistoryDrawerOpen] = useState(false); // below 1024px
  const [narrowTab, setNarrowTab] = useState<"answer" | "sources">("answer"); // below 1280px

  const [pdfViewerOpen, setPdfViewerOpen] = useState(false);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfPage, setPdfPage] = useState(1);
  const [pdfTitle, setPdfTitle] = useState("");
  const [pdfSearchText, setPdfSearchText] = useState<string | undefined>();
  const [pdfStudyId, setPdfStudyId] = useState<string | null>(null);

  const getSessionId = useCallback((): string => {
    if (typeof window === "undefined") return "";
    try {
      let sessionId = localStorage.getItem("chat_session_id");
      if (!sessionId) {
        sessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;
        localStorage.setItem("chat_session_id", sessionId);
      }
      return sessionId;
    } catch {
      return "";
    }
  }, []);

  const loadChatHistory = useCallback(
    async (projectId: string) => {
      try {
        const history = await getChatHistory(projectId, getSessionId());
        setChatHistory(
          history.map((item) => ({
            id: item.id,
            query: item.query,
            timestamp: new Date(item.timestamp),
            studyCount: item.studyCount,
            answer: item.answer,
            citationsUsed: item.citationsUsed,
            responseData: item.responseData,
          }))
        );
      } catch (err) {
        console.error("Failed to load chat history:", err);
      }
    },
    [getSessionId]
  );

  useEffect(() => {
    const fetchProject = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/rags/${ragId}/public`, {
          headers: await authHeaders(),
        });
        if (!response.ok) {
          setProjectError(
            response.status === 404
              ? "not_found"
              : response.status === 401
                ? "sign_in"
                : response.status === 403
                  ? "private"
                  : "failed"
          );
          return;
        }
        const data = await response.json();
        setProject(data);
        loadChatHistory(ragId);
      } catch {
        setProjectError("offline");
      } finally {
        setProjectLoading(false);
      }
    };
    fetchProject();
  }, [ragId, loadChatHistory]);

  const handleSearch = useCallback(
    async (searchQuery: string) => {
      if (!project) return;

      setQuery(searchQuery);
      setIsLoading(true);
      setHasSearched(true);
      setError(null);
      setNarrowTab("answer");
      setPdfViewerOpen(false);
      window.scrollTo({ top: 0 });

      const requestBody = {
        query: searchQuery,
        collection: project.id,
        project_id: project.id,
        settings: searchSettings,
      };

      // The full answer, from the stream's "done" event or from /api/query
      const applyResponse = async (data: QueryResult) => {
        const responseData = {
          citations: data.citations || [],
          studies: data.studies || [],
          suggestions: data.suggestions || [],
          evidenceHealth: data.evidenceHealth || defaultEvidenceHealth,
        };
        setStudies(responseData.studies);
        setCitations(responseData.citations);
        setAnswer(data.answer || "");
        setSuggestions(responseData.suggestions);
        setEvidenceHealth(responseData.evidenceHealth);
        setStudiesRead(typeof data.studiesRead === "number" ? data.studiesRead : undefined);
        setArrivingStudies([]);
        setProgress(null);

        const savedItem = await addChatHistory(
          project.id,
          searchQuery,
          responseData.studies.length,
          getSessionId(),
          data.answer || "",
          responseData.citations.length,
          // The cache keeps the frontend's shapes; its declared type predates them
          responseData as unknown as Parameters<typeof addChatHistory>[6]
        );
        if (savedItem) {
          setChatHistory((prev) => [
            {
              id: savedItem.id,
              query: savedItem.query,
              timestamp: new Date(savedItem.timestamp),
              studyCount: savedItem.studyCount,
              answer: savedItem.answer,
              responseData: savedItem.responseData,
            },
            ...prev.filter((h) => h.query !== searchQuery),
          ]);
          setCurrentQueryId(savedItem.id);
        }
      };

      setProgress(emptyProgress);
      setArrivingStudies([]);
      setAnswer("");

      try {
        let finished = false;
        try {
          // Live progress (roadmap N2): steps, a tally of findings and studies as they are read
          await postEventStream(`${API_BASE_URL}/api/query/stream`, requestBody, await authHeaders(), (event, raw) => {
            const data = raw as Record<string, unknown>;
            if (event === "stage") {
              setProgress((p) => ({
                ...(p ?? emptyProgress),
                stage: data.stage as ProgressStage,
                documents: (data.documents as number | null | undefined) ?? p?.documents,
              }));
            } else if (event === "candidates") {
              setProgress((p) => ({ ...(p ?? emptyProgress), total: data.total as number }));
            } else if (event === "study") {
              setProgress((p) => {
                const base = p ?? emptyProgress;
                const direction = data.direction as string | null;
                const design = data.design as string | null;
                return {
                  ...base,
                  done: data.done as number,
                  total: data.total as number,
                  relevant: base.relevant + (data.relevant ? 1 : 0),
                  directions: direction ? { ...base.directions, [direction]: (base.directions[direction] || 0) + 1 } : base.directions,
                  designs: design ? { ...base.designs, [design]: (base.designs[design] || 0) + 1 } : base.designs,
                };
              });
              if (data.study) setArrivingStudies((prev) => [...prev, data.study as Study]);
            } else if (event === "delta") {
              setAnswer((prev) => prev + (data.text as string));
            } else if (event === "done") {
              finished = true;
              void applyResponse(data as unknown as QueryResult);
            } else if (event === "error") {
              throw new Error((data.message as string) || "The answer could not be written. Try again.");
            }
          });
        } catch (streamErr) {
          // Older API without the stream endpoint: ask the plain endpoint instead
          if (!(streamErr instanceof StreamUnavailableError) || streamErr.status === 401 || streamErr.status === 403) {
            throw streamErr;
          }
        }
        if (finished) return;

        const response = await fetch(`${API_BASE_URL}/api/query`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...(await authHeaders()) },
          body: JSON.stringify(requestBody),
        });
        if (!response.ok) {
          throw new Error(
            response.status === 429
              ? "Too many questions in a short time. Wait a minute, then try again."
              : "The answer could not be written. Try again, and if it keeps failing, try a shorter question."
          );
        }
        await applyResponse(await response.json());
      } catch (err) {
        console.error("Search failed:", err);
        setProgress(null);
        setArrivingStudies([]);
        setError(
          err instanceof TypeError
            ? "Cannot reach the server. Check your connection and try again."
            : err instanceof StreamUnavailableError
              ? "The answer could not be written. Try again."
              : err instanceof Error
                ? err.message
                : "The answer could not be written. Try again."
        );
      } finally {
        setIsLoading(false);
      }
    },
    [project, searchSettings, getSessionId]
  );

  const openPdf = useCallback(
    (studyId: string, title: string, page: number, passage?: string) => {
      const text = encodeURIComponent(passage?.slice(0, 200) || "");
      setPdfUrl(`${API_BASE_URL}/rags/${ragId}/documents/${studyId}/pdf-highlighted?page=${page}&text=${text}`);
      setPdfPage(page);
      setPdfTitle(title);
      setPdfStudyId(studyId);
      setPdfSearchText(passage?.slice(0, 200));
      setPdfViewerOpen(true);
    },
    [ragId]
  );

  const handleCitationClick = useCallback(
    (citationId: number) => {
      const citation = citations.find((c) => c.id === citationId);
      if (!citation) return;

      setHighlightedCitation(citationId);
      setNarrowTab("sources");
      setTimeout(() => setHighlightedCitation(undefined), 3000);

      const page = citation.page || 1;
      const passage = citation.highlightText || citation.text;

      // Same document already open: move to the page without reloading the PDF.
      if (pdfViewerOpen && pdfStudyId === citation.studyId) {
        setPdfPage(page);
        setPdfSearchText(passage?.slice(0, 200));
        return;
      }
      openPdf(citation.studyId, citation.study?.title || citation.studyId, page, passage);
    },
    [citations, pdfViewerOpen, pdfStudyId, openPdf]
  );

  const closePdfViewer = useCallback(() => {
    setPdfViewerOpen(false);
    setPdfUrl(null);
    setPdfStudyId(null);
  }, []);

  const handleSelectStudy = useCallback((study: Study) => {
    setSelectedStudies((prev) =>
      prev.some((s) => s.id === study.id) ? prev.filter((s) => s.id !== study.id) : [...prev, study]
    );
  }, []);

  const handleReset = useCallback(() => {
    setHasSearched(false);
    setQuery("");
    setStudies([]);
    setCitations([]);
    setAnswer("");
    setSuggestions([]);
    setSelectedStudies([]);
    setError(null);
    setCurrentQueryId(undefined);
    setPdfViewerOpen(false);
    setNarrowTab("answer");
    setStudiesRead(undefined);
  }, []);

  const handleSelectHistoryItem = useCallback(
    (item: ChatHistoryItem) => {
      setIsHistoryDrawerOpen(false);
      // A cached response with citations restores instantly, with no new request.
      if (item.responseData?.citations && item.responseData.citations.length > 0) {
        setQuery(item.query);
        setAnswer(item.answer || "");
        setCitations((item.responseData.citations || []) as Citation[]);
        setStudies((item.responseData.studies || []) as Study[]);
        setSuggestions(item.responseData.suggestions || []);
        setEvidenceHealth(
          (item.responseData.evidenceHealth as unknown as EvidenceHealth) || defaultEvidenceHealth
        );
        setHasSearched(true);
        setStudiesRead(undefined);
        setCurrentQueryId(item.id);
        setError(null);
        setPdfViewerOpen(false);
        setNarrowTab("answer");
      } else {
        handleSearch(item.query);
      }
    },
    [handleSearch]
  );

  const handleDeleteHistoryItem = useCallback(
    async (id: string) => {
      if (!project) return;
      await deleteChatHistoryItem(project.id, id, getSessionId());
      setChatHistory((prev) => prev.filter((h) => h.id !== id));
      if (currentQueryId === id) setCurrentQueryId(undefined);
    },
    [currentQueryId, project, getSessionId]
  );

  const handleNewChat = useCallback(() => {
    setIsHistoryDrawerOpen(false);
    handleReset();
  }, [handleReset]);

  // ------------------------------------------------------------------ states

  if (projectLoading) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-canvas">
        <p className="flex items-center gap-2 text-body text-ink-muted" role="status">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          Loading collection…
        </p>
      </div>
    );
  }

  if (projectError || !project) {
    const e = LOAD_ERRORS[projectError || "not_found"];
    return (
      <div className="flex min-h-dvh flex-col bg-canvas">
        <AppTopBar />
        <main className="flex flex-1 items-center justify-center px-4">
          <div className="max-w-md text-center">
            <h1 className="text-title text-ink">{e.title}</h1>
            <p className="mt-2 text-body text-ink-muted">{e.body}</p>
            <div className="mt-6 flex flex-col justify-center gap-2 sm:flex-row">
              {projectError === "sign_in" ? (
                <Button asChild>
                  <Link href="/auth">Sign in</Link>
                </Button>
              ) : projectError === "failed" || projectError === "offline" ? (
                <Button onClick={() => window.location.reload()}>
                  <RotateCcw aria-hidden="true" />
                  Try again
                </Button>
              ) : null}
              <Button variant="outline" asChild>
                <Link href="/dashboard">All collections</Link>
              </Button>
            </div>
          </div>
        </main>
      </div>
    );
  }

  const historyPanel = (
    <ChatHistory
      history={chatHistory}
      currentQueryId={currentQueryId}
      onSelectQuery={handleSelectHistoryItem}
      onDeleteQuery={handleDeleteHistoryItem}
      onNewChat={handleNewChat}
    />
  );

  const sourcesPanel =
    pdfViewerOpen && pdfUrl ? (
      <div className="flex h-[calc(100dvh-8rem)] flex-col overflow-hidden rounded-md border border-hairline xl:h-[calc(100dvh-6rem)]">
        <div className="flex items-center gap-2 border-b border-hairline bg-canvas p-2">
          <Button variant="ghost" size="sm" onClick={closePdfViewer}>
            <ArrowLeft aria-hidden="true" />
            All sources
          </Button>
          <h2 className="min-w-0 flex-1 truncate font-sans text-body font-medium text-ink" title={pdfTitle}>
            {pdfTitle}
          </h2>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => openPdfInNewTab(pdfUrl, pdfPage)}
            aria-label="Open the document in a new tab"
          >
            <ExternalLink aria-hidden="true" />
          </Button>
        </div>
        {pdfSearchText && <PassageCard snippet={pdfSearchText} page={pdfPage} />}
        <div className="relative min-h-0 flex-1">
          <PDFViewer url={pdfUrl} initialPage={pdfPage} searchText={pdfSearchText} hideToolbar />
        </div>
      </div>
    ) : (
      <EvidencePanel
        studies={studies}
        citations={citations}
        highlightedCitation={highlightedCitation}
        selectedStudies={selectedStudies}
        onSelectStudy={handleSelectStudy}
        onExcludeStudy={(study) => setStudies((prev) => prev.filter((s) => s.id !== study.id))}
        onOpenPdf={(study) => openPdf(study.id, study.title || study.id, 1)}
        query={query}
        answer={answer}
        studiesRead={studiesRead}
      />
    );

  return (
    <div className="flex min-h-dvh flex-col bg-canvas">
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-primary px-3 py-2 text-primary-foreground focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        Skip to content
      </a>

      <AppTopBar
        collectionName={project.name}
        leading={
          <>
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              onClick={() => setIsHistoryDrawerOpen(true)}
              aria-label="Open history"
            >
              <History aria-hidden="true" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="hidden lg:inline-flex"
              onClick={() => setIsSidebarOpen((open) => !open)}
              aria-label={isSidebarOpen ? "Hide history" : "Show history"}
              aria-expanded={isSidebarOpen}
            >
              {isSidebarOpen ? <PanelLeftClose aria-hidden="true" /> : <PanelLeft aria-hidden="true" />}
            </Button>
          </>
        }
        // Answer settings are hidden while the default answer model is also the strongest
        // one benchmarked (Sonnet 5.5, 10 Nov 2026). Bring the "Deeper answer" switch back
        // with a stronger model behind it: <SettingsDrawer settings={searchSettings} onSettingsChange={setSearchSettings} />
        trailing={null}
      />

      <Sheet open={isHistoryDrawerOpen} onOpenChange={setIsHistoryDrawerOpen}>
        <SheetContent side="left" className="w-72 gap-0 overscroll-contain p-0 lg:hidden">
          <SheetTitle className="sr-only">History</SheetTitle>
          {historyPanel}
        </SheetContent>
      </Sheet>

      <div className="flex min-h-0 flex-1">
        {isSidebarOpen && (
          <aside className="sticky top-14 hidden h-[calc(100dvh-3.5rem)] w-64 shrink-0 border-r border-hairline lg:block">
            {historyPanel}
          </aside>
        )}

        <main id="main" className="min-w-0 flex-1">
          {!hasSearched ? (
            // Empty state: what this place is for, the ask box, example questions.
            <div className="mx-auto flex w-full max-w-[760px] flex-col px-4 py-12 md:px-6 md:py-20">
              <h1 className="text-title text-ink">Ask about {project.name}</h1>
              <p className="mt-2 text-body-lg text-ink-muted">
                {project.description ||
                  "Answers are written from the studies in this collection. Every claim links to the passage and page it comes from."}
              </p>
              <SearchInput
                className="mt-6"
                onSearch={handleSearch}
                isLoading={isLoading}
                value={query}
                placeholder={`Ask about ${project.name}…`}
              />
              <div className="mt-6">
                <p className="mb-2 text-caption font-medium text-ink-muted">Try one of these</p>
                <ul className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                  {EXAMPLE_QUESTIONS.map((q) => (
                    <li key={q}>
                      <Button
                        variant="outline"
                        className="h-auto min-h-9 w-full justify-start py-2 text-left whitespace-normal sm:w-auto"
                        onClick={() => handleSearch(q)}
                      >
                        {q}
                      </Button>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : (
            <div className="mx-auto w-full max-w-[1280px] px-4 md:px-6">
              {/* Below 1280px: Answer and Sources are tabs */}
              <div
                role="tablist"
                aria-label="Answer or sources"
                className="sticky top-14 z-30 -mx-4 flex border-b border-hairline bg-canvas px-4 md:-mx-6 md:px-6 xl:hidden"
              >
                {(["answer", "sources"] as const).map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    role="tab"
                    id={`tab-${tab}`}
                    aria-selected={narrowTab === tab}
                    aria-controls={`panel-${tab}`}
                    onClick={() => setNarrowTab(tab)}
                    className={cn(
                      "-mb-px border-b-2 px-3 py-3 text-body font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring pointer-coarse:min-h-11",
                      narrowTab === tab
                        ? "border-primary text-primary"
                        : "border-transparent text-ink-muted hover:text-ink"
                    )}
                  >
                    {tab === "answer" ? "Answer" : "Sources"}
                    {tab === "sources" && !isLoading && (
                      <span className="tabular ml-1.5 text-caption text-ink-subtle">{studies.length}</span>
                    )}
                  </button>
                ))}
              </div>

              <div
                className={cn(
                  "grid gap-8 py-6",
                  pdfViewerOpen
                    ? "xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]"
                    : "xl:grid-cols-[minmax(0,1fr)_400px]"
                )}
              >
                {/* Answer column */}
                <div
                  id="panel-answer"
                  role="tabpanel"
                  aria-labelledby="tab-answer"
                  className={cn("min-w-0 flex-col", narrowTab === "answer" ? "flex" : "hidden xl:flex")}
                >
                  <h1 className="mb-4 text-heading break-words text-ink">{query}</h1>

                  {error ? (
                    <div className="max-w-[760px] rounded-md border border-hairline bg-surface-1 p-4" role="alert">
                      <p className="font-medium text-ink">The answer could not be loaded</p>
                      <p className="mt-1 text-body text-ink-muted">{error}</p>
                      <Button variant="outline" size="sm" className="mt-3" onClick={() => handleSearch(query)}>
                        <RotateCcw aria-hidden="true" />
                        Try again
                      </Button>
                    </div>
                  ) : (
                    <>
                    {isLoading && progress && !answer ? (
                      <AnswerProgress progress={progress} />
                    ) : (
                    <AnswerPanel
                      answer={answer}
                      citations={citations}
                      evidenceHealth={evidenceHealth}
                      suggestions={suggestions}
                      answerStyle={"executive" as AnswerStyle}
                      isLoading={isLoading}
                      onCitationClick={handleCitationClick}
                      onSuggestionClick={handleSearch}
                      onShowSources={() => setNarrowTab("sources")}
                      streaming={isLoading && !!answer}
                    />
                    )}
                    </>
                  )}

                  {/* Follow-up ask box at the foot of the answer column */}
                  <div
                    className={cn(
                      "sticky z-20 mt-8 max-w-[760px] bg-canvas pt-2 pb-4",
                      selectedStudies.length > 0 ? "bottom-16" : "bottom-0"
                    )}
                  >
                    <SearchInput
                      onSearch={handleSearch}
                      isLoading={isLoading}
                      placeholder="Ask another question…"
                      label="Another question"
                    />
                  </div>
                </div>

                {/* Sources column */}
                <aside
                  id="panel-sources"
                  role="tabpanel"
                  aria-labelledby="tab-sources"
                  className={cn(
                    "min-w-0 xl:sticky xl:top-20 xl:max-h-[calc(100dvh-6rem)] xl:self-start xl:overflow-y-auto xl:overscroll-contain",
                    narrowTab === "sources" ? "block" : "hidden xl:block",
                    selectedStudies.length > 0 && "pb-20"
                  )}
                >
                  {isLoading && arrivingStudies.length > 0 ? (
                    <EvidencePanel
                      studies={arrivingStudies}
                      citations={[]}
                      selectedStudies={[]}
                      onSelectStudy={() => {}}
                      onExcludeStudy={() => {}}
                      onOpenPdf={(study) => openPdf(study.id, study.title || study.id, 1)}
                      studiesRead={progress?.done}
                    />
                  ) : isLoading ? (
                    <div className="space-y-3" aria-hidden="true">
                      {[0, 1, 2].map((i) => (
                        <div key={i} className="h-36 animate-pulse rounded-md bg-surface-1" />
                      ))}
                    </div>
                  ) : (
                    sourcesPanel
                  )}
                </aside>
              </div>
            </div>
          )}
        </main>
      </div>

      {selectedStudies.length > 0 && (
        <div className="fixed inset-x-0 bottom-0 z-40 border-t border-hairline bg-canvas pb-[env(safe-area-inset-bottom)] shadow-lg">
          <div className="mx-auto flex max-w-[1280px] items-center justify-between gap-3 px-4 py-3 md:px-6">
            <p className="tabular text-body text-ink">
              {selectedStudies.length} {selectedStudies.length === 1 ? "study" : "studies"} selected
            </p>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setSelectedStudies([])}>
                Clear
              </Button>
              <Button onClick={() => setIsCompareModalOpen(true)} disabled={selectedStudies.length < 2}>
                Compare studies
              </Button>
            </div>
          </div>
        </div>
      )}

      <CompareModal
        isOpen={isCompareModalOpen}
        onClose={() => setIsCompareModalOpen(false)}
        studies={selectedStudies}
        onRemoveStudy={(study) => {
          setSelectedStudies((prev) => prev.filter((s) => s.id !== study.id));
          if (selectedStudies.length <= 1) setIsCompareModalOpen(false);
        }}
      />
    </div>
  );
}
