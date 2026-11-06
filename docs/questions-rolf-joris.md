# Questions for Rolf and Joris (test round 1, week of 2 November 2026)

Each question blocks a test case or a KPI. Write the answer and the date next to it.

| # | Question | Why we ask | Blocks |
|---|---|---|---|
| 1 | Which sample code notation is real: `M01` or `MM01` for asbestos, `CH6-01` or `CR601` for chromium-6? | Two RVL documents disagree: the work process says `M00`, the IHM template says `MM00` (and `CR600`). The repo uses `M` and `CH6`, Harm's test cases `MM`. The linker treats the prefix as the test type, so this changes what counts as a match. | TC01, TC03, TC04, K2 |
| 2 | Are the thresholds in `app/thresholds.json` right? The template says lead 100 mg/kg, we read 1000 mg/kg in MEPC.379(80): which one? PFOS has a section 2.3.4 but no line in Table A or B: where does it go? | The Table A/B proposal depends on them. | TC05, TC06, K6 |
| 3 | A value exactly on the threshold: listed or not? | The app lists it and flags it for the inspector. | TC05 |
| 4 | Is the RVL IHM template (Part I, 2.3, 3, 5.1) leading, and the Lloyd's 13-chapter list only a checklist? | The app follows the RVL template. | K6, Ch. 9 of the portfolio |
| 5 | How is a place that could not be sampled written in the field registration? What reason codes are used? | The app needs it to put the place under survey limitations as PCHM. | TC08 |
| 6 | How do labs write numbers: `1,400` or `1.400` or `1400`? Is it fixed per lab? | Ambiguous numbers go to the inspector now. If each lab has a fixed style, the app could read it per lab. | K1 |
| 7 | Does every lab line carry a certificate number, or one per report? | The completeness check flags a lab line without one. | TC07, K7 |
| 8 | How is the I-1 / I-2 / I-3 list decided in practice? | The app proposes it from the part and material. | K6 |
| 9 | How long does processing one lab report take now, by hand? | Baseline for K5 (≥ 50% faster). | TC09, K5 |
| 10 | May anonymised real lab reports be used, and with which AI tool? | Until then everything stays fictitious. | Safety rule 6 |
| 11 | Who processes lab reports today: the inspector, office staff, or both? Does a second person (quality reviewer) check before the report goes out? | The onboarding names office and quality staff as users and a quality reviewer for acceptance; the app now has one person who decides and signs. | Sign-off design, K10 |
| 12 | Which fields does the inspector fill in per source and sample during fieldwork, and how are drawing positions recorded? | Success criterion 1 starts at field registration; the app does not have it yet. | Field registration screen, K7 |
| 13 | Is the Technical Responsible Person always someone else than the surveyor? Must the app enforce that? | The template has both roles; the app now signs as Technical Responsible Person but does not check it is a different person. | Sign-off, K10 |
| 14 | Should a source with only a visual assessment (V00, marking, document) be registered without a lab sample? | The template has assessment methods besides lab analysis; the app now treats every registered sample as sampled or not sampled. | TC08, K6 |

## Answers from Rolf (6 November 2026)

| # | Answer | What we did with it |
|---|---|---|
| 1 | Standard = the English abbreviations of the IHM report: MM, KM, PBS, SS, OS, ODS, PFOS, HBCDD, HM, CR6, PAH, TBT, PFAS, NORM, TPH, VOC, plus VI (visual inspection), DR (document review), EI (equipment identification). Written with a dash and without leading zeros: `MM-1`, `CR6-1`, `HM-1`. Older codes such as `CH6-01`, `ZM-01` and `Pac-01` must stay recognisable. The original sample code on the lab certificate is always kept. | Alias table in the linker (CH6 → CR6, PAC → PAH, M → MM), new test set `dev3` in the standard notation. See `docs/decisions.md`, 6 Nov 2026. |
| 6 | Not at this stage: each laboratory has its own classification system and analytical methods. | Ambiguous numbers keep going to the inspector; no per-lab reading. |
| 9 | About 4 to 8 hours of reporting work per project once the results are in; longer for large IHM surveys. | Baseline for K5: 50% faster means 2 to 4 hours. |
| – | Reporting software: Microsoft Word. | The export is .odt, which Word opens. Check with Ivan whether .docx is needed. |
| – | Volume: hard to predict; assume 10 to 25 reports per month. James should later also cover asbestos surveys, chromium-6 assessments and other hazardous substances. | Input for the monthly cost estimate (multi-criteria analysis). |

Still open: 2, 3, 4, 5, 7, 8, 10 (which AI tool), 11–14, and:

| # | Question | Why we ask | Blocks |
|---|---|---|---|
| 15 | Which substance does the older code `ZM` stand for? | It must stay recognisable, but we cannot map it without knowing what it means. | Alias table |
| 16 | Do VI, DR and EI codes ever appear on a lab certificate, or only in the field registration? | They are assessment methods without a lab analysis. | Linker, TC08 |
