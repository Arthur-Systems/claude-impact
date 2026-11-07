# ClearPath submission kit

Write-up, demo script and video plan for the 2:30 PM submission (Lane 2, Clear it).

Every value below matches the running app and the reviewed Irvine data on main. If a feature
changes before recording, cut its line from the script and the form answers; never add a
number, fee, form name or deadline that the app or a checked source does not show.

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
> After: open ClearPath for a detached ADU next to an existing house in Irvine and get the
> city's own list of 10 requirements, each linked to the page and passage it came from with
> the date we checked it. Where the city's own sources disagree, the item says "needs
> information" and shows both sources instead of guessing. The project timeline shows the six
> approval steps in order, who acts at each step (city or applicant), and what is holding the
> project up.

**What it does**

> 1. Checklist: the city's requirements for the project, each marked applies / needs
>    information / not applicable, with a source chip showing the source title, link, exact
>    excerpt and date checked.
> 2. Conflicts and stale law: shows where sources disagree (for example the order of fee
>    payment and plan review, or whether the Hold Harmless Affidavit applies) and flags that
>    Irvine's checklist still cites Gov Code 65852.2, which the state renumbered to 66310 to
>    66342.
> 3. Timeline: creates a project and shows the six approval steps in order (application
>    preparation, submission through the IrvineReady! portal, completeness review, plan check
>    fee payment, plan review, permit issuance), who acts at each one, bottlenecks and sources. It shows no finish date because no reviewed durations exist, and
>    calculates no legal deadlines.
> 4. Projects: the API saves several projects and refuses out-of-order steps; housing types
>    without reviewed rules are saved as drafts marked "rule coverage unavailable".
>
> Rules live in a reviewed data file with citations, not in code, so adding a city or a
> project type is a data task: one manifest, checked by a person, published with one command.

**Sources and assumptions**

> City of Irvine: ADU construction guide page; ADU application package (2025 update);
> Development Standards Checklist (Form 67-01); Hold Harmless Affidavit (Form 67-02, title
> only); Pre-Approved ADU Plans page (list says "coming soon", so we list no plans); Fee
> Schedule (no fee amounts entered); AB 2234 building permit page. State: HCD ADU Handbook
> (March 2026), which cites Gov Code 66317 for completeness and decision timing. We could not
> open the statute text on leginfo, so the app shows that clock as guidance and calculates no
> legal due dates. 9 sources, 29 hand-checked excerpts, all checked November 7, 2026.
>
> Assumptions: the four-year baseline and the $85k-of-$535k time cost come from the event
> brief's rounded example (timeline.json) and are labeled ASSUMPTION. No duration estimates were
> added; the app shows none. The demo project is a made-up scenario (C01), not a real applicant.

**Public repo URL:** `https://github.com/Arthur-Systems/claude-impact`

**Video:** upload the MP4 on the form. Backup: YouTube unlisted link.

**Live demo URL:** leave blank (runs locally; see README Try it)

---

## 2. README

Done. `README.md` on main is filled in to match what shipped: header, what we built, how
Claude is used, Try it, real vs mocked, where it gets things wrong, next steps, data and
privacy. Edit it there directly; this section no longer holds a copy.

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
- Use the C01 facts (detached ADU, existing house). The "needs information" items come from recorded source conflicts (for example the Hold Harmless Affidavit), not from floor area: no reviewed rule uses floor area yet.
- Screen recorder: macOS `Cmd+Shift+5`, record selected portion, 1080p. Mic: a phone held
  close in a quiet hallway gives cleaner audio than a laptop mic in the room.
- Do 1 rehearsal, then 2 takes. Keep the better one. No editing beyond trimming the ends.

### 60-second script

| Time | Screen | Narration |
|---|---|---|
| 0:00 to 0:07 | Irvine ADU page, application PDF and HCD handbook open in three tabs | "Adding an ADU in Irvine means piecing together a city web page, a long PDF package, separate checklists and the state handbook." |
| 0:07 to 0:15 | ClearPath Documents tab with the live-data banner; Irvine, detached ADU, existing house | "For a detached ADU next to an existing house in Irvine, ClearPath pulls the city's own requirements." |
| 0:15 to 0:28 | Checklist appears. Click one citation chip; show URL, page, excerpt, date checked | "Every item is the city's own requirement, linked to the exact page and passage, with the date we checked it." |
| 0:28 to 0:36 | Point at an item marked needs information | "Where the city's own sources disagree, it says needs information and shows both sources. It does not guess." |
| 0:36 to 0:44 | The development standards checklist item and its conflict note | "It also flags stale law: Irvine's checklist still cites Gov Code 65852.2, which the state renumbered to 66310 and up." (Listed under source conflicts on the Documents tab.) |
| 0:44 to 0:54 | Timeline tab with the live banner: six steps in order, who acts at each step, bottlenecks and source chips | "The timeline shows every approval step in order, who acts, and what's holding the project up, each with its source." |
| 0:54 to 1:00 | The repo README with the URL on screen | "Each new city or project type is one reviewed data file. ClearPath, Lane 2." |

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
2. **Lookup (25 s).** Open Documents with the C01 facts (detached ADU, existing house). "Two facts,
   and it pulls Irvine's own list."
3. **Checklist and sources (40 s).** Open a citation chip. Read the excerpt aloud. "Every item
   shows where it came from and when we checked it. If we can't cite it, it doesn't appear."
   Point at "needs information".
4. **Honesty layer (25 s).** Warnings bar. "Property not verified, because we only chose the
   city. The state completeness clock is shown as guidance: we couldn't open the statute text
   today, so the app doesn't compute a legal deadline."
5. **Timeline (35 s).** Open the Timeline tab: six steps in order, who acts at each one (city
   or applicant), bottlenecks and source chips. "No finish date, because no reviewed source
   gives one. It will not invent a deadline."
6. **Scale (25 s).** Open `backend/data/irvine_adu/manifest.json` briefly. "A new city is this file: sources, excerpts, rules, steps, reviewed
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
