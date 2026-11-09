"use client";

import { Button } from "@/components/ui/button";
import { Trash2, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CachedResponseData } from "@/lib/api";

export interface ChatHistoryItem {
  id: string;
  query: string;
  timestamp: Date;
  studyCount?: number;
  answer?: string;
  citationsUsed?: number;
  responseData?: CachedResponseData;
}

interface ChatHistoryProps {
  history: ChatHistoryItem[];
  currentQueryId?: string;
  onSelectQuery: (item: ChatHistoryItem) => void;
  onDeleteQuery: (id: string) => void;
  onNewChat: () => void;
}

const relativeTime = new Intl.RelativeTimeFormat("en-GB", { numeric: "auto", style: "short" });

function formatTimeAgo(date: Date): string {
  const diffMins = Math.round((date.getTime() - Date.now()) / 60000);
  if (Math.abs(diffMins) < 1) return "Just now";
  if (Math.abs(diffMins) < 60) return relativeTime.format(diffMins, "minute");
  const diffHours = Math.round(diffMins / 60);
  if (Math.abs(diffHours) < 24) return relativeTime.format(diffHours, "hour");
  return relativeTime.format(Math.round(diffHours / 24), "day");
}

/** Past questions for this collection (DESIGN.md, Ask screen: history region). */
export function ChatHistory({
  history,
  currentQueryId,
  onSelectQuery,
  onDeleteQuery,
  onNewChat,
}: ChatHistoryProps) {
  return (
    <nav aria-label="Past questions" className="flex h-full flex-col bg-surface-1">
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <h2 className="text-caption font-medium tracking-wide text-ink-muted uppercase">History</h2>
      </div>
      <div className="px-3 pb-3">
        <Button variant="outline" className="w-full justify-start" onClick={onNewChat}>
          <Plus aria-hidden="true" />
          New question
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto overscroll-contain px-3 pb-4">
        {history.length === 0 ? (
          <p className="px-2 py-6 text-body text-ink-subtle">
            Questions you ask appear here.
          </p>
        ) : (
          <ul className="space-y-0.5">
            {history.map((item) => {
              const active = currentQueryId === item.id;
              return (
                <li key={item.id} className="group relative">
                  <button
                    type="button"
                    onClick={() => onSelectQuery(item)}
                    aria-current={active ? "true" : undefined}
                    className={cn(
                      "w-full rounded-md px-2 py-2 pr-9 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      active ? "bg-primary-tint" : "hover:bg-surface-2"
                    )}
                  >
                    <span
                      className={cn(
                        "line-clamp-2 text-body break-words",
                        active ? "font-medium text-primary" : "text-ink"
                      )}
                    >
                      {item.query}
                    </span>
                    <span className="tabular mt-0.5 block text-caption text-ink-subtle">
                      {formatTimeAgo(item.timestamp)}
                      {item.studyCount !== undefined && ` · ${item.studyCount} studies`}
                    </span>
                  </button>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    className="absolute top-1.5 right-1 text-ink-subtle opacity-0 group-hover:opacity-100 focus-visible:opacity-100 hover:text-danger pointer-coarse:opacity-100"
                    onClick={() => onDeleteQuery(item.id)}
                    aria-label={`Remove “${item.query.slice(0, 40)}” from history`}
                  >
                    <Trash2 aria-hidden="true" />
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </nav>
  );
}
