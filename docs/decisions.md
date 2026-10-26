# Decisions

One entry per decision: date, what, why, who agreed.

## 2026-10-26: Contract v1 for request and response (PROPOSED, waiting for Ivan)

- **What:** the request and response formats in `contract/` (schemas plus examples). The response is an object `{"proposals": [...]}`, not a bare list. Any broken answer turns every row into no link; a broken request raises an error.
- **Why:** an object can get new fields later without breaking the app. All-or-nothing rejection follows safety rule 4: a partly broken answer is not trusted for any line. Strict codes (exact spelling, must be in the register) follow rule 3.
- **Open point:** the v1 prompt (`ai/prompts/_output_format.txt`) still asks the model for a bare list, which this contract rejects. To be settled in Chunk 5 as a recorded prompt change, so v1 stays unchanged as the baseline for Appendix A.
- **Agreed by:** Tasnim (proposed). Ivan: not yet.

## 2026-10-26: Typed codes in the rule-based linker

- **What:** codes are read as prefix + number (`PBS 03` = `PBS3` = `PBS03`; `M12` is not `HM12`). Two new no-link rules: (A) the ID exists but a same-number, other-prefix sample fits the description better (`M12` vs `HM12`); (B) an unknown but well-formed code of a prefix family the register uses (`OS02` next to `OS01`), or one whose description points to a same-number, other-prefix sample, is not guessed from the description.
- **Why:** safety rule 2. A prefix marks a different test, so a prefix mismatch is conflicting evidence. dev2 went from 2 wrong links to 0.
- **Cost:** dev2 case e11 (`M3`, reference `M02`) is now a missed link instead of correct. Its reference answer contradicts e7 (`OS02`, reference no link), which has the same pattern. Ask Rolf which is right for real reports.
- **Agreed by:** Tasnim (owner of `ai/`).

## 2026-10-26: Answer format follows the contract; replay answers are tied to the exact prompt

- **What:** `ai/prompts/_output_format.txt` now asks for `{"proposals": [...]}` instead of a bare list. Only the shape changed, not the wording; `v1_baseline.txt` is unchanged. Replayed answers are stored under a key computed from the exact prompt text (`python3 -m ai.james_ai.ai_step prompt <request.json>` shows it).
- **Why:** with the old format every v1 answer broke the contract and became no link. The key makes sure an answer recorded for one prompt version is never reused for another, so each result in Appendix A belongs to the prompt that produced it.
- **Note:** prompt-lab answers recorded in the old list format before this change would be rejected; record them again with the new format.
- **Agreed by:** Tasnim (owner of `ai/`).

## 2026-10-26: Hybrid pipeline, rules first and AI second

- **What:** high-confidence rule links and rule no-links caused by conflicting evidence (conflict, duplicate, prefix conflict, collision, unregistered code) never go to the AI. All other lines go to the AI in one request. Rules and AI agree: link stays. They disagree: no link. Only the AI links: the AI's proposal. AI answer unusable: the rules' proposal stays. Guard: a sample proposed for two lines unlinks both.
- **Why:** the AI should only work where the rules are unsure, and two sources that disagree are conflicting evidence (safety rule 2). The AI cannot make contradicting evidence agree.
- **Also:** an unknown code of a prefix family the register uses (S-09 next to S-01..S-08) is now always flagged `unregistered`, so the AI never links it either.
- **Status:** no recorded AI answers yet, so the AI and hybrid numbers are not yet meaningful. Fill `ai/replays/dev_v1.json` and `dev2_v1.json` from the prompt lab.
- **Agreed by:** Tasnim (owner of `ai/`).

## 2026-10-26: An unregistered code gets no link, even if the description matches (e11 changed)

