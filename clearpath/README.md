# ClearPath frontend (starter)

## Run it
1. Install Node 18.17 or newer (check with `node -v`).
2. In this folder run:
   npm install
   npm run dev
3. Open http://localhost:3000

## What works right now
- Sidebar navigation across all six tabs
- Overview and Documents pages are fully working
- Documents accepts individual PDFs/images and standard ZIPs. This is filename-only demo matching, not OCR, form validation, completeness review, or city acceptance. Use fictional files only.
- With the API configured, Documents matches the live requirement keys, shows per-file activity and Received chips, and sequentially saves self-reported checklist status to the same project used by Timeline. Legal Unknown/source conflicts remain unchanged.
- Receipt metadata is scoped to the project in this browser. Reloading restores receipts; API failures stay visibly browser-only. Reset clears local receipts and selects a fresh project on next use without deleting old API history.
- Without the backend, ZIP entry names feed the existing labeled mock matcher. Only that mock state updates the Overview and nav badge.
- Download the fictional staged samples in Documents: stage 1 receives 3 of 10 requirements, stage 2 reaches 7 of 10 plus unmatched Site_Photos.pdf, and stage 3 reaches 10 of 10. The all-in-one ZIP contains the same 11 PDFs. Duplicates do not increase the live requirement count.
- Overview has a working map: type an address and a pin is placed (OpenStreetMap, no API key)
- Navigator: chat with suggested questions and a step by step guide that updates from your uploads
- Search: search sourced Irvine and California entries plus your uploaded file names
- Timeline: two approval paths, with a dropdown for how long missing documents take
- Ask the City: opens an email to the Irvine Planning Team and tracks your questions

## How it is organized
- app/            One folder per page. app/documents/page.tsx is the /documents page.
- app/layout.tsx  The frame around every page (sidebar plus content).
- app/globals.css All colors and styles. Colors are CSS variables at the top.
- components/     Small reusable pieces: Sidebar, PageHeader, MapPlaceholder.
- lib/project-context.tsx
                  The shared state (uploaded files, what is missing).
                  This is the file to connect to the backend.

## Where the backend plugs in
lib/backend.ts connects the live checklist and shared project identity to the API.
lib/docmatch.ts matches filenames only against keys returned by that checklist.
lib/zip.ts reads bounded ZIP central-directory names locally without extracting PDF contents.
lib/project-context.tsx retains the separate mock matcher for backend-off demos.
No model, OCR service, or document-content upload is involved.

## Add the Orange County logo
Save the official logo as public/oc-logo.png. It shows in the sidebar on a
white plate. Until the file exists, a plain text label shows instead.

## Connect to the backend
Copy .env.local.example to .env.local and set NEXT_PUBLIC_API_URL and NEXT_PUBLIC_API_KEY.
Start the backend with CLEARPATH_API_KEY set to the same key and CLEARPATH_CORS_ORIGINS=http://localhost:3000.
Documents then shows the live Irvine checklist with sources, and Timeline shows live milestones.
If the API is off or the variables are unset, both pages show demo data and say so in a banner.

## Connect the Navigator to the backend (optional)
Create a file named .env.local with:
   NEXT_PUBLIC_API_URL=http://localhost:8000
The Navigator then sends POST /api/navigator with { question, context }
and expects { answer, sources: [{ label, url }] }. If the backend is off,
the demo answers in lib/api.ts are used and labeled as demo answers.

## Where the numbers come from
lib/timeline.ts: the 60 day and 15 business day limits are state law
(California Gov. Code 66317). The 4 day completeness check is an assumption
based on Irvine saying it takes about two business days. Edit it there.

## Verification and fictional samples
From this folder, run `node --experimental-strip-types scripts/check-demo-zips.ts`
and `node --experimental-strip-types scripts/check-demo-state.ts` with a Node version
supporting type stripping (Node 22.6+), then `npm run build`.
Regenerate the four sample ZIPs with `python3 scripts/make_demo_docs.py`.
Processing pauses about 350 ms per entry for demo visibility, not a permit duration.
Only receipt status and requirement keys are sent to the API, never document bytes.

## Still to do
Real OCR matching, pgvector search in place of lib/knowledge.ts, and
checking the document checklist against Irvine's official submittal list.
