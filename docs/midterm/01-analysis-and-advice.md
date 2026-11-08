# 1. Problem analysis and advice

**Status:** working draft for team/client validation  
**Project:** James — RVL IHM lab-report workflow  
**Evidence date:** repository notes through 2 November 2026

## 1.1 Organization and user need

RVL performs inspections and prepares hazardous-material and IHM documentation. The project materials describe a workflow that moves from project setup and field registration through laboratory analysis, quality review and reporting. Lab results must be associated with the correct sample and source in the inspected object. The final assessment remains the responsibility of an authorised inspector.

The business need recorded in the project context is to reduce repeated manual handling, avoid omissions, preserve traceability, and reuse structured object history. The initial use case is deliberately narrow: help prepare IHM Part I results from registered samples and a lab report.

**Evidence:** `docs/context.md` summarises the RVL onboarding and work process. Verify this understanding with the client during the demo and record any corrections.

## 1.2 Current and proposed process

| Stage | Current/manual work described in project notes | James prototype contribution |
|---|---|---|
| Set up job and register field findings | Create project and record sources/samples, locations and evidence | Project and sample registration screens are described in the app and build notes |
| Receive laboratory report | Read report and identify result rows | Paste report text or upload PDF; digital text is extracted directly, scanned pages can use local OCR when installed |
| Match results to samples | Compare report rows with field register | Rules propose clear links; uncertain eligible cases can be passed to the AI step; conflicts abstain |
| Check and approve | Inspector checks findings and corrects errors | Named inspector approves, corrects, rejects or leaves items undecided |
| Prepare deliverable | Compile report and preserve supporting records | Draft IHM sections and ODT export from approved data; evidence and decision history are retained |

The process description is based on project notes, not a fresh time-and-motion study. Manual baseline time and current error rates have not yet been measured.

## 1.3 Problem statement

Preparing an IHM report requires people to transfer and reconcile information across field records, sample registers, lab reports and a report template. This creates repetitive work and opportunities for omissions or incorrect links. James explores whether structured registration, assisted extraction, conservative matching and human review can make this work more traceable and efficient.

The project has **not yet demonstrated** a measured reduction in processing time or reliable extraction across real laboratory layouts. Those are validation questions, not established benefits.

## 1.4 Scope

**In scope for the prototype/pilot:** one IHM/HazMat Part I workflow; fictional or explicitly approved test data; project and sample registration; report text/PDF intake; extraction and sample-link proposals; completeness warnings; human review; draft report output; audit/evidence capture; repeatable evaluation.

**Out of scope for the current prototype:** autonomous approval; unrestricted report-layout support; broad survey types; unapproved real client data or AI services; production deployment and operational support.

## 1.5 Options and provisional multi-criteria analysis

The following comparison is a **team working assessment**, not client-approved scoring. Scores are 1 (weak) to 5 (strong). For risk and cost, a higher score means lower/manageable risk or cost. Criteria and weights should be agreed with the client before presenting this as a final recommendation.

| Criterion | Weight | A. Manual process with templates | B. Digital workflow + deterministic rules | C. Digital workflow + rules and AI assistance |
|---|---:|---:|---:|
| Potential process value | 25% | 2 | 3 | 5 |
| Safety and controllability | 25% | 5 | 5 | 3 |
| Feasibility within three months | 20% | 5 | 4 | 3 |
| Traceability | 15% | 2 | 4 | 5 |
| Cost, privacy and dependency manageability | 15% | 5 | 4 | 2 |
| **Weighted score / 5** | **100%** | **3.80** | **4.00** | **3.65** |

**How to read this:** option B scores highest as a near-term controlled pilot because it improves structure and traceability without depending on an unapproved model. Option C has greater potential for difficult cases, but its value and risk are not yet evidenced; the current AI is a replay/stand-in, not a live service. This does not mean AI should be abandoned. It means real AI should remain a gated experiment and must beat the rules baseline on agreed test data without increasing silent wrong links.

**Recommendation:** continue with the digital workflow and rules as the dependable baseline. Trial AI linking only after RVL approves the tool and data conditions, and only on uncertain cases with strict validation and inspector review. Treat cloud hosting as a separate later decision after a pilot security and operating model is agreed.

**Confirm with stakeholders:** criteria and weights; what counts as acceptable error; approved data and AI provider; whether there is a second reviewer; pilot hosting requirements; measured manual baseline.

## 1.6 Advice and decision gates

1. Confirm workflow, report fields, sample-code conventions and sign-off roles with RVL.
2. Agree synthetic or approved representative documents and have an IHM expert label the expected fields and links.
3. Validate extraction and rule-linking first. Keep errors visible and route ambiguity to people.
4. Evaluate real AI against the same held-out cases only after tool and data approval.
5. Consider a limited hosted pilot only after privacy, access, backup, retention and support requirements are defined.
