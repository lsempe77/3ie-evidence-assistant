"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Citation, EvidenceHealth, AnswerStyle } from "@/types";
import { AlertTriangle, Info, Copy, Check, BookOpen } from "lucide-react";

interface AnswerPanelProps {
  answer: string;
  citations: Citation[];
  evidenceHealth: EvidenceHealth;
  suggestions: string[];
  answerStyle: AnswerStyle;
  isLoading?: boolean;
  onCitationClick: (citationId: number) => void;
  onSuggestionClick: (suggestion: string) => void;
  /** Shown on narrow screens, where sources sit in their own tab. */
  onShowSources?: () => void;
}

export function AnswerPanel({
  answer,
  citations,
  evidenceHealth,
  suggestions,
  isLoading = false,
  onCitationClick,
  onSuggestionClick,
  onShowSources,
}: AnswerPanelProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      // Try modern Clipboard API first
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(answer);
      } else {
        // Fallback for non-secure contexts (like VS Code Simple Browser)
        const textArea = document.createElement("textarea");
        textArea.value = answer;
        textArea.style.position = "fixed";
        textArea.style.left = "-999999px";
        textArea.style.top = "-999999px";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        document.execCommand("copy");
        textArea.remove();
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
      // Still show copied as user may have manually copied
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // Render a single citation button
  const renderCitationButton = (citationId: number, key: string): React.ReactNode => {
    const isValidCitation = citations.some(c => c.id === citationId);
    
    if (isValidCitation) {
      return (
        <button
          key={key}
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onCitationClick(citationId);
          }}
          aria-label={`Source ${citationId}`}
          className="tabular mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-sm bg-primary-tint px-1 align-baseline text-caption font-medium text-primary transition-colors hover:bg-highlight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {citationId}
        </button>
      );
    } else {
      return (
        <span key={key} className="text-ink-subtle" title="This source number is not in the list">
          [{citationId}]
        </span>
      );
    }
  };

  // Custom renderer for citations in markdown - converts [1], [2], [1,2], [1, 2, 3] to clickable bubbles
  const renderCitationLinks = (text: string): React.ReactNode => {
    // Match single [1] or combined [1,2] [1, 2, 3] patterns
    const parts = text.split(/(\[\d+(?:\s*,\s*\d+)*\])/g);
    
    return parts.map((part, index) => {
      // Check for combined citations like [1,2] or [1, 2, 3]
      const multiMatch = part.match(/\[(\d+(?:\s*,\s*\d+)+)\]/);
      if (multiMatch) {
        // Parse all citation numbers
        const citationIds = multiMatch[1].split(/\s*,\s*/).map(n => parseInt(n, 10));
        return (
          <span key={index}>
            {citationIds.map((citationId, i) => renderCitationButton(citationId, `${index}-${i}`))}
          </span>
        );
      }
      
      // Check for single citation like [1]
      const singleMatch = part.match(/\[(\d+)\]/);
      if (singleMatch) {
        const citationId = parseInt(singleMatch[1], 10);
        return renderCitationButton(citationId, `${index}`);
      }
      
      return <span key={index}>{part}</span>;
    });
  };

  // Recursively process all children to find citation patterns [1], [2], etc.
  const processNode = (node: React.ReactNode): React.ReactNode => {
    // Handle strings - this is where citations like [1] appear
    if (typeof node === "string") {
      if (/\[\d+(?:\s*,\s*\d+)*\]/.test(node)) {
        return renderCitationLinks(node);
      }
      return node;
    }
    
    // Handle numbers
    if (typeof node === "number") {
      return node;
    }
    
    // Handle arrays
    if (Array.isArray(node)) {
      return node.map((child, i) => (
        <React.Fragment key={i}>{processNode(child)}</React.Fragment>
      ));
    }
    
    // Handle React elements - recursively process children
    if (React.isValidElement(node)) {
      const props = node.props as { children?: React.ReactNode };
      if (props.children !== undefined) {
        return React.cloneElement(
          node,
          { ...props, key: node.key },
          processNode(props.children)
        );
      }
    }
    
    return node;
  };

  const hasHealth =
    evidenceHealth.studyCount > 0 || evidenceHealth.gaps.length > 0 || !!evidenceHealth.coverageWarning;

  if (isLoading) {
    return (
      <div className="w-full max-w-[760px]" aria-busy="true">
        <p className="mb-4 text-body text-ink-muted" role="status" aria-live="polite">
          Searching the collection and writing the answer…
        </p>
        <div className="animate-pulse space-y-3" aria-hidden="true">
          <div className="h-4 w-full rounded-sm bg-surface-2" />
          <div className="h-4 w-11/12 rounded-sm bg-surface-2" />
          <div className="h-4 w-4/6 rounded-sm bg-surface-2" />
          <div className="h-4" />
          <div className="h-4 w-full rounded-sm bg-surface-2" />
          <div className="h-4 w-5/6 rounded-sm bg-surface-2" />
        </div>
      </div>
    );
  }

  return (
    <article className="w-full max-w-[760px]" aria-label="Answer">
      <div className="text-body-lg break-words text-ink">
        <ReactMarkdown
          components={{
            // Override paragraph to handle citation links
            p: ({ children }) => (
              <p className="mb-4">
                {processNode(children)}
              </p>
            ),
            // Style headings - but hide "References" heading since we have our own
            h2: ({ children }) => {
              const text = String(children);
              if (text.toLowerCase() === "references") {
                return null; // Hide the LLM's References heading
              }
              return (
                <h2 className="mt-6 mb-2 text-heading text-ink">
                  {children}
                </h2>
              );
            },
            h3: ({ children }) => (
              <h3 className="mt-4 mb-1 text-body-lg font-semibold text-ink">
                {processNode(children)}
              </h3>
            ),
            // Style bold text
            strong: ({ children }) => (
              <strong className="font-semibold text-ink">
                {processNode(children)}
              </strong>
            ),
            // Style italic text
            em: ({ children }) => (
              <em className="italic">{processNode(children)}</em>
            ),
            // Style lists - but hide reference lists
            ul: ({ children }) => {
              // Check if this is a reference list (children are citations)
              const childArray = Array.isArray(children) ? children : [children];
              const isReferenceList = childArray.some((child: React.ReactNode) => {
                if (child && typeof child === 'object' && 'props' in child) {
                  const props = (child as React.ReactElement).props as { children?: React.ReactNode };
                  const text = String(props?.children || '');
                  return text.includes('(2023)') || text.includes('(2022)') || text.includes('(2021)');
                }
                return false;
              });
              if (isReferenceList) {
                return null; // Hide reference lists from LLM
              }
              return (
                <ul className="mb-4 list-disc space-y-1 pl-5">
                  {children}
                </ul>
              );
            },
            li: ({ children }) => (
              <li>{processNode(children)}</li>
            ),
            // Style horizontal rules
            hr: () => <Separator className="my-6" />,
          }}
        >
          {answer}
        </ReactMarkdown>
      </div>

      {/* Quiet footer row (DESIGN.md, Answer block) */}
      {answer && (
        <div className="mt-2 flex flex-wrap items-center gap-1 text-ink-muted">
          <Button variant="ghost" size="sm" onClick={handleCopy}>
            {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
            <span aria-live="polite">{copied ? "Copied" : "Copy answer"}</span>
          </Button>
          {onShowSources && citations.length > 0 && (
            <Button variant="ghost" size="sm" onClick={onShowSources} className="xl:hidden">
              <BookOpen aria-hidden="true" />
              Show sources
            </Button>
          )}
        </div>
      )}

      {/* Numbered list of what the answer cites */}
      {citations.length > 0 && (
        <section aria-labelledby="answer-references" className="mt-6 border-t border-hairline pt-4">
          <h2 id="answer-references" className="mb-2 text-body font-semibold text-ink">
            References
          </h2>
          <ol className="space-y-1">
            {citations.map((citation) => (
              <li key={citation.id}>
                <button
                  type="button"
                  onClick={() => onCitationClick(citation.id)}
                  className="-mx-2 flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span className="tabular inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-sm bg-primary-tint px-1 text-caption font-medium text-primary">
                    {citation.id}
                  </span>
                  <span className="min-w-0 break-words text-body text-ink-muted">
                    {citation.study.authors} ({citation.study.year}).{" "}
                    <span className="text-ink">{citation.study.title}</span>
                    {citation.page ? <span className="tabular text-ink-subtle">, page {citation.page}</span> : null}
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* How much evidence the answer rests on: a neutral block, words not colours */}
      {hasHealth && (
        <section aria-labelledby="answer-evidence" className="mt-6 rounded-md bg-surface-1 p-4">
          <h2 id="answer-evidence" className="mb-2 flex items-center gap-2 text-body font-semibold text-ink">
            <Info className="size-4 text-info" aria-hidden="true" />
            Evidence base
          </h2>
          {evidenceHealth.studyCount > 0 && (
            <p className="tabular text-body text-ink-muted">
              {evidenceHealth.studyCount} {evidenceHealth.studyCount === 1 ? "study" : "studies"}
              {evidenceHealth.dateRange ? `, published ${evidenceHealth.dateRange}` : ""}
            </p>
          )}
          {evidenceHealth.gaps.length > 0 && (
            <div className="mt-3">
              <p className="mb-1 text-caption font-medium text-ink-muted">Gaps</p>
              <ul className="space-y-1">
                {evidenceHealth.gaps.map((gap, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-body text-ink-muted">
                    <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-warning" aria-hidden="true" />
                    <span>{gap}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {evidenceHealth.coverageWarning && (
            <p className="mt-3 flex items-start gap-1.5 text-body text-ink-muted">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-warning" aria-hidden="true" />
              <span>{evidenceHealth.coverageWarning}</span>
            </p>
          )}
        </section>
      )}

      {suggestions.length > 0 && (
        <section aria-labelledby="answer-related" className="mt-6">
          <h2 id="answer-related" className="mb-2 text-body font-semibold text-ink">
            Related questions
          </h2>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((suggestion, i) => (
              <Button
                key={i}
                variant="outline"
                size="sm"
                className="h-auto min-h-8 py-1.5 text-left whitespace-normal"
                onClick={() => onSuggestionClick(suggestion)}
              >
                {suggestion}
              </Button>
            ))}
          </div>
        </section>
      )}
    </article>
  );
}
