// Turns a Content Understanding result into the record the agent reads.

export const LOW_CONFIDENCE = 0.8;
const HAS_DIGIT = /\d/;

export type Flag = { text: string; confidence: number; page: number };
type Word = { content?: string; confidence?: number };
type Page = { pageNumber?: number; words?: Word[] };
export type CuContent = { markdown?: string; pages?: Page[] };

// Content Understanding separates pages with <!-- PageBreak -->. The agent and the report
// cite pages, so each page gets an explicit, numbered marker.
export function tagPages(markdown: string): string {
  return markdown
    .split(/<!--\s*PageBreak\s*-->/)
    .map((page, i) => `<!-- page ${i + 1} -->\n${page.trim()}`)
    .join("\n\n");
}

// Flag only tokens that contain a digit: a misread number (a lab value, a date, a dose)
// changes a decision silently, while a misread word is obvious on the page.
export function lowConfidenceNumbers(content: CuContent, threshold = LOW_CONFIDENCE): Flag[] {
  const worst = new Map<string, Flag>();
  for (const page of content.pages ?? []) {
    for (const word of page.words ?? []) {
      const text = (word.content ?? "").trim();
      const confidence = word.confidence;
      if (!text || typeof confidence !== "number" || confidence >= threshold || !HAS_DIGIT.test(text)) continue;
      const key = `${text}@${page.pageNumber}`;
      const seen = worst.get(key);
      if (!seen || confidence < seen.confidence) {
        worst.set(key, { text, confidence: Number(confidence.toFixed(3)), page: page.pageNumber ?? 0 });
      }
    }
  }
  return [...worst.values()].sort((a, b) => a.confidence - b.confidence);
}

export function caseRecord(markdown: string, flags: Flag[]): string {
  const notes = flags.length
    ? `OCR notes: these values were read with low confidence. Confirm them against the page.\n${flags
        .map((f) => `- "${f.text}" on page ${f.page} (confidence ${f.confidence})`)
        .join("\n")}`
    : "OCR notes: no low-confidence numbers.";
  return `${notes}\n\n${tagPages(markdown)}`;
}

export const newCaseId = () => `c-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
export const CASE_ID = /^[A-Za-z0-9_-]{1,64}$/;
