"use client";

import { Button } from "@/components/ui/button";
import { Study } from "@/types";
import { FileText, GitCompare, X, Check } from "lucide-react";
import { StudyDesignBadge } from "./StudyDesignBadge";
import { cn } from "@/lib/utils";

interface StudyCardProps {
  study: Study;
  citationNumber?: number;
  isHighlighted?: boolean;
  isSelected?: boolean;
  onSelect?: (study: Study) => void;
  onExclude?: (study: Study) => void;
  onOpenPdf?: (study: Study) => void;
  onClick?: () => void;
}

const confidenceLabel: Record<Study["confidence"], string> = {
  high: "Close match",
  medium: "Partial match",
  low: "Weak match",
};

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-sm border border-hairline bg-surface-1 px-1.5 py-0.5 text-caption text-ink-muted">
      {children}
    </span>
  );
}

/**
 * Source card (DESIGN.md, Components: Source card): study, authors and year,
 * design and country tags, the quoted passage and a link to the page.
 */
export function StudyCard({
  study,
  citationNumber,
  isHighlighted = false,
  isSelected = false,
  onSelect,
  onExclude,
  onOpenPdf,
}: StudyCardProps) {
  const countries = study.country && study.country !== "Unknown" ? study.country : null;

  return (
    <article
      id={`study-${study.id}`}
      aria-labelledby={`study-title-${study.id}`}
      className={cn(
        "scroll-mt-4 rounded-md border bg-canvas p-4 transition-colors",
        isHighlighted ? "border-primary bg-primary-tint" : "border-hairline",
        isSelected && !isHighlighted && "border-primary"
      )}
    >
      <div className="flex items-start gap-2">
        {citationNumber !== undefined && (
          <span className="tabular mt-0.5 inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-sm bg-primary-tint px-1 text-caption font-medium text-primary">
            {citationNumber}
          </span>
        )}
        <div className="min-w-0 flex-1">
          <h3
            id={`study-title-${study.id}`}
            className="font-sans text-body font-semibold break-words text-ink"
          >
            {study.title || "Untitled study"}
          </h3>
          <p className="tabular mt-0.5 text-body break-words text-ink-muted">
            {study.authors}
            {study.year ? ` (${study.year})` : ""}
          </p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-1">
        {study.studyDesign && (
          <StudyDesignBadge design={study.studyDesign} confidence={study.studyDesignConfidence} />
        )}
        {countries && <Tag>{countries}</Tag>}
        {study.sector && <Tag>{study.sector}</Tag>}
        <Tag>{confidenceLabel[study.confidence] ?? study.confidence}</Tag>
      </div>

      {study.finding && <p className="mt-3 text-body text-ink">{study.finding}</p>}

      {study.snippet && (
        <blockquote className="mt-3 line-clamp-4 rounded-sm bg-surface-2 px-3 py-2 text-body text-ink-muted">
          “{study.snippet}”
        </blockquote>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-1">
        {onOpenPdf && study.pdfUrl && (
          <Button
            variant="link"
            size="sm"
            className="px-0 pr-2"
            onClick={() => onOpenPdf(study)}
          >
            <FileText aria-hidden="true" />
            Open document
          </Button>
        )}
        <div className="ml-auto flex items-center gap-1">
          {onSelect && (
            <Button
              variant="ghost"
              size="sm"
              aria-pressed={isSelected}
              className={cn(isSelected && "text-primary")}
              onClick={() => onSelect(study)}
            >
              {isSelected ? <Check aria-hidden="true" /> : <GitCompare aria-hidden="true" />}
              {isSelected ? "Selected" : "Compare"}
            </Button>
          )}
          {onExclude && (
            <Button
              variant="ghost"
              size="sm"
              className="text-ink-muted"
              onClick={() => onExclude(study)}
              aria-label={`Hide ${study.title || "this study"} from the sources`}
            >
              <X aria-hidden="true" />
              Hide
            </Button>
          )}
        </div>
      </div>
    </article>
  );
}
