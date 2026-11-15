---
name: underwriting-decision
description: The decision policy for the recommendation field of submit_report, grounded in the underwriting guidelines search. Load before choosing a decision.
---

# Underwriting decision policy

These are illustrative rules for a sample template, not actuarial guidance. Replace
them, and the guideline documents in the search index, with your own.

## Steps

1. For each condition, search the underwriting guidelines with the condition name and
   its key values (for example "hypertension blood pressure 150/95 treated").
2. Take the decision the guideline passage gives for the documented values. Record the
   passage titles in the condition's `guideline_refs`.
3. Combine conditions: the overall decision is the most severe individual decision,
   in this order: Standard, Rated, Refer to underwriter, Postpone, Decline.
4. Write the rationale as one sentence per condition, naming the value and the passage.

## When to postpone or refer

- **Postpone** when a condition is under active investigation, a key result is
  pending, or a guideline requires a waiting period that has not elapsed.
- **Refer to underwriter** when no guideline passage covers a material condition, the
  record contradicts itself on a value that changes the decision, or a decisive value
  is listed as low-confidence OCR.

## Hard rules

- No decision without at least one guideline passage in `guideline_refs`.
- Never derive a rating from general medical knowledge alone.
- The recommendation is advice. The underwriter decides.
