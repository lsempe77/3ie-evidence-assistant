/**
 * Text matching and highlight painting for the pdf.js text layer.
 *
 * pdf.js renders one absolutely positioned <span> per text item and splits words
 * across spans at will, so a quote never maps 1:1 to an element. We therefore
 * flatten the layer's text nodes into a single string whose characters keep a
 * pointer back to their DOM position, and match on a separator-free form of the
 * text. Line breaks and hyphenation stop mattering because spaces, hyphens and
 * line breaks are never part of the compared string.
 */

/** Letters and digits in the scripts the app's PDFs use, without \p{...} (target ES2017). */
const WORD_CHAR = /[0-9A-Za-z\u00c0-\u024f\u0370-\u03ff\u0400-\u04ff]/;

export interface TextLayerChar {
  nodeIndex: number;
  offset: number;
}

export interface TextLayerIndex {
  /** Separator-free, lowercased text of the layer. */
  text: string;
  /** DOM position of each character in `text`. */
  chars: TextLayerChar[];
  /** True when the character at this index begins a new word. */
  wordStart: boolean[];
  /** Text nodes of the layer, in document order. */
  nodes: Text[];
}

export interface HighlightSpec {
  start: number;
  end: number;
  className: string;
  group: string;
  matchIndex?: number;
  active?: boolean;
}

/** Reduce a phrase to the same separator-free form used by the index. */
export function normalizeForSearch(input: string): string {
  let out = "";
  for (const ch of input) {
    if (WORD_CHAR.test(ch)) {
      const lower = ch.toLowerCase();
      out += lower.length === 1 ? lower : ch;
    }
  }
  return out;
}

export function buildTextLayerIndex(container: HTMLElement): TextLayerIndex {
  const nodes: Text[] = [];
  const chars: TextLayerChar[] = [];
  const wordStart: boolean[] = [];
  let text = "";
  let prevWord = false;

  const visit = (node: Node): void => {
    if (node.nodeType === Node.TEXT_NODE) {
      const textNode = node as Text;
      const data = textNode.data;
      if (!data) return;
      const nodeIndex = nodes.length;
      nodes.push(textNode);
      for (let i = 0; i < data.length; i += 1) {
        const ch = data[i];
        if (WORD_CHAR.test(ch)) {
          const lower = ch.toLowerCase();
          if (lower.length !== 1) {
            prevWord = true;
            continue;
          }
          text += lower;
          chars.push({ nodeIndex, offset: i });
          wordStart.push(!prevWord);
          prevWord = true;
        } else {
          prevWord = false;
        }
      }
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const element = node as Element;
    if (element.classList.contains("endOfContent")) return;
    // A line break is a word separator; an element boundary inside a word is not.
    if (element.tagName === "BR") {
      prevWord = false;
      return;
    }
    const children = Array.from(node.childNodes);
    for (const child of children) visit(child);
  };

  visit(container);
  return { text, chars, wordStart, nodes };
}

/**
 * Indices in `index.text` where `query` occurs, leftmost first and non-overlapping.
 * `wholeWord` rejects matches that start or end inside a longer word, which keeps
 * short queries from matching inside unrelated words.
 */
export function findMatches(index: TextLayerIndex, query: string, wholeWord = true): number[] {
  const needle = normalizeForSearch(query);
  const hay = index.text;
  const out: number[] = [];
  if (!needle) return out;

  let from = 0;
  let lastEnd = -1;
  while (from <= hay.length - needle.length) {
    const at = hay.indexOf(needle, from);
    if (at === -1) break;
    const end = at + needle.length;
    const startsWord = !wholeWord || at === 0 || index.wordStart[at];
    const endsWord = !wholeWord || end >= hay.length || index.wordStart[end];
    if (startsWord && endsWord && at >= lastEnd) {
      out.push(at);
      lastEnd = end;
    }
    from = at + 1;
  }
  return out;
}

/**
 * Longest prefix of the quote that still matches this page. Full-text retrieval
 * sometimes returns a passage whose tail was re-flowed, so a shorter prefix keeps
 * the highlight useful instead of dropping it.
 */
export function findQuoteMatch(
  index: TextLayerIndex,
  quote: string
): { start: number; length: number } | null {
  const full = normalizeForSearch(quote);
  if (full.length < 6) return null;
  const probes = full.length > 120 ? [full, full.slice(0, 120), full.slice(0, 60), full.slice(0, 30)] : [full, full.slice(0, 40), full.slice(0, 20)];
  for (const probe of probes) {
    if (probe.length < 6) continue;
    const hits = findMatches(index, probe, false);
    if (hits.length > 0) return { start: hits[0], length: probe.length };
  }
  return null;
}

export function clearHighlights(container: HTMLElement): void {
  const marks = container.querySelectorAll("mark[data-pdf-mark]");
  marks.forEach((mark) => {
    const parent = mark.parentNode;
    if (!parent) return;
    while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
    parent.removeChild(mark);
  });
}

/**
 * Wrap each highlighted span in a <mark>. Ranges can cross several text nodes, so
 * every node on the way is painted; within a node the segments are applied from the
 * highest offset down, because splitting the node at a later offset leaves the
 * earlier offsets valid.
 */
export function applyHighlights(container: HTMLElement, index: TextLayerIndex, specs: HighlightSpec[]): void {
  const segmentsByNode = new Map<number, Array<{ a: number; b: number; spec: HighlightSpec }>>();

  for (const spec of specs) {
    if (spec.end <= spec.start) continue;
    const start = index.chars[spec.start];
    const end = index.chars[spec.end - 1];
    if (!start || !end) continue;
    for (let nodeIndex = start.nodeIndex; nodeIndex <= end.nodeIndex; nodeIndex += 1) {
      const node = index.nodes[nodeIndex];
      if (!node) continue;
      const a = nodeIndex === start.nodeIndex ? start.offset : 0;
      const b = nodeIndex === end.nodeIndex ? end.offset + 1 : node.data.length;
      if (a >= b) continue;
      const list = segmentsByNode.get(nodeIndex) ?? [];
      list.push({ a, b, spec });
      segmentsByNode.set(nodeIndex, list);
    }
  }

  for (const [nodeIndex, segments] of segmentsByNode) {
    const node = index.nodes[nodeIndex];
    if (!node || !node.parentNode) continue;
    segments.sort((left, right) => right.a - left.a);
    for (const segment of segments) {
      const mark = document.createElement("mark");
      mark.setAttribute("data-pdf-mark", "");
      mark.setAttribute("data-pdf-group", segment.spec.group);
      if (segment.spec.matchIndex !== undefined) {
        mark.setAttribute("data-pdf-match", String(segment.spec.matchIndex));
      }
      if (segment.spec.active) mark.setAttribute("data-pdf-active", "true");
      mark.className = segment.spec.className;
      const range = document.createRange();
      range.setStart(node, segment.a);
      range.setEnd(node, segment.b);
      try {
        range.surroundContents(mark);
      } catch {
        // A range that cannot be wrapped is skipped rather than breaking the rest.
      }
    }
  }
}
