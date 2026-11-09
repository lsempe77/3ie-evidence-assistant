"use client";

import { Button } from "@/components/ui/button";
import { Loader2, ArrowUp } from "lucide-react";
import { useState, useId, FormEvent, KeyboardEvent } from "react";
import { cn } from "@/lib/utils";

interface SearchInputProps {
  onSearch: (query: string) => void;
  isLoading?: boolean;
  placeholder?: string;
  value?: string; // External controlled value
  label?: string;
  className?: string;
}

/**
 * Ask box (DESIGN.md, Components: Ask box). One question field and the primary
 * "Ask" button. Enter submits, Shift+Enter adds a line.
 */
export function SearchInput({
  onSearch,
  isLoading = false,
  placeholder = "Ask a question about development evidence…",
  value: externalValue,
  label = "Your question",
  className,
}: SearchInputProps) {
  const [query, setQuery] = useState(externalValue || "");
  const [syncedValue, setSyncedValue] = useState(externalValue);
  const id = useId();

  // Follow the external value when it changes (adjusting state during render,
  // as React recommends, rather than in an effect).
  if (externalValue !== syncedValue) {
    setSyncedValue(externalValue);
    if (externalValue !== undefined) setQuery(externalValue);
  }

  const submit = () => {
    if (query.trim() && !isLoading) {
      onSearch(query.trim());
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className={cn(
        "flex items-end gap-2 rounded-md border border-hairline bg-canvas p-2 focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2",
        className
      )}
    >
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <textarea
        id={id}
        name="question"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        rows={1}
        autoComplete="off"
        className="field-sizing-content max-h-40 min-h-9 flex-1 resize-none bg-transparent px-2 py-1.5 text-body-lg text-ink placeholder:text-ink-subtle outline-none"
      />
      <Button type="submit" disabled={isLoading || !query.trim()} className="shrink-0">
        {isLoading ? (
          <>
            <Loader2 className="animate-spin" aria-hidden="true" />
            Asking…
          </>
        ) : (
          <>
            <ArrowUp aria-hidden="true" />
            Ask
          </>
        )}
      </Button>
    </form>
  );
}
