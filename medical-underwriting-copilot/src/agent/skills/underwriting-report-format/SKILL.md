---
name: underwriting-report-format
description: How to read an OCR'd medical record and fill every field of submit_report. Load before drafting any underwriting report.
---

# Underwriting report format

The report is evidence for a human underwriter. Every stated fact must be traceable
to a page of the record, and nothing may be stated that the record does not support.

## Reading the record

- Read every page. The record starts with OCR notes listing low-confidence values;
  treat those values as unconfirmed and list the ones that matter in `ocr_attention`.
- Pages are marked `<!-- page N -->`. Use those numbers for every `page` field.

## Field rules

| Field | Rule |
|---|---|
| `summary` | Three to five sentences: who, which conditions, how current, what is missing. |
| `conditions` | One entry per condition that could affect insurability. Skip minor, resolved, one-off complaints unless they recur. |
| `conditions[].icd10` | Exactly as written in the record. Records may use WHO ICD-10 codes that a US ICD-10-CM lookup does not list; never replace a documented code. Write `Not documented` when the record gives none. |
| `conditions[].evidence` | At least one fact with its page. Quote values with units as written. |
| `visits` | Every dated encounter, in date order, including laboratory-only visits. |
| `labs[].interpretation` | `Normal` or `Abnormal` only when a result is reported and the record or reference range supports it. A test that was ordered, sent, or pending is `Not interpreted`, with value `Pending`. |
| `discrepancies` | Conflicts inside the record (two different dates for one event, a diagnosis without supporting findings). Quote both sides with pages. |
| `recommendation` | Follow the underwriting-decision skill. |

## Absent information

Use `Not documented` when the record does not say something. Never fill a gap with a
typical value or an inference presented as fact.
