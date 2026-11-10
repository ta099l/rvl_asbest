# Glossary

Every term used in this project, in one plain sentence with an everyday comparison. Kept up to date with each new term.

## The work itself

| Term | What it means | Like... |
|---|---|---|
| **Register** | The inspector's list of samples for one object: code, location, material, colour. | The guest list at a party. |
| **Sample code** | The code on the sticker of a sample, e.g. `S-02`, `M12`, `PBS03`. | A cloakroom ticket number. |
| **Prefix** | The letters in front of a code that say which test it is (`M` asbestos, `HM` heavy metals, `PBS` PCB). | The department on a hospital wristband. |
| **Lab line** | One result line from the lab report: ID as the lab wrote it, description, result. | A returned parcel with a handwritten label. |
| **Link** | The connection between one lab line and one sample in the register. | Matching a coat to its cloakroom ticket. |
| **Proposal** | A link the system suggests; it is never final until an inspector decides. | A spell-checker's suggestion: you still click "accept". |
| **No link (abstain)** | The system deliberately proposes nothing, with a reason. | A shop assistant saying "I'm not sure, let me ask" instead of guessing. |
| **Inspector decision** | A named person approves, corrects or rejects a proposal. | A doctor signing a prescription. |
| **Audit log** | The list of every decision: who, what, when. Nothing is ever deleted. | A ship's logbook. |
| **Append-only** | New entries are added; old ones are never changed or removed. | Writing in pen in a notebook: you add a correction, you don't erase. |
| **Draft report** | The overview of linked results plus the open items still to decide. | A to-do list with the finished items ticked. |
| **Asset file** | The object's history of approved results over time, in versions. | A car's service book. |
| **Survey** | One visit to one object at one place and time (proposal for Ivan). | One appointment in a patient's medical file. |

## How we link

| Term | What it means | Like... |
|---|---|---|
| **Rule-based linker** | Code with fixed rules (compare codes, count matching words); no AI. | A recipe followed step by step. |
| **Normalise** | Make two spellings comparable: `S02`, `s-02`, `S 02` all become `S|2`. | Ignoring capitals and spaces when you compare names. |
| **Confidence** | How sure a proposal is: high (exact code, text agrees), medium (code tidied up), low (text only). | Weather forecast: "sure", "likely", "maybe". |
| **Conflicting evidence** | The code says one sample, the description another. We then propose no link. | Two witnesses telling different stories. |
| **Prefix conflict** | `M12` written, but the text fits `HM12`: same number, another test. No link. | Two flats, 12A and 12B: same number, different door. |
| **Unregistered code** | A proper code (like `OS02`) that is not in the register. No link, even if the text fits. | A ticket number the cloakroom never handed out. |
| **Standard notation** | RVL's agreed way to write a sample code: IHM prefix, dash, no leading zeros (`MM-1`, `CR6-1`). Set by Rolf on 6 Nov 2026. | The official spelling of a street name. |
| **Alias table** | A short list "old name → standard name" (`CH6` → `CR6`, `PAC` → `PAH`, `M` → `MM`). A match through it is at most medium confidence. | A street that was renamed: the old name still gets you there, but the postman double-checks. |
| **OCR** | Optical character recognition: turning a picture of text (a scanned PDF) into real text the computer can read. | Retyping a photographed page. |
| **Token** | The unit a language model reads and is billed in: a piece of a word, roughly ¾ of an English word. | Paying per syllable instead of per page. |
| **AI (language model)** | A program that writes text answers to text questions, trained on a lot of text. | A very well-read assistant who sometimes confidently gets things wrong. |
| **Prompt** | The exact text we send to the model: the task, the register, the lab lines, the answer format. | The instructions you give that assistant. |
| **Prompt version** | One saved wording of the prompt (`v1_baseline`); a change makes a new version. | Drafts of an essay: v1, v2, v3. |
| **Template** | A prompt with blanks (`{{REGISTER}}`, `{{LINES}}`) filled in per report. | A form letter with "Dear ___". |
| **Client** | The small piece of code that talks to the model; one method, `complete(text)`. | A phone: you can swap the phone without changing what you say. |
| **Stand-in** | A fake client used until the real AI is approved. | A rehearsal actor before the star arrives. |
| **Replay** | A stand-in that gives back answers you recorded earlier in the prompt lab. | Playing a voicemail instead of calling. |
| **Prompt lab** | A chat window where you paste a prompt by hand and copy the answer. | A test kitchen before the restaurant opens. |
| **Fingerprint (key)** | A short code computed from the exact prompt text; one changed letter gives another key. | A fingerprint: it identifies exactly one person. |
| **Hybrid** | Rules first; only lines the rules cannot settle go to the AI. Disagreement means no link. | A junior colleague who only asks the expert about the hard cases. |
| **Guard** | A final check: one sample can be linked to only one line. | A cinema seat can't be sold twice. |
| **API** | The official way for one program to call another over the internet (for the real model later). | A restaurant's order counter. |

## How we check

