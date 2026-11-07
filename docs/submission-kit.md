# ClearPath submission kit

Write-up, demo script and video plan for the 2:30 PM submission (Lane 2, Clear it).

Everything in `[BRACKETS]` must be replaced with what the running app actually shows. Do not
fill a bracket with a number, fee, form name or deadline that the app or a checked source does
not show. If the build cuts a feature, cut its line from the script and from the write-up.

---

## 1. Submission form answers

**Lane:** 2 Clear it

**One-liner**

> ClearPath gives a nonprofit project manager or first-time ADU builder a cited, step-by-step
> permit checklist and timeline for each project, starting with ADUs in Irvine, and says
> "unknown" instead of guessing.

**The real user, before and after**

> A nonprofit housing project manager juggling several small projects, or a homeowner adding
> their first ADU in Irvine. Today they piece the process together from the city's ADU page,
> a 2025 application package PDF, a separate development standards checklist, forms that
> Planning hands out, and the state HCD ADU Handbook. Nothing tells them which items apply
> to their project, what is still missing, or what step comes next.
>
> Before: open a dozen tabs, guess which forms apply, find out at the counter what was missed.
>
> After: answer four questions about the project and get the city's own checklist, each item
> linked to the page and passage it came from with the date we checked it. Items that depend
> on facts they have not given yet are marked "needs information" instead of guessed. They
> track each document and each approval step per project, and see what is blocking them.

**What it does**

> 1. Lookup: pick Irvine and answer the project facts (ADU form, existing house yes/no,
>    floor area, which can be left unknown).
> 2. Checklist: every requirement is sorted into applies / needs information / not
>    applicable, with a citation chip showing the source URL, page, exact excerpt and date
>    checked.
> 3. Warnings: shows when a source cites renumbered law (old Gov Code 65852.2, now
>    66310 to 66342), when two sources disagree, and when the property itself has not been
>    verified.
> 4. Tracker: save the project, mark documents not started / in progress / ready, and move
>    through six approval steps (preparation, submission, completeness review, plan review,
>    fees, permit issued). The app refuses out-of-order steps.
> 5. Timeline: progress, next actions, and what is holding the project up. Any time estimate
>    is labeled ASSUMPTION, or the app says "no estimate available".
> 6. Portfolio: several projects side by side. Housing types we have not sourced yet are
>    saved as drafts marked "rule coverage unavailable" rather than given a made-up checklist.
>
> Rules live in a reviewed data file with citations, not in code, so adding a city or a
> project type is a data task.

(Trim items 4 to 6 to what actually shipped.)

**Sources and assumptions**

> City of Irvine: ADU construction guide page; ADU application package (2025 update);
> Development Standards Checklist (Form 67-01); Hold Harmless Affidavit (Form 67-02);
> Pre-Approved ADU Plans page (plan list says "coming soon", so we list no plans);
> official city boundary GIS layer. State: HCD ADU Handbook (March 2026 update), which cites
> Gov Code 66317 for completeness and decision timing. We could not open the statute text on
> leginfo, so the app shows that clock as guidance and does not calculate legal due dates.
> All sources checked November 7, 2026.
>
> Assumptions: the four-year baseline and the $85k-of-$535k time cost come from the event
> brief's rounded example (timeline.json) and are labeled ASSUMPTION. [List any per-step day
> ranges the team added, each labeled ASSUMPTION, or write "No duration estimates; the app
> shows none."] The demo project is a made-up scenario (C01), not a real applicant.

**Public repo URL:** `https://github.com/Arthur-Systems/claude-impact`

**Video:** upload the MP4 on the form. Backup: YouTube unlisted link.

**Live demo URL:** [optional, only if deployed]

---

## 2. README sections to fill in

Paste into `README.md` in place of the "To be confirmed" and empty sections. Keep each one
matched to what shipped.

### Header

```
**Team:** [team name on the hub]
**Members:** [names]
```

### What we built

> ClearPath turns a city's scattered ADU guidance into one cited checklist and approval
> tracker per project. [Screenshot: checklist with a citation chip open.]
>
> **Demo video:** uploaded on the event hub [and YouTube link]
> **Live demo:** [link or "run locally, see Try it"]

### How Claude is used

> - Building: Claude (Claude Code) wrote the backend design spec, the ADU packet builder, the
>   rule engine and API, and the frontend, and drafted this README and the demo script. A
>   teammate checked every requirement and citation against the source page by hand.
> - Running: [Choose one and delete the other.]
>   - The checklist, citations and timeline work with no AI key. Claude is not in the
>     runtime path.
>   - Claude explains a cited requirement in plain language. It only sees the stored
>     passage, and the answer shows the same citation. A person checks the source before
>     relying on it.

### Sources and assumptions

