"use client";

import Image from "next/image";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";

interface AppTopBarProps {
  /** Name of the open collection, shown after "Collections". */
  collectionName?: string;
  /** Controls placed before the brand, such as the history toggle. */
  leading?: ReactNode;
  /** Controls on the right, such as settings and the account menu. */
  trailing?: ReactNode;
}

/**
 * 3ie marque (RGB, for white and light backgrounds) from 3ie's logo and branding
 * guidelines, version 1, 8 January 2015. Do not recolour or stretch it.
 */
function Brand() {
  return (
    <Link
      href="/dashboard"
      className="flex shrink-0 items-center gap-2 rounded-sm pointer-coarse:py-1.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <Image
        src="/brand/3ie-marque.svg"
        alt="3ie"
        width={26}
        height={32}
        priority
        unoptimized
      />
      <span className="hidden font-heading text-body leading-none font-medium text-ink sm:inline">
        Evidence Assistant
      </span>
    </Link>
  );
}

/** Top bar on every signed-in page (DESIGN.md, Components: Navigation). */
export function AppTopBar({ collectionName, leading, trailing }: AppTopBarProps) {
  return (
    <header className="sticky top-0 z-40 border-b border-hairline bg-canvas">
      <div className="flex h-14 items-center gap-2 px-4 md:px-6">
        {leading}
        <Brand />
        {collectionName && (
          <nav aria-label="Breadcrumb" className="flex min-w-0 items-center">
            <ChevronRight className="mx-1 size-4 shrink-0 text-ink-subtle" aria-hidden="true" />
            <Link
              href="/dashboard"
              className="hidden shrink-0 rounded-sm text-body text-ink-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:inline"
            >
              Collections
            </Link>
            <ChevronRight className="mx-1 hidden size-4 shrink-0 text-ink-subtle md:inline" aria-hidden="true" />
            <span className="truncate text-body font-medium text-ink" aria-current="page">
              {collectionName}
            </span>
          </nav>
        )}
        <div className="ml-auto flex shrink-0 items-center gap-1">{trailing}</div>
      </div>
    </header>
  );
}
