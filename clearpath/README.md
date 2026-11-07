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
- Upload files on Documents: each file is matched to a required document by its file name (try site_plan.pdf, floor_plan.pdf, structural.pdf, or vacation.pdf)
- Unmatched files show up under "Needs your attention"
- The Overview, the nav badge, and the checklist all update together
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
In lib/project-context.tsx, guessMatch() is a mock that looks at file names.
Replace it with a call to the FastAPI endpoint that runs OCR and Claude,
and have it return the matched document type and a confidence level.

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

## Still to do
Real OCR matching, pgvector search in place of lib/knowledge.ts, and
checking the document checklist against Irvine's official submittal list.
