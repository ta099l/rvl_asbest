# 5. Project management and control

**Status:** proposed plan for the remaining three months. Exact school and client milestones must be confirmed.

## 5.1 Delivery approach

Use short, reviewable stages. Each stage has a stakeholder check and an evidence output. Keep the prototype scope to one workflow and avoid treating a successful demo as proof of production readiness.

| Relative stage | Focus | Exit evidence |
|---|---|---|
| Weeks 1–2 | Midterm/client feedback; confirm use case, fields, code notation, review/sign-off roles, data permissions and success measures. | Dated client feedback; baselined requirements; decision log; approved test-data plan. |
| Weeks 3–5 | Improve the agreed extraction and review path; resolve the highest-impact gaps in registration and report output. | Requirement-to-test mapping; labelled synthetic/approved cases; extraction and completeness results. |
| Weeks 6–8 | Test rules and, only if approved, a real AI client on uncertain cases. Run controlled user review. | Rules/AI comparison with source/version recorded; user-test notes; privacy/AI approval record. |
| Weeks 9–10 | Fix observed failures; assess pilot hosting requirements and operational controls. | Prioritised defects; architecture/security decision; deployment readiness gaps. |
| Weeks 11–12 | Freeze a candidate, repeat agreed evaluation, prepare handover and final portfolio evidence. | Reproducible KPI sheet, transition document, known-limitations list and demo rehearsal. |

This schedule assumes timely decisions, access to a domain expert, and a stable student team. If those dependencies slip, reduce scope to a validated local prototype rather than claiming a live production system.

## 5.2 Decision and change control

Keep each material decision with date, owner, rationale, evidence and status (proposed/accepted/rejected). The repo already uses `docs/decisions.md`; add client decisions there or link the formal meeting record. Version prompts and test sets so results can be reproduced. Do not change hold-out references to improve a score; resolve disagreements with the domain expert and document any corrected reference set.

Before changing scope, ask: which user need does it address, which requirement changes, what evidence will demonstrate it, who owns the work, and what is displaced from the three-month plan?

## 5.3 Risks and controls

| Risk | Likelihood/impact (initial) | Control / trigger |
|---|---|---|
| Client rules and report conventions remain unresolved | High / High | Confirm codes, thresholds, required fields and template before baselining; record decision owner/date. |
| Real documents or AI service are not approved in time | Medium / High | Use synthetic cases; keep live AI behind an approval gate; do not send real data to unapproved tools. |
| OCR misreads identifiers or numbers | High / High | Display original alongside extracted fields; require human verification; measure errors per field and scan quality. |
| AI produces plausible but wrong links | Medium / High | Rules-first routing, strict contract, no-link on conflict, named review, zero-silent-wrong-link KPI. |
| Test set is too small or too similar to development data | High / High | Broaden cases by layout and failure mode; preserve a hold-out set; describe dataset limits. |
| Team capacity is consumed by production hosting | Medium / Medium | Defer hosting until the workflow and pilot need are agreed; document minimum security/operations for a later stage. |
| Evidence is split across team members or missing | Medium / High | Maintain one evidence map, owner and due date per rubric dimension; do a weekly completeness review. |

## 5.4 Roles to confirm

Existing project context assigns app/build work to Ivan, AI workflow and prompting to Tasnim, business analysis/case to Sydney, strategy/editing to Chris, and validation/handover to Harm. Confirm that these roles are current and assign one named owner to each outstanding client decision, KPI and portfolio artifact.

## 5.5 Weekly control check

At each team check-in, record: what changed; requirement(s) affected; risks/issues; test and KPI evidence; decision needed; owner and date; and whether the next client/coach review is ready. Escalate blockers early, particularly data approval, expert availability and report-field decisions.
