"use client";

import { Check, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export type ProgressStage = "searching" | "reading" | "writing";

export interface AnswerProgressState {
  stage: ProgressStage;
  documents?: number | null;
  total: number;            // studies to read
  done: number;             // studies read so far
  relevant: number;
  directions: Record<string, number>;
  designs: Record<string, number>;
}

export const emptyProgress: AnswerProgressState = {
  stage: "searching",
  total: 0,
  done: 0,
  relevant: 0,
  directions: {},
  designs: {},
};

const DIRECTIONS: { key: string; label: string }[] = [
  { key: "positive", label: "Positive effect" },
  { key: "mixed", label: "Mixed" },
  { key: "null", label: "No clear effect" },
  { key: "negative", label: "Negative effect" },
];

const DESIGN_LABELS: Record<string, string> = {
  rct: "RCT",
  cluster_rct: "cluster RCT",
  difference_in_differences: "difference-in-differences",
  propensity_score_matching: "matching",
  instrumental_variable: "instrumental variables",
  regression_discontinuity: "regression discontinuity",
  mixed_methods: "mixed methods",
  case_study: "case study",
  qualitative: "qualitative",
};

function Step({ state, children }: { state: "done" | "active" | "waiting"; children: React.ReactNode }) {
  return (
    <li className={cn("flex items-center gap-2 text-body", state === "waiting" ? "text-ink-subtle" : "text-ink")}>
      <span className="flex size-5 shrink-0 items-center justify-center" aria-hidden="true">
        {state === "done" ? (
          <Check className="size-4 text-success" />
        ) : state === "active" ? (
          <Loader2 className="size-4 animate-spin text-primary" />
        ) : (
          <span className="size-1.5 rounded-full bg-hairline" />
        )}
      </span>
      <span className="tabular">{children}</span>
    </li>
  );
}

/**
 * What the pipeline is doing while the answer is written (roadmap N2): the steps, a
 * tally of findings by direction as studies are read, and the designs behind them.
 */
export function AnswerProgress({ progress }: { progress: AnswerProgressState }) {
  const { stage, total, done, relevant, directions, designs } = progress;
  const stepState = (s: ProgressStage) => {
    const order: ProgressStage[] = ["searching", "reading", "writing"];
    const i = order.indexOf(s), cur = order.indexOf(stage);
    return i < cur ? "done" : i === cur ? "active" : "waiting";
  };
  const topDesigns = Object.entries(designs).sort((a, b) => b[1] - a[1]).slice(0, 4);
  const maxCount = Math.max(1, ...DIRECTIONS.map((d) => directions[d.key] || 0));

  return (
    <div className="w-full max-w-[760px] space-y-6">
      {/* Screen readers hear the stage changes, not every study */}
      <p className="sr-only" role="status" aria-live="polite">
        {stage === "searching" ? "Searching the collection" : stage === "reading" ? "Reading the studies" : "Writing the answer"}
      </p>

      <ol className="space-y-2" aria-label="Progress">
        <Step state={stepState("searching")}>
          {stage === "searching"
            ? `Searching ${progress.documents ? `${progress.documents} documents` : "the collection"}…`
            : `Found ${total} candidate ${total === 1 ? "study" : "studies"}`}
        </Step>
        <Step state={stepState("reading")}>
          {stage === "searching"
            ? "Read each study"
            : `Read ${done} of ${total} studies · ${relevant} address the question`}
        </Step>
        <Step state={stepState("writing")}>
          {stage === "writing" ? "Writing the answer from the relevant studies…" : "Write the answer"}
        </Step>
      </ol>

      {relevant > 0 && (
        <section aria-labelledby="progress-tally" className="rounded-md bg-surface-1 p-4">
          <h2 id="progress-tally" className="mb-3 text-body font-semibold text-ink">
            What the studies found so far
          </h2>
          <ul className="space-y-2">
            {DIRECTIONS.map(({ key, label }) => {
              const n = directions[key] || 0;
              return (
                <li key={key} className="grid grid-cols-[8.5rem_1fr_2rem] items-center gap-3 text-body">
                  <span className="text-ink-muted">{label}</span>
                  <span className="h-2 overflow-hidden rounded-full bg-surface-2" aria-hidden="true">
                    <span
                      className={cn(
                        "block h-full rounded-full transition-[width] duration-300 ease-out",
                        key === "positive" ? "bg-primary" : key === "negative" ? "bg-danger" : "bg-ink-subtle"
                      )}
                      style={{ width: `${(n / maxCount) * 100}%` }}
                    />
                  </span>
                  <span className="tabular text-right text-ink">{n}</span>
                </li>
              );
            })}
          </ul>
          {topDesigns.length > 0 && (
            <p className="mt-3 text-caption text-ink-muted">
              {topDesigns.map(([d, n]) => `${n} ${DESIGN_LABELS[d] ?? d.replace(/_/g, " ")}`).join(" · ")}
            </p>
          )}
        </section>
      )}
    </div>
  );
}