- **What:** the reference answer of dev2 case e11 (`M3 | Gasket, boiler door`) is now `null` instead of `M02`. Rule: a lab code that reads as a proper code (prefix + number) of a prefix family the register uses, but is not in the register, gets no link, even when the description fits a registered sample.
- **Why:** M3 next to M01 and M02 most likely is a sample nobody registered, not a typo for M02. Linking it would hang a result on the wrong sample (safety rule 2). e7 (`OS02`) already had this reference, so the two cases now agree. Supersedes the "Cost" note of the typed-codes entry above.
- **Exception, on purpose:** codes from another numbering system (a lab's own `GS15`, `XY7`) and malformed codes (`S-O3`) can still be matched on the description, at low confidence, because they say nothing about our register.
- **Effect:** dev2 rules 8 / 0 / 2 / 1 (correct / wrong / abstained_ok / abstained_missed), was 8 / 0 / 1 / 2.
- **Agreed by:** Tasnim. Still worth confirming with Rolf for real reports.

## 2026-10-26: Survey location belongs to a survey, not to the object (PROPOSAL for Ivan)

**Status:** proposed by Tasnim, waiting for Ivan. Nothing in `schema.sql` or `store.py` is changed until he agrees.

### The problem
Today `object.site` and `object.project` hold one port and one project per ship. But one ship can be surveyed in Rotterdam in 2026 and in Antwerp in 2027, under two RVL projects, with two sets of samples and lab reports. With one `site` on the object, the second survey overwrites where the first one happened, and the last link of the chain (`... -> object -> survey location`) points to the wrong place for old results.

### The proposal
A new table `survey`: one visit to one object, at one place, in one period, under one project. Samples and lab reports belong to a survey; the object only says *what* it is.

```sql
CREATE TABLE survey (
    id          INTEGER PRIMARY KEY,
    object_id   INTEGER NOT NULL REFERENCES object(id),
    project     TEXT NOT NULL,            -- RVL project code (moves here from object)
    site        TEXT NOT NULL,            -- port, shipyard, quay, road km (moves here from object)
    started_on  TEXT NOT NULL,            -- ISO date of the first survey day
    ended_on    TEXT,                     -- NULL while the survey is open
    inspector   TEXT NOT NULL             -- lead inspector, by name
);

-- object: drop site and project
CREATE TABLE object (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL,
    kind  TEXT NOT NULL,
    ref   TEXT                            -- IMO number, object code
);

-- sample: belongs to a survey; a code is unique within its survey
CREATE TABLE sample (
    survey_id INTEGER NOT NULL REFERENCES survey(id),
    code      TEXT NOT NULL,
    source    TEXT, location TEXT NOT NULL, part TEXT, material TEXT, notes TEXT, photo TEXT,
    PRIMARY KEY (survey_id, code)
);

-- lab_report: belongs to the survey whose samples it analyses
--   object_id INTEGER NOT NULL REFERENCES object(id)   becomes
--   survey_id INTEGER NOT NULL REFERENCES survey(id)
```

`lab_row`, `decision`, `asset_version` and `asset_entry` stay as they are; `asset_version.object_id` stays, because the asset file is the object's history over all surveys. The chain becomes `result -> lab_row -> sample -> survey -> object`, and the survey location is `survey.site` on `survey.started_on`.

### What changes in `store.py` (for Ivan to decide how)
- `add_object(name, kind, ref, site, project, samples)` splits into `add_object(name, kind, ref)` and `add_survey(object_id, project, site, started_on, inspector, samples)`.
- `ingest_report` takes a `survey_id`; the project check in the report header compares with `survey.project`.
- `register(...)` returns the samples of one survey; `draft_report` shows the survey's site and date.
- Existing data: one survey per object, filled from the old `object.site` and `object.project`.

### Questions for Ivan (and Rolf)
1. **Do sample codes restart per survey?** If S-01 in Antwerp 2027 is a new sticker, the key must be `(survey_id, code)` as above, and the asset history cannot follow a sample by code alone across surveys. It would then follow the *place in the object* (source/location) instead. Is that how RVL compares results over time?
2. Can one survey span two places (start in port, finish at the shipyard)? If yes, `site` needs its own small table.
3. Is the RVL project always one survey, or can one project cover several visits?
4. Who is the "inspector" of a survey: the lead only, or everyone who took samples?

### Effect on the AI part (Tasnim)
None on the contract: the app already sends one register per request, which will simply be the register of one survey.
