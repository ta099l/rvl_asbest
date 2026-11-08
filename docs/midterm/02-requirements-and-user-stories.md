# 2. Requirements and user stories

**Status:** draft derived from the RVL onboarding summary, project test cases and current prototype. Client acceptance is still required.

## 2.1 Functional requirements

| ID | Requirement | Acceptance check | Current evidence/status |
|---|---|---|---|
| FR-01 | A user can create a project/object and register sampled sources with identifiers and location/material details. | Create a fictional project and register at least one sample; the sample is available to the report workflow. | Described as implemented in `docs/what-we-built.md` and `app/README.md`; verify in live demo because an older status table conflicts. |
| FR-02 | A user can register a place that was not sampled with a reason. | Such a place appears as a survey limitation/PCHM and cannot receive a lab-result link. | Implemented according to `docs/what-we-built.md`; test case TC08. |
| FR-03 | A user can enter report lines by paste or upload a PDF. | Pasted text and a supported digital PDF produce visible lab rows; scan path reports that OCR was used. | Implemented for simple layouts; `james/extract.py`. |
| FR-04 | The system extracts report table fields without silently discarding supported columns. | For a supported table, IDs, descriptions, results and present certificate/method/quantity/remarks columns remain associated with the row. | Partial: simple table reconstruction; layout generality and full K1 fields are not established. |
| FR-05 | The system proposes a link only to a registered sample. | An unknown code, duplicate/ambiguous match or conflicting evidence results in no automatic link and an explanation. | Implemented in linker/contract/hybrid; synthetic test evidence exists. |
| FR-06 | The system uses AI only as assistance for eligible uncertain rows. | Rules settle clear/safety-conflict cases; invalid model output fails safely; model disagreement does not create an unsafe link. | Pipeline and optional Groq client are implemented; live model evaluation has not yet been recorded. |
| FR-07 | A named inspector can approve, correct, reject or defer each proposal. | Each recorded decision has a user identity and remains visible in the decision history. | Described in app build notes; verify complete flow in demo. |
| FR-08 | The system creates a draft IHM report from approved information. | Approved results appear in relevant draft sections/export; undecided rows do not silently become approved findings. | Draft and ODT export described as implemented. Template availability is external to the repo. |
| FR-09 | The system flags missing or uncertain information. | A seeded missing item or unreadable case is shown as a warning or review item, not silently filled. | Partial: some completeness checks and page-level OCR note exist; field-level OCR uncertainty is a gap. |
| FR-10 | The system preserves evidence about report intake and processing. | Report source/fingerprint, read method and relevant linker/prompt version can be inspected. | Implemented according to build notes. |

## 2.2 Nonfunctional requirements

| ID | Requirement | Acceptance measure | Current status |
|---|---|---|---|
| NFR-01 Safety | AI and rules produce proposals only; an authorised person owns final decisions. | No report can be treated as final without the required human decision/sign-off. | Core design principle implemented; confirm roles with RVL. |
| NFR-02 Safe failure | Invalid structured AI output, conflicting evidence or an unregistered sample must not create a link. | Deliberately malformed outputs and conflict cases return no link with a reason. | Covered by contract/linker test design and existing tests; see `docs/how-to-test.md`. |
| NFR-03 Traceability | A reviewer can reconstruct the input source, processing version and human changes. | Evidence and append-only decision history are available for a report. | Partly implemented; verify retained evidence and access needs with RVL. |
| NFR-04 Extraction quality | Required fields should meet the project target of at least 95% field accuracy. | Field-level accuracy measured against expert-labelled representative documents, reported per field and document type. | Target exists in `docs/context.md`; current coverage and result do not meet/prove it. |
| NFR-05 Link quality | Target at least 98% correct links and zero silent wrong links on agreed evaluation data. | Report correct, wrong, safe-abstain and missed-link counts on a labelled set; separately report hold-out results. | Synthetic baseline only; not evidence of real-world accuracy. |
| NFR-06 Usability | Inspectors can understand and correct proposals in the workflow. | Observe representative users completing tasks; collect task completion, errors and SUS if agreed. | Not yet measured. |
| NFR-07 Performance | Processing should reduce report handling time by at least 50% versus current practice. | Time matched manual and assisted workflows with comparable reports and users. | Target exists; baseline and outcome not measured. |
| NFR-08 Privacy | No real client or personal data is sent to an external service without explicit approval and suitable controls. | Document approved data classes, provider, retention, access and processing terms before any live AI test. | Fictional data rule is in force; approval not recorded. |
| NFR-09 Security for hosted pilot | Only authorised users can access projects and reports; connections and stored data are protected. | Define and verify authentication, role/access policy, HTTPS, secrets management, backup and recovery before pilot use. | Not demonstrated by the local prototype. |
| NFR-10 Compatibility | Draft output follows the RVL-approved report structure and terminology. | RVL reviewer checks a representative generated draft against the approved template. | ODT export exists; client acceptance and thresholds remain open. |

## 2.3 User stories

1. **As an inspector,** I want to register a sample with its location, material and source details, **so that** a lab result can be traced back to where it came from.
2. **As an inspector,** I want to mark an inaccessible place as not sampled with a reason, **so that** it is reported as a limitation rather than as confirmed clean.
3. **As an inspector,** I want to upload or paste a lab report and see the extracted rows, **so that** I can check the input before matching it.
4. **As an inspector,** I want a proposed sample link with an understandable reason, **so that** I can verify the match efficiently.
5. **As an inspector,** I want unclear or conflicting rows to remain unlinked and be highlighted, **so that** I can resolve them without a hidden guess.
6. **As an authorised reviewer,** I want to approve, correct or reject each proposal under my name, **so that** accountability is clear.
7. **As a technical responsible person,** I want a draft IHM report assembled from reviewed findings, **so that** I can check and sign the deliverable.
8. **As a quality reviewer,** I want to see the report source, processing version and decision history, **so that** I can trace how the draft was produced.

## 2.4 Stakeholder questions before baselining

- Which sample-code notation and fields are authoritative?
- Which threshold values and report template version should the prototype use?
- Does each report row carry a certificate number, or is it shared by the report?
- Who decides, who quality-checks and who signs?
- Which report layouts and scan quality are in the first pilot?
- What evidence is sufficient for acceptance of each requirement?

Until answered, these requirements are useful draft acceptance criteria, not a formal client sign-off.