| Item | Source or assumption | Date checked |
|---|---|---|
| Irvine ADU process and document links | [City of Irvine ADU construction guide](https://cityofirvine.gov/building-permits-and-inspections/project-constructing-accessory-dwelling-unit-adu) | 2026-11-07 |
| ADU application package | [Irvine ADU application package, 2025 update (PDF)](https://cityofirvine.gov/sites/default/files/legacy-documents/civica-34716-adu-application-package_updated-2025.pdf). Text extraction is garbled; excerpts were typed and checked by page | 2026-11-07 |
| Development standards | [Irvine Form 67-01 (PDF)](https://cityofirvine.gov/sites/default/files/legacy-documents/civica-35890-67-01.pdf) | 2026-11-07 |
| Hold harmless affidavit | [Irvine Form 67-02 (PDF)](https://cityofirvine.gov/sites/default/files/legacy-documents/civica-35928-67-02.pdf) | 2026-11-07 |
| Pre-approved plans | [Irvine pre-approved ADU plans page](https://cityofirvine.gov/building-permits-and-inspections/pre-approved-adu-plans-program): list says "coming soon"; no plans seeded | 2026-11-07 |
| City boundary | [Irvine CityBoundary GIS layer](https://gis.cityofirvine.org/arcgis/rest/services/CityBoundary/MapServer/0) | 2026-11-07 |
| State ADU guidance | [HCD ADU Handbook, March 2026](https://www.hcd.ca.gov/sites/default/files/docs/policy-and-research/adu-handbook-update.pdf) | 2026-11-07 |
| Completeness / decision clock | Gov Code 66317 per HCD Handbook. Statute text not opened (leginfo blocked); shown as guidance, no due-date math | 2026-11-07 |
| ADU law renumbering | Gov Code 65852.2 renumbered to 66310 to 66342 (event data sources note) | 2026-11-07 |
| Four-year baseline, $85k time cost | ASSUMPTION: event brief's rounded example, `lanes/2-clear-it/data/timeline.json` | n/a |
| Per-step durations | [ASSUMPTION with basis, or "none; app shows no estimate"] | n/a |
| Demo project | Made-up scenario C01, `lanes/2-clear-it/scenarios.json` | n/a |

### What is real and what is mocked

| Part | Status |
|---|---|
| Irvine detached ADU checklist and citations | [working] |
| Requirement status (applies / needs information / not applicable) | [working] |
| Project tracker and step order enforcement | [working / partly working] |
| Timeline progress, next actions, bottlenecks | [working / partly working] |
| Finish-date forecast | [mocked with labeled synthetic estimates / cut] |
| Address lookup | [selected-area mode only: property not verified] |
| Other cities and project types | Not covered. Saved as drafts with "rule coverage unavailable" |
| ADU submittal packet PDF | Abbreviated test sample, not an official Irvine form |
| Claude explanations | [working / not built] |

### Where it gets things wrong

> - It only knows what we typed in from Irvine's public pages on November 7. If Irvine
>   changes a form tomorrow, the checklist is stale until someone re-checks the source.
> - It does not check a real parcel: zoning, lot size, easements, HOA rules and utility
>   capacity are not looked up. "Selected area" results say "property not verified".
> - It does not calculate legal deadlines. We could not open the statute text, so the state
>   clock is shown as guidance only.
> - Facts outside our four questions (lot coverage, height, fire zone) are listed as gaps,
>   not answered.
> - Not legal advice. Confirm with the City of Irvine or a professional.

### Next steps

> Next month: a nonprofit could use the Irvine ADU profile as is, and a city permit tech
> could use the citation view to check a form against state guidance. For the next 100
> projects: each new city or project type is one reviewed data file (sources, excerpts,
> rules, steps), checked by a person, with no code change. With one more week: SB 9
> two-unit and lot-split profiles for Irvine, two more OC cities so a project manager can
> compare them (scenario C02), and HCD Annual Progress Report data to show how long
> permits really take in each city, with the data's limits stated.

---

## 3. Demo video plan

**Target length:** 60 seconds (the hub says 30 is ideal, 2 minutes max). A 30-second cut is
below. Record at 2:00 PM, upload by 2:20 PM.

**Who does what:** Person 1 drives the screen. One voice reads the narration (whoever reads
most clearly; record voice separately if the room is loud). One person checks the bracketed
values against the screen before recording.

**Setup before recording**

- Seed the C01 demo project fresh so the checklist starts at "not started".
- Browser zoom at 125 to 150% so text is readable in a phone-sized video. Hide bookmarks,
  other tabs, notifications and any terminal with keys or env vars.
- Leave floor area blank on purpose so "needs information" shows up.
- Screen recorder: macOS `Cmd+Shift+5`, record selected portion, 1080p. Mic: a phone held
  close in a quiet hallway gives cleaner audio than a laptop mic in the room.
- Do 1 rehearsal, then 2 takes. Keep the better one. No editing beyond trimming the ends.

### 60-second script

| Time | Screen | Narration |
|---|---|---|
| 0:00 to 0:07 | Irvine ADU page, application PDF and HCD handbook open in three tabs | "Adding an ADU in Irvine means piecing together a city web page, a long PDF package, separate checklists and the state handbook." |
| 0:07 to 0:15 | ClearPath start screen; choose Irvine, detached ADU, existing house yes, floor area left blank | "ClearPath asks four questions. We'll leave floor area blank, because a lot of people don't know it yet." |
| 0:15 to 0:28 | Checklist appears. Click one citation chip; show URL, page, excerpt, date checked | "Every item is the city's own requirement, linked to the exact page and passage, with the date we checked it." |
| 0:28 to 0:36 | Scroll to the "needs information" group | "Items that depend on floor area say needs information. It does not guess." |
| 0:36 to 0:44 | Warnings bar: stale citation or source conflict, plus "property not verified" | "It flags when a source cites old law. ADU law moved from section 65852.2 to 66310 and up, and some documents still use the old numbers." [Use only if the app shows a real flagged item. Otherwise say: "It tells you what it hasn't verified."] |
| 0:44 to 0:54 | Save project; mark two documents ready; try to complete plan review early and show the "complete the earlier step first" message; timeline shows progress and next action | "Save it as a project, track each document, and it keeps the steps in order and tells you what's next." |
| 0:54 to 1:00 | Portfolio view with the ADU project and a draft project, plus repo URL on screen | "Each new city or project type is a reviewed data file. ClearPath, Lane 2." |

### 30-second cut

Use rows 0:07 to 0:36 plus the last row, with this narration:

> "ClearPath turns Irvine's scattered ADU rules into one checklist. Four questions, and every
> item links to the exact city page and passage, with the date we checked it. Anything that
> depends on facts you haven't given says needs information instead of guessing. Each new city
> is a reviewed data file. ClearPath, Lane 2."

---

## 4. Live finalist demo (3:00 PM, about 3 minutes)

Run on the presenter's laptop against the local stack started before walking to the
auditorium. Keep the recorded video open in another tab as a fallback if the stack fails on
stage. Say "here's the recording of the same flow" and play it.

1. **The user (20 s).** "Picture a nonprofit project manager with four small projects, one of
   them a backyard ADU in Irvine. The fast, ministerial path exists, but the forms that
   describe it are spread over a web page, a PDF package, separate checklists and the state
   handbook."
2. **Lookup (25 s).** Enter the C01 facts and leave floor area blank. "Four facts. We left
   floor area blank on purpose."
3. **Checklist and sources (40 s).** Open a citation chip. Read the excerpt aloud. "Every item
   shows where it came from and when we checked it. If we can't cite it, it doesn't appear."
   Point at "needs information".
4. **Honesty layer (25 s).** Warnings bar. "Property not verified, because we only chose the
   city. The state completeness clock is shown as guidance: we couldn't open the statute text
   today, so the app doesn't compute a legal deadline."
5. **Tracker (35 s).** Mark documents ready, start a step, try an out-of-order completion,
   show the refusal, show progress and the next action.
6. **Scale (25 s).** Portfolio with a draft project marked "rule coverage unavailable". Open
   the data file briefly. "A new city is this file: sources, excerpts, rules, steps, reviewed
   by a person. No code change. Next is SB 9 in Irvine and two more OC cities, so a project
   manager can compare where the ministerial path is faster."
7. **Close (10 s).** "ClearPath. Cited, honest about what it doesn't know, and ready for a
   nonprofit to try on its next ADU."

**Likely judge questions**

- *Where do the rules come from?* Irvine's public pages and PDFs, typed in and checked by
  hand on November 7, each with a stored excerpt.
- *What happens when Irvine changes a form?* The source is dated and hashed. Re-checking it
  flags the change; until a person reviews it, the item shows as stale.
- *Why not let Claude read the PDFs and answer directly?* A confident wrong answer costs a
  resubmittal. Claude helped build and extract; a person approves every rule that ships.
- *How do you get to 100 projects?* Projects are cheap once a city/type profile exists. The
  work is profiles, and one profile covers every project of that type in that city.
- *Does it know if my lot qualifies?* No. It does not check zoning, lot size or easements
  yet, and it says so.

---

## 5. Final 2:20 PM checklist

- [ ] Every bracket above replaced or its line deleted.
- [ ] README "Try it" commands run on a fresh clone.
- [ ] `.env.example` has variable names only; no keys in history (`git log -p | grep -i key`).
- [ ] Repo public; main page opens in a private window.
- [ ] Video plays; under 2 minutes; no tabs or terminals showing secrets.
- [ ] Form submitted with the registered team email.
