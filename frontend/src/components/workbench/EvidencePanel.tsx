"use client";

import { Button } from "@/components/ui/button";
import { StudyCard } from "./StudyCard";
import { Study, Citation } from "@/types";

interface EvidencePanelProps {
  studies: Study[];
  citations: Citation[];
  highlightedCitation?: number;
  selectedStudies: Study[];
  onSelectStudy: (study: Study) => void;
  onExcludeStudy: (study: Study) => void;
  onOpenPdf: (study: Study) => void;
  query?: string;
  answer?: string;
  /** Studies the reader looked at, when the answer came from the study-synthesis pipeline. */
  studiesRead?: number;
}

export function EvidencePanel({
  studies,
  citations,
  highlightedCitation,
  selectedStudies,
  onSelectStudy,
  onExcludeStudy,
  onOpenPdf,
  query = "",
  answer = "",
  studiesRead,
}: EvidencePanelProps) {
  // Get citation number for each study
  const getCitationNumber = (studyId: string): number | undefined => {
    const study = studies.find((s) => s.id === studyId);
    if (study?.citationNumber !== undefined) return study.citationNumber;
    const citation = citations.find((c) => c.studyId === studyId);
    return citation?.id;
  };

  // Check if study is selected for comparison
  const isSelected = (study: Study): boolean => {
    return selectedStudies.some((s) => s.id === study.id);
  };

  // Check if study should be highlighted (matches clicked citation)
  const isHighlighted = (study: Study): boolean => {
    if (!highlightedCitation) return false;
    const citation = citations.find((c) => c.id === highlightedCitation);
    return citation?.studyId === study.id;
  };

  // Export results as CSV
  const handleExportCSV = () => {
    const headers = ["Citation #", "Title", "Authors", "Year", "Country", "Sector", "Study Type", "Confidence", "Relevance Score", "Key Finding", "PDF URL"];
    const rows = studies.map((s) => [
      getCitationNumber(s.id) || "",
      s.title,
      s.authors,
      s.year,
      s.country,
      s.sector || "",
      s.studyType,
      s.confidence,
      s.score ? (s.score * 100).toFixed(0) + "%" : "",
      s.snippet,
      s.pdfUrl || ""
    ]);
    
    const csv = [headers.join(","), ...rows.map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `evidence_results_${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Export full results including answer as JSON
  const handleExportJSON = () => {
    const exportData = {
      exportDate: new Date().toISOString(),
      query,
      answer,
      studyCount: studies.length,
      studies: studies.map((s) => ({
        citationNumber: getCitationNumber(s.id),
        ...s
      }))
    };
    
    const json = JSON.stringify(exportData, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `evidence_results_${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Export as BibTeX format
  const handleExportBibTeX = () => {
    const entries = studies.map((s) => {
      const citeKey = `${(s.authors || "unknown").split(",")[0].trim().toLowerCase().replace(/\s+/g, "")}${s.year || "nd"}`;
      const authors = s.authors || "Unknown";
      const title = s.title || "Untitled";
      const year = s.year || "";
      
      return `@article{${citeKey},
  title = {${title.replace(/[{}]/g, "")}},
  author = {${authors.replace(/[{}]/g, "")}},
  year = {${year}},
  note = {Retrieved via 3ie Evidence Assistant evidence search}
}`;
    });
    
    const bibtex = entries.join("\n\n");
    const blob = new Blob([bibtex], { type: "application/x-bibtex" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `evidence_results_${new Date().toISOString().split("T")[0]}.bib`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section aria-labelledby="sources-heading" className="flex flex-col">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 id="sources-heading" className="text-heading text-ink">
          Sources{" "}
          <span className="tabular font-sans text-body font-normal text-ink-muted">
            {studies.length} {studies.length === 1 ? "study" : "studies"}
          </span>
        </h2>
        {studies.length > 0 && (
          <div className="flex items-center gap-1" role="group" aria-label="Download sources">
            <span className="mr-1 text-caption text-ink-subtle">Download</span>
            <Button variant="ghost" size="sm" onClick={handleExportCSV}>CSV</Button>
            <Button variant="ghost" size="sm" onClick={handleExportBibTeX}>BibTeX</Button>
            <Button variant="ghost" size="sm" onClick={handleExportJSON}>JSON</Button>
          </div>
        )}
      </div>

      {studiesRead !== undefined && (
        <p className="tabular mb-2 text-body text-ink-muted">
          Read {studiesRead} {studiesRead === 1 ? "study" : "studies"}. {studies.length} address the question.
        </p>
      )}

      {studies.length > 1 && selectedStudies.length === 0 && (
        <p className="mb-3 text-caption text-ink-subtle">Select two or more studies to compare them.</p>
      )}

      {studies.length === 0 ? (
        <div className="rounded-md border border-dashed border-hairline px-4 py-10 text-center">
          <h3 className="font-sans text-body font-semibold text-ink">No studies match this question</h3>
          <p className="mx-auto mt-1 max-w-xs text-body text-ink-muted">
            Try wording the question differently, or lower the minimum relevance in answer settings.
          </p>
        </div>
      ) : (
        <ul className="space-y-3">
          {studies.map((study) => (
            <li key={study.id}>
              <StudyCard
                study={study}
                citationNumber={getCitationNumber(study.id)}
                isHighlighted={isHighlighted(study)}
                isSelected={isSelected(study)}
                onSelect={onSelectStudy}
                onExclude={onExcludeStudy}
                onOpenPdf={onOpenPdf}
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
