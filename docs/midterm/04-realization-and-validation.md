# 4. Realization and validation

**Status:** evidence summary, not a new test report. Results below are copied from existing project records; they have not been rerun for this document.

## 4.1 What has been realized

The repository describes a local end-to-end prototype with project/sample registration, pasted-text and PDF intake, a PDF text/OCR extraction path, a rule-based linker, a hybrid linking pipeline, an AI client interface with replay/stand-in answers, human decisions and audit history, draft IHM sections, and ODT export. The app README and `docs/what-we-built.md` provide the feature-level record.

The Groq client has now been added, but no live result has been recorded. Approved real-report processing, field-level OCR confidence/review, broad lab-layout support, hosted pilot controls and operational support remain unbuilt or unvalidated.

## 4.2 Existing quantitative evidence

Saved rule-only results in `docs/iteration-log.md` show:

| Dataset | Correct | Wrong | Correct abstentions | Missed links | Interpretation |
|---|---:|---:|---:|---:|---|
| dev, 12 lines | 8 | 0 | 2 | 2 | No wrong links in this synthetic set; two valid matches were conservatively missed. |
| dev2, 11 lines | 8 | 0 | 2 | 1 | No wrong links in this synthetic set; one valid match was conservatively missed. |
| hold, 9 lines | 6 | 0 | 2 | 1 | One recorded rules-only run; do not use it to tune the rules. |

The saved prompt v1 comparison shows **0 recorded AI answers out of 12 dev lines and 0 out of 11 dev2 lines**. The AI-only variant therefore abstained on available replay cases, and the hybrid matched rules. This is not evidence that a live model performs poorly or well; it means the live AI contribution has not yet been evaluated.

The dev/dev2 results are synthetic and small. They do not establish real-report accuracy, generalisation to new lab formats, or the K2 target of 98% across representative work.

## 4.3 Validation plan and metric definitions

| Measure | Definition | Evidence required / next check |
|---|---|---|
| Extraction accuracy (K1) | Correct extracted values divided by expert-labelled expected values, reported per field and document type. | Expert-labelled digital PDFs and scans; include ID, substance, result, unit, detection limit, method and certificate. |
| Link quality (K2) | Correct, wrong, correct abstention and missed-link counts; also report wrong-link rate and coverage. | Gold-standard matches validated by Joris/RVL; preserve hold-out cases for final evaluation. |
| Completeness (K3) | Seeded missing items found and false alarms, separately reported. | Seed missing photos, certificates and required fields; review warning correctness. |
| Escalation (K4) | Unclear cases routed to human review divided by all seeded unclear cases. | Low-quality scans, absent IDs, duplicates, conflicts and ambiguous numeric formats. |
| Time (K5) | Comparable elapsed time for manual workflow versus assisted workflow. | Record a manual baseline and assisted task with comparable reports and users. |
| Report correctness (K6) | Correct required output fields divided by expected fields. | Expert review against client-approved template and thresholds. |
| Traceability (K7) | Required links/evidence present across result → sample → source → location → photo/drawing → certificate. | Representative project audit; name missing links rather than only a total. |
| Usability (K8) | SUS score and observed task completion/issues if RVL accepts SUS. | Think-aloud session with representative inspectors. |
| Confidence calibration (K9) | Correctness among cases labelled high only when objective checks pass. | Use verifiable checks; never rely on model-reported confidence alone. |
| Reviewer error detection (K10) | Seeded errors found by reviewer divided by errors seeded. | Controlled practice review; do not mix practice score with live client performance. |

Targets recorded in `docs/context.md` include K1 ≥95%, K2 ≥98% and zero silent wrong links, K3 ≥90% seeded gaps found with ≤15% false alarms, K4 100% unclear cases escalated, K5 ≥50% faster, K6 ≥90%, K7 100%, K8 SUS ≥68, K9 ≥98% correct among high-confidence cases, and K10 ≥80%. Treat them as project targets pending stakeholder confirmation and a precise denominator for each KPI.

## 4.4 Known validation gaps

- No approved representative real lab reports have been evaluated.
- OCR field-level accuracy and field-level uncertainty are not established.
- The optional Groq client has not yet been evaluated; recorded stand-ins are not model output.
- Manual processing-time baseline and user usability results are missing.
- Thresholds, code notation, report conventions and sign-off roles still require RVL confirmation.
- Hosted security, privacy, reliability and recovery have not been validated.

## 4.5 Reproducibility

The repository contains test commands and saved evaluation runs. `docs/how-to-test.md` describes the test suite and scoring commands; `docs/iteration-log.md` records the saved runs and prompt version. For a formal midterm submission, capture dated command output or screenshots from the actual commit being presented and state dataset, code version, and whether any answers came from a stand-in.