| Term | What it means | Like... |
|---|---|---|
| **Test** | A small program that checks one behaviour automatically and says OK or FAIL. | A smoke alarm test button. |
| **Test case** | One lab line with the correct answer an inspector would give. | One exam question with its answer key. |
| **Reference answer (truth)** | That correct answer; `null` means no sample is right. | The answer key. |
| **Correct / wrong** | The proposal matches / does not match the reference. Wrong is the worst outcome. | Right or wrong answer on the exam. |
| **Abstained ok / missed** | No link, and none existed / no link, but one did exist (the inspector links by hand). | Leaving a question blank when there was no answer / when you could have known. |
| **Baseline** | The score of the simplest approach (rules only) that anything new must beat. | Your time on the first run, before training. |
| **dev / dev2 set** | Test cases we may look at and improve against. | Practice exams. |
| **Hold-out set** | Test cases kept aside; used once per final version, never to tune. | The real exam: you don't see it before. |
| **Run record** | A saved result of one scoring run, with time and commit. | A dated lab measurement in a notebook. |
| **Iteration log** | Generated overview of all prompt versions and their results (Appendix A). | A training diary. |

## The IHM report (added 27 Oct 2026, app build)

| Term | What it means | Like... |
|---|---|---|
| **Certificate number** | The number of the lab certificate a result comes from; the last link in the chain sample → result → certificate. | The receipt number that proves where a purchase came from. |
| **Analysis method** | How the lab tested the sample, e.g. NEN 5896 for asbestos. | The recipe a cook followed. |
| **Deck level** | Which deck of the ship a sample comes from; its own column in the IHM report. | The floor number in an office building. |
| **Threshold** | The value above which a material must be listed in the IHM (for example lead 1000 mg/kg). In `app/thresholds.json`, still to confirm by RVL. | A speed limit: below it nothing happens, above it you get a ticket. |
| **Table A / Table B** | The two IHM lists: A for banned materials (asbestos, PCB, ODS, ...), B for restricted ones (lead, cadmium, ...). | A list of forbidden items and a list of items you must declare at customs. |
| **Part I lists (I-1, I-2, I-3)** | Where a hazardous material sits: I-1 paints and coatings, I-2 equipment and machinery, I-3 structure and hull. | Sorting a moving inventory into furniture, appliances and the house itself. |
| **Survey limitation** | A place the inspector could not reach or sample, with the reason. | A "could not inspect: locked" note in a house survey. |
| **PCHM** | Potentially Containing Hazardous Materials: a place that was not sampled is treated as possibly hazardous, never as clean. | Treating an unopened parcel as fragile because you cannot see inside. |
| **Not sampled** | Register status for such a place. No lab result may ever be linked to it. | A guest on the list who sent apologies: nobody may sit in their chair. |
| **Completeness check** | The flags for what is missing: a result, a photo, a certificate number. | A checklist before handing in a form. |
| **Sign-off** | The inspector signs the report sections once every lab line is decided. After that, decisions are locked; open items are recorded with the signature. | Signing a delivery note: you note the dents, then sign. |
| **Practice review (seeded errors)** | A copy of a report with deliberately wrong proposals, to measure whether the reviewer really checks (TC12, K10). | A fire drill: a fake alarm to see if people follow the procedure. |
| **Automation bias** | People trusting a system so much that they stop checking it. | Following the sat-nav into a lake. |
| **Processing time** | Minutes from reading a lab report to the last decision (K5). | A stopwatch on a pit stop. |
| **Ambiguous number** | "1,400" is 1400 in English and 1.4 in Dutch; the app does not guess and hands it to the inspector. | A date like 03/04: March or April? |
| **Source (bron)** | One place where a material is applied, e.g. "gasket at flange B03". A sample belongs to a source; a source has a quantity. | A room in a house; the sample is the paint chip you took from it. |
| **Source Record** | The block per source in section 2.3 of the IHM report: description, sample, certificate, location, material, result, quantity, conclusion. | An index card per item in a museum. |
| **Technical Responsible Person** | The person who signs the IHM report on behalf of James; in the template this is a separate role from the surveyor. | The head chef who checks every plate before it leaves the kitchen. |
| **VSCP** | Visual/Sampling and Check Plan: the plan made before fieldwork of what to check and sample, where and how. | A packing list made before a trip. |
| **Register log** | The append-only list of every change to the field registration, with name and time. | Track changes in a shared document. |
| **SHA-256 fingerprint** | A code computed from the exact bytes of a file; one changed letter gives a completely different code. | A fingerprint: it proves which file it was, without storing the file again. |

## Tools

| Term | What it means | Like... |
|---|---|---|
| **JSON** | A text format for structured data: `{"sample": "S-02"}`. | A neatly filled-in form. |
| **Schema** | Rules for what valid JSON looks like (which fields, which values). | The rules printed on the form: "date in DD-MM-YYYY". |
| **Contract** | The agreed request and response format between Ivan's app and the AI part. | A delivery agreement: what is sent, what comes back. |
| **Validation** | Checking an answer against the contract; anything broken becomes no link. | Customs checking a parcel against its papers. |
| **Repository (repo)** | The project folder with its full history. | A binder with every version of every page. |
| **Git** | The tool that keeps that history. | The binder's librarian. |
| **Commit** | One saved snapshot with a message saying what changed. | A dated entry in a diary. |
| **Branch** | A separate line of work (`tasnim/ai`) that does not touch `main`. | A copy of the essay you edit without touching the handed-in version. |
| **Virtual environment (.venv)** | A private Python install for this project only. | A separate toolbox for one job. |
| **Command line / terminal** | The text window where you type commands. | Texting the computer instead of clicking. |
