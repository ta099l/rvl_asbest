# Manual tests in the browser

No browser test tool is installed in the repo. Fictitious data only.

Start the app: `.venv/bin/python app/server.py` (Windows: `start_james.bat`), open http://127.0.0.1:8000.
Type a name in the **Inspector** field at the top before you approve, register or save anything.

## Navigation (18 Nov 2026: separate pages, URL keeps the project)

**Checked by script (18 Nov 2026):** headless Chrome on this laptop, driven step by step against a local server with an in-memory database, demo ship and demo reports only. 36 of 36 checks passed after one fix (see the 768 px item). A ticked box means the script checked it. A person still has to look at the items marked **you**.

- [x] Opening the app lands on **Projects** (`#/projects`), with the demo ship in the list.
- [x] Clicking a project opens its **Dashboard**, at the top of the page.
- [x] Choosing a project in the top-bar picker opens its Dashboard; "All projects…" goes back to the list.
- [x] The tabs are in this order: Dashboard, Upload, Intake, Desk research, Fieldwork, Lab results, Bronbladen, Report. The open tab is marked and has a coloured underline. **You:** check that it looks right.
- [x] **Lab results** shows a badge with the lab lines without a decision, over all reports of the project. It went from 9 to 8 after one decision.
- [x] On **Lab results**, a line scrolled to the bottom of a 700 px high window and approved stays exactly where it was (0 px moved; page scrolled down about 2,900 px).
  - The demo report has 9 lines, not 20. **You:** try it with a longer report, and with the mouse.
- [x] Typing a note on one line, then approving another line: the note is still there.
- [x] On **Fieldwork**, a half-typed sample survives going to Lab results and back.
- [x] On **Fieldwork**, **Edit** fills the form with that sample; **Cancel** empties it.
- [x] Browser **Back** and **Forward** move between the tabs you opened.
- [x] **Refresh** keeps the same tab, project and lab report (checked on the second demo report).
- [x] `#/p/1/nope`, `#/something` and an unknown project (`#/p/999/dashboard`) go to Projects.
- [x] **Two windows:**
  - Window 1 made a new project and registered a sample in it.
  - Window 2 stayed on the demo ship without that sample, and decided a line there.
  - Window 1 still showed its own project, also after a refresh.
- [x] **Intake:** a changed client is saved, stays after a refresh, is logged, and the lab report is **not** marked out of date.
- [x] **Report:** the report card, sign-off button and Download button are there. **You:** the download itself; the check ran without the template.
- [x] **Dashboard:** "History of this object" and "Audit log" start folded.
- [x] At **1280 px** and **768 px**, Dashboard, Intake, Fieldwork, Lab results and Report do not scroll sideways.
  - Fieldwork at 768 px failed at first: hidden column labels in the register table widened the page. Fixed with one CSS rule (`.tscroll { position: relative }`).
- [x] No script errors in either window during the run.

**Still for a person:**
- [ ] How it looks and feels with a real mouse, in your own browser.
- [ ] The downloaded .odt opens in Word or LibreOffice.
- [ ] With login on (`JAMES_USERS` set): log in, then repeat the two-window check.

## Fieldwork substance groups (18 Nov 2026)

**Checked by script (18 Nov 2026):** same setup as above, demo ship plus fictional codes. 11 of 11 checks passed.

- [x] Demo project, Fieldwork: tabs Asbestos 5, PCB 3, Heavy metals 1 and ODS 1. "Add group" offers PFOS / PFAS, HBCDD, Radioactive and Other.
- [x] Each tab lists only its samples and shows its report section (2.3.1, 2.3.2, 2.3.6).
- [x] "Add sample" pre-fills the next code: MM-6, PBS-3, HM-2 on the demo; MM-1 in an empty project; M13 after M12.
- [x] In one project, M12 lands in Asbestos, and HM12 and ZM-03 land in Heavy metals. A saved sample opens its own tab.
- [x] MI02 lands in Other with an "unknown code" mark. A warning naming it shows on every Fieldwork tab, with a link to Other. The Dashboard says "1 with an unknown code".
- [x] "Add group → PFOS / PFAS" shows an empty tab with next code PFOS-1 and section 2.3.4.
- [x] No horizontal page scroll at 768 px; no script errors.

**Still for a person:**
- [ ] How the group tabs look and read.
- [ ] Export a report and check one sample per group appears under the same 2.3.x section as its tab. A unit test covers this for the demo data; the real template was not used.

## Sources, photos, condition, saved AI proposals (18 Nov 2026)

**Checked by script (18 Nov 2026):** a database file made by the previous version (demo ship, a new project, 4 decisions) was opened by the new version in local headless Chrome. 22 of 22 checks passed.

- [x] Both projects are listed, and all 8 pages of both projects open.
- [x] The 4 old decisions are still there.
- [x] The report card's Source Records have a Condition row ("–" until a condition is set).
- [x] In the register form, Condition is disabled with "Enter a source number first" until a source number is typed.
- [x] The condition of an upgraded source can be saved and is shown again when you edit the sample.
- [x] No script errors.

**Still for a person:**
- [ ] Open your own `james.db` with the new version (make a copy first) and click through every page.
- [ ] Restart the app with `JAMES_AI_PROVIDER=groq`: a report read before the restart shows its proposals without a new "Groq usage" line in the console.
- [ ] Export a report and check the Condition line under each Source Record in Word or LibreOffice.

## Photos and the link check (19 Nov 2026)

**Checked by script (19 Nov 2026):** local headless Chrome, demo ship, 19 fictional images made in the page with the same names as `app/demo/make_demo_photos.py`. 13 of 13 checks passed.

- [x] The register form has no Photo field; the Photos panel shows the 8 known photo numbers as "Photo missing".
- [x] 19 photos upload one at a time with "Uploading 7 of 19"; the summary says "19 photos uploaded, 17 with a proposed link".
- [x] Thumbnails load (with the tab in front: the first check ran in a background tab, where Chrome does not load lazy images).
- [x] "Accept all proposals (9)" links 9 photos and fills their descriptions; 2 stay unlinked (an overview and the typo MI02).
- [x] A text file renamed to notes.jpg is refused with "please export it as JPG".
- [x] Bronbladen lists the issues (B01 with 5 photos, MI02 not linked, MM-9 not in the register, MM-1 and HM-1 differ only by prefix, ...).
- [x] Fix on "MI02 not linked" opens Fieldwork at that photo; linking it with the dropdown removes the issue.
- [x] "Mark as checked" removes the MM-1/HM-1 warning.
- [x] After approving HM-1, Fix on "no certificate number" opens that lab line; typing C-4471-07 removes the issue.
- [x] No horizontal scroll at 768 px; no script errors.

**Covered by unit tests, not in the browser:** 40 MB refused before reading, a duplicate skipped, a stalled upload not blocking another window, the photo route refusing another project and a missing login.

**Still for a person:**
- [ ] Use the real file picker: run `.venv/bin/python app/demo/make_demo_photos.py`, then on Fieldwork click **Upload photos** and pick all files in `data/demo_photos`.
- [ ] Upload a real (fictional) phone photo with GPS, download it with right-click → Open image in new tab, and check no location data is left (for example in Windows Properties → Details).
- [ ] Upload a 15 MB photo in one window and click around in another window meanwhile.
- [ ] Try an iPhone HEIC photo: expect "please export it as JPG".
