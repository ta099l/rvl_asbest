# User stories

James · AI-assisted linking of lab results for RVL Asbest · Version 2 · 17 November 2026

**Status:** user stories with acceptance criteria, linked to the requirements (FR / NFR) in the requirements document. Status as built and tested on fictional data on 17 November 2026. Priorities use MoSCoW (Must, Should, Could, Won't).

**Users:**

| Role | Who | Main goal |
| --- | --- | --- |
| Inspector | RVL surveyor in the field and at the desk | Register samples and link lab results quickly and correctly |
| Technical Responsible Person | Signs the IHM report for the company | Sign only a complete, correct report |
| Quality reviewer | Checks reports before they leave RVL | See how every result was linked and by whom |
| Project coordinator | Sets up projects at the office | Start a project with the right information |
| Product owner | Rolf van Leeuwen | Control over data, tools and the quality of the output |

## Epic 1 · Project and field registration

### US-01 · Create a project

Priority: **Must** · Requirements: FR-01

As a project coordinator, I want to create a project with the Project Information of the RVL template, so that every report starts with the right object, location and people.
- Given the New project form, when I leave the object name, project number or location empty, then the project is not created and I see why.
- Given a created project, when I open the project list, then I can select it and its information appears in the report.

**Status:** Done.

### US-02 · Register a sample

Priority: **Must** · Requirements: FR-02

As an inspector, I want to register each sample with its code, place, material and photo, so that a lab result can later be traced back to where it was taken.
- Given a new sample, when I save it with my name, then it appears in the register and the change is logged with my name and the time.
- Given a registered sample, when I edit it, then its code cannot change.

**Status:** Done.

### US-03 · Record a place that could not be sampled

Priority: **Must** · Requirements: FR-03

As an inspector, I want to mark a place as "not sampled" with a reason, so that it is reported as a limitation and never as "no hazardous material".
- Given a "not sampled" place, when a lab line carries its code, then no link is proposed.
- Given the report, when I download it, then the place is listed under survey limitations as potentially containing hazardous materials.

**Status:** Done.

### US-04 · Work on several projects

Priority: **Must** · Requirements: FR-04

As an inspector, I want to switch between projects and find my work again after a restart, so that I can handle more than one survey.

**Status:** Done.

## Epic 2 · Reading lab reports

### US-05 · Upload a lab report

Priority: **Must** · Requirements: FR-05, FR-06

As an inspector, I want to upload the lab's PDF, so that I do not have to type the results.
- Given a lab report with an overview table and results tables, when I upload it, then every result appears with our sample code and the lab's own ID.
- Given a result whose lab ID is not in the overview, when it is read, then it gets no sample code and I see a warning.
- Given a scanned PDF, when I upload it, then it is read by OCR and the screen says so.

**Status:** Done on fictional reports; not yet checked on real layouts.

### US-06 · See lab remarks and new versions

Priority: **Must** · Requirements: FR-07, FR-08

As an inspector, I want lab remark letters and replaced report versions to be visible, so that I do not treat an uncertain result as "absent" or use an outdated report.

**Status:** Done.

### US-07 · Read long result lists

Priority: **Should** · Requirements: FR-09

As an inspector, I want a sample with 16 parameters shown in one readable line, so that I can check it at a glance without losing values.

**Status:** Done.

## Epic 3 · Link proposals

### US-08 · Get a proposal with a reason

Priority: **Must** · Requirements: FR-11, FR-12, FR-19

As an inspector, I want a proposed sample for each lab result with a short reason, so that I can check the link instead of searching for it.
- Given a lab code in an older notation (CH6-01, Pac-01, ZM-03), when the report is read, then the matching RVL sample is proposed at "medium" with the reason "older notation".
- Given lines that need a person, when I open the report, then they are shown first.

**Status:** Done.

### US-09 · No guessing when evidence conflicts

Priority: **Must** · Requirements: FR-13, FR-14, NFR-02

As an inspector, I want a line to stay unlinked when the code and the place disagree, when two samples fit equally, or when the code is not registered, so that no convincing wrong link slips through.
- Given a code that exists but a place that fits another sample, when the report is read, then no link is proposed and the reason names both.
- Given a heavy-metals result on a chromium-6 code, when the report is read, then no link is proposed.

**Status:** Partly done; the result-fits-the-test check (second criterion) is still open.

### US-10 · AI help only where it is needed

Priority: **Should** · Requirements: FR-15, FR-16, NFR-06, NFR-08

As the product owner, I want the AI to look only at lines the rules cannot settle, and only with approved data, so that the AI cannot overrule clear evidence or leak client data.
- Given rules and AI that disagree, when the line is shown, then it says "rules and AI disagree" and has no link.
- Given an AI answer that is invalid or missing, when the report is read, then the rules' proposals stay and the AI adds nothing.

**Status:** Done; the AI is off by default and used only on fictional data.

## Epic 4 · Review and sign-off

### US-11 · Decide every line under my name

Priority: **Must** · Requirements: FR-17, FR-18, NFR-01

As an inspector, I want to approve, correct or reject each line, and change my decision later, so that I stay responsible for every link.
- Given a line, when I decide without entering my name, then the decision is refused and I am asked for my name.
- Given a decided line, when I choose "Change decision", then I can decide again and both decisions stay in the log.

**Status:** Done.

### US-12 · See what is missing

Priority: **Should** · Requirements: FR-20

As an inspector, I want missing photos, drawings, certificate numbers and samples without results flagged, so that I complete the report before signing.

**Status:** Done.

### US-13 · Sign the report

Priority: **Must** · Requirements: FR-21

As the Technical Responsible Person, I want to sign only when every line is decided, so that an unfinished report can never be delivered as final.
- Given open lines, when I try to sign, then signing is not possible.
- Given a signed report, when someone tries to change a decision, then it is refused.

**Status:** Done.

### US-14 · Practise reviewing

Priority: **Should** · Requirements: FR-22

As a quality reviewer, I want a practice report with hidden wrong links and a score, so that inspectors learn not to approve proposals blindly.

**Status:** Done.

## Epic 5 · Report and records

### US-15 · Download the IHM report

Priority: **Must** · Requirements: FR-23 to FR-26

As an inspector, I want the approved results filled into RVL's own IHM template, with a summary for this project, so that I do not copy tables by hand.
- Given approved lines, when I download the report, then cover, header, summary, Part I, the 2.3 sections, limitations and Tables 15 and 16 are filled and no placeholder is left.
- Given an approved PAH result, when I download the report, then it appears under "2.3.8 Other substances" and not in Table A or B.

**Status:** Done; RVL review of the output pending.

### US-16 · Trace every result

Priority: **Must** · Requirements: FR-27, FR-28, NFR-07

As a quality reviewer, I want to see which file, version, rule or AI reason and person led to each link, so that I can check or defend the report later.

**Status:** Done.

### US-17 · Compare with the previous survey

Priority: **Should** · Requirements: FR-29

As an inspector, I want approved results saved in the object's history, so that at the next survey I see what changed.

**Status:** Done.

### US-18 · Add photos

Priority: **Could** · Requirements: FR-30

As an inspector, I want to upload photos with each sample, so that the report shows them.

**Status:** Open.

## Epic 6 · Access

### US-19 · Shared access with a login

Priority: **Must** · Requirements: FR-31, NFR-09

As the product owner, I want a shared copy that only team members can open, so that the team, the coach and RVL can try it safely.

**Status:** Done (hosting on Render with a persistent disk; fictional data only).
